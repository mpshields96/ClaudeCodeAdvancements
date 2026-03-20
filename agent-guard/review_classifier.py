#!/usr/bin/env python3
"""Review Classifier — MT-20 Senior Dev Agent: CRScore-style finding classifier.

Maps SATD/effort finding text to a review category with a priority score.
Categories and scores from CRScore (NAACL 2025, arXiv:2409.19801):

  bugfix:        8.53  — null/crash/error/exception handling
  refactoring:   7.1   — extract/simplify/deduplicate/rename
  testing:       6.8   — add test/coverage/mock/assert
  logging:       6.1   — add log/debug/trace output
  documentation: 5.9   — docstring/comment/explain
  style:         5.0   — format/lint/whitespace/naming

Higher score = more impactful review finding type.
Used by senior_dev_hook.py to prioritize what gets surfaced to Claude.
"""

import re
from dataclasses import dataclass
from typing import Optional


# CRScore-grounded category scores (NAACL 2025, arXiv:2409.19801)
CATEGORY_SCORES: dict = {
    "bugfix": 8.53,
    "refactoring": 7.1,
    "testing": 6.8,
    "logging": 6.1,
    "documentation": 5.9,
    "style": 5.0,
}

# Keyword → category mapping (ordered by priority; first match wins)
# Note: keywords like "fix" and "error" are intentionally excluded from bugfix —
# they're too generic and appear in testing/style contexts ("fix lint", "error paths").
# Bugfix requires stronger, unambiguous indicators.
_KEYWORD_RULES = [
    # bugfix: crash, null/None handling, exception, broken, fail — strong signals only
    (
        "bugfix",
        re.compile(
            r"\b(bug|crash|null|none|exception|fail|broken|undefined|segfault|panic|corrupt)\b",
            re.IGNORECASE,
        ),
    ),
    # refactoring: structural code improvement
    (
        "refactoring",
        re.compile(
            r"\b(refactor|extract|rename|move|split|simplify|duplicate|complex|abstract|restructure)\b"
            r"|de.?dup",  # de-dup, dedup, de-duped
            re.IGNORECASE,
        ),
    ),
    # testing: test coverage
    (
        "testing",
        re.compile(
            r"\b(test|coverage|mock|assert|spec|pytest|unittest|fixture|stub)\b",
            re.IGNORECASE,
        ),
    ),
    # logging: observability
    (
        "logging",
        re.compile(
            r"\b(logging|logger|debug|trace|warn|info|monitor|observ|metric|telemetry)\b"
            r"|\blog\b",  # "log" as standalone word
            re.IGNORECASE,
        ),
    ),
    # documentation: comments, docstrings, readability
    (
        "documentation",
        re.compile(
            r"\b(doc|comment|docstring|readme|explain|clarify|describe|document)\b",
            re.IGNORECASE,
        ),
    ),
    # style: formatting, linting, naming
    (
        "style",
        re.compile(
            r"\b(style|format|indent|lint|pep8|whitespace|naming|convention|spacing)\b",
            re.IGNORECASE,
        ),
    ),
]

# Default fallback when no keyword matches
_DEFAULT_CATEGORY = "style"


@dataclass
class ReviewCategory:
    name: str
    score: float

    def to_dict(self) -> dict:
        return {"name": self.name, "score": self.score}


class ReviewClassifier:
    """Classifies finding text into a review category with a CRScore-based priority."""

    def classify(self, text) -> ReviewCategory:
        """Classify text into the highest-priority matching category."""
        if not text:
            name = _DEFAULT_CATEGORY
            return ReviewCategory(name=name, score=CATEGORY_SCORES[name])

        text_str = str(text)

        for category_name, pattern in _KEYWORD_RULES:
            if pattern.search(text_str):
                return ReviewCategory(
                    name=category_name,
                    score=CATEGORY_SCORES[category_name],
                )

        # Fallback to default
        return ReviewCategory(name=_DEFAULT_CATEGORY, score=CATEGORY_SCORES[_DEFAULT_CATEGORY])

    def priority_score(self, category: str) -> float:
        """Return the priority score for a named category, or 0.0 if unknown."""
        return CATEGORY_SCORES.get(category, 0.0)

    def classify_findings(self, findings: list) -> list:
        """
        Classify a list of finding dicts, adding 'category' and 'category_score' fields.
        Returns findings sorted by category_score descending (highest priority first).
        """
        if not findings:
            return []

        result = []
        for finding in findings:
            msg = finding.get("message", "")
            cat = self.classify(msg)
            enriched = dict(finding)
            enriched["category"] = cat.name
            enriched["category_score"] = cat.score
            result.append(enriched)

        result.sort(key=lambda f: f["category_score"], reverse=True)
        return result
