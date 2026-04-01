"""
SessionStart Hook — Runs lightweight init checks when a Claude Code session starts.

Fires on CC session start (SessionStart event). Runs slim_init.py in check-only
mode and outputs a 3-line status: tests OK/FAIL, budget peak/off-peak, top task.

Does NOT replace /cca-init — it's a lightweight pre-check that gives Claude
immediate awareness of project state before any user input.

Wire as SessionStart hook in settings.local.json:
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/hooks/session_start_hook.py"
          }
        ]
      }
    ]
  }
}

Environment variables:
  CCA_SESSION_START_DISABLED - Set to "1" to disable
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CCA_ROOT = Path(__file__).resolve().parent.parent


def get_budget_window() -> str:
    """Determine peak/off-peak based on current time (ET)."""
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()
    if weekday >= 5:
        return "OFF-PEAK (100%)"
    elif 8 <= hour < 14:
        return "PEAK (40-50%)"
    else:
        return "OFF-PEAK (100%)"


def run_smoke_test() -> tuple[bool, str]:
    """Run the 10-suite smoke test via init_cache.py."""
    try:
        result = subprocess.run(
            ["python3", str(CCA_ROOT / "init_cache.py"), "smoke"],
            capture_output=True, text=True, timeout=30,
            cwd=str(CCA_ROOT),
        )
        output = result.stdout.strip()
        passed = result.returncode == 0
        # Extract pass count from output
        for line in output.split("\n"):
            if "PASS" in line or "pass" in line:
                return passed, line.strip()
        return passed, "10/10 PASS" if passed else "SMOKE FAILED"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, "smoke test timeout/missing"


def get_top_task() -> str:
    """Get the top task from TODAYS_TASKS.md."""
    tasks_file = CCA_ROOT / "TODAYS_TASKS.md"
    if not tasks_file.exists():
        return "No TODAYS_TASKS.md"
    try:
        content = tasks_file.read_text()
        for line in content.split("\n"):
            if "TODO]" in line:
                # Strip markdown list prefix and brackets
                task = line.strip().lstrip("-").lstrip("*").strip()
                # Remove [TODO] prefix
                task = task.replace("[TODO]", "").strip()
                return task[:80]
        return "All tasks done — check MASTER_TASKS"
    except Exception:
        return "Could not read tasks"


def main() -> None:
    if os.environ.get("CCA_SESSION_START_DISABLED") == "1":
        return

    # Read hook input from stdin (SessionStart provides sessionId, sessionLocation)
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    session_id = hook_input.get("session_id", "unknown")

    # Only run for CCA project sessions
    cwd = hook_input.get("cwd", os.getcwd())
    if "ClaudeCodeAdvancements" not in cwd:
        return

    # Gather status
    budget = get_budget_window()
    smoke_ok, smoke_msg = run_smoke_test()
    top_task = get_top_task()

    # Build status output
    status_lines = [
        f"Tests: {smoke_msg}",
        f"Budget: {budget}",
        f"Next: {top_task}",
    ]

    if not smoke_ok:
        status_lines.insert(0, "WARNING: Smoke tests failing — run /cca-init for details")

    # Output as user-visible message
    output = {
        "suppressOutput": False,
        "message": "CCA Session Pre-Check:\n" + "\n".join(status_lines),
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
