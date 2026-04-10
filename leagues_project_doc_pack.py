#!/usr/bin/env python3
"""Materialize the Leagues Claude Project doc pack from repo templates."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


TEMPLATE_MAP = {
    "01_OVERVIEW.md": "LEAGUES_CLAUDE_PROJECT_TEMPLATE_01_OVERVIEW.md",
    "02_REGIONS_RELICS_TASKS.md": "LEAGUES_CLAUDE_PROJECT_TEMPLATE_02_REGIONS_RELICS_TASKS.md",
    "03_COMMUNITY_META.md": "LEAGUES_CLAUDE_PROJECT_TEMPLATE_03_COMMUNITY_META.md",
    "04_QUERY_EXAMPLES.md": "LEAGUES_CLAUDE_PROJECT_TEMPLATE_04_QUERY_EXAMPLES.md",
    "05_PLANNER_ROUTE_NOTES.md": "LEAGUES_CLAUDE_PROJECT_TEMPLATE_05_PLANNER_ROUTE_NOTES.md",
}


@dataclass
class InitResult:
    created: list[str]
    skipped: list[str]
    output_dir: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def init_pack(output_dir: Path | str, with_planner: bool = False, overwrite: bool = False) -> InitResult:
    root = repo_root()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    skipped: list[str] = []
    docs = [
        "01_OVERVIEW.md",
        "02_REGIONS_RELICS_TASKS.md",
        "03_COMMUNITY_META.md",
        "04_QUERY_EXAMPLES.md",
    ]
    if with_planner:
        docs.append("05_PLANNER_ROUTE_NOTES.md")

    for doc_name in docs:
        template_name = TEMPLATE_MAP[doc_name]
        source = root / template_name
        target = out_dir / doc_name
        if target.exists() and not overwrite:
            skipped.append(doc_name)
            continue
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(doc_name)

    return InitResult(created=created, skipped=skipped, output_dir=str(out_dir))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create the Leagues Claude Project upload doc pack from templates.")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="Initialize a doc pack directory")
    init.add_argument("output_dir", help="Target directory for 01_*.md docs")
    init.add_argument("--with-planner", action="store_true", help="Include 05_PLANNER_ROUTE_NOTES.md")
    init.add_argument("--overwrite", action="store_true", help="Overwrite existing docs")
    init.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command != "init":
        parser.print_help()
        return 2

    result = init_pack(args.output_dir, with_planner=args.with_planner, overwrite=args.overwrite)
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(f"Initialized Leagues doc pack in {result.output_dir}")
        if result.created:
            print("Created:")
            for name in result.created:
                print(f"- {name}")
        if result.skipped:
            print("Skipped existing:")
            for name in result.skipped:
                print(f"- {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
