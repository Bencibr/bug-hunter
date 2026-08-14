#!/usr/bin/env python3
"""项目一致性测试 — 防「改了提示词忘了同步文档/脚本」的漂移。

覆盖：
  - bug-hunter.md frontmatter 的 version 与 README 版本号一致
  - bug-hunter.md 引用的 .opencode/agent/* 路径全部存在
  - frontmatter permission 的 verify_life reset 是 ask（不 deny）
  - README 文件结构表提到的文件都存在
  - 各 .md 清单文件（mistake-book/bug-log/module-coverage）存在
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AGENT = REPO / ".opencode" / "agent"
BUG_HUNTER = AGENT / "bug-hunter.md"
README = REPO / "README.md"


class ConsistencyTestCase(unittest.TestCase):
    def test_version_consistent(self):
        """bug-hunter.md frontmatter version == README Version。"""
        bh = BUG_HUNTER.read_text(encoding="utf-8")
        rd = README.read_text(encoding="utf-8")
        m_bh = re.search(r"^version:\s*([\d.]+)", bh, re.M)
        m_rd = re.search(r"\*\*Version\s+([\d.]+)\*\*", rd)
        self.assertIsNotNone(m_bh, "bug-hunter.md 无 version frontmatter")
        self.assertIsNotNone(m_rd, "README 无 Version 标记")
        self.assertEqual(
            m_bh.group(1), m_rd.group(1),
            f"版本漂移: bug-hunter.md={m_bh.group(1)} README={m_rd.group(1)}",
        )

    def test_referenced_agent_files_exist(self):
        """bug-hunter.md 引用的 .opencode/agent/* 路径必须存在。"""
        bh = BUG_HUNTER.read_text(encoding="utf-8")
        refs = set(re.findall(r"\.opencode/agent/[A-Za-z0-9_.\-]+", bh))
        missing = [p for p in refs if not (REPO / p).exists()]
        self.assertEqual(missing, [], f"提示词引用了不存在的文件: {missing}")

    def test_reset_permission_is_ask(self):
        """verify_life.py reset 权限必须是 ask（保证自动化授权通道）。"""
        bh = BUG_HUNTER.read_text(encoding="utf-8")
        self.assertIn('"*verify_life.py reset*": ask', bh,
                      "reset 权限应改为 ask（deny 会阻断自动化重置）")

    def test_core_scripts_have_tests(self):
        """每个核心脚本都应有对应测试文件（广度保障）。"""
        scripts = ["verify_life", "launch_bug_hunter", "setup_ui_env",
                   "minimize_repro", "fuzz_input", "corpus_fetch"]
        tests = [p.name for p in (REPO / "tests").glob("test_*.py")]
        for s in scripts:
            self.assertTrue(
                any(s in t for t in tests), f"{s}.py 缺少测试: tests/"
            )

    def test_readme_file_structure_rows_exist(self):
        """README 文件结构表列出的 .opencode/agent/* 文件必须存在。"""
        rd = README.read_text(encoding="utf-8")
        refs = set(re.findall(r"\.opencode/agent/[A-Za-z0-9_.\-]+", rd))
        # 通配符 glob（如 findings_round*.txt 被正则截断为 findings_round）不要求常驻
        wildcards = {p for p in refs if "*" in p or p.endswith("findings_round")}
        refs -= wildcards
        # 运行时生成/忽略文件不常驻，跳过
        runtime = {".opencode/agent/bug-hunter-life.json",
                   ".opencode/agent/bug-hunter-life.json.snapshot",
                   ".opencode/agent/repair-audit.log"}
        missing = [p for p in refs if not (REPO / p).exists() and p not in runtime]
        self.assertEqual(missing, [], f"README 引用了不存在的文件: {missing}")

    def test_required_md_templates_exist(self):
        """agent 依赖的三个清单文件必须存在。"""
        for name in ("mistake-book.md", "bug-log.md", "module-coverage.md"):
            self.assertTrue((AGENT / name).is_file(), f"缺少 {name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
