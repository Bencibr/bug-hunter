#!/usr/bin/env python3
"""minimize_repro.py 的单元测试 — 验证 ddmin 最小化确实能缩小输入。"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent / ".opencode" / "agent"
sys.path.insert(0, str(AGENT_DIR))

import minimize_repro as mr  # noqa: E402


class MinimizeReproTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ddmin-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ddmin_removes_noise_keeps_trigger(self):
        """输入 = 大量前缀噪声 + 触发串 + 后缀噪声 → 最小化后只剩触发串。"""
        # 触发条件：输入含 "CRASH" 时验证脚本 exit 0
        noise = "A" * 200
        trigger = b"CRASH"
        data = noise.encode() + trigger + noise.encode()
        check = "grep -q CRASH {input}"
        m = mr.Minimizer(cmd="true", check=check, timeout=10)

        # 前置确认：含触发串的输入应复现
        self.assertTrue(m.reproduces(data, self.tmp))

        minimized = m.ddmin(data, self.tmp)
        # 最小化后仍复现（含触发串）
        self.assertIn(trigger, minimized)
        # 明显缩小
        self.assertLess(len(minimized), len(data))
        # 不应保留大段噪声
        self.assertLess(len(minimized), 50)

    def test_ddmin_keeps_multiple_required_tokens(self):
        """需要两个 token 同时存在才复现 → 两者都保留。"""
        data = b"PREFIX-TOK1-TOK2-SUFFIX"
        # 复现条件：同时含 TOK1 和 TOK2
        check = "grep -q TOK1 {input} && grep -q TOK2 {input}"
        m = mr.Minimizer(cmd="true", check=check, timeout=10)
        self.assertTrue(m.reproduces(data, self.tmp))
        minimized = m.ddmin(data, self.tmp)
        self.assertIn(b"TOK1", minimized)
        self.assertIn(b"TOK2", minimized)

    def test_reproduces_false_when_trigger_absent(self):
        """不含触发串 → reproduces 返回 False。"""
        m = mr.Minimizer(cmd="true", check="grep -q CRASH {input}", timeout=10)
        self.assertFalse(m.reproduces(b"NO TRIGGER HERE", self.tmp))


if __name__ == "__main__":
    unittest.main(verbosity=2)
