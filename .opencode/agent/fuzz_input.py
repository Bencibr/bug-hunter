#!/usr/bin/env python3
"""fuzz_input.py — 变异模糊矩阵工具（并发批量轰输入，筛出异常样本）。

用途：取一份合法输入，逐字段/逐字节变异成批量变体，**并发**喂给目标，
收集每次 exit code + 输出，筛出异常样本（崩溃/挂起/非零退出）供进一步
最小化与根因分析。与 minimize_repro.py 配套：fuzz 负责"广撒网找异常"，
minimize 负责"把异常缩到最小复现"。

用法：
  python3 fuzz_input.py --input <合法输入文件> \
      --cmd '<目标命令，{input} 占位>' \
      --out <输出目录> [--count N] [--jobs P] [--timeout S] [--seed S]

示例：
  # 对 json 解析器变异 500 个样本，8 并发，异常存到 /tmp/fuzz-out
  python3 fuzz_input.py \
      --input valid.json --cmd 'python3 -m json.tool {input}' \
      --out /tmp/fuzz-out --count 500 --jobs 8

变异策略（each sample applies one random strategy）：
  - truncate      截断文件尾部（模拟不完整数据）
  - flip_byte     随机翻转一个字节
  - insert_garbage 在随机位置插入一段垃圾字节
  - mutate_numeric 把数字字段放大/改负/改零（正则）
  - mutate_string 把字符串字段换成超长/CJK/emoji/控制字符
  - duplicate     重复文件中间一段（制造超大/重复结构）

筛选标准：目标进程 exit code 非 0（崩溃/报错）或超时（挂起）→ 记为异常样本，
原始输入与 stderr 一并保存到输出目录。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="合法输入文件路径")
    p.add_argument("--cmd", required=True,
                   help="目标命令，用 {input} 占位表示输入文件路径")
    p.add_argument("--out", required=True, help="异常样本输出目录")
    p.add_argument("--count", type=int, default=100, help="变异样本数（默认 100）")
    p.add_argument("--jobs", type=int, default=4, help="并发数（默认 4）")
    p.add_argument("--timeout", type=float, default=10, help="单次执行超时秒（默认 10）")
    p.add_argument("--seed", type=int, default=None, help="随机种子（可复现）")
    return p.parse_args()


# ---------- 变异策略 ----------

def _mutate_truncate(data: bytes, rng: random.Random) -> bytes:
    if len(data) <= 1:
        return b""
    cut = rng.randint(1, len(data) - 1)
    return data[:cut]


def _mutate_flip_byte(data: bytes, rng: random.Random) -> bytes:
    if not data:
        return data
    pos = rng.randrange(len(data))
    val = data[pos] ^ (1 << rng.randrange(8))
    return data[:pos] + bytes([val]) + data[pos + 1:]


def _mutate_insert_garbage(data: bytes, rng: random.Random) -> bytes:
    garbage = bytes(
        rng.choice(b"\x00\xff\x7f\\n\r\x01\x1b") for _ in range(rng.randint(1, 16))
    )
    pos = rng.randrange(len(data) + 1)
    return data[:pos] + garbage + data[pos:]


_NUM_RE = re.compile(rb"-?\d+\.?\d*")

def _mutate_numeric(data: bytes, rng: random.Random) -> bytes:
    choices = [b"0", b"-1", b"999999999999999999999", b"1e999", b"-0.0"]
    def repl(m: re.Match) -> bytes:
        return rng.choice(choices)
    return _NUM_RE.sub(repl, data, count=rng.randint(1, 3))


_STR_FILL = [b"a" * 1000, "你好世界".encode(), "🎉🎉🎉".encode(),
             b"\x00\x01\x02", b"%s%s%s%s"]

def _mutate_string(data: bytes, rng: random.Random) -> bytes:
    def repl(m: re.Match) -> bytes:
        return rng.choice(_STR_FILL)
    return _NUM_RE.sub(repl, data, count=rng.randint(1, 2))


def _mutate_duplicate(data: bytes, rng: random.Random) -> bytes:
    if not data:
        return data
    mid = len(data) // 2
    chunk = data[mid:mid + rng.randint(1, max(1, len(data) // 4))]
    return data + chunk


STRATEGIES = [
    ("truncate", _mutate_truncate),
    ("flip_byte", _mutate_flip_byte),
    ("insert_garbage", _mutate_insert_garbage),
    ("mutate_numeric", _mutate_numeric),
    ("mutate_string", _mutate_string),
    ("duplicate", _mutate_duplicate),
]


def mutate(data: bytes, rng: random.Random) -> tuple[str, bytes]:
    """对输入施加一个随机变异策略，返回 (策略名, 变异后数据)。"""
    name, fn = rng.choice(STRATEGIES)
    return name, fn(data, rng)


# ---------- 执行与筛选 ----------

def _run_target(cmd: str, payload: bytes, tmp: Path,
                timeout: float) -> subprocess.CompletedProcess:
    inp = tmp / "input"
    inp.write_bytes(payload)
    cmd = cmd.replace("{input}", str(inp))
    return subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)


def fuzz_once(cmd: str, data: bytes, rng: random.Random, tmp: Path,
              timeout: float, idx: int) -> dict | None:
    """跑一个变异样本；异常（非零退出/超时）返回记录，正常返回 None。"""
    name, payload = mutate(data, rng)
    try:
        r = _run_target(cmd, payload, tmp, timeout)
    except subprocess.TimeoutExpired:
        return {
            "idx": idx, "strategy": name, "kind": "timeout",
            "exit": "TIMEOUT", "len": len(payload), "payload": payload,
        }
    if r.returncode != 0:
        return {
            "idx": idx, "strategy": name, "kind": "crash",
            "exit": r.returncode, "len": len(payload), "payload": payload,
            "stderr": r.stderr[:2000],
        }
    return None


def main() -> int:
    args = parse_args()
    src = Path(args.input)
    if not src.is_file():
        print(f"[fuzz_input] 输入文件不存在: {src}")
        return 2
    data = src.read_bytes()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    crashes_dir = out / "crashes"
    crashes_dir.mkdir(exist_ok=True)

    print(f"[fuzz_input] 目标: {src.name} ({len(data)} 字节) "
          f"样本={args.count} 并发={args.jobs} 种子={args.seed or '随机'}")
    crashes: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="fuzz-") as td:
        tmp = Path(td)
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {
                pool.submit(fuzz_once, args.cmd, data, rng, tmp,
                            args.timeout, i): i
                for i in range(args.count)
            }
            for fut in as_completed(futs):
                try:
                    res = fut.result()
                except Exception as e:  # noqa: BLE001
                    print(f"  ! 任务异常: {e}")
                    continue
                if res is not None:
                    crashes.append(res)

    # 写异常样本
    meta = out / "summary.json"
    records = []
    for c in sorted(crashes, key=lambda x: x["idx"]):
        fn = crashes_dir / f"crash-{c['idx']:04d}-{c['strategy']}-exit{c['exit']}"
        fn.write_bytes(c["payload"])
        rec = {k: v for k, v in c.items() if k != "payload"}
        if isinstance(rec.get("stderr"), bytes):
            rec["stderr"] = rec["stderr"].decode("utf-8", errors="replace")
        rec["file"] = fn.name
        records.append(rec)
    meta.write_text(
        json.dumps({"total": args.count, "anomalies": len(crashes),
                    "crashes": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    by_kind: dict[str, int] = {}
    for c in crashes:
        by_kind[c["kind"]] = by_kind.get(c["kind"], 0) + 1
    print(f"[fuzz_input] 完成: {args.count} 样本, 异常 {len(crashes)} 个"
          f"（{by_kind}）")
    print(f"[fuzz_input] 异常样本已写入: {crashes_dir}")
    print(f"[fuzz_input] 汇总: {meta}")
    if crashes:
        print("  下一步: 用 minimize_repro.py 把异常样本缩到最小复现，再定位根因。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
