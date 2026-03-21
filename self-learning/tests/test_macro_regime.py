#!/usr/bin/env python3
"""Tests for macro_regime.py — MT-26 Tier 2: Macro Regime Context.

Macro regime context provides economic event awareness as a volatility
regime modifier. When major macro events (FOMC, CPI, NFP) are imminent,
crypto direction becomes less predictable — the bot should size down or skip.
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from macro_regime import (
    MacroEvent,
    MacroRegimeContext,
    MacroImpact,
)


class TestMacroEvent(unittest.TestCase):
    """Test MacroEvent data structure."""

    def test_create_event(self):
        event = MacroEvent(
            name="FOMC Decision",
            event_type="FOMC",
            timestamp=datetime(2026, 3, 19, 14, 0),
            impact=MacroImpact.HIGH,
        )
        self.assertEqual(event.name, "FOMC Decision")
        self.assertEqual(event.event_type, "FOMC")
        self.assertEqual(event.impact, MacroImpact.HIGH)

    def test_event_to_dict(self):
        event = MacroEvent(
            name="CPI Release",
            event_type="CPI",
            timestamp=datetime(2026, 3, 12, 8, 30),
            impact=MacroImpact.HIGH,
        )
        d = event.to_dict()
        self.assertEqual(d["name"], "CPI Release")
        self.assertEqual(d["event_type"], "CPI")
        self.assertEqual(d["impact"], "HIGH")
        self.assertIn("timestamp", d)

    def test_event_from_dict(self):
        d = {
            "name": "NFP Report",
            "event_type": "NFP",
            "timestamp": "2026-03-07T08:30:00",
            "impact": "HIGH",
        }
        event = MacroEvent.from_dict(d)
        self.assertEqual(event.name, "NFP Report")
        self.assertEqual(event.event_type, "NFP")
        self.assertEqual(event.impact, MacroImpact.HIGH)
        self.assertEqual(event.timestamp.hour, 8)

    def test_event_from_dict_medium_impact(self):
        d = {
            "name": "Initial Jobless Claims",
            "event_type": "JOBLESS_CLAIMS",
            "timestamp": "2026-03-20T08:30:00",
            "impact": "MEDIUM",
        }
        event = MacroEvent.from_dict(d)
        self.assertEqual(event.impact, MacroImpact.MEDIUM)


class TestMacroImpact(unittest.TestCase):
    """Test MacroImpact enum."""

    def test_impact_values(self):
        self.assertEqual(MacroImpact.HIGH.value, "HIGH")
        self.assertEqual(MacroImpact.MEDIUM.value, "MEDIUM")
        self.assertEqual(MacroImpact.LOW.value, "LOW")

    def test_impact_ordering(self):
        # HIGH > MEDIUM > LOW for comparisons
        self.assertTrue(MacroImpact.HIGH.weight > MacroImpact.MEDIUM.weight)
        self.assertTrue(MacroImpact.MEDIUM.weight > MacroImpact.LOW.weight)


class TestMacroRegimeContext(unittest.TestCase):
    """Test MacroRegimeContext classifier."""

    def setUp(self):
        self.ctx = MacroRegimeContext()

    # --- No events ---

    def test_no_events_returns_calm(self):
        result = self.ctx.classify(
            events=[], now=datetime(2026, 3, 21, 10, 0)
        )
        self.assertEqual(result["regime"], "CALM")
        self.assertEqual(result["sizing_modifier"], 1.0)

    # --- HIGH impact event proximity ---

    def test_high_impact_within_1h_returns_high_impact(self):
        fomc = MacroEvent(
            name="FOMC Decision",
            event_type="FOMC",
            timestamp=datetime(2026, 3, 19, 14, 0),
            impact=MacroImpact.HIGH,
        )
        now = datetime(2026, 3, 19, 13, 30)  # 30 min before
        result = self.ctx.classify(events=[fomc], now=now)
        self.assertEqual(result["regime"], "HIGH_IMPACT")
        self.assertLessEqual(result["sizing_modifier"], 0.25)

    def test_high_impact_within_2h_returns_elevated(self):
        fomc = MacroEvent(
            name="FOMC Decision",
            event_type="FOMC",
            timestamp=datetime(2026, 3, 19, 14, 0),
            impact=MacroImpact.HIGH,
        )
        now = datetime(2026, 3, 19, 12, 30)  # 90 min before
        result = self.ctx.classify(events=[fomc], now=now)
        self.assertEqual(result["regime"], "ELEVATED")

    def test_high_impact_after_event_still_elevated(self):
        """Post-FOMC volatility can last 30+ minutes."""
        fomc = MacroEvent(
            name="FOMC Decision",
            event_type="FOMC",
            timestamp=datetime(2026, 3, 19, 14, 0),
            impact=MacroImpact.HIGH,
        )
        now = datetime(2026, 3, 19, 14, 20)  # 20 min after
        result = self.ctx.classify(events=[fomc], now=now)
        self.assertIn(result["regime"], ["HIGH_IMPACT", "ELEVATED"])

    def test_high_impact_well_after_returns_calm(self):
        fomc = MacroEvent(
            name="FOMC Decision",
            event_type="FOMC",
            timestamp=datetime(2026, 3, 19, 14, 0),
            impact=MacroImpact.HIGH,
        )
        now = datetime(2026, 3, 19, 16, 0)  # 2h after
        result = self.ctx.classify(events=[fomc], now=now)
        self.assertEqual(result["regime"], "CALM")

    # --- MEDIUM impact events ---

    def test_medium_impact_within_30min(self):
        claims = MacroEvent(
            name="Initial Jobless Claims",
            event_type="JOBLESS_CLAIMS",
            timestamp=datetime(2026, 3, 20, 8, 30),
            impact=MacroImpact.MEDIUM,
        )
        now = datetime(2026, 3, 20, 8, 10)  # 20 min before
        result = self.ctx.classify(events=[claims], now=now)
        self.assertEqual(result["regime"], "ELEVATED")

    def test_medium_impact_far_away_returns_calm(self):
        claims = MacroEvent(
            name="Initial Jobless Claims",
            event_type="JOBLESS_CLAIMS",
            timestamp=datetime(2026, 3, 20, 8, 30),
            impact=MacroImpact.MEDIUM,
        )
        now = datetime(2026, 3, 20, 6, 0)  # 2.5h before
        result = self.ctx.classify(events=[claims], now=now)
        self.assertEqual(result["regime"], "CALM")

    # --- LOW impact events ---

    def test_low_impact_never_elevates(self):
        event = MacroEvent(
            name="Consumer Sentiment",
            event_type="SENTIMENT",
            timestamp=datetime(2026, 3, 21, 10, 0),
            impact=MacroImpact.LOW,
        )
        now = datetime(2026, 3, 21, 9, 55)  # 5 min before
        result = self.ctx.classify(events=[event], now=now)
        # LOW impact should at most slightly adjust modifier
        self.assertGreaterEqual(result["sizing_modifier"], 0.8)

    # --- Multiple events ---

    def test_multiple_events_picks_worst(self):
        """When two events are near, the most impactful one drives the regime."""
        fomc = MacroEvent(
            name="FOMC Decision",
            event_type="FOMC",
            timestamp=datetime(2026, 3, 19, 14, 0),
            impact=MacroImpact.HIGH,
        )
        claims = MacroEvent(
            name="Jobless Claims",
            event_type="JOBLESS_CLAIMS",
            timestamp=datetime(2026, 3, 19, 14, 30),
            impact=MacroImpact.MEDIUM,
        )
        now = datetime(2026, 3, 19, 13, 45)
        result = self.ctx.classify(events=[fomc, claims], now=now)
        self.assertEqual(result["regime"], "HIGH_IMPACT")
        self.assertEqual(result["nearest_event"], "FOMC Decision")

    def test_multiple_events_far_away(self):
        events = [
            MacroEvent("CPI", "CPI", datetime(2026, 3, 12, 8, 30), MacroImpact.HIGH),
            MacroEvent("NFP", "NFP", datetime(2026, 3, 7, 8, 30), MacroImpact.HIGH),
        ]
        now = datetime(2026, 3, 21, 10, 0)
        result = self.ctx.classify(events=events, now=now)
        self.assertEqual(result["regime"], "CALM")

    # --- Sizing modifier ---

    def test_sizing_modifier_range(self):
        """Sizing modifier should always be between 0.0 and 1.0."""
        fomc = MacroEvent(
            name="FOMC",
            event_type="FOMC",
            timestamp=datetime(2026, 3, 19, 14, 0),
            impact=MacroImpact.HIGH,
        )
        for delta_min in range(-60, 180, 5):
            now = fomc.timestamp + timedelta(minutes=delta_min)
            result = self.ctx.classify(events=[fomc], now=now)
            self.assertGreaterEqual(result["sizing_modifier"], 0.0)
            self.assertLessEqual(result["sizing_modifier"], 1.0)

    def test_sizing_modifier_decreases_near_event(self):
        fomc = MacroEvent(
            name="FOMC",
            event_type="FOMC",
            timestamp=datetime(2026, 3, 19, 14, 0),
            impact=MacroImpact.HIGH,
        )
        far = self.ctx.classify(
            events=[fomc], now=datetime(2026, 3, 19, 11, 0))
        near = self.ctx.classify(
            events=[fomc], now=datetime(2026, 3, 19, 13, 45))
        self.assertGreater(far["sizing_modifier"], near["sizing_modifier"])

    # --- Output structure ---

    def test_output_has_required_fields(self):
        result = self.ctx.classify(events=[], now=datetime(2026, 3, 21, 10, 0))
        self.assertIn("regime", result)
        self.assertIn("sizing_modifier", result)
        self.assertIn("advice", result)
        self.assertIn("active_events", result)

    def test_output_active_events_list(self):
        fomc = MacroEvent(
            name="FOMC",
            event_type="FOMC",
            timestamp=datetime(2026, 3, 19, 14, 0),
            impact=MacroImpact.HIGH,
        )
        now = datetime(2026, 3, 19, 13, 30)
        result = self.ctx.classify(events=[fomc], now=now)
        self.assertEqual(len(result["active_events"]), 1)
        self.assertEqual(result["active_events"][0]["name"], "FOMC")

    # --- Known events calendar ---

    def test_known_events_2026_populated(self):
        """The module should ship with a built-in 2026 macro calendar."""
        events = MacroRegimeContext.known_events_2026()
        self.assertGreater(len(events), 10)
        # Should include FOMC, CPI, NFP at minimum
        types = {e.event_type for e in events}
        self.assertIn("FOMC", types)
        self.assertIn("CPI", types)
        self.assertIn("NFP", types)

    def test_known_events_all_have_required_fields(self):
        events = MacroRegimeContext.known_events_2026()
        for e in events:
            self.assertIsInstance(e.name, str)
            self.assertIsInstance(e.event_type, str)
            self.assertIsInstance(e.timestamp, datetime)
            self.assertIsInstance(e.impact, MacroImpact)

    # --- Convenience method ---

    def test_classify_now(self):
        """classify_now uses current time automatically."""
        result = self.ctx.classify_now()
        self.assertIn("regime", result)
        self.assertIn("sizing_modifier", result)

    # --- Custom thresholds ---

    def test_custom_thresholds(self):
        ctx = MacroRegimeContext(
            high_impact_window_hours=0.5,  # 30 min instead of 1h
            elevated_window_hours=1.0,
            post_event_cooldown_hours=0.25,
        )
        fomc = MacroEvent(
            name="FOMC",
            event_type="FOMC",
            timestamp=datetime(2026, 3, 19, 14, 0),
            impact=MacroImpact.HIGH,
        )
        # 45 min before — outside custom HIGH window, but in ELEVATED
        now = datetime(2026, 3, 19, 13, 15)
        result = ctx.classify(events=[fomc], now=now)
        self.assertEqual(result["regime"], "ELEVATED")

    # --- JSON serialization ---

    def test_output_json_serializable(self):
        fomc = MacroEvent(
            name="FOMC",
            event_type="FOMC",
            timestamp=datetime(2026, 3, 19, 14, 0),
            impact=MacroImpact.HIGH,
        )
        result = self.ctx.classify(
            events=[fomc], now=datetime(2026, 3, 19, 13, 30))
        # Should not raise
        json_str = json.dumps(result)
        self.assertIsInstance(json_str, str)

    # --- Edge cases ---

    def test_event_exactly_now(self):
        fomc = MacroEvent(
            name="FOMC",
            event_type="FOMC",
            timestamp=datetime(2026, 3, 19, 14, 0),
            impact=MacroImpact.HIGH,
        )
        result = self.ctx.classify(
            events=[fomc], now=datetime(2026, 3, 19, 14, 0))
        self.assertEqual(result["regime"], "HIGH_IMPACT")

    def test_empty_event_list(self):
        result = self.ctx.classify(events=[], now=datetime(2026, 3, 21, 10, 0))
        self.assertEqual(result["regime"], "CALM")
        self.assertEqual(result["sizing_modifier"], 1.0)
        self.assertEqual(result["active_events"], [])

    def test_past_events_only(self):
        """Events far in the past should not affect regime."""
        old = MacroEvent(
            name="CPI",
            event_type="CPI",
            timestamp=datetime(2026, 1, 12, 8, 30),
            impact=MacroImpact.HIGH,
        )
        result = self.ctx.classify(
            events=[old], now=datetime(2026, 3, 21, 10, 0))
        self.assertEqual(result["regime"], "CALM")

    def test_future_events_far_away(self):
        future = MacroEvent(
            name="CPI",
            event_type="CPI",
            timestamp=datetime(2026, 6, 12, 8, 30),
            impact=MacroImpact.HIGH,
        )
        result = self.ctx.classify(
            events=[future], now=datetime(2026, 3, 21, 10, 0))
        self.assertEqual(result["regime"], "CALM")


class TestMacroRegimeCLI(unittest.TestCase):
    """Test CLI interface."""

    def test_cli_json_output(self):
        """CLI should produce valid JSON."""
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(
                os.path.dirname(__file__), "..", "macro_regime.py"),
             "--now", "2026-03-21T10:00:00"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("regime", data)
        self.assertIn("sizing_modifier", data)


if __name__ == "__main__":
    unittest.main()
