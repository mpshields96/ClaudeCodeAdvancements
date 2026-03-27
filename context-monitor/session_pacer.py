#!/usr/bin/env python3
"""
session_pacer.py — Session pacing for long autonomous /cca-auto runs.

Combines context health, elapsed time, and task count into a single
"should I keep working or wrap up?" decision. Designed for 2-3 hour
autonomous sessions where Claude needs to self-pace.

Decision outputs:
  CONTINUE  — keep working, start next task
  WRAP_SOON — finish current task, then wrap (approaching limit)
  WRAP_NOW  — stop immediately and run /cca-wrap

Triggers for WRAP_NOW (any one):
  - Context zone is red or critical (from auto_wrap.py / meter.py)
  - Elapsed time exceeds max_duration_minutes
  - Compaction count >= 2

Triggers for WRAP_SOON:
  - Within wrap_buffer_minutes of max duration
  - Context zone is yellow AND time > 2/3 of max duration

Usage as library:
    from session_pacer import SessionPacer
    pacer = SessionPacer(max_duration_minutes=120)
    pacer.start_task("MT-17 Phase 3")
    # ... do work ...
    pacer.complete_task("MT-17 Phase 3", commit_hash="abc1234")
    decision = pacer.check()
    if decision.should_wrap:
        # trigger /cca-wrap

Usage as CLI:
    python3 session_pacer.py check                    # Check pacing decision
    python3 session_pacer.py check --json             # JSON output
    python3 session_pacer.py check --wrap-at 80       # Override wrap threshold to 80%
    python3 session_pacer.py start "Task name"        # Record task start
    python3 session_pacer.py complete "Task" --commit abc1234
    python3 session_pacer.py status                   # Show session status
    python3 session_pacer.py reset                    # Reset for new session

Wrap threshold priority (highest wins):
    1. --wrap-at CLI flag
    2. CCA_WRAP_THRESHOLD_PCT env var
    3. Default: 70%

When wrap_threshold_pct is set above the default red zone (70%), the pacer
will NOT trigger wrap_now until context exceeds that threshold. This ensures
user's explicit "wrap at X%" directive always wins over zone-based defaults.

Stdlib only. No external dependencies.
"""

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class PaceDecision:
    """Result of a pacing check."""
    action: str = "continue"  # continue, wrap_soon, wrap_now
    reason: str = ""
    should_wrap: bool = False  # True only for wrap_now
    tasks_completed: int = 0
    elapsed_minutes: float = 0.0
    context_zone: str = "unknown"
    context_pct: float = 0.0
    remaining_minutes: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TaskRecord:
    """A single task tracked during the session."""
    name: str
    started_at: str  # ISO 8601
    completed_at: Optional[str] = None
    commit_hash: Optional[str] = None


# ── Session State ────────────────────────────────────────────────────────────


_DEFAULT_STATE_PATH = str(Path.home() / ".cca-session-pace.json")
_DEFAULT_MAX_DURATION = 120  # 2 hours


class SessionState:
    """Persistent session state: tasks, timing, config."""

    def __init__(
        self,
        state_path: str = None,
        max_duration_minutes: int = _DEFAULT_MAX_DURATION,
    ):
        self.state_path = state_path or _DEFAULT_STATE_PATH
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.max_duration_minutes = max_duration_minutes
        self.tasks: List[TaskRecord] = []

    def add_task(self, name: str):
        self.tasks.append(TaskRecord(
            name=name,
            started_at=datetime.now(timezone.utc).isoformat(),
        ))

    def complete_task(self, name: str, commit_hash: str = None):
        for t in self.tasks:
            if t.name == name and t.completed_at is None:
                t.completed_at = datetime.now(timezone.utc).isoformat()
                t.commit_hash = commit_hash
                return

    def completed_count(self) -> int:
        return sum(1 for t in self.tasks if t.completed_at is not None)

    def elapsed_minutes(self) -> float:
        start = datetime.fromisoformat(self.started_at)
        now = datetime.now(timezone.utc)
        return (now - start).total_seconds() / 60.0

    def save(self):
        data = {
            "started_at": self.started_at,
            "max_duration_minutes": self.max_duration_minutes,
            "tasks": [asdict(t) for t in self.tasks],
        }
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.state_path)

    @classmethod
    def load(cls, state_path: str) -> "SessionState":
        state = cls(state_path=state_path)
        if not os.path.exists(state_path):
            return state
        try:
            with open(state_path) as f:
                data = json.load(f)
            state.started_at = data.get("started_at", state.started_at)
            state.max_duration_minutes = data.get(
                "max_duration_minutes", _DEFAULT_MAX_DURATION
            )
            for t in data.get("tasks", []):
                state.tasks.append(TaskRecord(
                    name=t["name"],
                    started_at=t["started_at"],
                    completed_at=t.get("completed_at"),
                    commit_hash=t.get("commit_hash"),
                ))
        except (json.JSONDecodeError, OSError, KeyError):
            pass
        return state


# ── Session Pacer ────────────────────────────────────────────────────────────


_DEFAULT_CONTEXT_STATE = str(Path.home() / ".claude-context-health.json")
_DEFAULT_WRAP_STATE = str(Path.home() / ".cca-wrap-state.json")
_DEFAULT_WRAP_BUFFER = 15  # minutes before max duration to trigger wrap_soon
_DEFAULT_WRAP_THRESHOLD_PCT = 70  # context % to trigger wrap_now
_DEFAULT_WRAP_SOON_PCT = 50  # context % to trigger wrap_soon (with time condition)


class SessionPacer:
    """
    Combines context health + time + task count into pacing decisions.

    Check between tasks to know whether to continue, prepare to wrap,
    or wrap immediately.
    """

    def __init__(
        self,
        state_path: str = None,
        context_state_path: str = None,
        wrap_state_path: str = None,
        max_duration_minutes: int = _DEFAULT_MAX_DURATION,
        wrap_buffer_minutes: int = _DEFAULT_WRAP_BUFFER,
        wrap_threshold_pct: float = None,
    ):
        self.context_state_path = context_state_path or _DEFAULT_CONTEXT_STATE
        self.wrap_state_path = wrap_state_path or _DEFAULT_WRAP_STATE
        self.wrap_buffer_minutes = wrap_buffer_minutes

        # Resolve wrap threshold: CLI arg > env var > default
        # This ensures user's explicit "wrap at X%" always wins.
        if wrap_threshold_pct is not None:
            self.wrap_threshold_pct = float(wrap_threshold_pct)
        else:
            env_val = os.environ.get("CCA_WRAP_THRESHOLD_PCT")
            if env_val is not None:
                self.wrap_threshold_pct = float(env_val)
            else:
                self.wrap_threshold_pct = _DEFAULT_WRAP_THRESHOLD_PCT

        # wrap_soon triggers at a proportional point below the wrap threshold
        # (default: 10% below wrap_threshold, floored at 50%)
        self.wrap_soon_pct = max(_DEFAULT_WRAP_SOON_PCT, self.wrap_threshold_pct - 10)

        # Load or create session state
        sp = state_path or _DEFAULT_STATE_PATH
        if os.path.exists(sp):
            self.state = SessionState.load(sp)
            # Only override loaded max_duration if caller explicitly specified
            # (not using default). This preserves max_duration set by reset/start.
            if max_duration_minutes != _DEFAULT_MAX_DURATION:
                self.state.max_duration_minutes = max_duration_minutes
            # Sync pacer's max_duration from persisted state
            self.max_duration_minutes = self.state.max_duration_minutes
        else:
            self.max_duration_minutes = max_duration_minutes
            self.state = SessionState(
                state_path=sp,
                max_duration_minutes=max_duration_minutes,
            )

    def _read_context_health(self) -> dict:
        if not os.path.exists(self.context_state_path):
            return {}
        try:
            with open(self.context_state_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _read_compaction_count(self) -> int:
        if not os.path.exists(self.wrap_state_path):
            return 0
        try:
            with open(self.wrap_state_path) as f:
                data = json.load(f)
            return data.get("compaction_count", 0)
        except (json.JSONDecodeError, OSError):
            return 0

    def start_task(self, name: str):
        self.state.add_task(name)
        self.state.save()

    def complete_task(self, name: str, commit_hash: str = None):
        self.state.complete_task(name, commit_hash)
        self.state.save()

    def save(self):
        self.state.save()

    def check(self) -> PaceDecision:
        """
        Check all pacing signals and return a decision.

        Uses configurable wrap_threshold_pct instead of hardcoded zone names.
        This ensures user's explicit "wrap at X%" always wins over defaults.

        Priority order:
        1. Context >= wrap_threshold_pct → WRAP_NOW
        2. Time exceeded → WRAP_NOW
        3. Compaction count >= 2 → WRAP_NOW
        4. Time approaching limit → WRAP_SOON
        5. Context >= wrap_soon_pct + past 2/3 duration → WRAP_SOON
        6. Otherwise → CONTINUE
        """
        ctx = self._read_context_health()
        zone = ctx.get("zone", "unknown")
        pct = ctx.get("pct", 0.0)
        compactions = self._read_compaction_count()

        elapsed = self.state.elapsed_minutes()
        remaining = self.max_duration_minutes - elapsed

        decision = PaceDecision(
            tasks_completed=self.state.completed_count(),
            elapsed_minutes=round(elapsed, 1),
            context_zone=zone,
            context_pct=pct,
            remaining_minutes=round(max(0, remaining), 1),
        )

        # ── WRAP_NOW triggers ──

        # 1. Context at or above wrap threshold (percentage-based, not zone-based)
        if pct >= self.wrap_threshold_pct:
            decision.action = "wrap_now"
            decision.should_wrap = True
            decision.reason = (
                f"Context at {pct:.0f}% (wrap threshold: {self.wrap_threshold_pct:.0f}%). "
                f"Wrap immediately to preserve quality."
            )
            return decision

        # 2. Time exceeded
        if elapsed >= self.max_duration_minutes:
            decision.action = "wrap_now"
            decision.should_wrap = True
            decision.reason = (
                f"Max duration exceeded ({elapsed:.0f} min / "
                f"{self.max_duration_minutes} min limit). "
                f"Wrap to save progress."
            )
            return decision

        # 3. Too many compactions
        if compactions >= 2:
            decision.action = "wrap_now"
            decision.should_wrap = True
            decision.reason = (
                f"Context compacted {compactions} times. "
                f"Quality at risk — wrap and start fresh."
            )
            return decision

        # ── WRAP_SOON triggers ──

        # 4. Approaching time limit
        if 0 < remaining <= self.wrap_buffer_minutes:
            decision.action = "wrap_soon"
            decision.reason = (
                f"{remaining:.0f} min remaining of {self.max_duration_minutes} min. "
                f"Finish current task, then wrap."
            )
            return decision

        # 5. Context approaching threshold + past 2/3 of duration
        two_thirds = self.max_duration_minutes * 2 / 3
        if pct >= self.wrap_soon_pct and elapsed > two_thirds:
            decision.action = "wrap_soon"
            decision.reason = (
                f"Context at {pct:.0f}% (warn threshold: {self.wrap_soon_pct:.0f}%) "
                f"and {elapsed:.0f} min elapsed "
                f"(past 2/3 of {self.max_duration_minutes} min). "
                f"Finish current task, then wrap."
            )
            return decision

        # ── CONTINUE ──
        decision.action = "continue"
        return decision


# ── CLI ──────────────────────────────────────────────────────────────────────


def cli_main(args: list = None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args:
        print(
            "Usage: python3 session_pacer.py "
            "[check|start <name>|complete <name>|status|reset] [options]\n"
            "\n"
            "Options:\n"
            "  --state PATH          Session state file\n"
            "  --context-state PATH  Context health file\n"
            "  --wrap-state PATH     Wrap state file\n"
            "  --max-duration MIN    Max session duration (default: 120)\n"
            "  --wrap-at PCT         Context % to trigger wrap (default: 70, env: CCA_WRAP_THRESHOLD_PCT)\n"
            "  --json                Output as JSON (check command)\n"
            "  --commit HASH         Commit hash (complete command)"
        )
        return

    cmd = args[0]

    # Parse flags
    state_path = None
    context_state_path = None
    wrap_state_path = None
    max_duration = _DEFAULT_MAX_DURATION
    wrap_at = None
    json_output = False
    commit_hash = None
    positional = []

    i = 1
    while i < len(args):
        if args[i] == "--state" and i + 1 < len(args):
            state_path = args[i + 1]
            i += 2
        elif args[i] == "--context-state" and i + 1 < len(args):
            context_state_path = args[i + 1]
            i += 2
        elif args[i] == "--wrap-state" and i + 1 < len(args):
            wrap_state_path = args[i + 1]
            i += 2
        elif args[i] == "--max-duration" and i + 1 < len(args):
            max_duration = int(args[i + 1])
            i += 2
        elif args[i] == "--wrap-at" and i + 1 < len(args):
            wrap_at = float(args[i + 1])
            i += 2
        elif args[i] == "--json":
            json_output = True
            i += 1
        elif args[i] == "--commit" and i + 1 < len(args):
            commit_hash = args[i + 1]
            i += 2
        else:
            positional.append(args[i])
            i += 1

    pacer = SessionPacer(
        state_path=state_path,
        context_state_path=context_state_path,
        wrap_state_path=wrap_state_path,
        max_duration_minutes=max_duration,
        wrap_threshold_pct=wrap_at,
    )

    if cmd == "check":
        decision = pacer.check()
        if json_output:
            print(json.dumps(decision.to_dict(), indent=2))
        else:
            label = decision.action.upper().replace("_", " ")
            if decision.should_wrap:
                print(f"{label}: {decision.reason}")
            else:
                print(
                    f"{label} | "
                    f"Tasks: {decision.tasks_completed} | "
                    f"Elapsed: {decision.elapsed_minutes:.0f}m | "
                    f"Remaining: {decision.remaining_minutes:.0f}m | "
                    f"Context: {decision.context_zone} ({decision.context_pct:.0f}%)"
                )
                if decision.action == "wrap_soon":
                    print(f"  Note: {decision.reason}")

    elif cmd == "start":
        if not positional:
            print("Usage: session_pacer.py start <task_name>")
            return
        name = " ".join(positional)
        pacer.start_task(name)
        print(f"Started: {name}")

    elif cmd == "complete":
        if not positional:
            print("Usage: session_pacer.py complete <task_name> [--commit HASH]")
            return
        name = " ".join(positional)
        pacer.complete_task(name, commit_hash)
        print(f"Completed: {name}" + (f" ({commit_hash})" if commit_hash else ""))

    elif cmd == "status":
        elapsed = pacer.state.elapsed_minutes()
        remaining = pacer.max_duration_minutes - elapsed
        completed = pacer.state.completed_count()
        total = len(pacer.state.tasks)
        ctx = pacer._read_context_health()

        print(f"Session started: {pacer.state.started_at}")
        print(f"Elapsed: {elapsed:.0f}m / {pacer.max_duration_minutes}m "
              f"({remaining:.0f}m remaining)")
        print(f"Tasks: {completed}/{total} completed")
        print(f"Context: {ctx.get('zone', 'unknown')} ({ctx.get('pct', 0):.0f}%)")
        print(f"Wrap threshold: {pacer.wrap_threshold_pct:.0f}% "
              f"(warn at {pacer.wrap_soon_pct:.0f}%)")
        if pacer.state.tasks:
            print("\nTask log:")
            for t in pacer.state.tasks:
                status = "DONE" if t.completed_at else "IN PROGRESS"
                commit = f" [{t.commit_hash}]" if t.commit_hash else ""
                print(f"  [{status}] {t.name}{commit}")

    elif cmd == "reset":
        pacer.state = SessionState(
            state_path=pacer.state.state_path,
            max_duration_minutes=pacer.max_duration_minutes,
        )
        pacer.state.save()
        print("Reset: New session started.")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    cli_main()
