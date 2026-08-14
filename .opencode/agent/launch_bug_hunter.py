#!/usr/bin/env python3
"""launch_bug_hunter.py — bug-hunter 启动协议执行器（真实落地的外部防线）。

把「启动前检查 + 基线快照 + 结束后核对 + 异常回滚」固化为一条命令，
消除对「调用方记得手动跑」的依赖——外部防线不靠记忆，靠脚本。

用法：
  python3 launch_bug_hunter.py pre      # 启动前：check(失败先 repair) → snapshot
                                         #         → 打印启动指引（exit 非 0 = 基线不可用）
  python3 launch_bug_hunter.py post     # 结束后：diff + 准备记录 + 模块结构检查
  python3 launch_bug_hunter.py post --final  # 结束/死亡：额外要求 100% 模块覆盖
  python3 launch_bug_hunter.py status   # 当前状态一览 + 一致性 check

调用方流程（真实落地闭环）：
  1. python3 launch_bug_hunter.py pre
  2. 在 opencode 中用 Task 工具启动 bug-hunter（subagent_type=bug-hunter）
  3. python3 launch_bug_hunter.py post     # diff 异常会自动 restore 基线
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
VERIFY = AGENT_DIR / "verify_life.py"
MODULE_COVERAGE = AGENT_DIR / "module_coverage.py"
TOOLS_KB = AGENT_DIR / "tools_kb.py"
PREP_VALIDATE = AGENT_DIR / "prep_validate.py"


def _project_root() -> Path:
    """兼容正式 .opencode/agent 布局与隔离测试目录。"""
    if AGENT_DIR.parent.name == ".opencode":
        return AGENT_DIR.parent.parent
    return AGENT_DIR


def _run(*args: str) -> int:
    return subprocess.call([sys.executable, str(VERIFY), *args])


def _run_module_coverage(final: bool = False) -> int:
    """外部校验模块清单；覆盖门禁不能只由 agent 自报。"""
    if not MODULE_COVERAGE.is_file():
        print("[launch_bug_hunter] ✗ 缺少 module_coverage.py，拒绝通过覆盖门禁")
        return 1
    command = "final-check" if final else "check"
    return subprocess.call(
        [sys.executable, str(MODULE_COVERAGE), command,
         "--root", str(_project_root()),
         "--manifest", str(AGENT_DIR / "module-coverage.md")],
        cwd=str(_project_root()),
    )


def _run_tools_kb() -> int:
    """启动前拒绝使用过期/无日期工具知识。"""
    if not TOOLS_KB.is_file():
        print("[launch_bug_hunter] ✗ 缺少 tools_kb.py，无法验证工具知识有效期")
        return 1
    return subprocess.call(
        [sys.executable, str(TOOLS_KB), "check"],
        cwd=str(_project_root()),
    )


def _run_prep_validate() -> int:
    """结束前确认开工准备有可追溯记录。"""
    if not PREP_VALIDATE.is_file():
        print("[launch_bug_hunter] ✗ 缺少 prep_validate.py，拒绝通过准备门禁")
        return 1
    return subprocess.call(
        [sys.executable, str(PREP_VALIDATE),
         "--root", str(_project_root()),
         "--record", str(AGENT_DIR / "prep-record.md")],
        cwd=str(_project_root()),
    )


def pre() -> int:
    print("=" * 56)
    print("bug-hunter 启动前协议：校验基线 → 建立快照 → 输出外部基线")
    print("=" * 56)
    if _run_tools_kb() != 0:
        print("✗ tools-kb 存在过期/缺日期条目，先搜索更新后再启动")
        return 1
    if _run("check") != 0:
        print("→ 基线不一致，先 repair 恢复…")
        if _run("repair") != 0:
            print("✗ repair 无法自动修复（可能 history 被篡改），基线不可用。")
            print("  请人工复核 bug-hunter-life.json，或 reset 后重建。")
            return 1
        if _run("check") != 0:
            print("✗ repair 后仍不一致，基线不可用。")
            return 1
        print("✓ 基线已修复")
    if _run("snapshot") != 0:
        print("✗ 快照建立失败")
        return 1
    print("-" * 56)
    print("✓ 基线就绪。现在在 opencode 中用 Task 工具启动 bug-hunter：")
    print("    subagent_type: bug-hunter")
    print("  运行结束后执行：python3 launch_bug_hunter.py post")
    print()
    print("  防篡改外部基线（复制下面 export 行，agent 结束后在 post 前执行，")
    print("  或手动传给 post——agent 无法篡改外部基线）：")
    baseline = _baseline_json()
    if baseline:
        import json as _json

        escaped = _json.dumps(baseline, ensure_ascii=False)
        print(f"  export BH_PRE_BASELINE='{escaped}'")
    return 0


def post(final: bool = False) -> int:
    print("=" * 56)
    print("bug-hunter 结束协议：核对 life 变化 → 异常回滚")
    print("=" * 56)
    if _run("diff") != 0:
        print("→ diff 检出异常，回滚到基线快照…")
        _run("restore")
        print("✗ 已回滚到启动前基线。")
        print("  请复核 bug-hunter 的报告：findings 是否真实存在、修复是否真转绿。")
        return 1
    if _run_module_coverage(final=final) != 0:
        print("→ 模块覆盖门禁失败，回滚到基线快照…")
        _run("restore")
        print("✗ 模块清单无效或未达到覆盖要求。")
        return 1
    if _run_prep_validate() != 0:
        print("→ 开工准备记录不完整，回滚到基线快照…")
        _run("restore")
        print("✗ 缺项目识别、工具调研/选择/就绪或协作记录。")
        return 1
    _print_new_findings()
    suffix = "，最终 100% 覆盖通过" if final else "，模块清单结构有效"
    print(f"✓ 本轮结算正常，life 变化在合法范围内{suffix}。")
    return 0


def _baseline_json() -> dict | None:
    """读取当前 life 状态作为外部基线（供 pre 输出，防漏洞 2）。"""
    import json

    life = AGENT_DIR / "bug-hunter-life.json"
    if not life.is_file():
        return None
    try:
        return json.loads(life.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _print_new_findings() -> None:
    """打印本轮新增发现摘要（供调用方复核真实性）。"""
    import json

    try:
        d = json.loads(
            (AGENT_DIR / "bug-hunter-life.json").read_text(encoding="utf-8")
        )
        hist = d.get("history") or []
        if not hist:
            return
        last = hist[-1]
        findings = last.get("findings") or []
        credited = last.get("credited", len(findings))
        print("-" * 56)
        print(f"本轮（round={last.get('round')}）新增发现：{len(findings)} 条 "
              f"（计命 {credited} 条）")
        for f in findings:
            print(f"  - {f}")
        print("请逐条复核：证据是否真实、修复是否转绿。")
    except Exception as e:  # noqa: BLE001
        print(f"（读取本轮 findings 摘要失败: {e}）")


def status() -> int:
    print("=" * 56)
    print("bug-hunter 当前状态")
    print("=" * 56)
    return _run("check")


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "post":
        return post(final="--final" in argv[2:])
    fn = {"pre": pre, "status": status}.get(cmd)
    if fn is None:
        print(f"[launch_bug_hunter] 未知命令: {cmd}（可选 pre/post/status）")
        return 2
    return fn()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
