#!/usr/bin/env python3
"""Tests for queue_hook.py — Unified queue check hook for all hook events.

Fires on PostToolUse (every tool call) and UserPromptSubmit (every user message)
to inject unread cross-chat AND internal queue messages as context. This ensures
autonomous chats see new messages between every tool call, not just when the
user types.

The hook is lightweight — reads two small JSONL files and returns JSON.
Must complete in <5ms to not impact hook chain latency budget.
"""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestQueueHookPostToolUse(unittest.TestCase):
    """Test hook behavior on PostToolUse events."""

    def test_no_messages_returns_empty(self):
        from queue_hook import check_queues
        with tempfile.TemporaryDirectory() as tmpdir:
            cross = os.path.join(tmpdir, "cross.jsonl")
            internal = os.path.join(tmpdir, "internal.jsonl")
            open(cross, "w").close()
            open(internal, "w").close()
            result = check_queues("cca", cross_path=cross, internal_path=internal)
            self.assertEqual(result, "")

    def test_cross_chat_unread_included(self):
        from queue_hook import check_queues
        with tempfile.TemporaryDirectory() as tmpdir:
            cross = os.path.join(tmpdir, "cross.jsonl")
            internal = os.path.join(tmpdir, "internal.jsonl")
            open(internal, "w").close()
            with open(cross, "w") as f:
                f.write(json.dumps({
                    "id": "msg_001", "sender": "km", "target": "cca",
                    "subject": "Need research on volatility", "body": "",
                    "priority": "high", "category": "question",
                    "status": "unread", "created_at": "2026-03-20T04:00:00Z"
                }) + "\n")
            result = check_queues("cca", cross_path=cross, internal_path=internal)
            self.assertIn("Need research on volatility", result)

    def test_internal_queue_unread_included(self):
        from queue_hook import check_queues
        with tempfile.TemporaryDirectory() as tmpdir:
            cross = os.path.join(tmpdir, "cross.jsonl")
            internal = os.path.join(tmpdir, "internal.jsonl")
            open(cross, "w").close()
            with open(internal, "w") as f:
                f.write(json.dumps({
                    "id": "cca_001", "sender": "desktop", "target": "terminal",
                    "subject": "Switch to cca-loop work", "body": "Matthew directive",
                    "priority": "high", "category": "handoff",
                    "status": "unread", "created_at": "2026-03-20T04:00:00Z"
                }) + "\n")
            result = check_queues(
                "cca", cross_path=cross, internal_path=internal,
                internal_identity="terminal"
            )
            self.assertIn("Switch to cca-loop work", result)

    def test_both_queues_combined(self):
        from queue_hook import check_queues
        with tempfile.TemporaryDirectory() as tmpdir:
            cross = os.path.join(tmpdir, "cross.jsonl")
            internal = os.path.join(tmpdir, "internal.jsonl")
            with open(cross, "w") as f:
                f.write(json.dumps({
                    "id": "msg_001", "sender": "km", "target": "cca",
                    "subject": "Cross-chat message", "body": "",
                    "priority": "medium", "category": "fyi",
                    "status": "unread", "created_at": "2026-03-20T04:00:00Z"
                }) + "\n")
            with open(internal, "w") as f:
                f.write(json.dumps({
                    "id": "cca_001", "sender": "desktop", "target": "terminal",
                    "subject": "Internal message", "body": "",
                    "priority": "medium", "category": "fyi",
                    "status": "unread", "created_at": "2026-03-20T04:00:00Z"
                }) + "\n")
            result = check_queues(
                "cca", cross_path=cross, internal_path=internal,
                internal_identity="terminal"
            )
            self.assertIn("Cross-chat message", result)
            self.assertIn("Internal message", result)

    def test_read_messages_excluded(self):
        from queue_hook import check_queues
        with tempfile.TemporaryDirectory() as tmpdir:
            cross = os.path.join(tmpdir, "cross.jsonl")
            internal = os.path.join(tmpdir, "internal.jsonl")
            open(internal, "w").close()
            with open(cross, "w") as f:
                f.write(json.dumps({
                    "id": "msg_001", "sender": "km", "target": "cca",
                    "subject": "Already seen", "body": "",
                    "priority": "medium", "category": "fyi",
                    "status": "read", "created_at": "2026-03-20T04:00:00Z"
                }) + "\n")
            result = check_queues("cca", cross_path=cross, internal_path=internal)
            self.assertEqual(result, "")


class TestThrottling(unittest.TestCase):
    """Test that PostToolUse checks are throttled to avoid spam."""

    def test_throttle_skips_rapid_checks(self):
        from queue_hook import should_check_queues
        # First check should always pass
        self.assertTrue(should_check_queues(last_check=0, now=100, interval=30))
        # Check within interval should skip
        self.assertFalse(should_check_queues(last_check=100, now=110, interval=30))
        # Check after interval should pass
        self.assertTrue(should_check_queues(last_check=100, now=135, interval=30))

    def test_user_prompt_always_checks(self):
        """UserPromptSubmit should always check, ignoring throttle."""
        from queue_hook import should_check_queues
        self.assertTrue(should_check_queues(
            last_check=100, now=101, interval=30, force=True
        ))


class TestHookJsonOutput(unittest.TestCase):
    """Test the hook's JSON output format for both hook types."""

    def test_post_tool_use_format(self):
        from queue_hook import format_hook_response
        result = format_hook_response("[queue] 2 unread", hook_type="PostToolUse")
        data = json.loads(result)
        # PostToolUse uses additionalContext (not decision/block)
        self.assertIn("additionalContext", data)

    def test_user_prompt_submit_format(self):
        from queue_hook import format_hook_response
        result = format_hook_response("[queue] 1 unread", hook_type="UserPromptSubmit")
        data = json.loads(result)
        self.assertIn("continue", data)
        self.assertIn("additionalContext", data)

    def test_empty_context_minimal_output(self):
        from queue_hook import format_hook_response
        result = format_hook_response("", hook_type="PostToolUse")
        data = json.loads(result)
        self.assertNotIn("additionalContext", data)

    def test_never_blocks(self):
        from queue_hook import format_hook_response
        for hook_type in ["PostToolUse", "UserPromptSubmit"]:
            result = format_hook_response("some context", hook_type=hook_type)
            data = json.loads(result)
            # Should never have decision: block
            self.assertNotIn("decision", data)


class TestChatIdentityDetection(unittest.TestCase):
    """Test detecting which chat we're in."""

    def test_cca_from_cwd(self):
        from queue_hook import detect_identity
        cross_id, internal_id = detect_identity(
            cwd="/Users/matthewshields/Projects/ClaudeCodeAdvancements"
        )
        self.assertEqual(cross_id, "cca")

    def test_kalshi_from_cwd(self):
        from queue_hook import detect_identity
        cross_id, internal_id = detect_identity(
            cwd="/Users/matthewshields/Projects/polymarket-bot"
        )
        self.assertEqual(cross_id, "km")

    def test_env_override(self):
        from queue_hook import detect_identity
        cross_id, internal_id = detect_identity(
            cwd="/tmp", env_cross_id="kr", env_internal_id="terminal"
        )
        self.assertEqual(cross_id, "kr")
        self.assertEqual(internal_id, "terminal")

    def test_internal_identity_from_env(self):
        from queue_hook import detect_identity
        _, internal_id = detect_identity(
            cwd="/Users/matthewshields/Projects/ClaudeCodeAdvancements",
            env_internal_id="desktop"
        )
        self.assertEqual(internal_id, "desktop")


class TestPerformance(unittest.TestCase):
    """Test that hook completes within latency budget."""

    def test_completes_under_5ms_empty_queues(self):
        from queue_hook import check_queues
        with tempfile.TemporaryDirectory() as tmpdir:
            cross = os.path.join(tmpdir, "cross.jsonl")
            internal = os.path.join(tmpdir, "internal.jsonl")
            open(cross, "w").close()
            open(internal, "w").close()
            start = time.monotonic()
            for _ in range(100):
                check_queues("cca", cross_path=cross, internal_path=internal)
            elapsed = (time.monotonic() - start) / 100
            self.assertLess(elapsed, 0.005, f"Avg {elapsed*1000:.1f}ms exceeds 5ms budget")

    def test_completes_under_5ms_with_messages(self):
        from queue_hook import check_queues
        with tempfile.TemporaryDirectory() as tmpdir:
            cross = os.path.join(tmpdir, "cross.jsonl")
            internal = os.path.join(tmpdir, "internal.jsonl")
            open(internal, "w").close()
            with open(cross, "w") as f:
                for i in range(20):
                    f.write(json.dumps({
                        "id": f"msg_{i:03d}", "sender": "km", "target": "cca",
                        "subject": f"Message {i}", "body": "Body text here",
                        "priority": "medium", "category": "fyi",
                        "status": "unread", "created_at": "2026-03-20T04:00:00Z"
                    }) + "\n")
            start = time.monotonic()
            for _ in range(100):
                check_queues("cca", cross_path=cross, internal_path=internal)
            elapsed = (time.monotonic() - start) / 100
            self.assertLess(elapsed, 0.005, f"Avg {elapsed*1000:.1f}ms exceeds 5ms budget")


class TestMissingFiles(unittest.TestCase):
    """Test graceful handling of missing queue files."""

    def test_missing_cross_queue(self):
        from queue_hook import check_queues
        with tempfile.TemporaryDirectory() as tmpdir:
            internal = os.path.join(tmpdir, "internal.jsonl")
            open(internal, "w").close()
            result = check_queues(
                "cca",
                cross_path="/nonexistent/cross.jsonl",
                internal_path=internal
            )
            self.assertEqual(result, "")

    def test_missing_internal_queue(self):
        from queue_hook import check_queues
        with tempfile.TemporaryDirectory() as tmpdir:
            cross = os.path.join(tmpdir, "cross.jsonl")
            open(cross, "w").close()
            result = check_queues(
                "cca",
                cross_path=cross,
                internal_path="/nonexistent/internal.jsonl"
            )
            self.assertEqual(result, "")

    def test_both_missing(self):
        from queue_hook import check_queues
        result = check_queues(
            "cca",
            cross_path="/nonexistent/a.jsonl",
            internal_path="/nonexistent/b.jsonl"
        )
        self.assertEqual(result, "")

    def test_corrupt_jsonl_line(self):
        from queue_hook import check_queues
        with tempfile.TemporaryDirectory() as tmpdir:
            cross = os.path.join(tmpdir, "cross.jsonl")
            internal = os.path.join(tmpdir, "internal.jsonl")
            open(internal, "w").close()
            with open(cross, "w") as f:
                f.write("not json\n")
                f.write(json.dumps({
                    "id": "msg_001", "sender": "km", "target": "cca",
                    "subject": "Valid message", "body": "",
                    "priority": "medium", "category": "fyi",
                    "status": "unread", "created_at": "2026-03-20T04:00:00Z"
                }) + "\n")
            result = check_queues("cca", cross_path=cross, internal_path=internal)
            self.assertIn("Valid message", result)


class TestScopeClaimHighlighting(unittest.TestCase):
    """Test that scope claims are highlighted in output."""

    def test_scope_claim_marked(self):
        from queue_hook import check_queues
        with tempfile.TemporaryDirectory() as tmpdir:
            cross = os.path.join(tmpdir, "cross.jsonl")
            internal = os.path.join(tmpdir, "internal.jsonl")
            open(cross, "w").close()
            with open(internal, "w") as f:
                f.write(json.dumps({
                    "id": "cca_001", "sender": "desktop", "target": "terminal",
                    "subject": "Working on cca-loop", "body": "Don't touch it",
                    "priority": "high", "category": "scope_claim",
                    "status": "unread", "created_at": "2026-03-20T04:00:00Z"
                }) + "\n")
            result = check_queues(
                "cca", cross_path=cross, internal_path=internal,
                internal_identity="terminal"
            )
            self.assertIn("SCOPE", result.upper())


if __name__ == "__main__":
    unittest.main()
