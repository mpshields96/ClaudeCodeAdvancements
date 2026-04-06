"""
UserPromptSubmit Hook — Cache Expiry Guard

Fires before every user prompt is processed. Reads `idle_since` from the
context health state file, calculates idle duration, and emits a one-time
warning when the Anthropic prompt cache is likely cold.

Does NOT block the prompt — warns once, then allows it through. Clears
`idle_since` after warning so the alert fires only once per idle period.

Cache TTLs (Anthropic):
  Pro plan:  300s  (5 minutes)  — default
  Max plan: 3600s  (60 minutes)

Wire in settings.local.json:
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/hooks/user_prompt_submit_cache_guard.py"
          }
        ]
      }
    ]
  }
}

Environment variables:
  CCA_CLAUDE_PLAN           - "pro" (default, 300s TTL) or "max" (3600s TTL)
  CCA_CACHE_GUARD_DISABLED  - Set to "1" to disable
  CLAUDE_CONTEXT_STATE_FILE - Override state file path
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path(os.environ.get(
    "CLAUDE_CONTEXT_STATE_FILE",
    Path.home() / ".claude-context-health.json",
))

TTL_BY_PLAN = {
    "pro": 300,    # 5 minutes
    "max": 3600,   # 60 minutes
}


def main() -> None:
    if os.environ.get("CCA_CACHE_GUARD_DISABLED") == "1":
        return

    if not STATE_FILE.exists():
        return

    try:
        state = json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return

    idle_since_raw = state.get("idle_since")
    if not idle_since_raw:
        return

    try:
        idle_since = datetime.fromisoformat(idle_since_raw)
    except ValueError:
        return

    now = datetime.now(timezone.utc)
    idle_secs = (now - idle_since).total_seconds()

    plan = os.environ.get("CCA_CLAUDE_PLAN", "pro").lower()
    ttl = TTL_BY_PLAN.get(plan, TTL_BY_PLAN["pro"])

    if idle_secs < ttl:
        return  # Cache still warm — no warning needed

    # Cache is cold — emit warning, then clear idle_since so it only fires once
    idle_min = int(idle_secs // 60)
    ttl_min = ttl // 60

    warning = (
        f"[cache-guard] Prompt cache likely cold: {idle_min}m idle "
        f"(TTL={ttl_min}m for {plan.upper()} plan). "
        f"First response may re-read context; expect higher token cost."
    )

    # Clear idle_since so this only fires once per idle period
    state.pop("idle_since", None)
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            dir=STATE_FILE.parent,
            prefix=".tmp_health_",
            suffix=".json",
            delete=False,
        )
        json.dump(state, tmp, indent=2)
        tmp.close()
        os.replace(tmp.name, STATE_FILE)
    except OSError:
        pass

    # Output hook result — user-visible message, no block
    result = {
        "suppressOutput": False,
        "message": warning,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
