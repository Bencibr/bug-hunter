#!/usr/bin/env python3
"""module_coverage.py — 模块清单结构/路径/覆盖门禁。

这是「全覆盖宪法」的外部检查器，不相信 agent 口头报告：
  check       校验清单结构、路径、工具、证据字段，并报告当前进度
  final-check 要求所有真实模块行都是「已覆盖」，且 X/Y == Y/Y

清单格式由 module-coverage.md 定义。模块行必须提供：路径、难度、命中、
主工具、负责任务、状态、发现数、证据/测试。示例行（含「示例」）只用于模板展示，
严格检查时不会被当作真实模块。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent.parent
MANIFEST = AGENT_DIR / "module-coverage.md"
VALID_STATUS = {"未覆盖", "挖掘中", "挂起", "已覆盖"}
EXCLUDED_DIRS = {
    ".git", ".opencode", ".code-review-graph", "node_modules", "target", "build",
    "dist", ".venv", "venv", "__pycache__", ".gradle", "vendor", "third_party",
    "tests", "test", "__tests__", "docs", "examples",
}
SOURCE_ROOTS = (
    "src", "app", "lib", "libs", "packages", "modules", "crates", "cmd",
    "internal", "services", "server", "client", "frontend", "backend",
)
SOURCE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".kts", ".go",
    ".rs", ".swift", ".c", ".h", ".cc", ".cpp", ".cxx", ".cs", ".rb",
    ".php", ".vue", ".svelte",
}
EVIDENCE_EXTS = SOURCE_EXTS | {
    ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".md",
    ".txt", ".log", ".png", ".jpg", ".jpeg", ".webp",
}
EVIDENCE_PATH_RE = re.compile(
    r"`([^`]+)`|([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]+(?:\:\:\w+|\:\d+)?)"
)


@dataclass(frozen=True)
class ModuleRow:
    number: str
    name: str
    path: str
    difficulty: str
    hit: str
    tool: str
    owner: str
    deps: str
    status: str
    findings: str
    evidence: str
    note: str


def _cells(line: str) -> list[str]:
    return [x.strip() for x in line.strip().strip("|").split("|")]


def parse_manifest(path: Path = MANIFEST) -> tuple[list[ModuleRow], list[str]]:
    """解析模块 Markdown 表，返回 rows + 结构错误。"""
    if not path.is_file():
        return [], [f"缺少模块清单: {path}"]
    lines = path.read_text(encoding="utf-8").splitlines()
    header_index = next(
        (i for i, line in enumerate(lines)
         if "路径/范围" in line and "状态" in line),
        None,
    )
    if header_index is None:
        return [], ["模块清单缺少包含『路径/范围』和『状态』的表头"]
    header = _cells(lines[header_index])
    errors: list[str] = []
    required = {"模块", "路径/范围", "状态", "发现数", "主工具", "负责任务", "证据/测试"}
    missing = required - set(header)
    if missing:
        errors.append(f"模块清单表头缺少字段: {sorted(missing)}")
    index = {name: i for i, name in enumerate(header)}
    rows: list[ModuleRow] = []
    for line_no, line in enumerate(lines[header_index + 2:], header_index + 3):
        if not line.strip().startswith("|") or "---" in line:
            continue
        cells = _cells(line)
        if len(cells) < len(header):
            errors.append(f"第 {line_no} 行列数不足: {len(cells)}/{len(header)}")
            continue
        get = lambda key: cells[index[key]] if key in index else ""
        row = ModuleRow(
            number=get("#"), name=get("模块"), path=get("路径/范围"),
            difficulty=get("难度"), hit=get("命中"), tool=get("主工具"),
            owner=get("负责任务"), deps=get("依赖"), status=get("状态"), findings=get("发现数"),
            evidence=get("证据/测试"), note=get("备注"),
        )
        if "示例" in row.name or "示例" in row.path:
            continue
        rows.append(row)
    return rows, errors


def _resolve_in_root(path: str, root: Path) -> Path | None:
    """解析仓库内路径；拒绝绝对路径/符号链接逃出审计根目录。"""
    clean = path.strip().strip("`").rstrip("/")
    if not clean or clean in {"-", "N/A", "待定"}:
        return None
    p = Path(clean)
    candidate = p if p.is_absolute() else root / p
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError):
        return None
    return resolved


def _path_exists(path: str, root: Path) -> bool:
    return _resolve_in_root(path, root) is not None


def _evidence_real(evidence: str, root: Path) -> bool:
    """证据必须引用仓库内真实文件，可带 :行号 或 ::test_name。"""
    for match in EVIDENCE_PATH_RE.finditer(evidence):
        raw = next((group for group in match.groups() if group), "")
        clean = raw.split("::", 1)[0]
        line = None
        line_match = re.search(r":(\d+)$", clean)
        if line_match:
            line = int(line_match.group(1))
            clean = clean[:line_match.start()]
        resolved = _resolve_in_root(clean, root)
        if not resolved or not resolved.is_file() or resolved.suffix.lower() not in EVIDENCE_EXTS:
            continue
        if line is not None:
            try:
                with resolved.open("r", encoding="utf-8", errors="replace") as handle:
                    line_count = sum(1 for _ in handle)
                if not 1 <= line <= line_count:
                    continue
            except OSError:
                continue
        return True
    return False


def _has_source(path: Path) -> bool:
    try:
        return any(
            p.is_file() and p.suffix.lower() in SOURCE_EXTS
            for p in path.rglob("*")
            if not any(part in EXCLUDED_DIRS for part in p.parts)
        )
    except OSError:
        return False


def discover_module_paths(root: Path) -> set[str]:
    """发现常见源码根下的一级模块，防止清单漏列整个模块。

    这是保守的完整性检查：它不替代人工拆分嵌套模块，但能拦住最危险的
    逃逸——把一个大型源码目录完全漏出清单。
    """
    candidates: set[str] = set()
    roots = [root / name for name in SOURCE_ROOTS if (root / name).is_dir()]
    if not roots:
        roots = [
            p for p in root.iterdir()
            if p.is_dir() and p.name not in EXCLUDED_DIRS and _has_source(p)
        ] if root.is_dir() else []
    for base in roots:
        children = [
            p for p in base.iterdir()
            if p.is_dir() and p.name not in EXCLUDED_DIRS and _has_source(p)
        ]
        if children:
            candidates.update(str(p.relative_to(root)) for p in children)
        elif _has_source(base):
            candidates.add(str(base.relative_to(root)))
    # 没有源码目录时，纳入顶层源码文件作为模块。
    if not candidates and root.is_dir():
        candidates.update(
            str(p.relative_to(root)) for p in root.iterdir()
            if p.is_file() and p.suffix.lower() in SOURCE_EXTS
        )
    return candidates


def validate_rows(rows: list[ModuleRow], root: Path = REPO_ROOT,
                 final: bool = False) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    if not rows:
        errors.append("模块清单没有真实模块行（不能用空清单伪造 100% 覆盖）")
    for row in rows:
        label = f"#{row.number} {row.name}"
        resolved = _resolve_in_root(row.path, root)
        normalized = str(resolved) if resolved else row.path.strip().strip("`").rstrip("/")
        if normalized in seen:
            errors.append(f"{label}: 模块路径重复: {row.path}")
        seen.add(normalized)
        if resolved is None:
            errors.append(f"{label}: 模块路径不存在或逃出仓库根目录: {row.path}")
        try:
            difficulty = int(row.difficulty)
            hit = int(row.hit)
            if not 1 <= difficulty <= 5 or not 1 <= hit <= 5:
                raise ValueError
        except ValueError:
            errors.append(f"{label}: 难度/命中必须是 1-5")
        if row.status not in VALID_STATUS:
            errors.append(f"{label}: 状态无效: {row.status!r}")
        try:
            if int(row.findings) < 0:
                raise ValueError
        except ValueError:
            errors.append(f"{label}: 发现数必须是非负整数")
        if not row.tool or row.tool in {"待定", "-"}:
            errors.append(f"{label}: 缺主工具（复杂项目协作责任不可为空）")
        if not row.owner or row.owner in {"待定", "-"}:
            errors.append(f"{label}: 缺负责任务（必须明确谁/哪个并行任务负责）")
        if not row.evidence or row.evidence in {"待定", "待补", "-"}:
            errors.append(f"{label}: 缺证据/测试记录")
        elif not _evidence_real(row.evidence, root):
            errors.append(
                f"{label}: 证据必须引用仓库内现有文件（可带 :行号 或 ::test_name）"
            )
    if final:
        listed = {row.path.strip().strip("`").rstrip("/") for row in rows}
        discovered = {p.rstrip("/") for p in discover_module_paths(root)}
        omitted = sorted(p for p in discovered if p not in listed)
        if omitted:
            errors.append(
                "最终覆盖门禁发现清单漏列模块: " + ", ".join(omitted)
            )
    if final:
        uncovered = [r for r in rows if r.status != "已覆盖"]
        if uncovered:
            errors.append(
                "最终覆盖门禁失败: "
                + ", ".join(f"#{r.number} {r.name}={r.status}" for r in uncovered)
            )
    return errors


def check(final: bool = False, root: Path = REPO_ROOT,
          manifest: Path = MANIFEST) -> int:
    rows, errors = parse_manifest(manifest)
    errors.extend(validate_rows(rows, root, final=final))
    covered = sum(r.status == "已覆盖" for r in rows)
    total = len(rows)
    print(f"[module_coverage] 覆盖: {covered}/{total} ({(covered / total * 100) if total else 0:.1f}%)")
    if errors:
        print(f"[module_coverage] 失败（{len(errors)} 项）:")
        for error in errors:
            print(f"  ✗ {error}")
        return 1
    print("[module_coverage] OK: 清单结构、模块路径、责任工具、证据均有效")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "final-check"), nargs="?",
                        default="check")
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args(argv)
    return check(args.command == "final-check", args.root, args.manifest)


if __name__ == "__main__":
    sys.exit(main())
