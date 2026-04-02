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
DEFAULT_FEEDBACK_LOG = os.path.join(SCRIPT_DIR, "self-learning", "feedback_log.jsonl")
DEFAULT_PRINCIPLES_PATH = os.path.join(SCRIPT_DIR, "self-learning", "principles.jsonl")

VALID_GRADES = {"A", "B", "C", "D"}
VALID_OUTCOMES = {"success", "partial", "failure"}
VALID_DOMAINS = {
    "nuclear_scan", "memory_system", "spec_system", "context_monitor",
    "agent_guard", "usage_dashboard", "reddit_intelligence",
    "self_learning", "general",
    # Kalshi/trading domains (polymarket-bot cross-project learning)
    "kalshi_monitoring", "kalshi_research", "kalshi_trading",
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


def _outcome_feedback_roi(feedback_log_path: str) -> dict:
    """Load outcome feedback ROI summary from feedback log JSONL.

    Reads the feedback_log directly (no import needed) to avoid
    circular dependency on outcome_feedback.py.
    """
    events = []
    if os.path.exists(feedback_log_path):
        with open(feedback_log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))

    profitable = sum(1 for e in events if e.get("outcome") == "profitable")
    unprofitable = sum(1 for e in events if e.get("outcome") == "unprofitable")
    total_profit = sum(e.get("profit_cents", 0) for e in events)
    all_pids = set()
    for e in events:
        all_pids.update(e.get("principle_ids", []))

    return {
        "total_feedback_events": len(events),
        "profitable_count": profitable,
        "unprofitable_count": unprofitable,
        "total_profit_cents": total_profit,
        "principles_updated": len(all_pids),
        "win_rate": (profitable / len(events)) if events else 0.0,
    }


def _sentinel_bridge_stats(principles_path: str) -> dict:
    """Load sentinel bridge stats from principles JSONL.

    Reads principles directly (no import needed) to count sentinel-sourced
    and counter-principles without importing the full registry.
    """
    principles = []
    if os.path.exists(principles_path):
        with open(principles_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    principles.append(json.loads(line))

    # Deduplicate by id (latest entry wins, same as principle_registry)
    by_id = {}
    for p in principles:
        pid = p.get("id", "")
        if pid:
            by_id[pid] = p

    total = len(by_id)
    counter = sum(1 for p in by_id.values()
                  if p.get("text", "").startswith("Avoid:"))
    sentinel = sum(1 for p in by_id.values()
                   if "sentinel" in (p.get("source_context", "") or ""))

    return {
        "total_principles": total,
        "counter_principles": counter,
        "sentinel_sourced": sentinel,
    }


def run_batch(
    batch: WrapBatch,
    journal_path: str = DEFAULT_JOURNAL_PATH,
    wrap_path: str = DEFAULT_WRAP_PATH,
    tip_path: str = DEFAULT_TIP_PATH,
    outcome_path: str = DEFAULT_OUTCOME_PATH,
    feedback_log_path: str = DEFAULT_FEEDBACK_LOG,
    principles_path: str = DEFAULT_PRINCIPLES_PATH,
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

    # 8. Outcome feedback ROI summary (surfaces research→profit loop)
    try:
        roi = _outcome_feedback_roi(feedback_log_path)
        _append_jsonl(journal_path, {
            "event_type": "feedback_roi",
            "session": batch.session_id,
            "total_feedback_events": roi.get("total_feedback_events", 0),
            "profitable_count": roi.get("profitable_count", 0),
            "unprofitable_count": roi.get("unprofitable_count", 0),
            "total_profit_cents": roi.get("total_profit_cents", 0),
            "win_rate": roi.get("win_rate", 0.0),
            "principles_updated": roi.get("principles_updated", 0),
            "timestamp": now,
        })
        result.record("outcome_feedback_roi", True)
    except Exception as e:
        result.record("outcome_feedback_roi", False, str(e))

    # 9. Sentinel bridge stats (surfaces mutation→principle loop)
    try:
        stats = _sentinel_bridge_stats(principles_path)
        _append_jsonl(journal_path, {
            "event_type": "sentinel_stats",
            "session": batch.session_id,
            "total_principles": stats.get("total_principles", 0),
            "counter_principles": stats.get("counter_principles", 0),
            "sentinel_sourced": stats.get("sentinel_sourced", 0),
            "timestamp": now,
        })
        result.record("sentinel_bridge_stats", True)
    except Exception as e:
        result.record("sentinel_bridge_stats", False, str(e))

    # 10. Meta-tracker snapshot (MT-49 Phase 1 — track meta-learning health over time)
    try:
        sys.path.insert(0, os.path.join(SCRIPT_DIR, "self-learning"))
        from meta_tracker import MetaTracker
        mt = MetaTracker()
        snap = mt.snapshot(session=batch.session_id)
        _append_jsonl(journal_path, {
            "event_type": "meta_learning_health",
            "session": batch.session_id,
            "health_score": snap.get("health_score", 0),
            "total_principles": snap.get("total", 0),
            "active_principles": snap.get("active", 0),
            "zombie_principles": snap.get("zombies", 0),
            "timestamp": now,
        })
        result.record("meta_tracker_snapshot", True)
    except Exception as e:
        result.record("meta_tracker_snapshot", False, str(e))

    # 11. Auto-accept high-confidence principle transfers (MT-49 Phase 2)
    try:
        sys.path.insert(0, os.path.join(SCRIPT_DIR, "self-learning"))
        from principle_transfer import PrincipleTransfer
        pt = PrincipleTransfer()
        # First propose new transfers, then auto-accept high-scoring ones
        new_proposals = pt.propose_transfers(max_proposals=5)
        accepted = pt.auto_accept(min_score=0.60)
        if new_proposals or accepted:
            _append_jsonl(journal_path, {
                "event_type": "principle_transfer",
                "session": batch.session_id,
                "new_proposals": len(new_proposals),
                "auto_accepted": len(accepted),
                "accepted_details": [
                    {"id": p.proposal_id, "score": p.transfer_score,
                     "from": p.source_domain, "to": p.target_domain}
                    for p in accepted
                ],
                "timestamp": now,
            })
        result.record("principle_transfer", True)
    except Exception as e:
        result.record("principle_transfer", False, str(e))

    # 12. Confidence recalibration — apply Bayesian staleness decay (MT-49 Phase 4)
    try:
        from confidence_recalibrator import apply_recalibration, DEFAULT_CHECKPOINT_PATH
        recal = apply_recalibration(
            current_session=batch.session_id,
            checkpoint_path=DEFAULT_CHECKPOINT_PATH,
            min_gap=10,
        )
        if recal["applied"] > 0:
            _append_jsonl(journal_path, {
                "event_type": "confidence_recalibration",
                "session": batch.session_id,
                "applied": recal["applied"],
                "skipped": recal["skipped"],
                "reason": recal["reason"],
                "timestamp": now,
            })
        result.record("confidence_recalibration", True)
    except Exception as e:
        result.record("confidence_recalibration", False, str(e))

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

    # MT-49 unified health snapshot
    try:
        sys.path.insert(0, os.path.join(SCRIPT_DIR, "self-learning"))
        from wrap_summary import build_summary, format_summary
        snap = build_summary(batch.session_id)
        print(format_summary(snap))
    except Exception:
        pass  # Non-blocking — wrap continues even if snapshot fails

    if not result.all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
