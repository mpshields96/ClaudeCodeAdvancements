#!/usr/bin/env python3
"""design_linter.py — MT-32 Phase 3: Design system lint rules.

Checks HTML/SVG output for design token compliance. Detects:
- Orphan hex colors not in the CCA palette
- Unapproved font families
- Spacing values off the 8px grid
- AI-slop patterns (purple/indigo defaults, Tailwind classes, rounded-full)

Usage:
    python3 design-skills/design_linter.py <file.html>
    python3 design-skills/design_linter.py --check-all design-skills/templates/

Stdlib only. No external dependencies. One file = one job.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from typing import Optional

import design_tokens

# --- Import canonical tokens, extend with linter-specific values ---

CCA_PALETTE = design_tokens.CCA_PALETTE
SERIES_COLORS = design_tokens.SERIES_COLORS
ANTI_SLOP_COLORS = design_tokens.ANTI_SLOP_COLORS

# Linter extends the canonical dark palette with extra dashboard-specific colors
DARK_PALETTE = {
    **design_tokens.DARK_PALETTE,
    "dark_muted": "#8b949e",
    "dark_accent": "#388bfd",
    "dark_highlight": "#f85149",
    "dark_success": "#3fb950",
    "dark_warning": "#d29922",
    "dark_text": "#e6edf3",
}

# Common safe colors that should never trigger violations
SAFE_COLORS = {
    "#000000", "#ffffff", "#000", "#fff",
    "#333333", "#666666", "#999999", "#cccccc",
    "#f0f0f0", "#fafafa", "#f5f5f5",
    "none", "transparent",
}

ALL_APPROVED_COLORS = (
    set(CCA_PALETTE.values())
    | set(DARK_PALETTE.values())
    | set(SERIES_COLORS)
    | SAFE_COLORS
)

# Approved font families (extends canonical list with linter-specific extras)
APPROVED_FONTS = set(design_tokens.APPROVED_FONTS) | {
    "source sans pro", "helvetica", "monospace", "serif", "system-ui",
}

# Tailwind anti-patterns
TAILWIND_SLOP_RE = re.compile(
    r'(?:bg|text|border)-(?:indigo|purple|violet)-\d{3}'
)
ROUNDED_FULL_RE = re.compile(r'rounded-full')

# Spacing grid: 0, 1, 2, 4, 8, 12, 16, 20, 24, 32, 48, 64 (px)
VALID_SPACING = {0, 1, 2, 3, 4, 6, 8, 12, 16, 20, 24, 32, 48, 64}

# Regex patterns
HEX_COLOR_RE = re.compile(r'#[0-9a-fA-F]{6}(?![0-9a-fA-F])')
FONT_FAMILY_RE = re.compile(r'font-family:\s*([^;}"]+)', re.IGNORECASE)
SPACING_RE = re.compile(r'(?:padding|margin|gap)(?:-\w+)?:\s*(\d+)px', re.IGNORECASE)


@dataclass
class Violation:
    """A single lint violation."""
    category: str  # "color", "font", "spacing", "anti-slop"
    severity: str  # "error", "warning"
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def lint_colors(content: str) -> list[Violation]:
    """Check for hex colors not in the CCA palette."""
    if not content:
        return []

    violations = []
    found_colors = set(HEX_COLOR_RE.findall(content))

    for color in found_colors:
        color_lower = color.lower()
        if color_lower not in {c.lower() for c in ALL_APPROVED_COLORS}:
            violations.append(Violation(
                category="color",
                severity="error",
                detail=f"Orphan color {color} not in CCA palette. Use a named token.",
            ))

    return violations


def lint_fonts(content: str) -> list[Violation]:
    """Check for unapproved font families."""
    if not content:
        return []

    violations = []
    matches = FONT_FAMILY_RE.findall(content)

    for match in matches:
        # Parse comma-separated font list
        fonts = [f.strip().strip("'\"").lower() for f in match.split(",")]
        for font in fonts:
            if font and font not in APPROVED_FONTS:
                violations.append(Violation(
                    category="font",
                    severity="warning",
                    detail=f"Unapproved font '{font}'. Use Source Sans 3 or approved fallbacks.",
                ))

    return violations


def lint_spacing(content: str) -> list[Violation]:
    """Check for spacing values off the 8px base grid."""
    if not content:
        return []

    violations = []
    matches = SPACING_RE.findall(content)

    for px_str in matches:
        px = int(px_str)
        if px not in VALID_SPACING:
            violations.append(Violation(
                category="spacing",
                severity="warning",
                detail=f"Spacing {px}px is off-grid. Use: {sorted(VALID_SPACING)}",
            ))

    return violations


def lint_anti_slop(content: str) -> list[Violation]:
    """Check for AI-slop patterns: purple defaults, Tailwind classes, rounded-full."""
    if not content:
        return []

    violations = []

    # Check for slop colors (but not series-6 violet in SVG fill/stroke context)
    found_colors = set(HEX_COLOR_RE.findall(content))
    for color in found_colors:
        color_lower = color.lower()
        # Series 6 violet is approved in CCA palette for data series
        if color_lower == "#8b5cf6":
            continue
        if color_lower in {c.lower() for c in ANTI_SLOP_COLORS}:
            violations.append(Violation(
                category="anti-slop",
                severity="error",
                detail=f"AI-slop color {color} detected. Use CCA palette tokens.",
            ))

    # Check Tailwind default classes
    tw_matches = TAILWIND_SLOP_RE.findall(content)
    for match in tw_matches:
        violations.append(Violation(
            category="anti-slop",
            severity="error",
            detail=f"Tailwind default class '{match}' detected. Use explicit CCA tokens.",
        ))

    # Check rounded-full
    if ROUNDED_FULL_RE.search(content):
        violations.append(Violation(
            category="anti-slop",
            severity="warning",
            detail="'rounded-full' detected. Use 3-5px border-radius for cards.",
        ))

    return violations


def lint_all(content: str) -> dict:
    """Run all lint checks. Returns structured result."""
    all_violations = []
    all_violations.extend(lint_colors(content))
    all_violations.extend(lint_fonts(content))
    all_violations.extend(lint_spacing(content))
    all_violations.extend(lint_anti_slop(content))

    return {
        "passed": len(all_violations) == 0,
        "violation_count": len(all_violations),
        "violations": [v.to_dict() for v in all_violations],
    }


def main():
    """CLI entrypoint."""
    if len(sys.argv) < 2:
        print("Usage: design_linter.py <file.html|file.svg>")
        print("       design_linter.py --check-all <directory>")
        sys.exit(1)

    if sys.argv[1] == "--check-all":
        directory = sys.argv[2] if len(sys.argv) > 2 else "."
        total_violations = 0
        files_checked = 0
        for root, _, files in os.walk(directory):
            for fname in files:
                if fname.endswith((".html", ".svg")):
                    path = os.path.join(root, fname)
                    with open(path) as f:
                        content = f.read()
                    result = lint_all(content)
                    files_checked += 1
                    if not result["passed"]:
                        print(f"\n{path}: {result['violation_count']} violations")
                        for v in result["violations"]:
                            print(f"  [{v['severity']}] {v['category']}: {v['detail']}")
                        total_violations += result["violation_count"]
        print(f"\n{files_checked} files checked, {total_violations} total violations")
        sys.exit(1 if total_violations > 0 else 0)
    else:
        path = sys.argv[1]
        with open(path) as f:
            content = f.read()
        result = lint_all(content)
        if result["passed"]:
            print(f"{path}: PASSED (0 violations)")
        else:
            print(f"{path}: FAILED ({result['violation_count']} violations)")
            for v in result["violations"]:
                print(f"  [{v['severity']}] {v['category']}: {v['detail']}")
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
