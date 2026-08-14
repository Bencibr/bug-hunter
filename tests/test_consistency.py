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
PYPROJECT = REPO / "pyproject.toml"
RUNTIME_AGENT_FILES = {
    ".opencode/agent/bug-hunter-life.json",
    ".opencode/agent/bug-hunter-life.json.snapshot",
    ".opencode/agent/repair-audit.log",
}


class ConsistencyTestCase(unittest.TestCase):
    def test_version_consistent(self):
        """bug-hunter.md、README、pyproject 的版本必须一致。"""
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
        pyproject = PYPROJECT.read_text(encoding="utf-8")
        project = pyproject.split("[project]", 1)[-1].split("[", 1)[0]
        m_project = re.search(r'^version\s*=\s*"([\d.]+)"', project, re.M)
        self.assertIsNotNone(m_project, "pyproject.toml 无 project.version")
        self.assertEqual(m_bh.group(1), m_project.group(1))

    def test_referenced_agent_files_exist(self):
        """bug-hunter.md 引用的 .opencode/agent/* 路径必须存在。"""
        bh = BUG_HUNTER.read_text(encoding="utf-8")
        refs = set(re.findall(r"\.opencode/agent/[A-Za-z0-9_.\-]+", bh))
        missing = [
            p for p in refs
            if not (REPO / p).exists() and p not in RUNTIME_AGENT_FILES
        ]
        self.assertEqual(missing, [], f"提示词引用了不存在的文件: {missing}")

    def test_reset_permission_is_ask(self):
        """verify_life.py reset 权限必须是 ask（保证自动化授权通道）。"""
        bh = BUG_HUNTER.read_text(encoding="utf-8")
        self.assertIn('"*verify_life.py reset*": ask', bh,
                      "reset 权限应改为 ask（deny 会阻断自动化重置）")
        self.assertIn('"*verify_life.py set-mode*": ask', bh,
                      "set-mode 权限应为 ask（模式切换必须有用户授权）")

    def test_core_scripts_have_tests(self):
        """每个核心脚本都应有对应测试文件（广度保障）。"""
        scripts = ["verify_life", "launch_bug_hunter", "setup_ui_env",
                   "minimize_repro", "fuzz_input", "corpus_fetch",
                   "module_coverage", "tools_kb", "prep_validate"]
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
        missing = [
            p for p in refs
            if not (REPO / p).exists() and p not in RUNTIME_AGENT_FILES
        ]
        self.assertEqual(missing, [], f"README 引用了不存在的文件: {missing}")

    def test_required_md_templates_exist(self):
        """agent 依赖的清单文件必须存在（含工具知识库）。"""
        for name in ("mistake-book.md", "bug-log.md", "module-coverage.md",
                     "tools-kb.md", "prep-record.md"):
            self.assertTrue((AGENT / name).is_file(), f"缺少 {name}")

    def test_research_before_output_is_hard_gate(self):
        """防「记忆库偷懒」逃逸：调研必须本地优先→搜索兜底，禁止凭记忆输出。"""
        bh = BUG_HUNTER.read_text(encoding="utf-8")
        self.assertIn("本地优先", bh,
                      "调研必须本地优先（tools-kb 优先）")
        self.assertIn("记忆库偷懒", bh,
                      "反模式必须定义「记忆库偷懒」逃逸")
        self.assertIn("搜索是行为不是记忆", bh,
                      "哲学必须强调搜索是行为不是记忆（通用性来源）")
        self.assertIn("30 天", bh,
                      "调研必须含 30 天有效期（工具知识会过期）")
        self.assertIn("过期知识复用", bh,
                      "反模式必须定义「过期知识复用」逃逸（>30 天仍直接用）")

    def test_external_gates_are_wired(self):
        """覆盖/准备/知识库门禁必须接入 launch post/pre，而不是只写文档。"""
        launch = (AGENT / "launch_bug_hunter.py").read_text(encoding="utf-8")
        self.assertIn("_run_module_coverage", launch)
        self.assertIn("_run_prep_validate", launch)
        self.assertIn("_run_tools_kb", launch)
        self.assertIn('"--final"', launch)

    def test_external_tool_versions_are_pinned(self):
        """MCP/安装脚本不可使用漂移的 latest 或无版本安装。"""
        config = (REPO / "opencode.json").read_text(encoding="utf-8")
        setup = (AGENT / "setup_ui_env.py").read_text(encoding="utf-8")
        self.assertNotIn("@latest", config)
        self.assertIn("@playwright/mcp@0.0.79", config)
        self.assertIn('AGENT_TTY_VERSION = "0.5.0"', setup)
        self.assertIn('PEXPECT_VERSION = "4.9.0"', setup)

    def test_runtime_and_ci_metadata_exist(self):
        """运行时约束和双版本 CI 必须常驻，防止只在文档里声明。"""
        self.assertEqual((REPO / ".python-version").read_text().strip(), "3.14.6")
        self.assertEqual((REPO / ".nvmrc").read_text().strip(), "24")
        workflow = (REPO / ".github" / "workflows" / "ci.yml")
        self.assertTrue(workflow.is_file())
        text = workflow.read_text(encoding="utf-8")
        self.assertIn('"3.11"', text)
        self.assertIn('"3.14"', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
