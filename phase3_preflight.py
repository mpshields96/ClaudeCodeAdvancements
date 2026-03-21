#!/usr/bin/env python3
"""
phase3_preflight.py — Pre-session safety checks for 3-chat hivemind.

Run before launching Phase 3 to verify:
1. No duplicate workers already running
2. Queue file accessible and not corrupted
3. No stale scope claims from previous sessions

Usage:
    import phase3_preflight as pf

    result = pf.run_preflight()
    print(pf.format_report(result))
    if not result["ok"]:
        print("Fix issues before launching Phase 3")

CLI:
    python3 phase3_preflight.py
    # Prints preflight report and exits with 0 (pass) or 1 (fail)

Stdlib only. No external dependencies.
"""

import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_QUEUE_PATH = os.path.join(SCRIPT_DIR, "cca_internal_queue.jsonl")
WORKER_IDS = ["cli1", "cli2"]


def _check_worker_running(worker_id: str) -> bool:
    """Check if a worker process is running via chat_detector."""
    try:
        result = subprocess.run(
            ["python3", os.path.join(SCRIPT_DIR, "chat_detector.py"), "check", worker_id],
            capture_output=True, text=True, timeout=5,
        )
        return "BLOCKED" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False  # Fail open — can't detect, assume not running


def check_no_duplicate_workers() -> dict:
    """Check that no cli1/cli2 workers are already running."""
    running = [wid for wid in WORKER_IDS if _check_worker_running(wid)]
    return {
        "name": "No duplicate workers",
        "ok": len(running) == 0,
        "running": running,
    }


def check_queue_health(queue_path: str = DEFAULT_QUEUE_PATH) -> dict:
    """Check queue file is accessible and parseable."""
    if not os.path.exists(queue_path):
        return {
            "name": "Queue health",
            "ok": True,
            "reason": "no queue file (fresh start)",
            "total_lines": 0,
            "corrupt_lines": 0,
        }

    total = 0
    corrupt = 0
    try:
        with open(queue_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    corrupt += 1
    except OSError as e:
        return {
            "name": "Queue health",
            "ok": False,
            "reason": f"cannot read queue: {e}",
            "total_lines": 0,
            "corrupt_lines": 0,
        }

    return {
        "name": "Queue health",
        "ok": True,  # Corrupt lines are warnings, not failures
        "total_lines": total,
        "corrupt_lines": corrupt,
    }


def check_stale_scopes(queue_path: str = DEFAULT_QUEUE_PATH) -> dict:
    """Check for unreleased scope claims from previous sessions."""
    if not os.path.exists(queue_path):
        return {"name": "Stale scopes", "ok": True, "stale_count": 0, "stale_scopes": []}

    messages = []
    try:
        with open(queue_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return {"name": "Stale scopes", "ok": True, "stale_count": 0, "stale_scopes": []}

    # Find active (unreleased) scope claims
    claims = [m for m in messages if m.get("category") == "scope_claim"]
    releases = [m for m in messages if m.get("category") == "scope_release"]

    stale = []
    for claim in claims:
        sender = claim.get("sender", "")
        subject = claim.get("subject", "")
        claim_time = claim.get("created_at", "")

        released = any(
            r.get("sender") == sender
            and r.get("created_at", "") > claim_time
            and (r.get("subject", "") == subject or subject in r.get("subject", ""))
            for r in releases
        )
        if not released:
            stale.append({"sender": sender, "subject": subject, "claimed_at": claim_time})

    return {
        "name": "Stale scopes",
        "ok": len(stale) == 0,
        "stale_count": len(stale),
        "stale_scopes": stale,
    }


def run_preflight(queue_path: str = DEFAULT_QUEUE_PATH) -> dict:
    """Run all preflight checks. Returns combined result."""
    checks = [
        check_no_duplicate_workers(),
        check_queue_health(queue_path),
        check_stale_scopes(queue_path),
    ]

    all_ok = all(c["ok"] for c in checks)
    return {
        "ok": all_ok,
        "checks": checks,
    }


def format_report(result: dict) -> str:
    """Format preflight result as readable report."""
    lines = ["Phase 3 Preflight:", ""]

    for check in result["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        name = check.get("name", "Unknown check")
        lines.append(f"  [{status}] {name}")

        # Add details for failures
        if not check["ok"]:
            if "running" in check:
                lines.append(f"         Running: {', '.join(check['running'])}")
            if "stale_scopes" in check:
                for s in check["stale_scopes"]:
                    lines.append(f"         Stale: {s['sender']} -> {s['subject']}")

        # Add warnings
        if check.get("corrupt_lines", 0) > 0:
            lines.append(f"         Warning: {check['corrupt_lines']} corrupt lines in queue")

    lines.append("")
    overall = "READY" if result["ok"] else "NOT READY"
    lines.append(f"  Overall: {overall}")

    return "\n".join(lines)


if __name__ == "__main__":
    result = run_preflight()
    print(format_report(result))
    sys.exit(0 if result["ok"] else 1)
