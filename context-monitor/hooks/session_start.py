#!/usr/bin/env python3
"""
session_start.py — SessionStart hook: clear stale context health state.

Runs once when Claude Code opens a new session. Writes pct=0/zone=green
to ~/.claude-context-health.json so the session pacer doesn't inherit
red/critical context percentages from the previous session.

Never blocks: always exits 0.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATE_FILE = Path.home() / ".claude-context-health.json"


CLAUDE_MD_SIZE_THRESHOLD = 3072  # 3 KB — re-sent on every turn, warn if large


def _check_resume_flag() -> str | None:
    """Return advisory message if session was started with --resume, else None.

    --resume disables caching: every turn re-transmits the full context.
    Detected via CLAUDE_CODE_RESUME env var (set by Claude Code when --resume is used).
    """
    if os.environ.get("CLAUDE_CODE_RESUME"):
        return (
            "Note: session started with --resume. "
            "Caching is disabled — every turn re-transmits full context."
        )
    return None


def _check_claude_md_size(cwd: str) -> str | None:
    """Return advisory message if any CLAUDE.md file exceeds the size threshold, else None.

    Checks both the global ~/.claude/CLAUDE.md and the project-level CLAUDE.md.
    Large CLAUDE.md files re-send on every interaction, increasing token cost.
    """
    candidates = [
        Path.home() / ".claude" / "CLAUDE.md",
        Path(cwd) / "CLAUDE.md",
    ]
    for path in candidates:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > CLAUDE_MD_SIZE_THRESHOLD:
            size_kb = size / 1024
            return (
                f"Advisory: {path.name} ({path.parent}) is {size_kb:.0f}KB. "
                f"It re-sends on every interaction. "
                f"Consider progressive disclosure (file references, not @includes)."
            )
    return None


def main() -> None:
    state_path_str = os.environ.get("CLAUDE_CONTEXT_STATE_FILE", "")
    state_path = Path(state_path_str) if state_path_str else DEFAULT_STATE_FILE

    # Read cwd from hook input if available (SessionStart provides it)
    try:
        hook_input = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except (json.JSONDecodeError, OSError):
        hook_input = {}
    cwd = hook_input.get("cwd", os.getcwd())

    fresh = {
        "pct": 0.0,
        "zone": "green",
        "tokens": 0,
        "turns": 0,
        "window": int(os.environ.get("CLAUDE_CONTEXT_WINDOW", "200000")),
        "session_id": "session_start",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(fresh, indent=2))
        tmp.replace(state_path)
    except OSError:
        pass  # Non-fatal — staleness check in session_pacer is the backstop

    # Signal 2: --resume detection
    resume_msg = _check_resume_flag()
    # Signal 3: CLAUDE.md size warning
    size_msg = _check_claude_md_size(cwd)

    advisories = [m for m in (resume_msg, size_msg) if m]
    if advisories:
        output = {
            "suppressOutput": False,
            "message": "\n".join(advisories),
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
