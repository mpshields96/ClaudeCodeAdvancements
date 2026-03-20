"""hivemind_metrics.py — Phase 1 hivemind validation metrics tracker.

Tracks sessions_completed, coordination_failures, task_completions,
worker_regressions, and overhead_ratio. Persists to JSONL.

API:
    record_session(session_id, sessions_completed, coordination_failures,
                   task_completions, worker_regressions, overhead_ratio)
    get_stats() -> dict
    format_for_init() -> str  (one-line briefing for /cca-init)
"""
import json
import os
from datetime import date
from typing import Optional


DEFAULT_PATH = os.path.expanduser(
    "~/.claude/projects/hivemind_metrics.jsonl"
)


class HivemindMetrics:
    """Persistent tracker for hivemind session validation metrics."""

    def __init__(self, path: str = DEFAULT_PATH) -> None:
        self.path = path

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record_session(
        self,
        session_id: str,
        sessions_completed: int,
        coordination_failures: int,
        task_completions: int,
        worker_regressions: int,
        overhead_ratio: float,
        queue_throughput: Optional[int] = None,
    ) -> None:
        """Append one session record to the JSONL file."""
        entry = {
            "session_id": session_id,
            "date": date.today().isoformat(),
            "sessions_completed": sessions_completed,
            "coordination_failures": coordination_failures,
            "task_completions": task_completions,
            "worker_regressions": worker_regressions,
            "overhead_ratio": overhead_ratio,
            "queue_throughput": queue_throughput,
        }
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def _load(self) -> list[dict]:
        """Return all records from the JSONL file, oldest first."""
        if not os.path.exists(self.path):
            return []
        records = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records

    def get_stats(self) -> dict:
        """Return aggregate stats across all recorded sessions.

        Keys:
            total_sessions          int
            total_task_completions  int
            total_coordination_failures int
            total_worker_regressions int
            avg_overhead_ratio      float
            failure_rate            float  (failures / sessions, 0.0 if no sessions)
            regression_rate         float  (regressions / task_completions, 0.0 if none)
            avg_queue_throughput    float  (Phase 2: avg msgs/session, 0.0 if no data)
            max_queue_throughput    int    (Phase 2: highest msgs in a single session)
            phase2_throughput_met   bool   (Phase 2: any session >= 50 msgs)
            last_session            dict | None
        """
        records = self._load()

        if not records:
            return {
                "total_sessions": 0,
                "total_task_completions": 0,
                "total_coordination_failures": 0,
                "total_worker_regressions": 0,
                "avg_overhead_ratio": 0.0,
                "failure_rate": 0.0,
                "regression_rate": 0.0,
                "avg_queue_throughput": 0.0,
                "max_queue_throughput": 0,
                "phase2_throughput_met": False,
                "last_session": None,
            }

        total_sessions = len(records)
        total_task_completions = sum(r["task_completions"] for r in records)
        total_coordination_failures = sum(r["coordination_failures"] for r in records)
        total_worker_regressions = sum(r["worker_regressions"] for r in records)
        avg_overhead_ratio = sum(r["overhead_ratio"] for r in records) / total_sessions

        failure_rate = (
            total_coordination_failures / total_sessions
            if total_sessions > 0
            else 0.0
        )
        regression_rate = (
            total_worker_regressions / total_task_completions
            if total_task_completions > 0
            else 0.0
        )

        # Queue throughput (Phase 2 metric)
        throughputs = [
            r["queue_throughput"] for r in records
            if r.get("queue_throughput") is not None
        ]
        avg_queue_throughput = (
            sum(throughputs) / len(throughputs) if throughputs else 0.0
        )
        max_queue_throughput = max(throughputs) if throughputs else 0
        phase2_throughput_met = max_queue_throughput >= 50

        return {
            "total_sessions": total_sessions,
            "total_task_completions": total_task_completions,
            "total_coordination_failures": total_coordination_failures,
            "total_worker_regressions": total_worker_regressions,
            "avg_overhead_ratio": avg_overhead_ratio,
            "failure_rate": failure_rate,
            "regression_rate": regression_rate,
            "avg_queue_throughput": avg_queue_throughput,
            "max_queue_throughput": max_queue_throughput,
            "phase2_throughput_met": phase2_throughput_met,
            "last_session": records[-1],
        }

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def format_for_init(self) -> str:
        """Return a one-line briefing suitable for /cca-init output."""
        stats = self.get_stats()
        n = stats["total_sessions"]
        tasks = stats["total_task_completions"]
        failures = stats["total_coordination_failures"]
        overhead_pct = stats["avg_overhead_ratio"] * 100
        max_throughput = stats["max_queue_throughput"]

        session_word = "session" if n == 1 else "sessions"
        task_word = "task" if tasks == 1 else "tasks"
        failure_word = "failure" if failures == 1 else "failures"

        base = (
            f"Hivemind: {n} {session_word}, {tasks} {task_word}, "
            f"{failures} {failure_word}, overhead {overhead_pct:.1f}%"
        )
        if max_throughput > 0:
            met = "MET" if stats["phase2_throughput_met"] else "NOT MET"
            base += f", queue peak {max_throughput} msgs ({met})"
        return base
