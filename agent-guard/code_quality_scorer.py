#!/usr/bin/env python3
"""Code Quality Scorer — MT-20 Senior Dev Agent: aggregate quality assessment.

Combines multiple quality signals into a single 0-100 score for a code file or diff.
Used by:
- senior_dev_hook.py (PostToolUse — real-time scoring)
- /cca-review (on-demand quality assessment of external repos/files)

Quality dimensions (mapped from Google eng-practices review framework):
1. Debt density — SATD markers per 100 LOC
2. Complexity density — control flow markers per 100 LOC
3. Size risk — LOC relative to Atlassian's 200-400 LOC review threshold
4. Documentation ratio — docstrings/comments vs code ratio
5. Naming quality — average identifier length (proxy for readability)

Output: CodeQualityReport with overall score, dimension breakdown, and grade (A-F).
"""

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
if _MODULE_DIR not in sys.path:
    sys.path.insert(0, _MODULE_DIR)

try:
    from satd_detector import SATDDetector
    _satd_available = True
except ImportError:
    _satd_available = False

# File extensions to skip
SKIP_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".txt", ".rst", ".toml", ".ini", ".cfg", ".lock"}

# Complexity markers (Python-focused but broadly applicable)
_COMPLEXITY_PATTERN = re.compile(
    r"^\s*(if |elif |else:|for |while |try:|except |with |def |class |async def |async for |async with )",
    re.MULTILINE,
)

# Docstring/comment pattern
_COMMENT_PATTERN = re.compile(r"^\s*#", re.MULTILINE)
_DOCSTRING_PATTERN = re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'')

# Identifier pattern (variable/function/class names)
_IDENTIFIER_PATTERN = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]{2,})\b")

# Reserved words to exclude from identifier analysis
_RESERVED = {
    "def", "class", "return", "import", "from", "if", "elif", "else", "for",
    "while", "try", "except", "finally", "with", "as", "pass", "break",
    "continue", "raise", "yield", "and", "or", "not", "in", "is", "None",
    "True", "False", "self", "cls", "lambda", "global", "nonlocal", "del",
    "assert", "async", "await", "print", "range", "len", "str", "int",
    "float", "list", "dict", "set", "tuple", "bool", "type", "isinstance",
    "hasattr", "getattr", "setattr", "super", "property", "staticmethod",
    "classmethod", "abstractmethod", "dataclass", "field", "Optional",
    "Union", "List", "Dict", "Set", "Tuple", "Any",
}


@dataclass
class DimensionScore:
    """Score for a single quality dimension."""
    name: str
    score: float      # 0-100
    weight: float     # 0-1
    detail: str       # Human-readable explanation

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": round(self.score, 1),
            "weight": self.weight,
            "detail": self.detail,
        }


@dataclass
class CodeQualityReport:
    """Aggregate code quality assessment."""
    overall_score: float    # 0-100
    grade: str              # A, B, C, D, F
    loc: int
    dimensions: list = field(default_factory=list)
    file_path: str = ""

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 1),
            "grade": self.grade,
            "loc": self.loc,
            "file_path": self.file_path,
            "dimensions": [d.to_dict() for d in self.dimensions],
        }

    def summary(self) -> str:
        """One-line summary for additionalContext."""
        return f"Quality: {self.grade} ({self.overall_score:.0f}/100) — {self.loc} LOC"


def _score_to_grade(score: float) -> str:
    """Convert 0-100 score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


class CodeQualityScorer:
    """Scores code quality across multiple dimensions."""

    def __init__(self):
        self._satd = SATDDetector() if _satd_available else None

    def score(self, content: str, file_path: str = "") -> CodeQualityReport:
        """Score content across all quality dimensions. Returns CodeQualityReport."""
        if not content or not content.strip():
            return CodeQualityReport(
                overall_score=100.0, grade="A", loc=0,
                dimensions=[], file_path=file_path,
            )

        # Skip non-code files
        if file_path:
            ext = _get_extension(file_path)
            if ext in SKIP_EXTENSIONS:
                return CodeQualityReport(
                    overall_score=100.0, grade="A", loc=0,
                    dimensions=[], file_path=file_path,
                )

        lines = content.splitlines()
        loc = len([l for l in lines if l.strip()])

        dimensions = []

        # 1. Debt density (weight: 0.25)
        debt_score = self._score_debt_density(content, file_path, loc)
        dimensions.append(debt_score)

        # 2. Complexity density (weight: 0.25)
        complexity_score = self._score_complexity(content, loc)
        dimensions.append(complexity_score)

        # 3. Size risk (weight: 0.20)
        size_score = self._score_size(loc)
        dimensions.append(size_score)

        # 4. Documentation ratio (weight: 0.15)
        doc_score = self._score_documentation(content, loc)
        dimensions.append(doc_score)

        # 5. Naming quality (weight: 0.15)
        naming_score = self._score_naming(content)
        dimensions.append(naming_score)

        # Weighted average
        total_weight = sum(d.weight for d in dimensions)
        if total_weight > 0:
            overall = sum(d.score * d.weight for d in dimensions) / total_weight
        else:
            overall = 100.0

        overall = max(0.0, min(100.0, overall))

        return CodeQualityReport(
            overall_score=overall,
            grade=_score_to_grade(overall),
            loc=loc,
            dimensions=dimensions,
            file_path=file_path,
        )

    def _score_debt_density(self, content: str, file_path: str, loc: int) -> DimensionScore:
        """Score based on SATD marker density. Fewer markers = higher score."""
        if not self._satd or loc == 0:
            return DimensionScore(
                name="debt_density", score=100.0, weight=0.25,
                detail="No SATD markers (or detector unavailable)",
            )

        markers = self._satd.scan_file_content(content, file_path=file_path)
        marker_count = len(markers)
        high_count = sum(1 for m in markers if m.level.name == "HIGH")

        # Density per 100 LOC
        density = (marker_count / loc) * 100

        # Scoring: 0 density = 100, 1/100 LOC = 80, 3/100 = 60, 5+ = 40, 10+ = 20
        if density == 0:
            score = 100.0
        elif density <= 1:
            score = 90.0
        elif density <= 2:
            score = 80.0
        elif density <= 3:
            score = 70.0
        elif density <= 5:
            score = 55.0
        elif density <= 10:
            score = 35.0
        else:
            score = 20.0

        # HIGH severity markers penalize more
        if high_count > 0:
            score = max(20.0, score - (high_count * 5))

        return DimensionScore(
            name="debt_density", score=score, weight=0.25,
            detail=f"{marker_count} SATD markers ({high_count} HIGH) in {loc} LOC",
        )

    def _score_complexity(self, content: str, loc: int) -> DimensionScore:
        """Score based on control flow complexity density."""
        if loc == 0:
            return DimensionScore(
                name="complexity", score=100.0, weight=0.25,
                detail="No code to analyze",
            )

        matches = _COMPLEXITY_PATTERN.findall(content)
        complexity = len(matches)
        density = (complexity / loc) * 100

        # Scoring: <5/100 LOC = excellent, 5-15 = good, 15-25 = moderate, 25+ = high
        if density <= 5:
            score = 100.0
        elif density <= 10:
            score = 85.0
        elif density <= 15:
            score = 70.0
        elif density <= 25:
            score = 55.0
        elif density <= 35:
            score = 40.0
        else:
            score = 25.0

        return DimensionScore(
            name="complexity", score=score, weight=0.25,
            detail=f"{complexity} control flow markers in {loc} LOC ({density:.1f}/100)",
        )

    def _score_size(self, loc: int) -> DimensionScore:
        """Score based on file size relative to Atlassian 200-400 LOC threshold."""
        if loc <= 200:
            score = 100.0
            detail = f"{loc} LOC — within optimal review range"
        elif loc <= 400:
            score = 80.0
            detail = f"{loc} LOC — at Atlassian review limit"
        elif loc <= 600:
            score = 60.0
            detail = f"{loc} LOC — exceeds recommended review size"
        elif loc <= 1000:
            score = 40.0
            detail = f"{loc} LOC — large file, consider splitting"
        else:
            score = 20.0
            detail = f"{loc} LOC — very large, review quality will degrade"

        return DimensionScore(name="size", score=score, weight=0.20, detail=detail)

    def _score_documentation(self, content: str, loc: int) -> DimensionScore:
        """Score based on comment/docstring ratio."""
        if loc == 0:
            return DimensionScore(
                name="documentation", score=100.0, weight=0.15,
                detail="No code to analyze",
            )

        comment_lines = len(_COMMENT_PATTERN.findall(content))
        docstrings = _DOCSTRING_PATTERN.findall(content)
        docstring_lines = sum(ds.count("\n") + 1 for ds in docstrings)
        doc_lines = comment_lines + docstring_lines

        ratio = doc_lines / loc

        # Scoring: 10-30% is ideal. Below 5% = underdocumented. Above 50% = overdocumented.
        if 0.10 <= ratio <= 0.30:
            score = 100.0
        elif 0.05 <= ratio < 0.10:
            score = 80.0
        elif 0.30 < ratio <= 0.50:
            score = 80.0
        elif ratio < 0.05:
            score = 60.0
        else:
            score = 70.0  # Over-documented is better than under-documented

        return DimensionScore(
            name="documentation", score=score, weight=0.15,
            detail=f"{doc_lines} doc lines / {loc} LOC ({ratio:.0%})",
        )

    def _score_naming(self, content: str) -> DimensionScore:
        """Score based on identifier naming quality (length as proxy)."""
        identifiers = _IDENTIFIER_PATTERN.findall(content)
        # Filter out reserved words and very common names
        meaningful = [i for i in identifiers if i.lower() not in _RESERVED and len(i) > 1]

        if not meaningful:
            return DimensionScore(
                name="naming", score=85.0, weight=0.15,
                detail="No meaningful identifiers found",
            )

        avg_len = sum(len(i) for i in meaningful) / len(meaningful)

        # Scoring: 5-15 chars average is ideal. <3 = cryptic. >25 = verbose.
        if 5 <= avg_len <= 15:
            score = 100.0
        elif 4 <= avg_len < 5:
            score = 85.0
        elif 15 < avg_len <= 20:
            score = 85.0
        elif 3 <= avg_len < 4:
            score = 70.0
        elif 20 < avg_len <= 25:
            score = 70.0
        elif avg_len < 3:
            score = 50.0
        else:
            score = 60.0

        return DimensionScore(
            name="naming", score=score, weight=0.15,
            detail=f"Avg identifier length: {avg_len:.1f} chars ({len(meaningful)} identifiers)",
        )


def score_file(content: str, file_path: str = "") -> CodeQualityReport:
    """Convenience function to score a file's content."""
    scorer = CodeQualityScorer()
    return scorer.score(content, file_path=file_path)


def _get_extension(file_path: str) -> str:
    """Return lowercase file extension including dot, or '' if none."""
    basename = file_path.split("/")[-1]
    if "." not in basename:
        return ""
    return "." + basename.rsplit(".", 1)[-1].lower()


if __name__ == "__main__":
    import json
    content = sys.stdin.read()
    file_path = sys.argv[1] if len(sys.argv) > 1 else ""
    report = score_file(content, file_path=file_path)
    print(json.dumps(report.to_dict(), indent=2))
