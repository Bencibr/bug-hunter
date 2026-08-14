#!/usr/bin/env python3
"""setup_ui_env.py 的单元测试 — 验证环境自检与 install 决策逻辑。

检测函数（node_ok/npx_ok/browser_ok/check/install）是纯逻辑，可 mock。
核心断言：
  - node 缺失 → node_ok False
  - npx 缺失 → npx_ok False
  - 浏览器缓存为空/不存在 → browser_ok False
  - check 汇总缺失项、缺失时返回非 0
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

AGENT_DIR = Path(__file__).resolve().parent.parent / ".opencode" / "agent"
sys.path.insert(0, str(AGENT_DIR))

import setup_ui_env as s  # noqa: E402


class SetupUiEnvTestCase(unittest.TestCase):
    # ---- node_ok ----

    @mock.patch("setup_ui_env.shutil.which", return_value=None)
    def test_node_missing(self, _w):
        ok, msg = s.node_ok()
        self.assertFalse(ok)
        self.assertIn("node", msg)

    @mock.patch("setup_ui_env.shutil.which", return_value="/usr/bin/node")
    @mock.patch("setup_ui_env.sh", return_value=mock.Mock(returncode=0, stdout="v24.0.0"))
    def test_node_ok(self, _sh, _w):
        ok, msg = s.node_ok()
        self.assertTrue(ok)
        self.assertIn("v24.0.0", msg)

    @mock.patch("setup_ui_env.shutil.which", return_value="/usr/bin/node")
    @mock.patch("setup_ui_env.sh", return_value=mock.Mock(returncode=0, stdout="v22.0.0"))
    def test_node_too_old(self, _sh, _w):
        ok, msg = s.node_ok()
        self.assertFalse(ok)
        self.assertIn("不兼容", msg)

    # ---- npx_ok ----

    @mock.patch("setup_ui_env.shutil.which", return_value=None)
    def test_npx_missing(self, _w):
        ok, msg = s.npx_ok()
        self.assertFalse(ok)
        self.assertIn("npx", msg)

    @mock.patch("setup_ui_env.shutil.which", return_value="/usr/bin/npx")
    @mock.patch("setup_ui_env.sh", return_value=mock.Mock(returncode=0, stdout="11.16.0"))
    def test_npx_ok(self, _sh, _w):
        ok, msg = s.npx_ok()
        self.assertTrue(ok)

    @mock.patch("setup_ui_env.shutil.which", return_value="/usr/bin/npx")
    @mock.patch("setup_ui_env.sh", return_value=mock.Mock(returncode=1, stdout=""))
    def test_npx_execution_failure(self, _sh, _w):
        """npx 路径存在但无法执行时必须标记失败。"""
        ok, msg = s.npx_ok()
        self.assertFalse(ok)
        self.assertIn("无法执行", msg)

    # ---- browser_ok ----

    def test_browser_missing_no_cache_dir(self):
        fake_home = Path(tempfile.mkdtemp())
        with mock.patch.object(Path, "home", return_value=fake_home):
            ok, msg = s.browser_ok()
            self.assertFalse(ok)

    def test_browser_ok_with_cache(self):
        fake_home = Path(tempfile.mkdtemp())
        cache = fake_home / "Library" / "Caches" / "ms-playwright"
        cache.mkdir(parents=True)
        (cache / "chromium-1234").mkdir()
        with mock.patch.object(Path, "home", return_value=fake_home):
            ok, msg = s.browser_ok()
            self.assertTrue(ok)
            self.assertIn("Chromium", msg)

    # ---- check / install ----

    @mock.patch("setup_ui_env.node_ok", return_value=(True, "ok"))
    @mock.patch("setup_ui_env.npx_ok", return_value=(True, "ok"))
    @mock.patch("setup_ui_env.browser_ok", return_value=(True, "ok"))
    @mock.patch("setup_ui_env.tui_ok", return_value=(True, "ok"))
    def test_check_all_ok_returns_zero(self, *_):
        self.assertEqual(s.check(), 0)

    @mock.patch("setup_ui_env.node_ok", return_value=(False, "node 未安装"))
    @mock.patch("setup_ui_env.npx_ok", return_value=(True, "ok"))
    @mock.patch("setup_ui_env.browser_ok", return_value=(True, "ok"))
    @mock.patch("setup_ui_env.tui_ok", return_value=(True, "ok"))
    def test_check_node_missing_returns_nonzero(self, *_):
        self.assertNotEqual(s.check(), 0)

    @mock.patch("setup_ui_env.node_ok", return_value=(True, "ok"))
    @mock.patch("setup_ui_env.npx_ok", return_value=(False, "npx 缺失"))
    @mock.patch("setup_ui_env.browser_ok", return_value=(False, "浏览器缺失"))
    @mock.patch("setup_ui_env.tui_ok", return_value=(True, "ok"))
    def test_check_multiple_missing_reports_both(self, *_):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = s.check()
        self.assertNotEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("npx", out)
        self.assertIn("浏览器", out)

    # ---- tui_ok ----

    @mock.patch("setup_ui_env.sh", return_value=mock.Mock(returncode=0, stdout="agent-tty 0.5.0"))
    @mock.patch("setup_ui_env.shutil.which", return_value="/usr/bin/agent-tty")
    def test_tui_ok_with_agent_tty(self, _w, _sh):
        ok, msg = s.tui_ok()
        self.assertTrue(ok)
        self.assertIn("agent-tty", msg)

    @mock.patch("setup_ui_env.sh", return_value=mock.Mock(returncode=1, stdout="", stderr="boom"))
    @mock.patch("setup_ui_env.shutil.which", side_effect=lambda name: f"/usr/bin/{name}")
    @mock.patch("setup_ui_env.node_ok", return_value=(True, "ok"))
    def test_install_stops_on_mcp_failure(self, _node, _which, _sh):
        self.assertNotEqual(s.install(), 0)

    @mock.patch("setup_ui_env.shutil.which", return_value=None)
    def test_tui_ok_missing_both(self, _w):
        # 模拟 pexpect 未装（无论真实环境是否有）
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *a, **kw):
            if name == "pexpect" or name.startswith("pexpect."):
                raise ImportError("pexpect not installed (mock)")
            return real_import(name, *a, **kw)

        with mock.patch.object(builtins, "__import__", fake_import):
            ok, msg = s.tui_ok()
        self.assertFalse(ok)
        self.assertIn("缺失", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
