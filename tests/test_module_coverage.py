#!/usr/bin/env python3
"""module_coverage.py 的全覆盖门禁测试。"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent / ".opencode" / "agent"
sys.path.insert(0, str(AGENT_DIR))

import module_coverage as mc  # noqa: E402


HEADER = "| # | 模块 | 路径/范围 | 难度 | 命中 | 主工具 | 负责任务 | 依赖 | 状态 | 发现数 | 证据/测试 | 备注 |"
SEPARATOR = "|---|------|-----------|------|------|--------|----------|------|------|--------|-----------|------|"


class ModuleCoverageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="module-coverage-test-"))
        (self.tmp / "src" / "api").mkdir(parents=True)
        (self.tmp / "src" / "api" / "handler.py").write_text("def handle():\n", encoding="utf-8")
        (self.tmp / "tests").mkdir()
        (self.tmp / "tests" / "test_api.py").write_text(
            "def test_handle():\n    pass\n", encoding="utf-8"
        )
        self.manifest = self.tmp / "module-coverage.md"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_manifest(self, rows: str) -> None:
        self.manifest.write_text(
            "# coverage\n\n" + HEADER + "\n" + SEPARATOR + "\n" + rows + "\n",
            encoding="utf-8",
        )

    def row(self, status: str = "已覆盖", path: str = "src/api/",
            evidence: str = "tests/test_api.py::test_handle") -> str:
        return f"| 1 | API | `{path}` | 2 | 4 | pytest | api-worker | 无 | {status} | 1 | {evidence} | ok |"

    def test_check_accepts_valid_progress_manifest(self):
        self.write_manifest(self.row("挖掘中"))
        self.assertEqual(mc.check(root=self.tmp, manifest=self.manifest), 0)

    def test_final_check_requires_all_covered(self):
        self.write_manifest(self.row("挖掘中"))
        self.assertNotEqual(mc.check(final=True, root=self.tmp, manifest=self.manifest), 0)

    def test_final_check_accepts_all_covered(self):
        self.write_manifest(self.row("已覆盖"))
        self.assertEqual(mc.check(final=True, root=self.tmp, manifest=self.manifest), 0)

    def test_missing_path_rejected(self):
        self.write_manifest(self.row(path="src/missing/"))
        self.assertNotEqual(mc.check(root=self.tmp, manifest=self.manifest), 0)

    def test_absolute_path_outside_root_rejected(self):
        self.write_manifest(self.row(path=str(Path(tempfile.gettempdir()))))
        self.assertNotEqual(mc.check(root=self.tmp, manifest=self.manifest), 0)

    def test_missing_tool_rejected(self):
        row = self.row().replace("| pytest |", "| 待定 |")
        self.write_manifest(row)
        self.assertNotEqual(mc.check(root=self.tmp, manifest=self.manifest), 0)

    def test_missing_evidence_rejected(self):
        self.write_manifest(self.row(evidence="待补"))
        self.assertNotEqual(mc.check(root=self.tmp, manifest=self.manifest), 0)

    def test_arbitrary_evidence_text_rejected(self):
        self.write_manifest(self.row(evidence="我已经测过了"))
        self.assertNotEqual(mc.check(root=self.tmp, manifest=self.manifest), 0)

    def test_out_of_range_evidence_line_rejected(self):
        self.write_manifest(self.row(evidence="src/api/handler.py:999"))
        self.assertNotEqual(mc.check(root=self.tmp, manifest=self.manifest), 0)

    def test_duplicate_path_rejected(self):
        self.write_manifest(self.row() + "\n" + self.row().replace("| 1 |", "| 2 |"))
        self.assertNotEqual(mc.check(root=self.tmp, manifest=self.manifest), 0)

    def test_example_rows_do_not_fake_coverage(self):
        self.write_manifest(
            "| 1 | （示例）解析器 | `src/missing/` | 4 | 5 | fuzz | fuzz-worker | 无 | 已覆盖 | 0 | ok | 示例 |"
        )
        self.assertNotEqual(mc.check(final=True, root=self.tmp, manifest=self.manifest), 0)

    def test_final_check_rejects_omitted_discovered_module(self):
        """清单不能只列一个模块，把同级源码模块藏起来。"""
        (self.tmp / "src" / "auth").mkdir()
        (self.tmp / "src" / "auth" / "login.py").write_text("def login():\n", encoding="utf-8")
        self.write_manifest(self.row())  # 只列 api，漏 auth
        self.assertNotEqual(mc.check(final=True, root=self.tmp, manifest=self.manifest), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
