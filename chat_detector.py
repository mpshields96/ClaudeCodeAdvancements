#!/usr/bin/env python3
"""
chat_detector.py — Detect and manage running Claude Code chat sessions.

Finds running Claude Code processes for the CCA project, identifies duplicates,
and provides pre-launch safety checks + terminal close capability.

Usage:
    python3 chat_detector.py status             # Show all CCA Claude processes
    python3 chat_detector.py check <chat_id>    # Pre-launch safety check
    python3 chat_detector.py close              # Generate AppleScript to close current tab

Designed for hivemind workflow:
- launch_worker.sh calls 'check cli1' before launching
- /cca-wrap calls 'close' to clean up terminal tabs
- /cca-init calls 'status' to flag duplicates at session start

Stdlib only. No external dependencies.
"""

import os
import re
import subprocess
import sys
from collections import defaultdict
from typing import Optional

CCA_PROJECT_PATH = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"


def _run_ps() -> str:
    """Run ps to get process listing. Separated for testability."""
    try:
        result = subprocess.run(
            ["ps", "axo", "pid,command"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def parse_ps_line(line: str) -> Optional[dict]:
    """Parse a single ps output line into a process dict.

    Returns dict with pid and command, or None if unparseable.
    """
    line = line.strip()
    if not line:
        return None

    match = re.match(r"(\d+)\s+(.+)", line)
    if not match:
        return None

    pid = int(match.group(1))
    command = match.group(2)

    return {"pid": pid, "command": command}


def is_cca_project(command: str) -> bool:
    """Check if a command string references the CCA project directory."""
    if not command:
        return False
    return "ClaudeCodeAdvancements" in command


def extract_chat_id_from_env(env_str: str) -> Optional[str]:
    """Extract CCA_CHAT_ID from a process environment string.

    Environment strings come from 'ps eww' output where env vars
    appear as KEY=VALUE pairs separated by spaces.
    """
    match = re.search(r"CCA_CHAT_ID=(\S+)", env_str)
    if match:
        return match.group(1)
    return None


def find_claude_processes() -> list:
    """Find all running Claude Code processes for the CCA project.

    Returns list of dicts with: pid, command, chat_id, cca_project
    """
    ps_output = _run_ps()
    processes = []

    for line in ps_output.strip().split("\n"):
        parsed = parse_ps_line(line)
        if parsed is None:
            continue

        command = parsed["command"]

        # Must be a claude process, not grep
        if "claude" not in command.lower():
            continue
        if command.strip().startswith("grep"):
            continue

        # Try to get chat ID from command env vars
        chat_id = extract_chat_id_from_env(command)

        processes.append({
            "pid": parsed["pid"],
            "command": command,
            "chat_id": chat_id,
            "cca_project": is_cca_project(command),
        })

    return processes


def find_duplicates(processes: list) -> list:
    """Find duplicate CCA chat sessions.

    Groups CCA processes by chat_id. Any group with 2+ processes is a duplicate.
    Returns list of dicts: {chat_id, pids, count}
    """
    cca_procs = [p for p in processes if p.get("cca_project")]

    groups = defaultdict(list)
    for proc in cca_procs:
        groups[proc["chat_id"]].append(proc["pid"])

    duplicates = []
    for chat_id, pids in groups.items():
        if len(pids) >= 2:
            duplicates.append({
                "chat_id": chat_id,
                "pids": pids,
                "count": len(pids),
            })

    return duplicates


def generate_status_report(processes: list) -> dict:
    """Generate a status report for CCA Claude processes.

    Returns dict with: status, process_count, processes, duplicates
    """
    cca_procs = [p for p in processes if p.get("cca_project")]
    duplicates = find_duplicates(processes)

    if not cca_procs:
        status = "clean"
    elif duplicates:
        status = "duplicates_found"
    else:
        status = "healthy"

    return {
        "status": status,
        "process_count": len(cca_procs),
        "processes": cca_procs,
        "duplicates": duplicates,
    }


def generate_close_script() -> str:
    """Generate AppleScript to close the current Terminal tab.

    Used by /cca-wrap-worker to clean up after session ends.
    """
    return '''tell application "Terminal"
    set targetWindow to front window
    set targetTab to selected tab of targetWindow
    close targetTab
end tell'''


def pre_launch_check(target_chat_id: str) -> dict:
    """Check if it's safe to launch a new worker with the given chat ID.

    Returns dict with: safe (bool), reason (str), warnings (list)
    """
    processes = find_claude_processes()
    cca_procs = [p for p in processes if p.get("cca_project")]

    warnings = []
    # Check for stale processes (no chat ID)
    stale = [p for p in cca_procs if p["chat_id"] is None]
    if stale:
        pids = [str(p["pid"]) for p in stale]
        warnings.append(f"Stale CCA process(es) without chat ID: PIDs {', '.join(pids)}")

    # Check for existing process with same chat ID
    existing = [p for p in cca_procs if p["chat_id"] == target_chat_id]
    if existing:
        pids = [str(p["pid"]) for p in existing]
        return {
            "safe": False,
            "reason": f"Existing {target_chat_id} process(es) found: PIDs {', '.join(pids)}. Kill or wrap before launching new.",
            "warnings": warnings,
        }

    return {
        "safe": True,
        "reason": f"No existing {target_chat_id} processes. Safe to launch.",
        "warnings": warnings,
    }


def cli_main(args: list = None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] not in ("status", "check", "close"):
        print("chat_detector.py — CCA Claude Code Chat Session Manager")
        print()
        print("Commands:")
        print("  status              Show all CCA Claude processes + duplicates")
        print("  check <chat_id>     Pre-launch safety check (cli1/cli2/desktop)")
        print("  close               Print AppleScript to close current Terminal tab")
        print()
        print("Examples:")
        print("  python3 chat_detector.py status")
        print("  python3 chat_detector.py check cli1")
        return

    cmd = args[0]

    if cmd == "status":
        processes = find_claude_processes()
        report = generate_status_report(processes)
        print(f"CCA Chat Status: {report['status'].upper()}")
        print(f"CCA Processes: {report['process_count']}")
        if report["processes"]:
            for p in report["processes"]:
                role = p["chat_id"] or "unknown"
                print(f"  PID {p['pid']}: {role}")
        if report["duplicates"]:
            print("\nDUPLICATES DETECTED:")
            for d in report["duplicates"]:
                role = d["chat_id"] or "unknown"
                print(f"  {role}: {d['count']} instances (PIDs: {', '.join(map(str, d['pids']))})")

    elif cmd == "check":
        if len(args) < 2:
            print("Usage: check <chat_id>  (cli1/cli2/desktop)")
            return
        target = args[1]
        result = pre_launch_check(target)
        if result["safe"]:
            print(f"SAFE: {result['reason']}")
        else:
            print(f"BLOCKED: {result['reason']}")
        for w in result.get("warnings", []):
            print(f"  WARNING: {w}")

    elif cmd == "close":
        print(generate_close_script())


if __name__ == "__main__":
    cli_main()
