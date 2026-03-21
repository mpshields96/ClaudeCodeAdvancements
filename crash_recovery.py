#!/usr/bin/env python3
"""
crash_recovery.py — Worker crash detection and scope recovery.

Handles the Phase 2 hivemind scenario where a CLI worker crashes mid-scope-claim,
leaving orphaned scopes and potentially uncommitted work.

Recovery pipeline:
1. Detect orphaned scopes (scope_claim without a running worker process)
2. Release orphaned scopes (write scope_release to queue)
3. Report uncommitted git changes that may need attention
4. Generate a recovery report for the desktop coordinator

Usage:
    python3 crash_recovery.py run          # Full recovery pipeline
    python3 crash_recovery.py status       # Detection only (no changes)

Designed to be called from:
- /cca-init (Step 4.5, alongside chat_detector.py status)
- /cca-auto-desktop (periodic health check)
- Manual invocation after suspected crash

Stdlib only. No external dependencies.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import chat_detector
import cca_internal_queue as ciq

WORKER_CHAT_IDS = {"cli1", "cli2", "terminal"}
DEFAULT_QUEUE_PATH = os.path.join(SCRIPT_DIR, "cca_internal_queue.jsonl")


def _get_claude_processes() -> list:
    """Get running Claude processes. Wrapper for testability."""
    return chat_detector.find_claude_processes()


def _get_git_status() -> str:
    """Get git status --short. Wrapper for testability."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, timeout=5,
            cwd=SCRIPT_DIR,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _get_active_scopes(queue_path: str = DEFAULT_QUEUE_PATH) -> list:
    """Get active scope claims from queue. Wrapper for testability."""
    return ciq.get_active_scopes(queue_path)


def detect_crashed_workers(active_scopes: list) -> list:
    """Detect workers that have scope claims but no running process.

    A 'crashed worker' is one where:
    - A scope_claim exists from a worker chat ID (cli1/cli2/terminal)
    - No Claude process with that chat_id is currently running

    Desktop scopes are never considered crashed (desktop doesn't crash in the same way).

    Returns list of dicts: {chat_id, scope, created_at, pid}
    """
    processes = _get_claude_processes()
    running_chat_ids = {
        p["chat_id"] for p in processes
        if p.get("cca_project") and p.get("chat_id")
    }

    crashed = []
    for scope in active_scopes:
        sender = scope.get("sender", "")
        if sender not in WORKER_CHAT_IDS:
            continue
        if sender in running_chat_ids:
            continue
        crashed.append({
            "chat_id": sender,
            "scope": scope.get("subject", "unknown"),
            "created_at": scope.get("created_at", ""),
            "pid": None,
        })

    return crashed


def release_orphaned_scopes(crashed_workers: list, queue_path: str = DEFAULT_QUEUE_PATH) -> list:
    """Release scope claims from crashed workers.

    Checks if scope is still active (not already released) before releasing.
    Writes scope_release with crash-recovery marker.

    Returns list of released scopes.
    """
    active = ciq.get_active_scopes(queue_path)
    active_subjects = {
        (s.get("sender", ""), s.get("subject", ""))
        for s in active
    }

    released = []
    for crash in crashed_workers:
        key = (crash["chat_id"], crash["scope"])
        if key not in active_subjects:
            continue

        ciq.send_message(
            sender=crash["chat_id"],
            target="desktop",
            subject=crash["scope"],
            body=f"crash-recovery: auto-released scope from {crash['chat_id']} (no running process found)",
            category="scope_release",
            path=queue_path,
        )
        released.append({"scope": crash["scope"], "chat_id": crash["chat_id"]})

    return released


def generate_recovery_report(crashed: list, released: list, git_status: str) -> dict:
    """Generate a structured recovery report.

    Returns dict with: status, actions, summary, has_uncommitted_changes
    """
    actions = []
    has_uncommitted = bool(git_status.strip())

    for r in released:
        actions.append(f"Released orphaned scope '{r['scope']}' from {r['chat_id']}")

    if has_uncommitted and crashed:
        actions.append(f"Uncommitted changes detected (may be from crashed worker): {git_status[:200]}")

    if not crashed:
        status = "clean"
        summary = "No crashed workers detected."
    elif released:
        status = "recovered"
        chat_ids = ", ".join(set(c["chat_id"] for c in crashed))
        summary = f"Recovered from crash: {chat_ids}. Released {len(released)} orphaned scope(s)."
    else:
        status = "detected"
        chat_ids = ", ".join(set(c["chat_id"] for c in crashed))
        summary = f"Crash detected for {chat_ids} but scopes already released."

    return {
        "status": status,
        "actions": actions,
        "summary": summary,
        "has_uncommitted_changes": has_uncommitted,
        "crashed_workers": crashed,
        "released_scopes": released,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def expire_stale_scopes(queue_path: str = DEFAULT_QUEUE_PATH, timeout_minutes: int = 30) -> list:
    """Expire scope claims older than timeout_minutes, even if worker is still running.

    This catches hung workers — process alive but stuck/unresponsive.
    Delegates to ciq.expire_stale_scopes() which writes scope_release messages.

    Returns list of expired scope claims.
    """
    return ciq.expire_stale_scopes(timeout_minutes=timeout_minutes, path=queue_path)


def run_recovery(queue_path: str = DEFAULT_QUEUE_PATH) -> dict:
    """Run the full recovery pipeline.

    1. Expire stale scopes (hung workers — process alive but scope too old)
    2. Get active scopes from queue
    3. Detect crashed workers (scope without process)
    4. Release orphaned scopes
    5. Check git status for uncommitted work
    6. Generate and return report
    """
    # Step 1: Expire stale scopes first (catches hung workers)
    stale_expired = expire_stale_scopes(queue_path)

    # Step 2-4: Detect and release crashed worker scopes
    active_scopes = _get_active_scopes(queue_path)
    crashed = detect_crashed_workers(active_scopes)
    released = release_orphaned_scopes(crashed, queue_path)
    git_status = _get_git_status()

    report = generate_recovery_report(crashed, released, git_status)
    # Include stale scope info in report
    if stale_expired:
        report["stale_expired"] = len(stale_expired)
        report["actions"].insert(0, f"Expired {len(stale_expired)} stale scope(s) (>30m old)")
        if report["status"] == "clean":
            report["status"] = "recovered"
            report["summary"] = f"Expired {len(stale_expired)} stale scope(s)."
    else:
        report["stale_expired"] = 0

    return report


def cli_main(args: list = None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] not in ("run", "status"):
        print("crash_recovery.py — Worker Crash Detection and Recovery")
        print()
        print("Commands:")
        print("  run       Full recovery pipeline (detect + release + report)")
        print("  status    Detection only (no modifications)")
        print()
        return

    cmd = args[0]

    if cmd == "run":
        report = run_recovery()
        print(f"Recovery Status: {report['status'].upper()}")
        print(f"Summary: {report['summary']}")
        for action in report["actions"]:
            print(f"  - {action}")
        if report.get("has_uncommitted_changes"):
            print("  WARNING: Uncommitted changes may need manual review")

    elif cmd == "status":
        processes = _get_claude_processes()
        scopes = _get_active_scopes()
        crashed = detect_crashed_workers(scopes)

        if not crashed:
            print("No crashed workers detected.")
            print(f"Running CCA processes: {len([p for p in processes if p.get('cca_project')])}")
            print(f"Active scopes: {len(scopes)}")
        else:
            print(f"CRASHED WORKERS DETECTED: {len(crashed)}")
            for c in crashed:
                print(f"  {c['chat_id']}: scope '{c['scope']}' (no running process)")
            print()
            print("Run 'python3 crash_recovery.py run' to recover.")


if __name__ == "__main__":
    cli_main()
