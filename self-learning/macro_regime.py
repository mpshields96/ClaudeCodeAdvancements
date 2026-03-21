#!/usr/bin/env python3
"""
macro_regime.py — MT-26 Tier 2: Macro Regime Context

Provides economic event awareness as a volatility regime modifier.
When major macro events (FOMC, CPI, NFP) are imminent, crypto direction
becomes less predictable — the bot should size down or skip.

This module does NOT call external APIs. It provides:
1. A built-in 2026 macro event calendar (FOMC, CPI, NFP dates)
2. Classification of current macro context (CALM/ELEVATED/HIGH_IMPACT)
3. A sizing modifier (0.0 to 1.0) based on proximity to macro events
4. Advice strings for the bot's decision engine

The bot provides the current time, this module provides the classification.

Usage:
    from macro_regime import MacroRegimeContext

    ctx = MacroRegimeContext()

    # With built-in 2026 calendar
    result = ctx.classify_now()
    # result = {"regime": "CALM", "sizing_modifier": 1.0, ...}

    # Or with custom events
    events = [MacroEvent("FOMC", "FOMC", datetime(2026,3,19,14,0), MacroImpact.HIGH)]
    result = ctx.classify(events=events, now=datetime(2026,3,19,13,30))

CLI:
    python3 macro_regime.py --now 2026-03-19T13:30:00
"""

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class MacroImpact(Enum):
    """Impact level of a macro event on crypto volatility."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @property
    def weight(self) -> float:
        """Numeric weight for comparisons and modifier calculations."""
        return {"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0}[self.value]


@dataclass
class MacroEvent:
    """A scheduled macroeconomic event."""
    name: str
    event_type: str  # FOMC, CPI, NFP, JOBLESS_CLAIMS, etc.
    timestamp: datetime
    impact: MacroImpact

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "impact": self.impact.value,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MacroEvent":
        return cls(
            name=d["name"],
            event_type=d["event_type"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            impact=MacroImpact(d["impact"]),
        )


class MacroRegimeContext:
    """Classifies macro regime context based on proximity to economic events.

    Regimes:
        CALM: No significant macro events nearby. Trade normally.
        ELEVATED: A macro event is approaching. Reduce sizing.
        HIGH_IMPACT: A major event is imminent or just occurred. Skip or minimal sizing.
    """

    def __init__(
        self,
        high_impact_window_hours: float = 1.0,
        elevated_window_hours: float = 2.0,
        post_event_cooldown_hours: float = 0.5,
    ):
        """
        Args:
            high_impact_window_hours: Hours before a HIGH event that triggers HIGH_IMPACT.
            elevated_window_hours: Hours before a HIGH event that triggers ELEVATED.
            post_event_cooldown_hours: Hours after an event before returning to CALM.
        """
        self.high_impact_window = timedelta(hours=high_impact_window_hours)
        self.elevated_window = timedelta(hours=elevated_window_hours)
        self.post_cooldown = timedelta(hours=post_event_cooldown_hours)

    def classify(
        self,
        events: Optional[List[MacroEvent]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Classify the current macro regime.

        Args:
            events: List of macro events to consider. If None, uses built-in calendar.
            now: Current time. If None, uses datetime.now().

        Returns:
            dict with:
                regime: str — CALM, ELEVATED, HIGH_IMPACT
                sizing_modifier: float — 0.0 to 1.0 (multiply with Kelly fraction)
                advice: str — trading recommendation
                active_events: list — events contributing to current regime
                nearest_event: str | None — name of the closest relevant event
        """
        if now is None:
            now = datetime.now()
        if events is None:
            events = self.known_events_2026()

        worst_regime = "CALM"
        best_modifier = 1.0
        active_events = []
        nearest_event = None
        nearest_distance = None

        for event in events:
            delta = event.timestamp - now
            delta_hours = delta.total_seconds() / 3600.0
            abs_delta_hours = abs(delta_hours)

            # Determine impact windows based on event impact level
            if event.impact == MacroImpact.HIGH:
                hi_window = self.high_impact_window.total_seconds() / 3600.0
                el_window = self.elevated_window.total_seconds() / 3600.0
                cooldown = self.post_cooldown.total_seconds() / 3600.0
            elif event.impact == MacroImpact.MEDIUM:
                hi_window = 0  # MEDIUM events don't trigger HIGH_IMPACT
                el_window = self.high_impact_window.total_seconds() / 3600.0
                cooldown = self.post_cooldown.total_seconds() / 3600.0 * 0.5
            else:  # LOW
                hi_window = 0
                el_window = 0
                cooldown = 0

            # Check if event is relevant (within any window)
            max_window = max(el_window, hi_window, cooldown)
            if delta_hours < -cooldown or delta_hours > max(el_window, 1):
                # Event is too far in the past or future
                continue

            # Track nearest event
            if nearest_distance is None or abs_delta_hours < nearest_distance:
                nearest_distance = abs_delta_hours
                nearest_event = event.name

            # Classify this event's contribution
            event_regime = "CALM"
            event_modifier = 1.0

            if delta_hours >= 0:
                # Event is in the future
                if hi_window > 0 and delta_hours <= hi_window:
                    event_regime = "HIGH_IMPACT"
                    # Linear ramp: 0.25 at event time, up to ~0.5 at window edge
                    progress = delta_hours / hi_window if hi_window > 0 else 0
                    event_modifier = 0.25 * (1 - progress) + 0.5 * progress
                    if event.impact == MacroImpact.HIGH:
                        event_modifier = min(event_modifier, 0.25)
                elif el_window > 0 and delta_hours <= el_window:
                    event_regime = "ELEVATED"
                    progress = (delta_hours - hi_window) / (el_window - hi_window) \
                        if el_window > hi_window else 0
                    event_modifier = 0.5 * (1 - progress) + 0.85 * progress
            else:
                # Event is in the past (within cooldown)
                past_hours = -delta_hours
                if past_hours <= cooldown:
                    if event.impact == MacroImpact.HIGH:
                        if past_hours <= cooldown * 0.5:
                            event_regime = "HIGH_IMPACT"
                            event_modifier = 0.3
                        else:
                            event_regime = "ELEVATED"
                            progress = (past_hours - cooldown * 0.5) / (cooldown * 0.5)
                            event_modifier = 0.3 + 0.5 * progress
                    elif event.impact == MacroImpact.MEDIUM:
                        event_regime = "ELEVATED"
                        progress = past_hours / cooldown if cooldown > 0 else 1
                        event_modifier = 0.6 + 0.3 * progress

            if event_regime != "CALM":
                active_events.append(event.to_dict())

            # Update worst regime
            regime_rank = {"CALM": 0, "ELEVATED": 1, "HIGH_IMPACT": 2}
            if regime_rank.get(event_regime, 0) > regime_rank.get(worst_regime, 0):
                worst_regime = event_regime

            if event_modifier < best_modifier:
                best_modifier = event_modifier

        # LOW impact events: minimal modifier reduction
        if worst_regime == "CALM" and active_events:
            best_modifier = max(best_modifier, 0.9)

        advice = self._generate_advice(worst_regime, best_modifier, nearest_event)

        return {
            "regime": worst_regime,
            "sizing_modifier": round(best_modifier, 3),
            "advice": advice,
            "active_events": active_events,
            "nearest_event": nearest_event,
        }

    def classify_now(self) -> Dict[str, Any]:
        """Convenience: classify using built-in calendar and current time."""
        return self.classify(events=self.known_events_2026(), now=datetime.now())

    @staticmethod
    def known_events_2026() -> List[MacroEvent]:
        """Built-in 2026 US macro event calendar.

        Includes FOMC decisions, CPI releases, and Non-Farm Payrolls.
        All times are Eastern (market convention).

        Sources: Federal Reserve calendar, BLS release schedule.
        """
        events = []

        # 2026 FOMC Decision dates (2:00 PM ET)
        # https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
        fomc_dates = [
            (1, 29), (3, 18), (5, 6), (6, 17),
            (7, 29), (9, 16), (10, 28), (12, 9),
        ]
        for month, day in fomc_dates:
            events.append(MacroEvent(
                name=f"FOMC Decision {month}/{day}",
                event_type="FOMC",
                timestamp=datetime(2026, month, day, 14, 0),
                impact=MacroImpact.HIGH,
            ))

        # 2026 CPI Release dates (8:30 AM ET)
        cpi_dates = [
            (1, 14), (2, 12), (3, 12), (4, 10), (5, 13), (6, 10),
            (7, 14), (8, 12), (9, 10), (10, 13), (11, 12), (12, 10),
        ]
        for month, day in cpi_dates:
            events.append(MacroEvent(
                name=f"CPI Release {month}/{day}",
                event_type="CPI",
                timestamp=datetime(2026, month, day, 8, 30),
                impact=MacroImpact.HIGH,
            ))

        # 2026 Non-Farm Payrolls (8:30 AM ET, first Friday)
        nfp_dates = [
            (1, 9), (2, 6), (3, 6), (4, 3), (5, 8), (6, 5),
            (7, 2), (8, 7), (9, 4), (10, 2), (11, 6), (12, 4),
        ]
        for month, day in nfp_dates:
            events.append(MacroEvent(
                name=f"NFP Report {month}/{day}",
                event_type="NFP",
                timestamp=datetime(2026, month, day, 8, 30),
                impact=MacroImpact.HIGH,
            ))

        # Weekly Jobless Claims (8:30 AM ET, Thursdays) — MEDIUM impact
        # Include every Thursday for 2026 Q1-Q2
        from datetime import date
        d = date(2026, 1, 1)
        while d.year == 2026 and d.month <= 6:
            if d.weekday() == 3:  # Thursday
                events.append(MacroEvent(
                    name=f"Jobless Claims {d.month}/{d.day}",
                    event_type="JOBLESS_CLAIMS",
                    timestamp=datetime(d.year, d.month, d.day, 8, 30),
                    impact=MacroImpact.MEDIUM,
                ))
            d += timedelta(days=1)

        return events

    def _generate_advice(
        self, regime: str, modifier: float, nearest: Optional[str]
    ) -> str:
        """Generate trading advice based on macro regime."""
        if regime == "HIGH_IMPACT":
            return (
                f"Major macro event imminent ({nearest}). "
                f"Sizing modifier: {modifier:.0%}. "
                f"Skip or use minimal position sizes — "
                f"crypto direction is unpredictable around major releases."
            )
        if regime == "ELEVATED":
            return (
                f"Macro event approaching ({nearest}). "
                f"Sizing modifier: {modifier:.0%}. "
                f"Reduce position sizes — volatility may increase."
            )
        return (
            "No significant macro events nearby. "
            "Trade normally — macro context is calm."
        )


def _cli():
    """CLI interface for macro regime classification."""
    import argparse
    parser = argparse.ArgumentParser(description="Macro Regime Context Classifier")
    parser.add_argument("--now", type=str,
                        help="Current time (ISO format, default: now)")
    parser.add_argument("--events", type=str,
                        help="JSON file with custom events")
    args = parser.parse_args()

    now = datetime.fromisoformat(args.now) if args.now else datetime.now()

    ctx = MacroRegimeContext()

    if args.events:
        with open(args.events) as f:
            raw = json.load(f)
        events = [MacroEvent.from_dict(e) for e in raw]
        result = ctx.classify(events=events, now=now)
    else:
        result = ctx.classify(now=now)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _cli()
