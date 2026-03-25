#!/usr/bin/env python3
"""mt_originator.py — MT-41 Phase 1: Synthetic MT Origination.

Scans FINDINGS_LOG.md for BUILD verdicts not covered by existing MTs,
scores them by recency and community signal, and proposes new MTs.

Usage:
    python3 mt_originator.py                    # Show uncovered BUILD proposals
    python3 mt_originator.py --save             # Save proposals to mt_proposals.jsonl
    python3 mt_originator.py --json             # JSON output

Stdlib only. No external dependencies. One file = one job.
"""

import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import date
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINDINGS_LOG_PATH = os.path.join(SCRIPT_DIR, "FINDINGS_LOG.md")
PROPOSALS_PATH = os.path.join(SCRIPT_DIR, "mt_proposals.jsonl")

# Pattern: [date] [VERDICT] [frontier/tag] title — url
FINDING_RE = re.compile(
    r'^\[(\d{4}-\d{2}-\d{2})\]\s+'
    r'\[(\w+(?:-\w+)?)\]\s+'
    r'\[([^\]]+)\]\s+'
    r'(.+?)(?:\s*—\s*(https?://\S+))?$'
)

POINTS_RE = re.compile(r'\((\d+)pts')


@dataclass
class Finding:
    """One parsed entry from FINDINGS_LOG.md."""
    date: str
    verdict: str
    frontier: str
    title: str
    url: str
    points: int = 0


@dataclass
class MTProposal:
    """A proposed new MT from an uncovered BUILD finding."""
    name: str
    frontier: str
    source_url: str
    source_date: str
    score: float
    description: str
    points: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def parse_findings_log(text: str) -> list[Finding]:
    """Parse FINDINGS_LOG.md text into Finding objects."""
    findings = []
    for line in text.splitlines():
        line = line.strip()
        m = FINDING_RE.match(line)
        if not m:
            continue
        date_str, verdict, frontier, title, url = m.groups()
        url = url or ""

        # Extract points if present
        pm = POINTS_RE.search(title)
        points = int(pm.group(1)) if pm else 0

        # Clean title — take first sentence/phrase
        title_clean = title.split("—")[0].strip().rstrip(".")
        if len(title_clean) > 120:
            title_clean = title_clean[:117] + "..."

        findings.append(Finding(
            date=date_str,
            verdict=verdict,
            frontier=frontier,
            title=title_clean,
            url=url,
            points=points,
        ))
    return findings


def get_existing_mt_coverage() -> dict[int, list[str]]:
    """Return keyword sets for each existing MT to check coverage.

    Maps mt_id -> list of lowercase keywords that this MT covers.
    Used to determine if a BUILD finding is already addressed.
    """
    return {
        0: ["kalshi", "self-learning", "trading", "bot"],
        1: ["maestro", "grid", "visual", "session manager", "multi-session ui"],
        2: ["mermaid", "architecture diagram"],
        3: ["design review", "multi-persona", "design team"],
        4: ["design vocabulary", "ui design", "frontend design"],
        5: ["claude pro", "bridge", "pro code"],
        6: ["subreddit scanner", "nuclear", "on-demand scan"],
        7: ["trace analysis", "transcript", "ace pattern"],
        8: ["iphone", "remote control", "mobile", "ios app"],
        9: ["autonomous scan", "cross-subreddit", "intelligence gathering"],
        10: ["yoyo", "self-learning", "self-building", "evolving agent"],
        11: ["github", "trending", "repo intelligence"],
        12: ["academic paper", "arxiv", "semantic scholar"],
        13: ["ios", "xcode", "swiftui", "app development"],
        14: ["rescan", "re-scanning", "delta scan"],
        17: ["report", "design", "visual", "chart", "typst"],
        18: ["academic writing", "prism", "workspace"],
        19: ["local llm", "fine-tuning", "unsloth"],
        20: ["senior dev", "code review", "quality scoring", "satd"],
        21: ["hivemind", "multi-chat", "coordination", "worker"],
        22: ["autoloop", "desktop", "electron", "automation"],
        23: ["telegram", "discord", "channel", "mobile remote"],
        24: ["visualization", "graphics", "svg chart"],
        25: ["presentation", "slides", "grand rounds"],
        26: ["financial intelligence", "regime", "calibration", "kelly"],
        27: ["nuclear v2", "enhanced scanning", "apf"],
        28: ["self-learning v2", "principle registry", "pattern registry", "multi-domain"],
        29: ["cowork", "pro bridge"],
        30: ["session daemon", "tmux", "auto-spawn"],
        31: ["gemini", "flash", "multi-model"],
        32: ["visual excellence", "design engineering", "report charts"],
        33: ["strategic report", "intelligence report", "kalshi data"],
        34: ["medical", "openevidence", "clinical"],
        35: ["background autoloop", "non-intrusive", "pause resume"],
        36: ["efficiency", "optimizer", "session timer", "overhead"],
        37: ["investment", "portfolio", "etf", "factor model"],
        38: ["peak", "off-peak", "token budget", "rate limit"],
        39: ["priority picker", "dust", "aging"],
        40: ["nuclear loop", "automated scanning"],
        41: ["synthetic", "origination", "auto-propose"],
        # Frontier-level coverage (not MTs, but addressed by existing modules)
        100: ["memory system", "omega", "memory hook", "cross-session memory"],
        101: ["spec system", "spec-driven", "split claude.md"],
        102: ["context monitor", "context health", "context rot", "context bar", "statusline",
              "token counter", "cship", "rtk"],
        103: ["agent guard", "credential guard", "hacked", "wiped", "deleted s3",
              "port exposure", "firewall", "destructive", "rm -rf", "safeexec"],
        104: ["usage dashboard", "usage bar", "cost visibility", "token usage",
              "otel", "opentelemetry", "claude island", "devtools", "usage progress"],
        105: ["wrap-up", "self-improvement loop", "wrap skill"],
        106: ["claude squad", "multi-agent manager"],
        107: ["recon", "tmux dashboard", "ratatui"],
    }


def _keywords_match(text: str, keywords: list[str]) -> bool:
    """Check if any keywords appear in text (case-insensitive)."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def find_uncovered_builds(builds: list[Finding]) -> list[Finding]:
    """Find BUILD findings not covered by any existing MT."""
    coverage = get_existing_mt_coverage()
    all_keywords = []
    for kw_list in coverage.values():
        all_keywords.extend(kw_list)

    uncovered = []
    for f in builds:
        # Match against title + frontier only, NOT URL (URLs contain generic words like "github")
        search_text = f"{f.title} {f.frontier}"
        if not _keywords_match(search_text, all_keywords):
            uncovered.append(f)
    return uncovered


def score_proposal(finding: Finding) -> float:
    """Score a proposal 0-100 based on recency, community signal, frontier relevance.

    Components:
    - Recency: 40 points max (decays 4 points per day from today)
    - Community signal: 30 points max (based on upvote points)
    - Frontier relevance: 30 points (NEW tag gets full, specific frontier gets 20)
    """
    score = 0.0

    # Recency (40 points max, -4 per day old)
    try:
        finding_date = date.fromisoformat(finding.date)
        days_old = (date.today() - finding_date).days
        recency = max(0, 40 - days_old * 4)
    except (ValueError, TypeError):
        recency = 0
    score += recency

    # Community signal (30 points max, logarithmic scale)
    if finding.points > 0:
        import math
        signal = min(30, math.log(finding.points + 1) * 5)
    else:
        signal = 5  # Base score for no-point findings
    score += signal

    # Frontier relevance (30 points)
    frontier_lower = finding.frontier.lower()
    if "new" in frontier_lower:
        score += 30  # Completely new category
    elif any(f in frontier_lower for f in ["frontier", "mt-"]):
        score += 20  # Maps to existing frontier
    else:
        score += 10  # General

    return round(min(score, 100), 1)


def generate_proposals(builds: list[Finding]) -> list[MTProposal]:
    """Generate MT proposals from uncovered BUILD findings."""
    if not builds:
        return []

    uncovered = find_uncovered_builds(builds)
    proposals = []

    for f in uncovered:
        score = score_proposal(f)
        proposals.append(MTProposal(
            name=f.title,
            frontier=f.frontier,
            source_url=f.url,
            source_date=f.date,
            score=score,
            description=f.title,
            points=f.points,
        ))

    # Sort by score descending
    proposals.sort(key=lambda p: p.score, reverse=True)
    return proposals


def load_findings_log(path: str = FINDINGS_LOG_PATH) -> str:
    """Load FINDINGS_LOG.md content."""
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_proposals(proposals: list[MTProposal], path: str = PROPOSALS_PATH) -> None:
    """Save proposals to JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for p in proposals:
            f.write(json.dumps(p.to_dict(), separators=(",", ":")) + "\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MT-41: Synthetic MT Origination")
    parser.add_argument("--save", action="store_true", help="Save proposals to mt_proposals.jsonl")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--findings", default=FINDINGS_LOG_PATH, help="Path to FINDINGS_LOG.md")
    args = parser.parse_args()

    text = load_findings_log(args.findings)
    findings = parse_findings_log(text)
    builds = [f for f in findings if f.verdict == "BUILD"]

    print(f"Parsed {len(findings)} findings ({len(builds)} BUILD)")

    proposals = generate_proposals(builds)

    if not proposals:
        print("No uncovered BUILD findings. All BUILD verdicts map to existing MTs.")
        return

    if args.json:
        print(json.dumps([p.to_dict() for p in proposals], indent=2))
    else:
        print(f"\n{len(proposals)} uncovered BUILD findings (not mapped to any MT):\n")
        for i, p in enumerate(proposals, 1):
            print(f"  {i}. [{p.score:.0f}] {p.name}")
            print(f"     Frontier: {p.frontier} | Date: {p.source_date} | Points: {p.points}")
            print(f"     URL: {p.source_url}")
            print()

    if args.save:
        save_proposals(proposals)
        print(f"Saved {len(proposals)} proposals to {PROPOSALS_PATH}")


if __name__ == "__main__":
    main()
