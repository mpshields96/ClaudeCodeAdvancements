#!/usr/bin/env python3
"""ADR Reader — MT-20 Senior Dev Agent Full Vision: Architectural Decision Record awareness.

Discovers Architectural Decision Records (ADRs) in a project and surfaces relevant
decisions when code is written or edited, preventing accidental violations of
recorded architectural choices.

Supported ADR formats:
- MADR (Markdown ADR): ## Status section
- Nygard format: ## Status heading
- Inline: "Status: accepted" line

ADR directories searched (in priority order):
  docs/adr/, adr/, docs/decisions/, .adr/

Usage in senior_dev_hook.py:
  reader = ADRReader()
  adrs = reader.discover(project_root)
  relevant = reader.find_relevant(adrs, file_path, content)
  output = reader.hook_output(payload, relevant)
"""

import os
import re
from dataclasses import dataclass
from typing import Optional

# Directories to search for ADR files (checked in order)
_ADR_DIRS = ["docs/adr", "adr", "docs/decisions", ".adr", "doc/adr", "architecture/decisions"]

# Status keywords (normalized to lowercase)
_STATUS_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:##\s+)?status\s*:?\s*(accepted|proposed|deprecated|superseded[^\n]*)",
    re.IGNORECASE | re.MULTILINE,
)

# Keywords that make an ADR relevant to a file/content
# Maps keyword → set of trigger words that suggest the ADR is relevant
_MAX_SUMMARY_LENGTH = 200
_MAX_CONTEXT_LENGTH = 500


@dataclass
class ADR:
    path: str
    title: str
    status: str     # accepted / proposed / deprecated / superseded / unknown
    summary: str    # First substantive paragraph of the decision

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "title": self.title,
            "status": self.status,
            "summary": self.summary,
        }


def _normalize_status(raw: str) -> str:
    raw_lower = raw.strip().lower()
    if raw_lower.startswith("accepted"):
        return "accepted"
    if raw_lower.startswith("proposed"):
        return "proposed"
    if raw_lower.startswith("deprecated"):
        return "deprecated"
    if raw_lower.startswith("superseded"):
        return "superseded"
    return "unknown"


def _extract_title(content: str) -> str:
    """Extract H1 title from markdown content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return "Untitled"


def _extract_summary(content: str) -> str:
    """Extract the first substantive paragraph (skipping headers and status lines)."""
    lines = content.splitlines()
    paragraphs = []
    current = []

    for line in lines:
        stripped = line.strip()
        # Skip headers, empty lines start new paragraph
        if stripped.startswith("#"):
            if current:
                paragraphs.append(" ".join(current))
                current = []
        elif stripped == "":
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(stripped)

    if current:
        paragraphs.append(" ".join(current))

    # Return first paragraph that isn't just a status line
    for para in paragraphs:
        lower = para.lower()
        if lower.startswith("status") or lower.startswith("accepted") or \
           lower.startswith("proposed") or lower.startswith("deprecated") or \
           lower.startswith("superseded"):
            continue
        if len(para) > 10:
            return para[:_MAX_SUMMARY_LENGTH]

    return ""


def parse_adr_file(path: str, content: str) -> ADR:
    """Parse an ADR markdown file into an ADR dataclass."""
    title = _extract_title(content)
    summary = _extract_summary(content)

    # Parse status
    status = "unknown"
    m = _STATUS_PATTERN.search(content)
    if m:
        status = _normalize_status(m.group(1))

    return ADR(path=path, title=title, status=status, summary=summary)


def _extract_keywords(text: str) -> set:
    """Extract lowercase significant words (4+ chars) from text."""
    words = re.findall(r"[a-z]{4,}", text.lower())
    # Filter stop words
    stop_words = {
        "this", "that", "with", "from", "have", "will", "when", "then",
        "also", "only", "must", "should", "would", "could", "their", "there",
        "where", "which", "while", "were", "been", "make", "more", "some",
        "than", "into", "does", "what", "each",
    }
    return {w for w in words if w not in stop_words}


class ADRReader:
    """Discovers and surfaces ADRs relevant to written code."""

    def discover(self, project_root: str) -> list:
        """Scan project_root for ADR files. Returns list of ADR objects."""
        if not project_root or not os.path.isdir(project_root):
            return []

        adrs = []
        for adr_dir in _ADR_DIRS:
            full_dir = os.path.join(project_root, adr_dir)
            if not os.path.isdir(full_dir):
                continue
            for fname in sorted(os.listdir(full_dir)):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(full_dir, fname)
                rel_path = os.path.join(adr_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    adr = parse_adr_file(rel_path, content)
                    adrs.append(adr)
                except OSError:
                    continue
            if adrs:
                # Found ADRs in this directory — don't search further
                break

        return adrs

    def find_relevant(self, adrs: list, file_path: str, content: str) -> list:
        """
        Return ADRs relevant to this file/content change.

        Relevance rules:
        - Only accepted and deprecated ADRs are surfaced (actionable)
        - Deprecated: always surfaced if any keyword overlap (warns about old patterns)
        - Accepted: surfaced if meaningful keyword overlap with summary+title
        """
        if not adrs:
            return []

        # Combine file path and content keywords
        context_keywords = _extract_keywords(file_path + " " + content)

        relevant = []
        for adr in adrs:
            if adr.status not in ("accepted", "deprecated"):
                continue

            adr_keywords = _extract_keywords(adr.title + " " + adr.summary)
            overlap = context_keywords & adr_keywords

            if overlap:
                relevant.append(adr)

        return relevant

    def hook_output(self, payload: dict, relevant_adrs: list) -> dict:
        """
        Produce PostToolUse hook output for ADR findings.
        Returns {} if no relevant ADRs, or {"additionalContext": "..."} if findings.
        """
        if not payload:
            return {}

        tool_name = payload.get("tool_name", "")
        if tool_name not in ("Write", "Edit"):
            return {}

        if not relevant_adrs:
            return {}

        lines = ["[ADR] Relevant architectural decisions:"]
        for adr in relevant_adrs[:3]:  # Cap at 3 to avoid noise
            status_marker = "⚠ DEPRECATED" if adr.status == "deprecated" else "✓ accepted"
            short_summary = adr.summary[:80] + "..." if len(adr.summary) > 80 else adr.summary
            lines.append(f"  [{status_marker}] {adr.title}: {short_summary}")

        context = "\n".join(lines)
        if len(context) > _MAX_CONTEXT_LENGTH:
            context = context[:_MAX_CONTEXT_LENGTH - 3] + "..."

        return {"additionalContext": context}
