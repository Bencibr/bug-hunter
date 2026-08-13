#!/usr/bin/env python3
"""verify_life.py — bug-hunter 寿命状态文件外部校验/修复器（元审计修复）。

背景：bug-hunter 寿命机制的漏洞 A/B/E —— 寿命文件此前唯一的权威是 agent
自评自写回，无任何外部校验；且「支付轮费立即写回」在中断（kill/超时/打断）
下会产生「幽灵轮费」（life 已扣、history 无记录），状态不可恢复。

本脚本由调用方（主会话/用户）在启动 bug-hunter 前后执行，提供硬校验：
  check     校验一致性（不一致 exit 1，打印差异）
  repair    修复不一致（回滚幽灵轮费：life 恢复到最后结算值）
  settle    每轮结算（确定性入口：脚本计算 delta/life 并原子写回）
  reset     重置为初始状态
  snapshot  把当前状态备份到 .snapshot.json（基线）
  diff      对比当前状态与快照，检出「自洽撒谎」（内部一致但篡改/超范围涨命）
  restore   从快照恢复当前状态（diff 检出异常后的回滚）

调用规范（防「自洽撒谎」盲区）：
  1. 启动 bug-hunter 前：check（确认基线一致）→ snapshot（记录真实基线）
  2. bug-hunter 运行结束后：diff（life 变化必须落在
     [基线 - 轮数, 基线 - 轮数 + 轮数×MAX_PER_ROUND]，history 前缀必须未被篡改）
  3. diff 异常 → restore 回滚到基线，并复核 agent 报告是否真实

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
  python3 verify_life.py repair     # 修复不一致（幂等）
  python3 verify_life.py reset      # 重置初始态
  python3 verify_life.py snapshot   # 备份当前状态
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LIFE_FILE = Path(__file__).resolve().parent / "bug-hunter-life.json"
SNAPSHOT_FILE = LIFE_FILE.with_suffix(".json.snapshot")

# 单轮每项真实发现的加分上限（与 bug-hunter.md「单轮加分上限」一致）。
# 防「凑数无限续命」：每轮 life 净增上限 = -1(轮费) + MAX_PER_ROUND。
MAX_PER_ROUND = 5


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
        return 1
    d["life"] = hist[-1]["life_after"] if hist else 1
    d["rounds_completed"] = len(hist)
    d["round"] = len(hist) + 1
    d["alive"] = d["life"] > 0
    d["found_total"] = sum(_credited(h) for h in hist)
    save(d)
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
        "history": [],
    }
    save(d)
    print("[verify_life] 已重置为初始状态")
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
    """对比当前状态与快照基线，检出「自洽撒谎」/超范围涨命/历史篡改。"""
    if not SNAPSHOT_FILE.is_file():
        print("[verify_life] 无快照基线——先运行 snapshot 再跑 diff")
        return 2
    snap = _load_json(SNAPSHOT_FILE, "快照基线")
    cur = load()
    issues: list[str] = []
    snap_rounds = snap.get("rounds_completed", 0)
    cur_rounds = cur.get("rounds_completed", 0)
    run = cur_rounds - snap_rounds
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
        f"[verify_life] diff OK: life {snap.get('life')} -> {cur_life} "
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
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "settle":
        return cmd_settle(argv[2:])
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
            f"{cmd}（可选 check/repair/reset/snapshot/diff/restore/settle）"
        )
        return 2
    return fn()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
