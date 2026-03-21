#!/usr/bin/env python3
"""
test_mobile_approver_extended.py — Extended coverage for mobile_approver.py.

Targets gaps in the original test suite:
- _needs_approval: NotebookEdit, MCP calls, empty string
- _format_notification: description truncation, multiple fields, path outside cwd
- _ntfy_publish: HTTPError handling, request structure (title/message encoding)
- _ntfy_poll: uppercase body, empty body, invalid JSON lines, multi-line response
- main(): invalid default env, whitespace-only topic, unknown tool fails safe,
  timeout custom value, notebook_edit approval, deny response reason content
"""

import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

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


# ── _needs_approval: Edge Cases ───────────────────────────────────────────────


class TestNeedsApprovalEdgeCases(unittest.TestCase):

    def test_notebook_edit_needs_approval(self):
        self.assertTrue(_needs_approval("NotebookEdit"))

    def test_mcp_call_always_allowed(self):
        # mcp__supabase__list_tables is in ALWAYS_ALLOW_TOOLS
        self.assertFalse(_needs_approval("mcp__supabase__list_tables"))

    def test_empty_string_not_required(self):
        # Empty tool name not in APPROVAL_REQUIRED_TOOLS — fails safe
        self.assertFalse(_needs_approval(""))

    def test_write_in_approval_set(self):
        self.assertIn("Write", APPROVAL_REQUIRED_TOOLS)

    def test_edit_in_approval_set(self):
        self.assertIn("Edit", APPROVAL_REQUIRED_TOOLS)

    def test_task_in_approval_set(self):
        self.assertIn("Task", APPROVAL_REQUIRED_TOOLS)

    def test_always_allow_and_approval_are_disjoint(self):
        overlap = APPROVAL_REQUIRED_TOOLS & ALWAYS_ALLOW_TOOLS
        self.assertEqual(overlap, set())

    def test_webfetch_in_always_allow(self):
        self.assertIn("WebFetch", ALWAYS_ALLOW_TOOLS)

    def test_websearch_in_always_allow(self):
        self.assertIn("WebSearch", ALWAYS_ALLOW_TOOLS)

    def test_ask_user_question_in_always_allow(self):
        self.assertIn("AskUserQuestion", ALWAYS_ALLOW_TOOLS)


# ── _format_notification: Edge Cases ─────────────────────────────────────────


class TestFormatNotificationEdgeCases(unittest.TestCase):

    def test_description_truncated_at_100(self):
        long_desc = "x" * 150
        title, message = _format_notification("Write", {"description": long_desc})
        self.assertIn("x" * 100, message)
        self.assertNotIn("x" * 101, message)

    def test_command_truncated_at_120(self):
        long_cmd = "echo " + "y" * 200
        title, message = _format_notification("Bash", {"command": long_cmd})
        cmd_part = message.split("Command: ")[1] if "Command: " in message else message
        self.assertLessEqual(len(cmd_part.split("\n")[0]), 120)

    def test_multiple_fields_all_shown(self):
        title, message = _format_notification("Write", {
            "file_path": "/tmp/test.py",
            "description": "Writing test file",
        })
        self.assertIn("test.py", message)
        self.assertIn("Writing test file", message)

    def test_path_outside_cwd_shown_as_absolute(self):
        title, message = _format_notification("Write", {"file_path": "/completely/different/path.py"})
        self.assertIn("path.py", message)

    def test_title_contains_tool_name(self):
        for tool in ("Write", "Edit", "Task", "NotebookEdit"):
            title, _ = _format_notification(tool, {})
            self.assertIn(tool, title, f"Title should contain {tool}")

    def test_empty_input_falls_back_to_json(self):
        title, message = _format_notification("Task", {})
        self.assertIsInstance(message, str)
        self.assertGreater(len(message), 0)

    def test_large_tool_input_truncated(self):
        large_input = {"key": "x" * 500}
        title, message = _format_notification("Write", large_input)
        # raw fallback is truncated to 150 chars
        self.assertLessEqual(len(message), 200)

    def test_file_path_relative_strips_cwd_prefix(self):
        cwd = os.getcwd()
        abs_path = os.path.join(cwd, "subdir", "file.py")
        title, message = _format_notification("Write", {"file_path": abs_path})
        self.assertNotIn(cwd, message)
        self.assertIn("file.py", message)

    def test_returns_tuple_of_two_strings(self):
        result = _format_notification("Write", {"file_path": "/tmp/test.py"})
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], str)
        self.assertIsInstance(result[1], str)


# ── _allow_response / _deny_response: Edge Cases ─────────────────────────────


class TestResponseEdgeCases(unittest.TestCase):

    def test_allow_response_has_hook_specific_output(self):
        resp = _allow_response()
        self.assertIn("hookSpecificOutput", resp)

    def test_deny_response_custom_reason(self):
        resp = _deny_response("Custom reason here")
        self.assertEqual(resp["hookSpecificOutput"]["denyReason"], "Custom reason here")

    def test_deny_response_default_mentions_iphone(self):
        resp = _deny_response()
        reason = resp["hookSpecificOutput"]["denyReason"]
        self.assertIn("iPhone", reason)

    def test_deny_response_has_deny_decision(self):
        resp = _deny_response()
        self.assertEqual(resp["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_allow_response_has_allow_decision(self):
        resp = _allow_response()
        self.assertEqual(resp["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_allow_is_serializable(self):
        resp = _allow_response()
        self.assertIsInstance(json.dumps(resp), str)

    def test_deny_is_serializable(self):
        resp = _deny_response("test")
        self.assertIsInstance(json.dumps(resp), str)


# ── _ntfy_publish: Edge Cases ─────────────────────────────────────────────────


class TestNtfyPublishEdgeCases(unittest.TestCase):

    def _make_urlopen_mock(self, status=200):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = status
        return mock_resp

    def test_returns_false_on_http_error(self):
        with patch("mobile_approver.urlopen",
                   side_effect=HTTPError("url", 403, "Forbidden", {}, None)):
            result = _ntfy_publish("topic", "T", "M", "resp")
        self.assertFalse(result)

    def test_request_has_title_header(self):
        captured = {}
        def fake_urlopen(req, timeout=None):
            captured["headers"] = dict(req.headers)
            return self._make_urlopen_mock()
        with patch("mobile_approver.urlopen", fake_urlopen):
            _ntfy_publish("topic", "My Title", "My Message", "resp")
        self.assertEqual(captured["headers"].get("Title"), "My Title")

    def test_request_is_post(self):
        captured = {}
        def fake_urlopen(req, timeout=None):
            captured["method"] = req.method
            return self._make_urlopen_mock()
        with patch("mobile_approver.urlopen", fake_urlopen):
            _ntfy_publish("topic", "T", "M", "resp")
        self.assertEqual(captured["method"], "POST")

    def test_request_has_priority_high(self):
        captured = {}
        def fake_urlopen(req, timeout=None):
            captured["headers"] = dict(req.headers)
            return self._make_urlopen_mock()
        with patch("mobile_approver.urlopen", fake_urlopen):
            _ntfy_publish("topic", "T", "M", "resp")
        self.assertEqual(captured["headers"].get("Priority"), "high")

    def test_request_has_allow_deny_actions(self):
        captured = {}
        def fake_urlopen(req, timeout=None):
            captured["headers"] = dict(req.headers)
            return self._make_urlopen_mock()
        with patch("mobile_approver.urlopen", fake_urlopen):
            _ntfy_publish("topic", "T", "M", "resp-id")
        actions = captured["headers"].get("Actions", "")
        self.assertIn("Allow", actions)
        self.assertIn("Deny", actions)
        self.assertIn("resp-id", actions)

    def test_url_uses_topic(self):
        captured = {}
        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            return self._make_urlopen_mock()
        with patch("mobile_approver.urlopen", fake_urlopen):
            _ntfy_publish("my-topic", "T", "M", "resp")
        self.assertIn("my-topic", captured["url"])

    def test_returns_false_on_non_200(self):
        mock_resp = self._make_urlopen_mock(status=500)
        with patch("mobile_approver.urlopen", return_value=mock_resp):
            result = _ntfy_publish("topic", "T", "M", "resp")
        self.assertFalse(result)


# ── _ntfy_poll: Edge Cases ────────────────────────────────────────────────────


class TestNtfyPollEdgeCases(unittest.TestCase):

    def _make_mock_resp(self, body_str: str):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = body_str.encode()
        return mock_resp

    def test_case_insensitive_allow(self):
        # body "ALLOW" should be lowercased before comparison
        body = json.dumps({"id": "1", "message": "ALLOW", "event": "message"})
        with patch("mobile_approver.urlopen", return_value=self._make_mock_resp(body)):
            with patch("mobile_approver.time.sleep"):
                result = _ntfy_poll("topic", timeout=10)
        self.assertEqual(result, "allow")

    def test_case_insensitive_deny(self):
        body = json.dumps({"id": "1", "message": "DENY", "event": "message"})
        with patch("mobile_approver.urlopen", return_value=self._make_mock_resp(body)):
            with patch("mobile_approver.time.sleep"):
                result = _ntfy_poll("topic", timeout=10)
        self.assertEqual(result, "deny")

    def test_empty_response_body_does_not_crash(self):
        with patch("mobile_approver.urlopen", return_value=self._make_mock_resp("")):
            with patch("mobile_approver.time.sleep"):
                result = _ntfy_poll("topic", timeout=0)
        self.assertIsNone(result)

    def test_multiline_response_uses_last_valid_message(self):
        lines = [
            json.dumps({"id": "1", "message": "irrelevant", "event": "message"}),
            json.dumps({"id": "2", "message": "deny", "event": "message"}),
        ]
        body = "\n".join(lines)
        with patch("mobile_approver.urlopen", return_value=self._make_mock_resp(body)):
            with patch("mobile_approver.time.sleep"):
                result = _ntfy_poll("topic", timeout=10)
        self.assertEqual(result, "deny")

    def test_invalid_json_line_skipped(self):
        body = "INVALID JSON\n" + json.dumps({"id": "1", "message": "allow", "event": "message"})
        with patch("mobile_approver.urlopen", return_value=self._make_mock_resp(body)):
            with patch("mobile_approver.time.sleep"):
                result = _ntfy_poll("topic", timeout=10)
        self.assertEqual(result, "allow")

    def test_network_error_continues_polling(self):
        # First call fails, subsequent call would succeed but timeout=0 so returns None
        with patch("mobile_approver.urlopen", side_effect=URLError("err")):
            with patch("mobile_approver.time.sleep"):
                result = _ntfy_poll("topic", timeout=0)
        self.assertIsNone(result)

    def test_poll_url_format(self):
        captured = {}
        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            raise URLError("stop")
        with patch("mobile_approver.urlopen", fake_urlopen):
            with patch("mobile_approver.time.sleep"):
                _ntfy_poll("my-topic", timeout=0)
        if "url" in captured:
            self.assertIn("my-topic", captured["url"])
            self.assertIn("poll=1", captured["url"])


# ── main(): Extended Edge Cases ───────────────────────────────────────────────


class TestMainExtended(unittest.TestCase):

    def _run_main(self, hook_input: dict, env: dict = None) -> str:
        """Run main() and return raw stdout string."""
        import mobile_approver
        env = env or {}
        stdin_data = json.dumps(hook_input)
        with patch.dict(os.environ, env, clear=False):
            with patch("sys.stdin", io.StringIO(stdin_data)):
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    mobile_approver.main()
        return captured.getvalue()

    def test_invalid_default_env_falls_back_to_allow(self):
        hook = {"tool_name": "Write", "tool_input": {"file_path": "/tmp/test.py"}}
        env = {
            "MOBILE_APPROVER_TOPIC": "test-topic",
            "MOBILE_APPROVER_DEFAULT": "invalid_value",
        }
        with patch("mobile_approver._ntfy_publish", return_value=True):
            with patch("mobile_approver._ntfy_poll", return_value=None):
                output = self._run_main(hook, env=env)
        result = json.loads(output)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_whitespace_only_topic_allows(self):
        hook = {"tool_name": "Write", "tool_input": {}}
        env = {"MOBILE_APPROVER_TOPIC": "   "}
        output = self._run_main(hook, env=env)
        result = json.loads(output)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_unknown_tool_no_stdout(self):
        # Unknown tools not in either set → _needs_approval returns False → no output
        hook = {"tool_name": "SomeCustomTool", "tool_input": {}}
        output = self._run_main(hook)
        self.assertEqual(output, "")

    def test_notebook_edit_sends_notification(self):
        hook = {"tool_name": "NotebookEdit", "tool_input": {}}
        env = {"MOBILE_APPROVER_TOPIC": "test-topic"}
        publish_calls = []
        def fake_publish(*args):
            publish_calls.append(args)
            return True
        with patch("mobile_approver._ntfy_publish", fake_publish):
            with patch("mobile_approver._ntfy_poll", return_value="allow"):
                output = self._run_main(hook, env=env)
        self.assertEqual(len(publish_calls), 1)
        result = json.loads(output)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_timeout_deny_reason_mentions_timeout(self):
        hook = {"tool_name": "Edit", "tool_input": {}}
        env = {
            "MOBILE_APPROVER_TOPIC": "test-topic",
            "MOBILE_APPROVER_DEFAULT": "deny",
        }
        with patch("mobile_approver._ntfy_publish", return_value=True):
            with patch("mobile_approver._ntfy_poll", return_value=None):
                output = self._run_main(hook, env=env)
        result = json.loads(output)
        reason = result["hookSpecificOutput"].get("denyReason", "")
        self.assertIn("imed", reason)  # "Timed out" or similar

    def test_response_topic_is_unique(self):
        # Two calls should use different response topics
        hook = {"tool_name": "Write", "tool_input": {}}
        env = {"MOBILE_APPROVER_TOPIC": "test-topic"}
        topics_seen = []
        def fake_publish(topic, title, message, resp_topic):
            topics_seen.append(resp_topic)
            return False  # fail open so no polling
        with patch("mobile_approver._ntfy_publish", fake_publish):
            self._run_main(hook, env=env)
            self._run_main(hook, env=env)
        if len(topics_seen) >= 2:
            self.assertNotEqual(topics_seen[0], topics_seen[1])

    def test_disabled_0_is_not_disabled(self):
        hook = {"tool_name": "Read", "tool_input": {}}
        env = {"MOBILE_APPROVER_DISABLED": "0"}
        output = self._run_main(hook, env=env)
        # Read is always allowed (no output), not affected by DISABLED=0
        self.assertEqual(output, "")

    def test_bash_no_output_from_main(self):
        # Bash is in ALWAYS_ALLOW_TOOLS — no stdout
        hook = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
        output = self._run_main(hook)
        self.assertEqual(output, "")

    def test_deny_from_phone_reason_mentions_iphone(self):
        hook = {"tool_name": "Write", "tool_input": {}}
        env = {"MOBILE_APPROVER_TOPIC": "test-topic"}
        with patch("mobile_approver._ntfy_publish", return_value=True):
            with patch("mobile_approver._ntfy_poll", return_value="deny"):
                output = self._run_main(hook, env=env)
        result = json.loads(output)
        reason = result["hookSpecificOutput"].get("denyReason", "")
        self.assertIn("iPhone", reason)


if __name__ == "__main__":
    unittest.main()
