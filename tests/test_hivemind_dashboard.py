"""Tests for hivemind_dashboard.py — Phase 1 status reporter."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPhase1Report(unittest.TestCase):
    """phase1_report() returns correct dict from combined data sources."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sessions_path = os.path.join(self.tmpdir, "hivemind_sessions.jsonl")
        self.metrics_path = os.path.join(self.tmpdir, "hivemind_metrics.jsonl")

    def _write_sessions(self, entries):
        with open(self.sessions_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def _write_metrics(self, entries):
        with open(self.metrics_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_empty_sources_returns_zero_metrics(self):
        from hivemind_dashboard import phase1_report
        report = phase1_report(self.sessions_path, self.metrics_path)
        self.assertEqual(report["consecutive_passes"], 0)
        self.assertEqual(report["total_sessions"], 0)
        self.assertEqual(report["coordination_failures"], 0)
        self.assertFalse(report["gate_ready"])

    def test_returns_dict_with_all_required_keys(self):
        from hivemind_dashboard import phase1_report
        report = phase1_report(self.sessions_path, self.metrics_path)
        required = [
            "consecutive_passes", "total_sessions", "total_passes",
            "total_fails", "gate_ready", "coordination_failures",
            "task_completion_rate", "worker_regressions",
            "avg_overhead_ratio", "failure_rate", "regression_rate",
        ]
        for key in required:
            self.assertIn(key, report, f"Missing key: {key}")

    def test_consecutive_passes_from_session_validator(self):
        from hivemind_dashboard import phase1_report
        self._write_sessions([
            {"session": 90, "verdict": "PASS", "worker_id": "cli1"},
            {"session": 91, "verdict": "PASS", "worker_id": "cli1"},
        ])
        report = phase1_report(self.sessions_path, self.metrics_path)
        self.assertEqual(report["consecutive_passes"], 2)

    def test_gate_ready_at_three_consecutive_passes(self):
        from hivemind_dashboard import phase1_report
        self._write_sessions([
            {"session": 89, "verdict": "PASS", "worker_id": "cli1"},
            {"session": 90, "verdict": "PASS", "worker_id": "cli1"},
            {"session": 91, "verdict": "PASS", "worker_id": "cli1"},
        ])
        report = phase1_report(self.sessions_path, self.metrics_path)
        self.assertTrue(report["gate_ready"])

    def test_gate_not_ready_with_two_passes(self):
        from hivemind_dashboard import phase1_report
        self._write_sessions([
            {"session": 90, "verdict": "PASS", "worker_id": "cli1"},
            {"session": 91, "verdict": "PASS", "worker_id": "cli1"},
        ])
        report = phase1_report(self.sessions_path, self.metrics_path)
        self.assertFalse(report["gate_ready"])

    def test_coordination_failures_from_metrics(self):
        from hivemind_dashboard import phase1_report
        self._write_metrics([
            {"session_id": "S90", "date": "2026-03-20",
             "sessions_completed": 1, "coordination_failures": 2,
             "task_completions": 3, "worker_regressions": 0, "overhead_ratio": 0.1},
        ])
        report = phase1_report(self.sessions_path, self.metrics_path)
        self.assertEqual(report["coordination_failures"], 2)

    def test_task_completion_rate_calculated(self):
        from hivemind_dashboard import phase1_report
        self._write_metrics([
            {"session_id": "S90", "date": "2026-03-20",
             "sessions_completed": 2, "coordination_failures": 0,
             "task_completions": 4, "worker_regressions": 0, "overhead_ratio": 0.05},
        ])
        report = phase1_report(self.sessions_path, self.metrics_path)
        # task_completions / sessions_completed = 4/2 = 2.0 or use total metrics sessions
        self.assertIsInstance(report["task_completion_rate"], float)
        self.assertGreater(report["task_completion_rate"], 0.0)

    def test_total_passes_and_fails_counted(self):
        from hivemind_dashboard import phase1_report
        self._write_sessions([
            {"session": 88, "verdict": "FAIL", "worker_id": "cli1"},
            {"session": 89, "verdict": "PASS", "worker_id": "cli1"},
            {"session": 90, "verdict": "PASS_WITH_WARNINGS", "worker_id": "cli1"},
        ])
        report = phase1_report(self.sessions_path, self.metrics_path)
        self.assertEqual(report["total_sessions"], 3)
        self.assertEqual(report["total_passes"], 2)
        self.assertEqual(report["total_fails"], 1)

    def test_streak_broken_by_fail(self):
        from hivemind_dashboard import phase1_report
        self._write_sessions([
            {"session": 88, "verdict": "PASS", "worker_id": "cli1"},
            {"session": 89, "verdict": "PASS", "worker_id": "cli1"},
            {"session": 90, "verdict": "FAIL", "worker_id": "cli1"},
            {"session": 91, "verdict": "PASS", "worker_id": "cli1"},
        ])
        report = phase1_report(self.sessions_path, self.metrics_path)
        self.assertEqual(report["consecutive_passes"], 1)
        self.assertFalse(report["gate_ready"])

    def test_worker_regressions_from_metrics(self):
        from hivemind_dashboard import phase1_report
        self._write_metrics([
            {"session_id": "S90", "date": "2026-03-20",
             "sessions_completed": 1, "coordination_failures": 0,
             "task_completions": 1, "worker_regressions": 2, "overhead_ratio": 0.1},
        ])
        report = phase1_report(self.sessions_path, self.metrics_path)
        self.assertEqual(report["worker_regressions"], 2)


class TestFormatReport(unittest.TestCase):
    """format_report() returns a multi-line string with all key sections."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sessions_path = os.path.join(self.tmpdir, "hivemind_sessions.jsonl")
        self.metrics_path = os.path.join(self.tmpdir, "hivemind_metrics.jsonl")

    def test_returns_string(self):
        from hivemind_dashboard import format_report
        result = format_report(self.sessions_path, self.metrics_path)
        self.assertIsInstance(result, str)

    def test_contains_phase1_label(self):
        from hivemind_dashboard import format_report
        result = format_report(self.sessions_path, self.metrics_path)
        self.assertIn("Phase 1", result)

    def test_contains_gate_status(self):
        from hivemind_dashboard import format_report
        result = format_report(self.sessions_path, self.metrics_path)
        # Should mention gate status one way or another
        self.assertTrue("gate" in result.lower() or "Gate" in result)

    def test_contains_consecutive_passes(self):
        from hivemind_dashboard import format_report
        with open(self.sessions_path, "w") as f:
            for s in [88, 89, 90]:
                f.write(json.dumps({"session": s, "verdict": "PASS", "worker_id": "cli1"}) + "\n")
        result = format_report(self.sessions_path, self.metrics_path)
        self.assertIn("3", result)

    def test_multiline_output(self):
        from hivemind_dashboard import format_report
        result = format_report(self.sessions_path, self.metrics_path)
        lines = [l for l in result.splitlines() if l.strip()]
        self.assertGreaterEqual(len(lines), 3)

    def test_gate_ready_shown_when_three_passes(self):
        from hivemind_dashboard import format_report
        with open(self.sessions_path, "w") as f:
            for s in [88, 89, 90]:
                f.write(json.dumps({"session": s, "verdict": "PASS", "worker_id": "cli1"}) + "\n")
        result = format_report(self.sessions_path, self.metrics_path)
        self.assertIn("READY", result)


class TestOverheadTimerIntegration(unittest.TestCase):
    """phase1_report() and format_report() integrate with overhead_timer."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sessions_path = os.path.join(self.tmpdir, "hivemind_sessions.jsonl")
        self.metrics_path = os.path.join(self.tmpdir, "hivemind_metrics.jsonl")
        self.overhead_path = os.path.join(self.tmpdir, "overhead_log.jsonl")

    def _write_overhead(self, entries):
        with open(self.overhead_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_overhead_ratio_key_present_in_report(self):
        from hivemind_dashboard import phase1_report
        report = phase1_report(self.sessions_path, self.metrics_path, self.overhead_path)
        self.assertIn("overhead_ratio", report)

    def test_overhead_ratio_zero_when_no_log(self):
        from hivemind_dashboard import phase1_report
        report = phase1_report(self.sessions_path, self.metrics_path, self.overhead_path)
        self.assertEqual(report["overhead_ratio"], 0.0)

    def test_overhead_ratio_averaged_from_log(self):
        from hivemind_dashboard import phase1_report
        self._write_overhead([
            {"session": 89, "ratio": 0.10},
            {"session": 90, "ratio": 0.20},
        ])
        report = phase1_report(self.sessions_path, self.metrics_path, self.overhead_path)
        self.assertAlmostEqual(report["overhead_ratio"], 0.15, places=5)

    def test_format_report_shows_overhead_from_timer(self):
        from hivemind_dashboard import format_report
        self._write_overhead([
            {"session": 90, "ratio": 0.08},
        ])
        result = format_report(self.sessions_path, self.metrics_path, self.overhead_path)
        # Should show overhead ratio in some form
        self.assertIn("8.0", result)


if __name__ == "__main__":
    unittest.main()
