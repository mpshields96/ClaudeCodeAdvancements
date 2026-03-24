#!/usr/bin/env python3
"""Tests for convergence_detector wiring into reflect.py and improver.py (S150).

Validates that:
- reflect.py builds ConvergenceDetector from journal trace_analysis entries
- improver.py checks proposal history for convergence signals
- Convergence signals appear in reflection reports
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

_TESTS_DIR = Path(__file__).resolve().parent
_MODULE_DIR = _TESTS_DIR.parent
sys.path.insert(0, str(_MODULE_DIR))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_trace_entry(score, session_id=None, **kwargs):
    """Build a trace_analysis journal entry."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "trace_analysis",
        "domain": "self_learning",
        "outcome": "success" if score >= 50 else "needs_improvement",
        "session_id": session_id,
        "metrics": {"score": score, **kwargs},
    }


def _make_proposal(status="proposed", risk="LOW", pattern_type="retry_loop"):
    """Build a minimal proposal dict for improver tests."""
    import secrets
    return {
        "id": f"imp_test_{secrets.token_hex(4)}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "pattern_type": pattern_type,
        "pattern_data": {},
        "source": "trace_analysis",
        "proposed_fix": "Test fix",
        "expected_improvement": "Test improvement",
        "test_plan": "Test plan",
        "risk_level": risk,
        "target_module": "self-learning",
        "target_file": None,
        "outcome": None,
        "session_id": None,
    }


# ── reflect.py convergence wiring ─────────────────────────────────────────────

class TestReflectConvergenceCheck(unittest.TestCase):
    """Test check_improvement_convergence() in reflect.py."""

    def test_detects_plateau_from_trace_scores(self):
        """When trace scores plateau, convergence is detected."""
        import reflect
        # 6 trace entries with flat scores (72.0-72.3 range)
        entries = [_make_trace_entry(72.0 + i * 0.05) for i in range(6)]
        signals = reflect.check_improvement_convergence(entries)
        # Should detect plateau
        plateau_signals = [s for s in signals if s.signal_type == "plateau"]
        self.assertTrue(len(plateau_signals) > 0)

    def test_no_convergence_with_improving_scores(self):
        """When trace scores are improving, no convergence."""
        import reflect
        entries = [_make_trace_entry(50 + i * 5) for i in range(6)]
        signals = reflect.check_improvement_convergence(entries)
        plateau_signals = [s for s in signals if s.signal_type == "plateau"]
        self.assertEqual(len(plateau_signals), 0)

    def test_no_convergence_with_few_entries(self):
        """With fewer than 5 trace entries, no convergence possible."""
        import reflect
        entries = [_make_trace_entry(72.0) for _ in range(2)]
        signals = reflect.check_improvement_convergence(entries)
        self.assertEqual(len(signals), 0)

    def test_filters_only_trace_analysis_entries(self):
        """Only trace_analysis events are used, not other journal entries."""
        import reflect
        entries = [
            {"event_type": "nuclear_batch", "metrics": {"score": 50}},
            {"event_type": "bet_outcome", "metrics": {"score": 50}},
        ] + [_make_trace_entry(72.0) for _ in range(6)]
        signals = reflect.check_improvement_convergence(entries)
        # Should still detect plateau from the 6 trace entries
        plateau_signals = [s for s in signals if s.signal_type == "plateau"]
        self.assertTrue(len(plateau_signals) > 0)

    def test_detects_discard_streak_from_proposals(self):
        """When many proposals are rejected, discard streak is detected."""
        import reflect
        entries = [_make_trace_entry(72.0) for _ in range(3)]
        # Simulate rejected proposals via journal entries
        for _ in range(6):
            entries.append({
                "event_type": "improvement_outcome",
                "domain": "self_learning",
                "outcome": "rejected",
                "metrics": {},
            })
        signals = reflect.check_improvement_convergence(entries)
        discard_signals = [s for s in signals if s.signal_type == "discard_streak"]
        self.assertTrue(len(discard_signals) > 0)

    def test_returns_empty_for_empty_journal(self):
        """Empty journal produces no convergence signals."""
        import reflect
        signals = reflect.check_improvement_convergence([])
        self.assertEqual(signals, [])


class TestReflectOutputIncludesConvergence(unittest.TestCase):
    """Test that reflect() output includes convergence info."""

    @patch("reflect._load_journal")
    @patch("reflect._load_strategy")
    @patch("reflect.detect_patterns")
    @patch("reflect.check_improvement_convergence")
    def test_convergence_section_in_output(self, mock_conv, mock_patterns,
                                           mock_strategy, mock_journal):
        """reflect() prints convergence signals when detected."""
        import reflect
        from convergence_detector import ConvergenceSignal

        mock_journal.return_value = [_make_trace_entry(72.0) for _ in range(6)]
        mock_strategy.return_value = {}
        mock_patterns.return_value = []
        mock_conv.return_value = [
            ConvergenceSignal(
                signal_type="plateau",
                severity="converged",
                detail="Metric flat over 5 obs",
                recommendation="Try different strategy",
            )
        ]

        import io
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            reflect.reflect()

        output = captured.getvalue()
        self.assertIn("Convergence", output)
        self.assertIn("plateau", output)


# ── improver.py convergence wiring ────────────────────────────────────────────

class TestImproverConvergence(unittest.TestCase):
    """Test convergence detection in Improver class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "improvements.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_proposals(self, proposals):
        """Write proposal dicts to the store file."""
        with open(self.store_path, "w") as f:
            for p in proposals:
                f.write(json.dumps(p) + "\n")

    def test_check_convergence_no_proposals(self):
        """No proposals = no convergence."""
        import improver
        imp = improver.Improver(store_path=self.store_path)
        result = imp.check_convergence()
        self.assertEqual(result["signals"], [])
        self.assertFalse(result["is_converged"])

    def test_check_convergence_with_rejected_streak(self):
        """Many rejected proposals = discard streak convergence."""
        import improver
        proposals = [_make_proposal(status="rejected") for _ in range(6)]
        self._write_proposals(proposals)
        imp = improver.Improver(store_path=self.store_path)
        result = imp.check_convergence()
        self.assertTrue(result["is_converged"])
        self.assertTrue(any(s.signal_type == "discard_streak" for s in result["signals"]))

    def test_check_convergence_with_mixed_outcomes(self):
        """Mix of accepted and rejected = no convergence."""
        import improver
        proposals = []
        for i in range(6):
            status = "committed" if i % 2 == 0 else "rejected"
            proposals.append(_make_proposal(status=status))
        self._write_proposals(proposals)
        imp = improver.Improver(store_path=self.store_path)
        result = imp.check_convergence()
        # Should detect oscillation, not discard streak
        discard_signals = [s for s in result["signals"] if s.signal_type == "discard_streak"]
        self.assertEqual(len(discard_signals), 0)

    def test_convergence_summary_human_readable(self):
        """get_convergence_summary() returns readable text."""
        import improver
        proposals = [_make_proposal(status="rejected") for _ in range(6)]
        self._write_proposals(proposals)
        imp = improver.Improver(store_path=self.store_path)
        summary = imp.get_convergence_summary()
        self.assertIsInstance(summary, str)
        self.assertIn("CONVERGENCE", summary)

    def test_convergence_summary_no_signals(self):
        """Summary with no convergence is brief."""
        import improver
        imp = improver.Improver(store_path=self.store_path)
        summary = imp.get_convergence_summary()
        self.assertIn("No convergence", summary)


if __name__ == "__main__":
    unittest.main()
