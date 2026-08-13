#!/usr/bin/env python3
"""launch_bug_hunter.py — bug-hunter 启动协议执行器（真实落地的外部防线）。

把「启动前检查 + 基线快照 + 结束后核对 + 异常回滚」固化为一条命令，
消除对「调用方记得手动跑」的依赖——外部防线不靠记忆，靠脚本。

用法：
  python3 launch_bug_hunter.py pre      # 启动前：check(失败先 repair) → snapshot
                                        #         → 打印启动指引（exit 非 0 = 基线不可用）
  python3 launch_bug_hunter.py post     # 结束后：diff → 异常则 restore 并提示复核
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


def _run(*args: str) -> int:
    return subprocess.call([sys.executable, str(VERIFY), *args])


def pre() -> int:
    print("=" * 56)
    print("bug-hunter 启动前协议：校验基线 → 建立快照")
    print("=" * 56)
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
    return 0


def post() -> int:
    print("=" * 56)
    print("bug-hunter 结束协议：核对 life 变化 → 异常回滚")
    print("=" * 56)
    if _run("diff") != 0:
        print("→ diff 检出异常，回滚到基线快照…")
        _run("restore")
        print("✗ 已回滚到启动前基线。")
        print("  请复核 bug-hunter 的报告：findings 是否真实存在、修复是否真转绿。")
        return 1
    _print_new_findings()
    print("✓ 本轮结算正常，life 变化在合法范围内。")
    return 0


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
    fn = {"pre": pre, "post": post, "status": status}.get(cmd)
    if fn is None:
        print(f"[launch_bug_hunter] 未知命令: {cmd}（可选 pre/post/status）")
        return 2
    return fn()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
