"""Parse cca-reviewer agent output into structured data for /cca-nuclear.

The cca-reviewer agent returns freeform markdown in a known format:
  REVIEW: [title]
  Source: [url]
  Score: [N] pts | [N]% upvoted | [N] comments
  FRONTIER: [name]
  RAT POISON: [CLEAN / CONTAMINATED]
  WHAT IT IS: [text]
  WHAT WE CAN STEAL: [text]
  VERDICT: [BUILD / ADAPT / REFERENCE / REFERENCE-PERSONAL / SKIP]
  WHY: [text]

This module extracts those fields into a dict for programmatic use.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReviewVerdict:
    title: str = ""
    url: str = ""
    score_pts: int = 0
    upvote_pct: int = 0
    comment_count: int = 0
    frontier: str = ""
    rat_poison: str = "UNKNOWN"
    what_it_is: str = ""
    what_to_steal: str = ""
    verdict: str = "SKIP"
    why: str = ""
    special_flags: list = field(default_factory=list)
    raw_text: str = ""

    def to_findings_log_entry(self, date: str) -> str:
        """Format as a FINDINGS_LOG.md entry."""
        frontier_str = self.frontier if self.frontier else "General"
        score_str = f"{self.score_pts}pts"
        if self.upvote_pct:
            score_str += f", {self.upvote_pct}%"
        if self.comment_count:
            score_str += f", {self.comment_count}c"

        steal = ""
        if self.verdict in ("BUILD", "ADAPT") and self.what_to_steal:
            steal = f" {self.what_to_steal}"

        flags = ""
        if self.special_flags:
            flags = " " + " ".join(f"[{f}]" for f in self.special_flags)

        return (
            f"[{date}] [{self.verdict}] [{frontier_str}] "
            f'"{self.title}" ({score_str}).{steal}{flags} '
            f"— {self.url}"
        )

    def to_condensed(self) -> str:
        """Format as condensed /cca-nuclear verdict (1-3 lines)."""
        frontier_str = self.frontier if self.frontier else "General"
        if self.verdict == "SKIP":
            reason = self.why[:50] if self.why else "not actionable"
            return f"SKIP: {self.title} ({self.score_pts} pts) — {reason}"
        elif self.verdict == "REFERENCE":
            summary = self.why[:80] if self.why else self.what_it_is[:80]
            return f"REF: {self.title} ({self.score_pts} pts) — {frontier_str} — {summary}"
        else:
            steal = self.what_to_steal[:120] if self.what_to_steal else self.why[:120]
            return (
                f"{self.verdict}: {self.title} ({self.score_pts} pts) — {frontier_str}\n"
                f"STEAL: {steal}"
            )


def parse_verdict(text: str) -> ReviewVerdict:
    """Parse cca-reviewer agent output into a ReviewVerdict."""
    v = ReviewVerdict(raw_text=text)

    # Title
    m = re.search(r"REVIEW:\s*(.+)", text)
    if m:
        v.title = m.group(1).strip()

    # Source URL
    m = re.search(r"Source:\s*(https?://\S+)", text)
    if m:
        v.url = m.group(1).strip()

    # Score line: "Score: 241 pts | 83% upvoted | 43 comments"
    m = re.search(r"Score:\s*(\d+)\s*pts?", text)
    if m:
        v.score_pts = int(m.group(1))
    m = re.search(r"(\d+)%\s*upvoted", text)
    if m:
        v.upvote_pct = int(m.group(1))
    m = re.search(r"(\d+)\s*comments?", text)
    if m:
        v.comment_count = int(m.group(1))

    # Frontier
    m = re.search(r"FRONTIER:\s*(.+)", text)
    if m:
        v.frontier = m.group(1).strip()

    # Rat poison
    m = re.search(r"RAT POISON:\s*(CLEAN|CONTAMINATED[^$]*)", text, re.IGNORECASE)
    if m:
        v.rat_poison = m.group(1).strip()

    # What it is (multiline — grab until next section header)
    m = re.search(
        r"WHAT IT IS:\s*\n(.+?)(?=\n(?:WHAT WE CAN STEAL|IMPLEMENTATION|VERDICT|WHY):)",
        text,
        re.DOTALL,
    )
    if m:
        v.what_it_is = m.group(1).strip()
    else:
        # Single line
        m = re.search(r"WHAT IT IS:\s*(.+)", text)
        if m:
            v.what_it_is = m.group(1).strip()

    # What we can steal (multiline)
    m = re.search(
        r"WHAT WE CAN STEAL:\s*\n(.+?)(?=\n(?:IMPLEMENTATION|VERDICT|WHY):)",
        text,
        re.DOTALL,
    )
    if m:
        v.what_to_steal = m.group(1).strip()
    else:
        m = re.search(r"WHAT WE CAN STEAL:\s*(.+)", text)
        if m:
            v.what_to_steal = m.group(1).strip()

    # Verdict
    m = re.search(
        r"VERDICT:\s*(BUILD|ADAPT|REFERENCE-PERSONAL|REFERENCE|SKIP)",
        text,
        re.IGNORECASE,
    )
    if m:
        v.verdict = m.group(1).upper()

    # Why (multiline — grab until end or next section)
    m = re.search(r"WHY:\s*(.+?)(?:\n\n|\Z)", text, re.DOTALL)
    if m:
        v.why = m.group(1).strip()

    # Special flags — detect from content
    lower = text.lower()
    if any(kw in lower for kw in ["self-learning", "autonomous agent", "self-improv"]):
        v.special_flags.append("POLYBOT-RELEVANT")
    if any(kw in lower for kw in ["multi-session", "tmux", "workspace", "maestro"]):
        v.special_flags.append("MAESTRO-RELEVANT")
    if any(kw in lower for kw in ["claude.md", "rules file", "project rules"]):
        v.special_flags.append("RULES-RELEVANT")
    if any(kw in lower for kw in ["token usage", "cost track", "billing", "usage dashboard"]):
        v.special_flags.append("USAGE-DASHBOARD")

    return v


def parse_multiple(text: str) -> list:
    """Parse agent output that may contain multiple REVIEW blocks."""
    blocks = re.split(r"(?=^REVIEW:)", text, flags=re.MULTILINE)
    results = []
    for block in blocks:
        block = block.strip()
        if block.startswith("REVIEW:"):
            results.append(parse_verdict(block))
    return results if results else [parse_verdict(text)]


if __name__ == "__main__":
    # Self-test with sample output
    sample = """REVIEW: Follow-up: Claude Code's source confirms the system prompt problem
Source: https://www.reddit.com/r/ClaudeCode/comments/1s99j2t/
Score: 241 pts | 83% upvoted | 43 comments

FRONTIER: Frontier 1: Memory + Frontier 4: Agent Guard
RAT POISON: CLEAN

WHAT IT IS:
Technical deep-dive confirming CC's internal system prompt hierarchy.

WHAT WE CAN STEAL:
Use <important> XML wrappers for critical CLAUDE.md directives.

IMPLEMENTATION:
- Delivery: CLAUDE.md template change
- Effort: 1 hour
- Dependencies: none

VERDICT: ADAPT
WHY: Confirms system prompt subordination. Actionable XML wrapper pattern."""

    v = parse_verdict(sample)
    assert v.title == "Follow-up: Claude Code's source confirms the system prompt problem"
    assert v.url == "https://www.reddit.com/r/ClaudeCode/comments/1s99j2t/"
    assert v.score_pts == 241
    assert v.upvote_pct == 83
    assert v.comment_count == 43
    assert v.verdict == "ADAPT"
    assert "Frontier 1" in v.frontier
    assert v.rat_poison == "CLEAN"

    log = v.to_findings_log_entry("2026-04-01")
    assert "[2026-04-01]" in log
    assert "[ADAPT]" in log

    condensed = v.to_condensed()
    assert "ADAPT:" in condensed or "REF:" in condensed

    print("All self-tests passed.")
    print(f"  Title: {v.title}")
    print(f"  Verdict: {v.verdict}")
    print(f"  Frontier: {v.frontier}")
    print(f"  Log entry: {log[:100]}...")
