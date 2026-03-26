#!/usr/bin/env python3
"""batch_wrap_learning.py — MT-36 Phase 3: Consolidated wrap self-learning.

Replaces 11 separate subprocess calls in cca-wrap Steps 6a-6h with a single
batch execution. Saves ~5,000-10,000 tokens per session by eliminating
subprocess spawn overhead and redundant file reads.

What this batches (previously 11 separate calls):
  1. journal.py log session_outcome
  2. session_outcome_tracker.py auto-record
  3. journal.py log win (per win)
  4. journal.py log pain (per loss)
  5. wrap_tracker.py log
  6. tip_tracker.py add (per tip)
  7. reflect.py --brief (DEFERRED — run in next init)
  8. reflect.py --apply (DEFERRED)
  9. improver.py evolve (DEFERRED)
  10. validate_strategies.py --brief (DEFERRED)
  11. Various inline checks (DEFERRED)

Steps 1-6 are write-only (JSONL appends). Steps 7-11 are analysis that can
run at next init without quality loss.

Usage:
    python3 batch_wrap_learning.py \\
        --session 147 --grade B \\
        --wins "Built analyzer" "Fixed picker" \\
        --losses "Stale data" \\
        --summary "MT-36 Phase 2 complete" \\
        --domain general \\
        --tests-added 32 --tests-total 8715 \\
        --tips "Wire timer into wrap"

Stdlib only. No external dependencies.
"""
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Default paths (match existing tools' locations)
DEFAULT_JOURNAL_PATH = os.path.join(SCRIPT_DIR, "self-learning", "journal.jsonl")
DEFAULT_WRAP_PATH = os.path.join(SCRIPT_DIR, "wrap_assessments.jsonl")
DEFAULT_TIP_PATH = os.path.join(SCRIPT_DIR, "tip_tracker_data.jsonl")
DEFAULT_OUTCOME_PATH = os.path.join(SCRIPT_DIR, "session_outcomes.jsonl")

VALID_GRADES = {"A", "B", "C", "D"}
VALID_OUTCOMES = {"success", "partial", "failure"}
VALID_DOMAINS = {
    "nuclear_scan", "memory_system", "spec_system", "context_monitor",
    "agent_guard", "usage_dashboard", "reddit_intelligence",
    "self_learning", "general",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WrapBatch:
    """All data needed for a single wrap's self-learning writes."""
    session_id: int
    grade: str
    wins: list[str]
    losses: list[str]
    outcome: str
    summary: str
    domain: str
    tests_added: int
    tests_total: int
    tips: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        if self.grade not in VALID_GRADES:
            return False
        if self.outcome not in VALID_OUTCOMES:
            return False
        return True

    @staticmethod
    def grade_to_outcome(grade: str) -> str:
        if grade in ("A", "B"):
            return "success"
        if grade == "C":
            return "partial"
        return "failure"


@dataclass
class BatchResult:
    """Tracks what the batch did."""
    steps_run: int = 0
    steps_failed: int = 0
    errors: list[str] = field(default_factory=list)
    _step_results: list[tuple[str, bool]] = field(default_factory=list)

    def record(self, step_name: str, success: bool, error: Optional[str] = None):
        self.steps_run += 1
        if not success:
            self.steps_failed += 1
            if error:
                self.errors.append(f"{step_name}: {error}")
        self._step_results.append((step_name, success))

    @property
    def all_ok(self) -> bool:
        return self.steps_failed == 0

    def summary(self) -> str:
        status = "OK" if self.all_ok else f"{self.steps_failed} failed"
        msg = f"{self.steps_run} steps, {status}"
        if self.errors:
            msg += f" — errors: {'; '.join(self.errors)}"
        return msg


# ---------------------------------------------------------------------------
# Batch execution
# ---------------------------------------------------------------------------

def _append_jsonl(path: str, entry: dict) -> None:
    """Append a JSON entry to a JSONL file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")


def run_batch(
    batch: WrapBatch,
    journal_path: str = DEFAULT_JOURNAL_PATH,
    wrap_path: str = DEFAULT_WRAP_PATH,
    tip_path: str = DEFAULT_TIP_PATH,
    outcome_path: str = DEFAULT_OUTCOME_PATH,
) -> BatchResult:
    """Execute all wrap self-learning writes in a single batch.

    This replaces 11 subprocess calls with direct file writes.
    """
    result = BatchResult()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # 1. Log session_outcome to journal
    try:
        _append_jsonl(journal_path, {
            "event_type": "session_outcome",
            "session": batch.session_id,
            "domain": batch.domain,
            "outcome": batch.outcome,
            "notes": batch.summary,
            "timestamp": now,
        })
        result.record("journal_session_outcome", True)
    except Exception as e:
        result.record("journal_session_outcome", False, str(e))

    # 2. Log wins
    for win in batch.wins:
        try:
            _append_jsonl(journal_path, {
                "event_type": "win",
                "session": batch.session_id,
                "domain": batch.domain,
                "notes": win,
                "timestamp": now,
            })
            result.record("journal_win", True)
        except Exception as e:
            result.record("journal_win", False, str(e))

    # 3. Log losses as pain
    for loss in batch.losses:
        try:
            _append_jsonl(journal_path, {
                "event_type": "pain",
                "session": batch.session_id,
                "domain": batch.domain,
                "notes": loss,
                "timestamp": now,
            })
            result.record("journal_pain", True)
        except Exception as e:
            result.record("journal_pain", False, str(e))

    # 4. Wrap assessment
    try:
        _append_jsonl(wrap_path, {
            "session": batch.session_id,
            "grade": batch.grade,
            "wins": batch.wins,
            "losses": batch.losses,
            "tests": batch.tests_total,
            "timestamp": now,
        })
        result.record("wrap_assessment", True)
    except Exception as e:
        result.record("wrap_assessment", False, str(e))

    # 5. Tips
    for tip in batch.tips:
        try:
            _append_jsonl(tip_path, {
                "tip": tip,
                "source": "cca-desktop",
                "session": f"S{batch.session_id}",
                "timestamp": now,
            })
            result.record("tip_tracker", True)
        except Exception as e:
            result.record("tip_tracker", False, str(e))

    # 6. Session outcome tracking
    try:
        _append_jsonl(outcome_path, {
            "session": batch.session_id,
            "grade": batch.grade,
            "outcome": batch.outcome,
            "tests_added": batch.tests_added,
            "tests_total": batch.tests_total,
            "summary": batch.summary,
            "timestamp": now,
        })
        result.record("outcome_tracker", True)
    except Exception as e:
        result.record("outcome_tracker", False, str(e))

    # 7. Principle seeding from findings + journal (MT-28 growth)
    try:
        from self_learning_imports import seed_all as _seed_all
        summary = _seed_all(session=batch.session_id)
        seeded = summary.get("total_seeded", 0)
        result.record("principle_seeding", True)
    except ImportError:
        # Fallback: try direct import
        try:
            import sys as _sys
            import os as _os
            _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "self-learning"))
            from principle_seeder import seed_all as _seed_all_direct
            summary = _seed_all_direct(session=batch.session_id)
            result.record("principle_seeding", True)
        except Exception as e:
            result.record("principle_seeding", False, f"import: {e}")
    except Exception as e:
        result.record("principle_seeding", False, str(e))

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Batch wrap self-learning (MT-36 Phase 3)"
    )
    parser.add_argument("--session", type=int, required=True)
    parser.add_argument("--grade", required=True, choices=["A", "B", "C", "D"])
    parser.add_argument("--wins", nargs="*", default=[])
    parser.add_argument("--losses", nargs="*", default=[])
    parser.add_argument("--summary", required=True)
    parser.add_argument("--domain", default="general")
    parser.add_argument("--tests-added", type=int, default=0)
    parser.add_argument("--tests-total", type=int, default=0)
    parser.add_argument("--tips", nargs="*", default=[])
    args = parser.parse_args()

    batch = WrapBatch(
        session_id=args.session,
        grade=args.grade,
        wins=args.wins,
        losses=args.losses,
        outcome=WrapBatch.grade_to_outcome(args.grade),
        summary=args.summary,
        domain=args.domain,
        tests_added=args.tests_added,
        tests_total=args.tests_total,
        tips=args.tips,
    )

    if not batch.is_valid():
        print(f"ERROR: Invalid batch data", file=sys.stderr)
        sys.exit(1)

    result = run_batch(batch)
    print(result.summary())
    if not result.all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
