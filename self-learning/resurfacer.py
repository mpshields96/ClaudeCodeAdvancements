#!/usr/bin/env python3
"""
MT-10 Phase 3B: Findings Re-surfacing Module

Parses FINDINGS_LOG.md into structured data and matches findings to
current work context (frontier, module, keywords, MT task).

Surfaces relevant past reviews so knowledge from previous sessions
isn't lost — e.g., when working on context-monitor, automatically
surface findings tagged with Frontier 3.

Usage:
    from resurfacer import resurface, format_resurface_report

    # Find relevant findings for current work
    results = resurface("FINDINGS_LOG.md", module="context-monitor")
    print(format_resurface_report(results, "context-monitor improvements"))

    # Or match by frontier number, keywords, MT task
    results = resurface("FINDINGS_LOG.md", frontier=3, keywords=["compaction"])
    results = resurface("FINDINGS_LOG.md", mt_task="MT-17")
    results = resurface("FINDINGS_LOG.md", keywords=["trading", "Kalshi"])

CLI:
    python3 self-learning/resurfacer.py FINDINGS_LOG.md --module context-monitor
    python3 self-learning/resurfacer.py FINDINGS_LOG.md --frontier 3
    python3 self-learning/resurfacer.py FINDINGS_LOG.md --keywords trading Kalshi
    python3 self-learning/resurfacer.py FINDINGS_LOG.md --mt MT-17
"""

import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class Finding:
    """One parsed entry from FINDINGS_LOG.md."""
    date: str
    verdict: str
    tags: list[str]
    raw_tags: str
    title: str
    description: str
    url: str

    def to_dict(self) -> dict:
        return asdict(self)

    def __repr__(self) -> str:
        return f"Finding({self.verdict}, {self.title!r}, tags={self.tags})"


# ── Module-to-frontier mapping ───────────────────────────────────────────────

MODULE_FRONTIER_MAP = {
    "memory-system": 1,
    "spec-system": 2,
    "context-monitor": 3,
    "agent-guard": 4,
    "usage-dashboard": 5,
}


def module_to_frontier(module_name: str) -> int | None:
    """Map a module directory name to its frontier number."""
    return MODULE_FRONTIER_MAP.get(module_name)


# ── Parsing ──────────────────────────────────────────────────────────────────

# Pattern: [date] [VERDICT] [tags] title — description — url
_ENTRY_RE = re.compile(
    r'^\[(\d{4}-\d{2}-\d{2})\]\s+'     # date
    r'\[([A-Z][-A-Z]*)\]\s+'            # verdict (BUILD, ADAPT, REFERENCE, etc.)
    r'\[([^\]]+)\]\s+'                   # tags in brackets
    r'(.+)$'                             # rest (title + description + url)
)

# Extract frontier numbers and MT task numbers from tag strings
_FRONTIER_RE = re.compile(r'Frontier\s+(\d+)')
_MT_RE = re.compile(r'MT-(\d+)')

# Common tag keywords that map to known categories
_TAG_CATEGORIES = {
    "Trading": "Trading",
    "Kalshi": "Trading",
    "Memory": "Frontier 1",
    "Spec": "Frontier 2",
    "Context": "Frontier 3",
    "Agent": "Frontier 4",
    "Usage": "Frontier 5",
}


def _parse_tags(raw_tags: str) -> list[str]:
    """Extract structured tags from raw tag string.

    Input: "Frontier 5: Usage Dashboard + Frontier 3: Context Health"
    Output: ["Frontier 5", "Frontier 3"]

    Input: "MT-17: Design"
    Output: ["MT-17"]

    Input: "Trading/Kalshi"
    Output: ["Trading"]
    """
    tags = []

    # Extract Frontier N references
    for m in _FRONTIER_RE.finditer(raw_tags):
        tags.append(f"Frontier {m.group(1)}")

    # Extract MT-N references
    for m in _MT_RE.finditer(raw_tags):
        tags.append(f"MT-{m.group(1)}")

    # Extract category keywords
    for keyword, tag in _TAG_CATEGORIES.items():
        if keyword.lower() in raw_tags.lower() and tag not in tags:
            tags.append(tag)

    # If nothing matched, use raw as-is
    if not tags:
        tags.append(raw_tags.strip())

    return tags


def _parse_body(body: str) -> tuple[str, str, str]:
    """Split the body into title, description, and URL.

    The body after the tags looks like:
    'CShip — Rust statusline for CC with cost... — https://reddit.com/...'

    We split on ' — ' and take the last segment starting with http as URL.
    """
    url = ""
    # Extract URL from end
    url_match = re.search(r'https?://\S+$', body.strip())
    if url_match:
        url = url_match.group(0)
        body = body[:url_match.start()].strip()
        # Remove trailing separator
        body = body.rstrip(" —-").strip()

    # Split title from description on first ' — '
    parts = body.split(" — ", 1)
    title = parts[0].strip()
    description = parts[1].strip() if len(parts) > 1 else title

    # Clean up title — remove leading/trailing quotes and point counts
    title = title.strip('"')

    return title, description, url


def parse_findings_log(content: str) -> list[Finding]:
    """Parse FINDINGS_LOG.md content into Finding objects.

    Each line is one finding in the format:
    [date] [VERDICT] [tags] title — description — url
    """
    findings = []

    for line in content.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        match = _ENTRY_RE.match(line)
        if not match:
            continue

        date = match.group(1)
        verdict = match.group(2)
        raw_tags = match.group(3)
        body = match.group(4)

        tags = _parse_tags(raw_tags)
        title, description, url = _parse_body(body)

        findings.append(Finding(
            date=date,
            verdict=verdict,
            tags=tags,
            raw_tags=raw_tags,
            title=title,
            description=description,
            url=url,
        ))

    return findings


# ── Matching ─────────────────────────────────────────────────────────────────

VERDICT_PRIORITY = {
    "BUILD": 0,
    "ADAPT": 1,
    "REFERENCE": 2,
    "REFERENCE-PERSONAL": 3,
    "SKIP": 4,
}


def match_findings(
    findings: list[Finding],
    *,
    frontier: int | None = None,
    keywords: list[str] | None = None,
    module: str | None = None,
    mt_task: str | None = None,
    include_skip: bool = False,
    limit: int | None = None,
) -> list[Finding]:
    """Match findings against work context filters.

    Args:
        findings: Parsed findings list
        frontier: Frontier number (1-5) or 0 for "all non-SKIP"
        keywords: Text search terms (matched against title + description + raw_tags)
        module: Module directory name (auto-maps to frontier)
        mt_task: Master task ID like "MT-17"
        include_skip: Whether to include SKIP-verdict findings
        limit: Max results to return

    Returns:
        Matched findings sorted by verdict priority (BUILD first).
    """
    # Resolve module to frontier if provided
    if module and frontier is None:
        frontier = module_to_frontier(module)

    results = []

    for f in findings:
        # Skip SKIP verdicts by default
        if not include_skip and f.verdict == "SKIP":
            continue

        matched = False

        # frontier=0 means "all" (match everything that passes SKIP filter)
        if frontier == 0:
            matched = True
        elif frontier is not None:
            tag_key = f"Frontier {frontier}"
            if tag_key in f.tags:
                matched = True

        # MT task match
        if mt_task is not None:
            if mt_task in f.tags:
                matched = True

        # Keyword match (any keyword in title, description, or raw_tags)
        if keywords:
            searchable = f"{f.title} {f.description} {f.raw_tags}".lower()
            if any(kw.lower() in searchable for kw in keywords):
                matched = True

        if matched:
            results.append(f)

    # Sort by verdict priority
    results.sort(key=lambda f: VERDICT_PRIORITY.get(f.verdict, 5))

    if limit is not None:
        results = results[:limit]

    return results


# ── Main API ─────────────────────────────────────────────────────────────────

def resurface(
    log_path: str,
    *,
    frontier: int | None = None,
    keywords: list[str] | None = None,
    module: str | None = None,
    mt_task: str | None = None,
    include_skip: bool = False,
    limit: int | None = None,
) -> list[Finding]:
    """Load FINDINGS_LOG.md and return matched findings.

    Safe: returns empty list if file doesn't exist.
    """
    path = Path(log_path)
    if not path.exists():
        return []

    content = path.read_text()
    findings = parse_findings_log(content)
    return match_findings(
        findings,
        frontier=frontier,
        keywords=keywords,
        module=module,
        mt_task=mt_task,
        include_skip=include_skip,
        limit=limit,
    )


def format_resurface_report(findings: list[Finding], context: str = "") -> str:
    """Format matched findings as a readable report.

    Returns a markdown-formatted string suitable for injection into
    session context or display to user.
    """
    if not findings:
        return f"No relevant past findings for: {context}" if context else "No relevant past findings."

    lines = []
    if context:
        lines.append(f"## Relevant Past Findings for: {context}")
    else:
        lines.append("## Relevant Past Findings")
    lines.append("")

    for f in findings:
        verdict_marker = f"[{f.verdict}]"
        lines.append(f"- {verdict_marker} **{f.title}** ({f.date})")
        # Show description truncated to 120 chars
        desc = f.description[:120] + "..." if len(f.description) > 120 else f.description
        lines.append(f"  {desc}")
        if f.url:
            lines.append(f"  {f.url}")
        lines.append("")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Surface relevant findings from FINDINGS_LOG.md")
    parser.add_argument("log_path", help="Path to FINDINGS_LOG.md")
    parser.add_argument("--frontier", type=int, help="Frontier number (1-5, or 0 for all)")
    parser.add_argument("--module", help="Module name (e.g., context-monitor)")
    parser.add_argument("--mt", dest="mt_task", help="Master task (e.g., MT-17)")
    parser.add_argument("--keywords", nargs="+", help="Search keywords")
    parser.add_argument("--include-skip", action="store_true", help="Include SKIP verdicts")
    parser.add_argument("--limit", type=int, help="Max results")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    results = resurface(
        args.log_path,
        frontier=args.frontier,
        keywords=args.keywords,
        module=args.module,
        mt_task=args.mt_task,
        include_skip=args.include_skip,
        limit=args.limit,
    )

    if args.json:
        import json
        print(json.dumps([f.to_dict() for f in results], indent=2))
    else:
        context_parts = []
        if args.module:
            context_parts.append(f"module={args.module}")
        if args.frontier:
            context_parts.append(f"frontier={args.frontier}")
        if args.mt_task:
            context_parts.append(f"task={args.mt_task}")
        if args.keywords:
            context_parts.append(f"keywords={','.join(args.keywords)}")

        context = ", ".join(context_parts) or "all"
        print(format_resurface_report(results, context))


if __name__ == "__main__":
    main()
