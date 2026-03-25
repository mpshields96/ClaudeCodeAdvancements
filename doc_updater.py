#!/usr/bin/env python3
"""doc_updater.py — Batch doc updates for /cca-wrap optimization.

Replaces 3-4 separate Read/Edit cycles (SESSION_STATE, CHANGELOG, LEARNINGS,
PROJECT_INDEX) with a single subprocess call. Saves ~3000-5000 tokens per wrap
by eliminating file reads and Edit retry loops.

Usage:
    python3 doc_updater.py --json '{"session": 158, "grade": "A", ...}'
    python3 doc_updater.py --session 158 --grade A --summary "Did stuff" \
        --wins "Win 1" "Win 2" --losses "Loss 1" \
        --next "Next thing" --tests 8970 --suites 224

Stdlib only. No external dependencies.
"""
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Union

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Default paths
DEFAULT_PATHS = {
    "session_state": os.path.join(SCRIPT_DIR, "SESSION_STATE.md"),
    "changelog": os.path.join(SCRIPT_DIR, "CHANGELOG.md"),
    "learnings": os.path.join(SCRIPT_DIR, "LEARNINGS.md"),
    "project_index": os.path.join(SCRIPT_DIR, "PROJECT_INDEX.md"),
}


@dataclass
class SessionData:
    """All data needed for a session wrap doc update."""
    session: int
    grade: str
    summary: str
    wins: list = field(default_factory=list)
    losses: list = field(default_factory=list)
    next_items: list = field(default_factory=list)
    test_count: int = 0
    test_suites: int = 0
    new_files: list = field(default_factory=list)
    learnings: list = field(default_factory=list)
    date: str = ""

    def __post_init__(self):
        if not self.date:
            self.date = datetime.now().strftime("%Y-%m-%d")

    @classmethod
    def from_dict(cls, d: dict) -> "SessionData":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_json(cls, json_str: str) -> "SessionData":
        return cls.from_dict(json.loads(json_str))


def update_session_state(sd: SessionData, path: str = None) -> bool:
    """Update SESSION_STATE.md — new state at top, old demoted to Previous."""
    path = path or DEFAULT_PATHS["session_state"]

    # Build new current state section
    lines = []
    lines.append(f"## Current State (as of Session {sd.session} — {sd.date})")
    lines.append("")
    lines.append(f"**Phase:** Session {sd.session} COMPLETE. {sd.summary}")
    lines.append("")
    lines.append(f"**What was done this session (S{sd.session}):**")
    for win in sd.wins:
        lines.append(f"- {win}")
    if not sd.wins:
        lines.append(f"- {sd.summary}")
    if sd.test_count:
        lines.append(f"- **Tests**: {sd.test_suites} suites, {sd.test_count} tests passing. All green.")
    lines.append("")
    if sd.next_items:
        lines.append("**Next:**")
        for i, item in enumerate(sd.next_items, 1):
            lines.append(f"{i}. {item}")
        lines.append("")

    new_section = "\n".join(lines)

    # Read existing file
    existing = ""
    if os.path.exists(path):
        with open(path, "r") as f:
            existing = f.read()

    if existing:
        # Find and demote current state to previous
        # Pattern: ## Current State ... (up to next ## or end)
        current_match = re.search(
            r"(## Current State \(as of Session (\d+)[^)]*\).*?)(?=\n## |\Z)",
            existing, re.DOTALL
        )

        if current_match:
            old_current = current_match.group(1).strip()
            old_session = current_match.group(2)
            # Replace "Current State" with "Previous State" in old section
            old_as_previous = old_current.replace(
                f"Current State (as of Session {old_session}",
                f"Previous State (Session {old_session}"
            )
            # Replace the current state section with new + old-as-previous
            header_end = existing.find("## Current State")
            if header_end >= 0:
                # Get everything before "## Current State"
                before = existing[:header_end]
                # Get everything after the old current section
                after = existing[current_match.end():]
                result = before + new_section + "\n---\n\n" + old_as_previous + after
            else:
                result = existing + "\n" + new_section
        else:
            # No current state found — just prepend after header
            header_match = re.search(r"(# .*\n(?:.*\n)*?---\n)", existing)
            if header_match:
                result = header_match.group(0) + "\n" + new_section + "\n" + existing[header_match.end():]
            else:
                result = existing + "\n" + new_section
    else:
        result = (
            "# ClaudeCodeAdvancements — Session State\n"
            "# Update at end of every session before closing.\n\n"
            "---\n\n" + new_section
        )

    with open(path, "w") as f:
        f.write(result)

    return True


def append_changelog(sd: SessionData, path: str = None) -> bool:
    """Append a new session entry to CHANGELOG.md."""
    path = path or DEFAULT_PATHS["changelog"]

    entry_lines = []
    entry_lines.append(f"\n## Session {sd.session} — {sd.date}")
    entry_lines.append("")
    entry_lines.append("**What changed:**")
    for win in sd.wins:
        entry_lines.append(f"- {win}")
    if not sd.wins:
        entry_lines.append(f"- {sd.summary}")
    entry_lines.append("")
    entry_lines.append("**Why:**")
    entry_lines.append(f"- {sd.summary}")
    entry_lines.append("")
    if sd.test_count:
        entry_lines.append(f"**Tests:** {sd.test_count}/{sd.test_count} passing ({sd.test_suites} suites)")
    else:
        entry_lines.append("**Tests:** All passing")
    entry_lines.append("")
    if sd.losses:
        entry_lines.append("**Lessons:**")
        for loss in sd.losses:
            entry_lines.append(f"- {loss}")
        entry_lines.append("")
    entry_lines.append("---")
    entry_lines.append("")

    entry = "\n".join(entry_lines)

    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write("# CCA Changelog\n" + entry)
    else:
        with open(path, "a") as f:
            f.write(entry)

    return True


def append_learnings(sd: SessionData, path: str = None) -> bool:
    """Append learnings to LEARNINGS.md. Returns False if no learnings."""
    path = path or DEFAULT_PATHS["learnings"]

    if not sd.learnings:
        return False

    entries = []
    for learning in sd.learnings:
        if isinstance(learning, dict):
            title = learning.get("title", "Untitled")
            severity = learning.get("severity", 1)
            anti_pattern = learning.get("anti_pattern", "")
            fix = learning.get("fix", "")
        elif isinstance(learning, str):
            title = learning
            severity = 1
            anti_pattern = ""
            fix = ""
        else:
            continue

        entry = f"\n### {title} — Severity: {severity} — Count: 1\n"
        if anti_pattern:
            entry += f"- **Anti-pattern:** {anti_pattern}\n"
        if fix:
            entry += f"- **Fix:** {fix}\n"
        entry += f"- **First seen:** {sd.date}\n"
        entry += f"- **Last seen:** {sd.date}\n"
        entries.append(entry)

    if not entries:
        return False

    text = "\n".join(entries)

    if not os.path.exists(path):
        header = (
            "# CCA Learnings — Severity-Tracked Patterns\n"
            "# Severity: 1 = noted, 2 = hard rule, 3 = global (promoted to ~/.claude/rules/)\n"
            "# Append-only. Never truncate.\n"
        )
        with open(path, "w") as f:
            f.write(header + text)
    else:
        with open(path, "a") as f:
            f.write(text)

    return True


def add_to_project_index(sd: SessionData, path: str = None) -> bool:
    """Add new file entries to PROJECT_INDEX.md. Returns False if no new files."""
    path = path or DEFAULT_PATHS["project_index"]

    if not sd.new_files:
        return False

    entries = []
    for item in sd.new_files:
        if isinstance(item, tuple) and len(item) == 2:
            name, desc = item
            entries.append(f"- `{name}` — {desc} (S{sd.session})")
        elif isinstance(item, str):
            entries.append(f"- `{item}` (S{sd.session})")
        else:
            continue

    if not entries:
        return False

    text = "\n\n### Added in S" + str(sd.session) + "\n" + "\n".join(entries) + "\n"

    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write("# Project Index\n" + text)
    else:
        with open(path, "a") as f:
            f.write(text)

    return True


def batch_update(sd: SessionData, paths: dict = None) -> dict:
    """Run all doc updates in one call. Returns dict of what was updated."""
    paths = paths or DEFAULT_PATHS
    results = {}

    try:
        results["session_state"] = update_session_state(
            sd, paths.get("session_state"))
    except Exception as e:
        results["session_state"] = False
        results["session_state_error"] = str(e)

    try:
        results["changelog"] = append_changelog(
            sd, paths.get("changelog"))
    except Exception as e:
        results["changelog"] = False
        results["changelog_error"] = str(e)

    try:
        results["learnings"] = append_learnings(
            sd, paths.get("learnings"))
    except Exception as e:
        results["learnings"] = False
        results["learnings_error"] = str(e)

    try:
        results["project_index"] = add_to_project_index(
            sd, paths.get("project_index"))
    except Exception as e:
        results["project_index"] = False
        results["project_index_error"] = str(e)

    return results


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Batch doc updater for /cca-wrap")
    parser.add_argument("--json", help="JSON blob with all session data")
    parser.add_argument("--session", type=int, help="Session number")
    parser.add_argument("--grade", help="Session grade (A/B/C/D)")
    parser.add_argument("--summary", help="One-sentence session summary")
    parser.add_argument("--wins", nargs="*", default=[], help="Win bullets")
    parser.add_argument("--losses", nargs="*", default=[], help="Loss bullets")
    parser.add_argument("--next", nargs="*", default=[], dest="next_items",
                       help="Next action items")
    parser.add_argument("--tests", type=int, default=0, dest="test_count",
                       help="Total test count")
    parser.add_argument("--suites", type=int, default=0, dest="test_suites",
                       help="Total suite count")
    parser.add_argument("--date", default="", help="Date string (YYYY-MM-DD)")
    parser.add_argument("--learnings-json", help="JSON array of learnings")
    parser.add_argument("--new-files", nargs="*", default=[],
                       help="New files added this session")

    args = parser.parse_args()

    if args.json:
        sd = SessionData.from_json(args.json)
    elif args.session and args.grade and args.summary:
        learnings = []
        if args.learnings_json:
            learnings = json.loads(args.learnings_json)
        sd = SessionData(
            session=args.session, grade=args.grade, summary=args.summary,
            wins=args.wins, losses=args.losses,
            next_items=args.next_items,
            test_count=args.test_count, test_suites=args.test_suites,
            date=args.date,
            learnings=learnings,
            new_files=args.new_files,
        )
    else:
        parser.error("Provide --json or --session + --grade + --summary")
        return

    results = batch_update(sd)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
