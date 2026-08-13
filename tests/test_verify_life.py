#!/usr/bin/env python3
"""verify_life.py 的单元测试 — 覆盖寿命记账的防舞弊核心逻辑。

运行：
  python3 tests/test_verify_life.py            # 直接跑
  python3 -m unittest discover tests           # unittest 方式
  ./tests/run_tests.sh                         # 一键

覆盖：
  - check 一致性 / 篡改检测
  - settle 结算（credited/evidence/round 护栏）
  - snapshot / diff / restore（外部基线对比）
  - repair（幽灵轮费回滚 + 审计日志）
  - 证据校验（真实文件引用 vs 编造）
  - selfhash / 篡改拦截
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# 让 verify_life 可 import（它在 .opencode/agent/ 下）
AGENT_DIR = Path(__file__).resolve().parent.parent / ".opencode" / "agent"
sys.path.insert(0, str(AGENT_DIR))

import verify_life as v  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


class VerifyLifeTestCase(unittest.TestCase):
    """每个测试在独立临时目录跑，不污染真实 bug-hunter-life.json。"""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="vl-test-"))
        # 把校验器的文件目标指向临时目录
        v.LIFE_FILE = self.tmp / "bug-hunter-life.json"
        v.SNAPSHOT_FILE = self.tmp / "bug-hunter-life.json.snapshot"
        v.AUDIT_LOG = self.tmp / "repair-audit.log"
        # 证据校验的仓库根指向真实仓库根（存在 bug-hunter.md 等）
        v._REPO_ROOT = REPO_ROOT
        v.cmd_reset()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def load(self) -> dict:
        return json.loads(v.LIFE_FILE.read_text(encoding="utf-8"))

    def write_findings(self, lines: list[str]) -> Path:
        p = self.tmp / "findings.txt"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    # ---- evidence 真实引用（存在文件 + 行号）----
    def evidence_real(self) -> str:
        return f"[MEDIUM] 测试。.opencode/agent/bug-hunter.md:100。复现：x。观察：y。"

    def evidence_fake(self) -> str:
        return "[HIGH] 编造。nonexist_file.py:999。复现：x。观察：y。"

    # ================= check =================

    def test_check_ok_on_reset(self):
        self.assertEqual(v.cmd_check(), 0)

    def test_check_detects_life_tamper(self):
        d = self.load()
        d["life"] = 999
        v.save(d)
        self.assertNotEqual(v.cmd_check(), 0)

    def test_check_detects_alive_inconsistency(self):
        d = self.load()
        d["alive"] = False
        v.save(d)
        self.assertNotEqual(v.cmd_check(), 0)

    def test_check_detects_round_mismatch(self):
        d = self.load()
        d["round"] = 5
        v.save(d)
        self.assertNotEqual(v.cmd_check(), 0)

    def test_check_detects_found_total_mismatch(self):
        d = self.load()
        d["found_total"] = 3
        v.save(d)
        self.assertNotEqual(v.cmd_check(), 0)

    # ================= settle =================

    def test_settle_round1_credit_one(self):
        f = self.write_findings([self.evidence_real()])
        self.assertEqual(
            v.cmd_settle(["--credited", "1", "--findings-file", str(f), "--round", "1"]),
            0,
        )
        d = self.load()
        self.assertEqual(d["life"], 1)  # -1(轮费) + 1(发现) = 0? no: 1-1+1=1
        self.assertEqual(d["found_total"], 1)
        self.assertEqual(d["rounds_completed"], 1)
        self.assertEqual(d["round"], 2)
        self.assertTrue(d["alive"])

    def test_settle_credit_five_max(self):
        f = self.write_findings([self.evidence_real()] * 5)
        self.assertEqual(
            v.cmd_settle(["--credited", "5", "--findings-file", str(f), "--round", "1"]),
            0,
        )
        d = self.load()
        self.assertEqual(d["life"], 5)  # 1 - 1 + 5
        self.assertEqual(d["found_total"], 5)

    def test_settle_rejects_credit_overflow(self):
        f = self.write_findings([self.evidence_real()] * 6)
        self.assertNotEqual(
            v.cmd_settle(["--credited", "6", "--findings-file", str(f), "--round", "1"]),
            0,
        )

    def test_settle_rejects_fake_evidence(self):
        f = self.write_findings([self.evidence_fake()])
        self.assertNotEqual(
            v.cmd_settle(["--credited", "1", "--findings-file", str(f), "--round", "1"]),
            0,
        )
        # 文件未被写回（拒绝结算）
        self.assertEqual(self.load()["rounds_completed"], 0)

    def test_settle_rejects_wrong_round(self):
        f = self.write_findings([self.evidence_real()])
        self.assertNotEqual(
            v.cmd_settle(["--credited", "1", "--findings-file", str(f), "--round", "99"]),
            0,
        )

    def test_settle_rejects_duplicate_of_history(self):
        f1 = self.write_findings([self.evidence_real()])
        self.assertEqual(
            v.cmd_settle(["--credited", "1", "--findings-file", str(f1), "--round", "1"]),
            0,
        )
        # 第二轮完全相同的字符串 → 历史重复，拒绝计命
        f2 = self.write_findings([self.evidence_real()])
        self.assertNotEqual(
            v.cmd_settle(["--credited", "1", "--findings-file", str(f2), "--round", "2"]),
            0,
        )

    def test_settle_refuses_when_dead(self):
        # 先结算到 life=0：credited=0
        f = self.write_findings([self.evidence_real()])
        self.assertEqual(
            v.cmd_settle(["--credited", "0", "--findings-file", str(f), "--round", "1"]),
            0,
        )
        d = self.load()
        self.assertEqual(d["life"], 0)
        self.assertFalse(d["alive"])
        # 死亡后拒绝再结算
        f2 = self.write_findings([self.evidence_real()])
        self.assertNotEqual(
            v.cmd_settle(["--credited", "1", "--findings-file", str(f2), "--round", "2"]),
            0,
        )

    def test_settle_parallel_multiple_credited(self):
        # 一轮并行发现多个非重复 bug → 按数量计命
        f = self.write_findings(
            [
                "[MEDIUM] a。.opencode/agent/bug-hunter.md:10。复现：x。观察：y。",
                "[MEDIUM] b。.opencode/agent/bug-hunter.md:20。复现：x。观察：y。",
                "[MEDIUM] c。.opencode/agent/bug-hunter.md:30。复现：x。观察：y。",
            ]
        )
        self.assertEqual(
            v.cmd_settle(["--credited", "3", "--findings-file", str(f), "--round", "1"]),
            0,
        )
        d = self.load()
        self.assertEqual(d["life"], 3)  # 1 - 1 + 3
        self.assertEqual(d["found_total"], 3)

    # ================= snapshot / diff / restore =================

    def test_diff_ok_after_normal_settle(self):
        self.assertEqual(v.cmd_snapshot(), 0)
        f = self.write_findings([self.evidence_real()])
        self.assertEqual(
            v.cmd_settle(["--credited", "1", "--findings-file", str(f), "--round", "1"]),
            0,
        )
        self.assertEqual(v.cmd_diff(), 0)

    def test_diff_detects_snapshot_tamper(self):
        """agent 同时篡改 life + snapshot → 外部基线仍能检出（漏洞 2 修复）。"""
        self.assertEqual(v.cmd_snapshot(), 0)
        for path in (v.LIFE_FILE, v.SNAPSHOT_FILE):
            d = json.loads(path.read_text(encoding="utf-8"))
            d["life"] = 999
            path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        # 用外部基线 diff（BH_PRE_BASELINE 覆盖仓库内 snapshot）
        import os

        base = json.loads(v.LIFE_FILE.read_text(encoding="utf-8"))
        base["life"] = 1
        base["rounds_completed"] = 0
        base["history"] = []
        os.environ["BH_PRE_BASELINE"] = json.dumps(base)
        try:
            self.assertNotEqual(v.cmd_diff(), 0)
        finally:
            os.environ.pop("BH_PRE_BASELINE", None)

    def test_restore_recovers_from_snapshot(self):
        self.assertEqual(v.cmd_snapshot(), 0)
        f = self.write_findings([self.evidence_real()])
        self.assertEqual(
            v.cmd_settle(["--credited", "1", "--findings-file", str(f), "--round", "1"]),
            0,
        )
        self.assertEqual(v.cmd_restore(), 0)
        d = self.load()
        self.assertEqual(d["life"], 1)
        self.assertEqual(d["rounds_completed"], 0)

    # ================= repair =================

    def test_repair_rolls_back_ghost_fee(self):
        f = self.write_findings([self.evidence_real()])
        self.assertEqual(
            v.cmd_settle(["--credited", "1", "--findings-file", str(f), "--round", "1"]),
            0,
        )
        # 制造幽灵轮费：life 被改成 99（结算值 1）
        d = self.load()
        d["life"] = 99
        v.save(d)
        self.assertNotEqual(v.cmd_check(), 0)
        self.assertEqual(v.cmd_repair(), 0)
        self.assertEqual(self.load()["life"], 1)
        # 审计日志留痕
        self.assertTrue(v.AUDIT_LOG.is_file())
        self.assertIn("repair", v.AUDIT_LOG.read_text(encoding="utf-8"))

    def test_repair_refuses_broken_chain(self):
        """history 链断裂 → repair 拒绝机械修复。"""
        f = self.write_findings([self.evidence_real()])
        self.assertEqual(
            v.cmd_settle(["--credited", "1", "--findings-file", str(f), "--round", "1"]),
            0,
        )
        d = self.load()
        d["history"][0]["life_after"] = 777  # 链断裂
        v.save(d)
        self.assertNotEqual(v.cmd_repair(), 0)

    # ================= evidence 校验 =================

    def test_evidence_real_file_passes(self):
        self.assertEqual(v.evidence_bad_lines([self.evidence_real()]), [])

    def test_evidence_fake_file_rejected(self):
        bad = v.evidence_bad_lines([self.evidence_fake()])
        self.assertEqual(len(bad), 1)

    def test_evidence_testname_repro_passes(self):
        line = "[MEDIUM] test_foo_bar 复现：x 观察：y 修复：z"
        self.assertEqual(v.evidence_bad_lines([line]), [])

    def test_evidence_no_marker_rejected(self):
        line = "[LOW] 这只是一句描述没有任何引用"
        self.assertEqual(len(v.evidence_bad_lines([line])), 1)

    # ================= selfhash / 篡改 =================

    def test_selfhash_constant_matches_file(self):
        """SELF_HASH 必须与文件（排除 SELF_HASH 行）计算一致——防篡改防线自身自洽。"""
        raw = Path(v.__file__).read_bytes()
        lines = raw.splitlines()
        cleaned = b"\n".join(
            ln for ln in lines if not ln.startswith(b'SELF_HASH = "')
        )
        actual = hashlib.sha256(cleaned).hexdigest()
        self.assertEqual(actual, v.SELF_HASH)


if __name__ == "__main__":
    unittest.main(verbosity=2)
