#!/usr/bin/env python3
"""commit_scanner.py — Scan Kalshi bot git commits for REQ delivery implementations.

Part of MT-49 Phase 5: automated delivery status detection. Scans the polymarket-bot
git log for commits referencing REQ-xxx identifiers, categorizes them, and matches
them to research_outcomes.jsonl entries to auto-update delivery statuses.

Usage:
    python3 self-learning/commit_scanner.py scan [--repo-path PATH] [--count N]
    python3 self-learning/commit_scanner.py match [--outcomes-path PATH] [--repo-path PATH]

Stdlib only. No external dependencies.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTCOMES_PATH = os.path.join(SCRIPT_DIR, "research_outcomes.jsonl")
DEFAULT_REPO_PATH = os.path.expanduser("~/Projects/polymarket-bot")

REQ_PATTERN = re.compile(r"REQ-(\d+)")

# Commit category priority for status resolution
STATUS_PRIORITY = {
    "implementation": "implemented",
    "testing": "implemented",
    "fix": "implemented",
    "documentation": "acknowledged",
}

CATEGORY_PRIORITY_ORDER = ["implementation", "testing", "fix", "documentation"]


@dataclass
class CommitInfo:
    """Parsed commit from git log --oneline."""
    hash: str
    message: str
    req_ids: List[str] = field(default_factory=list)
    category: str = "unknown"


def parse_commit_line(line: str) -> Optional[CommitInfo]:
    """Parse a single git log --oneline line into CommitInfo."""
    line = line.strip()
    if not line:
        return None
    parts = line.split(" ", 1)
    if len(parts) < 2:
        return CommitInfo(hash=parts[0], message="")
    return CommitInfo(hash=parts[0], message=parts[1])


def extract_req_ids(text: str) -> List[str]:
    """Extract and normalize REQ-NNN identifiers from text.

    Normalizes short forms (REQ-4 -> REQ-004). Deduplicates.
    """
    matches = REQ_PATTERN.findall(text)
    seen = set()
    result = []
    for num_str in matches:
        padded = num_str.zfill(3)
        req_id = f"REQ-{padded}"
        if req_id not in seen:
            seen.add(req_id)
            result.append(req_id)
    return result


def _categorize_commit(message: str) -> str:
    """Categorize a commit message by its conventional-commit prefix."""
    msg_lower = message.lower().strip()
    if msg_lower.startswith("feat:") or msg_lower.startswith("feat("):
        return "implementation"
    elif msg_lower.startswith("fix:") or msg_lower.startswith("fix("):
        return "implementation"
    elif msg_lower.startswith("test:") or msg_lower.startswith("test("):
        return "testing"
    elif msg_lower.startswith("docs:") or msg_lower.startswith("doc:") or msg_lower.startswith("doc("):
        return "documentation"
    elif msg_lower.startswith("refactor:") or msg_lower.startswith("refactor("):
        return "implementation"
    return "implementation"  # Default to implementation if unclear


def scan_commits(log_output: str) -> List[CommitInfo]:
    """Scan raw git log --oneline output for commits referencing REQ-xxx.

    Returns only commits that contain at least one REQ reference.
    """
    results = []
    for line in log_output.strip().splitlines():
        ci = parse_commit_line(line)
        if ci is None:
            continue
        req_ids = extract_req_ids(ci.message)
        if req_ids:
            ci.req_ids = req_ids
            ci.category = _categorize_commit(ci.message)
            results.append(ci)
    return results


def get_git_log(repo_path: str, count: int = 100) -> str:
    """Get git log --oneline from a repository."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{count}"],
            capture_output=True, text=True, timeout=10,
            cwd=repo_path,
        )
        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ""


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


def match_commits_to_outcomes(
    commits: List[CommitInfo],
    outcomes_path: str = DEFAULT_OUTCOMES_PATH,
) -> List[dict]:
    """Match scanned commits to research_outcomes entries by req_id.

    Returns list of match records: {delivery_id, req_id, commit_hash, new_status, old_status}

    For multiple commits referencing the same REQ, picks the highest-priority
    category (implementation > testing > documentation).
    """
    outcomes = _load_outcomes(outcomes_path)
    if not outcomes or not commits:
        return []

    # Build req_id -> outcome index
    req_to_outcome: Dict[str, dict] = {}
    for o in outcomes:
        rid = o.get("req_id")
        if rid:
            req_to_outcome[rid] = o

    # Group commits by req_id, pick best category
    req_to_best_commit: Dict[str, CommitInfo] = {}
    for ci in commits:
        for rid in ci.req_ids:
            existing = req_to_best_commit.get(rid)
            if existing is None:
                req_to_best_commit[rid] = ci
            else:
                # Pick higher priority category
                existing_idx = CATEGORY_PRIORITY_ORDER.index(existing.category) if existing.category in CATEGORY_PRIORITY_ORDER else 99
                new_idx = CATEGORY_PRIORITY_ORDER.index(ci.category) if ci.category in CATEGORY_PRIORITY_ORDER else 99
                if new_idx < existing_idx:
                    req_to_best_commit[rid] = ci

    # Match to outcomes
    matches = []
    for rid, ci in req_to_best_commit.items():
        outcome = req_to_outcome.get(rid)
        if outcome is None:
            continue

        new_status = STATUS_PRIORITY.get(ci.category, "acknowledged")
        old_status = outcome.get("status", "delivered")

        # Don't downgrade: implemented > acknowledged > delivered
        status_rank = {"delivered": 0, "acknowledged": 1, "implemented": 2}
        if status_rank.get(new_status, 0) <= status_rank.get(old_status, 0):
            continue

        matches.append({
            "delivery_id": outcome["delivery_id"],
            "req_id": rid,
            "commit_hash": ci.hash,
            "commit_message": ci.message,
            "old_status": old_status,
            "new_status": new_status,
            "matched_by": "commit_scan",
        })

    return matches


def main():
    parser = argparse.ArgumentParser(description="Scan Kalshi bot commits for REQ implementations")
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="Show REQ-referencing commits")
    scan_p.add_argument("--repo-path", default=DEFAULT_REPO_PATH)
    scan_p.add_argument("--count", type=int, default=100)

    match_p = sub.add_parser("match", help="Match commits to outcomes")
    match_p.add_argument("--repo-path", default=DEFAULT_REPO_PATH)
    match_p.add_argument("--outcomes-path", default=DEFAULT_OUTCOMES_PATH)
    match_p.add_argument("--count", type=int, default=200)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "scan":
        log_text = get_git_log(args.repo_path, args.count)
        commits = scan_commits(log_text)
        print(f"Found {len(commits)} REQ-referencing commits:")
        for ci in commits:
            reqs = ", ".join(ci.req_ids)
            print(f"  {ci.hash} [{ci.category:14s}] {reqs:10s} {ci.message[:60]}")

    elif args.command == "match":
        log_text = get_git_log(args.repo_path, args.count)
        commits = scan_commits(log_text)
        matches = match_commits_to_outcomes(commits, args.outcomes_path)
        if matches:
            print(f"Found {len(matches)} new status updates:")
            for m in matches:
                print(f"  {m['req_id']:8s} {m['old_status']:12s} -> {m['new_status']:12s} ({m['commit_hash']})")
        else:
            print("No new status updates found.")


if __name__ == "__main__":
    main()
