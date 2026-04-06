#!/usr/bin/env python3
"""
overhead_timer.py — Measures coordination overhead vs productive work time
for hivemind Phase 1 validation.

Phase 1 target: overhead ratio < 15% (time on coordination vs actual work).

Usage:
    timer = OverheadTimer()

    # When doing coordination (queue checks, scope claims, inbox reads)
    timer.start("coordination")
    # ... do coordination work ...
    timer.stop()

    # When doing productive work (writing code, running tests)
    timer.start("work")
    # ... do productive work ...
    timer.stop()

    # Get the ratio
    print(timer.get_ratio())     # 0.12 = 12% overhead
    print(timer.format_summary())

    # Save for cross-session tracking
    timer.save(90)  # session number

Stdlib only. No external dependencies.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_PATH = os.path.join(SCRIPT_DIR, "overhead_log.jsonl")

VALID_TYPES = ("coordination", "work")


class OverheadTimer:
    """Track coordination overhead vs productive work time."""

    def __init__(self):
        self.coordination_seconds: float = 0.0
        self.work_seconds: float = 0.0
        self.current_type: str | None = None
        self._start_time: float | None = None

    def start(self, activity_type: str) -> None:
        """Start timing an activity segment."""
        if activity_type not in VALID_TYPES:
            raise ValueError(f"Invalid type: {activity_type}. Must be one of {VALID_TYPES}")
        if self.current_type is not None:
            raise RuntimeError(f"Already timing '{self.current_type}'. Call stop() first.")
        self.current_type = activity_type
        self._start_time = time.monotonic()

    def stop(self) -> float:
        """Stop timing and accumulate. Returns elapsed seconds."""
        if self.current_type is None or self._start_time is None:
            raise RuntimeError("No active timer. Call start() first.")
        elapsed = time.monotonic() - self._start_time
        if self.current_type == "coordination":
            self.coordination_seconds += elapsed
        else:
            self.work_seconds += elapsed
        self.current_type = None
        self._start_time = None
        return elapsed

    def get_ratio(self) -> float:
        """Get coordination overhead ratio (0.0 to 1.0)."""
        total = self.coordination_seconds + self.work_seconds
        if total == 0:
            return 0.0
        return self.coordination_seconds / total

    def format_summary(self) -> str:
        """Human-readable summary."""
        ratio = self.get_ratio()
        total = self.coordination_seconds + self.work_seconds
        return (
            f"Overhead: {ratio * 100:.1f}% coordination "
            f"({self.coordination_seconds:.0f}s coord / {self.work_seconds:.0f}s work / "
            f"{total:.0f}s total)"
        )

    def save(self, session: int, path: str = DEFAULT_LOG_PATH) -> None:
        """Persist this session's overhead data."""
        entry = {
            "session": session,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "coordination_seconds": round(self.coordination_seconds, 2),
            "work_seconds": round(self.work_seconds, 2),
            "ratio": round(self.get_ratio(), 4),
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")


def load_history(path: str = DEFAULT_LOG_PATH) -> list[dict]:
    """Read all overhead log entries."""
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


def avg_overhead(path: str = DEFAULT_LOG_PATH) -> float:
    """Average overhead ratio across all recorded sessions."""
    entries = load_history(path)
    if not entries:
        return 0.0
    return sum(e.get("ratio", 0) for e in entries) / len(entries)
