#!/usr/bin/env python3
"""Effort Scorer — MT-20 Senior Dev Agent Phase 2: PR effort scoring.

PostToolUse hook that scores the effort required to review written content
on a 1-5 scale mirroring PR-Agent's effort ratings.

Scoring is grounded in Atlassian/Cisco empirical research:
- 200-400 LOC is the empirically validated review limit
- Complexity markers (if/for/while/def/class/try) increase cognitive load
- Score is clamped to 1-5 always

Only emits additionalContext for scores >= 3 (Moderate+), to avoid noise on trivial writes.
"""

import json
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

# File extensions to skip complexity counting (prose/config, not code)
SKIP_COMPLEXITY_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".txt", ".rst", ".toml", ".ini", ".cfg"}

# Complexity keywords to count (regex word-boundary match)
_COMPLEXITY_KEYWORDS = re.compile(r"\b(if|for|while|def|class|try|except|elif|with|lambda)\b")

# Score thresholds and labels
_SCORE_LABELS = {1: "Trivial", 2: "Simple", 3: "Moderate", 4: "Complex", 5: "Very Complex"}

# LOC → base score bands (upper bound exclusive)
_LOC_BANDS = [
    (25, 1),    # 0-24 lines: Trivial
    (75, 2),    # 25-74 lines: Simple
    (200, 3),   # 75-199 lines: Moderate
    (400, 4),   # 200-399 lines: Complex
    (float("inf"), 5),  # 400+ lines: Very Complex
]

# Complexity → bonus points (added to LOC base before clamping)
_COMPLEXITY_BANDS = [
    (5, 0),     # 0-4 complexity: no bonus
    (15, 1),    # 5-14: +1
    (30, 2),    # 15-29: +2
    (float("inf"), 3),  # 30+: +3
]


@dataclass
class EffortScore:
    score: int          # 1-5
    label: str          # Trivial / Simple / Moderate / Complex / Very Complex
    loc: int            # total non-blank lines
    complexity: int     # count of complexity keyword occurrences
    breakdown: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "label": self.label,
            "loc": self.loc,
            "complexity": self.complexity,
            "breakdown": self.breakdown,
        }


def _get_extension(file_path: str) -> str:
    """Return lowercase file extension including dot, or '' if none."""
    basename = file_path.split("/")[-1]
    if "." not in basename:
        return ""
    return "." + basename.rsplit(".", 1)[-1].lower()


def _band_value(value: float, bands: list) -> int:
    for threshold, result in bands:
        if value < threshold:
            return result
    return bands[-1][1]


class EffortScorer:
    def score_content(self, content: str, file_path: str = "") -> EffortScore:
        """Score the review effort for the given content string."""
        if not content:
            return EffortScore(score=1, label="Trivial", loc=0, complexity=0,
                               breakdown={"loc_points": 1, "complexity_points": 0})

        # Count non-blank lines
        lines = [l for l in content.splitlines() if l.strip()]
        loc = len(lines)

        # Count complexity markers (skip for non-code files)
        skip_complexity = False
        if file_path:
            ext = _get_extension(file_path)
            if ext in SKIP_COMPLEXITY_EXTENSIONS:
                skip_complexity = True

        if skip_complexity:
            complexity = 0
        else:
            complexity = len(_COMPLEXITY_KEYWORDS.findall(content))

        # Compute score
        loc_points = _band_value(loc, _LOC_BANDS)
        complexity_points = _band_value(complexity, _COMPLEXITY_BANDS)
        raw = loc_points + complexity_points
        score = max(1, min(5, raw))
        label = _SCORE_LABELS[score]

        return EffortScore(
            score=score,
            label=label,
            loc=loc,
            complexity=complexity,
            breakdown={"loc_points": loc_points, "complexity_points": complexity_points},
        )

    def hook_output(self, payload: dict) -> dict:
        """
        Produce PostToolUse hook output.
        Returns {} for trivial/simple writes, or {"additionalContext": "..."} for score >= 3.
        """
        if not payload:
            return {}

        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})

        if tool_name == "Write":
            content = tool_input.get("content", "")
            file_path = tool_input.get("file_path", "")
        elif tool_name == "Edit":
            content = tool_input.get("new_string", "")
            file_path = tool_input.get("file_path", "")
        else:
            return {}

        if not content:
            return {}

        result = self.score_content(content, file_path=file_path)

        # Only emit context for Moderate+ (score >= 3)
        if result.score < 3:
            return {}

        context = (
            f"Write effort score: {result.score}/5 ({result.label}) — "
            f"{result.loc} lines, {result.complexity} complexity markers. "
            f"Consider breaking into smaller, focused writes if reviewing this change."
        )

        # Bound to 500 chars
        if len(context) > 500:
            context = context[:497] + "..."

        return {"additionalContext": context}


def score_content(content: str, file_path: str = "") -> EffortScore:
    """Module-level convenience function."""
    return EffortScorer().score_content(content, file_path=file_path)


def main():
    """PostToolUse hook entry point."""
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({}))
            return
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({}))
        return

    scorer = EffortScorer()
    output = scorer.hook_output(payload)
    print(json.dumps(output))


if __name__ == "__main__":
    main()
