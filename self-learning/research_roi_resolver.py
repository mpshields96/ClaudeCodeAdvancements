#!/usr/bin/env python3
"""research_roi_resolver.py — MT-49 Phase 5: Research-to-production ROI tracking.

Bridges the gap between CCA research deliveries and their actual financial outcomes.
Parses DELIVERY_ACK.md for implementation evidence, resolves delivery statuses,
and produces ROI reports by category and by principle.

The pipeline:
  1. Parse DELIVERY_ACK.md -> structured AckEntry list
  2. Match AckEntries to research_outcomes.jsonl deliveries (by REQ-ID or fuzzy title)
  3. Update delivery statuses (delivered -> implemented/acknowledged/rejected)
  4. Aggregate ROI by category and by linked principles

Usage:
    python3 self-learning/research_roi_resolver.py resolve [--ack-path PATH] [--outcomes-path PATH]
    python3 self-learning/research_roi_resolver.py report [--json]
    python3 self-learning/research_roi_resolver.py summary

Stdlib only. No external dependencies.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

DEFAULT_OUTCOMES_PATH = os.path.join(SCRIPT_DIR, "research_outcomes.jsonl")
DEFAULT_ACK_PATH = os.path.expanduser("~/.claude/cross-chat/DELIVERY_ACK.md")

# Patterns for parsing DELIVERY_ACK.md
# Matches: ## [date] — ACK REQ-NNN STATUS (session)
ACK_HEADER_RE = re.compile(
    r"##\s+\[?(\d{4}-\d{2}-\d{2}[^]]*)\]?\s*[—-]+\s*ACK\s+"
    r"(?:REQ-(\d+)\s+)?(IMPLEMENTED|PARTIAL|REJECTED|REVIEWED|NOTED)"
    r"(?:\s*\(?(S\d+)\)?)?",
    re.IGNORECASE,
)
# Matches: ## [date] — ACK REQ-NNN (session) — no explicit status
ACK_REQ_NO_STATUS_RE = re.compile(
    r"##\s+\[?(\d{4}-\d{2}-\d{2}[^]]*)\]?\s*[—-]+\s*ACK\s+"
    r"REQ-(\d+)\s*\(?(S\d+)\)?",
    re.IGNORECASE,
)
# Matches: ### REQ-NNN ... | IMPLEMENTED | ... | date
LEGACY_ACK_RE = re.compile(
    r"###\s+(?:REQ-(\d+).*?)\s*\|\s*(IMPLEMENTED|PARTIAL|REJECTED|REVIEWED)",
    re.IGNORECASE,
)
# Matches: ### REQ-NNN through REQ-MMM | IMPLEMENTED | ...
BATCH_ACK_RE = re.compile(
    r"###\s+REQ-(\d+)\s+through\s+REQ-(\d+)\s*\|\s*(IMPLEMENTED|PARTIAL|REJECTED)",
    re.IGNORECASE,
)


@dataclass
class AckEntry:
    """A parsed acknowledgment from DELIVERY_ACK.md."""
    req_id: Optional[str] = None
    status: str = "unknown"
    date: Optional[str] = None
    session: Optional[str] = None
    description: str = ""
    commit: Optional[str] = None


def parse_delivery_acks(text: str) -> List[AckEntry]:
    """Parse DELIVERY_ACK.md text into structured AckEntry list."""
    if not text or not text.strip():
        return []

    entries = []
    lines = text.splitlines()

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Try modern format: ## [date] — ACK REQ-NNN STATUS
        m = ACK_HEADER_RE.search(line_stripped)
        if m:
            date_str, req_num, status_str, session_str = m.groups()
            # Collect description from subsequent lines
            desc_lines = []
            for j in range(i + 1, min(i + 10, len(lines))):
                if lines[j].strip().startswith("##"):
                    break
                if lines[j].strip():
                    desc_lines.append(lines[j].strip())

            entry = AckEntry(
                req_id=f"REQ-{req_num}" if req_num else None,
                status=_normalize_status(status_str),
                date=_clean_date(date_str),
                session=session_str,
                description=" ".join(desc_lines),
            )
            entries.append(entry)
            continue

        # Try no-status format: ## [date] — ACK REQ-NNN (session)
        m = ACK_REQ_NO_STATUS_RE.search(line_stripped)
        if m:
            date_str, req_num, session_str = m.groups()
            desc_lines = []
            for j in range(i + 1, min(i + 10, len(lines))):
                if lines[j].strip().startswith("##"):
                    break
                if lines[j].strip():
                    desc_lines.append(lines[j].strip())

            entry = AckEntry(
                req_id=f"REQ-{req_num}",
                status="acknowledged",
                date=_clean_date(date_str),
                session=session_str,
                description=" ".join(desc_lines),
            )
            entries.append(entry)
            continue

        # Try batch format: ### REQ-NNN through REQ-MMM | STATUS | ...
        m = BATCH_ACK_RE.search(line_stripped)
        if m:
            start_num, end_num, status_str = m.groups()
            parts = line_stripped.split("|")
            date_str = parts[3].strip() if len(parts) > 3 else None
            # Collect description from subsequent lines
            desc_lines = []
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].strip().startswith("#"):
                    break
                if lines[j].strip():
                    desc_lines.append(lines[j].strip())
            desc = " ".join(desc_lines)

            # Create one entry per REQ in range, all sharing the description
            for rn in range(int(start_num), int(end_num) + 1):
                entry = AckEntry(
                    req_id=f"REQ-{rn:03d}",
                    status=_normalize_status(status_str),
                    date=date_str,
                    description=desc,
                )
                entries.append(entry)
            continue

        # Try legacy format: ### REQ-NNN | STATUS | ...
        m = LEGACY_ACK_RE.search(line_stripped)
        if m:
            req_num, status_str = m.groups()
            # Extract date from the pipe-separated format
            parts = line_stripped.split("|")
            date_str = parts[3].strip() if len(parts) > 3 else None
            # Collect description
            desc_lines = []
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].strip().startswith("#"):
                    break
                if lines[j].strip():
                    desc_lines.append(lines[j].strip())

            entry = AckEntry(
                req_id=f"REQ-{req_num}" if req_num else None,
                status=_normalize_status(status_str),
                date=date_str,
                description=" ".join(desc_lines),
            )
            entries.append(entry)

    return entries


def _normalize_status(status: str) -> str:
    """Normalize ACK status to research_outcomes status vocabulary."""
    s = status.strip().upper()
    if s == "IMPLEMENTED":
        return "implemented"
    elif s == "PARTIAL":
        return "acknowledged"
    elif s in ("REJECTED", "DEFERRED"):
        return "rejected"
    elif s in ("REVIEWED", "NOTED"):
        return "acknowledged"
    return "acknowledged"


def _clean_date(date_str: str) -> str:
    """Extract YYYY-MM-DD from a date string that may contain time/UTC info."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", date_str)
    return m.group(1) if m else date_str


def _load_outcomes(path: str) -> List[dict]:
    """Load research_outcomes.jsonl."""
    if not os.path.exists(path):
        return []
    results = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return results


_STOPWORDS = frozenset(
    "a an the is was were be been being have has had do does did will would "
    "shall should may might can could of in on at to for with by from as or "
    "and but not no its it this that these those are am".split()
)


def _fuzzy_match_score(ack_desc: str, delivery_title: str, delivery_desc: str) -> float:
    """Word-overlap fuzzy match score between ACK and delivery.

    Uses overlap / min(len) to avoid penalizing long ACK descriptions.
    Filters stopwords for better signal.
    """
    if not ack_desc:
        return 0.0
    ack_words = {w for w in ack_desc.lower().split() if w not in _STOPWORDS and len(w) > 2}
    target_words = {w for w in f"{delivery_title} {delivery_desc}".lower().split()
                    if w not in _STOPWORDS and len(w) > 2}
    if not target_words or not ack_words:
        return 0.0
    overlap = ack_words & target_words
    # Use min denominator so long descriptions don't dilute score
    return len(overlap) / min(len(ack_words), len(target_words))


def resolve_deliveries(
    acks: List[AckEntry],
    outcomes_path: str = DEFAULT_OUTCOMES_PATH,
) -> List[dict]:
    """Match ACK entries to research_outcomes deliveries and produce update records.

    Returns list of dicts: {delivery_id, old_status, new_status, matched_by, ack_date}
    """
    deliveries = _load_outcomes(outcomes_path)
    if not deliveries or not acks:
        return []

    updates = []
    matched_delivery_ids = set()

    for ack in acks:
        best_match = None
        best_score = 0.0
        match_method = None

        # Priority 1: Exact REQ-ID match (highest confidence)
        if ack.req_id:
            for d in deliveries:
                if d["delivery_id"] in matched_delivery_ids:
                    continue
                if d.get("req_id") == ack.req_id:
                    best_match = d
                    best_score = 1.0
                    match_method = "req_id"
                    break

        # Priority 2: Session number match
        if best_match is None and ack.session:
            session_num = ack.session.replace("S", "")
            for d in deliveries:
                if d["delivery_id"] in matched_delivery_ids:
                    continue
                if str(d.get("session", "")) == session_num:
                    best_match = d
                    match_method = "session"
                    best_score = 1.0
                    break

        # Priority 3: Fuzzy title/description match
        if best_match is None:
            ack_text = " ".join(filter(None, [ack.req_id, ack.description, ack.session]))
            for d in deliveries:
                if d["delivery_id"] in matched_delivery_ids:
                    continue
                score = _fuzzy_match_score(
                    ack_text,
                    d.get("title", ""),
                    d.get("description", ""),
                )
                if score > best_score and score >= 0.15:
                    best_match = d
                    best_score = score
                    match_method = "fuzzy"

        if best_match and best_score >= 0.15:
            matched_delivery_ids.add(best_match["delivery_id"])
            updates.append({
                "delivery_id": best_match["delivery_id"],
                "old_status": best_match.get("status", "delivered"),
                "new_status": ack.status,
                "matched_by": match_method,
                "match_score": round(best_score, 3),
                "ack_date": ack.date,
            })

    return updates


def roi_by_category(deliveries: List[dict]) -> Dict[str, dict]:
    """Aggregate ROI metrics by research category."""
    categories = defaultdict(lambda: {
        "total": 0,
        "implemented": 0,
        "profitable": 0,
        "unprofitable": 0,
        "net_profit_cents": 0,
        "implementation_rate": 0.0,
    })

    for d in deliveries:
        cat = d.get("category", "unknown")
        status = d.get("status", "delivered")
        profit = d.get("profit_impact_cents") or 0

        categories[cat]["total"] += 1
        if status in ("implemented", "profitable", "unprofitable"):
            categories[cat]["implemented"] += 1
        if status == "profitable":
            categories[cat]["profitable"] += 1
            categories[cat]["net_profit_cents"] += profit
        elif status == "unprofitable":
            categories[cat]["unprofitable"] += 1
            categories[cat]["net_profit_cents"] += profit

    # Calculate rates
    for cat_data in categories.values():
        if cat_data["total"] > 0:
            cat_data["implementation_rate"] = round(
                cat_data["implemented"] / cat_data["total"], 3
            )

    return dict(categories)


def roi_by_principle(feedback_entries: List[dict]) -> Dict[str, dict]:
    """Aggregate ROI by linked principle IDs from outcome feedback entries."""
    if not feedback_entries:
        return {}

    principles = defaultdict(lambda: {
        "total_outcomes": 0,
        "profitable": 0,
        "unprofitable": 0,
        "net_profit_cents": 0,
        "win_rate": 0.0,
    })

    for entry in feedback_entries:
        principle_ids = entry.get("principle_ids", [])
        outcome = entry.get("outcome", "")
        profit = entry.get("profit_cents", 0) or 0

        for pid in principle_ids:
            principles[pid]["total_outcomes"] += 1
            principles[pid]["net_profit_cents"] += profit
            if outcome == "profitable":
                principles[pid]["profitable"] += 1
            elif outcome == "unprofitable":
                principles[pid]["unprofitable"] += 1

    # Calculate win rates
    for p_data in principles.values():
        if p_data["total_outcomes"] > 0:
            p_data["win_rate"] = round(
                p_data["profitable"] / p_data["total_outcomes"], 3
            )

    return dict(principles)


class ROIResolver:
    """Full ROI resolver pipeline.

    Combines two resolution sources:
    1. DELIVERY_ACK.md parsing (manual acknowledgments from monitoring chat)
    2. Kalshi bot git commit scanning (automated implementation detection)
    """

    def __init__(
        self,
        outcomes_path: str = DEFAULT_OUTCOMES_PATH,
        ack_path: str = DEFAULT_ACK_PATH,
        kalshi_repo_path: Optional[str] = None,
    ):
        self.outcomes_path = outcomes_path
        self.ack_path = ack_path
        self.kalshi_repo_path = kalshi_repo_path or os.path.expanduser(
            "~/Projects/polymarket-bot"
        )

    def run(self) -> dict:
        """Run the full resolve + ROI pipeline. Returns JSON-serializable report."""
        # Load
        deliveries = _load_outcomes(self.outcomes_path)
        ack_text = ""
        if os.path.exists(self.ack_path):
            with open(self.ack_path) as f:
                ack_text = f.read()

        # Source 1: Parse & resolve from DELIVERY_ACK.md
        acks = parse_delivery_acks(ack_text)
        updates = resolve_deliveries(acks, self.outcomes_path)

        # Source 2: Scan Kalshi bot git commits for REQ implementations
        commit_updates = self._scan_commits()

        # Merge: commit_updates fill gaps not covered by ACK-based resolution
        resolved_delivery_ids = {u["delivery_id"] for u in updates}
        for cu in commit_updates:
            if cu["delivery_id"] not in resolved_delivery_ids:
                updates.append(cu)
                resolved_delivery_ids.add(cu["delivery_id"])

        # Apply updates to delivery copies for ROI calculation
        delivery_map = {d["delivery_id"]: dict(d) for d in deliveries}
        for u in updates:
            did = u["delivery_id"]
            if did in delivery_map:
                delivery_map[did]["status"] = u["new_status"]

        updated_deliveries = list(delivery_map.values())
        by_cat = roi_by_category(updated_deliveries)

        # Status summary
        status_counts = defaultdict(int)
        for d in updated_deliveries:
            status_counts[d.get("status", "delivered")] += 1

        return {
            "total_deliveries": len(deliveries),
            "resolved": len(updates),
            "updates": updates,
            "by_category": by_cat,
            "by_status": dict(status_counts),
        }

    def _scan_commits(self) -> List[dict]:
        """Scan Kalshi bot commits for REQ implementations."""
        try:
            from commit_scanner import scan_commits, get_git_log, match_commits_to_outcomes
            log_text = get_git_log(self.kalshi_repo_path, 200)
            if not log_text:
                return []
            commits = scan_commits(log_text)
            return match_commits_to_outcomes(commits, self.outcomes_path)
        except (ImportError, Exception):
            return []


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Research-to-production ROI resolver")
    sub = parser.add_subparsers(dest="command")

    resolve_p = sub.add_parser("resolve", help="Resolve delivery statuses from ACK file")
    resolve_p.add_argument("--ack-path", default=DEFAULT_ACK_PATH)
    resolve_p.add_argument("--outcomes-path", default=DEFAULT_OUTCOMES_PATH)

    report_p = sub.add_parser("report", help="Full ROI report")
    report_p.add_argument("--json", action="store_true")
    report_p.add_argument("--ack-path", default=DEFAULT_ACK_PATH)
    report_p.add_argument("--outcomes-path", default=DEFAULT_OUTCOMES_PATH)

    sub.add_parser("summary", help="Brief ROI summary")

    args = parser.parse_args()

    if args.command == "resolve":
        resolver = ROIResolver(args.outcomes_path, args.ack_path)
        report = resolver.run()
        print(f"Resolved {report['resolved']}/{report['total_deliveries']} deliveries")
        for u in report["updates"]:
            print(f"  {u['delivery_id']}: {u['old_status']} -> {u['new_status']} (via {u['matched_by']})")

    elif args.command == "report":
        resolver = ROIResolver(
            getattr(args, "outcomes_path", DEFAULT_OUTCOMES_PATH),
            getattr(args, "ack_path", DEFAULT_ACK_PATH),
        )
        report = resolver.run()
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2))
        else:
            print(f"Total deliveries: {report['total_deliveries']}")
            print(f"Resolved: {report['resolved']}")
            print(f"\nBy status: {json.dumps(report['by_status'], indent=2)}")
            print(f"\nBy category:")
            for cat, data in report["by_category"].items():
                print(f"  {cat}: {data['total']} total, {data['implemented']} impl, "
                      f"net={data['net_profit_cents']}c")

    elif args.command == "summary":
        resolver = ROIResolver()
        report = resolver.run()
        print(f"Deliveries: {report['total_deliveries']}, "
              f"Resolved: {report['resolved']}, "
              f"By status: {report['by_status']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
