#!/usr/bin/env python3
"""launch_bug_hunter.py 的单元测试 — 验证启动协议的 pre/post/status 防线。

launch 脚本直接调用 verify_life.py（相对路径），因此测试在**临时目录**复制
两份脚本运行，不污染真实状态。核心断言：
  - pre：check 失败时 repair 后放行 / 基线可用时输出外部基线
  - post：diff 异常时 restore 回滚并返回非 0
  - status：委托 verify_life check
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent / ".opencode" / "agent"


def run_launch(tmp: Path, *args: str) -> subprocess.CompletedProcess:
    """在隔离目录运行 launch_bug_hunter.py（连同 verify_life.py 副本）。"""
    shutil.copy(AGENT_DIR / "launch_bug_hunter.py", tmp)
    shutil.copy(AGENT_DIR / "verify_life.py", tmp)
    shutil.copy(AGENT_DIR / "module_coverage.py", tmp)
    shutil.copy(AGENT_DIR / "tools_kb.py", tmp)
    shutil.copy(AGENT_DIR / "prep_validate.py", tmp)
    return subprocess.run(
        [sys.executable, str(tmp / "launch_bug_hunter.py"), *args],
        capture_output=True,
        text=True,
        cwd=tmp,
        timeout=30,
    )


class LaunchBugHunterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="launch-test-"))
        # 初始化一个干净的 life 文件供 launch 使用
        shutil.copy(AGENT_DIR / "verify_life.py", self.tmp)
        shutil.copy(AGENT_DIR / "tools_kb.py", self.tmp)
        shutil.copy(AGENT_DIR / "tools-kb.md", self.tmp)
        shutil.copy(AGENT_DIR / "prep_validate.py", self.tmp)
        (self.tmp / "prep-record.md").write_text(
            "## 项目识别\n项目：test\n\n"
            "## 测试类型\n黑盒：是\n\n"
            "## 工具调研\n来源：https://github.com/example/tool；验证日期：2026-08-14\n\n"
            "## 工具选择\n主工具：pytest\n\n"
            "## 工具就绪\n可以开工：是\n\n"
            "## 多工具协作\n模块分配：test→pytest\n\n"
            "## 准备结论\n准备完成，可以开工\n",
            encoding="utf-8",
        )
        # 提供一个隔离、已覆盖的合法清单，让 post 覆盖门禁可验证
        (self.tmp / "module-coverage.md").write_text(
            "| # | 模块 | 路径/范围 | 难度 | 命中 | 主工具 | 负责任务 | 依赖 | 状态 | 发现数 | 证据/测试 | 备注 |\n"
            "|---|------|-----------|------|------|--------|----------|------|------|--------|-----------|------|\n"
            "| 1 | test target | `.` | 1 | 1 | pytest | test-worker | 无 | 已覆盖 | 0 | verify_life.py:1 | ok |\n",
            encoding="utf-8",
        )
        subprocess.run(
            [sys.executable, "verify_life.py", "reset"],
            capture_output=True, cwd=self.tmp, timeout=30,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def life(self) -> dict:
        return json.loads(
            (self.tmp / "bug-hunter-life.json").read_text(encoding="utf-8")
        )

    # ---- pre ----

    def test_pre_ok_on_clean_baseline(self):
        r = run_launch(self.tmp, "pre")
        self.assertEqual(r.returncode, 0)
        # 输出包含外部基线 export 行
        self.assertIn("BH_PRE_BASELINE", r.stdout)
        # 快照已建立
        self.assertTrue((self.tmp / "bug-hunter-life.json.snapshot").is_file())

    def test_pre_repairs_inconsistent_baseline(self):
        """life 被改成 99 → pre 先 repair 再放行。"""
        d = self.life()
        d["life"] = 99
        (self.tmp / "bug-hunter-life.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8"
        )
        r = run_launch(self.tmp, "pre")
        self.assertEqual(r.returncode, 0)
        self.assertIn("BH_PRE_BASELINE", r.stdout)
        # 已修复回 life=1
        self.assertEqual(self.life()["life"], 1)

    # ---- post ----

    def test_post_ok_after_normal(self):
        """pre → 模拟一轮结算（credited=0, life 不变）→ post diff 通过。"""
        self.assertEqual(run_launch(self.tmp, "pre").returncode, 0)
        # 模拟 agent 结算：delta=-1 用 verify_life settle（需要合法证据）
        f = self.tmp / "f.txt"
        f.write_text(
            "[MEDIUM] 测试。bug-hunter-life.json:1。复现：x。观察：y。\n",
            encoding="utf-8",
        )
        subprocess.run(
            [sys.executable, "verify_life.py", "settle",
             "--credited", "0", "--findings-file", str(f), "--round", "1"],
            capture_output=True, cwd=self.tmp, timeout=30,
        )
        r = run_launch(self.tmp, "post")
        self.assertEqual(r.returncode, 0)

    def test_post_restores_on_diff_abnormal(self):
        """post diff 检出异常（幽灵轮费/超范围）→ restore 回滚并返回非 0。"""
        self.assertEqual(run_launch(self.tmp, "pre").returncode, 0)
        # 模拟 agent 作弊：结算后把 life 手动改大（只改 life，不改 snapshot）
        # → diff 用仓库内快照对比即可检出 life 超范围变化。
        d = self.life()
        d["life"] = 999
        (self.tmp / "bug-hunter-life.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        r = run_launch(self.tmp, "post")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("已回滚", r.stdout)
        # 快照恢复后 life 回原值
        self.assertEqual(self.life()["life"], 1)

    def test_post_final_rejects_uncovered_module(self):
        """最终 post 必须阻止未覆盖模块通过。"""
        self.assertEqual(run_launch(self.tmp, "pre").returncode, 0)
        manifest = self.tmp / "module-coverage.md"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace("| 已覆盖 |", "| 挖掘中 |"),
            encoding="utf-8",
        )
        r = run_launch(self.tmp, "post", "--final")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("模块清单", r.stdout)

    def test_post_rejects_missing_prep_record(self):
        """准备记录缺失时 post 不能通过。"""
        self.assertEqual(run_launch(self.tmp, "pre").returncode, 0)
        (self.tmp / "prep-record.md").unlink()
        r = run_launch(self.tmp, "post")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("准备记录", r.stdout)

    # ---- status ----

    def test_status_delegates_check(self):
        r = run_launch(self.tmp, "status")
        self.assertEqual(r.returncode, 0)
        self.assertIn("OK", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
