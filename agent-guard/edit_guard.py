#!/usr/bin/env python3
"""edit_guard.py — PreToolUse hook: warns on Edit of structured table files.

Batch trace analysis (S58) found PROJECT_INDEX.md Edit retries in 64% of sessions
(32/50), averaging 4.9 retries per instance. The root cause: Edit requires exact
string matching, but structured markdown tables have alignment-sensitive whitespace
that causes frequent mismatches.

This hook intercepts Edit calls on known structured-table files and returns an
advisory message suggesting Write (full rewrite) instead. It does NOT block —
it only warns, allowing Claude to proceed if the Edit is intentional.

Hook protocol:
  - stdin: JSON with tool_name + tool_input
  - stdout: JSON response (empty {} to pass, {"message": "..."} to warn)
"""

import json
import sys
from pathlib import Path

# Files with structured tables that cause frequent Edit retry storms.
# Criteria: file appeared in retry hotspots across 3+ sessions in batch analysis.
STRUCTURED_FILES = frozenset({
    "PROJECT_INDEX.md",
    "SESSION_STATE.md",
    "MASTER_TASKS.md",
    "ROADMAP.md",
})


def should_guard(file_path) -> bool:
    """Return True if file_path points to a known structured-table file."""
    if not file_path:
        return False
    return Path(file_path).name in STRUCTURED_FILES


def check_edit(tool_name: str, tool_input) -> str | None:
    """Check if an Edit call targets a structured file.

    Returns:
        None if no warning needed (pass-through).
        A warning message string if Edit targets a structured file.
    """
    if tool_name != "Edit":
        return None

    if not tool_input or not isinstance(tool_input, dict):
        return None

    file_path = tool_input.get("file_path")
    if not should_guard(file_path):
        return None

    filename = Path(file_path).name
    return (
        f"WARNING: {filename} has structured tables that cause Edit retry storms "
        f"(64% of sessions). Consider using Write (full file rewrite) instead of Edit "
        f"to avoid exact-match failures. If you must use Edit, Read the file first and "
        f"copy the exact old_string from the Read output."
    )


def main():
    """Hook entry point: read stdin, check, write stdout."""
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({}))
            return

        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({}))
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input")

    warning = check_edit(tool_name, tool_input)

    if warning:
        print(json.dumps({"message": warning}))
    else:
        print(json.dumps({}))


if __name__ == "__main__":
    main()
