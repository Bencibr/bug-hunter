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

PLAYWRIGHT_MCP_VERSION = "0.0.79"
PLAYWRIGHT_BROWSER_VERSION = "1.63.0-alpha-2026-08-05"
AGENT_TTY_VERSION = "0.5.0"
PEXPECT_VERSION = "4.9.0"
NODE_MIN_MAJOR = 24
NODE_MAX_MAJOR = 27


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def node_ok() -> tuple[bool, str]:
    node = shutil.which("node")
    if not node:
        return False, "node 未安装"
    v = sh([node, "-v"])
    version = v.stdout.strip() or v.stderr.strip()
    if v.returncode != 0:
        return False, f"node 无法执行: {version}"
    try:
        major = int(version.lstrip("v").split(".", 1)[0])
    except ValueError:
        return False, f"node 版本无法解析: {version}"
    if not NODE_MIN_MAJOR <= major < NODE_MAX_MAJOR:
        return False, (
            f"node {version} 不兼容（固定工具链要求 "
            f">={NODE_MIN_MAJOR}, <{NODE_MAX_MAJOR}）"
        )
    return True, f"node {version}"


def npx_ok() -> tuple[bool, str]:
    npx = shutil.which("npx")
    if not npx:
        return False, "npx 未安装（需 npm 自带）"
    # npm 11 的临时 npx 缓存不能被 --no-install 稳定识别；这里仅做只读运行时
    # 检查。固定 MCP 包的下载与版本执行在 install() 第 1 步强校验。
    v = sh([npx, "--version"])
    if v.returncode != 0:
        return False, f"npx 无法执行: {v.stderr.strip() or v.stdout.strip()}"
    return True, f"npx {v.stdout.strip()}（MCP 固定 {PLAYWRIGHT_MCP_VERSION}）"


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


def tui_ok() -> tuple[bool, str]:
    """检测 TUI 测试工具：agent-tty（terminal 版 Playwright）或 pexpect。"""
    found = []
    agent_tty = shutil.which("agent-tty")
    if agent_tty:
        version = sh([agent_tty, "version"])
        if version.returncode == 0 and AGENT_TTY_VERSION in version.stdout:
            found.append(f"agent-tty {AGENT_TTY_VERSION}")
    try:
        import pexpect  # noqa: F401
        if getattr(pexpect, "__version__", None) == PEXPECT_VERSION:
            found.append(f"pexpect {PEXPECT_VERSION}")
    except ImportError:
        pass
    if found:
        return True, f"TUI 工具就绪（{', '.join(found)}）"
    return False, (
        "TUI 工具缺失或版本不匹配（需要 "
        f"agent-tty@{AGENT_TTY_VERSION} 或 pexpect=={PEXPECT_VERSION}）"
    )


def check() -> int:
    print("=" * 52)
    print("Bug-Hunter UI/TUI 环境自检")
    print("=" * 52)
    checks = [("Node", node_ok), ("npx", npx_ok), ("Playwright 浏览器", browser_ok),
              ("TUI 工具(agent-tty/pexpect)", tui_ok)]
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
    print("UI/TUI 环境就绪。playwright_* / agent-tty / pexpect 可用。")
    return 0


def install() -> int:
    print("=" * 52)
    print("自动补装缺失依赖")
    print("=" * 52)
    if not node_ok()[0]:
        print(
            f"✗ Node.js 版本不兼容，请安装 >= {NODE_MIN_MAJOR} 且 "
            f"< {NODE_MAX_MAJOR}（https://nodejs.org）"
        )
        return 1
    npx = shutil.which("npx")
    if not npx:
        print("✗ npx 缺失，请安装 npm（随 Node.js 附带）")
        return 1
    npm = shutil.which("npm")
    if not npm:
        print("✗ npm 缺失，无法安装 agent-tty")
        return 1
    # 1. 确保 @playwright/mcp 可用（触发 npx 下载缓存）
    mcp_package = f"@playwright/mcp@{PLAYWRIGHT_MCP_VERSION}"
    print(f"[1/4] 准备 {mcp_package} …")
    r = sh([npx, "--yes", mcp_package, "--version"])
    if r.returncode != 0:
        print("✗ Playwright MCP 安装失败：", r.stderr.strip()[-500:])
        return 1
    # 2. 确保 Chromium 浏览器
    print("[2/4] 下载 Chromium 浏览器 …")
    playwright = f"playwright@{PLAYWRIGHT_BROWSER_VERSION}"
    r = sh([npx, "--yes", playwright, "install", "chromium"])
    if r.returncode != 0:
        print("✗ Chromium 下载失败：", r.stderr.strip()[-500:])
        return 1
    print("✓ Chromium 就绪")
    # 3. 确保 TUI 工具（agent-tty 全局 + pexpect）
    print("[3/4] 安装 TUI 工具（agent-tty + pexpect）…")
    r = sh([npm, "install", "-g", f"agent-tty@{AGENT_TTY_VERSION}"])
    if r.returncode != 0:
        print("✗ agent-tty 安装失败：", r.stderr.strip()[-500:])
        return 1
    r = sh([
        sys.executable, "-m", "pip", "install", "--quiet",
        f"pexpect=={PEXPECT_VERSION}",
    ])
    if r.returncode != 0:
        print("✗ pexpect 安装失败：", r.stderr.strip()[-500:])
        return 1
    print("✓ TUI 工具就绪")
    # 4. 复检
    print("[4/4] 复检 …")
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
