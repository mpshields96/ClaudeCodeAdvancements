#!/usr/bin/env python3
"""Create and materialize the Leagues Claude Project doc pack."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from datetime import datetime, timezone


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


@dataclass
class MaterializeResult:
    created: list[str]
    manifest_path: str
    output_dir: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def _doc_names(with_planner: bool) -> list[str]:
    docs = [
        "01_OVERVIEW.md",
        "02_REGIONS_RELICS_TASKS.md",
        "03_COMMUNITY_META.md",
        "04_QUERY_EXAMPLES.md",
    ]
    if with_planner:
        docs.append("05_PLANNER_ROUTE_NOTES.md")
    return docs


def init_pack(output_dir: Path | str, with_planner: bool = False, overwrite: bool = False) -> InitResult:
    root = repo_root()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    skipped: list[str] = []
    docs = _doc_names(with_planner)

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


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    header = "| " + " | ".join(headers) + " |"
    separator = "|" + "|".join("-" * (len(h) + 2) for h in headers) + "|"
    lines = [header, separator]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _render_overview(data: dict) -> str:
    snapshot = data.get("snapshot", {})
    region_rows = [
        [
            str(row.get("region", "")),
            str(row.get("points", "")),
            str(row.get("notes", "")),
        ]
        for row in data.get("region_point_snapshot", [])
    ]
    parts = [
        "# Leagues 6 Planner",
        "",
        "Use this file as the front door for the Claude Project.",
        "",
        "## What This Project Contains",
        "",
        "This project packages Leagues 6 planning knowledge from two source types:",
        "- verified reference data",
        "- distilled community consensus",
        "",
        "## Ground Rules",
        "",
        "- Treat wiki/reference facts as higher confidence than Discord opinions.",
        "- When community opinions conflict, say so explicitly.",
        "- Prefer Leagues-specific answers over generic OSRS advice.",
        "",
        "## League Snapshot",
        "",
        f"- League dates: {snapshot.get('league_dates', '')}",
        f"- Key reveal dates: {snapshot.get('key_reveal_dates', '')}",
        f"- Always-unlocked context: {snapshot.get('always_unlocked_context', '')}",
        f"- Current planner/runtime note: {snapshot.get('current_planner_runtime_note', '')}",
        "",
    ]
    if region_rows:
        parts.extend(["## Region Point Snapshot", ""])
        parts.extend(_table(["Region", "Points", "Notes"], region_rows))
        parts.append("")
    parts.extend(["## Current High-Confidence Consensus", ""])
    parts.extend(_bullet_lines(data.get("current_high_confidence_consensus", [])))
    parts.extend(["", "## Known Uncertainties", ""])
    parts.extend(_bullet_lines(data.get("known_uncertainties", [])))
    parts.extend([
        "",
        "## How To Use The Other Uploaded Docs",
        "",
        "- `02_REGIONS_RELICS_TASKS.md` for structured planning facts",
        "- `03_COMMUNITY_META.md` for Discord/community consensus",
        "- `04_QUERY_EXAMPLES.md` for high-value mobile prompt patterns",
    ])
    if data.get("includes_planner_doc"):
        parts.append("- `05_PLANNER_ROUTE_NOTES.md` for planner/advisor outputs and route-specific guidance")
    return "\n".join(parts).rstrip() + "\n"


def _render_regions_relics_tasks(data: dict) -> str:
    parts = [
        "# Regions, Relics, and Tasks",
        "",
        "This file is the structured Leagues reference layer.",
        "",
        "## Regions",
        "",
    ]
    for region in data.get("regions", []):
        parts.extend([
            f"### {region.get('name', '')}",
            "",
            f"- Points: {region.get('points', '')}",
            f"- Identity: {region.get('identity', '')}",
            "- Main reasons to unlock:",
        ])
        parts.extend([f"  - {item}" for item in region.get("reasons", [])])
        parts.append("- Important echo/item/reward notes:")
        parts.extend([f"  - {item}" for item in region.get("notes", [])])
        parts.append("- Best fit for:")
        parts.extend([f"  - {item}" for item in region.get("best_fit", [])])
        parts.append("")
    parts.extend(["## Relic Tiers", ""])
    for tier in data.get("relic_tiers", []):
        rows = [
            [
                str(relic.get("name", "")),
                str(relic.get("description", "")),
                str(relic.get("best_use_case", "")),
                str(relic.get("notes", "")),
            ]
            for relic in tier.get("relics", [])
        ]
        parts.extend([f"### Tier {tier.get('tier', '')}", ""])
        parts.extend(_table(["Relic", "Short Description", "Best Use Case", "Notes"], rows))
        parts.append("")
    parts.extend(["## High-Value Tasks By Theme", ""])
    for theme in ["Magic", "Melee", "Ranged", "Early / Easy Points", "Dad / Lazy Route"]:
        rows = [
            [
                str(task.get("task", "")),
                str(task.get("region", "")),
                str(task.get("points", "")),
                str(task.get("note", "")),
            ]
            for task in data.get("task_themes", {}).get(theme, [])
        ]
        parts.extend([f"### {theme}", ""])
        parts.extend(_table(["Task", "Region", "Points", "Why It Matters"], rows))
        parts.append("")
    parts.extend(["## Important Build Constraints", ""])
    parts.extend(_bullet_lines(data.get("important_build_constraints", [])))
    parts.extend(["", "## Notes On Fact Quality", "", "- Facts in this file should come from wiki/reference data first.", "- If a line is based on inference, label it clearly."])
    return "\n".join(parts).rstrip() + "\n"


def _render_community_meta(data: dict) -> str:
    trio_rows = [
        [
            str(item.get("trio", "")),
            str(item.get("goal", "")),
            str(item.get("confidence", "")),
            str(item.get("summary", "")),
        ]
        for item in data.get("trios", [])
    ]
    parts = [
        "# Community Meta",
        "",
        "This file captures distilled Discord/community consensus.",
        "",
        "Use it for:",
        "- what strong players are repeatedly recommending",
        "- what archetypes keep showing up",
        "- where the community is split",
        "",
        "Do not treat this file as a source of hard facts unless the claim is also verified elsewhere.",
        "",
        "## Strongest Repeated Region Trios",
        "",
    ]
    parts.extend(_table(["Trio", "Combat Style / Goal", "Confidence", "Why People Like It"], trio_rows))
    parts.extend(["", "## Repeated Archetypes", ""])
    for archetype in data.get("archetypes", []):
        parts.extend([
            f"### {archetype.get('name', '')}",
            "",
            f"- Style: {archetype.get('style', '')}",
            f"- Core regions: {archetype.get('core_regions', '')}",
            f"- Core relics or pact choices: {archetype.get('core_choices', '')}",
            "- Why it repeats:",
        ])
        parts.extend([f"  - {item}" for item in archetype.get("reasons", [])])
        parts.append("- Weaknesses:")
        parts.extend([f"  - {item}" for item in archetype.get("weaknesses", [])])
        parts.append("")
    parts.extend(["## Community Agreements", ""])
    parts.extend(_bullet_lines(data.get("agreements", [])))
    parts.extend(["", "## Community Splits", ""])
    for split in data.get("splits", []):
        parts.append(f"- {split.get('question', '')}")
        parts.append(f"  - Side A: {split.get('side_a', '')}")
        parts.append(f"  - Side B: {split.get('side_b', '')}")
    parts.extend(["", "## Lazy / Dad / AFK Recommendations", ""])
    parts.extend(_bullet_lines(data.get("lazy_recommendations", [])))
    parts.extend([
        "",
        "## Confidence Legend",
        "",
        "- `High`: repeated across multiple threads or heavily reinforced",
        "- `Medium`: present in multiple places but with meaningful disagreement",
        "- `Low`: interesting but not yet stable",
    ])
    return "\n".join(parts).rstrip() + "\n"


def _render_query_examples(data: dict) -> str:
    parts = ["# Query Examples", "", "Use these prompts directly in the Claude Project.", ""]
    sections = [
        ("## Fact Queries", data.get("fact_queries", [])),
        ("## Build Queries", data.get("build_queries", [])),
        ("## Route Queries", data.get("route_queries", [])),
        ("## Validation Queries", data.get("validation_queries", [])),
        ("## Planner Support Queries", data.get("planner_support_queries", [])),
    ]
    for heading, items in sections:
        parts.extend([heading, ""])
        parts.extend(_bullet_lines(items))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _render_planner_route_notes(data: dict) -> str:
    focus = data.get("current_focus_build", {})
    parts = [
        "# Planner and Route Notes",
        "",
        "Use this file when the Claude Project pack needs a dedicated planning layer beyond the core reference docs.",
        "",
        "## What This File Is For",
        "",
        "- planner/advisor outputs worth preserving for mobile use",
        "- route notes for a specific build direction",
        "- major tradeoffs between competing region paths",
        "- warnings that materially change route quality",
        "",
        "## Current Focus Build",
        "",
        f"- Build label: {focus.get('build_label', '')}",
        f"- Target style: {focus.get('target_style', '')}",
        f"- Core regions: {focus.get('core_regions', '')}",
        f"- Core relic direction: {focus.get('core_relic_direction', '')}",
        f"- Main goal: {focus.get('main_goal', '')}",
        "",
        "## Recommended Route Notes",
        "",
    ]
    parts.extend(_bullet_lines(data.get("recommended_route_notes", [])))
    parts.extend(["", "## Planner Outputs Worth Keeping", ""])
    parts.extend(_bullet_lines(data.get("planner_outputs", [])))
    parts.extend(["", "## Tradeoffs and Warnings", ""])
    parts.extend(_bullet_lines(data.get("tradeoffs_and_warnings", [])))
    parts.extend(["", "## Open Questions", ""])
    parts.extend(_bullet_lines(data.get("open_questions", [])))
    parts.extend([
        "",
        "## Confidence Notes",
        "",
        "- Mark anything derived from community opinion or local planner heuristics as opinionated.",
        "- Keep verified facts in the structured reference docs where possible.",
    ])
    return "\n".join(parts).rstrip() + "\n"


def _write_manifest(output_dir: Path, context_path: str | None, with_planner: bool, docs: list[str], context: dict) -> str:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "with_planner": with_planner,
        "doc_count": len(docs),
        "docs": docs,
        "context_path": context_path,
        "context_keys": sorted(context.keys()),
        "source_paths": context.get("source_paths", []),
    }
    manifest_path = output_dir / "leagues_project_pack.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return str(manifest_path)


def materialize_pack(
    output_dir: Path | str,
    context: dict,
    context_path: str | None = None,
    with_planner: bool = False,
) -> MaterializeResult:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    docs = _doc_names(with_planner)

    rendered = {
        "01_OVERVIEW.md": _render_overview({
            **context.get("overview", {}),
            "includes_planner_doc": with_planner,
        }),
        "02_REGIONS_RELICS_TASKS.md": _render_regions_relics_tasks(context.get("regions_relics_tasks", {})),
        "03_COMMUNITY_META.md": _render_community_meta(context.get("community_meta", {})),
        "04_QUERY_EXAMPLES.md": _render_query_examples(context.get("query_examples", {})),
    }
    if with_planner:
        rendered["05_PLANNER_ROUTE_NOTES.md"] = _render_planner_route_notes(context.get("planner_route_notes", {}))

    created: list[str] = []
    for name in docs:
        (out_dir / name).write_text(rendered[name], encoding="utf-8")
        created.append(name)
    manifest_path = _write_manifest(out_dir, context_path, with_planner, docs, context)
    return MaterializeResult(created=created, manifest_path=manifest_path, output_dir=str(out_dir))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create the Leagues Claude Project upload doc pack from templates.")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="Initialize a doc pack directory")
    init.add_argument("output_dir", help="Target directory for 01_*.md docs")
    init.add_argument("--with-planner", action="store_true", help="Include 05_PLANNER_ROUTE_NOTES.md")
    init.add_argument("--overwrite", action="store_true", help="Overwrite existing docs")
    init.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    materialize = sub.add_parser("materialize", help="Render a doc pack from structured context JSON")
    materialize.add_argument("output_dir", help="Target directory for rendered docs")
    materialize.add_argument("context_json", help="Structured context JSON path")
    materialize.add_argument("--with-planner", action="store_true", help="Render 05_PLANNER_ROUTE_NOTES.md")
    materialize.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        result = init_pack(args.output_dir, with_planner=args.with_planner, overwrite=args.overwrite)
    elif args.command == "materialize":
        context_path = Path(args.context_json)
        context = json.loads(context_path.read_text(encoding="utf-8"))
        result = materialize_pack(
            args.output_dir,
            context=context,
            context_path=str(context_path),
            with_planner=args.with_planner,
        )
    else:
        parser.print_help()
        return 2
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        action = "Rendered" if args.command == "materialize" else "Initialized"
        print(f"{action} Leagues doc pack in {result.output_dir}")
        if getattr(result, "created", None):
            print("Created:")
            for name in result.created:
                print(f"- {name}")
        if hasattr(result, "skipped") and result.skipped:
            print("Skipped existing:")
            for name in result.skipped:
                print(f"- {name}")
        if hasattr(result, "manifest_path"):
            print(f"Manifest: {result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
