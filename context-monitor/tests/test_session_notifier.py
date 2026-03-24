#!/usr/bin/env python3
"""Tests for session_notifier.py — ntfy.sh session-end notifications."""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO

import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import session_notifier

# Patch cooldown state file to a temp location for ALL tests,
# preventing cross-test interference from cooldown writes.
_ORIG_COOLDOWN_FILE = session_notifier.COOLDOWN_STATE_FILE
_TEST_COOLDOWN_DIR = tempfile.mkdtemp()
session_notifier.COOLDOWN_STATE_FILE = os.path.join(_TEST_COOLDOWN_DIR, "test-cooldown.json")


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

    def setUp(self):
        # Clear cooldown state before each test
        if os.path.exists(session_notifier.COOLDOWN_STATE_FILE):
            os.unlink(session_notifier.COOLDOWN_STATE_FILE)

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

    def setUp(self):
        if os.path.exists(session_notifier.COOLDOWN_STATE_FILE):
            os.unlink(session_notifier.COOLDOWN_STATE_FILE)

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

    def setUp(self):
        if os.path.exists(session_notifier.COOLDOWN_STATE_FILE):
            os.unlink(session_notifier.COOLDOWN_STATE_FILE)

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

    def setUp(self):
        if os.path.exists(session_notifier.COOLDOWN_STATE_FILE):
            os.unlink(session_notifier.COOLDOWN_STATE_FILE)

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

    def setUp(self):
        if os.path.exists(session_notifier.COOLDOWN_STATE_FILE):
            os.unlink(session_notifier.COOLDOWN_STATE_FILE)

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


class TestCooldown(unittest.TestCase):
    """Test notification cooldown mechanism (S144 Matthew directive)."""

    def setUp(self):
        import tempfile
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmpfile.close()
        self.state_file = self.tmpfile.name
        # Clean state
        if os.path.exists(self.state_file):
            os.unlink(self.state_file)

    def tearDown(self):
        if os.path.exists(self.state_file):
            os.unlink(self.state_file)

    def test_no_cooldown_file_allows_send(self):
        """First send always goes through."""
        result = session_notifier._check_cooldown("default", self.state_file)
        self.assertTrue(result)

    def test_high_priority_bypasses_cooldown(self):
        """High priority always sends, even in cooldown."""
        # Record a recent send
        session_notifier._record_send(self.state_file)
        result = session_notifier._check_cooldown("high", self.state_file)
        self.assertTrue(result)

    @patch.dict(os.environ, {"CCA_NTFY_COOLDOWN_MIN": "30"})
    def test_recent_send_blocks_default(self):
        """Default priority blocked if sent within cooldown window."""
        session_notifier._record_send(self.state_file)
        result = session_notifier._check_cooldown("default", self.state_file)
        self.assertFalse(result)

    @patch.dict(os.environ, {"CCA_NTFY_COOLDOWN_MIN": "30"})
    def test_recent_send_blocks_low(self):
        """Low priority also blocked by cooldown."""
        session_notifier._record_send(self.state_file)
        result = session_notifier._check_cooldown("low", self.state_file)
        self.assertFalse(result)

    @patch.dict(os.environ, {"CCA_NTFY_COOLDOWN_MIN": "0"})
    def test_cooldown_zero_disables(self):
        """Setting cooldown to 0 disables rate limiting."""
        session_notifier._record_send(self.state_file)
        result = session_notifier._check_cooldown("default", self.state_file)
        self.assertTrue(result)

    def test_expired_cooldown_allows_send(self):
        """Send allowed after cooldown window expires."""
        import time as t
        # Write a timestamp 60 minutes ago
        old_ts = t.time() - 3600
        with open(self.state_file, "w") as f:
            json.dump({"last_sent_ts": old_ts}, f)
        result = session_notifier._check_cooldown("default", self.state_file)
        self.assertTrue(result)

    def test_corrupt_state_file_allows_send(self):
        """Corrupt state file = fail open, allow send."""
        with open(self.state_file, "w") as f:
            f.write("not json")
        result = session_notifier._check_cooldown("default", self.state_file)
        self.assertTrue(result)

    def test_record_send_creates_file(self):
        """_record_send creates the state file."""
        session_notifier._record_send(self.state_file)
        self.assertTrue(os.path.exists(self.state_file))
        with open(self.state_file) as f:
            data = json.load(f)
        self.assertIn("last_sent_ts", data)

    @patch.dict(os.environ, {"CCA_NTFY_COOLDOWN_MIN": "not_a_number"})
    def test_invalid_cooldown_env_uses_default(self):
        """Invalid env var falls back to default cooldown."""
        cooldown = session_notifier._get_cooldown_minutes()
        self.assertEqual(cooldown, session_notifier.DEFAULT_COOLDOWN_MINUTES)

    @patch.dict(os.environ, {"MOBILE_APPROVER_TOPIC": "test-topic", "CCA_NTFY_COOLDOWN_MIN": "30"})
    @patch("session_notifier.urlopen")
    def test_send_notification_respects_cooldown(self, mock_urlopen):
        """Integration: send_notification skips when in cooldown."""
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        # Patch the cooldown state file to use our temp
        with patch.object(session_notifier, 'COOLDOWN_STATE_FILE', self.state_file):
            # First send should go through
            r1 = session_notifier.send_notification("Test", "body1")
            self.assertTrue(r1)
            # Second send should be blocked by cooldown
            r2 = session_notifier.send_notification("Test", "body2")
            self.assertFalse(r2)
            # High priority should bypass
            r3 = session_notifier.send_notification("Error", "critical", priority="high")
            self.assertTrue(r3)


if __name__ == "__main__":
    unittest.main()
