#!/usr/bin/env python3
"""prep_validate.py — 开工准备记录的结构/知识库门禁。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent.parent
REQUIRED = (
    "## 项目识别",
    "## 测试类型",
    "## 工具调研",
    "## 工具选择",
    "## 工具就绪",
    "## 多工具协作",
    "## 准备结论",
)
PLACEHOLDERS = ("待填写", "TODO", "<待", "...", "未填写")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
NEGATIVE_RE = re.compile(r"(?:不可以|不能|未完成|未就绪|失败|\bno\b)", re.I)


def _section_bodies(text: str) -> dict[str, str]:
    """按二级标题切分正文，避免仅出现标题就绕过准备门禁。"""
    headings = list(re.finditer(r"^## .+$", text, re.M))
    bodies: dict[str, str] = {}
    for i, match in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[match.end():end]
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S).strip()
        bodies[match.group(0).strip()] = body
    return bodies


def check(record: Path | None = None, root: Path = REPO_ROOT) -> tuple[int, list[str]]:
    record = record or root / ".opencode" / "agent" / "prep-record.md"
    errors: list[str] = []
    if not record.is_file():
        return 1, [f"缺少准备记录: {record}"]
    text = record.read_text(encoding="utf-8")
    bodies = _section_bodies(text)
    for heading in REQUIRED:
        if heading not in bodies:
            errors.append(f"缺少章节: {heading}")
            continue
        body = bodies[heading]
        if not body or any(p in body for p in PLACEHOLDERS):
            errors.append(f"章节未填写: {heading}")
    research = bodies.get("## 工具调研", "")
    if "本地命中" not in research and not re.search(r"https?://|github\.com/", research):
        errors.append("工具调研缺本地命中说明或公开来源 URL")
    if research and not DATE_RE.search(research):
        errors.append("工具调研缺 YYYY-MM-DD 验证日期")
    readiness = bodies.get("## 工具就绪", "")
    if (not re.search(r"(?:是否可以开工|可以开工)\s*[：:]?\s*(?:是|可以|通过|已就绪)", readiness)
            or NEGATIVE_RE.search(readiness)):
        errors.append("工具就绪未明确确认『可以开工：是』")
    conclusion = bodies.get("## 准备结论", "")
    if (not re.search(r"(?:准备完成|可以开工|结论\s*[：:]?\s*通过)", conclusion)
            or NEGATIVE_RE.search(conclusion)):
        errors.append("准备结论未明确是否可以开工")
    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    rc, errors = check(args.record, args.root)
    if errors:
        print(f"[prep_validate] 失败（{len(errors)} 项）:")
        for error in errors:
            print(f"  ✗ {error}")
    else:
        print("[prep_validate] OK: 项目识别、测试类型、工具调研/选择/就绪、协作记录完整")
    return rc


if __name__ == "__main__":
    sys.exit(main())
