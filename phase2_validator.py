#!/usr/bin/env python3
"""
phase2_validator.py — Phase 2 Hivemind Infrastructure Validation

Exercises crash_recovery.py + chat_detector.py + cca_internal_queue.py together
as an integrated system. Validates that the Phase 2 hivemind stack is healthy
before each worker launch.

Validation pipeline:
1. Count JSONL queue messages (total/valid/corrupt)
2. Check queue structural integrity (active scopes, stale scopes, corrupt lines)
3. Run pre-launch safety check + crash recovery scan together
4. Report crash recovery integration status

Usage:
    python3 phase2_validator.py validate [chat_id]   # Full validation (default: cli1)
    python3 phase2_validator.py counts               # Queue message counts only
    python3 phase2_validator.py status               # Queue integrity only

Stdlib only. No external dependencies beyond project modules.
"""

import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import chat_detector
import crash_recovery
import cca_internal_queue as ciq

DEFAULT_QUEUE_PATH = os.path.join(SCRIPT_DIR, "cca_internal_queue.jsonl")


# ── Testability shim ─────────────────────────────────────────────────────────

def _get_processes() -> list:
    """Get running Claude processes. Separated for testability."""
    return chat_detector.find_claude_processes()


# ── Core functions ────────────────────────────────────────────────────────────

def count_queue_messages(queue_path: str = DEFAULT_QUEUE_PATH) -> dict:
    """Count messages in the JSONL queue file.

    Returns dict with: total, valid, corrupt
    - total: all non-blank lines
    - valid: successfully parsed JSON lines
    - corrupt: lines that fail JSON parsing
    """
    result = {"total": 0, "valid": 0, "corrupt": 0}

    if not os.path.exists(queue_path):
        return result

    try:
        with open(queue_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                result["total"] += 1
                try:
                    json.loads(line)
                    result["valid"] += 1
                except json.JSONDecodeError:
                    result["corrupt"] += 1
    except OSError:
        pass

    return result


def validate_queue_integrity(queue_path: str = DEFAULT_QUEUE_PATH) -> dict:
    """Validate structural integrity of the JSONL queue.

    Returns dict with: status, total_messages, active_scopes, corrupt_lines, details
    Status: healthy / warning / error
    """
    counts = count_queue_messages(queue_path)
    active_scopes = ciq.get_active_scopes(queue_path) if os.path.exists(queue_path) else []

    status = "healthy"
    details = []

    if counts["corrupt"] > 0:
        status = "warning"
        details.append(f"{counts['corrupt']} corrupt line(s) in queue")

    if not os.path.exists(queue_path):
        status = "healthy"

    return {
        "status": status,
        "total_messages": counts["valid"],
        "corrupt_lines": counts["corrupt"],
        "active_scopes": len(active_scopes),
        "details": details,
    }


def validate_pre_launch_pipeline(chat_id: str, queue_path: str = DEFAULT_QUEUE_PATH) -> dict:
    """Run pre-launch safety check + crash recovery scan together.

    Checks:
    1. No existing process with same chat_id (via chat_detector)
    2. No orphaned scopes from crashed workers (via crash_recovery)

    Returns dict with: status, pre_launch_safe, pre_launch_reason,
    crashed_workers_detected, warnings
    """
    processes = _get_processes()

    # Override crash_recovery's internal process getter with our injectable version
    # by patching the module-level wrapper
    _original_getter = crash_recovery._get_claude_processes
    crash_recovery._get_claude_processes = lambda: processes

    try:
        # Step 1: Pre-launch check
        pre_launch = chat_detector.pre_launch_check.__wrapped__(chat_id) \
            if hasattr(chat_detector.pre_launch_check, '__wrapped__') \
            else _pre_launch_check_with_processes(chat_id, processes)

        # Step 2: Crash recovery scan (uses patched _get_claude_processes)
        active_scopes = ciq.get_active_scopes(queue_path)
        crashed = crash_recovery.detect_crashed_workers(active_scopes)
    finally:
        crash_recovery._get_claude_processes = _original_getter

    warnings = list(pre_launch.get("warnings", []))

    if not pre_launch["safe"]:
        status = "blocked"
    elif crashed:
        status = "warning"
    else:
        status = "ready"

    return {
        "status": status,
        "pre_launch_safe": pre_launch["safe"],
        "pre_launch_reason": pre_launch["reason"],
        "crashed_workers_detected": len(crashed),
        "crashed_workers": crashed,
        "warnings": warnings,
    }


def _pre_launch_check_with_processes(chat_id: str, processes: list) -> dict:
    """Run pre-launch check using provided process list (no live ps call)."""
    cca_procs = [p for p in processes if p.get("cca_project")]

    warnings = []
    stale = [p for p in cca_procs if p["chat_id"] is None]
    if stale:
        pids = [str(p["pid"]) for p in stale]
        warnings.append(f"Stale CCA process(es) without chat ID: PIDs {', '.join(pids)}")

    existing = [p for p in cca_procs if p["chat_id"] == chat_id]
    if existing:
        pids = [str(p["pid"]) for p in existing]
        return {
            "safe": False,
            "reason": f"Existing {chat_id} process(es) found: PIDs {', '.join(pids)}. Kill or wrap before launching new.",
            "warnings": warnings,
        }

    return {
        "safe": True,
        "reason": f"No existing {chat_id} processes. Safe to launch.",
        "warnings": warnings,
    }


def validate_crash_recovery_integration(queue_path: str = DEFAULT_QUEUE_PATH) -> dict:
    """Validate crash_recovery + chat_detector working together.

    Detects orphaned scopes (scope claimed but no worker running) and
    auto-releases them. Reports result.

    Returns dict with: status, orphaned_scopes, released_scopes, details
    Status: clean / recovered / detected
    """
    processes = _get_processes()
    _original_getter = crash_recovery._get_claude_processes
    crash_recovery._get_claude_processes = lambda: processes

    try:
        active_scopes = ciq.get_active_scopes(queue_path)
        crashed = crash_recovery.detect_crashed_workers(active_scopes)
        released = crash_recovery.release_orphaned_scopes(crashed, queue_path)
        report = crash_recovery.generate_recovery_report(crashed, released, "")
    finally:
        crash_recovery._get_claude_processes = _original_getter

    return {
        "status": report["status"],
        "orphaned_scopes": len(crashed),
        "released_scopes": len(released),
        "details": report["actions"],
        "summary": report["summary"],
    }


def run_phase2_validation(
    chat_id: str = "cli1",
    queue_path: str = DEFAULT_QUEUE_PATH,
) -> dict:
    """Run the full Phase 2 validation pipeline.

    Combines all checks into a single structured report:
    - queue_counts: raw JSONL message counts
    - pre_launch: pre-launch safety + crash detection
    - crash_recovery: orphaned scope recovery status
    - status: overall status (ready / blocked / warning / error)
    - summary: one-line human-readable string

    Returns a dict suitable for display or logging.
    """
    queue_counts = count_queue_messages(queue_path)
    integrity = validate_queue_integrity(queue_path)
    pre_launch = validate_pre_launch_pipeline(chat_id, queue_path)
    crash_rec = validate_crash_recovery_integration(queue_path)

    # Determine overall status
    if not pre_launch["pre_launch_safe"]:
        status = "blocked"
    elif integrity["status"] == "warning" or pre_launch["crashed_workers_detected"] > 0:
        status = "warning"
    else:
        status = "ready"

    # Build summary
    parts = [f"Phase2 [{chat_id}]: {status.upper()}"]
    parts.append(f"queue={queue_counts['valid']} msgs")
    if queue_counts["corrupt"]:
        parts.append(f"{queue_counts['corrupt']} corrupt")
    if not pre_launch["pre_launch_safe"]:
        parts.append("LAUNCH BLOCKED")
    if pre_launch["crashed_workers_detected"]:
        parts.append(f"{pre_launch['crashed_workers_detected']} crashed worker(s)")
    if crash_rec["released_scopes"]:
        parts.append(f"{crash_rec['released_scopes']} scope(s) auto-released")

    return {
        "status": status,
        "chat_id": chat_id,
        "queue_counts": queue_counts,
        "queue_integrity": integrity,
        "pre_launch": pre_launch,
        "crash_recovery": crash_rec,
        "summary": " | ".join(parts),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def cli_main(args: list = None):
    if args is None:
        args = sys.argv[1:]

    cmd = args[0] if args else "validate"

    if cmd == "counts":
        counts = count_queue_messages()
        print(f"Queue messages: {counts['valid']} valid, {counts['corrupt']} corrupt, {counts['total']} total")
        return

    if cmd == "status":
        integrity = validate_queue_integrity()
        print(f"Queue integrity: {integrity['status'].upper()}")
        print(f"  Total messages: {integrity['total_messages']}")
        print(f"  Active scopes:  {integrity['active_scopes']}")
        print(f"  Corrupt lines:  {integrity['corrupt_lines']}")
        for detail in integrity["details"]:
            print(f"  WARNING: {detail}")
        return

    # Default: validate
    chat_id = args[1] if len(args) > 1 else os.environ.get("CCA_CHAT_ID", "cli1")
    report = run_phase2_validation(chat_id)

    print(report["summary"])
    print()
    print(f"  Queue:          {report['queue_counts']['valid']} msgs ({report['queue_counts']['corrupt']} corrupt)")
    print(f"  Pre-launch:     {'SAFE' if report['pre_launch']['pre_launch_safe'] else 'BLOCKED'} — {report['pre_launch']['pre_launch_reason']}")
    print(f"  Crash recovery: {report['crash_recovery']['status'].upper()} ({report['crash_recovery']['orphaned_scopes']} orphaned)")
    if report["pre_launch"]["warnings"]:
        for w in report["pre_launch"]["warnings"]:
            print(f"  WARNING: {w}")


if __name__ == "__main__":
    cli_main()
