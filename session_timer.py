#!/usr/bin/env python3
"""
session_timer.py — Per-step timing instrumentation for CCA session lifecycle.

MT-36 Phase 1: Measures WHERE time goes within init/wrap/auto cycles.
Unlike overhead_timer.py (binary coordination/work), this tracks individual
named steps with categories for granular efficiency analysis.

Usage:
    timer = SessionTimer(session_id=144)

    # Context manager (preferred)
    with timer.time_step("init:read_project_index", category="init"):
        read_file("PROJECT_INDEX.md")

    # Manual start/stop
    timer.start_step("test:run_suites", category="test")
    run_tests()
    timer.stop_step()

    # Pre-measured steps
    timer.add_step("code:implement_feature", "code", 120.5)

    # Analysis
    print(timer.total_duration())
    print(timer.duration_by_category())
    print(timer.category_percentages())
    print(format_breakdown(timer))

    # Persist
    timer.save()

    # Cross-session analysis
    history = load_timing_history()
    avgs = compute_step_averages(history)
    outliers = find_outliers(history)

Stdlib only. No external dependencies.
"""

import json
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_PATH = os.path.join(SCRIPT_DIR, "session_timings.jsonl")

VALID_CATEGORIES = ("init", "wrap", "test", "code", "doc", "other")


@dataclass
class StepTiming:
    """One timed step within a session."""
    name: str
    category: str
    duration_s: float

    def __post_init__(self):
        if self.category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category: {self.category!r}. "
                f"Must be one of {VALID_CATEGORIES}"
            )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StepTiming":
        return cls(
            name=d["name"],
            category=d["category"],
            duration_s=d["duration_s"],
        )


class SessionTimer:
    """Per-step timing engine for a single session."""

    def __init__(self, session_id: int):
        self.session_id = session_id
        self.steps: list[StepTiming] = []
        self._active_name: Optional[str] = None
        self._active_category: Optional[str] = None
        self._active_start: Optional[float] = None
        self._session_start = datetime.now(timezone.utc)

    def start_step(self, name: str, category: str) -> None:
        """Start timing a named step."""
        if self._active_name is not None:
            raise RuntimeError(
                f"Already timing {self._active_name!r}. Call stop_step() first."
            )
        # Validate category early
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category: {category!r}. Must be one of {VALID_CATEGORIES}"
            )
        self._active_name = name
        self._active_category = category
        self._active_start = time.monotonic()

    def stop_step(self) -> float:
        """Stop the active step. Returns elapsed seconds."""
        if self._active_name is None or self._active_start is None:
            raise RuntimeError("No active step. Call start_step() first.")
        elapsed = time.monotonic() - self._active_start
        self.steps.append(StepTiming(
            name=self._active_name,
            category=self._active_category,
            duration_s=round(elapsed, 3),
        ))
        self._active_name = None
        self._active_category = None
        self._active_start = None
        return elapsed

    @contextmanager
    def time_step(self, name: str, category: str):
        """Context manager for timing a step."""
        self.start_step(name, category)
        try:
            yield
        finally:
            self.stop_step()

    def add_step(self, name: str, category: str, duration_s: float) -> None:
        """Add a pre-measured step without using the timer."""
        self.steps.append(StepTiming(
            name=name,
            category=category,
            duration_s=round(duration_s, 3),
        ))

    def total_duration(self) -> float:
        """Total measured time across all steps."""
        return sum(s.duration_s for s in self.steps)

    def duration_by_category(self) -> dict[str, float]:
        """Total duration per category."""
        by_cat: dict[str, float] = {}
        for s in self.steps:
            by_cat[s.category] = by_cat.get(s.category, 0.0) + s.duration_s
        return by_cat

    def category_percentages(self) -> dict[str, float]:
        """Percentage of total time per category."""
        total = self.total_duration()
        if total == 0:
            return {}
        by_cat = self.duration_by_category()
        return {k: round(v / total * 100, 1) for k, v in by_cat.items()}

    def top_steps(self, n: int = 5) -> list[StepTiming]:
        """Top N steps by duration (descending)."""
        return sorted(self.steps, key=lambda s: s.duration_s, reverse=True)[:n]

    def save(self, path: str = DEFAULT_LOG_PATH) -> None:
        """Persist this session's timing data to JSONL."""
        entry = {
            "session_id": self.session_id,
            "timestamp": self._session_start.isoformat().replace("+00:00", "Z"),
            "total_duration_s": round(self.total_duration(), 2),
            "steps": [s.to_dict() for s in self.steps],
            "by_category": {
                k: round(v, 2)
                for k, v in self.duration_by_category().items()
            },
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")


def load_timing_history(path: str = DEFAULT_LOG_PATH) -> list[dict]:
    """Load all session timing entries from JSONL."""
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


def compute_step_averages(history: list[dict]) -> dict[str, float]:
    """Compute average duration per step name across sessions."""
    step_totals: dict[str, list[float]] = {}
    for entry in history:
        for step in entry.get("steps", []):
            name = step["name"]
            step_totals.setdefault(name, []).append(step["duration_s"])
    return {
        name: round(sum(durations) / len(durations), 2)
        for name, durations in step_totals.items()
    }


def compute_category_averages(history: list[dict]) -> dict[str, float]:
    """Compute average duration per category across sessions."""
    cat_totals: dict[str, list[float]] = {}
    for entry in history:
        # Accumulate per-session category totals
        session_cats: dict[str, float] = {}
        for step in entry.get("steps", []):
            cat = step["category"]
            session_cats[cat] = session_cats.get(cat, 0.0) + step["duration_s"]
        for cat, total in session_cats.items():
            cat_totals.setdefault(cat, []).append(total)
    return {
        cat: round(sum(totals) / len(totals), 2)
        for cat, totals in cat_totals.items()
    }


def find_outliers(
    history: list[dict],
    threshold: float = 2.0,
) -> list[dict]:
    """Find steps that exceed threshold * their historical average.

    Requires at least 2 sessions to establish a baseline.
    Only flags steps in the LAST session that deviate from the average
    of all PREVIOUS sessions.
    """
    if len(history) < 2:
        return []

    # Baseline = all sessions except last
    baseline = history[:-1]
    current = history[-1]
    avgs = compute_step_averages(baseline)

    outliers = []
    for step in current.get("steps", []):
        name = step["name"]
        if name not in avgs:
            continue
        avg = avgs[name]
        if avg <= 0:
            continue
        ratio = step["duration_s"] / avg
        if ratio >= threshold:
            outliers.append({
                "session_id": current.get("session_id"),
                "step_name": name,
                "duration_s": step["duration_s"],
                "average_s": avg,
                "ratio": round(ratio, 2),
            })
    return outliers


def format_breakdown(timer: "SessionTimer") -> str:
    """Human-readable breakdown of a session's timing."""
    if not timer.steps:
        return f"Session {timer.session_id}: No steps recorded."

    total = timer.total_duration()
    lines = [f"Session {timer.session_id} — {total:.1f}s total"]
    lines.append("-" * 50)

    # Group by category
    by_cat = timer.duration_by_category()
    pcts = timer.category_percentages()

    for cat in sorted(by_cat.keys(), key=lambda c: by_cat[c], reverse=True):
        cat_steps = [s for s in timer.steps if s.category == cat]
        lines.append(f"  {cat}: {by_cat[cat]:.1f}s ({pcts[cat]:.0f}%)")
        for s in sorted(cat_steps, key=lambda x: x.duration_s, reverse=True):
            lines.append(f"    {s.name}: {s.duration_s:.1f}s")

    return "\n".join(lines)


def format_category_bar(timer: "SessionTimer", width: int = 40) -> str:
    """Visual bar chart of category distribution."""
    if not timer.steps:
        return "No steps recorded."

    pcts = timer.category_percentages()
    by_cat = timer.duration_by_category()
    lines = []

    for cat in sorted(pcts.keys(), key=lambda c: pcts[c], reverse=True):
        bar_len = int(pcts[cat] / 100 * width)
        bar = "#" * bar_len
        lines.append(f"  {cat:6s} {bar} {pcts[cat]:.0f}% ({by_cat[cat]:.0f}s)")

    return "\n".join(lines)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage:")
        print("  python3 session_timer.py history    # Show all session timings")
        print("  python3 session_timer.py averages   # Step averages across sessions")
        print("  python3 session_timer.py outliers   # Detect timing anomalies")
        sys.exit(0)

    cmd = args[0]

    if cmd == "history":
        history = load_timing_history()
        if not history:
            print("No timing data recorded yet.")
            sys.exit(0)
        for entry in history[-5:]:  # Last 5 sessions
            sid = entry.get("session_id", "?")
            total = entry.get("total_duration_s", 0)
            cats = entry.get("by_category", {})
            cat_str = ", ".join(f"{k}={v:.0f}s" for k, v in cats.items())
            print(f"  S{sid}: {total:.0f}s total — {cat_str}")

    elif cmd == "averages":
        history = load_timing_history()
        if not history:
            print("No timing data recorded yet.")
            sys.exit(0)
        avgs = compute_step_averages(history)
        for name, avg in sorted(avgs.items(), key=lambda x: x[1], reverse=True):
            print(f"  {name}: {avg:.1f}s avg")

    elif cmd == "outliers":
        history = load_timing_history()
        if len(history) < 2:
            print("Need at least 2 sessions to detect outliers.")
            sys.exit(0)
        outliers = find_outliers(history)
        if not outliers:
            print("No outliers detected.")
        else:
            for o in outliers:
                print(
                    f"  S{o['session_id']} {o['step_name']}: "
                    f"{o['duration_s']:.0f}s (avg {o['average_s']:.0f}s, "
                    f"{o['ratio']:.1f}x)"
                )

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
