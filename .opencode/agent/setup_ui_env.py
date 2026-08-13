#!/usr/bin/env python3
"""setup_ui_env.py — UI 视觉挖掘环境自检 + 自动安装缺失依赖。

bug-hunter 的 UI 面依赖：Node/npx + @playwright/mcp + Chromium 浏览器。
本脚本检测并自动补装缺失部分。注意：MCP 工具本身由 opencode 在启动时
加载，本脚本只能安装其底层运行时依赖——装完后需重启 opencode 会话，
playwright_* 工具才会出现在 bug-hunter 的工具集里。

用法：
  python3 setup_ui_env.py check    # 只检测，列出缺失项（exit 0=就绪）
  python3 setup_ui_env.py install  # 检测并自动补装缺失项
  python3 setup_ui_env.py status   # 同 check，输出当前状态
"""

from __future__ import annotations

import shutil
import subprocess
import sys


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def node_ok() -> tuple[bool, str]:
    node = shutil.which("node")
    if not node:
        return False, "node 未安装"
    v = sh([node, "-v"])
    return v.returncode == 0, f"node {v.stdout.strip() or v.stderr.strip()}"


def npx_ok() -> tuple[bool, str]:
    npx = shutil.which("npx")
    if not npx:
        return False, "npx 未安装（需 npm 自带）"
    v = sh([npx, "--no-install", "@playwright/mcp@latest", "--version"])
    if v.returncode == 0:
        return True, f"@playwright/mcp {v.stdout.strip()}"
    return False, "@playwright/mcp 未缓存（首次运行自动下载）"


def browser_ok() -> tuple[bool, str]:
    # 检测常见平台 Chromium 缓存目录
    import os
    from pathlib import Path

    home = Path.home()
    candidates = [
        home / "Library/Caches/ms-playwright",      # macOS
        home / ".cache/ms-playwright",              # Linux
        Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright" if os.name == "nt" else None,
    ]
    for c in candidates:
        if c and c.is_dir() and any(c.iterdir()):
            n = sum(1 for _ in c.iterdir())
            return True, f"Chromium 已就绪（{c.name}: {n} 项）"
    return False, "Chromium 浏览器未下载"


def check() -> int:
    print("=" * 52)
    print("Bug-Hunter UI 环境自检")
    print("=" * 52)
    checks = [("Node", node_ok), ("npx", npx_ok), ("Playwright 浏览器", browser_ok)]
    missing: list[str] = []
    for name, fn in checks:
        ok, detail = fn()
        print(f"  {'✓' if ok else '✗'} {name}: {detail}")
        if not ok:
            missing.append(name)
    print("-" * 52)
    if missing:
        print(f"缺失 {len(missing)} 项：{', '.join(missing)}")
        print("运行 `python3 setup_ui_env.py install` 自动补装。")
        return 1
    print("UI 环境就绪。playwright_* 工具可用。")
    return 0


def install() -> int:
    print("=" * 52)
    print("自动补装缺失依赖")
    print("=" * 52)
    if not node_ok()[0]:
        print("✗ node 缺失，请先安装 Node.js ≥18（https://nodejs.org）")
        return 1
    npx = shutil.which("npx")
    if not npx:
        print("✗ npx 缺失，请安装 npm（随 Node.js 附带）")
        return 1
    # 1. 确保 @playwright/mcp 可用（触发 npx 下载缓存）
    print("[1/3] 准备 @playwright/mcp …")
    sh([npx, "--yes", "@playwright/mcp@latest", "--version"])
    # 2. 确保 Chromium 浏览器
    print("[2/3] 下载 Chromium 浏览器 …")
    r = sh([npx, "--yes", "playwright", "install", "chromium"])
    if r.returncode != 0:
        print("✗ Chromium 下载失败：", r.stderr.strip()[-500:])
        return 1
    print("✓ Chromium 就绪")
    # 3. 复检
    print("[3/3] 复检 …")
    rc = check()
    if rc == 0:
        print("=" * 52)
        print("✓ 全部就绪。注意：MCP 工具由 opencode 启动时加载，")
        print("  新装依赖后请【重启 opencode 会话】让 playwright_* 生效。")
    return rc


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "check"
    fn = {"check": check, "status": check, "install": install}.get(cmd)
    if fn is None:
        print(f"[setup_ui_env] 未知命令: {cmd}（可选 check/status/install）")
        return 2
    return fn()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
