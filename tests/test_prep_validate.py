#!/usr/bin/env python3
"""prep_validate.py 准备记录门禁测试。"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent / ".opencode" / "agent"
sys.path.insert(0, str(AGENT_DIR))

import prep_validate as pv  # noqa: E402


VALID = """# prep
## 项目识别
项目：demo，技术栈：Python，入口：app.py
## 测试类型
黑盒：是；白盒：是；自动化：是
## 工具调研
来源：https://github.com/example/tool；验证日期：2026-08-14
## 工具选择
主工具：pytest；辅助：fuzz
## 工具就绪
工具检查：通过；可以开工：是
## 多工具协作
模块分配：api→postmcp；逻辑→pytest
## 准备结论
准备完成，可以开工
"""


class PrepValidateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="prep-test-"))
        self.record = self.tmp / "prep-record.md"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_valid_record(self):
        self.record.write_text(VALID, encoding="utf-8")
        rc, errors = pv.check(self.record, self.tmp)
        self.assertEqual(rc, 0)
        self.assertEqual(errors, [])

    def test_missing_section_rejected(self):
        self.record.write_text("## 项目识别\n项目：demo\n", encoding="utf-8")
        rc, errors = pv.check(self.record, self.tmp)
        self.assertEqual(rc, 1)
        self.assertTrue(any("缺少章节" in e for e in errors))

    def test_placeholder_rejected(self):
        self.record.write_text(VALID.replace("项目：demo", "项目：待填写"), encoding="utf-8")
        rc, errors = pv.check(self.record, self.tmp)
        self.assertEqual(rc, 1)
        self.assertTrue(any("未填写" in e for e in errors))

    def test_research_without_source_rejected(self):
        self.record.write_text(VALID.replace("https://github.com/example/tool", "本地"), encoding="utf-8")
        rc, errors = pv.check(self.record, self.tmp)
        self.assertEqual(rc, 1)
        self.assertTrue(any("来源" in e for e in errors))

    def test_empty_section_rejected(self):
        self.record.write_text(VALID.replace("项目：demo，技术栈：Python，入口：app.py", ""), encoding="utf-8")
        rc, errors = pv.check(self.record, self.tmp)
        self.assertEqual(rc, 1)
        self.assertTrue(any("项目识别" in e for e in errors))

    def test_research_without_date_rejected(self):
        self.record.write_text(VALID.replace("；验证日期：2026-08-14", ""), encoding="utf-8")
        rc, errors = pv.check(self.record, self.tmp)
        self.assertEqual(rc, 1)
        self.assertTrue(any("日期" in e for e in errors))

    def test_negative_readiness_rejected(self):
        self.record.write_text(VALID.replace("可以开工：是", "可以开工：否"), encoding="utf-8")
        rc, errors = pv.check(self.record, self.tmp)
        self.assertEqual(rc, 1)
        self.assertTrue(any("工具就绪" in e for e in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
