#!/usr/bin/env python3
"""
outcome_feedback.py — MT-28 Phase 4: Research Outcomes Feedback Loop

Bridges research_outcomes.py (delivery tracking) with principle_registry.py
(principle scoring). When a research delivery produces profit or loss,
the principles that informed that research get scored accordingly.

The closed loop:
  1. CCA delivers research to Kalshi via cross_chat_queue
  2. Kalshi implements and records outcome (profitable/unprofitable + P&L)
  3. This module receives the outcome and linked principle IDs
  4. Principle scores updated (success for profitable, usage-only for unprofitable)
  5. Future research prioritization uses updated principle scores

This is the CCA-side infrastructure. The Kalshi bot integration (providing
the outcomes) is MT-0 Phase 2 work done in the polybot project.

Usage:
    from outcome_feedback import OutcomeFeedback

    fb = OutcomeFeedback()
    event = fb.record_outcome(
        delivery_id="d-abc12345",
        outcome="profitable",
        profit_cents=450,
        principle_ids=["prin_bayesian_01"],
    )

    # Batch process pending outcomes
    fb.process_pending(principle_mapping={...})

    # ROI summary with principle context
    summary = fb.roi_summary()

CLI:
    python3 outcome_feedback.py record <delivery_id> --outcome profitable \\
        --profit 450 --principles prin_abc,prin_def
    python3 outcome_feedback.py summary

Zero external dependencies. Stdlib only.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from research_outcomes import OutcomeTracker
from principle_registry import (
    Principle,
    _load_principles,
    _save_principle,
)

DEFAULT_OUTCOMES_PATH = os.path.join(SCRIPT_DIR, "research_outcomes.jsonl")
DEFAULT_PRINCIPLES_PATH = os.path.join(SCRIPT_DIR, "principles.jsonl")
DEFAULT_FEEDBACK_LOG = os.path.join(SCRIPT_DIR, "feedback_log.jsonl")

VALID_OUTCOMES = ("profitable", "unprofitable")


@dataclass
class FeedbackEvent:
    """Record of a single feedback loop iteration."""
    delivery_id: str
    outcome: str  # profitable or unprofitable
    principle_ids: List[str]
    profit_cents: int
    timestamp: str = ""
    skipped_principles: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "outcome": self.outcome,
            "principle_ids": self.principle_ids,
            "profit_cents": self.profit_cents,
            "timestamp": self.timestamp,
            "skipped_principles": self.skipped_principles,
        }


class OutcomeFeedback:
    """Bridges research outcomes to principle scoring.

    When a delivery outcome is recorded (profitable/unprofitable),
    this module updates the linked principles' scores.
    """

    def __init__(
        self,
        outcomes_path: str = DEFAULT_OUTCOMES_PATH,
        principles_path: str = DEFAULT_PRINCIPLES_PATH,
        feedback_log_path: str = DEFAULT_FEEDBACK_LOG,
    ):
        self.outcomes_path = outcomes_path
        self.principles_path = principles_path
        self.feedback_log_path = feedback_log_path

    def record_outcome(
        self,
        delivery_id: str,
        outcome: str,
        profit_cents: int,
        principle_ids: List[str],
    ) -> FeedbackEvent:
        """Record a research outcome and update principle scores.

        Args:
            delivery_id: ID of the delivery in research_outcomes.jsonl.
            outcome: "profitable" or "unprofitable".
            profit_cents: P&L in cents (positive for profit, negative for loss).
            principle_ids: Principle IDs that informed this research.

        Returns:
            FeedbackEvent with details of what was updated.

        Raises:
            ValueError: If outcome is invalid.
            KeyError: If delivery_id not found.
        """
        if outcome not in VALID_OUTCOMES:
            raise ValueError(
                f"Invalid outcome: {outcome}. Must be one of {VALID_OUTCOMES}")

        # 1. Update delivery status
        tracker = OutcomeTracker(db_path=self.outcomes_path)
        if outcome == "profitable":
            tracker.mark_profitable(delivery_id, profit_cents)
        else:
            tracker.mark_unprofitable(delivery_id, profit_cents)
        tracker.save()

        # 2. Update principle scores
        skipped = []
        if principle_ids:
            principles = _load_principles(path=self.principles_path)

            for pid in principle_ids:
                if pid not in principles:
                    skipped.append(pid)
                    continue

                p = principles[pid]
                p.usage_count += 1
                if outcome == "profitable":
                    p.success_count += 1
                p.updated_at = datetime.now(timezone.utc).isoformat()

                # Save updated principle (append — latest version wins)
                _save_principle(p, path=self.principles_path)

        # 3. Log the feedback event
        event = FeedbackEvent(
            delivery_id=delivery_id,
            outcome=outcome,
            principle_ids=principle_ids,
            profit_cents=profit_cents,
            skipped_principles=skipped,
        )
        self._append_log(event)

        return event

    def process_pending(
        self,
        principle_mapping: Dict[str, List[str]],
    ) -> List[FeedbackEvent]:
        """Process all deliveries with profit/unprofitable status.

        For deliveries that already have a profit status but haven't had
        their principles updated yet.

        Args:
            principle_mapping: {delivery_id: [principle_ids]} mapping
                which principles each delivery was informed by.

        Returns:
            List of FeedbackEvents for processed deliveries.
        """
        tracker = OutcomeTracker(db_path=self.outcomes_path)
        events = []

        for d in tracker.deliveries:
            if d.delivery_id not in principle_mapping:
                continue
            if d.status not in ("profitable", "unprofitable"):
                continue

            pids = principle_mapping[d.delivery_id]
            profit = d.profit_impact_cents or 0

            event = self.record_outcome(
                delivery_id=d.delivery_id,
                outcome=d.status,
                profit_cents=profit,
                principle_ids=pids,
            )
            events.append(event)

        return events

    def roi_summary(self) -> Dict[str, Any]:
        """Generate ROI summary with principle score context."""
        events = self._load_log()

        profitable_count = sum(1 for e in events if e["outcome"] == "profitable")
        unprofitable_count = sum(1 for e in events if e["outcome"] == "unprofitable")
        total_profit = sum(e["profit_cents"] for e in events)

        all_pids = set()
        for e in events:
            all_pids.update(e.get("principle_ids", []))

        return {
            "total_feedback_events": len(events),
            "profitable_count": profitable_count,
            "unprofitable_count": unprofitable_count,
            "total_profit_cents": total_profit,
            "principles_updated": len(all_pids),
            "win_rate": (profitable_count / len(events)
                         if events else 0.0),
        }

    def _append_log(self, event: FeedbackEvent) -> None:
        """Append feedback event to log (JSONL)."""
        with open(self.feedback_log_path, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    def _load_log(self) -> List[Dict]:
        """Load all feedback events from log."""
        events = []
        if not os.path.exists(self.feedback_log_path):
            return events
        with open(self.feedback_log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events


def _cli():
    """CLI interface."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Research Outcomes Feedback Loop")
    sub = parser.add_subparsers(dest="command")

    rec = sub.add_parser("record", help="Record an outcome")
    rec.add_argument("delivery_id")
    rec.add_argument("--outcome", required=True,
                     choices=["profitable", "unprofitable"])
    rec.add_argument("--profit", type=int, default=0)
    rec.add_argument("--principles", type=str, default="",
                     help="Comma-separated principle IDs")

    sub.add_parser("summary", help="Show ROI summary")

    args = parser.parse_args()
    fb = OutcomeFeedback()

    if args.command == "record":
        pids = [p.strip() for p in args.principles.split(",") if p.strip()]
        event = fb.record_outcome(
            delivery_id=args.delivery_id,
            outcome=args.outcome,
            profit_cents=args.profit,
            principle_ids=pids,
        )
        print(json.dumps(event.to_dict(), indent=2))
    elif args.command == "summary":
        print(json.dumps(fb.roi_summary(), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
