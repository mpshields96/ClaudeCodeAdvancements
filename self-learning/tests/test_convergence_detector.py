#!/usr/bin/env python3
"""Tests for convergence_detector.py — MT-10 Growth: convergence detection."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from convergence_detector import (
    ConvergenceDetector, ConvergenceSignal, Observation,
)


class TestObservation(unittest.TestCase):
    """Test Observation dataclass."""

    def test_create_observation(self):
        obs = Observation(metric_value=72.5, accepted=True, label="test")
        self.assertEqual(obs.metric_value, 72.5)
        self.assertTrue(obs.accepted)

    def test_observation_none_metric(self):
        obs = Observation(metric_value=None, accepted=False)
        self.assertIsNone(obs.metric_value)

    def test_observation_default_label(self):
        obs = Observation(metric_value=1.0, accepted=True)
        self.assertEqual(obs.label, "")


class TestConvergenceSignal(unittest.TestCase):
    """Test ConvergenceSignal dataclass."""

    def test_create_signal(self):
        sig = ConvergenceSignal(
            signal_type="plateau", severity="warning",
            detail="test detail", recommendation="pivot",
        )
        self.assertEqual(sig.signal_type, "plateau")
        self.assertEqual(sig.severity, "warning")


class TestConvergenceDetectorInit(unittest.TestCase):
    """Test detector initialization and configuration."""

    def test_default_config(self):
        d = ConvergenceDetector()
        self.assertEqual(d.plateau_threshold, 0.5)
        self.assertEqual(d.plateau_window, 5)
        self.assertEqual(d.discard_streak_limit, 5)
        self.assertEqual(d.oscillation_window, 6)

    def test_custom_config(self):
        d = ConvergenceDetector(plateau_threshold=1.0, plateau_window=10)
        self.assertEqual(d.plateau_threshold, 1.0)
        self.assertEqual(d.plateau_window, 10)

    def test_empty_observations(self):
        d = ConvergenceDetector()
        self.assertEqual(len(d.observations), 0)
        self.assertEqual(d.check_convergence(), [])
        self.assertFalse(d.is_converged)

    def test_add_observation(self):
        d = ConvergenceDetector()
        d.add_observation(metric_value=72.5, accepted=True, label="s1")
        self.assertEqual(len(d.observations), 1)
        self.assertEqual(d.observations[0].metric_value, 72.5)


class TestPlateauDetection(unittest.TestCase):
    """Test metric plateau detection."""

    def test_no_plateau_too_few_observations(self):
        d = ConvergenceDetector(plateau_window=5)
        for _ in range(3):
            d.add_observation(metric_value=72.5, accepted=True)
        signals = d.check_convergence()
        plateau_signals = [s for s in signals if s.signal_type == "plateau"]
        self.assertEqual(len(plateau_signals), 0)

    def test_plateau_detected_flat_metric(self):
        d = ConvergenceDetector(plateau_window=5, plateau_threshold=0.5)
        for v in [72.5, 72.5, 72.5, 72.5, 72.5]:
            d.add_observation(metric_value=v, accepted=True)
        signals = d.check_convergence()
        plateau = [s for s in signals if s.signal_type == "plateau"]
        self.assertEqual(len(plateau), 1)
        self.assertEqual(plateau[0].severity, "converged")

    def test_plateau_detected_tiny_change(self):
        d = ConvergenceDetector(plateau_window=5, plateau_threshold=0.5)
        for v in [72.5, 72.6, 72.5, 72.7, 72.6]:
            d.add_observation(metric_value=v, accepted=True)
        signals = d.check_convergence()
        plateau = [s for s in signals if s.signal_type == "plateau"]
        self.assertTrue(len(plateau) >= 1)

    def test_no_plateau_with_progress(self):
        d = ConvergenceDetector(plateau_window=5, plateau_threshold=0.5)
        for v in [70.0, 71.0, 72.0, 73.0, 74.0]:
            d.add_observation(metric_value=v, accepted=True)
        signals = d.check_convergence()
        plateau = [s for s in signals if s.signal_type == "plateau"]
        self.assertEqual(len(plateau), 0)

    def test_plateau_ignores_none_metrics(self):
        d = ConvergenceDetector(plateau_window=5)
        d.add_observation(metric_value=72.0, accepted=True)
        d.add_observation(metric_value=None, accepted=True)
        d.add_observation(metric_value=72.1, accepted=True)
        # Only 2 metric observations, not enough for window of 5
        signals = d.check_convergence()
        plateau = [s for s in signals if s.signal_type == "plateau"]
        self.assertEqual(len(plateau), 0)

    def test_plateau_zero_first_value(self):
        d = ConvergenceDetector(plateau_window=3)
        for v in [0.0, 0.0, 0.0]:
            d.add_observation(metric_value=v, accepted=True)
        signals = d.check_convergence()
        plateau = [s for s in signals if s.signal_type == "plateau"]
        # Should not crash on division by zero
        self.assertEqual(len(plateau), 0)


class TestDiscardStreakDetection(unittest.TestCase):
    """Test discard streak detection."""

    def test_no_streak_all_accepted(self):
        d = ConvergenceDetector(discard_streak_limit=5)
        for _ in range(10):
            d.add_observation(accepted=True)
        signals = d.check_convergence()
        streaks = [s for s in signals if s.signal_type == "discard_streak"]
        self.assertEqual(len(streaks), 0)

    def test_streak_detected(self):
        d = ConvergenceDetector(discard_streak_limit=5)
        d.add_observation(accepted=True)  # break point
        for _ in range(5):
            d.add_observation(accepted=False)
        signals = d.check_convergence()
        streaks = [s for s in signals if s.signal_type == "discard_streak"]
        self.assertEqual(len(streaks), 1)
        self.assertEqual(streaks[0].severity, "converged")

    def test_streak_warning_before_limit(self):
        d = ConvergenceDetector(discard_streak_limit=5)
        d.add_observation(accepted=True)
        for _ in range(3):  # 60% of 5 = 3
            d.add_observation(accepted=False)
        signals = d.check_convergence()
        streaks = [s for s in signals if s.signal_type == "discard_streak"]
        self.assertEqual(len(streaks), 1)
        self.assertEqual(streaks[0].severity, "warning")

    def test_streak_broken_by_accept(self):
        d = ConvergenceDetector(discard_streak_limit=5)
        for _ in range(4):
            d.add_observation(accepted=False)
        d.add_observation(accepted=True)  # breaks streak
        d.add_observation(accepted=False)  # streak = 1
        signals = d.check_convergence()
        streaks = [s for s in signals if s.signal_type == "discard_streak"]
        self.assertEqual(len(streaks), 0)

    def test_streak_too_few_observations(self):
        d = ConvergenceDetector(discard_streak_limit=5)
        d.add_observation(accepted=False)
        signals = d.check_convergence()
        streaks = [s for s in signals if s.signal_type == "discard_streak"]
        self.assertEqual(len(streaks), 0)

    def test_long_streak(self):
        d = ConvergenceDetector(discard_streak_limit=3)
        for _ in range(10):
            d.add_observation(accepted=False)
        signals = d.check_convergence()
        streaks = [s for s in signals if s.signal_type == "discard_streak"]
        self.assertEqual(len(streaks), 1)
        self.assertIn("10", streaks[0].detail)


class TestOscillationDetection(unittest.TestCase):
    """Test alternating accept/discard oscillation detection."""

    def test_no_oscillation_all_same(self):
        d = ConvergenceDetector(oscillation_window=6)
        for _ in range(6):
            d.add_observation(accepted=True)
        signals = d.check_convergence()
        osc = [s for s in signals if s.signal_type == "oscillation"]
        self.assertEqual(len(osc), 0)

    def test_oscillation_detected_alternating(self):
        d = ConvergenceDetector(oscillation_window=6, oscillation_ratio=0.4)
        for i in range(6):
            d.add_observation(accepted=(i % 2 == 0))
        signals = d.check_convergence()
        osc = [s for s in signals if s.signal_type == "oscillation"]
        self.assertEqual(len(osc), 1)

    def test_perfect_alternation_is_converged(self):
        d = ConvergenceDetector(oscillation_window=6, oscillation_ratio=0.4)
        # Perfect alternation: T F T F T F = 5/5 = 100%
        for i in range(6):
            d.add_observation(accepted=(i % 2 == 0))
        signals = d.check_convergence()
        osc = [s for s in signals if s.signal_type == "oscillation"]
        self.assertEqual(len(osc), 1)
        self.assertEqual(osc[0].severity, "converged")

    def test_no_oscillation_too_few(self):
        d = ConvergenceDetector(oscillation_window=6)
        d.add_observation(accepted=True)
        d.add_observation(accepted=False)
        signals = d.check_convergence()
        osc = [s for s in signals if s.signal_type == "oscillation"]
        self.assertEqual(len(osc), 0)

    def test_oscillation_recommendation_mentions_decompose(self):
        d = ConvergenceDetector(oscillation_window=4, oscillation_ratio=0.4)
        for i in range(4):
            d.add_observation(accepted=(i % 2 == 0))
        signals = d.check_convergence()
        osc = [s for s in signals if s.signal_type == "oscillation"]
        if osc:
            self.assertIn("Decompose", osc[0].recommendation)


class TestCombinedSignals(unittest.TestCase):
    """Test multiple simultaneous convergence signals."""

    def test_plateau_and_discard_streak(self):
        d = ConvergenceDetector(plateau_window=5, discard_streak_limit=5)
        # Flat metric + all rejected
        for v in [72.5, 72.5, 72.5, 72.5, 72.5]:
            d.add_observation(metric_value=v, accepted=False)
        signals = d.check_convergence()
        types = {s.signal_type for s in signals}
        self.assertIn("plateau", types)
        self.assertIn("discard_streak", types)

    def test_is_converged_property(self):
        d = ConvergenceDetector(discard_streak_limit=3)
        for _ in range(3):
            d.add_observation(accepted=False)
        self.assertTrue(d.is_converged)

    def test_has_warnings_property(self):
        d = ConvergenceDetector(discard_streak_limit=5)
        d.add_observation(accepted=True)
        for _ in range(3):
            d.add_observation(accepted=False)
        self.assertTrue(d.has_warnings)

    def test_no_warnings_when_healthy(self):
        d = ConvergenceDetector()
        for v in [70.0, 72.0, 74.0, 76.0, 78.0]:
            d.add_observation(metric_value=v, accepted=True)
        self.assertFalse(d.has_warnings)
        self.assertFalse(d.is_converged)


class TestSummary(unittest.TestCase):
    """Test human-readable summary output."""

    def test_summary_no_signals(self):
        d = ConvergenceDetector()
        d.add_observation(metric_value=72.0, accepted=True)
        s = d.summary()
        self.assertIn("No convergence signals", s)
        self.assertIn("1 observations", s)

    def test_summary_with_signals(self):
        d = ConvergenceDetector(discard_streak_limit=3)
        for _ in range(3):
            d.add_observation(accepted=False)
        s = d.summary()
        self.assertIn("CONVERGENCE DETECTED", s)
        self.assertIn("discard_streak", s)


class TestSerialization(unittest.TestCase):
    """Test to_dict/from_dict round-trip."""

    def test_round_trip(self):
        d = ConvergenceDetector(plateau_threshold=1.0, plateau_window=10)
        d.add_observation(metric_value=72.5, accepted=True, label="s1")
        d.add_observation(metric_value=73.0, accepted=False, label="s2")

        data = d.to_dict()
        d2 = ConvergenceDetector.from_dict(data)

        self.assertEqual(len(d2.observations), 2)
        self.assertEqual(d2.observations[0].metric_value, 72.5)
        self.assertEqual(d2.observations[1].accepted, False)
        self.assertEqual(d2.plateau_threshold, 1.0)
        self.assertEqual(d2.plateau_window, 10)

    def test_from_dict_empty(self):
        d = ConvergenceDetector.from_dict({})
        self.assertEqual(len(d.observations), 0)
        # Should use defaults
        self.assertEqual(d.plateau_threshold, 0.5)

    def test_to_dict_structure(self):
        d = ConvergenceDetector()
        d.add_observation(metric_value=1.0, accepted=True)
        data = d.to_dict()
        self.assertIn("observations", data)
        self.assertIn("config", data)
        self.assertEqual(len(data["observations"]), 1)


class TestReset(unittest.TestCase):
    """Test reset functionality."""

    def test_reset_clears_observations(self):
        d = ConvergenceDetector()
        for _ in range(10):
            d.add_observation(metric_value=72.0, accepted=True)
        self.assertEqual(len(d.observations), 10)
        d.reset()
        self.assertEqual(len(d.observations), 0)
        self.assertFalse(d.is_converged)


if __name__ == "__main__":
    unittest.main()
