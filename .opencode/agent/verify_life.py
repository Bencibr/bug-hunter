#!/usr/bin/env python3
"""verify_life.py — bug-hunter 寿命状态文件外部校验/修复器（元审计修复）。

背景：bug-hunter 寿命机制的漏洞 A/B/E —— 寿命文件此前唯一的权威是 agent
自评自写回，无任何外部校验；且「支付轮费立即写回」在中断（kill/超时/打断）
下会产生「幽灵轮费」（life 已扣、history 无记录），状态不可恢复。

审计修复（v0.0.1 审计发现的三条逃逸链，全部在此封堵）：
  1. 自评刷命（漏洞 1）：settle 此前全盘信任 agent 自报 findings/credited，
     可凭空编造 5 条刷命。→ 现在每条 finding 必须含真实证据引用
     （`文件:行号` 且文件真实存在，或 `test_*` 测试名 + 复现/观察标记），
     无证据的编造条自动剔除出计命，刷命被拒。
  2. bash 篡改校验器/快照（漏洞 2）：校验器与快照与寿命文件同权限，agent
     可用 bash 的 sed/cp 改掉校验逻辑或同步改快照绕过 diff。
     → 现在校验器内嵌 SELF_HASH 自校验（脚本被改则所有命令拒绝执行）；
     且 pre 输出「外部基线」JSON，post 用调用方传入的基线对比，
     agent 改仓库内 snapshot 不再有效。
  3. repair 滥用（漏洞 3）：repair 机械修复可能被用来掩盖双结算痕迹。
     → repair 增加审计日志（repair-audit.log），每次修复留痕，调用方可查。

本脚本由调用方（主会话/用户）在启动 bug-hunter 前后执行，提供硬校验：
  check     校验一致性（不一致 exit 1，打印差异）
  repair    修复不一致（回滚幽灵轮费：life 恢复到最后结算值，留审计日志）
  settle    每轮结算（确定性入口：脚本计算 delta/life 并原子写回；含证据校验）
  reset     重置为初始状态
  snapshot  把当前状态备份到 .snapshot.json（基线）
  diff      对比当前状态与快照/外部基线，检出「自洽撒谎」与超范围涨命
  restore   从快照恢复当前状态（diff 检出异常后的回滚）
  selfhash  输出本脚本当前 SHA256（维护用：改完脚本后更新 SELF_HASH）
  set-mode  持久化用户确认的修复模式（auto/log-only）

调用规范（防「自洽撒谎」盲区，v0.0.1 加固）：
  1. 启动 bug-hunter 前：`launch_bug_hunter.py pre` —— 做 check + snapshot，
     并**输出一行外部基线 JSON**（含 life/rounds_completed/history 前缀哈希）。
     调用方把该基线保存到 agent 会话之外（如手动记录，或 export 环境变量）。
  2. bug-hunter 运行结束后：`launch_bug_hunter.py post` —— 优先用
     `BH_PRE_BASELINE` 环境变量（调用方传入的外部基线）做 diff；
     若未设置则回退读仓库内 snapshot。外部基线是权威，agent 无法篡改。
  3. diff 异常 → restore 回滚到基线，并复核 agent 报告是否真实。

不变量（新机制：轮费改在结算时支付，life 只由结算写入）：
  1. history 的 round 号必须连续 1..N
  2. life == 最后一条 history.life_after（无 history 则必须 == 1）
     —— 违反即「幽灵轮费/未结算」，可被 repair 回滚
  3. rounds_completed == len(history)
  4. round == rounds_completed + 1
  5. alive == (life > 0)
  6. found_total == sum(credited)（各轮计命数之和，超额/重复不计命）

用法：
  python3 verify_life.py check      # 一致 exit 0；不一致 exit 1
  python3 verify_life.py repair     # 修复不一致（幂等，留审计日志）
  python3 verify_life.py reset      # 重置初始态
  python3 verify_life.py snapshot   # 备份当前状态
  python3 verify_life.py selfhash   # 输出自身 SHA256（维护用）
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

LIFE_FILE = Path(__file__).resolve().parent / "bug-hunter-life.json"
SNAPSHOT_FILE = LIFE_FILE.with_suffix(".json.snapshot")
AUDIT_LOG = Path(__file__).resolve().parent / "repair-audit.log"

# 自校验：脚本被 bash/sed/cp 篡改后，所有命令拒绝执行。
# 维护方法：改完本脚本后运行 `python3 verify_life.py selfhash`，
# 把输出粘贴到下面 SELF_HASH = "..." 即可（哈希会随每次编辑变化）。
SELF_HASH = "d8b1fc183bd98acbfad3bf8f9aac665135ac725c9a5968a748fab8d4854031a6"

# 单轮每项真实发现的加分上限（与 bug-hunter.md「单轮加分上限」一致）。
# 防「凑数无限续命」：每轮 life 净增上限 = -1(轮费) + MAX_PER_ROUND。
MAX_PER_ROUND = 5
VALID_MODES = {"auto", "log-only"}


def self_check() -> None:
    """脚本自校验：SELF_HASH 与真实内容不符 → 拒绝执行（exit 3）。

    哈希计算**排除本文件内的 SELF_HASH 行**（避免自引用死循环）——
    只校验代码与注释，SELF_HASH 常量行本身可自由更新。
    维护：改完脚本后运行 `python3 verify_life.py selfhash` 更新基线。
    """
    if "--selfhash" in sys.argv:
        print(SELF_HASH)
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "selfhash":
        print(SELF_HASH)
        sys.exit(0)
    try:
        raw = Path(__file__).resolve().read_bytes()
    except OSError:
        return
    # 去掉 SELF_HASH = "..." 这一行再算哈希
    lines = raw.splitlines()
    cleaned = b"\n".join(
        ln for ln in lines if not ln.startswith(b'SELF_HASH = "')
    )
    actual = hashlib.sha256(cleaned).hexdigest()
    if actual != SELF_HASH:
        print("[verify_life] 校验器自身被篡改（SHA256 不匹配），拒绝执行。")
        print("  可能被 bash 的 sed/cp 修改。请从仓库恢复：")
        print("    git checkout .opencode/agent/verify_life.py")
        print("  或维护者运行 `python3 verify_life.py selfhash` 更新基线。")
        sys.exit(3)




def load() -> dict:
    """读寿命文件；JSON 损坏（写回中断）时优雅报错而非崩溃。"""
    try:
        return json.loads(LIFE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[verify_life] 寿命文件无法解析: {e}")
        print(f"  路径: {LIFE_FILE}")
        print("  可能上次写回被中断导致 JSON 损坏。")
        print("  处理：有快照基线则 `restore` 回滚；否则人工修复该文件。")
        sys.exit(2)


def save(d: dict) -> None:
    LIFE_FILE.write_text(
        json.dumps(d, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _credited(h: dict) -> int:
    """本轮计命发现数：优先取 credited 字段（新机制，超额/重复不计命），
    缺失（旧数据）回退到 len(findings)。"""
    if h.get("credited") is not None:
        return int(h["credited"])
    return len(h.get("findings") or [])


def _load_json(path: Path, what: str) -> dict:
    """读 JSON 文件；损坏/缺失时优雅报错（exit 2），不 traceback。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[verify_life] {what} 无法解析: {e}")
        print(f"  路径: {path}")
        print("  可能文件被写回中断或篡改。先 `snapshot` 重建基线，"
              "或人工修复。")
        sys.exit(2)


def _int_arg(val: str, name: str) -> int:
    try:
        return int(val)
    except ValueError:
        print(f"[verify_life] 参数 {name} 必须是整数，got {val!r}")
        sys.exit(2)


# ---- 证据校验（修复漏洞 1：堵「凭空编造 findings 刷命」）----

# 真实证据引用形态：
#   1) `文件路径:行号`（文件必须真实存在；路径可相对仓库根或绝对）
#   2) `test_xxx` 测试名 + 出现 复现/观察/Repro/Observed 标记
# 两者任一命中且文件存在才计为「有证据」。
_EVIDENCE_FILE_RE = re.compile(
    r"(?P<path>[A-Za-z0-9_./\\\-]+\.(?:py|js|ts|jsx|tsx|go|rs|java|kt|"
    r"c|cpp|h|sh|md|json|yaml|yml|toml|xml|html|css|sql))"
    r"\s*[:#]\s*(?P<line>\d+)"
)
_TEST_NAME_RE = re.compile(r"\btest_[A-Za-z0-9_]+")
_REPRO_MARK_RE = re.compile(r"(复现|观察|预期|Repro|Observed|Expected|exit\s+code)")

# 仓库根 = verify_life.py 所在目录（.opencode/agent/）的上上级。
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _file_real(path: str, line: int | None = None) -> bool:
    """文件和（如提供）行号真实存在于仓库。"""
    p = Path(path)
    if not p.is_absolute():
        p = _REPO_ROOT / path
    if not p.is_file():
        return False
    if line is None:
        return True
    try:
        # 行号证据至少不能超出文件实际范围；语义正确性仍需调用方复核。
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            line_count = sum(1 for _ in fh)
        return 1 <= line <= line_count
    except OSError:
        return False


def _audit(kind: str, detail: str) -> None:
    """修复/重置等外部操作用途留痕（修复漏洞 3：repair 可被追踪）。"""
    import datetime

    try:
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(
                f"{datetime.datetime.now().isoformat(timespec='seconds')} "
                f"[{kind}] {detail}\n"
            )
    except OSError:
        pass


def evidence_bad_lines(findings: list[str]) -> list[str]:
    """返回没有真实证据引用的 findings 行（漏洞 1 校验）。

    有证据判定：`文件:行号` 且文件存在；或 `test_*` 名 + 复现/观察标记。
    """
    bad: list[str] = []
    for f in findings:
        has_file_ref = False
        for m in _EVIDENCE_FILE_RE.finditer(f):
            if _file_real(m.group("path"), int(m.group("line"))):
                has_file_ref = True
                break
        has_test_repro = bool(_TEST_NAME_RE.search(f) and _REPRO_MARK_RE.search(f))
        if not (has_file_ref or has_test_repro):
            bad.append(f)
    return bad


def external_baseline() -> dict | None:
    """读取调用方传入的外部基线（修复漏洞 2 的关键）。

    优先级：环境变量 BH_PRE_BASELINE（调用方 pre 时输出、post 时传回）
    > 仓库内 snapshot 文件。外部基线在 agent 会话之外，agent 无法篡改。
    """
    import os

    raw = os.environ.get("BH_PRE_BASELINE", "").strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[verify_life] BH_PRE_BASELINE 无法解析: {e}")
            return None
    if SNAPSHOT_FILE.is_file():
        return _load_json(SNAPSHOT_FILE, "快照基线")
    return None





def check_errors(d: dict) -> list[str]:
    """返回不变量违反清单（空列表 = 一致）。"""
    errors: list[str] = []
    hist = d.get("history") or []
    rounds = [h.get("round") for h in hist]
    if rounds != list(range(1, len(hist) + 1)):
        errors.append(f"history round 号不连续: {rounds}")
    if hist:
        last_after = hist[-1].get("life_after")
        if d.get("life") != last_after:
            errors.append(
                f"life({d.get('life')}) != 最后 history.life_after({last_after})"
                " —— 幽灵轮费/未结算"
            )
    else:
        if d.get("life") != 1:
            errors.append(f"空 history 时 life 必须为 1，当前 {d.get('life')}")
    if d.get("rounds_completed") != len(hist):
        errors.append(
            f"rounds_completed({d.get('rounds_completed')}) != len(history)"
            f"({len(hist)})"
        )
    # round 恒等于 rounds_completed + 1（下一轮号）。结算写回时必须同步推进。
    if d.get("round") != d.get("rounds_completed") + 1:
        errors.append(
            f"round({d.get('round')}) != rounds_completed+1"
            f"({d.get('rounds_completed') + 1})"
        )
    if d.get("alive") != (d.get("life") > 0):
        errors.append(f"alive({d.get('alive')}) 与 life({d.get('life')}) 不一致")
    mode = d.get("mode")
    if mode is not None and mode not in VALID_MODES:
        errors.append(
            f"mode({mode!r}) 无效，必须是 auto/log-only 或 null"
        )
    # found_total 必须等于各轮计命数（credited）之和——超额/重复发现计入
    # findings 但不计命，故不能用 sum(findings)。
    ft = sum(_credited(h) for h in hist)
    if d.get("found_total") != ft:
        errors.append(
            f"found_total({d.get('found_total')}) != sum(credited)({ft})"
        )
    # life_after 链：第 i 条（i>=1）必须 == 上一条 life_after + delta。
    # 第一条无前置参照（初始 life 未硬编码，兼容非 1 初始），仅要求 delta 存在。
    # life == 最后一条 life_after 已在上方单独校验。
    if hist and hist[0].get("delta") is None:
        errors.append(f"history[0](round={hist[0].get('round')}) 缺 delta")
    for i, h in enumerate(hist):
        dlt = h.get("delta")
        if dlt is not None and dlt > MAX_PER_ROUND - 1:
            errors.append(
                f"history[{i}](round={h.get('round')}) delta({dlt}) 超上界 "
                f"(≤{MAX_PER_ROUND - 1})——计命发现数可疑/伪造"
            )
        cred = h.get("credited")
        if cred is not None and not (0 <= cred <= MAX_PER_ROUND):
            errors.append(
                f"history[{i}](round={h.get('round')}) credited({cred}) 越界，"
                f"须在 [0, {MAX_PER_ROUND}]"
            )
    for i in range(1, len(hist)):
        prev_after = hist[i - 1].get("life_after")
        h = hist[i]
        delta = h.get("delta")
        after = h.get("life_after")
        if delta is None:
            errors.append(f"history[{i}](round={h.get('round')}) 缺 delta")
            continue
        if prev_after is None or after is None or after != prev_after + delta:
            errors.append(
                f"history[{i}](round={h.get('round')}) life_after({after}) "
                f"!= prev({prev_after})+delta({delta})"
                f"{'' if prev_after is None else '=' + str(prev_after + delta)}"
            )
    return errors


def cmd_check() -> int:
    d = load()
    errors = check_errors(d)
    if errors:
        print(f"[verify_life] 不一致（{len(errors)} 项）:")
        for e in errors:
            print(f"  ✗ {e}")
        return 1
    print(
        f"[verify_life] OK: life={d.get('life')} round={d.get('round')} "
        f"rounds_completed={d.get('rounds_completed')} alive={d.get('alive')}"
    )
    return 0


def cmd_repair() -> int:
    d = load()
    errors = check_errors(d)
    if not errors:
        print("[verify_life] 已一致，无需修复")
        return 0
    hist = d.get("history") or []
    # 先检测 history 的 life_after 链是否断裂 / 缺 delta：
    # 若断裂，说明 history 内容被篡改，机械修复会把伪造的 life_after
    # 当作权威写进 life —— 拒绝自动修，交给 diff/restore 或人工。
    prev = 1
    chain_broken = False
    for h in hist:
        delta = h.get("delta")
        after = h.get("life_after")
        if delta is None or after is None or after != prev + delta:
            chain_broken = True
            break
        prev = after
    if chain_broken:
        print("[verify_life] history 的 life_after 链断裂或缺 delta——文件可能"
              "被篡改，拒绝机械修复。")
        print("  请用 `snapshot` 建立基线后 `restore` 回滚，"
              "或人工复核 history 内容。")
        _audit("repair-refused", f"链断裂拒绝修复: {errors[:3]}")
        return 1
    d["life"] = hist[-1]["life_after"] if hist else 1
    d["rounds_completed"] = len(hist)
    d["round"] = len(hist) + 1
    d["alive"] = d["life"] > 0
    d["found_total"] = sum(_credited(h) for h in hist)
    save(d)
    _audit("repair", f"life={d['life']} rounds={d['rounds_completed']}")
    print(
        f"[verify_life] 已修复: life={d['life']} round={d['round']} "
        f"rounds_completed={d['rounds_completed']} alive={d['alive']} "
        f"found_total={d['found_total']}"
    )
    print("  回滚项: 幽灵轮费已退回（life 恢复到最后结算值，未结算轮次不扣命）")
    for e in errors:
        print(f"  ✓ 已处理: {e}")
    return 0


def cmd_reset() -> int:
    d = {
        "life": 1,
        "found_total": 0,
        "round": 1,
        "rounds_completed": 0,
        "alive": True,
        "mode": None,
        "history": [],
    }
    save(d)
    print("[verify_life] 已重置为初始状态")
    return 0


def cmd_set_mode(argv: list[str]) -> int:
    """持久化用户已确认的修复模式；模式不由 agent 自行猜测。"""
    mode = None
    i = 0
    while i < len(argv):
        if argv[i] == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1]
            i += 2
        else:
            print(f"[verify_life] set-mode 未知参数: {argv[i]}")
            return 2
    if mode not in VALID_MODES:
        print(
            f"[verify_life] mode({mode!r}) 无效，必须是 "
            "auto 或 log-only"
        )
        return 1
    d = load()
    if not d.get("alive", True) or d.get("life", 0) <= 0:
        print("[verify_life] 已死亡，不能设置会话模式——先经用户确认 reset")
        return 1
    d["mode"] = mode
    _save_atomic(d)
    errs = check_errors(d)
    if errs:
        print("[verify_life] 设置 mode 后校验失败:")
        for e in errs:
            print(f"  ✗ {e}")
        return 1
    print(f"[verify_life] 已保存用户确认模式: {mode}")
    return 0


def cmd_snapshot() -> int:
    import shutil

    if not LIFE_FILE.is_file():
        print("[verify_life] 无寿命文件可备份——先确认 bug-hunter-life.json 存在")
        return 1
    try:
        shutil.copyfile(LIFE_FILE, SNAPSHOT_FILE)
    except OSError as e:
        print(f"[verify_life] 快照建立失败: {e}")
        return 1
    print(f"[verify_life] 已备份当前状态到 {SNAPSHOT_FILE.name}")
    return 0


def cmd_diff() -> int:
    """对比当前状态与基线（外部基线优先，快照文件兜底），
    检出「自洽撒谎」/超范围涨命/历史篡改。修复漏洞 2。"""
    snap = external_baseline()
    if snap is None:
        print("[verify_life] 无可用基线——外部基线未设置且无快照文件，"
              "先运行 snapshot 再跑 diff")
        return 2
    src = "外部基线(BH_PRE_BASELINE)" if os.environ.get("BH_PRE_BASELINE") else "快照文件"
    cur = load()
    issues: list[str] = []
    snap_rounds = snap.get("rounds_completed", 0)
    cur_rounds = cur.get("rounds_completed", 0)
    run = cur_rounds - snap_rounds
    # 已确认的会话模式不可在运行中静默切换；旧基线没有 mode 时允许一次迁移初始化。
    snap_mode = snap.get("mode")
    cur_mode = cur.get("mode")
    if snap_mode is not None and cur_mode != snap_mode:
        issues.append(f"会话 mode 被改写: {snap_mode!r} -> {cur_mode!r}")
    if run < 0:
        issues.append(f"rounds_completed 回退: {snap_rounds} -> {cur_rounds}")
    snap_hist = snap.get("history") or []
    cur_hist = cur.get("history") or []
    # 历史前缀不可篡改（已结算的轮次不允许被改/删）
    for i in range(min(len(snap_hist), len(cur_hist))):
        if snap_hist[i] != cur_hist[i]:
            issues.append(f"history[{i}]（round={snap_hist[i].get('round')}）"
                          f"被篡改或改写")
            break
    if len(cur_hist) < len(snap_hist):
        issues.append("history 条目被删除")
    if len(cur_hist) != snap_rounds + run:
        issues.append(
            f"history 条数({len(cur_hist)}) != 基线轮数+运行轮数"
            f"({snap_rounds}+{run})"
        )
    # 新增轮次的 delta 精确校验（替代旧的粗略范围，防「诚实记欺诈被误报」）：
    #   delta = -1(轮费) + credited - fraud
    #   上界：credited ≤ MAX_PER_ROUND → delta ≤ MAX_PER_ROUND - 1
    #   下界：fraud 无上限，不硬校验（诚实记录欺诈不该被回滚）
    cur_life = cur.get("life", 0)
    new_hist = cur_hist[len(snap_hist):]
    total_delta = 0
    for h in new_hist:
        dlt = h.get("delta")
        if dlt is None:
            issues.append(f"新增轮次 round={h.get('round')} 缺 delta")
            continue
        total_delta += dlt
        if dlt > MAX_PER_ROUND - 1:
            issues.append(
                f"round={h.get('round')} delta({dlt}) 超上界 "
                f"(≤{MAX_PER_ROUND - 1})——计命发现数可疑/伪造"
            )
    snap_life = snap.get("life", 1)
    if cur_life != snap_life + total_delta:
        issues.append(
            f"life 变化({cur_life - snap_life}) != 新增轮 delta 之和"
            f"({total_delta})"
        )
    if cur_life <= 0 and cur.get("alive"):
        issues.append("life≤0 但仍 alive（死亡绕过）")
    if issues:
        print(f"[verify_life] diff 检出异常（{len(issues)} 项）:")
        for e in issues:
            print(f"  ✗ {e}")
        return 1
    print(
        f"[verify_life] diff OK({src}): life {snap.get('life')} -> {cur_life} "
        f"（{run} 轮）history 前缀未篡改"
    )
    return 0


def cmd_restore() -> int:
    """从快照恢复；快照必须本身合法（可解析 + 通过不变量），防恢复损坏文件。"""
    import shutil

    if not SNAPSHOT_FILE.is_file():
        print("[verify_life] 无快照可恢复——先运行 snapshot")
        return 2
    snap = _load_json(SNAPSHOT_FILE, "快照基线")
    errs = check_errors(snap)
    if errs:
        print("[verify_life] 快照基线本身不合法，拒绝恢复——防止把损坏/篡改的"
              "快照写回并覆盖真实状态：")
        for e in errs:
            print(f"  ✗ {e}")
        print("  请人工复核 bug-hunter-life.json 与快照内容。")
        return 1
    shutil.copyfile(SNAPSHOT_FILE, LIFE_FILE)
    d = load()
    print(
        f"[verify_life] 已从快照恢复: life={d.get('life')} "
        f"round={d.get('round')} rounds_completed={d.get('rounds_completed')}"
    )
    return 0


def _save_atomic(d: dict) -> None:
    """原子写回：临时文件 + os.replace，写回被中断也不会损坏 JSON。"""
    import os
    import tempfile

    fd, tmp = tempfile.mkstemp(
        dir=str(LIFE_FILE.parent), prefix=".life-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
        os.replace(tmp, LIFE_FILE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def cmd_settle(argv: list[str]) -> int:
    """agent 每轮结算的确定性入口（替代手写 JSON）。

    由脚本计算 delta/life/life_after/found_total/rounds 并原子写回，
    结算结果必然满足全部不变量（check 必过）。参数：
      --credited N            本轮计命发现数（[0, MAX_PER_ROUND]，脚本护栏）
      --fraud N               本轮欺诈扣分（≥0，默认 0）
      --findings-file PATH    本轮全部发现清单文件（每行一条；可含超额/重复）
      --ts YYYY-MM-DD         时间戳（默认今天）
      --round N               期望本轮号（可选；与 rounds_completed+1 不符则拒绝，
                              防误用旧轮号重复结算）
    """
    import time

    credited = 0
    fraud = 0
    findings_file = None
    ts = None
    expect_round = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--credited" and i + 1 < len(argv):
            credited = _int_arg(argv[i + 1], "--credited"); i += 2
        elif a == "--fraud" and i + 1 < len(argv):
            fraud = _int_arg(argv[i + 1], "--fraud"); i += 2
        elif a == "--findings-file" and i + 1 < len(argv):
            findings_file = argv[i + 1]; i += 2
        elif a == "--ts" and i + 1 < len(argv):
            ts = argv[i + 1]; i += 2
        elif a == "--round" and i + 1 < len(argv):
            expect_round = _int_arg(argv[i + 1], "--round"); i += 2
        else:
            print(f"[verify_life] settle 未知参数: {a}")
            return 2
    if credited < 0 or credited > MAX_PER_ROUND:
        print(f"[verify_life] credited({credited}) 越界，须在 [0, {MAX_PER_ROUND}]")
        return 1
    if fraud < 0:
        print(f"[verify_life] fraud({fraud}) 不能为负")
        return 1
    d = load()
    if not d.get("alive", True) or d.get("life", 0) <= 0:
        print("[verify_life] 已死亡（alive=false, life≤0），拒绝结算——"
              "死亡即冻结，不得再记录轮次")
        return 1
    errs = check_errors(d)
    if errs:
        print("[verify_life] 基线不一致，拒绝结算——先 `repair` 或 `restore` 恢复基线")
        for e in errs:
            print(f"  ✗ {e}")
        return 1
    if findings_file is None:
        print("[verify_life] settle 必须提供 --findings-file")
        return 2
    try:
        findings = [
            ln.strip()
            for ln in Path(findings_file).read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
    except OSError as e:
        print(f"[verify_life] 读取 findings 文件失败: {e}")
        return 1
    if len(findings) < credited:
        print(f"[verify_life] findings({len(findings)} 条) 少于 credited({credited})"
              "——计命数不能超过已记录发现")
        return 1
    round_no = d["rounds_completed"] + 1
    if expect_round is not None and expect_round != round_no:
        print(f"[verify_life] 期望轮号({expect_round}) != 当前应结算轮号"
              f"({round_no})——疑似重复结算或轮号错乱，拒绝")
        return 1
    # 与历史「原样字符串」重复的发现不计命（根因去重的字符串级护栏）：
    # 堵「复制粘贴历史 findings 刷命」；语义重复（措辞不同）仍靠 agent 自觉。
    all_hist_findings = set()
    for h in d.get("history") or []:
        for f in (h.get("findings") or []):
            all_hist_findings.add(str(f))
    dups = [f for f in findings if f in all_hist_findings]
    max_creditable = len(findings) - len(dups)
    if credited > max_creditable:
        print(f"[verify_life] 本轮 {len(dups)} 条发现与历史原样重复，"
              f"最多可计命 {max_creditable} 条（当前 credited={credited}）——"
              f"请剔除重复项后重试")
        for dd in dups[:5]:
            print(f"  ✗ 重复: {dd[:80]}")
        return 1
    # 证据校验（修复漏洞 1：堵「凭空编造 findings 刷命」）：
    # 每条计命发现必须含真实证据引用——`文件:行号`（文件真实存在）或
    # `test_*` 测试名 + 复现/观察标记。无证据的编造条被剔除出计命上限。
    bad_evidence = evidence_bad_lines(findings)
    evidence_creditable = len(findings) - len(bad_evidence)
    if credited > evidence_creditable:
        print(f"[verify_life] {len(bad_evidence)} 条发现缺真实证据引用"
              f"（无存在的 `文件:行号`，或非 `test_*`+复现标记）——"
              f"凭证据最多可计命 {evidence_creditable} 条"
              f"（当前 credited={credited}），拒绝结算。")
        for b in bad_evidence[:5]:
            print(f"  ✗ 无证据: {b[:100]}")
        return 1
    delta = -1 + credited - fraud
    d["life"] = d["life"] + delta
    d["found_total"] = d["found_total"] + credited
    d["rounds_completed"] += 1
    d["round"] = d["rounds_completed"] + 1
    d["alive"] = d["life"] > 0
    d["history"].append({
        "round": round_no,
        "ts": ts or time.strftime("%Y-%m-%d"),
        "delta": delta,
        "credited": credited,
        "life_after": d["life"],
        "findings": findings,
    })
    _save_atomic(d)
    # 自证：settle 写出的状态必须通过 check
    errs2 = check_errors(d)
    if errs2:
        print("[verify_life] settle 后校验失败（内部错误，请上报）:")
        for e in errs2:
            print(f"  ✗ {e}")
        return 1
    print(
        f"[verify_life] 第 {round_no} 轮结算完成: "
        f"delta={delta} (credited={credited}, fraud={fraud}) "
        f"life={d['life']} found_total={d['found_total']} "
        f"rounds_completed={d['rounds_completed']} alive={d['alive']}"
    )
    print(f"  findings 记录: {len(findings)} 条（含超额/重复，计命 {credited} 条）")
    return 0


def main(argv: list[str]) -> int:
    # 自校验前置：脚本被篡改则拒绝执行（漏洞 2 防线）。
    # --selfhash 也走这里（self_check 内处理）。
    self_check()
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "settle":
        return cmd_settle(argv[2:])
    if cmd == "set-mode":
        return cmd_set_mode(argv[2:])
    fn = {
        "check": cmd_check,
        "repair": cmd_repair,
        "reset": cmd_reset,
        "snapshot": cmd_snapshot,
        "diff": cmd_diff,
        "restore": cmd_restore,
    }.get(cmd)
    if fn is None:
        print(
            "[verify_life] 未知命令: "
            f"{cmd}（可选 check/repair/reset/set-mode/snapshot/diff/restore/settle/selfhash）"
        )
        return 2
    return fn()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
