#!/usr/bin/env python3
"""Validate the Leagues Claude Project upload pack.

Checks that the expected doc set exists, required headings are present,
and template placeholders are not left behind in upload-ready docs.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


DOC_SPECS = {
    "01_OVERVIEW.md": {
        "required_headings": ["# Leagues 6 Planner", "## League Snapshot", "## Current High-Confidence Consensus"],
    },
    "02_REGIONS_RELICS_TASKS.md": {
        "required_headings": ["# Regions, Relics, and Tasks", "## Regions", "## Relic Tiers"],
    },
    "03_COMMUNITY_META.md": {
        "required_headings": ["# Community Meta", "## Strongest Repeated Region Trios"],
    },
    "04_QUERY_EXAMPLES.md": {
        "required_headings": ["# Query Examples", "## Fact Queries"],
    },
    "05_PLANNER_ROUTE_NOTES.md": {
        "required_headings": ["# Planner and Route Notes", "## Current Focus Build", "## Recommended Route Notes"],
    },
}


PLACEHOLDER_SNIPPETS = [
    "[fill in",
    "[region]",
    "[regions]",
    "[points]",
    "[1-line summary]",
    "[consensus bullet]",
    "[uncertainty",
    "[value]",
    "[reason]",
    "[note]",
    "[task]",
    "[name]",
    "[short desc]",
    "[use case]",
    "[constraint]",
    "[style/goal]",
    "[summary]",
    "[weakness]",
    "[recommendation]",
    "[step or priority note]",
    "[planner output or summary]",
    "[tradeoff or warning]",
    "[open question]",
]


@dataclass
class ValidationResult:
    ok: bool
    doc_count: int
    issue_count: int
    issues: list[str]


def expected_docs(require_planner: bool) -> list[str]:
    docs = [
        "01_OVERVIEW.md",
        "02_REGIONS_RELICS_TASKS.md",
        "03_COMMUNITY_META.md",
        "04_QUERY_EXAMPLES.md",
    ]
    if require_planner:
        docs.append("05_PLANNER_ROUTE_NOTES.md")
    return docs


def _check_file(path: Path, required_headings: list[str], allow_placeholders: bool) -> list[str]:
    issues: list[str] = []
    content = path.read_text(encoding="utf-8")
    for heading in required_headings:
        if heading not in content:
            issues.append(f"{path.name}: missing required heading `{heading}`")
    if not allow_placeholders:
        lowered = content.lower()
        for snippet in PLACEHOLDER_SNIPPETS:
            if snippet.lower() in lowered:
                issues.append(f"{path.name}: unresolved placeholder token `{snippet}`")
                break
    return issues


def validate_pack(doc_root: Path | str, require_planner: bool = False, allow_placeholders: bool = False) -> ValidationResult:
    root = Path(doc_root)
    issues: list[str] = []

    docs = expected_docs(require_planner=require_planner)
    for name in docs:
        path = root / name
        if not path.exists():
            issues.append(f"missing required document `{name}`")
            continue
        issues.extend(
            _check_file(
                path,
                DOC_SPECS[name]["required_headings"],
                allow_placeholders=allow_placeholders,
            )
        )

    return ValidationResult(
        ok=not issues,
        doc_count=len(docs),
        issue_count=len(issues),
        issues=issues,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the Leagues Claude Project upload pack.")
    sub = parser.add_subparsers(dest="command")

    validate = sub.add_parser("validate", help="Validate a docs directory")
    validate.add_argument("doc_root", nargs="?", default=".", help="Directory containing 01_*.md etc.")
    validate.add_argument("--require-planner", action="store_true", help="Require 05_PLANNER_ROUTE_NOTES.md")
    validate.add_argument("--allow-placeholders", action="store_true", help="Allow template placeholders")
    validate.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command != "validate":
        parser.print_help()
        return 2

    result = validate_pack(
        args.doc_root,
        require_planner=args.require_planner,
        allow_placeholders=args.allow_placeholders,
    )
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        verdict = "PASS" if result.ok else "FAIL"
        print(f"{verdict}: checked {result.doc_count} docs, {result.issue_count} issues")
        for issue in result.issues:
            print(f"- {issue}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
