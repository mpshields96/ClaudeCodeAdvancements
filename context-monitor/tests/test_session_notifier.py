#!/usr/bin/env python3
"""Tests for session_notifier.py — ntfy.sh session-end notifications."""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import session_notifier


class TestNotificationMessage(unittest.TestCase):
    """Test notification message formatting."""

    def test_wrap_message_basic(self):
        msg = session_notifier.format_wrap_message(
            tasks_completed=3,
            elapsed_minutes=47.2,
            session_id="S95",
        )
        self.assertIn("S95", msg["title"])
        self.assertIn("3 tasks", msg["body"])
        self.assertIn("47m", msg["body"])

    def test_wrap_message_with_grade(self):
        msg = session_notifier.format_wrap_message(
            tasks_completed=5,
            elapsed_minutes=58.0,
            session_id="S95",
            grade="B+",
        )
        self.assertIn("B+", msg["body"])

    def test_wrap_message_zero_tasks(self):
        msg = session_notifier.format_wrap_message(
            tasks_completed=0,
            elapsed_minutes=12.0,
            session_id="S95",
        )
        self.assertIn("0 tasks", msg["body"])

    def test_wrap_message_no_session_id(self):
        msg = session_notifier.format_wrap_message(
            tasks_completed=2,
            elapsed_minutes=30.0,
        )
        self.assertIn("CCA Session", msg["title"])

    def test_error_message_basic(self):
        msg = session_notifier.format_error_message(
            error="Test suite regression in agent-guard",
            task_name="MT-20 validation",
        )
        self.assertIn("Error", msg["title"])
        self.assertIn("regression", msg["body"])
        self.assertIn("MT-20", msg["body"])

    def test_error_message_no_task(self):
        msg = session_notifier.format_error_message(
            error="Context critical — forced wrap",
        )
        self.assertIn("Error", msg["title"])
        self.assertIn("critical", msg["body"])

    def test_error_message_truncates_long_error(self):
        long_error = "x" * 500
        msg = session_notifier.format_error_message(error=long_error)
        self.assertLessEqual(len(msg["body"]), 300)


class TestSendNotification(unittest.TestCase):
    """Test the ntfy.sh send function."""

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_send_success(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = session_notifier.send_notification(
            title="Test", body="Test body", priority="default"
        )
        self.assertTrue(result)
        mock_urlopen.assert_called_once()

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_send_network_failure(self, mock_urlopen):
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Network down")

        result = session_notifier.send_notification(
            title="Test", body="Test body"
        )
        self.assertFalse(result)

    @patch.dict(os.environ, {}, clear=True)
    def test_send_no_topic_configured(self):
        # Remove MOBILE_APPROVER_TOPIC if present
        os.environ.pop("MOBILE_APPROVER_TOPIC", None)
        result = session_notifier.send_notification(
            title="Test", body="Test body"
        )
        self.assertFalse(result)

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": ""})
    def test_send_empty_topic(self):
        result = session_notifier.send_notification(
            title="Test", body="Test body"
        )
        self.assertFalse(result)

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_send_with_high_priority(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        session_notifier.send_notification(
            title="Error", body="Critical", priority="high"
        )

        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.get_header("Priority"), "high")


class TestNotifySessionEnd(unittest.TestCase):
    """Test the high-level notify_session_end function."""

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_notify_session_end_wrap(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = session_notifier.notify_session_end(
            tasks_completed=4,
            elapsed_minutes=55.0,
            session_id="S95",
            grade="A-",
        )
        self.assertTrue(result)

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_notify_session_error(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = session_notifier.notify_session_error(
            error="Tests failing after MT-20 change",
            task_name="MT-20 Phase 7",
        )
        self.assertTrue(result)


class TestCLI(unittest.TestCase):
    """Test CLI interface."""

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_cli_wrap(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        session_notifier.cli_main([
            "wrap", "--tasks", "3", "--elapsed", "45", "--session", "S95"
        ])

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_cli_error(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        session_notifier.cli_main([
            "error", "--message", "Something broke", "--task", "MT-22"
        ])

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_cli_wrap_with_grade(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        session_notifier.cli_main([
            "wrap", "--tasks", "5", "--elapsed", "58",
            "--session", "S95", "--grade", "A"
        ])

    def test_cli_no_args_prints_usage(self):
        # Should not raise
        session_notifier.cli_main([])

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_cli_wrap_reads_pacer_state(self, mock_urlopen):
        """CLI wrap --auto reads from session pacer state file."""
        import tempfile
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        # Create a fake pacer state
        from datetime import datetime, timezone, timedelta
        start = (datetime.now(timezone.utc) - timedelta(minutes=42)).isoformat()
        state = {
            "started_at": start,
            "max_duration_minutes": 60,
            "tasks": [
                {"name": "Task A", "started_at": start, "completed_at": start, "commit_hash": "abc"},
                {"name": "Task B", "started_at": start, "completed_at": start, "commit_hash": "def"},
                {"name": "Task C", "started_at": start, "completed_at": None, "commit_hash": None},
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(state, f)
            tmp_path = f.name

        try:
            session_notifier.cli_main([
                "wrap", "--auto", "--pacer-state", tmp_path
            ])
            # Should have sent notification with 2 completed tasks
            mock_urlopen.assert_called_once()
        finally:
            os.unlink(tmp_path)


class TestLoopHealthMessage(unittest.TestCase):
    """Test loop health notification formatting (MT-35 Phase 3)."""

    def test_format_loop_health_basic(self):
        msg = session_notifier.format_loop_health_message(
            iteration=5,
            max_iterations=50,
            total_crashes=0,
            uptime_minutes=120.0,
        )
        self.assertIn("Loop", msg["title"])
        self.assertIn("5/50", msg["body"])
        self.assertIn("120m", msg["body"])

    def test_format_loop_health_with_crashes(self):
        msg = session_notifier.format_loop_health_message(
            iteration=10,
            max_iterations=50,
            total_crashes=2,
            uptime_minutes=300.0,
        )
        self.assertIn("2 crashes", msg["body"])

    def test_format_loop_health_zero_crashes_omitted(self):
        msg = session_notifier.format_loop_health_message(
            iteration=3,
            max_iterations=50,
            total_crashes=0,
            uptime_minutes=45.0,
        )
        self.assertNotIn("crash", msg["body"])

    def test_format_loop_health_with_last_grade(self):
        msg = session_notifier.format_loop_health_message(
            iteration=7,
            max_iterations=50,
            total_crashes=0,
            uptime_minutes=200.0,
            last_session_grade="A-",
        )
        self.assertIn("A-", msg["body"])

    def test_format_loop_health_with_tests(self):
        msg = session_notifier.format_loop_health_message(
            iteration=4,
            max_iterations=50,
            total_crashes=0,
            uptime_minutes=90.0,
            test_suites_passing=213,
        )
        self.assertIn("213", msg["body"])


class TestLoopStoppedMessage(unittest.TestCase):
    """Test loop stopped notification."""

    def test_format_loop_stopped_normal(self):
        msg = session_notifier.format_loop_stopped_message(
            reason="Max iterations reached",
            total_iterations=50,
            total_crashes=1,
            uptime_minutes=600.0,
        )
        self.assertIn("Stopped", msg["title"])
        self.assertIn("50 iterations", msg["body"])
        self.assertIn("Max iterations", msg["body"])

    def test_format_loop_stopped_crash(self):
        msg = session_notifier.format_loop_stopped_message(
            reason="3 consecutive crashes",
            total_iterations=8,
            total_crashes=3,
            uptime_minutes=120.0,
        )
        self.assertIn("crash", msg["body"].lower())


class TestNotifyLoopHealth(unittest.TestCase):
    """Test high-level loop health notification API."""

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_notify_loop_health(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = session_notifier.notify_loop_health(
            iteration=5,
            max_iterations=50,
            total_crashes=0,
            uptime_minutes=120.0,
        )
        self.assertTrue(result)

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_notify_loop_stopped(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = session_notifier.notify_loop_stopped(
            reason="Max iterations",
            total_iterations=50,
            total_crashes=1,
            uptime_minutes=600.0,
        )
        self.assertTrue(result)

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_notify_loop_health_low_priority(self, mock_urlopen):
        """Health pings use low priority to avoid excessive buzzing."""
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        session_notifier.notify_loop_health(
            iteration=5, max_iterations=50,
            total_crashes=0, uptime_minutes=120.0,
        )
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.get_header("Priority"), "low")

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_notify_loop_stopped_high_priority_on_crash(self, mock_urlopen):
        """Loop stopped by crash uses high priority."""
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        session_notifier.notify_loop_stopped(
            reason="3 consecutive crashes",
            total_iterations=8, total_crashes=3, uptime_minutes=120.0,
        )
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.get_header("Priority"), "high")


class TestLoopHealthCLI(unittest.TestCase):
    """Test CLI for loop health commands."""

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_cli_loop_health(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        session_notifier.cli_main([
            "loop-health", "--iteration", "5", "--max", "50",
            "--crashes", "0", "--uptime", "120"
        ])
        mock_urlopen.assert_called_once()

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic"})
    @patch("session_notifier.urlopen")
    def test_cli_loop_stopped(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        session_notifier.cli_main([
            "loop-stopped", "--reason", "Max iterations",
            "--iterations", "50", "--crashes", "1", "--uptime", "600"
        ])
        mock_urlopen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
