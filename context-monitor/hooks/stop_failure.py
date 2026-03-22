#!/usr/bin/env python3
"""
StopFailure hook handler — fires when a turn ends due to API error.

New in Claude Code v2.1.78 (2026-03-17). Fires on:
- Rate limit errors (429)
- Auth failures
- Other API errors that abort the turn

This hook logs the failure event to the context health state file
and the self-learning journal for pattern detection.

Wire as StopFailure hook in .claude/settings.local.json:
{
  "hooks": {
    "StopFailure": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "python3 .../stop_failure.py"}]
      }
    ]
  }
}

Stdlib only.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# State file for context health
STATE_FILE = Path(os.environ.get(
    "CLAUDE_CONTEXT_STATE_FILE",
    str(Path.home() / ".claude-context-health.json")
))

# Journal file for self-learning
JOURNAL_FILE = Path(os.environ.get(
    "CLAUDE_JOURNAL_FILE",
    ""
))


def read_hook_input() -> dict:
    """Read hook input from stdin."""
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return {}


def classify_error(hook_input: dict) -> dict:
    """Classify the error type from hook input.

    Returns dict with: error_type, is_rate_limit, severity, recommendation.
    """
    # StopFailure hook input may include error details
    error = hook_input.get("error", "")
    error_str = str(error).lower() if error else ""

    if "rate" in error_str or "429" in error_str or "limit" in error_str:
        return {
            "error_type": "rate_limit",
            "is_rate_limit": True,
            "severity": "HIGH",
            "recommendation": "Wait before retrying. Consider wrapping session.",
        }
    elif "auth" in error_str or "401" in error_str or "403" in error_str:
        return {
            "error_type": "auth_failure",
            "is_rate_limit": False,
            "severity": "CRITICAL",
            "recommendation": "Check authentication. May need to re-login.",
        }
    elif "500" in error_str or "502" in error_str or "503" in error_str:
        return {
            "error_type": "server_error",
            "is_rate_limit": False,
            "severity": "MEDIUM",
            "recommendation": "Transient server error. Retry should succeed.",
        }
    else:
        return {
            "error_type": "unknown",
            "is_rate_limit": False,
            "severity": "LOW",
            "recommendation": "Unknown API error. Check logs.",
        }


def update_state_file(classification: dict):
    """Update context health state with failure info."""
    state = {}
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError):
            state = {}

    # Add failure tracking
    failures = state.get("api_failures", [])
    failures.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": classification["error_type"],
        "severity": classification["severity"],
    })

    # Keep only last 20 failures
    state["api_failures"] = failures[-20:]
    state["last_failure_ts"] = datetime.now(timezone.utc).isoformat()
    state["last_failure_type"] = classification["error_type"]

    # Count recent rate limits (last hour)
    hour_ago = time.time() - 3600
    recent_rate_limits = sum(
        1 for f in state["api_failures"]
        if f["type"] == "rate_limit"
    )
    state["recent_rate_limit_count"] = recent_rate_limits

    # Atomic write
    tmp = str(STATE_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, str(STATE_FILE))


def log_to_journal(classification: dict):
    """Log failure event to self-learning journal if path configured."""
    journal_path = JOURNAL_FILE
    if not journal_path or not str(journal_path):
        return

    try:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "api_failure",
            "event": classification["error_type"],
            "severity": classification["severity"],
            "recommendation": classification["recommendation"],
        }
        with open(journal_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # Non-fatal


def main():
    """Main hook handler."""
    hook_input = read_hook_input()
    classification = classify_error(hook_input)

    update_state_file(classification)
    log_to_journal(classification)

    # Output for Claude to see
    result = {
        "result": classification["recommendation"],
    }

    # If rate limited, suggest wrapping
    if classification["is_rate_limit"]:
        result["result"] = (
            "RATE LIMITED. " + classification["recommendation"] +
            " Consider running /cca-wrap to preserve progress."
        )

    print(json.dumps(result))


if __name__ == "__main__":
    main()
