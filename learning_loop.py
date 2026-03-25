#!/usr/bin/env python3
"""learning_loop.py — Cross-Chat Learning Feedback Loop.

Automates the CCA <-> Kalshi feedback cycle:
1. Reads outcome_report messages from cross_chat_queue.jsonl
2. Updates research_outcomes.jsonl with reported results
3. Computes research priority scores by category based on historical ROI
4. Generates research_priority recommendations for CCA task selection

This closes the loop: CCA researches -> Kalshi implements -> Kalshi reports
outcome -> CCA prioritizes research that produces profit.

Usage:
    python3 learning_loop.py cycle                 # Run full feedback cycle
    python3 learning_loop.py priorities             # Show current research priorities
    python3 learning_loop.py priorities --json      # JSON output

Stdlib only. No external dependencies. One file = one job.

S162 — Cross-chat learning loop (Matthew directive S161).
"""

import json
import os
import sys
from dataclasses import dataclass, asdict
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_QUEUE_PATH = os.path.join(SCRIPT_DIR, "cross_chat_queue.jsonl")
DEFAULT_OUTCOMES_PATH = os.path.join(SCRIPT_DIR, "self-learning", "research_outcomes.jsonl")

# Statuses that count as "resolved" for priority scoring
RESOLVED_STATUSES = {"profitable", "unprofitable", "rejected"}
PROFITABLE_STATUSES = {"profitable"}

# Cap profit contribution to score at this value (cents) to prevent outliers
PROFIT_CAP_CENTS = 5000


@dataclass
class OutcomeReport:
    """Parsed outcome report from a queue message."""
    delivery_id: str
    status: str
    profit_cents: Optional[int] = None
    bet_count: Optional[int] = None
    notes: Optional[str] = None
    source_msg_id: Optional[str] = None

    @classmethod
    def from_queue_message(cls, msg: dict) -> "OutcomeReport":
        """Parse an outcome_report queue message into an OutcomeReport."""
        try:
            body = json.loads(msg.get("body", "{}"))
        except (json.JSONDecodeError, TypeError):
            raise ValueError(f"Invalid outcome_report body in message {msg.get('id')}")

        delivery_id = body.get("delivery_id")
        if not delivery_id:
            raise ValueError(f"Missing delivery_id in outcome_report {msg.get('id')}")

        status = body.get("status")
        if not status:
            raise ValueError(f"Missing status in outcome_report {msg.get('id')}")

        return cls(
            delivery_id=delivery_id,
            status=status,
            profit_cents=body.get("profit_cents"),
            bet_count=body.get("bet_count"),
            notes=body.get("notes"),
            source_msg_id=msg.get("id"),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResearchPriority:
    """Priority score for a research category."""
    category: str
    score: float
    total_deliveries: int
    profitable_count: int
    total_profit_cents: int
    recommendation: str

    def to_dict(self) -> dict:
        return asdict(self)


class LearningLoop:
    """Core feedback loop engine."""

    def __init__(
        self,
        queue_path: str = DEFAULT_QUEUE_PATH,
        outcomes_path: str = DEFAULT_OUTCOMES_PATH,
    ):
        self.queue_path = queue_path
        self.outcomes_path = outcomes_path

    def _load_queue(self) -> list[dict]:
        if not os.path.exists(self.queue_path):
            return []
        messages = []
        with open(self.queue_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return messages

    def _load_outcomes(self) -> list[dict]:
        if not os.path.exists(self.outcomes_path):
            return []
        outcomes = []
        with open(self.outcomes_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        outcomes.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return outcomes

    def _save_outcomes(self, outcomes: list[dict]) -> None:
        with open(self.outcomes_path, "w", encoding="utf-8") as f:
            for o in outcomes:
                f.write(json.dumps(o, separators=(",", ":")) + "\n")

    def extract_outcome_reports(self) -> list[OutcomeReport]:
        """Extract unread outcome_report messages from the queue."""
        messages = self._load_queue()
        reports = []
        for msg in messages:
            if (msg.get("category") == "outcome_report"
                    and msg.get("target") == "cca"
                    and msg.get("status") == "unread"):
                try:
                    reports.append(OutcomeReport.from_queue_message(msg))
                except ValueError:
                    continue
        return reports

    def apply_outcomes(self, reports: list[OutcomeReport]) -> int:
        """Apply outcome reports to the research_outcomes DB. Returns count applied."""
        if not reports:
            return 0

        outcomes = self._load_outcomes()
        report_map = {r.delivery_id: r for r in reports}
        applied = 0

        for outcome in outcomes:
            did = outcome.get("delivery_id")
            if did in report_map:
                report = report_map[did]
                outcome["status"] = report.status
                if report.profit_cents is not None:
                    outcome["profit_impact_cents"] = report.profit_cents
                if report.bet_count is not None:
                    outcome["bet_count"] = report.bet_count
                if report.notes:
                    outcome["outcome_notes"] = report.notes
                applied += 1

        if applied:
            self._save_outcomes(outcomes)
        return applied

    def compute_priorities(self) -> list[ResearchPriority]:
        """Compute research priority scores by category from outcome history."""
        outcomes = self._load_outcomes()
        if not outcomes:
            return []

        # Group by category, only count resolved deliveries
        by_category: dict[str, list[dict]] = {}
        for o in outcomes:
            cat = o.get("category")
            status = o.get("status", "")
            if not cat or status not in RESOLVED_STATUSES:
                continue
            by_category.setdefault(cat, []).append(o)

        priorities = []
        for cat, deliveries in by_category.items():
            total = len(deliveries)
            profitable = sum(1 for d in deliveries if d.get("status") in PROFITABLE_STATUSES)
            total_profit = sum(d.get("profit_impact_cents", 0) or 0 for d in deliveries)

            # Score: win_rate component (0-50) + profit component (0-50)
            win_rate = profitable / total if total > 0 else 0
            win_score = win_rate * 50

            # Profit component: normalize to 0-50 range, capped
            capped_profit = max(-PROFIT_CAP_CENTS, min(PROFIT_CAP_CENTS, total_profit))
            # Map [-5000, 5000] to [0, 50]
            profit_score = ((capped_profit + PROFIT_CAP_CENTS) / (2 * PROFIT_CAP_CENTS)) * 50

            score = round(win_score + profit_score, 1)

            # Generate recommendation
            pct = round(win_rate * 100)
            dollars = total_profit / 100
            if score >= 70:
                level = "HIGH"
            elif score >= 40:
                level = "MEDIUM"
            else:
                level = "LOW"
            rec = f"{level} — {cat}: {pct}% hit rate ({profitable}/{total}), ${dollars:+.2f} total"

            priorities.append(ResearchPriority(
                category=cat,
                score=score,
                total_deliveries=total,
                profitable_count=profitable,
                total_profit_cents=total_profit,
                recommendation=rec,
            ))

        # Sort by score descending
        priorities.sort(key=lambda p: p.score, reverse=True)
        return priorities

    def run_cycle(self) -> dict:
        """Run a full feedback cycle: extract reports, apply, compute priorities."""
        reports = self.extract_outcome_reports()
        applied = self.apply_outcomes(reports) if reports else 0
        priorities = self.compute_priorities()

        return {
            "reports_processed": len(reports),
            "outcomes_applied": applied,
            "priorities": [p.to_dict() for p in priorities],
            "priority_message": generate_priority_message(priorities),
        }


def process_outcome_reports(
    queue_path: str = DEFAULT_QUEUE_PATH,
    outcomes_path: str = DEFAULT_OUTCOMES_PATH,
) -> int:
    """Convenience: process outcome reports and return count applied."""
    loop = LearningLoop(queue_path=queue_path, outcomes_path=outcomes_path)
    reports = loop.extract_outcome_reports()
    return loop.apply_outcomes(reports)


def compute_research_priorities(
    outcomes_path: str = DEFAULT_OUTCOMES_PATH,
) -> list[ResearchPriority]:
    """Convenience: compute and return research priorities sorted by score."""
    loop = LearningLoop(outcomes_path=outcomes_path)
    return loop.compute_priorities()


def generate_priority_message(priorities: list[ResearchPriority]) -> str:
    """Format priorities into a human-readable message for cross-chat delivery."""
    if not priorities:
        return "No outcome data yet — continue building research baseline."

    lines = ["Research Priority Scores (by historical ROI):"]
    for p in priorities:
        lines.append(f"  {p.recommendation}")
    lines.append("")
    lines.append("Focus research on HIGH categories. Reduce investment in LOW categories.")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cross-chat learning feedback loop")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("cycle", help="Run full feedback cycle")

    pri_p = sub.add_parser("priorities", help="Show research priorities")
    pri_p.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "cycle":
        loop = LearningLoop()
        result = loop.run_cycle()
        print(f"Reports processed: {result['reports_processed']}")
        print(f"Outcomes applied: {result['outcomes_applied']}")
        if result["priorities"]:
            print()
            print(result["priority_message"])
        else:
            print("No resolved outcomes yet — priorities will appear after Kalshi reports results.")

    elif args.command == "priorities":
        priorities = compute_research_priorities()
        if args.json:
            print(json.dumps([p.to_dict() for p in priorities], indent=2))
        else:
            print(generate_priority_message(priorities))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
