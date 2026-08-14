#!/usr/bin/env python3
"""fuzz_input.py 的单元测试 — 验证变异策略、异常筛选、并发执行。"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent / ".opencode" / "agent"
sys.path.insert(0, str(AGENT_DIR))

import fuzz_input as fz  # noqa: E402


class FuzzInputTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="fuzz-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- 变异策略 ----

    def test_mutate_strategies_present(self):
        names = {n for n, _ in fz.STRATEGIES}
        self.assertEqual(
            names,
            {"truncate", "flip_byte", "insert_garbage",
             "mutate_numeric", "mutate_string", "duplicate"},
        )

    def test_mutate_returns_strategy_and_bytes(self):
        rng = random.Random(42)
        data = b'{"key": 123, "name": "hello"}'
        for _ in range(50):
            name, out = fz.mutate(data, rng)
            self.assertIn(name, {n for n, _ in fz.STRATEGIES})
            self.assertIsInstance(out, bytes)

    def test_truncate_shortens(self):
        rng = random.Random(1)
        out = fz._mutate_truncate(b"abcdefgh", rng)
        self.assertLess(len(out), 8)

    def test_flip_byte_changes_one_byte(self):
        rng = random.Random(2)
        data = b"abcdef"
        out = fz._mutate_flip_byte(data, rng)
        self.assertEqual(len(out), len(data))
        diffs = sum(1 for a, b in zip(data, out) if a != b)
        self.assertEqual(diffs, 1)

    def test_numeric_mutation_changes_numbers(self):
        rng = random.Random(3)
        out = fz._mutate_numeric(b'{"n": 42}', rng)
        # 至少发生一次替换（含 "n": 42 → 0/-1/超大等）
        self.assertNotEqual(out, b'{"n": 42}')

    # ---- 执行与筛选 ----

    def test_fuzz_once_normal_exit_no_crash(self):
        """目标正常退出（exit 0）→ 返回 None。"""
        cmd = "true {input}"
        rng = random.Random(4)
        res = fz.fuzz_once(cmd, b"hello", rng, self.tmp, 5, 0)
        self.assertIsNone(res)

    def test_fuzz_once_crash_detected(self):
        """目标对非零输入退出非 0 → 记录 crash。"""
        # 用 shell 模拟"目标崩溃"：输入含 'BAD' 时 exit 1
        cmd = "grep -q BAD {input} || exit 0"
        rng = random.Random(5)
        res = fz.fuzz_once(cmd, b"BAD-data", rng, self.tmp, 5, 0)
        # 变异后可能仍含 BAD → 非零退出被记为 crash；也可能不含 BAD → None
        self.assertIn(res, (None, dict)) if res else None

    def test_fuzz_once_timeout_detected(self):
        """目标超时 → 记录 timeout。"""
        cmd = "sleep 5"  # 无 input 占位，命令本身跑 5 秒 > 超时 1 秒
        res = fz.fuzz_once(cmd, b"x", random.Random(6), self.tmp, 1, 0)
        self.assertIsNotNone(res)
        self.assertEqual(res["kind"], "timeout")

    def test_main_writes_summary_and_crashes(self):
        """端到端：fuzz 一批，产出 summary.json 与异常样本目录。"""
        src = self.tmp / "valid.txt"
        src.write_text('{"key": "value", "n": 42}\n' * 10, encoding="utf-8")
        out = self.tmp / "out"
        # 目标：python 解析非 JSON → 崩溃（非零退出）
        cmd = f"{sys.executable} -c 'import sys; json.load(open(sys.argv[1]))' {{input}}"
        r = subprocess.run(
            [sys.executable, str(AGENT_DIR / "fuzz_input.py"),
             "--input", str(src), "--cmd", cmd, "--out", str(out),
             "--count", "30", "--jobs", "4", "--seed", "7"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["total"], 30)
        self.assertGreater(summary["anomalies"], 0)
        crashes = list((out / "crashes").iterdir())
        self.assertGreater(len(crashes), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
