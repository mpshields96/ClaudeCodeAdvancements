#!/usr/bin/env python3
"""
phase3_coordinator.py — Desktop-side coordinator for 3-chat hivemind (Phase 3).

Manages 2 CLI workers (cli1 + cli2) with:
- Worker registration and status tracking
- Load-balanced task assignment (idle preference, then fewer-tasks)
- Inter-worker scope conflict detection
- Phase 3 validation metrics and gate evaluation
- State persistence across coordinator restarts

Usage:
    import phase3_coordinator as p3

    coord = p3.Coordinator()
    coord.register_worker("cli1")
    coord.register_worker("cli2")

    # Assign task to best available worker
    worker = coord.assign_task("write test_foo.py", files=["test_foo.py"])

    # Check for inter-worker conflicts
    conflicts = coord.check_inter_worker_conflicts()

    # Record session metrics
    coord.record_session_metrics(100, ["cli1", "cli2"], 5, 5, 0, 12.0)

    # Check Phase 3 gate
    gate = coord.check_phase3_gate()

Stdlib only. No external dependencies.
"""

import json
import os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STATE_PATH = os.path.join(SCRIPT_DIR, "phase3_state.json")
DEFAULT_METRICS_PATH = os.path.join(SCRIPT_DIR, "phase3_metrics.jsonl")
DEFAULT_QUEUE_PATH = os.path.join(SCRIPT_DIR, "cca_internal_queue.jsonl")


class Coordinator:
    """Manages 2 CLI workers for Phase 3 hivemind operation."""

    def __init__(
        self,
        state_path: str = DEFAULT_STATE_PATH,
        queue_path: str = DEFAULT_QUEUE_PATH,
    ):
        self.state_path = state_path
        self.queue_path = queue_path
        self.workers: dict[str, dict] = {}

    def register_worker(self, worker_id: str) -> None:
        """Register a worker. Idempotent — duplicate registration is a no-op."""
        if worker_id not in self.workers:
            self.workers[worker_id] = {
                "status": "idle",
                "task": None,
                "active_scope": [],
                "completed_count": 0,
            }

    def get_worker_status(self, worker_id: str) -> str:
        """Get worker's current status (idle/busy/done/error)."""
        if worker_id not in self.workers:
            raise ValueError(f"Worker {worker_id} not registered")
        return self.workers[worker_id]["status"]

    def get_worker_task(self, worker_id: str) -> str | None:
        """Get the current task description for a worker, or None if idle."""
        if worker_id not in self.workers:
            raise ValueError(f"Worker {worker_id} not registered")
        return self.workers[worker_id]["task"]

    def update_worker_status(
        self, worker_id: str, status: str, task: str | None = None
    ) -> None:
        """Update a worker's status and optionally its current task."""
        if worker_id not in self.workers:
            raise ValueError(f"Worker {worker_id} not registered")
        self.workers[worker_id]["status"] = status
        if task is not None:
            self.workers[worker_id]["task"] = task
        elif status == "idle":
            self.workers[worker_id]["task"] = None

    def assign_task(
        self,
        task_description: str,
        files: list[str] | None = None,
    ) -> str | None:
        """
        Assign a task to the best available worker.

        Selection logic:
        1. Only consider idle workers
        2. Exclude workers whose active_scope overlaps with the task's files
        3. Among remaining, pick the one with fewer completed tasks (load balance)

        Returns worker_id or None if no worker available.
        """
        files = files or []
        file_set = set(files)

        candidates = []
        for wid, wdata in self.workers.items():
            # Must be idle
            if wdata["status"] != "idle":
                continue

            # Check scope conflict
            if files and wdata.get("active_scope"):
                scope_set = set(wdata["active_scope"])
                # Direct file overlap
                if scope_set & file_set:
                    continue
                # Directory prefix overlap
                conflict = False
                for scope_item in wdata["active_scope"]:
                    if scope_item.endswith("/"):
                        for f in files:
                            if f.startswith(scope_item):
                                conflict = True
                                break
                    if conflict:
                        break
                if conflict:
                    continue

            candidates.append(wid)

        if not candidates:
            return None

        # Pick worker with fewest completed tasks (load balance)
        best = min(candidates, key=lambda w: self.workers[w].get("completed_count", 0))
        self.update_worker_status(best, "busy", task=task_description)
        return best

    def check_inter_worker_conflicts(self) -> list[dict]:
        """
        Check for scope overlaps between all registered workers.

        Returns list of conflict dicts: {"file": str, "workers": [str, str]}
        """
        worker_ids = list(self.workers.keys())
        conflicts = []

        for i, w1 in enumerate(worker_ids):
            for w2 in worker_ids[i + 1:]:
                scope1 = set(self.workers[w1].get("active_scope", []))
                scope2 = set(self.workers[w2].get("active_scope", []))

                # Direct file overlap
                overlap = scope1 & scope2
                for f in overlap:
                    conflicts.append({"file": f, "workers": [w1, w2]})

                # Directory prefix overlap
                for s1 in scope1:
                    if s1.endswith("/"):
                        for s2 in scope2:
                            if not s2.endswith("/") and s2.startswith(s1):
                                conflicts.append({"file": s2, "workers": [w1, w2]})
                for s2 in scope2:
                    if s2.endswith("/"):
                        for s1 in scope1:
                            if not s1.endswith("/") and s1.startswith(s2):
                                if {"file": s1, "workers": [w1, w2]} not in conflicts:
                                    conflicts.append({"file": s1, "workers": [w1, w2]})

        return conflicts

    def save_state(self) -> None:
        """Persist coordinator state to disk (atomic write)."""
        state = {
            "workers": self.workers,
            "saved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        tmp_path = self.state_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, self.state_path)

    def load_state(self) -> None:
        """Load coordinator state from disk. Missing/corrupt = clean state."""
        if not os.path.exists(self.state_path):
            self.workers = {}
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            self.workers = state.get("workers", {})
        except (json.JSONDecodeError, KeyError, TypeError):
            self.workers = {}

    def record_session_metrics(
        self,
        session_number: int,
        workers_used: list[str],
        tasks_assigned: int,
        tasks_completed: int,
        inter_worker_conflicts: int,
        coordination_overhead_pct: float,
        path: str = DEFAULT_METRICS_PATH,
    ) -> dict:
        """
        Record a Phase 3 session's metrics.

        Verdict logic:
        - FAIL: tasks_completed < tasks_assigned
        - PASS_WITH_WARNINGS: conflicts > 0 or overhead > 20%
        - PASS: clean session
        """
        if tasks_completed < tasks_assigned:
            verdict = "FAIL"
        elif inter_worker_conflicts > 0 or coordination_overhead_pct > 20.0:
            verdict = "PASS_WITH_WARNINGS"
        else:
            verdict = "PASS"

        entry = {
            "session": session_number,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "verdict": verdict,
            "workers_used": workers_used,
            "tasks_assigned": tasks_assigned,
            "tasks_completed": tasks_completed,
            "inter_worker_conflicts": inter_worker_conflicts,
            "coordination_overhead_pct": coordination_overhead_pct,
        }

        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

        return entry

    def check_phase3_gate(self, path: str = DEFAULT_METRICS_PATH) -> dict:
        """
        Check if Phase 3 gate criteria are met.

        Requires:
        - 3+ consecutive PASS/PASS_WITH_WARNINGS sessions
        - All qualifying sessions must have 2+ workers
        """
        entries = _load_metrics(path)
        if not entries:
            return {
                "ready": False,
                "consecutive_passes": 0,
                "total_sessions": 0,
                "reason": "no sessions recorded",
            }

        # Count consecutive passes from the end, requiring 2+ workers
        streak = 0
        all_have_2_workers = True
        for entry in reversed(entries):
            verdict = entry.get("verdict", "")
            workers = entry.get("workers_used", [])
            if verdict in ("PASS", "PASS_WITH_WARNINGS"):
                if len(workers) < 2:
                    all_have_2_workers = False
                streak += 1
            else:
                break

        # Check if all sessions in streak had 2+ workers
        if streak >= 3 and not all_have_2_workers:
            return {
                "ready": False,
                "consecutive_passes": streak,
                "total_sessions": len(entries),
                "reason": "need sessions with 2+ workers",
            }

        return {
            "ready": streak >= 3 and all_have_2_workers,
            "consecutive_passes": streak,
            "total_sessions": len(entries),
        }

    def format_briefing(self, path: str = DEFAULT_METRICS_PATH) -> str:
        """One-line briefing for /cca-init."""
        entries = _load_metrics(path)
        worker_count = len(self.workers)

        if not entries:
            workers_str = f" ({worker_count} workers registered)" if worker_count else ""
            return f"Phase 3: No Phase 3 sessions recorded{workers_str}."

        total = len(entries)
        gate = self.check_phase3_gate(path)
        streak = gate["consecutive_passes"]

        session_word = "session" if total == 1 else "sessions"
        parts = [f"Phase 3: {total} {session_word} ({streak} consecutive PASS)"]

        if worker_count:
            parts.append(f"{worker_count} workers")

        if gate["ready"]:
            parts.append("GATE READY")
        else:
            needed = 3 - streak
            parts.append(f"{needed} more PASS needed")

        return " — ".join(parts)

    def worker_summary(self) -> str:
        """Per-worker status summary."""
        if not self.workers:
            return "No workers registered."

        lines = []
        for wid, wdata in sorted(self.workers.items()):
            status = wdata["status"]
            task = wdata.get("task", "")
            task_str = f" ({task})" if task else ""
            completed = wdata.get("completed_count", 0)
            lines.append(f"  {wid}: {status}{task_str} [{completed} completed]")

        return "Workers:\n" + "\n".join(lines)


def _load_metrics(path: str) -> list[dict]:
    """Load Phase 3 metrics log."""
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
