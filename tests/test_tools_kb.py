#!/usr/bin/env python3
"""tools_kb.py 30 天有效期检查测试。"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent / ".opencode" / "agent"
sys.path.insert(0, str(AGENT_DIR))

import tools_kb as kb  # noqa: E402


class ToolsKbTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="tools-kb-test-"))
        self.file = self.tmp / "tools-kb.md"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, date_text: str) -> None:
        self.file.write_text(
            "| 工具 | 用途 | 来源 | 验证日期 |\n"
            "|------|------|------|---------|\n"
            f"| demo | test | source | {date_text} |\n",
            encoding="utf-8",
        )

    def test_fresh_entry_passes(self):
        self.write("2026-08-01")
        rc, errors = kb.check(self.file, today=date(2026, 8, 14))
        self.assertEqual(rc, 0)
        self.assertEqual(errors, [])

    def test_exact_thirty_days_passes(self):
        self.write("2026-07-15")
        rc, _ = kb.check(self.file, today=date(2026, 8, 14))
        self.assertEqual(rc, 0)

    def test_thirty_one_days_expires(self):
        self.write("2026-07-14")
        rc, errors = kb.check(self.file, today=date(2026, 8, 14))
        self.assertEqual(rc, 1)
        self.assertIn("过期", errors[0])

    def test_future_date_rejected(self):
        self.write("2026-08-15")
        rc, errors = kb.check(self.file, today=date(2026, 8, 14))
        self.assertEqual(rc, 1)
        self.assertIn("未来", errors[0])

    def test_missing_date_rejected(self):
        self.write("待定")
        rc, errors = kb.check(self.file, today=date(2026, 8, 14))
        self.assertEqual(rc, 1)
        self.assertIn("缺少", errors[0])

    def test_missing_file_returns_config_error(self):
        rc, errors = kb.check(self.file, today=date(2026, 8, 14))
        self.assertEqual(rc, 2)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
