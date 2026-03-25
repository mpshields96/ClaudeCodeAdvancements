#!/usr/bin/env python3
"""consistency_checker.py — MT-32 Phase 4: Cross-format design consistency.

Audits Python source files of output generators (dashboard, report, slides,
charts, website) to verify they use the canonical CCA design tokens rather
than hardcoded values. Catches design drift across output formats.

Unlike design_linter.py (which checks generated HTML/SVG output), this
checks the SOURCE CODE that produces those outputs.

Usage:
    python3 design-skills/consistency_checker.py                    # Audit all generators
    python3 design-skills/consistency_checker.py --file <path.py>   # Audit one file
    python3 design-skills/consistency_checker.py --json              # JSON output

Stdlib only. No external dependencies. One file = one job.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Canonical design tokens — the single source of truth is design_linter.py
try:
    from design_linter import (
        CCA_PALETTE, SERIES_COLORS, SAFE_COLORS, APPROVED_FONTS,
        VALID_SPACING, ALL_APPROVED_COLORS,
    )
except ImportError:
    # Fallback if import fails (e.g. running from different cwd)
    sys.path.insert(0, str(SCRIPT_DIR))
    from design_linter import (
        CCA_PALETTE, SERIES_COLORS, SAFE_COLORS, APPROVED_FONTS,
        VALID_SPACING, ALL_APPROVED_COLORS,
    )

# Files to audit — all Python generators that produce visual output
GENERATOR_FILES = [
    SCRIPT_DIR / "dashboard_generator.py",
    SCRIPT_DIR / "chart_generator.py",
    SCRIPT_DIR / "report_generator.py",
    SCRIPT_DIR / "slide_generator.py",
    SCRIPT_DIR / "website_generator.py",
    SCRIPT_DIR / "report_charts.py",
    SCRIPT_DIR / "design_linter.py",
    PROJECT_ROOT / "design-skills" / "efficiency_dashboard.py",
    PROJECT_ROOT / "coordination_dashboard.py",
]

# Patterns
HEX_IN_STRING_RE = re.compile(r'["\']#([0-9a-fA-F]{6})["\']')
HEX_IN_FSTRING_RE = re.compile(r'#([0-9a-fA-F]{6})')
FONT_IN_STRING_RE = re.compile(r'font-family:\s*([^;}"\']+)', re.IGNORECASE)
DICT_COLOR_RE = re.compile(r'["\'](#[0-9a-fA-F]{6})["\']')

# Lines that define color constants/dicts should be skipped (they ARE the tokens)
TOKEN_DEF_PATTERNS = [
    re.compile(r'^\s*["\']?\w+["\']?\s*:\s*["\']#'),  # Dict entries: "key": "#hex"
    re.compile(r'^\s*\w+\s*=\s*["\']#'),               # Variable: VAR = "#hex"
    re.compile(r'^\s*["\']#[0-9a-fA-F]{6}["\'],?\s*#'), # List entry with comment
    re.compile(r'CCA_PALETTE|SERIES_COLORS|SAFE_COLORS|CHART_COLORS|COLORS'),
    re.compile(r'^\s*#'),  # Python comments
]


@dataclass
class Issue:
    """A consistency issue found in source code."""
    file: str
    line_num: int
    category: str  # "orphan_color", "inline_color", "font_mismatch", "shared_token"
    severity: str  # "error", "warning", "info"
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def _is_token_definition(line: str) -> bool:
    """Check if this line is defining color tokens (should be skipped)."""
    return any(p.search(line) for p in TOKEN_DEF_PATTERNS)


def _extract_colors_from_source(content: str) -> list[tuple[int, str, str]]:
    """Extract (line_num, hex_color, full_line) from Python source."""
    results = []
    for i, line in enumerate(content.split("\n"), 1):
        if _is_token_definition(line):
            continue
        for match in HEX_IN_FSTRING_RE.finditer(line):
            color = f"#{match.group(1)}"
            results.append((i, color, line.strip()))
    return results


def audit_colors(filepath: Path, content: str) -> list[Issue]:
    """Check for hardcoded hex colors not referencing design tokens."""
    issues = []
    colors = _extract_colors_from_source(content)

    try:
        rel_path = str(filepath.relative_to(PROJECT_ROOT))
    except ValueError:
        rel_path = str(filepath)

    for line_num, color, line_text in colors:
        color_lower = color.lower()
        if color_lower not in {c.lower() for c in ALL_APPROVED_COLORS}:
            issues.append(Issue(
                file=rel_path,
                line_num=line_num,
                category="orphan_color",
                severity="error",
                detail=f"Unapproved color {color} in source. Use CCA palette token.",
            ))

    return issues


def audit_token_sharing(filepaths: list[Path]) -> list[Issue]:
    """Check that all generators import from the same token source.

    If generators define their own color dicts instead of importing from
    design_linter.py or a shared tokens module, the values will drift.
    """
    issues = []
    color_dict_re = re.compile(r'^\s*COLORS\s*=\s*\{', re.MULTILINE)
    import_linter_re = re.compile(r'from\s+design_linter\s+import|import\s+design_linter')

    for fp in filepaths:
        if not fp.exists() or fp.name == "design_linter.py":
            continue
        content = fp.read_text()

        has_local_colors = bool(color_dict_re.search(content))
        imports_linter = bool(import_linter_re.search(content))

        if has_local_colors and not imports_linter:
            try:
                rel_path = str(fp.relative_to(PROJECT_ROOT))
            except ValueError:
                rel_path = str(fp)
            issues.append(Issue(
                file=rel_path,
                line_num=0,
                category="shared_token",
                severity="warning",
                detail="Defines local COLORS dict without importing from design_linter. Values may drift.",
            ))

    return issues


def audit_font_consistency(filepaths: list[Path]) -> list[Issue]:
    """Check that all generators use the same primary font family."""
    issues = []
    primary_font_re = re.compile(r'font-family:\s*([^;}"\']+)', re.IGNORECASE)

    font_usage: dict[str, list[str]] = {}  # font -> [files]

    for fp in filepaths:
        if not fp.exists():
            continue
        content = fp.read_text()
        for i, line in enumerate(content.split("\n"), 1):
            # Skip regex definitions, comments, and token definition lines
            if _is_token_definition(line) or "re.compile" in line or "RE = " in line:
                continue
            matches = primary_font_re.findall(line)
            for match in matches:
                # Skip f-string interpolation artifacts
                if "{" in match or "(" in match:
                    continue
                first_font = match.split(",")[0].strip().strip("'\"").lower()
                if first_font:
                    font_usage.setdefault(first_font, []).append(fp.name)

    # If more than one primary font family is used across generators, flag it
    primary_fonts = {f for f in font_usage if f not in {"monospace", "serif", "sans-serif"}}
    if len(primary_fonts) > 1:
        for font, files in font_usage.items():
            if font in primary_fonts:
                issues.append(Issue(
                    file=", ".join(sorted(set(files))),
                    line_num=0,
                    category="font_mismatch",
                    severity="warning",
                    detail=f"Font '{font}' used in {len(set(files))} files. Multiple primary fonts detected across generators.",
                ))

    return issues


def run_audit(filepaths: list[Path] | None = None) -> dict:
    """Run full consistency audit across all generators."""
    if filepaths is None:
        filepaths = [fp for fp in GENERATOR_FILES if fp.exists()]

    all_issues: list[Issue] = []

    # Per-file audits
    for fp in filepaths:
        if not fp.exists():
            continue
        content = fp.read_text()
        all_issues.extend(audit_colors(fp, content))

    # Cross-file audits
    all_issues.extend(audit_token_sharing(filepaths))
    all_issues.extend(audit_font_consistency(filepaths))

    errors = sum(1 for i in all_issues if i.severity == "error")
    warnings = sum(1 for i in all_issues if i.severity == "warning")

    return {
        "passed": errors == 0,
        "files_audited": len([fp for fp in filepaths if fp.exists()]),
        "total_issues": len(all_issues),
        "errors": errors,
        "warnings": warnings,
        "issues": [i.to_dict() for i in all_issues],
    }


def main():
    """CLI entrypoint."""
    args = sys.argv[1:]

    if "--file" in args:
        idx = args.index("--file")
        filepath = Path(args[idx + 1]) if idx + 1 < len(args) else None
        if not filepath or not filepath.exists():
            print(f"File not found: {filepath}")
            sys.exit(1)
        result = run_audit([filepath])
    else:
        result = run_audit()

    if "--json" in args:
        print(json.dumps(result, indent=2))
    else:
        status = "PASSED" if result["passed"] else "FAILED"
        print(f"Consistency Audit: {status}")
        print(f"  Files: {result['files_audited']}")
        print(f"  Errors: {result['errors']}, Warnings: {result['warnings']}")

        if result["issues"]:
            print()
            for issue in result["issues"]:
                prefix = "ERROR" if issue["severity"] == "error" else "WARN"
                loc = f"{issue['file']}:{issue['line_num']}" if issue['line_num'] else issue['file']
                print(f"  [{prefix}] {loc} — {issue['detail']}")

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
