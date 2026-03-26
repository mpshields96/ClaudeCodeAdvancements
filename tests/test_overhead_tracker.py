#!/usr/bin/env python3
"""Tests for overhead_tracker.py — CCA token overhead measurement."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import overhead_tracker


class TestFormatTokens(unittest.TestCase):
    def test_small_number(self):
        self.assertEqual(overhead_tracker.format_tokens(500), "500")

    def test_thousands(self):
        self.assertEqual(overhead_tracker.format_tokens(16063), "16.1K")

    def test_large(self):
        self.assertEqual(overhead_tracker.format_tokens(49254), "49.3K")

    def test_zero(self):
        self.assertEqual(overhead_tracker.format_tokens(0), "0")

    def test_exactly_1000(self):
        self.assertEqual(overhead_tracker.format_tokens(1000), "1.0K")


class TestMeasureOverhead(unittest.TestCase):
    @patch("overhead_tracker.subprocess.run")
    def test_successful_measurement(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "usage": {
                    "cache_creation_input_tokens": 49000,
                    "cache_read_input_tokens": 0,
                    "input_tokens": 3,
                    "output_tokens": 14,
                },
                "modelUsage": {
                    "claude-opus-4-6[1m]": {"inputTokens": 3}
                },
            }),
        )
        result = overhead_tracker.measure_overhead("/tmp/test")
        self.assertEqual(result["total_overhead"], 49003)
        self.assertEqual(result["model"], "claude-opus-4-6[1m]")
        self.assertGreater(result["vs_empty_baseline"], 0)

    @patch("overhead_tracker.subprocess.run")
    def test_claude_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = overhead_tracker.measure_overhead()
        self.assertIn("error", result)

    @patch("overhead_tracker.subprocess.run")
    def test_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=120)
        result = overhead_tracker.measure_overhead()
        self.assertIn("error", result)

    @patch("overhead_tracker.subprocess.run")
    def test_nonzero_exit(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error msg")
        result = overhead_tracker.measure_overhead()
        self.assertIn("error", result)

    @patch("overhead_tracker.subprocess.run")
    def test_invalid_json(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="not json")
        result = overhead_tracker.measure_overhead()
        self.assertIn("error", result)


class TestHistory(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            with patch.object(overhead_tracker, "HISTORY_FILE", overhead_tracker.Path(path)):
                m = {
                    "timestamp": "2026-03-26T05:00:00Z",
                    "total_overhead": 49000,
                    "cache_creation": 49000,
                    "cache_read": 0,
                    "input_tokens": 3,
                }
                overhead_tracker.save_measurement(m)
                history = overhead_tracker.load_history()
                self.assertEqual(len(history), 1)
                self.assertEqual(history[0]["total_overhead"], 49000)
        finally:
            os.unlink(path)

    def test_skip_save_on_error(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            with patch.object(overhead_tracker, "HISTORY_FILE", overhead_tracker.Path(path)):
                overhead_tracker.save_measurement({"error": "test"})
                history = overhead_tracker.load_history()
                self.assertEqual(len(history), 0)
        finally:
            os.unlink(path)

    def test_load_empty_history(self):
        with patch.object(overhead_tracker, "HISTORY_FILE", overhead_tracker.Path("/nonexistent")):
            self.assertEqual(overhead_tracker.load_history(), [])


class TestBaselines(unittest.TestCase):
    def test_baselines_exist(self):
        self.assertEqual(overhead_tracker.BASELINE_EMPTY, 16063)
        self.assertEqual(overhead_tracker.BASELINE_REAL_PROJECT, 23000)

    def test_ratio_calculation(self):
        result = {
            "total_overhead": 49000,
            "vs_empty_baseline": 49000 - 16063,
            "ratio_to_empty": round(49000 / 16063, 2),
        }
        self.assertAlmostEqual(result["ratio_to_empty"], 3.05, places=1)


class TestCLI(unittest.TestCase):
    @patch("overhead_tracker.measure_overhead")
    @patch("overhead_tracker.save_measurement")
    def test_json_output(self, mock_save, mock_measure):
        mock_measure.return_value = {
            "total_overhead": 49000,
            "cache_creation": 49000,
            "cache_read": 0,
            "input_tokens": 3,
            "output_tokens": 14,
            "model": "opus",
            "vs_empty_baseline": 32937,
            "vs_project_baseline": 26000,
            "ratio_to_empty": 3.05,
            "timestamp": "2026-03-26T05:00:00Z",
            "project_dir": "/tmp",
        }
        import io
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            overhead_tracker.cli_main(["--json"])
        output = json.loads(buf.getvalue())
        self.assertEqual(output["total_overhead"], 49000)

    def test_history_no_data(self):
        with patch.object(overhead_tracker, "HISTORY_FILE", overhead_tracker.Path("/nonexistent")):
            import io
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                overhead_tracker.cli_main(["--history"])
            self.assertIn("No measurements", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
