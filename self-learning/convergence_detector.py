#!/usr/bin/env python3
"""convergence_detector.py — MT-10 Growth: Convergence detection for self-learning.

Detects when an improvement approach has converged (stopped making progress)
and should be abandoned or pivoted. Inspired by ResearcherSkill's convergence
signals pattern (S149 nuclear scan finding).

Three signal types:
1. Metric plateau — metric hasn't improved by threshold over N evaluations
2. Discard streak — N+ consecutive rejected/failed proposals = approach exhausted
3. Oscillation — alternating success/failure suggests conflating variables

Usage:
    from convergence_detector import ConvergenceDetector
    detector = ConvergenceDetector()
    detector.add_observation(metric_value=72.5, accepted=True)
    detector.add_observation(metric_value=72.8, accepted=True)
    signals = detector.check_convergence()
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Observation:
    """A single evaluation observation."""
    metric_value: Optional[float]  # None if not measurable
    accepted: bool  # Was the change kept or discarded?
    label: str = ""  # Optional description


@dataclass
class ConvergenceSignal:
    """A detected convergence signal."""
    signal_type: str  # "plateau", "discard_streak", "oscillation"
    severity: str  # "warning", "converged"
    detail: str
    recommendation: str


class ConvergenceDetector:
    """Detects convergence in a sequence of improvement observations.

    Tracks metric values and accept/reject decisions to determine when
    an approach has stopped making meaningful progress.
    """

    def __init__(
        self,
        plateau_threshold: float = 0.5,
        plateau_window: int = 5,
        discard_streak_limit: int = 5,
        oscillation_window: int = 6,
        oscillation_ratio: float = 0.4,
    ):
        """Initialize convergence detector.

        Args:
            plateau_threshold: Minimum % improvement to count as progress
            plateau_window: Number of observations to check for plateau
            discard_streak_limit: Consecutive discards before "approach exhausted"
            oscillation_window: Window size for oscillation detection
            oscillation_ratio: Min ratio of alternations to detect oscillation
        """
        self.plateau_threshold = plateau_threshold
        self.plateau_window = plateau_window
        self.discard_streak_limit = discard_streak_limit
        self.oscillation_window = oscillation_window
        self.oscillation_ratio = oscillation_ratio
        self.observations: list[Observation] = []

    def add_observation(
        self,
        metric_value: Optional[float] = None,
        accepted: bool = True,
        label: str = "",
    ) -> None:
        """Record a new observation."""
        self.observations.append(Observation(
            metric_value=metric_value,
            accepted=accepted,
            label=label,
        ))

    def check_convergence(self) -> list[ConvergenceSignal]:
        """Check all convergence signals. Returns list of active signals."""
        signals = []

        plateau = self._check_plateau()
        if plateau:
            signals.append(plateau)

        streak = self._check_discard_streak()
        if streak:
            signals.append(streak)

        osc = self._check_oscillation()
        if osc:
            signals.append(osc)

        return signals

    @property
    def is_converged(self) -> bool:
        """True if any signal has severity 'converged'."""
        return any(s.severity == "converged" for s in self.check_convergence())

    @property
    def has_warnings(self) -> bool:
        """True if any convergence warnings are active."""
        return len(self.check_convergence()) > 0

    def _check_plateau(self) -> Optional[ConvergenceSignal]:
        """Detect metric plateau — metric hasn't improved over window."""
        # Need at least plateau_window observations with metric values
        metric_obs = [o for o in self.observations if o.metric_value is not None]
        if len(metric_obs) < self.plateau_window:
            return None

        recent = metric_obs[-self.plateau_window:]
        first_val = recent[0].metric_value
        last_val = recent[-1].metric_value

        if first_val == 0:
            return None

        pct_change = abs(last_val - first_val) / abs(first_val) * 100

        if pct_change < self.plateau_threshold:
            best_in_window = max(o.metric_value for o in recent)
            worst_in_window = min(o.metric_value for o in recent)
            spread = best_in_window - worst_in_window

            if spread < abs(first_val) * (self.plateau_threshold / 100):
                return ConvergenceSignal(
                    signal_type="plateau",
                    severity="converged",
                    detail=f"Metric flat over {self.plateau_window} observations: "
                           f"{first_val:.2f} -> {last_val:.2f} ({pct_change:.2f}% change)",
                    recommendation="Current approach exhausted. Try a fundamentally different strategy.",
                )

            return ConvergenceSignal(
                signal_type="plateau",
                severity="warning",
                detail=f"Metric near-flat over {self.plateau_window} observations: "
                       f"{first_val:.2f} -> {last_val:.2f} ({pct_change:.2f}% change, "
                       f"spread: {spread:.2f})",
                recommendation="Diminishing returns. Consider pivoting approach.",
            )

        return None

    def _check_discard_streak(self) -> Optional[ConvergenceSignal]:
        """Detect discard streak — N+ consecutive rejected observations."""
        if len(self.observations) < 2:
            return None

        # Count consecutive discards from the end
        streak = 0
        for obs in reversed(self.observations):
            if not obs.accepted:
                streak += 1
            else:
                break

        if streak >= self.discard_streak_limit:
            return ConvergenceSignal(
                signal_type="discard_streak",
                severity="converged",
                detail=f"{streak} consecutive discarded changes",
                recommendation="Approach exhausted. Pivot to a different technique or target.",
            )

        # Warning at 60% of limit
        warning_threshold = max(2, int(self.discard_streak_limit * 0.6))
        if streak >= warning_threshold:
            return ConvergenceSignal(
                signal_type="discard_streak",
                severity="warning",
                detail=f"{streak} consecutive discards (limit: {self.discard_streak_limit})",
                recommendation="Approach may be exhausting. Consider alternatives.",
            )

        return None

    def _check_oscillation(self) -> Optional[ConvergenceSignal]:
        """Detect oscillation — alternating accept/discard pattern.

        This suggests the changes are conflating multiple variables
        and the approach needs decomposition.
        """
        if len(self.observations) < self.oscillation_window:
            return None

        recent = self.observations[-self.oscillation_window:]
        alternations = 0
        for i in range(1, len(recent)):
            if recent[i].accepted != recent[i - 1].accepted:
                alternations += 1

        max_alternations = len(recent) - 1
        if max_alternations == 0:
            return None

        ratio = alternations / max_alternations

        if ratio >= self.oscillation_ratio:
            return ConvergenceSignal(
                signal_type="oscillation",
                severity="warning" if ratio < 0.8 else "converged",
                detail=f"{alternations}/{max_alternations} alternations in last "
                       f"{self.oscillation_window} observations ({ratio:.0%})",
                recommendation="Changes may be conflating variables. Decompose into smaller, "
                              "isolated experiments.",
            )

        return None

    def summary(self) -> str:
        """Human-readable convergence summary."""
        signals = self.check_convergence()
        if not signals:
            total = len(self.observations)
            accepted = sum(1 for o in self.observations if o.accepted)
            return f"No convergence signals. {total} observations, {accepted} accepted."

        lines = [f"CONVERGENCE DETECTED ({len(signals)} signal(s)):"]
        for s in signals:
            lines.append(f"  [{s.severity.upper()}] {s.signal_type}: {s.detail}")
            lines.append(f"    -> {s.recommendation}")
        return "\n".join(lines)

    def reset(self) -> None:
        """Clear all observations."""
        self.observations.clear()

    def to_dict(self) -> dict:
        """Serialize state for persistence."""
        return {
            "observations": [
                {"metric_value": o.metric_value, "accepted": o.accepted, "label": o.label}
                for o in self.observations
            ],
            "config": {
                "plateau_threshold": self.plateau_threshold,
                "plateau_window": self.plateau_window,
                "discard_streak_limit": self.discard_streak_limit,
                "oscillation_window": self.oscillation_window,
                "oscillation_ratio": self.oscillation_ratio,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConvergenceDetector":
        """Restore from serialized state."""
        config = data.get("config", {})
        detector = cls(**config)
        for obs_data in data.get("observations", []):
            detector.add_observation(
                metric_value=obs_data.get("metric_value"),
                accepted=obs_data.get("accepted", True),
                label=obs_data.get("label", ""),
            )
        return detector
