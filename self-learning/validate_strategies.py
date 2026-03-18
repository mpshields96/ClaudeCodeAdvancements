#!/usr/bin/env python3
"""
validate_strategies.py — Strategy validation loop for SKILLBOOK.md.

Checks if recent session evidence confirms or contradicts active strategies.
Runs at session wrap time to keep the Skillbook honest.

Components:
  - StrategyValidator: reads Skillbook + journal, produces validation report
  - ValidationResult: per-strategy outcome (CONFIRMED/CONTRADICTED/UNCHANGED)
  - validate_all(): entry point — reads Skillbook, checks against journal

Evidence matching rules:
  - A strategy is CONFIRMED if recent journal entries contain evidence keywords
    AND the outcome was positive (success, improvement, win)
  - A strategy is CONTRADICTED if recent entries show the strategy was followed
    but produced negative outcomes (failure, regression, waste)
  - A strategy is UNCHANGED if no relevant evidence found in recent sessions

Usage:
    python3 validate_strategies.py              # Full validation report
    python3 validate_strategies.py --brief      # One-line summary
    python3 validate_strategies.py --json       # JSON output

Stdlib only. No external dependencies.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

_THIS_DIR = Path(__file__).parent
_SKILLBOOK_PATH = _THIS_DIR / "SKILLBOOK.md"
_JOURNAL_PATH = _THIS_DIR / "journal.jsonl"

# How many days of journal entries to consider "recent"
_RECENT_DAYS = 7


# ── Data Structures ────────────────────────────────────────────────────────


@dataclass
class Strategy:
    """A strategy extracted from SKILLBOOK.md."""
    id: str
    name: str
    confidence: int
    directive: str
    keywords: list  # extracted from directive for matching


@dataclass
class ValidationResult:
    """Result of validating one strategy against evidence."""
    strategy_id: str
    strategy_name: str
    current_confidence: int
    outcome: str  # CONFIRMED, CONTRADICTED, UNCHANGED
    evidence_count: int
    evidence_summary: str
    recommended_confidence: int

    def to_dict(self) -> dict:
        return asdict(self)


# ── Strategy Extraction ─────────────────────────────────────────────────────


def extract_strategies(content: str, min_confidence: int = 30) -> list:
    """
    Extract strategies from SKILLBOOK.md content.

    Returns list of Strategy objects with keywords derived from directives.
    """
    strategies = []
    pattern = re.compile(
        r'###\s+(S\d+):\s+(.+?)\s*—\s*Confidence:\s*(\d+)(?:\s*\(.*?\))?\s*\n'
        r'\*\*Directive:\*\*\s*"([^"]+)"',
        re.MULTILINE,
    )

    for match in pattern.finditer(content):
        sid = match.group(1)
        name = match.group(2).strip()
        confidence = int(match.group(3))
        directive = match.group(4).strip()

        if confidence < min_confidence:
            continue

        # Extract keywords from directive
        keywords = _extract_keywords(directive)

        strategies.append(Strategy(
            id=sid,
            name=name,
            confidence=confidence,
            directive=directive,
            keywords=keywords,
        ))

    return strategies


def _extract_keywords(directive: str) -> list:
    """Extract significant keywords from a directive for matching against journal entries."""
    # Remove common words, keep significant terms
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "must", "can", "could", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into", "through",
        "during", "before", "after", "above", "below", "between", "out",
        "this", "that", "these", "those", "it", "its", "and", "but", "or",
        "not", "no", "only", "just", "very", "all", "each", "every", "any",
        "when", "if", "than", "then", "also", "up", "so", "about", "which",
        "their", "them", "they", "we", "our", "you", "your", "he", "she",
    }

    # Tokenize and filter
    words = re.findall(r'[a-z]{3,}', directive.lower())
    keywords = [w for w in words if w not in stop_words]

    # Also extract multi-word phrases (2-grams)
    words_raw = directive.lower().split()
    for i in range(len(words_raw) - 1):
        bigram = words_raw[i] + " " + words_raw[i + 1]
        clean = re.sub(r'[^a-z ]', '', bigram).strip()
        if len(clean) > 5 and clean not in stop_words:
            keywords.append(clean)

    return list(set(keywords))[:15]  # Cap at 15 keywords


# ── Journal Reading ─────────────────────────────────────────────────────────


def load_recent_journal(days: int = _RECENT_DAYS) -> list:
    """Load journal entries from the last N days."""
    if not _JOURNAL_PATH.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    entries = []

    try:
        with open(_JOURNAL_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Parse timestamp
                    ts_str = entry.get("timestamp", "")
                    if ts_str:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        if ts >= cutoff:
                            entries.append(entry)
                except (json.JSONDecodeError, ValueError):
                    continue
    except OSError:
        return []

    return entries


# ── Validation Logic ────────────────────────────────────────────────────────


class StrategyValidator:
    """Validates strategies against journal evidence."""

    def __init__(self, strategies: list = None, journal_entries: list = None):
        self.strategies = strategies or []
        self.entries = journal_entries or []

    def validate_strategy(self, strategy: Strategy) -> ValidationResult:
        """
        Validate a single strategy against journal evidence.

        Matching: check if any journal entry's content matches strategy keywords.
        Outcome: positive outcomes (success, improvement) = CONFIRMED,
                 negative outcomes (failure, regression) = CONTRADICTED.
        """
        matching_entries = []
        positive = 0
        negative = 0

        for entry in self.entries:
            # Build searchable text from entry
            text = " ".join([
                str(entry.get("event_type", "")),
                str(entry.get("notes", "")),
                str(entry.get("outcome", "")),
                " ".join(entry.get("learnings", [])) if isinstance(entry.get("learnings"), list) else str(entry.get("learnings", "")),
                str(entry.get("description", "")),
            ]).lower()

            # Check keyword match
            matches = sum(1 for kw in strategy.keywords if kw in text)
            if matches >= 2:  # Need at least 2 keyword matches
                matching_entries.append(entry)
                outcome = str(entry.get("outcome", "")).lower()
                if outcome in ("success", "improvement", "win", "completed", "validated"):
                    positive += 1
                elif outcome in ("failure", "regression", "loss", "failed", "broken"):
                    negative += 1

        evidence_count = len(matching_entries)

        if evidence_count == 0:
            return ValidationResult(
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                current_confidence=strategy.confidence,
                outcome="UNCHANGED",
                evidence_count=0,
                evidence_summary="No recent evidence found",
                recommended_confidence=strategy.confidence,
            )

        # Determine outcome
        if positive > negative:
            outcome = "CONFIRMED"
            bump = min(5, positive * 2)  # +2 per positive, max +5
            recommended = min(100, strategy.confidence + bump)
            summary = f"{positive} positive, {negative} negative out of {evidence_count} matches"
        elif negative > positive:
            outcome = "CONTRADICTED"
            drop = min(10, negative * 3)  # -3 per negative, max -10
            recommended = max(0, strategy.confidence - drop)
            summary = f"{negative} negative, {positive} positive out of {evidence_count} matches"
        else:
            outcome = "UNCHANGED"
            recommended = strategy.confidence
            summary = f"{evidence_count} matches, {positive} positive, {negative} negative (balanced)"

        return ValidationResult(
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            current_confidence=strategy.confidence,
            outcome=outcome,
            evidence_count=evidence_count,
            evidence_summary=summary,
            recommended_confidence=recommended,
        )

    def validate_all(self) -> list:
        """Validate all strategies. Returns list of ValidationResult."""
        return [self.validate_strategy(s) for s in self.strategies]


# ── Public API ──────────────────────────────────────────────────────────────


def validate_all(days: int = _RECENT_DAYS) -> list:
    """
    Full validation: read Skillbook + journal, validate all strategies.

    Returns list of ValidationResult.
    """
    content = ""
    if _SKILLBOOK_PATH.exists():
        try:
            content = _SKILLBOOK_PATH.read_text()
        except OSError:
            content = ""

    strategies = extract_strategies(content, min_confidence=30)
    entries = load_recent_journal(days=days)
    validator = StrategyValidator(strategies, entries)
    return validator.validate_all()


# ── CLI ─────────────────────────────────────────────────────────────────────


def main():
    args = sys.argv[1:]
    brief = "--brief" in args
    json_output = "--json" in args

    results = validate_all()

    if json_output:
        print(json.dumps([r.to_dict() for r in results], indent=2))
        return

    if brief:
        confirmed = sum(1 for r in results if r.outcome == "CONFIRMED")
        contradicted = sum(1 for r in results if r.outcome == "CONTRADICTED")
        unchanged = sum(1 for r in results if r.outcome == "UNCHANGED")
        print(f"Strategy validation: {confirmed} confirmed, {contradicted} contradicted, {unchanged} unchanged ({len(results)} total)")
        return

    # Full report
    print("=" * 60)
    print("STRATEGY VALIDATION REPORT")
    print(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Evidence window: last {_RECENT_DAYS} days")
    print(f"Strategies checked: {len(results)}")
    print("=" * 60)

    for r in results:
        marker = {"CONFIRMED": "+", "CONTRADICTED": "-", "UNCHANGED": "="}[r.outcome]
        confidence_change = r.recommended_confidence - r.current_confidence
        change_str = f" ({'+' if confidence_change > 0 else ''}{confidence_change})" if confidence_change != 0 else ""
        print(f"\n  [{marker}] {r.strategy_id}: {r.strategy_name}")
        print(f"      Outcome: {r.outcome}  |  Evidence: {r.evidence_count} entries")
        print(f"      Confidence: {r.current_confidence} -> {r.recommended_confidence}{change_str}")
        if r.evidence_summary:
            print(f"      Summary: {r.evidence_summary}")

    # Summary
    confirmed = sum(1 for r in results if r.outcome == "CONFIRMED")
    contradicted = sum(1 for r in results if r.outcome == "CONTRADICTED")
    print(f"\n{'=' * 60}")
    print(f"CONFIRMED: {confirmed}  |  CONTRADICTED: {contradicted}  |  UNCHANGED: {len(results) - confirmed - contradicted}")


if __name__ == "__main__":
    main()
