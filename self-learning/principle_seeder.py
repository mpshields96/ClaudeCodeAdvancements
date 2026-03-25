#!/usr/bin/env python3
"""principle_seeder.py — Bootstrap principle registry from LEARNINGS.md, journal, and findings.

Seeds the principle_registry with principles derived from:
1. LEARNINGS.md — severity-tracked patterns already distilled by humans
2. journal.jsonl — recurring pain/win patterns detected programmatically
3. FINDINGS_LOG.md — community-validated BUILD/ADAPT verdicts from nuclear scans

This bridges the gap between raw data (journal, learnings, findings) and the
principle_registry → predictive_recommender pipeline.

Usage:
    python3 self-learning/principle_seeder.py seed-learnings [--min-severity 1]
    python3 self-learning/principle_seeder.py seed-journal
    python3 self-learning/principle_seeder.py seed-findings [--min-points 50]
    python3 self-learning/principle_seeder.py seed-all
    python3 self-learning/principle_seeder.py status

Stdlib only. No external dependencies.
"""
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from principle_registry import add_principle, _load_principles, VALID_DOMAINS

DEFAULT_LEARNINGS_PATH = os.path.join(PROJECT_ROOT, "LEARNINGS.md")
DEFAULT_JOURNAL_PATH = os.path.join(SCRIPT_DIR, "journal.jsonl")
DEFAULT_PRINCIPLES_PATH = os.path.join(SCRIPT_DIR, "principles.jsonl")
DEFAULT_FINDINGS_PATH = os.path.join(PROJECT_ROOT, "FINDINGS_LOG.md")

# Minimum occurrences of a journal pattern before it becomes a principle
MIN_PATTERN_OCCURRENCES = 3


@dataclass
class Learning:
    """A parsed learning from LEARNINGS.md."""

    title: str
    severity: int
    count: int
    anti_pattern: str
    fix: str
    first_seen: str
    last_seen: str
    files: str


# Domain keyword mapping — maps learning content to principle domains
DOMAIN_KEYWORDS = {
    "code_quality": [
        "credential",
        "regex",
        "api key",
        "security",
        "guard",
        "scanner",
        "validation",
        "test",
        "quality",
        "lint",
        "format",
        "type",
        "import",
        "dependency",
    ],
    "cca_operations": [
        "hook",
        "pretooluse",
        "posttooluse",
        "stop hook",
        "compact",
        "context",
        "token",
        "tool",
        "claude code",
        "claude.md",
        "command",
        "slash",
        "system-reminder",
    ],
    "nuclear_scan": [
        "reddit",
        "subreddit",
        "scan",
        "nuclear",
        "fetch",
        "url",
        "findings",
        "post",
        "github",
    ],
    "session_management": [
        "session",
        "wrap",
        "commit",
        "resume",
        "handoff",
        "init",
        "autoloop",
        "state",
    ],
    "trading_research": [
        "trading",
        "kalshi",
        "bet",
        "market",
        "strategy",
        "edge",
        "profit",
        "polymarket",
        "signal",
    ],
    "trading_execution": [
        "execution",
        "fill",
        "order",
        "slippage",
    ],
}


def parse_learnings_md(path: str) -> list:
    """Parse LEARNINGS.md into a list of Learning objects.

    Format expected:
        ### Title — Severity: N — Count: N
        - **Anti-pattern:** ...
        - **Fix:** ...
        - **First seen:** YYYY-MM-DD
        - **Last seen:** YYYY-MM-DD
        - **Files:** ...
    """
    if not os.path.isfile(path):
        return []

    with open(path) as f:
        content = f.read()

    learnings = []
    # Split on ### headers
    header_pattern = re.compile(
        r"^### (.+?) — Severity: (\d+) — Count: (\d+)", re.MULTILINE
    )

    matches = list(header_pattern.finditer(content))
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        severity = int(match.group(2))
        count = int(match.group(3))

        # Extract body text between this header and the next
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end]

        anti_pattern = _extract_field(body, "Anti-pattern")
        fix = _extract_field(body, "Fix")
        first_seen = _extract_field(body, "First seen")
        last_seen = _extract_field(body, "Last seen")
        files = _extract_field(body, "Files")

        learnings.append(
            Learning(
                title=title,
                severity=severity,
                count=count,
                anti_pattern=anti_pattern,
                fix=fix,
                first_seen=first_seen,
                last_seen=last_seen,
                files=files,
            )
        )

    return learnings


def _extract_field(body: str, field_name: str) -> str:
    """Extract a **Field:** value from learning body text."""
    pattern = re.compile(
        rf"\*\*{re.escape(field_name)}:\*\*\s*(.+?)(?:\n|$)", re.IGNORECASE
    )
    match = pattern.search(body)
    if match:
        return match.group(1).strip()
    return ""


def map_learning_to_domain(learning: Learning) -> str:
    """Map a learning to a principle domain based on content keywords."""
    searchable = (
        f"{learning.title} {learning.anti_pattern} {learning.fix} {learning.files}"
    ).lower()

    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in searchable)
        if score > 0:
            scores[domain] = score

    if not scores:
        return "general"

    return max(scores, key=scores.get)


def _learning_to_principle_text(learning: Learning) -> str:
    """Convert a learning into a concise principle statement."""
    if learning.fix:
        return f"{learning.title}: {learning.fix}"
    return learning.title


def _existing_principle_texts(path: str) -> set:
    """Load existing principle texts to prevent duplicates."""
    if not os.path.isfile(path):
        return set()
    texts = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    p = json.loads(line)
                    texts.add(p.get("text", ""))
                except json.JSONDecodeError:
                    continue
    return texts


def seed_principles_from_learnings(
    learnings_path: str = DEFAULT_LEARNINGS_PATH,
    principles_path: str = DEFAULT_PRINCIPLES_PATH,
    min_severity: int = 1,
) -> list:
    """Seed principle registry from LEARNINGS.md.

    Returns list of dicts describing what was seeded.
    """
    learnings = parse_learnings_md(learnings_path)
    existing = _existing_principle_texts(principles_path)

    results = []
    for learning in learnings:
        if learning.severity < min_severity:
            continue

        text = _learning_to_principle_text(learning)
        if text in existing:
            continue

        domain = map_learning_to_domain(learning)
        # Applicable domains: source domain + general
        applicable = [domain]
        if domain != "general":
            applicable.append("general")

        principle = add_principle(
            text=text,
            source_domain=domain,
            applicable_domains=applicable,
            session=0,
            source_context=f"Seeded from LEARNINGS.md (severity={learning.severity}, count={learning.count})",
            path=principles_path,
        )

        # Update usage_count based on learning count (reflects how many times seen)
        if principle and learning.count > 1:
            _update_principle_usage(principles_path, text, learning.count)

        existing.add(text)
        results.append(
            {
                "text": text,
                "domain": domain,
                "severity": learning.severity,
                "count": learning.count,
                "source_context": f"LEARNINGS.md",
            }
        )

    return results


def _update_principle_usage(path: str, text: str, count: int):
    """Update a principle's usage_count and success_count in the file.

    For learnings with count > 1, we set usage = count and success = count
    (the learning has been validated count times).
    """
    if not os.path.isfile(path):
        return
    lines = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    p = json.loads(line)
                    if p.get("text") == text:
                        p["usage_count"] = count
                        p["success_count"] = count
                    lines.append(json.dumps(p))
                except json.JSONDecodeError:
                    lines.append(line)

    with open(path, "w") as f:
        for line in lines:
            f.write(line + "\n")


def extract_journal_patterns(entries: list) -> list:
    """Extract recurring patterns from journal entries.

    Detects:
    - recurring_pain: same pain description 3+ times
    - recurring_win: same win description 3+ times
    """
    if not entries:
        return []

    patterns = []

    # Group by event_type + description
    pain_counter = Counter()
    win_counter = Counter()

    for entry in entries:
        event_type = entry.get("event_type", "")
        desc = entry.get("description", "")
        domain = entry.get("domain", "general")

        if not desc:
            continue

        if event_type == "pain":
            pain_counter[(desc, domain)] += 1
        elif event_type == "win":
            win_counter[(desc, domain)] += 1

    for (desc, domain), count in pain_counter.items():
        if count >= MIN_PATTERN_OCCURRENCES:
            patterns.append(
                {
                    "type": "recurring_pain",
                    "description": desc,
                    "domain": domain,
                    "count": count,
                    "principle_text": f"Avoid: {desc}",
                }
            )

    for (desc, domain), count in win_counter.items():
        if count >= MIN_PATTERN_OCCURRENCES:
            patterns.append(
                {
                    "type": "recurring_win",
                    "description": desc,
                    "domain": domain,
                    "count": count,
                    "principle_text": f"Continue: {desc}",
                }
            )

    return patterns


def seed_principles_from_journal(
    journal_path: str = DEFAULT_JOURNAL_PATH,
    principles_path: str = DEFAULT_PRINCIPLES_PATH,
) -> list:
    """Seed principle registry from journal pattern analysis.

    Returns list of dicts describing what was seeded.
    """
    if not os.path.isfile(journal_path):
        return []

    entries = []
    with open(journal_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    patterns = extract_journal_patterns(entries)
    existing = _existing_principle_texts(principles_path)
    results = []

    for pattern in patterns:
        text = pattern["principle_text"]
        if text in existing:
            continue

        domain = pattern.get("domain", "general")
        if domain not in VALID_DOMAINS:
            domain = "general"

        applicable = [domain]
        if domain != "general":
            applicable.append("general")

        add_principle(
            text=text,
            source_domain=domain,
            applicable_domains=applicable,
            session=0,
            source_context=f"Seeded from journal patterns (type={pattern['type']}, count={pattern['count']})",
            path=principles_path,
        )

        if pattern["count"] > 1:
            _update_principle_usage(principles_path, text, pattern["count"])

        existing.add(text)
        results.append(
            {
                "text": text,
                "domain": domain,
                "type": pattern["type"],
                "count": pattern["count"],
                "source_context": "journal.jsonl",
            }
        )

    return results


# --- Phase: Findings seeder (MT-28 growth) ---

# Reuse FINDING_RE from mt_originator pattern
FINDING_RE = re.compile(
    r'^\[(\d{4}-\d{2}-\d{2})\]\s+'
    r'\[(\w+(?:-\w+)?)\]\s+'
    r'\[([^\]]+)\]\s+'
    r'(.+?)(?:\s*—\s*(https?://\S+))?$'
)
POINTS_RE = re.compile(r'\((\d+)pts')

# Frontier -> domain mapping for findings
FRONTIER_DOMAIN_MAP = {
    "memory": "cca_operations",
    "spec": "cca_operations",
    "context": "cca_operations",
    "agent guard": "code_quality",
    "usage": "cca_operations",
    "security": "code_quality",
    "guard": "code_quality",
}


def parse_findings_for_seeding(text: str, min_points: int = 0) -> list:
    """Parse FINDINGS_LOG.md, return BUILD and ADAPT findings for seeding.

    Returns list of dicts with keys: date, verdict, frontier, title, url, points.
    """
    if not text:
        return []

    results = []
    for line in text.splitlines():
        line = line.strip()
        m = FINDING_RE.match(line)
        if not m:
            continue
        date_str, verdict, frontier, title, url = m.groups()
        url = url or ""

        if verdict not in ("BUILD", "ADAPT"):
            continue

        pm = POINTS_RE.search(title)
        points = int(pm.group(1)) if pm else 0

        if points < min_points:
            continue

        # Clean title
        title_clean = title.split("—")[0].strip().rstrip(".")
        if len(title_clean) > 120:
            title_clean = title_clean[:117] + "..."

        results.append({
            "date": date_str,
            "verdict": verdict,
            "frontier": frontier,
            "title": title_clean,
            "url": url,
            "points": points,
        })
    return results


def map_finding_to_domain(frontier: str, title: str) -> str:
    """Map a finding's frontier and title to a principle domain."""
    searchable = f"{frontier} {title}".lower()

    # Check trading keywords first (higher priority)
    trading_kws = ["kalshi", "trading", "bet", "market", "edge", "profit", "polymarket"]
    if any(kw in searchable for kw in trading_kws):
        return "trading_research"

    # Check frontier mapping
    for key, domain in FRONTIER_DOMAIN_MAP.items():
        if key in searchable:
            return domain

    # Check general domain keywords
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in searchable for kw in keywords):
            return domain

    return "general"


def finding_to_principle_text(verdict: str, title: str, frontier: str) -> str:
    """Convert a finding into a principle statement.

    BUILD findings become "Community-validated: <insight>"
    ADAPT findings become "Adapt pattern: <insight>"
    """
    # Extract the core insight from the title
    core = title.strip().strip('"').strip("'")

    frontier_tag = frontier.split(":")[-1].strip() if ":" in frontier else frontier

    if verdict == "BUILD":
        return f"Community-validated ({frontier_tag}): {core}"
    else:
        return f"Adapt pattern ({frontier_tag}): {core}"


def seed_principles_from_findings(
    findings_text: Optional[str] = None,
    findings_path: str = DEFAULT_FINDINGS_PATH,
    principles_path: str = DEFAULT_PRINCIPLES_PATH,
    min_points: int = 50,
) -> list:
    """Seed principle registry from FINDINGS_LOG.md BUILD/ADAPT verdicts.

    Args:
        findings_text: Direct text input (overrides findings_path if provided)
        findings_path: Path to FINDINGS_LOG.md (used only if findings_text is None)
        principles_path: Path to principles.jsonl
        min_points: Minimum community points to seed (filters noise)

    Returns list of dicts describing what was seeded.
    """
    if findings_text is None:
        if os.path.isfile(findings_path):
            with open(findings_path) as f:
                findings_text = f.read()
        else:
            return []

    parsed = parse_findings_for_seeding(findings_text, min_points=min_points)
    if not parsed:
        return []

    existing = _existing_principle_texts(principles_path)
    results = []

    for finding in parsed:
        text = finding_to_principle_text(
            finding["verdict"], finding["title"], finding["frontier"]
        )
        if text in existing:
            continue

        domain = map_finding_to_domain(finding["frontier"], finding["title"])
        if domain not in VALID_DOMAINS:
            domain = "general"

        applicable = [domain]
        if domain != "general":
            applicable.append("general")

        principle = add_principle(
            text=text,
            source_domain=domain,
            applicable_domains=applicable,
            session=0,
            source_context=f"Seeded from FINDINGS_LOG.md ({finding['verdict']}, {finding['points']}pts, {finding['date']})",
            path=principles_path,
        )

        existing.add(text)
        results.append({
            "text": text,
            "domain": domain,
            "verdict": finding["verdict"],
            "points": finding["points"],
            "source_context": "FINDINGS_LOG.md",
        })

    return results


def seed_all(
    learnings_path: str = DEFAULT_LEARNINGS_PATH,
    journal_path: str = DEFAULT_JOURNAL_PATH,
    findings_path: str = DEFAULT_FINDINGS_PATH,
    principles_path: str = DEFAULT_PRINCIPLES_PATH,
    min_severity: int = 1,
    min_points: int = 50,
) -> dict:
    """Seed from learnings, journal, and findings. Returns summary."""
    learnings_results = seed_principles_from_learnings(
        learnings_path, principles_path, min_severity
    )
    journal_results = seed_principles_from_journal(journal_path, principles_path)
    findings_results = seed_principles_from_findings(
        findings_path=findings_path,
        principles_path=principles_path,
        min_points=min_points,
    )

    return {
        "from_learnings": len(learnings_results),
        "from_journal": len(journal_results),
        "from_findings": len(findings_results),
        "total_seeded": len(learnings_results) + len(journal_results) + len(findings_results),
        "learnings_details": learnings_results,
        "journal_details": journal_results,
        "findings_details": findings_results,
    }


def get_status(principles_path: str = DEFAULT_PRINCIPLES_PATH) -> dict:
    """Get current principle registry status."""
    principles = _load_principles(principles_path)
    if not principles:
        return {"total": 0, "by_domain": {}, "avg_score": 0.0}

    by_domain = Counter()
    total_score = 0.0
    for p in principles.values():
        by_domain[p.source_domain] += 1
        total_score += p.score

    return {
        "total": len(principles),
        "by_domain": dict(by_domain),
        "avg_score": total_score / len(principles) if principles else 0.0,
    }


def main():
    """CLI entrypoint."""
    if len(sys.argv) < 2:
        print("Usage: principle_seeder.py [seed-learnings|seed-journal|seed-findings|seed-all|status]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "seed-learnings":
        min_sev = 1
        if "--min-severity" in sys.argv:
            idx = sys.argv.index("--min-severity")
            if idx + 1 < len(sys.argv):
                min_sev = int(sys.argv[idx + 1])
        results = seed_principles_from_learnings(min_severity=min_sev)
        print(f"Seeded {len(results)} principles from LEARNINGS.md")
        for r in results:
            print(f"  [{r['domain']}] {r['text'][:80]}")

    elif cmd == "seed-journal":
        results = seed_principles_from_journal()
        print(f"Seeded {len(results)} principles from journal patterns")
        for r in results:
            print(f"  [{r['domain']}] {r['text'][:80]}")

    elif cmd == "seed-findings":
        min_pts = 50
        if "--min-points" in sys.argv:
            idx = sys.argv.index("--min-points")
            if idx + 1 < len(sys.argv):
                min_pts = int(sys.argv[idx + 1])
        results = seed_principles_from_findings(min_points=min_pts)
        print(f"Seeded {len(results)} principles from FINDINGS_LOG.md")
        for r in results:
            print(f"  [{r['domain']}] {r['text'][:80]}")

    elif cmd == "seed-all":
        summary = seed_all()
        print(f"Seeded {summary['total_seeded']} principles total")
        print(f"  From LEARNINGS.md: {summary['from_learnings']}")
        print(f"  From journal: {summary['from_journal']}")
        print(f"  From FINDINGS_LOG: {summary.get('from_findings', 0)}")

    elif cmd == "status":
        status = get_status()
        print(f"Principle Registry: {status['total']} principles")
        print(f"  Avg score: {status['avg_score']:.2f}")
        for domain, count in sorted(status.get("by_domain", {}).items()):
            print(f"  {domain}: {count}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
