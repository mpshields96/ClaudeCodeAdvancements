"""Action diversity checking for Pokemon Crystal agent.

Mewtoo pattern: if one action exceeds 60% of the last 15 actions,
flag it and suggest alternatives. Complements stuck detection — you
might be moving (position changes) but still doing the same thing
repeatedly (e.g., walking right into a dead end, mashing A).

Usage:
    from diversity_checker import DiversityChecker

    dc = DiversityChecker()
    dc.record("right")
    dominant = dc.dominant_action()  # "right" if >60% of last 15
    prompt = dc.format_for_prompt()  # warning for LLM

Stdlib only. No external dependencies.
"""
from __future__ import annotations

from collections import Counter
from typing import List, Optional

ALL_DIRECTIONS = ["up", "down", "left", "right"]
DEFAULT_WINDOW = 15
DEFAULT_THRESHOLD = 0.60


class DiversityChecker:
    """Tracks action history and flags repetitive behavior."""

    def __init__(
        self,
        window_size: int = DEFAULT_WINDOW,
        threshold: float = DEFAULT_THRESHOLD,
    ):
        self.window_size = window_size
        self.threshold = threshold
        self._history: List[str] = []
        self._total: int = 0

    def record(self, action: str) -> None:
        """Record an action to the history window."""
        self._history.append(action)
        self._total += 1
        if len(self._history) > self.window_size:
            self._history = self._history[-self.window_size:]

    def dominant_action(self) -> Optional[str]:
        """Return the dominant action if one exceeds the threshold.

        Returns None if no action exceeds threshold or insufficient history.
        """
        if len(self._history) < self.window_size:
            return None

        counts = Counter(self._history)
        for action, count in counts.most_common(1):
            if count / len(self._history) > self.threshold:
                return action
        return None

    def suggest_alternatives(self) -> List[str]:
        """Suggest alternative actions when a dominant action is detected."""
        dominant = self.dominant_action()
        if dominant is None:
            return []

        # Suggest directions that aren't the dominant one
        if dominant in ALL_DIRECTIONS:
            return [d for d in ALL_DIRECTIONS if d != dominant]

        # For non-direction buttons, suggest all directions
        return ALL_DIRECTIONS

    def format_for_prompt(self) -> str:
        """Format a warning for the LLM prompt."""
        dominant = self.dominant_action()
        if dominant is None:
            return ""

        count = Counter(self._history)[dominant]
        pct = count / len(self._history) * 100
        alts = self.suggest_alternatives()
        alt_str = ", ".join(alts) if alts else "something different"
        return (
            f"WARNING: Repetitive action detected — '{dominant}' used "
            f"{pct:.0f}% of last {len(self._history)} actions. "
            f"Try: {alt_str}."
        )

    def clear(self) -> None:
        """Reset all history."""
        self._history.clear()
        self._total = 0

    def stats(self) -> dict:
        """Return action distribution stats."""
        return {
            "total_recorded": self._total,
            "window_size": len(self._history),
            "distribution": dict(Counter(self._history)),
            "dominant": self.dominant_action(),
        }
