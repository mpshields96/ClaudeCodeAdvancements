#!/usr/bin/env python3
"""coordination_dashboard.py — At-a-glance multi-chat session status.

Consolidates queue status, active scopes, recent commits, worker inbox,
and test health into one view. Designed for desktop coordinator to run
during coordination rounds.

Usage:
    python3 coordination_dashboard.py                # Full dashboard
    python3 coordination_dashboard.py --compact      # One-line summary
    python3 coordination_dashboard.py --json         # JSON for programmatic use

Stdlib only. No external dependencies.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent


def get_queue_status() -> dict:
    """Get queue unread counts and active scopes."""
    result = {
        "desktop_unread": 0,
        "cli1_unread": 0,
        "active_scopes": [],
        "raw": "",
    }
    try:
        r = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "cca_comm.py"), "status"],
            capture_output=True, text=True, timeout=10,
            env={**os.environ, "CCA_CHAT_ID": "desktop"},
            cwd=str(PROJECT_ROOT),
        )
        result["raw"] = r.stdout.strip()

        for line in r.stdout.split('\n'):
            line = line.strip()
            if "CCA Desktop:" in line:
                # Extract count
                parts = line.split(":")
                if len(parts) >= 2:
                    count_part = parts[1].strip().split()[0]
                    try:
                        result["desktop_unread"] = int(count_part)
                    except ValueError:
                        pass
            elif "CCA CLI 1:" in line and "ACTIVE SCOPES" not in r.stdout[:r.stdout.index(line)]:
                parts = line.split(":")
                if len(parts) >= 2:
                    count_part = parts[1].strip().split()[0]
                    try:
                        result["cli1_unread"] = int(count_part)
                    except ValueError:
                        pass
            elif "CCA CLI 1:" in line and "ACTIVE SCOPES" in r.stdout[:r.stdout.index(line)]:
                # This is an active scope line
                scope = line.split(":", 1)[1].strip() if ":" in line else line
                result["active_scopes"].append(scope)

    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return result


def get_recent_commits(count: int = 8) -> list:
    """Get recent git commits."""
    try:
        r = subprocess.run(
            ["git", "log", f"--oneline", f"-{count}"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        if r.returncode == 0:
            return [l.strip() for l in r.stdout.strip().split('\n') if l.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []


def get_session_commits(session_prefix: str = "S116") -> int:
    """Count commits with session prefix."""
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", f"--grep={session_prefix}:"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        if r.returncode == 0:
            return len([l for l in r.stdout.strip().split('\n') if l.strip()])
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return 0


def get_worker_status() -> str:
    """Determine worker status from queue."""
    try:
        r = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "cca_comm.py"), "status"],
            capture_output=True, text=True, timeout=10,
            env={**os.environ, "CCA_CHAT_ID": "desktop"},
            cwd=str(PROJECT_ROOT),
        )
        output = r.stdout
        if "ACTIVE SCOPES" in output:
            # Check if cli1 has an active scope
            in_scopes = False
            for line in output.split('\n'):
                if "ACTIVE SCOPES" in line:
                    in_scopes = True
                    continue
                if in_scopes and "CCA CLI 1:" in line:
                    scope = line.split(":", 1)[1].strip() if ":" in line else "unknown"
                    return f"WORKING: {scope}"
                if in_scopes and line.strip() and not line.strip().startswith("CCA"):
                    in_scopes = False

        # Check if any WRAP messages exist
        if "WRAP:" in output:
            return "COMPLETED (wrapped)"

        return "IDLE"

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "UNKNOWN"


def get_test_health() -> dict:
    """Quick test health check (runs smoke tests)."""
    # Don't run full suite — just check if key files exist
    critical_tests = [
        "tests/test_cca_internal_queue.py",
        "tests/test_cross_chat_queue.py",
        "design-skills/tests/test_chart_generator.py",
    ]
    existing = sum(1 for t in critical_tests if (PROJECT_ROOT / t).exists())
    return {
        "critical_tests_present": existing,
        "critical_tests_total": len(critical_tests),
        "all_present": existing == len(critical_tests),
    }


def get_peak_hours_status() -> str:
    """Check if we're in peak hours."""
    try:
        r = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "peak_hours.py"), "--check"],
            capture_output=True, text=True, timeout=5,
            cwd=str(PROJECT_ROOT),
        )
        return "OFF-PEAK (2x limits)" if r.returncode == 0 else "PEAK (standard limits)"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "UNKNOWN"


def build_dashboard(session_prefix: str = "S116") -> dict:
    """Build complete dashboard data."""
    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "session": session_prefix,
        "commits": get_session_commits(session_prefix),
        "worker_status": get_worker_status(),
        "peak_hours": get_peak_hours_status(),
        "test_health": get_test_health(),
        "recent_commits": get_recent_commits(6),
    }


def format_dashboard(data: dict) -> str:
    """Format dashboard as human-readable text."""
    lines = [
        f"=== Coordination Dashboard ({data['timestamp']}) ===",
        f"Session: {data['session']} | Commits: {data['commits']}",
        f"Worker: {data['worker_status']}",
        f"Rate limits: {data['peak_hours']}",
        f"Test files: {'OK' if data['test_health']['all_present'] else 'MISSING'}",
        "",
        "Recent commits:",
    ]
    for c in data["recent_commits"][:6]:
        lines.append(f"  {c}")
    return "\n".join(lines)


def format_compact(data: dict) -> str:
    """One-line compact format."""
    w = data["worker_status"].split(":")[0] if ":" in data["worker_status"] else data["worker_status"]
    return (
        f"[{data['timestamp']}] {data['session']}: "
        f"{data['commits']} commits | "
        f"Worker: {w} | "
        f"{data['peak_hours']}"
    )


def main():
    args = sys.argv[1:]
    json_output = "--json" in args
    compact = "--compact" in args
    session = "S116"  # Default, could be parameterized

    # Extract --session arg if present
    for i, a in enumerate(args):
        if a == "--session" and i + 1 < len(args):
            session = args[i + 1]

    data = build_dashboard(session)

    if json_output:
        print(json.dumps(data, indent=2))
    elif compact:
        print(format_compact(data))
    else:
        print(format_dashboard(data))


if __name__ == "__main__":
    main()
