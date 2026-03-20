#!/usr/bin/env python3
"""Tests for queue_injector.py — Cross-chat queue context injection hook.

This hook runs on UserPromptSubmit to inject unread cross-chat messages
as additional context, so Kalshi chats see CCA research findings immediately.
"""

import json
import os
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDetectChatIdentity(unittest.TestCase):
    """Test determining which chat we're in from environment/cwd."""

    def test_detect_cca_from_cwd(self):
        from queue_injector import detect_chat_identity
        result = detect_chat_identity(
            cwd="/Users/matthewshields/Projects/ClaudeCodeAdvancements"
        )
        self.assertEqual(result, "cca")

    def test_detect_kalshi_main_from_cwd(self):
        from queue_injector import detect_chat_identity
        result = detect_chat_identity(
            cwd="/Users/matthewshields/Projects/polymarket-bot"
        )
        # Can't distinguish main vs research from cwd alone
        self.assertIn(result, ("km", "kr", "kalshi"))

    def test_detect_unknown(self):
        from queue_injector import detect_chat_identity
        result = detect_chat_identity(cwd="/tmp/random")
        self.assertIsNone(result)

    def test_detect_from_env_override(self):
        from queue_injector import detect_chat_identity
        result = detect_chat_identity(
            cwd="/tmp/whatever",
            env_chat_id="kr"
        )
        self.assertEqual(result, "kr")


class TestBuildInjectionContext(unittest.TestCase):
    """Test building the context string for unread messages."""

    def test_no_unread_returns_empty(self):
        from queue_injector import build_injection_context
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("")
            f.flush()
            try:
                result = build_injection_context("km", f.name)
                self.assertEqual(result, "")
            finally:
                os.unlink(f.name)

    def test_unread_messages_produce_context(self):
        from queue_injector import build_injection_context
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            msg = {
                "id": "msg_test_001",
                "sender": "cca",
                "target": "km",
                "subject": "New edge signal found",
                "body": "Wilson CI shows drift in sniper timing",
                "priority": "high",
                "category": "research_finding",
                "status": "unread",
                "created_at": "2026-03-19T20:00:00Z",
            }
            f.write(json.dumps(msg) + "\n")
            f.flush()
            try:
                result = build_injection_context("km", f.name)
                self.assertIn("unread", result)
                self.assertIn("New edge signal found", result)
            finally:
                os.unlink(f.name)

    def test_context_shows_all_unread_subjects(self):
        from queue_injector import build_injection_context
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i, subj in enumerate(["Signal A", "Signal B", "Signal C"]):
                msg = {
                    "id": f"msg_test_{i:03d}",
                    "sender": "cca",
                    "target": "km",
                    "subject": subj,
                    "body": "",
                    "priority": "medium",
                    "category": "fyi",
                    "status": "unread",
                    "created_at": "2026-03-19T20:00:00Z",
                }
                f.write(json.dumps(msg) + "\n")
            f.flush()
            try:
                result = build_injection_context("km", f.name)
                self.assertIn("Signal A", result)
                self.assertIn("Signal B", result)
                self.assertIn("Signal C", result)
                self.assertIn("3", result)
            finally:
                os.unlink(f.name)

    def test_does_not_show_read_messages(self):
        from queue_injector import build_injection_context
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            msg = {
                "id": "msg_test_001",
                "sender": "cca",
                "target": "km",
                "subject": "Already seen",
                "body": "",
                "priority": "medium",
                "category": "fyi",
                "status": "read",
                "created_at": "2026-03-19T20:00:00Z",
            }
            f.write(json.dumps(msg) + "\n")
            f.flush()
            try:
                result = build_injection_context("km", f.name)
                self.assertEqual(result, "")
            finally:
                os.unlink(f.name)

    def test_does_not_show_messages_for_other_chats(self):
        from queue_injector import build_injection_context
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            msg = {
                "id": "msg_test_001",
                "sender": "cca",
                "target": "kr",  # For research, not main
                "subject": "Research only",
                "body": "",
                "priority": "medium",
                "category": "fyi",
                "status": "unread",
                "created_at": "2026-03-19T20:00:00Z",
            }
            f.write(json.dumps(msg) + "\n")
            f.flush()
            try:
                result = build_injection_context("km", f.name)
                self.assertEqual(result, "")
            finally:
                os.unlink(f.name)


class TestHookOutput(unittest.TestCase):
    """Test the hook's JSON output format."""

    def test_hook_returns_valid_json(self):
        from queue_injector import generate_hook_response
        result = generate_hook_response("")
        data = json.loads(result)
        self.assertIn("continue", data)

    def test_hook_with_context_adds_additional_context(self):
        from queue_injector import generate_hook_response
        result = generate_hook_response("[cross-chat] 2 unread messages")
        data = json.loads(result)
        self.assertTrue(data.get("continue", True))
        self.assertIn("additionalContext", data)
        self.assertIn("cross-chat", data["additionalContext"])

    def test_hook_without_context_is_minimal(self):
        from queue_injector import generate_hook_response
        result = generate_hook_response("")
        data = json.loads(result)
        self.assertTrue(data.get("continue", True))
        # No additionalContext when nothing to inject
        self.assertNotIn("additionalContext", data)

    def test_hook_never_blocks(self):
        """Hook should always continue, never block user input."""
        from queue_injector import generate_hook_response
        for ctx in ["", "some context", "[cross-chat] critical"]:
            result = generate_hook_response(ctx)
            data = json.loads(result)
            self.assertTrue(data.get("continue", True))


class TestFullHookFlow(unittest.TestCase):
    """Test the complete hook stdin->stdout flow."""

    def test_end_to_end_with_unread(self):
        from queue_injector import run_hook
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            msg = {
                "id": "msg_test_e2e",
                "sender": "cca",
                "target": "km",
                "subject": "Test signal",
                "body": "Body text",
                "priority": "high",
                "category": "action_item",
                "status": "unread",
                "created_at": "2026-03-19T20:00:00Z",
            }
            f.write(json.dumps(msg) + "\n")
            f.flush()
            try:
                result = run_hook(
                    chat_id="km",
                    queue_path=f.name,
                )
                data = json.loads(result)
                self.assertTrue(data.get("continue", True))
                self.assertIn("Test signal", data.get("additionalContext", ""))
            finally:
                os.unlink(f.name)

    def test_end_to_end_no_unread(self):
        from queue_injector import run_hook
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("")
            f.flush()
            try:
                result = run_hook(
                    chat_id="km",
                    queue_path=f.name,
                )
                data = json.loads(result)
                self.assertTrue(data.get("continue", True))
                self.assertNotIn("additionalContext", data)
            finally:
                os.unlink(f.name)

    def test_end_to_end_missing_queue_file(self):
        """Should not crash if queue file doesn't exist."""
        from queue_injector import run_hook
        result = run_hook(
            chat_id="km",
            queue_path="/nonexistent/queue.jsonl",
        )
        data = json.loads(result)
        self.assertTrue(data.get("continue", True))

    def test_end_to_end_cca_chat_gets_kalshi_messages(self):
        """CCA chat should see messages targeted at cca."""
        from queue_injector import run_hook
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            msg = {
                "id": "msg_test_cca",
                "sender": "km",
                "target": "cca",
                "subject": "Need research on X",
                "body": "",
                "priority": "medium",
                "category": "question",
                "status": "unread",
                "created_at": "2026-03-19T20:00:00Z",
            }
            f.write(json.dumps(msg) + "\n")
            f.flush()
            try:
                result = run_hook(
                    chat_id="cca",
                    queue_path=f.name,
                )
                data = json.loads(result)
                self.assertIn("Need research on X", data.get("additionalContext", ""))
            finally:
                os.unlink(f.name)


class TestContextFormat(unittest.TestCase):
    """Test that the injection context is useful and readable."""

    def test_critical_messages_highlighted(self):
        from queue_injector import build_injection_context
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            msg = {
                "id": "msg_crit",
                "sender": "cca",
                "target": "km",
                "subject": "URGENT: Block all bets",
                "body": "Critical signal detected",
                "priority": "critical",
                "category": "action_item",
                "status": "unread",
                "created_at": "2026-03-19T20:00:00Z",
            }
            f.write(json.dumps(msg) + "\n")
            f.flush()
            try:
                result = build_injection_context("km", f.name)
                self.assertIn("CRITICAL", result.upper())
                self.assertIn("URGENT: Block all bets", result)
            finally:
                os.unlink(f.name)

    def test_ack_command_included(self):
        """Context should tell the user how to acknowledge messages."""
        from queue_injector import build_injection_context
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            msg = {
                "id": "msg_test_ack",
                "sender": "cca",
                "target": "km",
                "subject": "Some finding",
                "body": "",
                "priority": "medium",
                "category": "fyi",
                "status": "unread",
                "created_at": "2026-03-19T20:00:00Z",
            }
            f.write(json.dumps(msg) + "\n")
            f.flush()
            try:
                result = build_injection_context("km", f.name)
                self.assertIn("cross_chat_queue.py", result)
            finally:
                os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
