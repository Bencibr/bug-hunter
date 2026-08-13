#!/usr/bin/env python3
"""minimize_repro.py — 失败输入自动最小化（delta-debugging）。

用途：给定一个"能复现 bug 的完整命令 + 输入文件"，自动删除冗余片段，
输出仍能复现的最短输入——最小输入 = 根因最集中 = 挖掘更深、举证更高效。

用法：
  python3 minimize_repro.py --cmd '<目标命令，用 {input} 占位>' \
      --input <原始输入文件> --check '<验证脚本，{input} 占位，exit0=仍复现>'

示例：
  # 目标：python3 app.py 读入 input.txt，崩溃则 exit 非 0
  python3 minimize_repro.py \
      --cmd 'python3 app.py {input}' \
      --input crash.txt \
      --check 'test -s {input}'

  # 更精确：用 shell 判断是否仍复现
  python3 minimize_repro.py \
      --cmd 'python3 app.py {input}' \
      --input crash.txt \
      --check 'python3 app.py {input} 2>&1 | grep -q "Segmentation fault"'

工作原理（ddmin 算法）：
  1. 把输入按粒度 2 切块，逐个删除块；删除后仍复现 → 保留删除（缩小）。
  2. 粒度翻倍，重复；粒度超过输入长度则停止。
  3. 每一步都在临时文件验证，不污染原输入。

输出：最小输入写入 <input>.min，并打印原大小→最小大小的对比。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cmd", required=True,
                   help="目标命令，用 {input} 占位表示输入文件路径")
    p.add_argument("--input", required=True, help="原始输入文件路径")
    p.add_argument("--check", required=True,
                   help="复现验证命令，{input} 占位；exit 0 = 仍复现，非 0 = 不再复现")
    p.add_argument("--timeout", type=float, default=30,
                   help="单次验证超时秒数（默认 30）")
    return p.parse_args()


class Minimizer:
    def __init__(self, cmd: str, check: str, timeout: float):
        self.cmd = cmd
        self.check = check
        self.timeout = timeout

    def reproduces(self, data: bytes, tmp: Path) -> bool:
        """data 写入临时文件，跑验证命令；exit 0 = 仍复现。"""
        inp = tmp / "input"
        inp.write_bytes(data)
        for template in (self.cmd, self.check):
            if "{input}" not in template:
                continue
        cmd = self.cmd.replace("{input}", str(inp))
        chk = self.check.replace("{input}", str(inp))
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True,
                               timeout=self.timeout)
            if r.returncode == 0:
                r2 = subprocess.run(chk, shell=True, capture_output=True,
                                    timeout=self.timeout)
                return r2.returncode == 0
            return False
        except subprocess.TimeoutExpired:
            return False

    def ddmin(self, data: bytes, tmp: Path) -> bytes:
        """经典 ddmin：按粒度 2 起逐步分块删除。"""
        n = 2
        while len(data) >= 2:
            chunk = (len(data) + n - 1) // n
            reduced = False
            for start in range(0, len(data), chunk):
                candidate = data[:start] + data[start + chunk:]
                if candidate and self.reproduces(candidate, tmp):
                    data = candidate
                    n = max(n - 1, 2)
                    reduced = True
                    break
            if not reduced:
                if n >= len(data):
                    break
                n = min(n * 2, len(data))
        return data


def main() -> int:
    args = parse_args()
    src = Path(args.input)
    if not src.is_file():
        print(f"[minimize_repro] 输入文件不存在: {src}")
        return 2
    original = src.read_bytes()
    m = Minimizer(args.cmd, args.check, args.timeout)

    with tempfile.TemporaryDirectory(prefix="ddmin-") as td:
        tmp = Path(td)
        # 先确认原始输入确实复现
        if not m.reproduces(original, tmp):
            print("[minimize_repro] ✗ 原始输入不触发复现（check 返回非 0 或超时）——")
            print("  先确认 --cmd/--check 正确。不进行最小化。")
            return 1
        print(f"[minimize_repro] 原始输入可复现，开始最小化 "
              f"（{len(original)} 字节）…")
        minimized = m.ddmin(original, tmp)

    out = src.with_name(src.name + ".min")
    out.write_bytes(minimized)
    print(f"[minimize_repro] 完成: {len(original)} → {len(minimized)} 字节 "
          f"（缩减 {100 * (1 - len(minimized) / len(original)):.1f}%）")
    print(f"[minimize_repro] 最小输入已写入: {out}")
    print(f"[minimize_repro] 校验：最小输入仍复现 = "
          f"{'是' if m.reproduces(minimized, Path('/tmp')) else '否'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
