#!/usr/bin/env python3
"""
init_benchmarker.py — Compare slim init trials against full init baselines.

After both Trial A and Trial B complete, run this to determine if slim init
should become the permanent default for /cca-init.

Criteria for approval (ALL must be true):
  1. Both trials have faster init than baseline average
  2. Zero quality issues in both trials
  3. At least 2 trials recorded

CLI:
    python3 init_benchmarker.py record S99a slim 4.0 6 77 500 0 45
    python3 init_benchmarker.py baseline     # Seed S95-S98 baseline data
    python3 init_benchmarker.py compare      # Compare trials vs baseline
    python3 init_benchmarker.py verdict      # Final recommendation

Stdlib only. No external dependencies.
"""

import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

from session_id import normalize as normalize_session_id

CCA_DIR = Path.home() / "Projects/ClaudeCodeAdvancements"
BENCH_FILE = CCA_DIR / ".cca-init-benchmarks.jsonl"


@dataclass
class SessionMetrics:
    """Metrics for a single session's init + work output."""
    session_id: str
    init_type: str  # "full" or "slim"
    time_to_first_commit_min: float
    total_commits: int
    new_tests: int
    loc_shipped: int
    quality_issues: int
    duration_min: float

    def __post_init__(self):
        # Normalize session_id to canonical "S{number}" format
        # Handles suffixed IDs like "S99a" gracefully
        try:
            self.session_id = normalize_session_id(self.session_id)
        except (ValueError, TypeError):
            pass  # Keep original if not parseable (e.g. custom labels)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SessionMetrics":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def save_metrics(m: SessionMetrics, bench_file: Path = BENCH_FILE) -> None:
    """Save session metrics to JSONL."""
    bench_file.parent.mkdir(parents=True, exist_ok=True)
    with open(bench_file, "a") as f:
        f.write(json.dumps(m.to_dict()) + "\n")


def load_metrics(
    init_type: Optional[str] = None,
    bench_file: Path = BENCH_FILE,
) -> List[SessionMetrics]:
    """Load session metrics, optionally filtered by init type."""
    if not bench_file.exists():
        return []
    results = []
    with open(bench_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                m = SessionMetrics.from_dict(d)
                if init_type is None or m.init_type == init_type:
                    results.append(m)
            except (json.JSONDecodeError, TypeError):
                continue
    return results


def compute_averages(sessions: List[SessionMetrics]) -> dict:
    """Compute average metrics across sessions."""
    if not sessions:
        return {
            "time_to_first_commit_min": 0,
            "total_commits": 0,
            "new_tests": 0,
            "loc_shipped": 0,
            "quality_issues": 0,
            "duration_min": 0,
        }
    n = len(sessions)
    return {
        "time_to_first_commit_min": sum(s.time_to_first_commit_min for s in sessions) / n,
        "total_commits": sum(s.total_commits for s in sessions) / n,
        "new_tests": sum(s.new_tests for s in sessions) / n,
        "loc_shipped": sum(s.loc_shipped for s in sessions) / n,
        "quality_issues": sum(s.quality_issues for s in sessions) / n,
        "duration_min": sum(s.duration_min for s in sessions) / n,
    }


def compare_trial(trial: SessionMetrics, baseline_avg: dict) -> dict:
    """Compare a single trial against baseline averages."""
    base_init = baseline_avg.get("time_to_first_commit_min", 0)
    init_faster = trial.time_to_first_commit_min < base_init if base_init > 0 else False
    speedup = ((base_init - trial.time_to_first_commit_min) / base_init * 100) if base_init > 0 else 0

    base_commits = baseline_avg.get("total_commits", 0)
    commits_ratio = trial.total_commits / base_commits if base_commits > 0 else 0

    base_tests = baseline_avg.get("new_tests", 0)
    tests_ratio = trial.new_tests / base_tests if base_tests > 0 else 0

    return {
        "session_id": trial.session_id,
        "init_faster": init_faster,
        "init_speedup_pct": round(speedup, 1),
        "has_quality_issues": trial.quality_issues > 0,
        "commits_ratio": round(commits_ratio, 2),
        "tests_ratio": round(tests_ratio, 2),
        "time_to_first_commit_min": trial.time_to_first_commit_min,
        "total_commits": trial.total_commits,
        "new_tests": trial.new_tests,
        "quality_issues": trial.quality_issues,
    }


def compute_verdict(comparisons: List[dict]) -> dict:
    """Determine if slim init should become default."""
    if len(comparisons) < 2:
        return {
            "approved": False,
            "recommendation": f"Need at least 2 trials, have {len(comparisons)}. Run more trials.",
            "comparisons": comparisons,
        }

    all_faster = all(c["init_faster"] for c in comparisons)
    any_quality_issues = any(c["has_quality_issues"] for c in comparisons)

    approved = all_faster and not any_quality_issues

    if approved:
        avg_speedup = sum(c["init_speedup_pct"] for c in comparisons) / len(comparisons)
        recommendation = (
            f"APPROVED: Slim init is {avg_speedup:.0f}% faster with zero quality issues "
            f"across {len(comparisons)} trials. Wire as default in /cca-init."
        )
    elif any_quality_issues:
        recommendation = (
            "REJECTED: Quality issues detected in one or more trials. "
            "Slim init skips too much context. Keep full init as default."
        )
    else:
        recommendation = (
            "REJECTED: Not all trials showed faster init time. "
            "Slim init may not be consistently better."
        )

    return {
        "approved": approved,
        "recommendation": recommendation,
        "comparisons": comparisons,
    }


def format_comparison_table(baseline_avg: dict, trials: List[dict]) -> str:
    """Format a comparison table for human review."""
    if not baseline_avg or not trials:
        return "No data available for comparison."

    lines = [
        f"{'Metric':<30} {'Baseline (avg)':<15} " + " ".join(f"{t.get('session_id', '?'):<12}" for t in trials),
        "-" * (45 + 13 * len(trials)),
    ]

    metrics = [
        ("Init time (min)", "time_to_first_commit_min"),
        ("Total commits", "total_commits"),
        ("New tests", "new_tests"),
        ("Quality issues", "quality_issues"),
    ]

    for label, key in metrics:
        base_val = baseline_avg.get(key, "?")
        if isinstance(base_val, float):
            base_str = f"{base_val:.1f}"
        else:
            base_str = str(base_val)
        trial_vals = " ".join(f"{str(t.get(key, '?')):<12}" for t in trials)
        lines.append(f"{label:<30} {base_str:<15} {trial_vals}")

    return "\n".join(lines)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage:")
        print("  python3 init_benchmarker.py record <session> <type> <init_min> <commits> <tests> <loc> <issues> <duration>")
        print("  python3 init_benchmarker.py baseline    # Seed S95-S98 data")
        print("  python3 init_benchmarker.py compare     # Show comparison table")
        print("  python3 init_benchmarker.py verdict     # Final recommendation")
        sys.exit(0)

    cmd = args[0]

    if cmd == "record":
        if len(args) < 9:
            print("Usage: init_benchmarker.py record <session> <type> <init_min> <commits> <tests> <loc> <issues> <duration>")
            sys.exit(1)
        m = SessionMetrics(
            args[1], args[2], float(args[3]), int(args[4]),
            int(args[5]), int(args[6]), int(args[7]), float(args[8]),
        )
        save_metrics(m)
        print(f"Recorded: {m.session_id} ({m.init_type})")

    elif cmd == "baseline":
        # Seed S95-S98 baseline data (from INIT_TRIAL_INSTRUCTIONS.md averages)
        baselines = [
            SessionMetrics("S95", "full", 12.0, 6, 120, 350, 0, 50),
            SessionMetrics("S96", "full", 14.0, 8, 200, 600, 0, 60),
            SessionMetrics("S97", "full", 13.0, 5, 100, 300, 0, 55),
            SessionMetrics("S98", "full", 15.0, 7, 180, 500, 0, 58),
        ]
        for b in baselines:
            save_metrics(b)
        print(f"Seeded {len(baselines)} baseline sessions (S95-S98)")

    elif cmd == "compare":
        full = load_metrics(init_type="full")
        slim = load_metrics(init_type="slim")
        if not full:
            print("No baseline data. Run: python3 init_benchmarker.py baseline")
            sys.exit(1)
        baseline_avg = compute_averages(full)
        comparisons = [compare_trial(s, baseline_avg) for s in slim]
        trial_dicts = [c for c in comparisons]
        print(format_comparison_table(baseline_avg, trial_dicts))

    elif cmd == "verdict":
        full = load_metrics(init_type="full")
        slim = load_metrics(init_type="slim")
        if not full or not slim:
            print("Need both baseline and trial data. Run baseline + record first.")
            sys.exit(1)
        baseline_avg = compute_averages(full)
        comparisons = [compare_trial(s, baseline_avg) for s in slim]
        verdict = compute_verdict(comparisons)
        print(verdict["recommendation"])

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
