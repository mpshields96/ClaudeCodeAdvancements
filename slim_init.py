#!/usr/bin/env python3
"""
slim_init.py — Codified slim session startup for CCA.

Replaces the 10-minute full init (4 large file reads + 109 test suites + counting)
with a ~1 minute automated startup:
  1. Parse SESSION_STATE.md for orientation
  2. Run 10-suite smoke test via init_cache.py
  3. Run priority_picker.py for task recommendation
  4. Output structured init summary

CLI:
    python3 slim_init.py              # Run full slim init
    python3 slim_init.py --json       # JSON output
    python3 slim_init.py orient       # Just parse SESSION_STATE
    python3 slim_init.py smoke        # Just run smoke test
    python3 slim_init.py priority     # Just run priority picker

Stdlib only. No external dependencies.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent
SESSION_STATE_PATH = PROJECT_ROOT / "SESSION_STATE.md"

INIT_STEPS = ["smoke", "priority", "summary"]


def parse_session_state(content: str) -> dict:
    """Parse SESSION_STATE.md for quick orientation."""
    result: dict = {}

    # Session number and date
    m = re.search(r"Session\s+(\d+)\s*(?:—|-)\s*(\d{4}-\d{2}-\d{2})", content)
    if m:
        result["session_num"] = int(m.group(1))
        result["session_date"] = m.group(2)
    else:
        m = re.search(r"Session\s+(\d+)", content)
        if m:
            result["session_num"] = int(m.group(1))

    # Test counts — handle both formats:
    #   "Tests: ~109 suites, ~4373 total passing"
    #   "Tests: 2897/2897 passing"
    m = re.search(r"Tests:\s*~?(\d+)\s*suites?,\s*~?(\d+)\s*total", content)
    if m:
        result["suite_count"] = int(m.group(1))
        result["test_count"] = int(m.group(2))
    else:
        m = re.search(r"Tests:\s*(\d+)/(\d+)\s*passing", content)
        if m:
            result["test_count"] = int(m.group(1))

    # Hivemind streak
    m = re.search(r"Hivemind:\s*(\d+)(?:st|nd|rd|th)\s+consecutive\s+PASS", content)
    if m:
        result["hivemind_streak"] = int(m.group(1))

    # Next items
    next_items = []
    in_next = False
    for line in content.split("\n"):
        if "**Next" in line and "prioritized" in line.lower():
            in_next = True
            continue
        if in_next:
            stripped = line.strip()
            if stripped.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                # Strip the number prefix
                item = re.sub(r"^\d+\.\s*", "", stripped)
                next_items.append(item)
            elif stripped.startswith("---") or (stripped.startswith("**") and stripped != ""):
                break
            elif not stripped:
                if next_items:
                    break
    result["next_items"] = next_items

    return result


def run_smoke() -> dict:
    """Run the 10-suite smoke test via init_cache.py."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "init_cache.py"), "smoke"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        output = proc.stdout.strip()

        # Parse "Smoke: N/M passed"
        m = re.search(r"Smoke:\s*(\d+)/(\d+)\s*passed", output)
        if m:
            passed_count = int(m.group(1))
            total_count = int(m.group(2))
            return {
                "passed": passed_count == total_count,
                "suites_passed": passed_count,
                "suites_total": total_count,
                "output": output,
            }

        return {
            "passed": proc.returncode == 0,
            "suites_passed": 0,
            "suites_total": 0,
            "output": output,
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "suites_passed": 0,
            "suites_total": 0,
            "error": "Timeout: smoke test exceeded 60 seconds",
        }


def run_priority() -> dict:
    """Run priority_picker.py recommend."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "priority_picker.py"), "recommend"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )

        if proc.returncode != 0:
            return {"error": proc.stderr.strip() or "priority_picker failed", "raw": proc.stdout}

        output = proc.stdout.strip()

        # Extract top pick
        m = re.search(r"\*\*TOP PICK:\*\*\s*(.+?)(?:\n|$)", output)
        top_pick = m.group(1).strip() if m else output.split("\n")[0]

        return {"top_pick": top_pick, "raw": output}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout: priority_picker exceeded 30 seconds"}


def build_summary(smoke: dict, priority: dict, state: dict) -> dict:
    """Combine all init results into a summary."""
    blockers = []
    if not smoke.get("passed", False):
        blockers.append(f"Smoke test failed: {smoke.get('suites_passed', 0)}/{smoke.get('suites_total', 0)}")

    ready = len(blockers) == 0

    summary = {
        "ready": ready,
        "last_session": state.get("session_num"),
        "top_pick": priority.get("top_pick", "unknown"),
        "smoke_status": f"{smoke.get('suites_passed', 0)}/{smoke.get('suites_total', 0)} {'PASS' if smoke.get('passed') else 'FAIL'}",
        "blockers": blockers,
    }

    if "test_count" in state:
        summary["cached_test_count"] = state["test_count"]
    if "suite_count" in state:
        summary["cached_suite_count"] = state["suite_count"]
    if "hivemind_streak" in state:
        summary["hivemind_streak"] = state["hivemind_streak"]

    return summary


def format_summary(summary: dict) -> str:
    """Format summary for human-readable display."""
    lines = []
    status = "READY" if summary["ready"] else "BLOCKED"
    lines.append(f"Slim Init: {status}")
    lines.append(f"  Last session: S{summary.get('last_session', '?')}")
    lines.append(f"  Smoke: {summary.get('smoke_status', '?')}")
    lines.append(f"  Top pick: {summary.get('top_pick', '?')}")

    if summary.get("cached_test_count"):
        lines.append(f"  Tests: ~{summary['cached_test_count']} ({summary.get('cached_suite_count', '?')} suites)")
    if summary.get("hivemind_streak"):
        lines.append(f"  Hivemind: {summary['hivemind_streak']}th consecutive PASS")

    if summary.get("blockers"):
        lines.append("  BLOCKERS:")
        for b in summary["blockers"]:
            lines.append(f"    - {b}")

    return "\n".join(lines)


def run_slim_init(session_state_path: Path = SESSION_STATE_PATH) -> dict:
    """Run the full slim init sequence."""
    # Step 1: Parse SESSION_STATE
    state = {}
    if session_state_path.exists():
        content = session_state_path.read_text()
        state = parse_session_state(content)

    # Step 2: Smoke test
    smoke = run_smoke()

    # Step 3: Priority pick
    priority = run_priority()

    # Step 4: Build summary
    summary = build_summary(smoke, priority, state)
    summary["priority_raw"] = priority.get("raw", "")

    return summary


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] not in ("--json", "orient", "smoke", "priority"):
        # Full slim init
        result = run_slim_init()
        if "--json" in args:
            print(json.dumps(result, indent=2))
        else:
            print(format_summary(result))
            if result.get("priority_raw"):
                print(f"\n{result['priority_raw']}")
    elif args[0] == "--json":
        result = run_slim_init()
        print(json.dumps(result, indent=2))
    elif args[0] == "orient":
        if SESSION_STATE_PATH.exists():
            state = parse_session_state(SESSION_STATE_PATH.read_text())
            print(json.dumps(state, indent=2))
        else:
            print("SESSION_STATE.md not found")
    elif args[0] == "smoke":
        result = run_smoke()
        print(json.dumps(result, indent=2))
    elif args[0] == "priority":
        result = run_priority()
        print(json.dumps(result, indent=2))
