#!/usr/bin/env python3
"""mt_originator.py — MT-41: Synthetic MT Origination.

Scans FINDINGS_LOG.md for BUILD verdicts not covered by existing MTs,
scores them by recency and community signal, clusters similar findings,
and proposes new MTs. Phase 2-3 adds cluster scoring, MASTER_TASKS.md
append, and /cca-init briefing integration.

Usage:
    python3 mt_originator.py                    # Show uncovered BUILD proposals
    python3 mt_originator.py --save             # Save proposals to mt_proposals.jsonl
    python3 mt_originator.py --json             # JSON output
    python3 mt_originator.py --briefing         # Show top proposals for /cca-init
    python3 mt_originator.py --append           # Append top proposals to MASTER_TASKS.md

Stdlib only. No external dependencies. One file = one job.
"""

import json
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from datetime import date
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINDINGS_LOG_PATH = os.path.join(SCRIPT_DIR, "FINDINGS_LOG.md")
PROPOSALS_PATH = os.path.join(SCRIPT_DIR, "mt_proposals.jsonl")
MASTER_TASKS_PATH = os.path.join(SCRIPT_DIR, "MASTER_TASKS.md")
CROSS_CHAT_PATH = os.path.expanduser("~/.claude/cross-chat/POLYBOT_TO_CCA.md")

# Pattern: [date] [VERDICT] [frontier/tag] title — url
FINDING_RE = re.compile(
    r'^\[(\d{4}-\d{2}-\d{2})\]\s+'
    r'\[(\w+(?:-\w+)?)\]\s+'
    r'\[([^\]]+)\]\s+'
    r'(.+?)(?:\s*—\s*(https?://\S+))?$'
)

POINTS_RE = re.compile(r'\((\d+)pts')

MT_HEADER_RE = re.compile(r'^## MT-(\d+):')


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
class PhaseExtension:
    """A proposed new phase for an existing MT from a partially-matched BUILD finding."""
    mt_id: int
    mt_name: str
    finding: Finding
    score: float
    suggested_phase: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["finding"] = asdict(self.finding)
        return d

    def briefing_line(self) -> str:
        """One-line summary for briefing output."""
        return f"[{self.score:.1f}] MT-{self.mt_id} ({self.mt_name}): {self.suggested_phase}"


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
    cluster_size: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    def briefing_line(self) -> str:
        """One-line summary for /cca-init briefing."""
        cluster_tag = f" ({self.cluster_size} findings)" if self.cluster_size > 1 else ""
        return f"[{self.score:.1f}] {self.name}{cluster_tag} — {self.frontier}"


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


# --- Phase 2: Cluster detection and enhanced scoring ---


def _cluster_key(finding: Finding) -> str:
    """Generate a cluster key from frontier. Findings with same frontier cluster together."""
    frontier = finding.frontier.strip().lower()
    # Normalize frontier names
    if "memory" in frontier:
        return "memory"
    elif "context" in frontier:
        return "context"
    elif "agent" in frontier or "guard" in frontier:
        return "agent-guard"
    elif "usage" in frontier or "dashboard" in frontier:
        return "usage"
    elif "spec" in frontier:
        return "spec"
    elif "new" == frontier:
        # NEW findings are unique — cluster by title words
        words = finding.title.lower().split()
        return f"new:{words[0]}" if words else "new:unknown"
    else:
        return frontier


def find_clusters(builds: list[Finding]) -> dict[str, list[Finding]]:
    """Group similar BUILD findings into clusters by frontier/topic.

    Findings in the same frontier are grouped together. This helps boost
    scoring for topics with multiple community signals.
    """
    if not builds:
        return {}

    clusters: dict[str, list[Finding]] = defaultdict(list)
    for f in builds:
        key = _cluster_key(f)
        clusters[key].append(f)

    return dict(clusters)


def score_with_clusters(finding: Finding, cluster_size: int = 1) -> float:
    """Score a proposal with cluster boost.

    Base score from score_proposal() + cluster bonus:
    - cluster_size=1: no bonus
    - cluster_size=2: +5 points
    - cluster_size=3+: +5 + 2*(size-2), capped at +15
    """
    base = score_proposal(finding)
    if cluster_size <= 1:
        return base

    bonus = 5.0 + max(0, 2.0 * (cluster_size - 2))
    bonus = min(bonus, 15.0)

    return round(min(base + bonus, 100), 1)


def generate_rich_proposals(builds: list[Finding]) -> list[MTProposal]:
    """Generate MT proposals with cluster-aware scoring.

    Findings in the same cluster are merged into a single proposal with
    combined community signal and all source URLs.
    """
    if not builds:
        return []

    uncovered = find_uncovered_builds(builds)
    if not uncovered:
        return []

    clusters = find_clusters(uncovered)
    proposals = []

    for cluster_key, findings in clusters.items():
        cluster_size = len(findings)

        # Use highest-scoring finding as the representative
        best = max(findings, key=lambda f: score_with_clusters(f, cluster_size))

        # Combine URLs and points
        urls = "|".join(f.url for f in findings if f.url)
        total_points = sum(f.points for f in findings)

        # Use most recent date
        latest_date = max(f.date for f in findings)

        # Build merged name
        if cluster_size > 1:
            name = best.title
        else:
            name = best.title

        score = score_with_clusters(best, cluster_size)

        proposals.append(MTProposal(
            name=name,
            frontier=best.frontier,
            source_url=urls if urls else best.url,
            source_date=latest_date,
            score=score,
            description=best.title,
            points=total_points,
            cluster_size=cluster_size,
        ))

    proposals.sort(key=lambda p: p.score, reverse=True)
    return proposals


# --- Phase 1 (unchanged): Simple proposals ---


def generate_proposals(builds: list[Finding]) -> list[MTProposal]:
    """Generate MT proposals from uncovered BUILD findings (Phase 1 compat)."""
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


# --- Phase 3: MASTER_TASKS.md append + briefing ---


def find_next_mt_id(master_tasks_text: str) -> int:
    """Find the next available MT ID from MASTER_TASKS.md content."""
    max_id = -1
    for line in master_tasks_text.splitlines():
        m = MT_HEADER_RE.match(line.strip())
        if m:
            mt_id = int(m.group(1))
            if mt_id < 100:  # Skip frontier-level IDs (100+)
                max_id = max(max_id, mt_id)
    return max_id + 1


def format_mt_entry(proposal: MTProposal, mt_id: int) -> str:
    """Format a proposal as a MASTER_TASKS.md entry."""
    lines = [
        f"## MT-{mt_id}: {proposal.name}",
        "",
        f"**Source:** Auto-proposed by MT-41 (score: {proposal.score}, {proposal.source_date})",
    ]

    if proposal.cluster_size > 1:
        lines.append(f"**Community signal:** {proposal.cluster_size} related findings, {proposal.points} total points")
    elif proposal.points > 0:
        lines.append(f"**Community signal:** {proposal.points} points")

    lines.append(f"**Frontier:** {proposal.frontier}")

    # Source URLs
    urls = proposal.source_url.split("|")
    if len(urls) == 1:
        lines.append(f"**Source URL:** {urls[0]}")
    else:
        lines.append("**Source URLs:**")
        for url in urls[:5]:  # Cap at 5
            lines.append(f"- {url}")

    lines.extend([
        "",
        f"**What:** {proposal.description}",
        "",
        "**Phases:**",
        "- Phase 1: Research and feasibility assessment",
        "- Phase 2: Core implementation with TDD",
        "- Phase 3: Integration and documentation",
        "",
        "**Status:** PROPOSED",
        "",
        "---",
    ])

    return "\n".join(lines)


def append_to_master_tasks(
    proposal: MTProposal,
    path: str = MASTER_TASKS_PATH,
) -> Optional[int]:
    """Append a proposal to MASTER_TASKS.md with PROPOSED status.

    Returns the assigned MT ID, or None if the proposal is a duplicate.
    """
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Dedup check: look for proposal name in existing entries
    name_lower = proposal.name.lower()
    for line in content.splitlines():
        m = MT_HEADER_RE.match(line.strip())
        if m:
            # Check if title after "MT-N: " matches
            title_part = line.strip().split(":", 1)[-1].strip().lower()
            if name_lower in title_part or title_part in name_lower:
                return None

    mt_id = find_next_mt_id(content)
    entry = format_mt_entry(proposal, mt_id)

    # Append to file
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + entry + "\n")

    return mt_id


# --- Phase 4: Extend existing MTs with new phases ---

# MT names for briefing output (covers active + completed)
MT_NAMES: dict[int, str] = {
    0: "Kalshi Self-Learning Integration",
    1: "Maestro Visual Grid UI",
    5: "Claude Pro Bridge",
    6: "Nuclear At Will",
    7: "Trace Analysis",
    9: "Autonomous Scanning",
    10: "YoYo Self-Learning",
    11: "GitHub Intelligence",
    12: "Academic Research Papers",
    14: "Rescan Stale Subs",
    15: "GitHub Repo Tester",
    17: "Design/Reports",
    18: "Academic Writing (PRISM)",
    19: "Local LLM Fine-Tuning",
    20: "Senior Dev Agent",
    22: "Autonomous Autoloop",
    27: "CCA Nuclear v2",
    28: "Self-Learning v2",
    30: "Session Daemon",
    32: "Visual Excellence",
    33: "Strategic Intelligence Report",
    34: "Medical AI Tool",
    35: "Background Autoloop",
    36: "Session Efficiency",
    37: "Investment Portfolio",
    38: "Peak/Off-Peak Budget",
    39: "Priority Picker",
    40: "Nuclear Loop",
    41: "Synthetic MT Origination",
}


def score_extension(finding: Finding, match_strength: int = 1) -> float:
    """Score a phase extension proposal 0-100.

    Components:
    - Recency: 30 points max (decays 3 points per day)
    - Community signal: 30 points max (log scale of upvotes)
    - Match strength: 40 points max (how many keywords matched)
    """
    score = 0.0

    # Recency (30 points max)
    try:
        finding_date = date.fromisoformat(finding.date)
        days_old = (date.today() - finding_date).days
        score += max(0, 30 - days_old * 3)
    except (ValueError, TypeError):
        pass

    # Community signal (30 points max)
    if finding.points > 0:
        score += min(30, math.log(finding.points + 1) * 5)
    else:
        score += 5

    # Match strength (40 points max): 1 keyword=10, 2=20, 3+=30-40
    score += min(40, match_strength * 12)

    return round(min(max(score, 0), 100), 1)


def find_phase_extensions(builds: list[Finding]) -> list[PhaseExtension]:
    """Find BUILD findings that match existing MTs and propose new phases.

    Unlike find_uncovered_builds (which finds findings NOT covered by any MT),
    this finds findings that ARE covered — meaning they extend an existing MT.
    Covers both active AND completed MTs.
    """
    if not builds:
        return []

    # Filter to BUILD only
    builds = [f for f in builds if f.verdict == "BUILD"]
    if not builds:
        return []

    coverage = get_existing_mt_coverage()
    extensions = []

    for f in builds:
        search_text = f"{f.title} {f.frontier}".lower()

        # Find which MTs this finding matches
        for mt_id, keywords in coverage.items():
            if mt_id >= 100:  # Skip frontier-level pseudo-IDs
                continue

            matched_keywords = [kw for kw in keywords if kw in search_text]
            if not matched_keywords:
                continue

            match_strength = len(matched_keywords)
            mt_name = MT_NAMES.get(mt_id, f"MT-{mt_id}")

            # Generate a suggested phase from the finding title
            suggested = f"{f.title}"

            ext_score = score_extension(f, match_strength)

            extensions.append(PhaseExtension(
                mt_id=mt_id,
                mt_name=mt_name,
                finding=f,
                score=ext_score,
                suggested_phase=suggested,
            ))

    # Sort by score descending
    extensions.sort(key=lambda e: e.score, reverse=True)
    return extensions


def format_extension_briefing(extensions: list[PhaseExtension], n: int = 5) -> str:
    """Format top N extensions as a readable briefing string."""
    if not extensions:
        return "No phase extensions found for existing MTs."

    lines = [f"PHASE EXTENSIONS ({min(n, len(extensions))} proposals for existing MTs):\n"]
    for ext in extensions[:n]:
        lines.append(f"  {ext.briefing_line()}")
        lines.append(f"     Source: {ext.finding.url or 'N/A'} ({ext.finding.date})")
    return "\n".join(lines)


def load_proposals(path: str = PROPOSALS_PATH) -> list[MTProposal]:
    """Load proposals from JSONL file."""
    if not os.path.exists(path):
        return []

    proposals = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                proposals.append(MTProposal(
                    name=d.get("name", ""),
                    frontier=d.get("frontier", ""),
                    source_url=d.get("source_url", ""),
                    source_date=d.get("source_date", ""),
                    score=d.get("score", 0.0),
                    description=d.get("description", ""),
                    points=d.get("points", 0),
                    cluster_size=d.get("cluster_size", 1),
                ))
            except (json.JSONDecodeError, KeyError):
                continue
    return proposals


def get_top_proposals_for_briefing(
    proposals: list[MTProposal],
    n: int = 3,
    min_score: float = 0.0,
) -> list[MTProposal]:
    """Return top N proposals above min_score for /cca-init briefing."""
    filtered = [p for p in proposals if p.score >= min_score]
    filtered.sort(key=lambda p: p.score, reverse=True)
    return filtered[:n]


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


# --- MT-52 Phase 1: Intelligence-Driven Origination ---


@dataclass
class MTStatus:
    """Parsed status of an MT from MASTER_TASKS.md."""
    mt_id: int
    name: str
    status: str  # COMPLETE, PROPOSED, PAUSED, FUTURE, IN_PROGRESS

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CrossChatRequest:
    """Parsed request from POLYBOT_TO_CCA.md."""
    request_id: int
    title: str
    status: str  # OPEN, PENDING, RESOLVED, CLOSED, INFO
    priority: str  # URGENT, NORMAL, BACKGROUND
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OriginationReport:
    """Unified origination report from all 3 intelligence sources."""
    adapt_extensions: list[PhaseExtension]
    stalled_mts: list[MTStatus]
    unresolved_requests: list[CrossChatRequest]
    new_mt_proposals: list[MTProposal]

    def total_actions(self) -> int:
        return (len(self.adapt_extensions) + len(self.stalled_mts)
                + len(self.unresolved_requests) + len(self.new_mt_proposals))

    def summary(self) -> str:
        lines = [
            f"ORIGINATION REPORT — {self.total_actions()} actionable items",
            "",
        ]

        if self.adapt_extensions:
            lines.append(f"ADAPT EXTENSIONS ({len(self.adapt_extensions)}):")
            for ext in self.adapt_extensions[:5]:
                lines.append(f"  {ext.briefing_line()}")
            lines.append("")

        if self.stalled_mts:
            lines.append(f"STALLED/PROPOSED MTs ({len(self.stalled_mts)}):")
            for mt in self.stalled_mts[:5]:
                lines.append(f"  MT-{mt.mt_id}: {mt.name} [{mt.status}]")
            lines.append("")

        if self.unresolved_requests:
            lines.append(f"UNRESOLVED KALSHI REQUESTS ({len(self.unresolved_requests)}):")
            for req in self.unresolved_requests[:5]:
                lines.append(f"  REQ-{req.request_id}: {req.title} [{req.priority}]")
            lines.append("")

        if self.new_mt_proposals:
            lines.append(f"NEW MT PROPOSALS ({len(self.new_mt_proposals)}):")
            for p in self.new_mt_proposals[:5]:
                lines.append(f"  {p.briefing_line()}")
            lines.append("")

        if self.total_actions() == 0:
            lines.append("No actionable items found.")

        return "\n".join(lines)


def find_actionable_adapts(findings: list[Finding]) -> list[PhaseExtension]:
    """Find ADAPT findings that map to existing MTs and propose phase extensions.

    ADAPT findings are actionable — they contain patterns/tools worth integrating
    into existing MTs. Unlike BUILD (which may need new MTs), ADAPT extends what exists.
    """
    if not findings:
        return []

    adapts = [f for f in findings if f.verdict == "ADAPT"]
    if not adapts:
        return []

    coverage = get_existing_mt_coverage()
    extensions = []

    for f in adapts:
        search_text = f"{f.title} {f.frontier}".lower()

        for mt_id, keywords in coverage.items():
            if mt_id >= 100:  # Skip frontier pseudo-IDs
                continue

            matched_keywords = [kw for kw in keywords if kw in search_text]
            if not matched_keywords:
                continue

            match_strength = len(matched_keywords)
            mt_name = MT_NAMES.get(mt_id, f"MT-{mt_id}")
            suggested = f"Integrate: {f.title}"
            ext_score = score_extension(f, match_strength)

            extensions.append(PhaseExtension(
                mt_id=mt_id,
                mt_name=mt_name,
                finding=f,
                score=ext_score,
                suggested_phase=suggested,
            ))

    extensions.sort(key=lambda e: e.score, reverse=True)
    return extensions


# Regex for MT headers: ## MT-N: Title
_MT_STATUS_RE = re.compile(r'^##\s+MT-(\d+):\s*(.+?)$')
_STATUS_LINE_RE = re.compile(r'\*\*Status:\*\*\s*(.+)', re.IGNORECASE)


def parse_master_tasks_status(text: str) -> list[MTStatus]:
    """Parse MASTER_TASKS.md to extract MT IDs, names, and statuses."""
    if not text.strip():
        return []

    results = []
    current_id: Optional[int] = None
    current_name: Optional[str] = None

    for line in text.splitlines():
        line_stripped = line.strip()

        # Check for MT header
        m = _MT_STATUS_RE.match(line_stripped)
        if m:
            current_id = int(m.group(1))
            current_name = m.group(2).split("(")[0].strip()
            continue

        # Check for status line (must follow an MT header)
        if current_id is not None and current_name is not None:
            sm = _STATUS_LINE_RE.match(line_stripped)
            if sm:
                raw_status = sm.group(1).upper()

                # Classify status
                if "COMPLETE" in raw_status:
                    status = "COMPLETE"
                elif "PROPOSED" in raw_status:
                    status = "PROPOSED"
                elif "PAUSED" in raw_status:
                    status = "PAUSED"
                elif "FUTURE" in raw_status or "ON HOLD" in raw_status:
                    status = "FUTURE"
                elif "PHASE" in raw_status and "NEXT" in raw_status:
                    status = "IN_PROGRESS"
                elif "PHASE" in raw_status:
                    status = "IN_PROGRESS"
                else:
                    status = "FUTURE"

                results.append(MTStatus(
                    mt_id=current_id,
                    name=current_name,
                    status=status,
                ))
                current_id = None
                current_name = None

    return results


def find_stalled_mts(statuses: list[MTStatus]) -> list[MTStatus]:
    """Find MTs that are stalled (PAUSED, FUTURE, PROPOSED) and need action."""
    if not statuses:
        return []

    stalled_categories = {"PAUSED", "FUTURE", "PROPOSED"}
    return [s for s in statuses if s.status in stalled_categories]


# Cross-chat request parsing
_REQUEST_HEADER_RE = re.compile(
    r'^##\s+REQUEST\s+(\d+)\s*[—–-]\s*(.+?)\s*\[STATUS:\s*(\w+)\]',
    re.IGNORECASE,
)

_REQ_HEADER_ALT_RE = re.compile(
    r'^##\s+REQUEST\s+(\d+)\s*[—–-]\s*(.+?)$',
    re.IGNORECASE,
)


def parse_cross_chat_requests(text: str) -> list[CrossChatRequest]:
    """Parse POLYBOT_TO_CCA.md for structured requests."""
    if not text.strip():
        return []

    results = []
    current_req: Optional[dict] = None
    body_lines: list[str] = []

    for line in text.splitlines():
        line_stripped = line.strip()

        # Try primary pattern: ## REQUEST N — Title [STATUS: X]
        m = _REQUEST_HEADER_RE.match(line_stripped)
        if m:
            # Save previous request
            if current_req is not None:
                current_req["summary"] = " ".join(body_lines[:3]).strip()[:200]
                results.append(CrossChatRequest(**current_req))

            req_id = int(m.group(1))
            title = m.group(2).strip()
            status = m.group(3).upper()
            body_lines = []

            current_req = {
                "request_id": req_id,
                "title": title,
                "status": status,
                "priority": "NORMAL",
                "summary": "",
            }
            continue

        # Detect priority
        if current_req is not None:
            if "URGENT" in line_stripped.upper() and "priority" in line_stripped.lower():
                current_req["priority"] = "URGENT"
            elif "BACKGROUND" in line_stripped.upper() and "priority" in line_stripped.lower():
                current_req["priority"] = "BACKGROUND"

            # Collect body text (non-empty, non-header lines)
            if line_stripped and not line_stripped.startswith("##"):
                body_lines.append(line_stripped)

    # Save final request
    if current_req is not None:
        current_req["summary"] = " ".join(body_lines[:3]).strip()[:200]
        results.append(CrossChatRequest(**current_req))

    return results


def find_unresolved_requests(requests: list[CrossChatRequest]) -> list[CrossChatRequest]:
    """Find requests that are still OPEN or PENDING, sorted by priority."""
    if not requests:
        return []

    open_statuses = {"OPEN", "PENDING"}
    unresolved = [r for r in requests if r.status in open_statuses]

    # Sort: URGENT first, then NORMAL, then BACKGROUND
    priority_order = {"URGENT": 0, "NORMAL": 1, "BACKGROUND": 2}
    unresolved.sort(key=lambda r: priority_order.get(r.priority, 1))

    return unresolved


def unified_origination(
    findings_text: str = "",
    master_tasks_text: str = "",
    cross_chat_text: str = "",
) -> OriginationReport:
    """Run all 3 origination sources and produce a unified report.

    Sources:
    1. FINDINGS_LOG.md — ADAPT findings -> phase extensions for existing MTs
    2. MASTER_TASKS.md — stalled/proposed MTs -> activation candidates
    3. POLYBOT_TO_CCA.md — unresolved requests -> research priorities

    Also includes BUILD findings -> new MT proposals (existing Phase 1-3 logic).
    """
    # Source 1: ADAPT extensions
    findings = parse_findings_log(findings_text)
    adapt_extensions = find_actionable_adapts(findings)

    # Source 2: Stalled MTs
    statuses = parse_master_tasks_status(master_tasks_text)
    stalled_mts = find_stalled_mts(statuses)

    # Source 3: Cross-chat unresolved requests
    requests = parse_cross_chat_requests(cross_chat_text)
    unresolved = find_unresolved_requests(requests)

    # Also: BUILD -> new MT proposals (existing logic)
    builds = [f for f in findings if f.verdict == "BUILD"]
    new_proposals = generate_rich_proposals(builds)

    return OriginationReport(
        adapt_extensions=adapt_extensions,
        stalled_mts=stalled_mts,
        unresolved_requests=unresolved,
        new_mt_proposals=new_proposals,
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MT-41: Synthetic MT Origination")
    parser.add_argument("--save", action="store_true", help="Save proposals to mt_proposals.jsonl")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--briefing", action="store_true", help="Show top proposals for /cca-init")
    parser.add_argument("--append", action="store_true", help="Append top proposals to MASTER_TASKS.md")
    parser.add_argument("--extend-existing", action="store_true",
                        help="Propose new phases for existing MTs (active + completed)")
    parser.add_argument("--unified", action="store_true",
                        help="MT-52: Run all 3 origination sources (findings + stalled MTs + cross-chat)")
    parser.add_argument("--findings", default=FINDINGS_LOG_PATH, help="Path to FINDINGS_LOG.md")
    parser.add_argument("--master-tasks", default=MASTER_TASKS_PATH, help="Path to MASTER_TASKS.md")
    parser.add_argument("--cross-chat", default=CROSS_CHAT_PATH, help="Path to POLYBOT_TO_CCA.md")
    parser.add_argument("--min-score", type=float, default=30.0, help="Minimum score for surfacing")
    parser.add_argument("--top", type=int, default=3, help="Number of top proposals to show")
    args = parser.parse_args()

    text = load_findings_log(args.findings)
    findings = parse_findings_log(text)
    builds = [f for f in findings if f.verdict == "BUILD"]

    print(f"Parsed {len(findings)} findings ({len(builds)} BUILD)")

    # --unified: MT-52 intelligence-driven origination from all 3 sources
    if args.unified:
        mt_text = ""
        if os.path.exists(args.master_tasks):
            with open(args.master_tasks, "r", encoding="utf-8") as f:
                mt_text = f.read()

        cc_text = ""
        if os.path.exists(args.cross_chat):
            with open(args.cross_chat, "r", encoding="utf-8") as f:
                cc_text = f.read()

        report = unified_origination(
            findings_text=text,
            master_tasks_text=mt_text,
            cross_chat_text=cc_text,
        )

        if args.json:
            out = {
                "adapt_extensions": [e.to_dict() for e in report.adapt_extensions[:args.top]],
                "stalled_mts": [s.to_dict() for s in report.stalled_mts],
                "unresolved_requests": [r.to_dict() for r in report.unresolved_requests[:args.top]],
                "new_mt_proposals": [p.to_dict() for p in report.new_mt_proposals[:args.top]],
                "total_actions": report.total_actions(),
            }
            print(json.dumps(out, indent=2, default=str))
        else:
            print(report.summary())
        return

    # --extend-existing: propose phases for existing MTs
    if args.extend_existing:
        extensions = find_phase_extensions(builds)
        filtered = [e for e in extensions if e.score >= args.min_score]
        if args.json:
            print(json.dumps([e.to_dict() for e in filtered[:args.top]], indent=2, default=str))
        else:
            print(format_extension_briefing(filtered, n=args.top))
        return

    # Use rich proposals (Phase 2) with cluster detection
    proposals = generate_rich_proposals(builds)

    if not proposals:
        print("No uncovered BUILD findings. All BUILD verdicts map to existing MTs.")
        return

    if args.briefing:
        top = get_top_proposals_for_briefing(proposals, n=args.top, min_score=args.min_score)
        if not top:
            print("No proposals above minimum score threshold.")
            return
        print(f"\nMT PROPOSALS ({len(top)} above score {args.min_score}):\n")
        for p in top:
            print(f"  {p.briefing_line()}")
        return

    if args.append:
        top = get_top_proposals_for_briefing(proposals, n=args.top, min_score=args.min_score)
        appended = 0
        for p in top:
            mt_id = append_to_master_tasks(p)
            if mt_id is not None:
                print(f"  Appended MT-{mt_id}: {p.name}")
                appended += 1
            else:
                print(f"  Skipped (duplicate): {p.name}")
        print(f"\n{appended} proposals appended to MASTER_TASKS.md")
        return

    if args.json:
        print(json.dumps([p.to_dict() for p in proposals], indent=2))
    else:
        print(f"\n{len(proposals)} uncovered BUILD findings (not mapped to any MT):\n")
        for i, p in enumerate(proposals, 1):
            cluster_tag = f" [cluster:{p.cluster_size}]" if p.cluster_size > 1 else ""
            print(f"  {i}. [{p.score:.0f}] {p.name}{cluster_tag}")
            print(f"     Frontier: {p.frontier} | Date: {p.source_date} | Points: {p.points}")
            print(f"     URL: {p.source_url}")
            print()

    if args.save:
        save_proposals(proposals)
        print(f"Saved {len(proposals)} proposals to {PROPOSALS_PATH}")


if __name__ == "__main__":
    main()
