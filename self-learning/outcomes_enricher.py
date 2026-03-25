#!/usr/bin/env python3
"""outcomes_enricher.py — Enrich research_outcomes.jsonl with missing REQ delivery entries.

Parses CCA_TO_POLYBOT.md to find REQ-xxx deliveries that were made but never recorded
in research_outcomes.jsonl. Adds them with proper req_id fields so the ROI resolver
can match ACKs by exact req_id instead of fuzzy matching.

Usage:
    python3 self-learning/outcomes_enricher.py scan [--polybot-path PATH]
    python3 self-learning/outcomes_enricher.py enrich [--outcomes-path PATH] [--polybot-path PATH] [--dry-run]

Stdlib only. No external dependencies.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTCOMES_PATH = os.path.join(SCRIPT_DIR, "research_outcomes.jsonl")
DEFAULT_POLYBOT_PATH = os.path.expanduser("~/.claude/cross-chat/CCA_TO_POLYBOT.md")

# Known REQ category mappings (from delivery context)
REQ_CATEGORIES: Dict[str, str] = {
    "REQ-025": "academic_paper",
    "REQ-027": "tool",
    "REQ-028": "academic_paper",
    "REQ-030": "framework",
    "REQ-031": "framework",
    "REQ-032": "signal",
    "REQ-033": "signal",
    "REQ-034": "framework",
    "REQ-035": "signal",
    "REQ-036": "framework",
    "REQ-037": "signal",
    "REQ-038": "tool",
    "REQ-039": "framework",
    "REQ-040": "tool",
}

# Regex for REQ-NNN in headers
REQ_IN_HEADER = re.compile(r"REQ-(\d+)")
SESSION_IN_HEADER = re.compile(r"S(\d+)")
DATE_IN_HEADER = re.compile(r"\[(\d{4}-\d{2}-\d{2}[^\]]*)\]")

# Header patterns that indicate a CCA delivery/response
DELIVERY_HEADER = re.compile(
    r"^##\s+\[.*?\].*?REQ-\d+.*?(?:DELIVERY|RESPONSE|COMPLETE|BUILT|UPDATE|STATUS)",
    re.IGNORECASE,
)


def parse_req_deliveries(text: str) -> List[dict]:
    """Parse CCA_TO_POLYBOT.md text to extract REQ delivery records.

    Returns list of dicts with: req_id, title, session, date
    Deduplicates by req_id (keeps first occurrence).
    """
    if not text or not text.strip():
        return []

    seen_reqs: Dict[str, dict] = {}
    lines = text.splitlines()

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped.startswith("##"):
            continue

        # Find all REQ-NNN in this header line
        req_matches = REQ_IN_HEADER.findall(line_stripped)
        if not req_matches:
            continue

        # Check it's a delivery/response header (not a random mention)
        if not DELIVERY_HEADER.match(line_stripped):
            # Also match "Responding to: REQ-NNN" pattern
            if "Responding to:" not in line_stripped and "REQ-" not in line_stripped:
                continue

        # Extract date
        date_match = DATE_IN_HEADER.search(line_stripped)
        date_str = date_match.group(1).strip() if date_match else ""

        # Extract session
        session_match = SESSION_IN_HEADER.search(line_stripped)
        session_num = int(session_match.group(1)) if session_match else None

        # Extract title (text after the REQ reference)
        title = _extract_title(line_stripped)

        for req_num in req_matches:
            # Normalize to 3-digit: REQ-4 -> REQ-004
            padded = req_num.zfill(3)
            req_id = f"REQ-{padded}"
            # Skip REQ-001 through REQ-009 (covered by batch ACK)
            if int(padded) <= 9:
                continue
            if req_id not in seen_reqs:
                seen_reqs[req_id] = {
                    "req_id": req_id,
                    "title": _known_title(req_id) or title,
                    "session": session_num,
                    "date": date_str,
                }

    return list(seen_reqs.values())


# Known clean titles for REQ deliveries (from CCA_TO_POLYBOT.md context)
_KNOWN_TITLES: Dict[str, str] = {
    "REQ-025": "Second Edge Research (verified academic sources)",
    "REQ-027": "Monte Carlo + Synthetic Bet Generator + Edge Stability",
    "REQ-028": "FLB Confirmed for Economic Data Contracts",
    "REQ-030": "Convergence Detector Integration Spec",
    "REQ-031": "Synthetic Bet Generator Validation",
    "REQ-032": "Economics Sniper Q&A (5 questions answered)",
    "REQ-033": "NO@91-92c Statistical Analysis",
    "REQ-034": "Monte Carlo + Synthetic Integration Plan",
    "REQ-035": "Daily Sniper Interim Analysis (10/10 paper wins)",
    "REQ-036": "CLV Tracking Design",
    "REQ-037": "Maker-Side Limit Order Feasibility",
    "REQ-038": "Cross-Chat Learning Loop Functions",
    "REQ-039": "MakerSniperStrategy Architecture Design",
    "REQ-040": "Monte Carlo Bankroll Simulator",
}


def _known_title(req_id: str) -> Optional[str]:
    """Return known clean title for a REQ, or None."""
    return _KNOWN_TITLES.get(req_id)


def _extract_title(header_line: str) -> str:
    """Extract a readable title from a header line."""
    # Remove the ## prefix and date bracket
    cleaned = re.sub(r"^##\s+", "", header_line)
    cleaned = re.sub(r"\[.*?\]\s*", "", cleaned)
    # Remove common prefixes
    cleaned = re.sub(r"^[—-]+\s*", "", cleaned)
    cleaned = re.sub(r"^(?:ACK|STATUS UPDATE|UPDATE \d+|DELIVERY|RESPONSE|COMPLETE)\s*[—:-]*\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^Responding to:\s*", "", cleaned, flags=re.IGNORECASE)
    # Remove REQ-NNN prefix from title
    cleaned = re.sub(r"^REQ-\d+\s*[+&]\s*REQ-\d+\s*", "", cleaned)
    cleaned = re.sub(r"^REQ-\d+\s*", "", cleaned)
    # Clean up remaining separators
    cleaned = re.sub(r"^[—:-]+\s*", "", cleaned)
    cleaned = re.sub(r"\s*[—-]+\s*S\d+.*$", "", cleaned)
    return cleaned.strip()


def find_missing_reqs(deliveries: List[dict], existing: List[dict]) -> List[dict]:
    """Find REQ deliveries not yet in existing outcomes."""
    existing_req_ids = {e.get("req_id") for e in existing if e.get("req_id")}
    return [d for d in deliveries if d["req_id"] not in existing_req_ids]


def build_outcome_entry(
    delivery: dict,
    category: Optional[str] = None,
) -> dict:
    """Build a research_outcomes.jsonl entry from a parsed delivery."""
    req_id = delivery["req_id"]
    title = delivery.get("title", "")

    # Generate deterministic delivery_id from req_id
    hash_input = req_id.encode()
    delivery_id = "d-" + hashlib.sha256(hash_input).hexdigest()[:8]

    # Use known category or default
    if category is None:
        category = REQ_CATEGORIES.get(req_id, "signal")

    return {
        "delivery_id": delivery_id,
        "session": delivery.get("session"),
        "title": f"{req_id}: {title}" if title else req_id,
        "category": category,
        "description": f"CCA delivery responding to {req_id}",
        "target_chat": "kalshi_monitoring",
        "status": "delivered",
        "req_id": req_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def enrich_outcomes_file(
    deliveries: List[dict],
    outcomes_path: str = DEFAULT_OUTCOMES_PATH,
    category_overrides: Optional[Dict[str, str]] = None,
) -> int:
    """Add missing REQ deliveries to research_outcomes.jsonl.

    Returns count of entries added.
    """
    # Load existing
    existing = []
    if os.path.exists(outcomes_path):
        with open(outcomes_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        existing.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    missing = find_missing_reqs(deliveries, existing)
    if not missing:
        return 0

    # Append new entries
    with open(outcomes_path, "a") as f:
        for delivery in missing:
            cat = (category_overrides or {}).get(delivery["req_id"])
            entry = build_outcome_entry(delivery, category=cat)
            f.write(json.dumps(entry) + "\n")

    return len(missing)


def main():
    parser = argparse.ArgumentParser(description="Enrich research_outcomes.jsonl with missing REQ entries")
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="Show REQ deliveries found in CCA_TO_POLYBOT.md")
    scan_p.add_argument("--polybot-path", default=DEFAULT_POLYBOT_PATH)

    enrich_p = sub.add_parser("enrich", help="Add missing REQ entries to outcomes file")
    enrich_p.add_argument("--outcomes-path", default=DEFAULT_OUTCOMES_PATH)
    enrich_p.add_argument("--polybot-path", default=DEFAULT_POLYBOT_PATH)
    enrich_p.add_argument("--dry-run", action="store_true", help="Show what would be added")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Read CCA_TO_POLYBOT.md
    if not os.path.exists(args.polybot_path):
        print(f"Error: {args.polybot_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(args.polybot_path) as f:
        text = f.read()

    deliveries = parse_req_deliveries(text)

    if args.command == "scan":
        print(f"Found {len(deliveries)} REQ deliveries:")
        for d in sorted(deliveries, key=lambda x: x["req_id"]):
            s = str(d.get('session') or '?')
            print(f"  {d['req_id']:8s} S{s:>4s}  {d.get('title', '?')[:60]}")

    elif args.command == "enrich":
        if args.dry_run:
            existing = []
            if os.path.exists(args.outcomes_path):
                with open(args.outcomes_path) as f:
                    for line in f:
                        if line.strip():
                            try:
                                existing.append(json.loads(line.strip()))
                            except json.JSONDecodeError:
                                continue
            missing = find_missing_reqs(deliveries, existing)
            print(f"Would add {len(missing)} entries:")
            for d in missing:
                print(f"  {d['req_id']:8s} {d.get('title', '?')[:60]}")
        else:
            added = enrich_outcomes_file(deliveries, args.outcomes_path)
            print(f"Added {added} entries to {args.outcomes_path}")


if __name__ == "__main__":
    main()
