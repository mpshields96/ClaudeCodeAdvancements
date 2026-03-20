"""
hivemind_dashboard.py — Combined Phase 1 hivemind status reporter.

Reads from:
  - hivemind_sessions.jsonl  (session validator data via hivemind_session_validator)
  - hivemind_metrics.jsonl   (metrics tracker data via HivemindMetrics)

API:
    phase1_report(sessions_path, metrics_path) -> dict
        All Phase 1 gate metrics combined from both sources.

    format_report(sessions_path, metrics_path) -> str
        Multi-line human-readable Phase 1 status report.

Stdlib only. No external dependencies.
"""

import os

import hivemind_session_validator as hsv
from hivemind_metrics import HivemindMetrics

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SESSIONS_PATH = os.path.join(SCRIPT_DIR, "hivemind_sessions.jsonl")
DEFAULT_METRICS_PATH = os.path.expanduser("~/.claude/projects/hivemind_metrics.jsonl")


def phase1_report(
    sessions_path: str = DEFAULT_SESSIONS_PATH,
    metrics_path: str = DEFAULT_METRICS_PATH,
) -> dict:
    """Return combined Phase 1 gate metrics dict.

    Keys from session validator:
        consecutive_passes    int   — consecutive PASS streak
        total_sessions        int   — total recorded sessions
        total_passes          int   — sessions with PASS or PASS_WITH_WARNINGS
        total_fails           int   — sessions with FAIL
        gate_ready            bool  — True when consecutive_passes >= 3

    Keys from metrics tracker:
        coordination_failures     int   — total across all metric sessions
        task_completion_rate      float — avg task_completions per metric session
        worker_regressions        int   — total across all metric sessions
        avg_overhead_ratio        float — mean overhead ratio
        failure_rate              float — coordination_failures / metric_sessions
        regression_rate           float — regressions / task_completions
    """
    # --- session validator side ---
    gate = hsv.check_phase1_gate(path=sessions_path)

    # --- metrics tracker side ---
    metrics = HivemindMetrics(path=metrics_path)
    stats = metrics.get_stats()

    # task_completion_rate: avg tasks per metric-recorded session
    n_metric = stats["total_sessions"]
    total_completions = stats["total_task_completions"]
    task_completion_rate = (
        total_completions / n_metric if n_metric > 0 else 0.0
    )

    return {
        # from session validator
        "consecutive_passes": gate["consecutive_passes"],
        "total_sessions": gate["total_sessions"],
        "total_passes": gate["total_passes"],
        "total_fails": gate["total_fails"],
        "gate_ready": gate["ready"],
        # from metrics tracker
        "coordination_failures": stats["total_coordination_failures"],
        "task_completion_rate": task_completion_rate,
        "worker_regressions": stats["total_worker_regressions"],
        "avg_overhead_ratio": stats["avg_overhead_ratio"],
        "failure_rate": stats["failure_rate"],
        "regression_rate": stats["regression_rate"],
    }


def format_report(
    sessions_path: str = DEFAULT_SESSIONS_PATH,
    metrics_path: str = DEFAULT_METRICS_PATH,
) -> str:
    """Return a multi-line formatted Phase 1 status report."""
    r = phase1_report(sessions_path, metrics_path)

    gate_status = "READY" if r["gate_ready"] else (
        f"{3 - r['consecutive_passes']} more consecutive PASS needed"
    )

    lines = [
        "── Hivemind Phase 1 Dashboard ──────────────────────────",
        f"Gate status        : {gate_status}",
        f"Consecutive passes : {r['consecutive_passes']} / 3 required",
        f"Total sessions     : {r['total_sessions']}  "
        f"(passes: {r['total_passes']}, fails: {r['total_fails']})",
        "",
        "── Coordination Metrics ────────────────────────────────",
        f"Coordination failures  : {r['coordination_failures']}",
        f"Task completion rate   : {r['task_completion_rate']:.2f} tasks/session",
        f"Worker regressions     : {r['worker_regressions']}",
        f"Avg overhead ratio     : {r['avg_overhead_ratio'] * 100:.1f}%",
        f"Failure rate           : {r['failure_rate']:.3f}",
        f"Regression rate        : {r['regression_rate']:.3f}",
    ]
    return "\n".join(lines)
