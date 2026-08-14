#!/usr/bin/env python3
"""tools_kb.py — tools-kb.md 的验证日期/30 天有效期检查器。

用法：
  python3 tools_kb.py check
  python3 tools_kb.py status

exit 0 = 所有工具条目日期格式正确且在有效期内；
exit 1 = 存在过期/未来/缺日期条目；
exit 2 = 知识库缺失或格式不可解析。
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from dataclasses import dataclass
from pathlib import Path

KB_FILE = Path(__file__).resolve().parent / "tools-kb.md"
MAX_AGE_DAYS = 30
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Entry:
    line: int
    name: str
    date: dt.date | None
    error: str | None = None


def read_entries(path: Path = KB_FILE) -> list[Entry]:
    if not path.is_file():
        raise FileNotFoundError(path)
    entries: list[Entry] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"工具", "语言", "数据库"}:
            continue
        # 工具表的日期是最后一列；没有日期的普通 Markdown 行不计入条目。
        date_text = cells[-1]
        if date_text in {"说明", "用途", "来源", "验证日期"}:
            continue
        if not DATE_RE.match(date_text):
            # 只有看起来像工具表的行才报缺日期；分隔线跳过。
            if set(date_text) <= {"-", " "}:
                continue
            if len(cells) >= 4:
                entries.append(Entry(number, cells[0], None, "缺少 YYYY-MM-DD 验证日期"))
            continue
        try:
            parsed = dt.date.fromisoformat(date_text)
        except ValueError:
            entries.append(Entry(number, cells[0], None, f"日期无效: {date_text}"))
            continue
        entries.append(Entry(number, cells[0], parsed))
    return entries


def check(path: Path = KB_FILE, today: dt.date | None = None,
          max_age: int = MAX_AGE_DAYS) -> tuple[int, list[str]]:
    today = today or dt.date.today()
    try:
        entries = read_entries(path)
    except (FileNotFoundError, OSError) as exc:
        return 2, [f"知识库无法读取: {exc}"]
    if not entries:
        return 2, ["知识库没有可验证的工具条目"]
    errors: list[str] = []
    for entry in entries:
        if entry.error:
            errors.append(f"第 {entry.line} 行 {entry.name}: {entry.error}")
            continue
        assert entry.date is not None
        age = (today - entry.date).days
        if age < 0:
            errors.append(f"第 {entry.line} 行 {entry.name}: 验证日期在未来 {entry.date}")
        elif age > max_age:
            errors.append(f"第 {entry.line} 行 {entry.name}: 已过期 {age} 天（上限 {max_age}）")
    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "status"), nargs="?", default="check")
    parser.add_argument("--today", help="测试用日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--max-age", type=int, default=MAX_AGE_DAYS)
    args = parser.parse_args(argv)
    today = dt.date.fromisoformat(args.today) if args.today else None
    rc, errors = check(today=today, max_age=args.max_age)
    entries = read_entries() if rc != 2 else []
    print(f"[tools_kb] 条目 {len(entries)}，有效期 {args.max_age} 天")
    if errors:
        for error in errors:
            print(f"  ✗ {error}")
        print("[tools_kb] 请重新搜索过期条目，并更新 tools-kb.md 的验证日期/来源")
    else:
        print("[tools_kb] OK: 所有条目在有效期内")
    return rc


if __name__ == "__main__":
    sys.exit(main())
