#!/usr/bin/env python3
"""Tests for coordination_dashboard.py — multi-chat session status view."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coordination_dashboard import (
    get_recent_commits,
    get_session_commits,
    get_test_health,
    build_dashboard,
    format_dashboard,
    format_compact,
)


class TestGetRecentCommits(unittest.TestCase):
    """Test git commit retrieval."""

    @patch('coordination_dashboard.subprocess.run')
    def test_returns_commits(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc1234 First\ndef5678 Second\n"
        )
        commits = get_recent_commits(2)
        self.assertEqual(len(commits), 2)

    @patch('coordination_dashboard.subprocess.run')
    def test_handles_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        commits = get_recent_commits()
        self.assertEqual(commits, [])

    @patch('coordination_dashboard.subprocess.run')
    def test_handles_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)
        commits = get_recent_commits()
        self.assertEqual(commits, [])


class TestGetSessionCommits(unittest.TestCase):
    """Test session-specific commit counting."""

    @patch('coordination_dashboard.subprocess.run')
    def test_counts_commits(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc S116: First\ndef S116: Second\nghi S116: Third\n"
        )
        count = get_session_commits("S116")
        self.assertEqual(count, 3)

    @patch('coordination_dashboard.subprocess.run')
    def test_zero_commits(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="\n")
        count = get_session_commits("S999")
        self.assertEqual(count, 0)

    @patch('coordination_dashboard.subprocess.run')
    def test_handles_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        count = get_session_commits("S116")
        self.assertEqual(count, 0)


class TestGetTestHealth(unittest.TestCase):
    """Test health check."""

    def test_critical_tests_exist(self):
        health = get_test_health()
        # At least some critical test files should exist in the project
        self.assertGreater(health["critical_tests_total"], 0)
        self.assertIn("all_present", health)

    def test_returns_counts(self):
        health = get_test_health()
        self.assertIsInstance(health["critical_tests_present"], int)
        self.assertIsInstance(health["critical_tests_total"], int)


class TestBuildDashboard(unittest.TestCase):
    """Test dashboard data construction."""

    @patch('coordination_dashboard.get_session_commits', return_value=5)
    @patch('coordination_dashboard.get_worker_status', return_value="IDLE")
    @patch('coordination_dashboard.get_peak_hours_status', return_value="OFF-PEAK (2x limits)")
    @patch('coordination_dashboard.get_recent_commits', return_value=["abc First", "def Second"])
    def test_builds_complete_data(self, *mocks):
        data = build_dashboard("S116")
        self.assertEqual(data["session"], "S116")
        self.assertEqual(data["commits"], 5)
        self.assertEqual(data["worker_status"], "IDLE")
        self.assertIn("timestamp", data)
        self.assertIn("test_health", data)
        self.assertIn("recent_commits", data)

    @patch('coordination_dashboard.get_session_commits', return_value=0)
    @patch('coordination_dashboard.get_worker_status', return_value="WORKING: design-skills")
    @patch('coordination_dashboard.get_peak_hours_status', return_value="PEAK (standard limits)")
    @patch('coordination_dashboard.get_recent_commits', return_value=[])
    def test_handles_working_state(self, *mocks):
        data = build_dashboard("S117")
        self.assertEqual(data["worker_status"], "WORKING: design-skills")
        self.assertEqual(data["session"], "S117")


class TestFormatDashboard(unittest.TestCase):
    """Test dashboard formatting."""

    def _sample_data(self):
        return {
            "timestamp": "14:30:00",
            "session": "S116",
            "commits": 5,
            "worker_status": "WORKING: chart_generator.py",
            "peak_hours": "OFF-PEAK (2x limits)",
            "test_health": {"all_present": True, "critical_tests_present": 3, "critical_tests_total": 3},
            "recent_commits": ["abc S116: First", "def S116: Second"],
        }

    def test_contains_session(self):
        output = format_dashboard(self._sample_data())
        self.assertIn("S116", output)

    def test_contains_commits(self):
        output = format_dashboard(self._sample_data())
        self.assertIn("5", output)

    def test_contains_worker_status(self):
        output = format_dashboard(self._sample_data())
        self.assertIn("WORKING", output)

    def test_contains_peak_hours(self):
        output = format_dashboard(self._sample_data())
        self.assertIn("OFF-PEAK", output)

    def test_contains_test_health(self):
        output = format_dashboard(self._sample_data())
        self.assertIn("OK", output)

    def test_test_health_missing(self):
        data = self._sample_data()
        data["test_health"]["all_present"] = False
        output = format_dashboard(data)
        self.assertIn("MISSING", output)

    def test_contains_recent_commits(self):
        output = format_dashboard(self._sample_data())
        self.assertIn("abc S116: First", output)


class TestFormatCompact(unittest.TestCase):
    """Test compact one-line formatting."""

    def test_compact_format(self):
        data = {
            "timestamp": "14:30:00",
            "session": "S116",
            "commits": 5,
            "worker_status": "WORKING: chart_generator.py",
            "peak_hours": "OFF-PEAK (2x limits)",
            "test_health": {"all_present": True},
            "recent_commits": [],
        }
        output = format_compact(data)
        self.assertIn("S116", output)
        self.assertIn("5 commits", output)
        self.assertIn("WORKING", output)
        # Should be one line
        self.assertEqual(output.count('\n'), 0)

    def test_compact_idle_worker(self):
        data = {
            "timestamp": "15:00:00",
            "session": "S117",
            "commits": 0,
            "worker_status": "IDLE",
            "peak_hours": "PEAK (standard limits)",
            "test_health": {"all_present": True},
            "recent_commits": [],
        }
        output = format_compact(data)
        self.assertIn("IDLE", output)
        self.assertIn("PEAK", output)


class TestCLI(unittest.TestCase):
    """Test CLI execution."""

    def test_default_output(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "coordination_dashboard.py")],
            capture_output=True, text=True, timeout=15,
        )
        self.assertIn("Coordination Dashboard", result.stdout)

    def test_compact_output(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "coordination_dashboard.py"), "--compact"],
            capture_output=True, text=True, timeout=15,
        )
        # Should be a single line
        lines = [l for l in result.stdout.strip().split('\n') if l.strip()]
        self.assertEqual(len(lines), 1)

    def test_json_output(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "coordination_dashboard.py"), "--json"],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(result.stdout)
        self.assertIn("session", data)
        self.assertIn("commits", data)


if __name__ == "__main__":
    unittest.main()
