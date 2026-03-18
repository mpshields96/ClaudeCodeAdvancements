#!/usr/bin/env python3
"""
skillbook_inject.py — UserPromptSubmit hook that injects top Skillbook strategies.

Reads SKILLBOOK.md, extracts strategies with confidence >= threshold,
and injects them as additionalContext so Claude starts every session
with the distilled wisdom from previous sessions.

Hook type: UserPromptSubmit (fires on each user message)
Delivery: additionalContext (appended to user message context)

Only injects once per session (tracks injection state in env var).
Only injects strategies with confidence >= 50 (configurable).

Stdlib only. No external dependencies.
"""

import json
import os
import re
import sys
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────

_SKILLBOOK_PATH = Path(__file__).parent.parent / "SKILLBOOK.md"
_MIN_CONFIDENCE = int(os.environ.get("SKILLBOOK_MIN_CONFIDENCE", "50"))
_MAX_STRATEGIES = int(os.environ.get("SKILLBOOK_MAX_STRATEGIES", "8"))
_ENV_INJECTED = "CCA_SKILLBOOK_INJECTED"

# ── Strategy Extraction ─────────────────────────────────────────────────────


def extract_strategies(content: str, min_confidence: int = 50,
                       max_count: int = 8) -> list:
    """
    Extract strategy directives from SKILLBOOK.md content.

    Returns list of dicts: {name, directive, confidence}
    Sorted by confidence descending.
    """
    strategies = []

    # Match pattern: ### S1: Name — Confidence: 90
    # Followed by **Directive:** "..."
    pattern = re.compile(
        r'###\s+(S\d+):\s+(.+?)\s*—\s*Confidence:\s*(\d+)\s*\n'
        r'\*\*Directive:\*\*\s*"([^"]+)"',
        re.MULTILINE,
    )

    for match in pattern.finditer(content):
        sid = match.group(1)
        name = match.group(2).strip()
        confidence = int(match.group(3))
        directive = match.group(4).strip()

        if confidence >= min_confidence:
            strategies.append({
                "id": sid,
                "name": name,
                "confidence": confidence,
                "directive": directive,
            })

    # Sort by confidence descending, take top N
    strategies.sort(key=lambda s: s["confidence"], reverse=True)
    return strategies[:max_count]


def format_injection(strategies: list) -> str:
    """Format strategies for context injection."""
    if not strategies:
        return ""

    lines = ["[CCA Skillbook — Top strategies from previous sessions]"]
    for s in strategies:
        lines.append(f"- [{s['id']} c={s['confidence']}] {s['directive']}")
    lines.append("[End Skillbook]")
    return "\n".join(lines)


def read_skillbook() -> str:
    """Read SKILLBOOK.md content. Returns empty string if not found."""
    try:
        return _SKILLBOOK_PATH.read_text()
    except (OSError, FileNotFoundError):
        return ""


# ── Hook Entry Point ────────────────────────────────────────────────────────


def main():
    """
    UserPromptSubmit hook entry point.

    Reads JSON from stdin, optionally adds additionalContext with
    top Skillbook strategies, writes JSON response to stdout.
    """
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, IOError):
        hook_input = {}

    # Check if we're in the CCA project
    cwd = hook_input.get("cwd", "")
    if "ClaudeCodeAdvancements" not in cwd:
        # Not a CCA session — no injection
        print(json.dumps({}))
        return

    # Only inject once per session (check env flag)
    if os.environ.get(_ENV_INJECTED) == "1":
        print(json.dumps({}))
        return

    # Read and extract strategies
    content = read_skillbook()
    if not content:
        print(json.dumps({}))
        return

    strategies = extract_strategies(content, _MIN_CONFIDENCE, _MAX_STRATEGIES)
    if not strategies:
        print(json.dumps({}))
        return

    injection = format_injection(strategies)

    # Mark as injected (for this process tree)
    os.environ[_ENV_INJECTED] = "1"

    # Return additionalContext
    response = {
        "additionalContext": injection,
    }
    print(json.dumps(response))


if __name__ == "__main__":
    main()
