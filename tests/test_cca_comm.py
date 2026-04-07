#!/usr/bin/env python3
"""
Tests for cca_comm.py — Simple CCA Hivemind Communication Wrappers.
Run: python3 tests/test_cca_comm.py
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import cca_comm
import cca_internal_queue as ciq


class TestDetectChatId(unittest.TestCase):
    def test_default_is_desktop(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CCA_CHAT_ID", None)
            self.assertEqual(cca_comm.detect_chat_id(), "desktop")

    def test_env_var_override(self):
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"}):
            self.assertEqual(cca_comm.detect_chat_id(), "cli1")

    def test_env_var_cli2(self):
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli2"}):
            self.assertEqual(cca_comm.detect_chat_id(), "cli2")

    def test_env_var_codex(self):
        with patch.dict(os.environ, {"CCA_CHAT_ID": "codex"}):
            self.assertEqual(cca_comm.detect_chat_id(), "codex")

    def test_invalid_env_var_falls_back(self):
        with patch.dict(os.environ, {"CCA_CHAT_ID": "bogus"}):
            self.assertEqual(cca_comm.detect_chat_id(), "desktop")


class TestInbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._orig = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.path)

    def test_empty_inbox(self):
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_inbox(["desktop"])
        self.assertIn("No unread", f.getvalue())

    def test_inbox_shows_messages(self):
        ciq.send_message("cli1", "desktop", "Test msg", path=self.path)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_inbox(["desktop"])
        output = f.getvalue()
        self.assertIn("Test msg", output)
        self.assertIn("1 unread", output)


class TestSay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._orig = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.path)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_say_sends_fyi(self):
        cca_comm.cmd_say(["cli1", "hello", "world"])
        msgs = ciq._load_queue(self.path)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["target"], "cli1")
        self.assertEqual(msgs[0]["subject"], "hello world")
        self.assertEqual(msgs[0]["category"], "fyi")


class TestTask(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._orig = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.path)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_task_sends_handoff(self):
        cca_comm.cmd_task(["cli2", "build", "feature", "X"])
        msgs = ciq._load_queue(self.path)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["target"], "cli2")
        self.assertEqual(msgs[0]["category"], "handoff")
        self.assertEqual(msgs[0]["priority"], "high")

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_task_preserves_recent_messages(self):
        """New task should NOT clear recent (<2h) unread messages from target inbox."""
        # Send a recent task (just now — within 2h window)
        ciq.send_message("desktop", "cli1", "recent task", priority="high",
                        category="handoff", path=self.path)
        unread = ciq.get_unread("cli1", self.path)
        self.assertEqual(len(unread), 1)
        # Assign new task — recent message should be preserved
        cca_comm.cmd_task(["cli1", "new", "task"])
        unread = ciq.get_unread("cli1", self.path)
        # Both messages should be present (recent preserved + new added)
        self.assertEqual(len(unread), 2)
        subjects = [m["subject"] for m in unread]
        self.assertIn("recent task", subjects)
        self.assertIn("new task", subjects)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_task_no_stale_messages_still_works(self):
        """Task assignment works fine when target has empty inbox."""
        cca_comm.cmd_task(["cli1", "fresh", "task"])
        unread = ciq.get_unread("cli1", self.path)
        self.assertEqual(len(unread), 1)
        self.assertIn("fresh task", unread[0]["subject"])

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_task_clears_stale_messages_before_assigning(self):
        """Old unread messages are acked without crashing before the new task is sent."""
        stale = ciq.send_message(
            "desktop", "cli1", "stale task",
            priority="high", category="handoff", path=self.path,
        )
        msgs = ciq._load_queue(self.path)
        msgs[0]["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        ciq._save_queue(msgs, self.path)

        cca_comm.cmd_task(["cli1", "replacement", "task"])

        msgs = ciq._load_queue(self.path)
        stale_msg = next(m for m in msgs if m["id"] == stale["id"])
        new_msg = next(m for m in msgs if m["subject"] == "replacement task")
        self.assertEqual(stale_msg["status"], "read")
        self.assertEqual(new_msg["status"], "unread")


class TestClaim(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._orig = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.path)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_claim_sends_to_all_others(self):
        cca_comm.cmd_claim(["cca-loop"])
        msgs = ciq._load_queue(self.path)
        # desktop -> cli1, cli2, terminal, codex (4 others)
        self.assertEqual(len(msgs), 4)
        targets = {m["target"] for m in msgs}
        self.assertNotIn("desktop", targets)
        self.assertIn("cli1", targets)
        self.assertIn("cli2", targets)
        self.assertIn("codex", targets)
        for m in msgs:
            self.assertEqual(m["category"], "scope_claim")


class TestRelease(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._orig = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.path)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"})
    def test_release_sends_to_all_others(self):
        cca_comm.cmd_release(["cca-loop"])
        msgs = ciq._load_queue(self.path)
        self.assertEqual(len(msgs), 4)
        for m in msgs:
            self.assertEqual(m["category"], "scope_release")
        targets = {m["target"] for m in msgs}
        self.assertNotIn("cli1", targets)


class TestDone(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._orig = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.path)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"})
    def test_done_sends_to_desktop(self):
        cca_comm.cmd_done(["timeout", "feature", "complete"])
        msgs = ciq._load_queue(self.path)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["target"], "desktop")
        self.assertIn("WRAP:", msgs[0]["subject"])
        self.assertEqual(msgs[0]["category"], "handoff")

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_done_from_desktop_warns(self):
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_done(["test"])
        self.assertIn("You ARE desktop", f.getvalue())


class TestAck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._orig = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.path)

    def test_ack_clears_messages(self):
        ciq.send_message("desktop", "cli1", "A", path=self.path)
        ciq.send_message("desktop", "cli1", "B", path=self.path)
        cca_comm.cmd_ack(["cli1"])
        self.assertEqual(len(ciq.get_unread("cli1", self.path)), 0)


class TestBroadcast(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._orig = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.path)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_broadcast_sends_to_all_others(self):
        cca_comm.cmd_broadcast(["wrap", "time"])
        msgs = ciq._load_queue(self.path)
        self.assertEqual(len(msgs), 4)  # cli1, cli2, terminal, codex
        targets = {m["target"] for m in msgs}
        self.assertNotIn("desktop", targets)


class TestStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._orig = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.path)

    def test_status_empty(self):
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_status([])
        self.assertIn("No unread", f.getvalue())

    def test_status_with_messages(self):
        ciq.send_message("desktop", "cli1", "Test", path=self.path)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_status([])
        self.assertIn("CLI 1", f.getvalue())


class TestContext(unittest.TestCase):
    """Tests for the context command — gives workers context about desktop's recent work."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._orig = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.path)

    @patch("cca_comm._get_recent_commits")
    def test_context_shows_recent_commits(self, mock_commits):
        mock_commits.return_value = [
            {"hash": "abc1234", "message": "S91: Build crash_recovery.py"},
            {"hash": "def5678", "message": "S91: Fix doc drift"},
        ]
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_context([])
        output = f.getvalue()
        self.assertIn("RECENT COMMITS", output)
        self.assertIn("abc1234", output)
        self.assertIn("crash_recovery", output)

    @patch("cca_comm._get_recent_commits")
    def test_context_shows_active_scopes(self, mock_commits):
        mock_commits.return_value = []
        ciq.send_message("desktop", "cli1", "agent-guard/", category="scope_claim",
                        priority="high", path=self.path)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_context([])
        output = f.getvalue()
        self.assertIn("ACTIVE SCOPES", output)
        self.assertIn("agent-guard/", output)

    @patch("cca_comm._get_recent_commits")
    def test_context_shows_queue_stats(self, mock_commits):
        mock_commits.return_value = []
        # Send several messages to create queue activity
        for i in range(5):
            ciq.send_message("desktop", "cli1", f"msg {i}", path=self.path)
        ciq.send_message("cli1", "desktop", "reply", path=self.path)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_context([])
        output = f.getvalue()
        self.assertIn("QUEUE STATS", output)
        self.assertIn("6", output)  # total messages

    @patch("cca_comm._get_recent_commits")
    def test_context_with_no_activity(self, mock_commits):
        mock_commits.return_value = []
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_context([])
        output = f.getvalue()
        self.assertIn("No active scope claims", output)

    @patch("cca_comm._get_recent_commits")
    def test_context_custom_commit_count(self, mock_commits):
        mock_commits.return_value = [
            {"hash": "abc1234", "message": "commit 1"},
        ]
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_context(["3"])
        # Should pass n=3 to _get_recent_commits
        mock_commits.assert_called_once_with(3)

    def test_get_recent_commits_returns_list(self):
        """_get_recent_commits should return a list of dicts with hash and message."""
        result = cca_comm._get_recent_commits(5)
        self.assertIsInstance(result, list)
        if result:  # May be empty in test env
            self.assertIn("hash", result[0])
            self.assertIn("message", result[0])

    def test_get_recent_commits_default_count(self):
        """Default should return up to 10 commits."""
        result = cca_comm._get_recent_commits()
        self.assertIsInstance(result, list)
        self.assertLessEqual(len(result), 10)

    @patch("cca_comm._get_recent_commits")
    def test_context_shows_crash_status(self, mock_commits):
        mock_commits.return_value = []
        # Simulate a crashed worker (scope claim from cli1, no process)
        ciq.send_message("cli1", "desktop", "test-module", category="scope_claim",
                        priority="high", path=self.path)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            with patch("cca_comm._get_crashed_workers") as mock_crashed:
                mock_crashed.return_value = [{"chat_id": "cli1", "scope": "test-module"}]
                cca_comm.cmd_context([])
        output = f.getvalue()
        self.assertIn("CRASHED WORKERS", output)
        self.assertIn("cli1", output)


class TestQueueThroughput(unittest.TestCase):
    """Tests for queue throughput measurement."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._orig = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.path)

    def test_count_queue_messages_empty(self):
        stats = cca_comm.get_queue_stats(self.path)
        self.assertEqual(stats["total_messages"], 0)
        self.assertEqual(stats["by_category"], {})

    def test_count_queue_messages_with_data(self):
        ciq.send_message("desktop", "cli1", "task 1", category="handoff", path=self.path)
        ciq.send_message("cli1", "desktop", "done", category="handoff", path=self.path)
        ciq.send_message("desktop", "cli1", "scope", category="scope_claim", path=self.path)
        stats = cca_comm.get_queue_stats(self.path)
        self.assertEqual(stats["total_messages"], 3)
        self.assertEqual(stats["by_category"]["handoff"], 2)
        self.assertEqual(stats["by_category"]["scope_claim"], 1)

    def test_queue_stats_by_sender(self):
        ciq.send_message("desktop", "cli1", "a", path=self.path)
        ciq.send_message("desktop", "cli1", "b", path=self.path)
        ciq.send_message("cli1", "desktop", "c", path=self.path)
        stats = cca_comm.get_queue_stats(self.path)
        self.assertEqual(stats["by_sender"]["desktop"], 2)
        self.assertEqual(stats["by_sender"]["cli1"], 1)


class TestCrossProjectRouting(unittest.TestCase):
    """Tests for routing messages to Kalshi chats (km/kr) via cross_chat_queue."""

    def setUp(self):
        import cross_chat_queue as ccq
        self.tmp_internal = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp_internal.close()
        self.tmp_cross = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp_cross.close()
        self._orig_internal = ciq.DEFAULT_QUEUE_PATH
        self._orig_cross = ccq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.tmp_internal.name
        ccq.DEFAULT_QUEUE_PATH = self.tmp_cross.name

    def tearDown(self):
        import cross_chat_queue as ccq
        ciq.DEFAULT_QUEUE_PATH = self._orig_internal
        ccq.DEFAULT_QUEUE_PATH = self._orig_cross
        os.unlink(self.tmp_internal.name)
        os.unlink(self.tmp_cross.name)

    def test_is_kalshi_target(self):
        self.assertTrue(cca_comm.is_kalshi_target("km"))
        self.assertTrue(cca_comm.is_kalshi_target("kr"))
        self.assertFalse(cca_comm.is_kalshi_target("cli1"))
        self.assertFalse(cca_comm.is_kalshi_target("desktop"))

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_task_km_routes_to_cross_queue(self):
        """task km should route through cross_chat_queue, not internal queue."""
        import cross_chat_queue as ccq
        cca_comm.cmd_task(["km", "implement", "sniper", "guard"])
        # Internal queue should be empty
        internal_msgs = ciq._load_queue(self.tmp_internal.name)
        self.assertEqual(len(internal_msgs), 0)
        # Cross-chat queue should have the message
        cross_msgs = ccq._load_queue(self.tmp_cross.name)
        self.assertEqual(len(cross_msgs), 1)
        self.assertEqual(cross_msgs[0]["target"], "km")
        self.assertIn("sniper guard", cross_msgs[0]["subject"])

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_task_kr_routes_to_cross_queue(self):
        """task kr should route through cross_chat_queue."""
        import cross_chat_queue as ccq
        cca_comm.cmd_task(["kr", "research", "Kelly", "criterion"])
        cross_msgs = ccq._load_queue(self.tmp_cross.name)
        self.assertEqual(len(cross_msgs), 1)
        self.assertEqual(cross_msgs[0]["target"], "kr")

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_say_km_routes_to_cross_queue(self):
        """say km should route through cross_chat_queue."""
        import cross_chat_queue as ccq
        cca_comm.cmd_say(["km", "check", "bot", "status"])
        cross_msgs = ccq._load_queue(self.tmp_cross.name)
        self.assertEqual(len(cross_msgs), 1)
        self.assertEqual(cross_msgs[0]["target"], "km")

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_task_cli1_still_routes_to_internal(self):
        """task cli1 should still use internal queue (not cross-chat)."""
        import cross_chat_queue as ccq
        cca_comm.cmd_task(["cli1", "build", "feature"])
        internal_msgs = ciq._load_queue(self.tmp_internal.name)
        self.assertEqual(len(internal_msgs), 1)
        cross_msgs = ccq._load_queue(self.tmp_cross.name)
        self.assertEqual(len(cross_msgs), 0)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_inbox_km_reads_from_cross_queue(self):
        """inbox km should read messages targeted AT km from cross_chat_queue."""
        import cross_chat_queue as ccq
        ccq.send_message("cca", "km", "implement sniper guard",
                        priority="high", category="action_item",
                        path=self.tmp_cross.name)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_inbox(["km"])
        output = f.getvalue()
        self.assertIn("sniper guard", output)

    def test_all_targets_recognized(self):
        """All valid targets (internal + Kalshi) should be recognized."""
        all_targets = cca_comm.all_valid_targets()
        self.assertIn("desktop", all_targets)
        self.assertIn("cli1", all_targets)
        self.assertIn("codex", all_targets)
        self.assertIn("km", all_targets)
        self.assertIn("kr", all_targets)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_status_includes_kalshi_chats(self):
        """status should show Kalshi chat queues too."""
        import cross_chat_queue as ccq
        ccq.send_message("cca", "km", "test task",
                        priority="high", category="action_item",
                        path=self.tmp_cross.name)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_status([])
        output = f.getvalue()
        self.assertIn("Kalshi", output)


class TestCommands(unittest.TestCase):
    def test_all_commands_registered(self):
        expected = {"inbox", "say", "task", "question", "claim", "release", "done", "ack",
                    "status", "broadcast", "assign", "shutdown", "context"}
        self.assertEqual(set(cca_comm.COMMANDS.keys()), expected)

    def test_all_commands_callable(self):
        for name, func in cca_comm.COMMANDS.items():
            self.assertTrue(callable(func), f"{name} is not callable")


class TestBMADContextCap(unittest.TestCase):
    """400-word cap warning on cmd_task (BMAD context cap pattern)."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        import cca_comm as _cc
        self._orig = _cc.ciq.DEFAULT_QUEUE_PATH
        _cc.ciq.DEFAULT_QUEUE_PATH = self.tmp.name

    def tearDown(self):
        import cca_comm as _cc
        _cc.ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.tmp.name)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_no_warning_under_cap(self):
        short_task = "do this thing"  # well under 400 words
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_task(["cli1", short_task])
        output = f.getvalue()
        self.assertNotIn("BMAD context cap", output)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_warning_over_cap(self):
        long_task = " ".join(["word"] * 401)
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_task(["cli1", long_task])
        output = f.getvalue()
        self.assertIn("BMAD context cap", output)
        self.assertIn("401 words", output)
        self.assertIn("cap 400", output)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"})
    def test_task_still_sent_over_cap(self):
        """Warning does NOT block the task — warn only."""
        long_task = " ".join(["word"] * 401)
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_task(["cli1", long_task])
        output = f.getvalue()
        self.assertIn("Task assigned", output)


class TestQuestionCommand(unittest.TestCase):
    """question command — reactive pair pattern (BMAD)."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        import cca_comm as _cc
        self._orig = _cc.ciq.DEFAULT_QUEUE_PATH
        _cc.ciq.DEFAULT_QUEUE_PATH = self.tmp.name

    def tearDown(self):
        import cca_comm as _cc
        _cc.ciq.DEFAULT_QUEUE_PATH = self._orig
        os.unlink(self.tmp.name)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"})
    def test_question_routes_with_question_category(self):
        import cca_internal_queue as ciq
        cca_comm.cmd_question(["desktop", "what is the plan?"])
        msgs = ciq.get_unread("desktop", self.tmp.name)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["category"], "question")

    @patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"})
    def test_question_output_says_needs_reply(self):
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_question(["desktop", "should I proceed?"])
        output = f.getvalue()
        self.assertIn("needs reply this session", output)

    def test_question_no_args_prints_usage(self):
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_question([])
        self.assertIn("Usage", f.getvalue())


class TestManifestCommand(unittest.TestCase):
    """manifest CLI command on session_orchestrator."""

    def test_manifest_prints_all_roles(self):
        from session_orchestrator import PidRegistry
        f = io.StringIO()
        with redirect_stdout(f):
            from session_orchestrator import cli_main
            cli_main(["manifest"])
        output = f.getvalue()
        for role in PidRegistry.ROLE_CAPABILITIES:
            self.assertIn(role, output)

    def test_manifest_shows_capabilities(self):
        f = io.StringIO()
        with redirect_stdout(f):
            from session_orchestrator import cli_main
            cli_main(["manifest"])
        output = f.getvalue()
        self.assertIn("coordinate", output)   # desktop capability
        self.assertIn("build", output)        # cli1/cli2 capability
        self.assertIn("monitor", output)      # kalshi capability

    def test_manifest_shows_alive_status(self):
        f = io.StringIO()
        with redirect_stdout(f):
            from session_orchestrator import cli_main
            cli_main(["manifest"])
        output = f.getvalue()
        # At minimum, offline roles shown
        self.assertIn("offline", output)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
