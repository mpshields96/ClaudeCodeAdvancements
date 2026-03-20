#!/usr/bin/env python3
"""
Tests for cca_comm.py — Simple CCA Hivemind Communication Wrappers.
Run: python3 tests/test_cca_comm.py
"""

import json
import os
import sys
import tempfile
import unittest
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
        # desktop -> cli1, cli2, terminal (3 others)
        self.assertEqual(len(msgs), 3)
        targets = {m["target"] for m in msgs}
        self.assertNotIn("desktop", targets)
        self.assertIn("cli1", targets)
        self.assertIn("cli2", targets)
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
        self.assertEqual(len(msgs), 3)
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
        self.assertEqual(len(msgs), 3)  # cli1, cli2, terminal
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


class TestCommands(unittest.TestCase):
    def test_all_commands_registered(self):
        expected = {"inbox", "say", "task", "claim", "release", "done", "ack", "status", "broadcast", "assign"}
        self.assertEqual(set(cca_comm.COMMANDS.keys()), expected)

    def test_all_commands_callable(self):
        for name, func in cca_comm.COMMANDS.items():
            self.assertTrue(callable(func), f"{name} is not callable")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
