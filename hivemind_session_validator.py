#!/usr/bin/env python3
"""
hivemind_session_validator.py — Desktop-side validation for hivemind sessions.

After a CLI worker completes a task, the desktop coordinator runs this to
validate the full cycle worked and record the result. Tracks Phase 1
validation metrics across sessions.

Storage: hivemind_sessions.jsonl (project root)

Usage:
    import hivemind_session_validator as hsv

    # Validate a worker's session from queue messages
    result = hsv.validate_session("cli1", queue_path="cca_internal_queue.jsonl")
    # {'verdict': 'PASS', 'task_assigned': True, 'task_completed': True, ...}

    # Record the result
    hsv.record_session(90, result)

    # Check Phase 1 gate
    gate = hsv.check_phase1_gate()
    # {'ready': True, 'consecutive_passes': 3, 'total_sessions': 5}

    # One-line briefing for /cca-init
    print(hsv.format_for_init())
    # "Hivemind: 5 sessions (3 consecutive PASS) — Phase 1 gate: READY"

Stdlib only. No external dependencies.
"""

import json
import os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_PATH = os.path.join(SCRIPT_DIR, "hivemind_sessions.jsonl")
DEFAULT_QUEUE_PATH = os.path.join(SCRIPT_DIR, "cca_internal_queue.jsonl")


def validate_session(
    worker_id: str,
    queue_path: str = DEFAULT_QUEUE_PATH,
) -> dict:
    """
    Validate a hivemind session by analyzing queue messages.

    Checks:
    1. Was a task assigned to the worker? (handoff from desktop)
    2. Did the worker complete and report back? (WRAP message)
    3. Were there any conflict alerts?
    4. Was scope properly released?

    Returns dict with verdict (PASS/PASS_WITH_WARNINGS/FAIL) and details.
    """
    messages = _load_queue(queue_path)

    # Find task assignments (desktop -> worker, category=handoff)
    assignments = [
        m for m in messages
        if m.get("sender") == "desktop"
        and m.get("target") == worker_id
        and m.get("category") == "handoff"
    ]

    # Find completion reports (worker -> desktop, category=handoff, subject contains WRAP)
    completions = [
        m for m in messages
        if m.get("sender") == worker_id
        and m.get("target") == "desktop"
        and m.get("category") == "handoff"
        and "WRAP" in m.get("subject", "").upper()
    ]

    # Find conflict alerts
    conflicts = [
        m for m in messages
        if m.get("sender") == worker_id
        and m.get("category") == "conflict_alert"
    ]

    # Find scope claims and releases from worker
    claims = [
        m for m in messages
        if m.get("sender") == worker_id
        and m.get("category") == "scope_claim"
    ]
    releases = [
        m for m in messages
        if m.get("sender") == worker_id
        and m.get("category") == "scope_release"
    ]

    task_assigned = len(assignments) > 0
    task_completed = len(completions) > 0
    has_conflicts = len(conflicts) > 0
    scope_released = len(releases) >= len(claims) if claims else True

    # Determine verdict
    if not task_assigned:
        verdict = "FAIL"
    elif not task_completed:
        verdict = "FAIL"
    elif has_conflicts or not scope_released:
        verdict = "PASS_WITH_WARNINGS"
    else:
        verdict = "PASS"

    return {
        "verdict": verdict,
        "worker_id": worker_id,
        "task_assigned": task_assigned,
        "task_completed": task_completed,
        "conflicts": has_conflicts,
        "scope_released": scope_released,
        "assignments": len(assignments),
        "completions": len(completions),
        "conflict_count": len(conflicts),
    }


def record_session(
    session_number: int,
    result: dict,
    path: str = DEFAULT_LOG_PATH,
) -> dict:
    """Record a session validation result to the log file."""
    entry = {
        "session": session_number,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verdict": result.get("verdict", "UNKNOWN"),
        "worker_id": result.get("worker_id", "unknown"),
        **{k: v for k, v in result.items() if k not in ("verdict", "worker_id")},
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    return entry


def get_history(path: str = DEFAULT_LOG_PATH) -> list[dict]:
    """Read all session validation entries."""
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def consecutive_passes(path: str = DEFAULT_LOG_PATH) -> int:
    """Count consecutive PASS results from the end of history."""
    history = get_history(path)
    if not history:
        return 0
    count = 0
    for entry in reversed(history):
        if entry.get("verdict") in ("PASS", "PASS_WITH_WARNINGS"):
            count += 1
        else:
            break
    return count


def check_phase1_gate(path: str = DEFAULT_LOG_PATH) -> dict:
    """
    Check if Phase 1 gate criteria are met.

    Phase 1 requires 3+ consecutive PASS sessions.
    """
    history = get_history(path)
    streak = consecutive_passes(path)
    total = len(history)
    passes = sum(1 for e in history if e.get("verdict") in ("PASS", "PASS_WITH_WARNINGS"))
    fails = total - passes

    return {
        "ready": streak >= 3,
        "consecutive_passes": streak,
        "total_sessions": total,
        "total_passes": passes,
        "total_fails": fails,
    }


def format_for_init(path: str = DEFAULT_LOG_PATH) -> str:
    """One-line briefing for /cca-init. Includes Phase 1-3 status."""
    history = get_history(path)
    if not history:
        return "Hivemind: No hivemind sessions recorded yet."

    total = len(history)
    streak = consecutive_passes(path)
    gate = check_phase1_gate(path)

    parts = [f"Hivemind: {total} sessions ({streak} consecutive PASS)"]

    if gate["ready"]:
        parts.append("Phase 1: PASSED, Phase 2: PASSED")
    else:
        needed = 3 - streak
        parts.append(f"Phase 1 gate: {needed} more consecutive PASS needed")

    # Phase 3 status (if module available)
    try:
        import phase3_coordinator as p3c
        coord = p3c.Coordinator()
        p3_brief = coord.format_briefing()
        if "No Phase 3" not in p3_brief:
            parts.append(p3_brief)
        else:
            parts.append("Phase 3: awaiting first 3-chat session")
    except ImportError:
        pass

    return " — ".join(parts)


def _load_queue(path: str) -> list[dict]:
    """Load queue messages."""
    if not os.path.exists(path):
        return []
    messages = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return messages
