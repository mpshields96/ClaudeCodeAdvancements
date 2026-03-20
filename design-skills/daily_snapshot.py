#!/usr/bin/env python3
"""
daily_snapshot.py — Daily state snapshots for CCA progress tracking.

Captures a point-in-time snapshot of project metrics and stores it as JSON.
Supports diffing any two snapshots to show what changed.

Storage: .cca-daily-snapshots/YYYY-MM-DD.json (gitignored, local only)

Usage:
    python3 design-skills/daily_snapshot.py capture              # Capture today's snapshot
    python3 design-skills/daily_snapshot.py diff                  # Today vs yesterday
    python3 design-skills/daily_snapshot.py diff 2026-03-19       # Today vs specific date
    python3 design-skills/daily_snapshot.py diff 2026-03-18 2026-03-19  # Two specific dates
    python3 design-skills/daily_snapshot.py history               # List all snapshots

Stdlib only. No external dependencies.
"""

import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SNAPSHOT_DIR = os.path.join(PROJECT_ROOT, ".cca-daily-snapshots")


def _read_file(relative_path: str) -> str:
    path = os.path.join(PROJECT_ROOT, relative_path)
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return ""


def _count_test_methods(filepath: str) -> int:
    """Count test methods in a Python test file."""
    count = 0
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                if line.strip().startswith("def test_"):
                    count += 1
    return count


def _count_python_loc(dirpath: str) -> int:
    """Count lines of Python code (excluding tests) in a directory."""
    total = 0
    if not os.path.isdir(dirpath):
        return 0
    for root, _, files in os.walk(dirpath):
        for fn in files:
            if fn.endswith(".py") and not fn.startswith("test_"):
                fp = os.path.join(root, fn)
                with open(fp) as f:
                    total += sum(1 for _ in f)
    return total


def capture_snapshot(snapshot_date: str = None) -> dict:
    """Capture a point-in-time snapshot of CCA project metrics.

    Returns a dict with all measurable project state.
    """
    if snapshot_date is None:
        snapshot_date = date.today().isoformat()

    snapshot = {
        "date": snapshot_date,
        "captured_at": datetime.now().isoformat(),
        "tests": {},
        "modules": {},
        "git": {},
        "totals": {},
    }

    # ── Test counts per suite ──
    total_tests = 0
    total_suites = 0
    test_files = []
    for root, _, files in os.walk(PROJECT_ROOT):
        # Skip hidden dirs and __pycache__
        if any(part.startswith(".") or part == "__pycache__" for part in root.split(os.sep)):
            continue
        for fn in sorted(files):
            if fn.startswith("test_") and fn.endswith(".py"):
                fp = os.path.join(root, fn)
                count = _count_test_methods(fp)
                rel_path = os.path.relpath(fp, PROJECT_ROOT)
                test_files.append({"file": rel_path, "count": count})
                total_tests += count
                total_suites += 1

    snapshot["tests"]["suites"] = test_files
    snapshot["tests"]["total_tests"] = total_tests
    snapshot["tests"]["total_suites"] = total_suites

    # ── Module metrics ──
    modules = [
        ("memory-system", "Memory System"),
        ("spec-system", "Spec System"),
        ("context-monitor", "Context Monitor"),
        ("agent-guard", "Agent Guard"),
        ("usage-dashboard", "Usage Dashboard"),
        ("reddit-intelligence", "Reddit Intelligence"),
        ("self-learning", "Self-Learning"),
        ("design-skills", "Design Skills"),
        ("research", "Research"),
    ]

    total_loc = 0
    total_py_files = 0
    for mod_path, mod_name in modules:
        full_path = os.path.join(PROJECT_ROOT, mod_path)
        if not os.path.isdir(full_path):
            continue

        loc = _count_python_loc(full_path)
        py_files = 0
        for root, _, files in os.walk(full_path):
            py_files += sum(1 for f in files if f.endswith(".py") and not f.startswith("test_"))

        # Count module-specific tests
        mod_tests = 0
        for tf in test_files:
            if tf["file"].startswith(mod_path):
                mod_tests += tf["count"]

        snapshot["modules"][mod_name] = {
            "path": mod_path,
            "loc": loc,
            "py_files": py_files,
            "tests": mod_tests,
        }
        total_loc += loc
        total_py_files += py_files

    # Root-level files
    root_loc = 0
    root_files = 0
    for fn in os.listdir(PROJECT_ROOT):
        fp = os.path.join(PROJECT_ROOT, fn)
        if fn.endswith(".py") and not fn.startswith("test_") and os.path.isfile(fp):
            with open(fp) as f:
                root_loc += sum(1 for _ in f)
            root_files += 1
    if root_loc > 0:
        snapshot["modules"]["Root"] = {"path": "./", "loc": root_loc, "py_files": root_files, "tests": 0}
        total_loc += root_loc
        total_py_files += root_files

    # Root-level tests
    for tf in test_files:
        if tf["file"].startswith("tests/"):
            snapshot["modules"].setdefault("Root", {"path": "./", "loc": 0, "py_files": 0, "tests": 0})
            snapshot["modules"]["Root"]["tests"] += tf["count"]

    snapshot["totals"]["loc"] = total_loc
    snapshot["totals"]["py_files"] = total_py_files
    snapshot["totals"]["tests"] = total_tests
    snapshot["totals"]["suites"] = total_suites

    # ── Git stats ──
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--since=midnight", "--format=%H"],
            capture_output=True, text=True, timeout=5, cwd=PROJECT_ROOT,
        )
        snapshot["git"]["commits_today"] = len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0
    except (subprocess.TimeoutExpired, OSError):
        snapshot["git"]["commits_today"] = 0

    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H %s"],
            capture_output=True, text=True, timeout=5, cwd=PROJECT_ROOT,
        )
        if result.stdout.strip():
            parts = result.stdout.strip().split(" ", 1)
            snapshot["git"]["last_commit_hash"] = parts[0][:8]
            snapshot["git"]["last_commit_msg"] = parts[1] if len(parts) > 1 else ""
    except (subprocess.TimeoutExpired, OSError):
        pass

    # ── Session number from SESSION_STATE ──
    state = _read_file("SESSION_STATE.md")
    session_match = re.search(r"Session (\d+)", state)
    if session_match:
        snapshot["totals"]["session_number"] = int(session_match.group(1))

    return snapshot


def save_snapshot(snapshot: dict, snapshot_dir: str = SNAPSHOT_DIR) -> str:
    """Save a snapshot to disk. Returns the file path."""
    os.makedirs(snapshot_dir, exist_ok=True)
    filename = f"{snapshot['date']}.json"
    filepath = os.path.join(snapshot_dir, filename)
    with open(filepath, "w") as f:
        json.dump(snapshot, f, indent=2)
    return filepath


def load_snapshot(snapshot_date: str, snapshot_dir: str = SNAPSHOT_DIR) -> dict | None:
    """Load a snapshot by date string (YYYY-MM-DD)."""
    filepath = os.path.join(snapshot_dir, f"{snapshot_date}.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath) as f:
        return json.load(f)


def list_snapshots(snapshot_dir: str = SNAPSHOT_DIR) -> list[str]:
    """List all snapshot dates, sorted newest first."""
    if not os.path.isdir(snapshot_dir):
        return []
    dates = []
    for fn in os.listdir(snapshot_dir):
        if fn.endswith(".json"):
            dates.append(fn.replace(".json", ""))
    return sorted(dates, reverse=True)


def find_previous_snapshot(before_date: str, snapshot_dir: str = SNAPSHOT_DIR) -> str | None:
    """Find the most recent snapshot before a given date."""
    snapshots = list_snapshots(snapshot_dir)
    for d in snapshots:
        if d < before_date:
            return d
    return None


def diff_snapshots(old: dict, new: dict) -> dict:
    """Compare two snapshots and produce a structured diff.

    Returns a dict with:
        - date_range: {from, to}
        - totals_delta: {tests, suites, loc, py_files, session_number}
        - module_deltas: [{name, tests_delta, loc_delta, ...}]
        - new_suites: test files that exist in new but not old
        - removed_suites: test files that exist in old but not new
        - git_summary: commits between snapshots
    """
    diff = {
        "date_range": {"from": old.get("date", "?"), "to": new.get("date", "?")},
        "totals_delta": {},
        "module_deltas": [],
        "new_suites": [],
        "removed_suites": [],
    }

    # ── Totals delta ──
    for key in ["tests", "suites", "loc", "py_files", "session_number"]:
        old_val = old.get("totals", {}).get(key, 0)
        new_val = new.get("totals", {}).get(key, 0)
        delta = new_val - old_val
        diff["totals_delta"][key] = {
            "old": old_val,
            "new": new_val,
            "delta": delta,
        }

    # ── Module deltas ──
    all_modules = set(list(old.get("modules", {}).keys()) + list(new.get("modules", {}).keys()))
    for mod_name in sorted(all_modules):
        old_mod = old.get("modules", {}).get(mod_name, {})
        new_mod = new.get("modules", {}).get(mod_name, {})

        tests_delta = new_mod.get("tests", 0) - old_mod.get("tests", 0)
        loc_delta = new_mod.get("loc", 0) - old_mod.get("loc", 0)
        files_delta = new_mod.get("py_files", 0) - old_mod.get("py_files", 0)

        if tests_delta != 0 or loc_delta != 0 or files_delta != 0:
            diff["module_deltas"].append({
                "name": mod_name,
                "tests_delta": tests_delta,
                "loc_delta": loc_delta,
                "files_delta": files_delta,
                "tests_new": new_mod.get("tests", 0),
                "loc_new": new_mod.get("loc", 0),
            })

    # ── New/removed test suites ──
    old_suites = {s["file"] for s in old.get("tests", {}).get("suites", [])}
    new_suites = {s["file"] for s in new.get("tests", {}).get("suites", [])}

    for s in sorted(new_suites - old_suites):
        suite_info = next((x for x in new["tests"]["suites"] if x["file"] == s), {})
        diff["new_suites"].append({"file": s, "count": suite_info.get("count", 0)})

    for s in sorted(old_suites - new_suites):
        diff["removed_suites"].append({"file": s})

    return diff


def format_diff_text(diff: dict) -> str:
    """Format a diff as human-readable text for reports."""
    lines = []
    dr = diff["date_range"]
    lines.append(f"Changes: {dr['from']} -> {dr['to']}")
    lines.append("")

    # Totals
    td = diff["totals_delta"]
    changes = []
    for key, label in [("tests", "tests"), ("suites", "suites"), ("loc", "LOC"),
                       ("py_files", "files"), ("session_number", "sessions")]:
        d = td.get(key, {})
        delta = d.get("delta", 0)
        if delta != 0:
            sign = "+" if delta > 0 else ""
            changes.append(f"{label}: {d['old']} -> {d['new']} ({sign}{delta})")
    if changes:
        lines.append("TOTALS:")
        for c in changes:
            lines.append(f"  {c}")
    else:
        lines.append("TOTALS: No changes")
    lines.append("")

    # Module deltas
    if diff["module_deltas"]:
        lines.append("MODULE CHANGES:")
        for md in diff["module_deltas"]:
            parts = []
            if md["tests_delta"] != 0:
                sign = "+" if md["tests_delta"] > 0 else ""
                parts.append(f"tests {sign}{md['tests_delta']}")
            if md["loc_delta"] != 0:
                sign = "+" if md["loc_delta"] > 0 else ""
                parts.append(f"LOC {sign}{md['loc_delta']}")
            if md["files_delta"] != 0:
                sign = "+" if md["files_delta"] > 0 else ""
                parts.append(f"files {sign}{md['files_delta']}")
            lines.append(f"  {md['name']}: {', '.join(parts)}")
    lines.append("")

    # New suites
    if diff["new_suites"]:
        lines.append("NEW TEST SUITES:")
        for s in diff["new_suites"]:
            lines.append(f"  + {s['file']} ({s['count']} tests)")

    if diff["removed_suites"]:
        lines.append("REMOVED TEST SUITES:")
        for s in diff["removed_suites"]:
            lines.append(f"  - {s['file']}")

    return "\n".join(lines)


def format_diff_markdown(diff: dict) -> str:
    """Format a diff as markdown for inclusion in reports."""
    lines = []
    dr = diff["date_range"]
    lines.append(f"### Changes: {dr['from']} -> {dr['to']}")
    lines.append("")

    td = diff["totals_delta"]
    lines.append("| Metric | Previous | Current | Delta |")
    lines.append("|--------|----------|---------|-------|")
    for key, label in [("tests", "Tests"), ("suites", "Suites"), ("loc", "Lines of Code"),
                       ("py_files", "Python Files"), ("session_number", "Session")]:
        d = td.get(key, {})
        delta = d.get("delta", 0)
        if delta != 0:
            sign = "+" if delta > 0 else ""
            lines.append(f"| {label} | {d['old']} | {d['new']} | {sign}{delta} |")

    if diff["module_deltas"]:
        lines.append("")
        lines.append("**Module Changes:**")
        for md in diff["module_deltas"]:
            parts = []
            if md["tests_delta"] != 0:
                sign = "+" if md["tests_delta"] > 0 else ""
                parts.append(f"{sign}{md['tests_delta']} tests")
            if md["loc_delta"] != 0:
                sign = "+" if md["loc_delta"] > 0 else ""
                parts.append(f"{sign}{md['loc_delta']} LOC")
            lines.append(f"- **{md['name']}**: {', '.join(parts)}")

    if diff["new_suites"]:
        lines.append("")
        lines.append("**New Test Suites:**")
        for s in diff["new_suites"]:
            lines.append(f"- `{s['file']}` ({s['count']} tests)")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: daily_snapshot.py {capture|diff|history}")
        print("")
        print("Commands:")
        print("  capture              Capture today's snapshot")
        print("  diff [date1] [date2] Compare snapshots (default: today vs previous)")
        print("  history              List all snapshots")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "capture":
        snapshot = capture_snapshot()
        filepath = save_snapshot(snapshot)
        print(f"Snapshot captured: {filepath}")
        print(f"  Tests: {snapshot['totals']['tests']} ({snapshot['totals']['suites']} suites)")
        print(f"  LOC: {snapshot['totals']['loc']}")
        print(f"  Files: {snapshot['totals']['py_files']}")

    elif cmd == "diff":
        if len(sys.argv) >= 4:
            date1 = sys.argv[2]
            date2 = sys.argv[3]
        elif len(sys.argv) >= 3:
            date2 = date.today().isoformat()
            date1 = sys.argv[2]
        else:
            date2 = date.today().isoformat()
            date1 = find_previous_snapshot(date2)
            if date1 is None:
                print("No previous snapshot found. Run 'capture' first.")
                sys.exit(1)

        old = load_snapshot(date1)
        new = load_snapshot(date2)

        # If today's snapshot doesn't exist, capture it now
        if new is None and date2 == date.today().isoformat():
            new = capture_snapshot()
            save_snapshot(new)

        if old is None:
            print(f"No snapshot for {date1}")
            sys.exit(1)
        if new is None:
            print(f"No snapshot for {date2}")
            sys.exit(1)

        result = diff_snapshots(old, new)
        print(format_diff_text(result))

    elif cmd == "history":
        snapshots = list_snapshots()
        if not snapshots:
            print("No snapshots found. Run 'capture' to create one.")
        else:
            print(f"Snapshots ({len(snapshots)}):")
            for d in snapshots:
                snap = load_snapshot(d)
                if snap:
                    t = snap.get("totals", {})
                    print(f"  {d}: {t.get('tests', '?')} tests, {t.get('loc', '?')} LOC, "
                          f"session {t.get('session_number', '?')}")
                else:
                    print(f"  {d}: (corrupt)")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
