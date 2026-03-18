#!/usr/bin/env python3
"""
Tests for auto_wrap.py — Automatic session wrap-up trigger.

Determines when a session should wrap based on:
1. Context health zone (red/critical = wrap)
2. Compaction count (>1 compaction = wrap)
3. Token usage exceeding safe quality limits
4. Session duration / commit count

TDD: Tests written first, then implementation.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

_THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(_THIS_DIR.parent))


class TestWrapDecision(unittest.TestCase):
    """Tests for WrapDecision dataclass."""

    def test_import(self):
        from auto_wrap import WrapDecision
        self.assertTrue(callable(WrapDecision))

    def test_should_wrap_false_by_default(self):
        from auto_wrap import WrapDecision
        d = WrapDecision()
        self.assertFalse(d.should_wrap)

    def test_to_dict_serializable(self):
        from auto_wrap import WrapDecision
        d = WrapDecision(should_wrap=True, reason="test", urgency="high")
        result = d.to_dict()
        json.dumps(result)  # Must be serializable
        self.assertEqual(result["should_wrap"], True)


class TestAutoWrapMonitor(unittest.TestCase):
    """Tests for AutoWrapMonitor — reads context state and decides."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "context-health.json")
        self.wrap_state_path = os.path.join(self.tmpdir, "wrap-state.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_context_state(self, **overrides):
        defaults = {
            "pct": 30.0,
            "zone": "green",
            "tokens": 60000,
            "turns": 50,
            "window": 200000,
            "thresholds": {"yellow": 50, "red": 70, "critical": 85},
            "session_id": "test-session",
            "autocompact_pct": None,
            "autocompact_proximity": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        defaults.update(overrides)
        with open(self.state_path, "w") as f:
            json.dump(defaults, f)

    def test_import(self):
        from auto_wrap import AutoWrapMonitor
        self.assertTrue(callable(AutoWrapMonitor))

    def test_green_zone_no_wrap(self):
        """Green zone should not trigger wrap."""
        from auto_wrap import AutoWrapMonitor
        self._write_context_state(pct=30.0, zone="green")
        m = AutoWrapMonitor(context_state_path=self.state_path, wrap_state_path=self.wrap_state_path)
        decision = m.check()
        self.assertFalse(decision.should_wrap)

    def test_yellow_zone_no_wrap(self):
        """Yellow zone alone should not trigger wrap (just a warning)."""
        from auto_wrap import AutoWrapMonitor
        self._write_context_state(pct=55.0, zone="yellow")
        m = AutoWrapMonitor(context_state_path=self.state_path, wrap_state_path=self.wrap_state_path)
        decision = m.check()
        self.assertFalse(decision.should_wrap)

    def test_red_zone_triggers_wrap(self):
        """Red zone should trigger wrap."""
        from auto_wrap import AutoWrapMonitor
        self._write_context_state(pct=75.0, zone="red")
        m = AutoWrapMonitor(context_state_path=self.state_path, wrap_state_path=self.wrap_state_path)
        decision = m.check()
        self.assertTrue(decision.should_wrap)
        self.assertIn("red", decision.reason.lower())

    def test_critical_zone_triggers_urgent_wrap(self):
        """Critical zone should trigger urgent wrap."""
        from auto_wrap import AutoWrapMonitor
        self._write_context_state(pct=90.0, zone="critical")
        m = AutoWrapMonitor(context_state_path=self.state_path, wrap_state_path=self.wrap_state_path)
        decision = m.check()
        self.assertTrue(decision.should_wrap)
        self.assertEqual(decision.urgency, "critical")

    def test_compaction_count_triggers_wrap(self):
        """More than 1 compaction should trigger wrap."""
        from auto_wrap import AutoWrapMonitor
        self._write_context_state(pct=40.0, zone="green")
        m = AutoWrapMonitor(context_state_path=self.state_path, wrap_state_path=self.wrap_state_path)
        m.record_compaction()
        decision = m.check()
        self.assertFalse(decision.should_wrap)  # 1 compaction is ok
        m.record_compaction()
        decision = m.check()
        self.assertTrue(decision.should_wrap)
        self.assertIn("compaction", decision.reason.lower())

    def test_high_token_count_triggers_wrap(self):
        """Tokens exceeding quality ceiling should trigger wrap."""
        from auto_wrap import AutoWrapMonitor
        self._write_context_state(pct=65.0, zone="yellow", tokens=450000, window=1000000)
        m = AutoWrapMonitor(context_state_path=self.state_path, wrap_state_path=self.wrap_state_path)
        decision = m.check()
        self.assertTrue(decision.should_wrap)
        self.assertIn("token", decision.reason.lower())

    def test_no_state_file_no_wrap(self):
        """Missing state file should not crash or trigger wrap."""
        from auto_wrap import AutoWrapMonitor
        m = AutoWrapMonitor(
            context_state_path=os.path.join(self.tmpdir, "nonexistent.json"),
            wrap_state_path=self.wrap_state_path,
        )
        decision = m.check()
        self.assertFalse(decision.should_wrap)

    def test_wrap_state_persists(self):
        """Wrap state (compaction count) should persist across instances."""
        from auto_wrap import AutoWrapMonitor
        self._write_context_state(pct=30.0, zone="green")
        m1 = AutoWrapMonitor(context_state_path=self.state_path, wrap_state_path=self.wrap_state_path)
        m1.record_compaction()
        m1.save_state()

        m2 = AutoWrapMonitor(context_state_path=self.state_path, wrap_state_path=self.wrap_state_path)
        self.assertEqual(m2.compaction_count, 1)

    def test_decision_includes_stats(self):
        """WrapDecision should include current context stats."""
        from auto_wrap import AutoWrapMonitor
        self._write_context_state(pct=75.0, zone="red", tokens=150000)
        m = AutoWrapMonitor(context_state_path=self.state_path, wrap_state_path=self.wrap_state_path)
        decision = m.check()
        self.assertIsNotNone(decision.context_pct)
        self.assertIsNotNone(decision.zone)

    def test_reset_clears_state(self):
        """reset() should clear compaction count and wrap state."""
        from auto_wrap import AutoWrapMonitor
        self._write_context_state(pct=30.0, zone="green")
        m = AutoWrapMonitor(context_state_path=self.state_path, wrap_state_path=self.wrap_state_path)
        m.record_compaction()
        m.record_compaction()
        m.reset()
        self.assertEqual(m.compaction_count, 0)


class TestWrapThresholds(unittest.TestCase):
    """Tests for configurable wrap thresholds."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "context-health.json")
        self.wrap_state_path = os.path.join(self.tmpdir, "wrap-state.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_context_state(self, **overrides):
        defaults = {
            "pct": 30.0, "zone": "green", "tokens": 60000, "turns": 50,
            "window": 200000, "thresholds": {"yellow": 50, "red": 70, "critical": 85},
            "session_id": "test", "autocompact_pct": None,
            "autocompact_proximity": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        defaults.update(overrides)
        with open(self.state_path, "w") as f:
            json.dump(defaults, f)

    def test_custom_token_ceiling(self):
        """Should respect custom token quality ceiling."""
        from auto_wrap import AutoWrapMonitor
        self._write_context_state(pct=50.0, zone="yellow", tokens=300000)
        m = AutoWrapMonitor(
            context_state_path=self.state_path,
            wrap_state_path=self.wrap_state_path,
            token_quality_ceiling=250000,
        )
        decision = m.check()
        self.assertTrue(decision.should_wrap)

    def test_custom_max_compactions(self):
        """Should respect custom max compaction count."""
        from auto_wrap import AutoWrapMonitor
        self._write_context_state(pct=30.0, zone="green")
        m = AutoWrapMonitor(
            context_state_path=self.state_path,
            wrap_state_path=self.wrap_state_path,
            max_compactions=3,
        )
        m.record_compaction()
        m.record_compaction()
        self.assertFalse(m.check().should_wrap)
        m.record_compaction()
        self.assertTrue(m.check().should_wrap)

    def test_default_thresholds_reasonable(self):
        """Default thresholds should be sane."""
        from auto_wrap import AutoWrapMonitor
        m = AutoWrapMonitor(
            context_state_path=self.state_path,
            wrap_state_path=self.wrap_state_path,
        )
        self.assertGreaterEqual(m.token_quality_ceiling, 200000)
        self.assertLessEqual(m.token_quality_ceiling, 500000)
        self.assertGreaterEqual(m.max_compactions, 1)
        self.assertLessEqual(m.max_compactions, 5)


class TestAutoWrapCLI(unittest.TestCase):
    """Tests for CLI interface."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cli_check_command(self):
        """CLI 'check' should output wrap decision."""
        from auto_wrap import cli_main
        import io
        from contextlib import redirect_stdout
        state_path = os.path.join(self.tmpdir, "ctx.json")
        with open(state_path, "w") as f:
            json.dump({"pct": 30.0, "zone": "green", "tokens": 60000, "turns": 50,
                       "window": 200000, "session_id": "test",
                       "updated_at": datetime.now(timezone.utc).isoformat()}, f)
        out = io.StringIO()
        with redirect_stdout(out):
            cli_main(["check", "--state", state_path,
                      "--wrap-state", os.path.join(self.tmpdir, "wrap.json")])
        output = out.getvalue()
        self.assertIn("wrap", output.lower())

    def test_cli_status_command(self):
        """CLI 'status' should show current wrap monitor state."""
        from auto_wrap import cli_main
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            cli_main(["status", "--wrap-state", os.path.join(self.tmpdir, "wrap.json")])
        output = out.getvalue()
        self.assertIn("compaction", output.lower())


if __name__ == "__main__":
    unittest.main()
