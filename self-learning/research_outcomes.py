#!/usr/bin/env python3
"""
research_outcomes.py — CCA Research ROI Tracker

Tracks which CCA research deliveries (papers, repos, signals, frameworks) got
implemented by Kalshi chats and whether they produced profit. Closes the
research-to-profit feedback loop identified as a critical gap.

Storage: self-learning/research_outcomes.jsonl (append-only JSONL)

Usage:
    python3 self-learning/research_outcomes.py add --session 56 --title "Tsang paper" \
        --category academic_paper --description "Overnight liquidity" --target kr
    python3 self-learning/research_outcomes.py list [--status delivered]
    python3 self-learning/research_outcomes.py update <id> --status implemented
    python3 self-learning/research_outcomes.py roi
    python3 self-learning/research_outcomes.py pending
    python3 self-learning/research_outcomes.py summary
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(SCRIPT_DIR, "research_outcomes.jsonl")

VALID_CATEGORIES = [
    "academic_paper",
    "repo_evaluation",
    "framework",
    "signal",
    "reddit_finding",
    "tool",
    "data_source",
]

VALID_STATUSES = [
    "delivered",       # CCA wrote it to bridge files
    "acknowledged",    # Kalshi chat confirmed receipt
    "implemented",     # Code was built from this research
    "rejected",        # Kalshi chat decided not to implement
    "profitable",      # Implementation produced net profit
    "unprofitable",    # Implementation lost money
]


class Delivery:
    """A single research delivery from CCA to Kalshi chats."""

    def __init__(self, delivery_id, session, title, category, description,
                 target_chat, status="delivered", created_at=None,
                 implemented_at=None, profit_impact_cents=None, notes=None):
        self.delivery_id = delivery_id
        self.session = session
        self.title = title
        self.category = category
        self.description = description
        self.target_chat = target_chat
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.implemented_at = implemented_at
        self.profit_impact_cents = profit_impact_cents
        self.notes = notes

    def to_dict(self):
        d = {
            "delivery_id": self.delivery_id,
            "session": self.session,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "target_chat": self.target_chat,
            "status": self.status,
            "created_at": self.created_at,
        }
        if self.implemented_at:
            d["implemented_at"] = self.implemented_at
        if self.profit_impact_cents is not None:
            d["profit_impact_cents"] = self.profit_impact_cents
        if self.notes:
            d["notes"] = self.notes
        return d

    @classmethod
    def from_dict(cls, data):
        return cls(
            delivery_id=data["delivery_id"],
            session=data["session"],
            title=data["title"],
            category=data["category"],
            description=data["description"],
            target_chat=data["target_chat"],
            status=data.get("status", "delivered"),
            created_at=data.get("created_at"),
            implemented_at=data.get("implemented_at"),
            profit_impact_cents=data.get("profit_impact_cents"),
            notes=data.get("notes"),
        )


def _generate_id(session, title):
    """Generate a deterministic delivery ID from session + title."""
    raw = f"{session}:{title}"
    return "d-" + hashlib.sha256(raw.encode()).hexdigest()[:8]


class OutcomeTracker:
    """Main tracking engine for CCA research deliveries and their ROI."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.deliveries = []
        self._id_index = {}
        if os.path.exists(self.db_path):
            self.load()

    def load(self):
        """Load deliveries from JSONL file."""
        self.deliveries = []
        self._id_index = {}
        if not os.path.exists(self.db_path):
            return
        with open(self.db_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                d = Delivery.from_dict(data)
                self.deliveries.append(d)
                self._id_index[d.delivery_id] = d

    def save(self):
        """Write all deliveries to JSONL file (full rewrite)."""
        with open(self.db_path, "w") as f:
            for d in self.deliveries:
                f.write(json.dumps(d.to_dict()) + "\n")

    def add_delivery(self, session, title, category, description, target_chat):
        """Add a new delivery. Returns the Delivery object."""
        did = _generate_id(session, title)
        d = Delivery(
            delivery_id=did,
            session=session,
            title=title,
            category=category,
            description=description,
            target_chat=target_chat,
        )
        self.deliveries.append(d)
        self._id_index[d.delivery_id] = d
        return d

    def bulk_add(self, items):
        """Add multiple deliveries, skipping duplicates (same session+title)."""
        existing = {(d.session, d.title) for d in self.deliveries}
        added = []
        for item in items:
            key = (item["session"], item["title"])
            if key in existing:
                continue
            d = self.add_delivery(
                session=item["session"],
                title=item["title"],
                category=item["category"],
                description=item["description"],
                target_chat=item["target_chat"],
            )
            existing.add(key)
            added.append(d)
        return added

    def _get_delivery(self, delivery_id):
        if delivery_id not in self._id_index:
            raise KeyError(f"Delivery {delivery_id} not found")
        return self._id_index[delivery_id]

    def update_status(self, delivery_id, new_status):
        """Update a delivery's status."""
        if new_status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}. Must be one of {VALID_STATUSES}")
        d = self._get_delivery(delivery_id)
        d.status = new_status

    def mark_implemented(self, delivery_id, notes=None):
        """Mark a delivery as implemented by Kalshi chat."""
        d = self._get_delivery(delivery_id)
        d.status = "implemented"
        d.implemented_at = datetime.now(timezone.utc).isoformat()
        if notes:
            d.notes = notes

    def mark_profitable(self, delivery_id, profit_cents=0, notes=None):
        """Mark an implemented delivery as profitable."""
        d = self._get_delivery(delivery_id)
        d.status = "profitable"
        d.profit_impact_cents = profit_cents
        if notes:
            d.notes = notes

    def mark_unprofitable(self, delivery_id, loss_cents=0, notes=None):
        """Mark an implemented delivery as unprofitable."""
        d = self._get_delivery(delivery_id)
        d.status = "unprofitable"
        d.profit_impact_cents = loss_cents
        if notes:
            d.notes = notes

    def filter_by_status(self, status):
        return [d for d in self.deliveries if d.status == status]

    def filter_by_category(self, category):
        return [d for d in self.deliveries if d.category == category]

    def filter_by_session(self, session):
        return [d for d in self.deliveries if d.session == session]

    def pending_pickups(self):
        """Deliveries that Kalshi chats haven't acknowledged yet."""
        return [d for d in self.deliveries if d.status == "delivered"]

    def compute_roi(self):
        """Compute research ROI metrics."""
        total = len(self.deliveries)
        if total == 0:
            return {
                "total_deliveries": 0,
                "implementation_rate": 0.0,
                "profit_rate": 0.0,
                "total_profit_cents": 0,
                "profitable_count": 0,
                "unprofitable_count": 0,
            }

        implemented = [d for d in self.deliveries
                       if d.status in ("implemented", "profitable", "unprofitable")]
        profitable = [d for d in self.deliveries if d.status == "profitable"]
        unprofitable = [d for d in self.deliveries if d.status == "unprofitable"]

        total_profit = sum(d.profit_impact_cents or 0 for d in self.deliveries
                          if d.profit_impact_cents is not None)

        impl_count = len(implemented)
        profit_rate = len(profitable) / impl_count if impl_count > 0 else 0.0

        return {
            "total_deliveries": total,
            "implementation_rate": impl_count / total,
            "profit_rate": profit_rate,
            "total_profit_cents": total_profit,
            "profitable_count": len(profitable),
            "unprofitable_count": len(unprofitable),
        }

    def roi_by_category(self):
        """ROI broken down by delivery category."""
        result = {}
        for d in self.deliveries:
            cat = d.category
            if cat not in result:
                result[cat] = {"total": 0, "implemented": 0, "profit_cents": 0}
            result[cat]["total"] += 1
            if d.status in ("implemented", "profitable", "unprofitable"):
                result[cat]["implemented"] += 1
            if d.profit_impact_cents is not None:
                result[cat]["profit_cents"] += d.profit_impact_cents
        return result

    def summary_report(self):
        """Generate a human-readable summary."""
        metrics = self.compute_roi()
        pending = self.pending_pickups()
        lines = [
            "=== CCA Research Outcomes ===",
            f"Total deliveries: {metrics['total_deliveries']}",
            f"Implementation rate: {metrics['implementation_rate']:.0%}",
            f"Profit rate: {metrics['profit_rate']:.0%}",
            f"Total profit: {metrics['total_profit_cents']}c (${metrics['total_profit_cents']/100:.2f})",
            f"Pending pickup: {len(pending)}",
        ]
        if pending:
            lines.append("")
            lines.append("Awaiting Kalshi pickup:")
            for d in pending[:10]:
                lines.append(f"  - S{d.session}: {d.title} ({d.category}) -> {d.target_chat}")
        return "\n".join(lines)


def parse_findings_line(line):
    """Parse a single FINDINGS_LOG.md line into a delivery dict, or None if not Kalshi-relevant.

    Only extracts lines tagged with [MT-0 Kalshi] or [Kalshi] in the category field.
    Skips [SKIP] verdicts and non-Kalshi findings.
    """
    import re

    line = line.strip()
    if not line:
        return None

    # Match: [date] [verdict] [category] title — description. — url
    match = re.match(
        r'\[(\d{4}-\d{2}-\d{2})\]\s+'
        r'\[([^\]]+)\]\s+'
        r'\[([^\]]+)\]\s+'
        r'(.+)',
        line,
    )
    if not match:
        return None

    date, verdict, category_tag, rest = match.groups()

    # Skip non-Kalshi findings
    if "kalshi" not in category_tag.lower():
        return None

    # Skip SKIP verdicts
    if verdict.upper() == "SKIP":
        return None

    # Extract title (up to first " — " or end)
    parts = rest.split(" — ", 1)
    title = parts[0].strip().strip('"')
    description = parts[1].strip() if len(parts) > 1 else ""

    # Remove trailing URL from description
    url_match = re.search(r'\s*—?\s*(https?://\S+|DOI:\S+|SSRN:\S+)\s*$', description)
    if url_match:
        description = description[:url_match.start()].strip().rstrip("—").strip()

    # Determine category from content
    if "github" in rest.lower() or "(GitHub)" in rest:
        cat = "repo_evaluation"
    elif any(kw in rest.lower() for kw in ["r/algo", "r/kalshi", "r/poly", "pts,"]):
        cat = "reddit_finding"
    elif any(kw in rest.lower() for kw in ["paper", "doi:", "arxiv", "ssrn", "journal"]):
        cat = "academic_paper"
    else:
        cat = "signal"

    return {
        "date": date,
        "title": title[:100],  # Cap at 100 chars
        "category": cat,
        "description": description[:200],
        "target_chat": "kalshi_research",
    }


def parse_findings_content(content):
    """Parse multiple FINDINGS_LOG.md lines, returning only Kalshi-relevant deliveries."""
    results = []
    for line in content.split("\n"):
        parsed = parse_findings_line(line)
        if parsed:
            results.append(parsed)
    return results


def main():
    parser = argparse.ArgumentParser(description="CCA Research Outcomes Tracker")
    sub = parser.add_subparsers(dest="command")

    # add
    add_p = sub.add_parser("add", help="Add a new delivery")
    add_p.add_argument("--session", type=int, required=True)
    add_p.add_argument("--title", required=True)
    add_p.add_argument("--category", required=True, choices=VALID_CATEGORIES)
    add_p.add_argument("--description", required=True)
    add_p.add_argument("--target", required=True)

    # list
    list_p = sub.add_parser("list", help="List deliveries")
    list_p.add_argument("--status", choices=VALID_STATUSES)

    # update
    upd_p = sub.add_parser("update", help="Update delivery status")
    upd_p.add_argument("id")
    upd_p.add_argument("--status", required=True, choices=VALID_STATUSES)
    upd_p.add_argument("--notes")
    upd_p.add_argument("--profit-cents", type=int)

    # roi
    sub.add_parser("roi", help="Show ROI metrics")

    # pending
    sub.add_parser("pending", help="List pending pickups")

    # summary
    sub.add_parser("summary", help="Show summary report")

    # import-findings
    imp_p = sub.add_parser("import-findings", help="Import Kalshi findings from FINDINGS_LOG.md")
    imp_p.add_argument("--file", default=os.path.join(
        os.path.dirname(SCRIPT_DIR), "FINDINGS_LOG.md"))
    imp_p.add_argument("--session", type=int, default=0,
                        help="Override session number for all imports")

    args = parser.parse_args()
    tracker = OutcomeTracker()

    if args.command == "add":
        d = tracker.add_delivery(args.session, args.title, args.category, args.description, args.target)
        tracker.save()
        print(f"Added: {d.delivery_id} — {d.title}")

    elif args.command == "list":
        items = tracker.filter_by_status(args.status) if args.status else tracker.deliveries
        for d in items:
            print(f"  {d.delivery_id}  S{d.session}  [{d.status:12s}]  {d.title}")

    elif args.command == "update":
        tracker.update_status(args.id, args.status)
        if args.notes:
            tracker._get_delivery(args.id).notes = args.notes
        if args.profit_cents is not None:
            tracker._get_delivery(args.id).profit_impact_cents = args.profit_cents
        tracker.save()
        print(f"Updated: {args.id} -> {args.status}")

    elif args.command == "roi":
        metrics = tracker.compute_roi()
        for k, v in metrics.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.1%}")
            else:
                print(f"  {k}: {v}")

    elif args.command == "pending":
        pending = tracker.pending_pickups()
        if not pending:
            print("No pending pickups.")
        for d in pending:
            print(f"  S{d.session}: {d.title} ({d.category}) -> {d.target_chat}")

    elif args.command == "summary":
        print(tracker.summary_report())

    elif args.command == "import-findings":
        if not os.path.exists(args.file):
            print(f"File not found: {args.file}")
            sys.exit(1)
        with open(args.file) as f:
            content = f.read()
        parsed = parse_findings_content(content)
        items = []
        for p in parsed:
            session = args.session if args.session else 0
            items.append({
                "session": session,
                "title": p["title"],
                "category": p["category"],
                "description": p["description"],
                "target_chat": p["target_chat"],
            })
        added = tracker.bulk_add(items)
        tracker.save()
        print(f"Parsed {len(parsed)} Kalshi findings, added {len(added)} new (deduped)")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
