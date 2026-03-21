#!/usr/bin/env python3
"""
phase3_validator.py — Validates 3-chat hivemind sessions from queue messages.

Analyzes cca_internal_queue.jsonl to determine if a 3-chat session
(desktop + cli1 + cli2) completed successfully. Detects inter-worker
scope conflicts, incomplete tasks, and coordination failures.

Usage:
    import phase3_validator as p3v

    # Validate the current session
    result = p3v.validate_3chat_session()
    # {'verdict': 'PASS', 'workers_validated': 2, 'inter_worker_conflicts': 0, ...}

    # Detect scope conflicts between workers
    conflicts = p3v.detect_inter_worker_conflicts()

    # Per-worker activity summary
    summary = p3v.worker_activity_summary()

    # Record and track sessions
    p3v.record_session(100, result)

Stdlib only. No external dependencies.
"""

import json
import os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_QUEUE_PATH = os.path.join(SCRIPT_DIR, "cca_internal_queue.jsonl")
DEFAULT_LOG_PATH = os.path.join(SCRIPT_DIR, "phase3_sessions.jsonl")

WORKER_IDS = ("cli1", "cli2")


def _load_queue(path: str) -> list[dict]:
    """Load queue messages from JSONL file."""
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


def validate_3chat_session(
    queue_path: str = DEFAULT_QUEUE_PATH,
) -> dict:
    """
    Validate a 3-chat hivemind session by analyzing queue messages.

    Checks per worker:
    1. Was a task assigned? (desktop -> worker handoff)
    2. Did the worker complete? (worker -> desktop WRAP handoff)
    3. Were there inter-worker scope conflicts?

    Returns dict with verdict and details.
    """
    messages = _load_queue(queue_path)
    if not messages:
        return {"verdict": "NO_DATA", "workers_validated": 0, "inter_worker_conflicts": 0, "incomplete_workers": []}

    # Identify which workers participated (had tasks assigned)
    active_workers = set()
    for m in messages:
        if m.get("sender") == "desktop" and m.get("target") in WORKER_IDS and m.get("category") == "handoff":
            active_workers.add(m["target"])

    if not active_workers:
        return {"verdict": "NO_DATA", "workers_validated": 0, "inter_worker_conflicts": 0, "incomplete_workers": []}

    # Check completion per worker
    incomplete = []
    for wid in active_workers:
        completions = [
            m for m in messages
            if m.get("sender") == wid
            and m.get("target") == "desktop"
            and m.get("category") == "handoff"
            and "WRAP" in m.get("subject", "").upper()
        ]
        if not completions:
            incomplete.append(wid)

    # Check inter-worker conflicts
    conflicts = detect_inter_worker_conflicts(queue_path)
    conflict_count = len(conflicts)

    # Determine verdict
    if incomplete:
        verdict = "FAIL"
    elif conflict_count > 0:
        verdict = "PASS_WITH_WARNINGS"
    else:
        verdict = "PASS"

    return {
        "verdict": verdict,
        "workers_validated": len(active_workers),
        "active_workers": sorted(active_workers),
        "inter_worker_conflicts": conflict_count,
        "incomplete_workers": sorted(incomplete),
    }


def detect_inter_worker_conflicts(
    queue_path: str = DEFAULT_QUEUE_PATH,
) -> list[dict]:
    """
    Detect scope conflicts between workers (cli1 vs cli2).

    A conflict occurs when both workers have active scope claims on the
    same file at the same time (overlapping claim periods).

    Returns list of conflict dicts.
    """
    messages = _load_queue(queue_path)

    # Build per-worker scope timelines: [(file, claim_time, release_time)]
    worker_scopes: dict[str, list[tuple[str, str, str]]] = {}

    for wid in WORKER_IDS:
        claims = [
            m for m in messages
            if m.get("sender") == wid and m.get("category") == "scope_claim"
        ]
        releases = [
            m for m in messages
            if m.get("sender") == wid and m.get("category") == "scope_release"
        ]

        timelines = []
        for claim in claims:
            claim_files = claim.get("files", [claim.get("subject", "")])
            claim_time = claim.get("created_at", "")

            # Find matching release
            release_time = "9999-12-31T23:59:59Z"  # Still active if no release
            for rel in releases:
                rel_files = rel.get("files", [rel.get("subject", "")])
                if rel.get("created_at", "") > claim_time:
                    # Check file overlap
                    if set(claim_files) & set(rel_files):
                        release_time = rel.get("created_at", "")
                        break

            for f in claim_files:
                timelines.append((f, claim_time, release_time))

        worker_scopes[wid] = timelines

    # Check for temporal overlaps between workers
    conflicts = []
    workers = [w for w in WORKER_IDS if w in worker_scopes]

    for i, w1 in enumerate(workers):
        for w2 in workers[i + 1:]:
            for f1, start1, end1 in worker_scopes[w1]:
                for f2, start2, end2 in worker_scopes[w2]:
                    if f1 == f2:
                        # Check time overlap: start1 < end2 AND start2 < end1
                        if start1 < end2 and start2 < end1:
                            conflicts.append({
                                "file": f1,
                                "workers": [w1, w2],
                                "w1_period": (start1, end1),
                                "w2_period": (start2, end2),
                            })

    return conflicts


def worker_activity_summary(
    queue_path: str = DEFAULT_QUEUE_PATH,
) -> dict[str, dict]:
    """
    Per-worker activity summary from queue messages.

    Returns dict keyed by worker_id with:
    - messages_sent: total messages from this worker
    - completed: whether worker sent a WRAP message
    - tasks_received: count of handoff messages to this worker
    """
    messages = _load_queue(queue_path)
    if not messages:
        return {}

    summary = {}
    for wid in WORKER_IDS:
        sent = [m for m in messages if m.get("sender") == wid]
        received = [
            m for m in messages
            if m.get("target") == wid and m.get("sender") == "desktop" and m.get("category") == "handoff"
        ]
        completed = any(
            m.get("category") == "handoff" and "WRAP" in m.get("subject", "").upper()
            for m in sent
        )

        if sent or received:
            summary[wid] = {
                "messages_sent": len(sent),
                "tasks_received": len(received),
                "completed": completed,
            }

    return summary


def record_session(
    session_number: int,
    result: dict,
    path: str = DEFAULT_LOG_PATH,
) -> dict:
    """Record a 3-chat session validation result."""
    entry = {
        "session": session_number,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verdict": result.get("verdict", "UNKNOWN"),
        "workers_validated": result.get("workers_validated", 0),
        "inter_worker_conflicts": result.get("inter_worker_conflicts", 0),
        "incomplete_workers": result.get("incomplete_workers", []),
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


def format_for_init(path: str = DEFAULT_LOG_PATH) -> str:
    """One-line briefing for /cca-init."""
    history = get_history(path)
    if not history:
        return "Phase 3 validation: No Phase 3 sessions recorded."

    total = len(history)
    passes = sum(1 for e in history if e.get("verdict") in ("PASS", "PASS_WITH_WARNINGS"))

    # Count consecutive passes from end
    streak = 0
    for entry in reversed(history):
        if entry.get("verdict") in ("PASS", "PASS_WITH_WARNINGS"):
            streak += 1
        else:
            break

    return f"Phase 3 validation: {total} sessions ({streak} consecutive PASS, {passes}/{total} total)"
