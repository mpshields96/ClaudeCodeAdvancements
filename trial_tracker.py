"""
trial_tracker.py — Record and query supervised trial results for MT validation gates.

MT-22 requires 3/3 supervised 1-hour trials to pass before autonomous approval.
This generalizes to any MT needing N/N validation trials.

Storage: JSONL at .cca-trial-results.jsonl (append-only, local-first).

CLI:
    python3 trial_tracker.py record MT-22 S99 pass --commits 5 --tests 30
    python3 trial_tracker.py status MT-22
    python3 trial_tracker.py gate MT-22 --required 3

Stdlib only. No external dependencies.
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

CCA_DIR = Path.home() / "Projects/ClaudeCodeAdvancements"
TRIAL_FILE = CCA_DIR / ".cca-trial-results.jsonl"


@dataclass
class TrialRecord:
    """A single trial result for an MT validation gate."""

    mt_id: str
    session_id: str
    result: str  # "pass" or "fail"
    timestamp: str = ""
    commits: int = 0
    tests_added: int = 0
    coordination_failures: int = 0
    test_regressions: int = 0
    duration_secs: int = 0
    notes: str = ""

    def __post_init__(self):
        if not self.mt_id:
            raise ValueError("mt_id cannot be empty")
        if not self.session_id:
            raise ValueError("session_id cannot be empty")
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TrialRecord":
        return cls(**d)


def record_trial(rec: TrialRecord, trial_file: Path = TRIAL_FILE) -> None:
    """Append a trial record to the JSONL file."""
    trial_file.parent.mkdir(parents=True, exist_ok=True)
    with open(trial_file, "a") as f:
        f.write(json.dumps(rec.to_dict()) + "\n")


def load_trials(
    mt_id: Optional[str] = None, trial_file: Path = TRIAL_FILE
) -> List[TrialRecord]:
    """Load trial records, optionally filtered by MT ID."""
    if not trial_file.exists():
        return []

    records = []
    with open(trial_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                rec = TrialRecord.from_dict(data)
                if mt_id is None or rec.mt_id == mt_id:
                    records.append(rec)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
    return records


def check_gate(
    mt_id: str, required: int = 3, trial_file: Path = TRIAL_FILE
) -> dict:
    """Check if an MT has met its validation gate."""
    trials = load_trials(mt_id=mt_id, trial_file=trial_file)

    pass_count = sum(1 for t in trials if t.result == "pass")
    fail_count = sum(1 for t in trials if t.result == "fail")

    # Count consecutive passes from the end
    consecutive = 0
    for t in reversed(trials):
        if t.result == "pass":
            consecutive += 1
        else:
            break

    return {
        "mt_id": mt_id,
        "passed": pass_count >= required,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "required": required,
        "consecutive_passes": consecutive,
        "total_trials": len(trials),
    }


def get_trial_status(mt_id: str, trial_file: Path = TRIAL_FILE) -> dict:
    """Get summary status for all trials of an MT."""
    trials = load_trials(mt_id=mt_id, trial_file=trial_file)

    if not trials:
        return {
            "total_trials": 0,
            "passes": 0,
            "fails": 0,
            "total_commits": 0,
            "total_tests_added": 0,
            "avg_duration_secs": 0,
        }

    passes = sum(1 for t in trials if t.result == "pass")
    fails = sum(1 for t in trials if t.result == "fail")
    total_commits = sum(t.commits for t in trials)
    total_tests_added = sum(t.tests_added for t in trials)

    durations = [t.duration_secs for t in trials if t.duration_secs > 0]
    avg_duration = sum(durations) // len(durations) if durations else 0

    return {
        "total_trials": len(trials),
        "passes": passes,
        "fails": fails,
        "total_commits": total_commits,
        "total_tests_added": total_tests_added,
        "avg_duration_secs": avg_duration,
    }


def cli_record(
    mt_id: str,
    session_id: str,
    result: str,
    commits: int = 0,
    tests_added: int = 0,
    coordination_failures: int = 0,
    test_regressions: int = 0,
    duration_secs: int = 0,
    notes: str = "",
    trial_file: Path = TRIAL_FILE,
) -> TrialRecord:
    """CLI wrapper for recording a trial."""
    if result not in ("pass", "fail"):
        raise ValueError(f"Result must be 'pass' or 'fail', got '{result}'")

    rec = TrialRecord(
        mt_id=mt_id,
        session_id=session_id,
        result=result,
        commits=commits,
        tests_added=tests_added,
        coordination_failures=coordination_failures,
        test_regressions=test_regressions,
        duration_secs=duration_secs,
        notes=notes,
    )
    record_trial(rec, trial_file=trial_file)
    return rec


def cli_gate(
    mt_id: str, required: int = 3, trial_file: Path = TRIAL_FILE
) -> dict:
    """CLI wrapper for checking a gate."""
    result = check_gate(mt_id, required=required, trial_file=trial_file)

    if result["passed"]:
        result["message"] = (
            f"GATE PASSED: {mt_id} has {result['pass_count']}/{result['required']} "
            f"passing trials. Approved for autonomous use."
        )
    else:
        result["message"] = (
            f"GATE NOT MET: {mt_id} has {result['pass_count']}/{result['required']} "
            f"passing trials ({result['fail_count']} fails). "
            f"Need {result['required'] - result['pass_count']} more passes."
        )

    return result


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage:")
        print("  python3 trial_tracker.py record <MT-ID> <SESSION> pass|fail [--commits N] [--tests N]")
        print("  python3 trial_tracker.py status <MT-ID>")
        print("  python3 trial_tracker.py gate <MT-ID> [--required N]")
        sys.exit(0)

    cmd = args[0]

    if cmd == "record":
        if len(args) < 4:
            print("Usage: trial_tracker.py record <MT-ID> <SESSION> pass|fail [--commits N] [--tests N] [--notes TEXT]")
            sys.exit(1)
        mt_id, session_id, result = args[1], args[2], args[3]

        kwargs = {}
        i = 4
        while i < len(args):
            if args[i] == "--commits" and i + 1 < len(args):
                kwargs["commits"] = int(args[i + 1])
                i += 2
            elif args[i] == "--tests" and i + 1 < len(args):
                kwargs["tests_added"] = int(args[i + 1])
                i += 2
            elif args[i] == "--duration" and i + 1 < len(args):
                kwargs["duration_secs"] = int(args[i + 1])
                i += 2
            elif args[i] == "--notes" and i + 1 < len(args):
                kwargs["notes"] = args[i + 1]
                i += 2
            elif args[i] == "--coord-failures" and i + 1 < len(args):
                kwargs["coordination_failures"] = int(args[i + 1])
                i += 2
            elif args[i] == "--test-regressions" and i + 1 < len(args):
                kwargs["test_regressions"] = int(args[i + 1])
                i += 2
            else:
                i += 1

        rec = cli_record(mt_id, session_id, result, **kwargs)
        print(f"Recorded: {rec.mt_id} {rec.session_id} {rec.result}")

    elif cmd == "status":
        if len(args) < 2:
            print("Usage: trial_tracker.py status <MT-ID>")
            sys.exit(1)
        status = get_trial_status(args[1])
        print(json.dumps(status, indent=2))

    elif cmd == "gate":
        if len(args) < 2:
            print("Usage: trial_tracker.py gate <MT-ID> [--required N]")
            sys.exit(1)
        mt_id = args[1]
        required = 3
        if "--required" in args:
            idx = args.index("--required")
            if idx + 1 < len(args):
                required = int(args[idx + 1])
        result = cli_gate(mt_id, required=required)
        print(result["message"])

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
