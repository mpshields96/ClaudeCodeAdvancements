#!/usr/bin/env python3
"""
Tests for AG-1: agent-guard/hooks/mobile_approver.py
Tests decision logic and formatting only — no live ntfy calls.
Run: python3 agent-guard/tests/test_mobile_approver.py
"""

import json
import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mobile_approver import (
    _needs_approval,
    _format_notification,
    _allow_response,
    _deny_response,
    _ntfy_publish,
    _ntfy_poll,
    APPROVAL_REQUIRED_TOOLS,
    ALWAYS_ALLOW_TOOLS,
)


class TestNeedsApproval(unittest.TestCase):
    def test_bash_needs_approval(self):
        self.assertTrue(_needs_approval("Bash"))

    def test_write_needs_approval(self):
        self.assertTrue(_needs_approval("Write"))

    def test_edit_needs_approval(self):
        self.assertTrue(_needs_approval("Edit"))

    def test_task_needs_approval(self):
        self.assertTrue(_needs_approval("Task"))

    def test_read_always_allowed(self):
        self.assertFalse(_needs_approval("Read"))

    def test_glob_always_allowed(self):
        self.assertFalse(_needs_approval("Glob"))

    def test_grep_always_allowed(self):
        self.assertFalse(_needs_approval("Grep"))

    def test_webfetch_always_allowed(self):
        self.assertFalse(_needs_approval("WebFetch"))

    def test_unknown_tool_not_required(self):
        # Unknown tools are not in APPROVAL_REQUIRED_TOOLS — fail safe (allow)
        self.assertFalse(_needs_approval("SomeNewTool"))

    def test_todowrite_always_allowed(self):
        self.assertFalse(_needs_approval("TodoWrite"))


class TestFormatNotification(unittest.TestCase):
    def test_bash_shows_command(self):
        title, message = _format_notification("Bash", {"command": "rm -rf /tmp/test"})
        self.assertIn("Bash", title)
        self.assertIn("rm -rf", message)

    def test_write_shows_file_path(self):
        title, message = _format_notification("Write", {"file_path": "/Users/matt/Projects/app/main.py"})
        self.assertIn("Write", title)
        self.assertIn("main.py", message)

    def test_long_command_truncated(self):
        long_cmd = "echo " + "x" * 200
        title, message = _format_notification("Bash", {"command": long_cmd})
        self.assertLessEqual(len(message), 300)

    def test_empty_input_doesnt_crash(self):
        title, message = _format_notification("Write", {})
        self.assertIn("Write", title)
        self.assertIsInstance(message, str)

    def test_description_included(self):
        title, message = _format_notification("Bash", {"description": "Run tests"})
        self.assertIn("Run tests", message)

    def test_relative_path_shown(self):
        cwd = os.getcwd()
        title, message = _format_notification("Write", {"file_path": f"{cwd}/main.py"})
        self.assertNotIn(cwd, message)
        self.assertIn("main.py", message)


class TestAllowDenyResponses(unittest.TestCase):
    def test_allow_response_structure(self):
        resp = _allow_response()
        self.assertEqual(resp["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_deny_response_structure(self):
        resp = _deny_response("test reason")
        self.assertEqual(resp["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("denyReason", resp["hookSpecificOutput"])

    def test_deny_default_reason(self):
        resp = _deny_response()
        self.assertIn("iPhone", resp["hookSpecificOutput"]["denyReason"])

    def test_responses_are_valid_json(self):
        allow = json.dumps(_allow_response())
        deny = json.dumps(_deny_response())
        self.assertIsInstance(json.loads(allow), dict)
        self.assertIsInstance(json.loads(deny), dict)


class TestNtfyPublish(unittest.TestCase):
    def test_returns_true_on_200(self):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        with patch("mobile_approver.urlopen", return_value=mock_resp):
            result = _ntfy_publish("test-topic", "Title", "Message", "resp-topic")
        self.assertTrue(result)

    def test_returns_false_on_network_error(self):
        from urllib.error import URLError
        with patch("mobile_approver.urlopen", side_effect=URLError("connection refused")):
            result = _ntfy_publish("test-topic", "Title", "Message", "resp-topic")
        self.assertFalse(result)

    def test_request_includes_action_buttons(self):
        captured = {}
        def fake_urlopen(req, timeout=None):
            captured["headers"] = dict(req.headers)
            mock_resp = MagicMock()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.status = 200
            return mock_resp
        with patch("mobile_approver.urlopen", fake_urlopen):
            _ntfy_publish("mytopic", "T", "M", "resp-123")
        self.assertIn("Actions", captured["headers"])
        self.assertIn("allow", captured["headers"]["Actions"])
        self.assertIn("deny", captured["headers"]["Actions"])


class TestNtfyPoll(unittest.TestCase):
    def _make_urlopen(self, body: str):
        """Returns a urlopen mock that immediately returns a valid ntfy message."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({
            "id": "abc123",
            "message": body,
            "event": "message"
        }).encode()
        return mock_resp

    def test_returns_allow_on_allow_body(self):
        # Use a short timeout — urlopen returns immediately so it won't actually wait
        with patch("mobile_approver.urlopen", return_value=self._make_urlopen("allow")):
            with patch("mobile_approver.time.sleep"):  # patch sleep to not wait
                result = _ntfy_poll("resp-topic", timeout=10)
        self.assertEqual(result, "allow")

    def test_returns_deny_on_deny_body(self):
        with patch("mobile_approver.urlopen", return_value=self._make_urlopen("deny")):
            with patch("mobile_approver.time.sleep"):
                result = _ntfy_poll("resp-topic", timeout=10)
        self.assertEqual(result, "deny")

    def test_returns_none_on_timeout(self):
        # Make urlopen always fail and use a real 0-second timeout
        from urllib.error import URLError
        with patch("mobile_approver.urlopen", side_effect=URLError("error")):
            with patch("mobile_approver.time.sleep"):
                result = _ntfy_poll("resp-topic", timeout=0)
        self.assertIsNone(result)

    def test_ignores_invalid_body(self):
        # urlopen returns a non-allow/deny message; poll should timeout
        with patch("mobile_approver.urlopen", return_value=self._make_urlopen("some random text")):
            with patch("mobile_approver.time.sleep"):
                result = _ntfy_poll("resp-topic", timeout=0)
        self.assertIsNone(result)


class TestMainIntegration(unittest.TestCase):
    """Integration tests for main() via stdin/stdout."""

    def _run_main(self, hook_input: dict, env: dict = None) -> dict:
        import io
        from unittest.mock import patch
        import mobile_approver

        env = env or {}
        stdin_data = json.dumps(hook_input)

        with patch.dict(os.environ, env, clear=False):
            with patch("sys.stdin", io.StringIO(stdin_data)):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    mobile_approver.main()
                return json.loads(captured.getvalue())

    def test_disabled_flag_allows_all(self):
        hook = {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}
        result = self._run_main(hook, env={"MOBILE_APPROVER_DISABLED": "1"})
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_no_topic_configured_allows_all(self):
        hook = {"tool_name": "Bash", "tool_input": {"command": "echo hi"}}
        env = {"MOBILE_APPROVER_TOPIC": ""}
        result = self._run_main(hook, env=env)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_read_tool_always_allowed(self):
        hook = {"tool_name": "Read", "tool_input": {"file_path": "/etc/passwd"}}
        result = self._run_main(hook)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_ntfy_failure_fails_open(self):
        from urllib.error import URLError
        hook = {"tool_name": "Bash", "tool_input": {"command": "echo hi"}}
        env = {"MOBILE_APPROVER_TOPIC": "test-topic"}
        with patch("mobile_approver._ntfy_publish", return_value=False):
            result = self._run_main(hook, env=env)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_allow_response_from_phone(self):
        hook = {"tool_name": "Write", "tool_input": {"file_path": "/tmp/test.py"}}
        env = {"MOBILE_APPROVER_TOPIC": "test-topic", "MOBILE_APPROVER_TIMEOUT": "5"}
        with patch("mobile_approver._ntfy_publish", return_value=True):
            with patch("mobile_approver._ntfy_poll", return_value="allow"):
                result = self._run_main(hook, env=env)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_deny_response_from_phone(self):
        hook = {"tool_name": "Bash", "tool_input": {"command": "rm important.py"}}
        env = {"MOBILE_APPROVER_TOPIC": "test-topic", "MOBILE_APPROVER_TIMEOUT": "5"}
        with patch("mobile_approver._ntfy_publish", return_value=True):
            with patch("mobile_approver._ntfy_poll", return_value="deny"):
                result = self._run_main(hook, env=env)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_timeout_defaults_to_allow(self):
        hook = {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/test.py"}}
        env = {"MOBILE_APPROVER_TOPIC": "test-topic", "MOBILE_APPROVER_DEFAULT": "allow"}
        with patch("mobile_approver._ntfy_publish", return_value=True):
            with patch("mobile_approver._ntfy_poll", return_value=None):
                result = self._run_main(hook, env=env)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_timeout_deny_default(self):
        hook = {"tool_name": "Bash", "tool_input": {"command": "echo hi"}}
        env = {
            "MOBILE_APPROVER_TOPIC": "test-topic",
            "MOBILE_APPROVER_DEFAULT": "deny"
        }
        with patch("mobile_approver._ntfy_publish", return_value=True):
            with patch("mobile_approver._ntfy_poll", return_value=None):
                result = self._run_main(hook, env=env)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_invalid_json_stdin_allows(self):
        import io
        import mobile_approver
        with patch("sys.stdin", io.StringIO("NOT JSON")):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                mobile_approver.main()
            result = json.loads(captured.getvalue())
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
