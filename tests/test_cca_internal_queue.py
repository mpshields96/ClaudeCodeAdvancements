#!/usr/bin/env python3
"""
Tests for cca_internal_queue.py — CCA Desktop <-> Terminal Communication Queue.
Run: python3 tests/test_cca_internal_queue.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import cca_internal_queue as ciq


class TestSendMessage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_send_creates_message(self):
        msg = ciq.send_message("desktop", "terminal", "Test subject", path=self.path)
        self.assertIn("id", msg)
        self.assertEqual(msg["sender"], "desktop")
        self.assertEqual(msg["target"], "terminal")
        self.assertEqual(msg["subject"], "Test subject")
        self.assertEqual(msg["status"], "unread")

    def test_send_writes_to_file(self):
        ciq.send_message("desktop", "terminal", "Test", path=self.path)
        with open(self.path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        msg = json.loads(lines[0])
        self.assertEqual(msg["subject"], "Test")

    def test_send_appends_multiple(self):
        ciq.send_message("desktop", "terminal", "First", path=self.path)
        ciq.send_message("terminal", "desktop", "Second", path=self.path)
        msgs = ciq._load_queue(self.path)
        self.assertEqual(len(msgs), 2)

    def test_send_with_body_and_files(self):
        msg = ciq.send_message(
            "desktop", "terminal", "Working on cca-loop",
            body="Do NOT touch cca-loop/ or SESSION_RESUME.md",
            files=["cca-loop/", "SESSION_RESUME.md"],
            path=self.path,
        )
        self.assertEqual(msg["body"], "Do NOT touch cca-loop/ or SESSION_RESUME.md")
        self.assertEqual(msg["files"], ["cca-loop/", "SESSION_RESUME.md"])

    def test_send_with_priority(self):
        msg = ciq.send_message("desktop", "terminal", "Urgent", priority="critical", path=self.path)
        self.assertEqual(msg["priority"], "critical")

    def test_send_with_category(self):
        msg = ciq.send_message("desktop", "terminal", "Scope", category="scope_claim", path=self.path)
        self.assertEqual(msg["category"], "scope_claim")

    def test_invalid_sender_raises(self):
        with self.assertRaises(ValueError):
            ciq.send_message("invalid", "terminal", "Test", path=self.path)

    def test_invalid_target_raises(self):
        with self.assertRaises(ValueError):
            ciq.send_message("desktop", "invalid", "Test", path=self.path)

    def test_self_send_raises(self):
        with self.assertRaises(ValueError):
            ciq.send_message("desktop", "desktop", "Test", path=self.path)

    def test_empty_subject_raises(self):
        with self.assertRaises(ValueError):
            ciq.send_message("desktop", "terminal", "", path=self.path)

    def test_invalid_priority_raises(self):
        with self.assertRaises(ValueError):
            ciq.send_message("desktop", "terminal", "Test", priority="urgent", path=self.path)

    def test_invalid_category_raises(self):
        with self.assertRaises(ValueError):
            ciq.send_message("desktop", "terminal", "Test", category="unknown", path=self.path)

    def test_id_format(self):
        msg = ciq.send_message("desktop", "terminal", "Test", path=self.path)
        self.assertTrue(msg["id"].startswith("cca_"))
        self.assertGreater(len(msg["id"]), 15)

    def test_created_at_is_iso(self):
        msg = ciq.send_message("desktop", "terminal", "Test", path=self.path)
        self.assertIn("T", msg["created_at"])
        self.assertTrue(msg["created_at"].endswith("Z"))

    def test_read_at_is_none(self):
        msg = ciq.send_message("desktop", "terminal", "Test", path=self.path)
        self.assertIsNone(msg["read_at"])

    def test_no_files_key_when_none(self):
        msg = ciq.send_message("desktop", "terminal", "Test", path=self.path)
        self.assertNotIn("files", msg)

    def test_default_category_is_fyi(self):
        msg = ciq.send_message("desktop", "terminal", "Test", path=self.path)
        self.assertEqual(msg["category"], "fyi")


class TestGetUnread(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_returns_unread_for_target(self):
        ciq.send_message("desktop", "terminal", "For terminal", path=self.path)
        ciq.send_message("terminal", "desktop", "For desktop", path=self.path)
        unread = ciq.get_unread("terminal", self.path)
        self.assertEqual(len(unread), 1)
        self.assertEqual(unread[0]["subject"], "For terminal")

    def test_empty_queue_returns_empty(self):
        unread = ciq.get_unread("desktop", self.path)
        self.assertEqual(unread, [])

    def test_read_messages_excluded(self):
        ciq.send_message("desktop", "terminal", "Test", path=self.path)
        msgs = ciq._load_queue(self.path)
        msgs[0]["status"] = "read"
        ciq._save_queue(msgs, self.path)
        unread = ciq.get_unread("terminal", self.path)
        self.assertEqual(len(unread), 0)


class TestAcknowledge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_ack_marks_as_read(self):
        msg = ciq.send_message("desktop", "terminal", "Test", path=self.path)
        result = ciq.acknowledge(msg["id"], self.path)
        self.assertTrue(result)
        msgs = ciq._load_queue(self.path)
        self.assertEqual(msgs[0]["status"], "read")
        self.assertIsNotNone(msgs[0]["read_at"])

    def test_ack_nonexistent_returns_false(self):
        result = ciq.acknowledge("nonexistent_id", self.path)
        self.assertFalse(result)

    def test_ack_already_read_returns_false(self):
        msg = ciq.send_message("desktop", "terminal", "Test", path=self.path)
        ciq.acknowledge(msg["id"], self.path)
        result = ciq.acknowledge(msg["id"], self.path)
        self.assertFalse(result)

    def test_ack_all_marks_all_for_target(self):
        ciq.send_message("desktop", "terminal", "First", path=self.path)
        ciq.send_message("desktop", "terminal", "Second", path=self.path)
        ciq.send_message("terminal", "desktop", "For desktop", path=self.path)
        count = ciq.acknowledge_all("terminal", self.path)
        self.assertEqual(count, 2)
        unread_t = ciq.get_unread("terminal", self.path)
        unread_d = ciq.get_unread("desktop", self.path)
        self.assertEqual(len(unread_t), 0)
        self.assertEqual(len(unread_d), 1)

    def test_ack_all_empty_returns_zero(self):
        count = ciq.acknowledge_all("desktop", self.path)
        self.assertEqual(count, 0)


class TestGetUnreadSummary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_summary_groups_by_chat(self):
        ciq.send_message("desktop", "terminal", "A", priority="high", path=self.path)
        ciq.send_message("desktop", "terminal", "B", priority="critical", path=self.path)
        ciq.send_message("terminal", "desktop", "C", priority="low", path=self.path)
        summary = ciq.get_unread_summary(self.path)
        self.assertEqual(summary["terminal"]["total"], 2)
        self.assertEqual(summary["terminal"]["high"], 1)
        self.assertEqual(summary["terminal"]["critical"], 1)
        self.assertEqual(summary["desktop"]["total"], 1)

    def test_empty_queue_returns_empty(self):
        summary = ciq.get_unread_summary(self.path)
        self.assertEqual(summary, {})

    def test_all_read_returns_empty(self):
        ciq.send_message("desktop", "terminal", "Test", path=self.path)
        ciq.acknowledge_all("terminal", self.path)
        summary = ciq.get_unread_summary(self.path)
        self.assertEqual(summary, {})


class TestListMessages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_list_all(self):
        ciq.send_message("desktop", "terminal", "A", path=self.path)
        ciq.send_message("terminal", "desktop", "B", path=self.path)
        msgs = ciq.list_messages(path=self.path)
        self.assertEqual(len(msgs), 2)

    def test_list_by_target(self):
        ciq.send_message("desktop", "terminal", "A", path=self.path)
        ciq.send_message("terminal", "desktop", "B", path=self.path)
        msgs = ciq.list_messages(target="terminal", path=self.path)
        self.assertEqual(len(msgs), 1)

    def test_list_by_status(self):
        ciq.send_message("desktop", "terminal", "A", path=self.path)
        msg = ciq.send_message("desktop", "terminal", "B", path=self.path)
        ciq.acknowledge(msg["id"], self.path)
        unread = ciq.list_messages(status="unread", path=self.path)
        read = ciq.list_messages(status="read", path=self.path)
        self.assertEqual(len(unread), 1)
        self.assertEqual(len(read), 1)

    def test_list_by_category(self):
        ciq.send_message("desktop", "terminal", "Scope", category="scope_claim", path=self.path)
        ciq.send_message("desktop", "terminal", "FYI", category="fyi", path=self.path)
        msgs = ciq.list_messages(category="scope_claim", path=self.path)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["category"], "scope_claim")

    def test_list_empty(self):
        msgs = ciq.list_messages(path=self.path)
        self.assertEqual(msgs, [])


class TestScopeTracking(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_active_scope_claim(self):
        ciq.send_message(
            "terminal", "desktop", "Working on cca-loop",
            category="scope_claim", files=["cca-loop/"],
            path=self.path,
        )
        active = ciq.get_active_scopes(self.path)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["subject"], "Working on cca-loop")

    def test_released_scope_not_active(self):
        ciq.send_message(
            "terminal", "desktop", "Working on cca-loop",
            category="scope_claim", files=["cca-loop/"],
            path=self.path,
        )
        # Manually set timestamp so release is after claim
        msgs = ciq._load_queue(self.path)
        msgs[0]["created_at"] = "2026-03-19T01:00:00Z"
        ciq._save_queue(msgs, self.path)

        ciq.send_message(
            "terminal", "desktop", "Done with cca-loop",
            category="scope_release", files=["cca-loop/"],
            path=self.path,
        )
        # Ensure release timestamp is after
        msgs = ciq._load_queue(self.path)
        msgs[1]["created_at"] = "2026-03-19T02:00:00Z"
        ciq._save_queue(msgs, self.path)

        active = ciq.get_active_scopes(self.path)
        self.assertEqual(len(active), 0)

    def test_no_scopes_returns_empty(self):
        active = ciq.get_active_scopes(self.path)
        self.assertEqual(active, [])

    def test_scope_from_different_sender_not_released(self):
        ciq.send_message(
            "terminal", "desktop", "Working on cca-loop",
            category="scope_claim", files=["cca-loop/"],
            path=self.path,
        )
        msgs = ciq._load_queue(self.path)
        msgs[0]["created_at"] = "2026-03-19T01:00:00Z"
        ciq._save_queue(msgs, self.path)

        # Desktop tries to release terminal's scope — should not work
        ciq.send_message(
            "desktop", "terminal", "Done with cca-loop",
            category="scope_release", files=["cca-loop/"],
            path=self.path,
        )
        msgs = ciq._load_queue(self.path)
        msgs[1]["created_at"] = "2026-03-19T02:00:00Z"
        ciq._save_queue(msgs, self.path)

        active = ciq.get_active_scopes(self.path)
        self.assertEqual(len(active), 1)  # Terminal's claim still active


class TestScopeConflict(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_conflict_detected(self):
        ciq.send_message(
            "terminal", "desktop", "Working on cca-loop",
            category="scope_claim", files=["cca-loop/"],
            path=self.path,
        )
        conflicts = ciq.check_scope_conflict("desktop", ["cca-loop/main.py"], self.path)
        self.assertEqual(len(conflicts), 1)

    def test_no_conflict_different_files(self):
        ciq.send_message(
            "terminal", "desktop", "Working on cca-loop",
            category="scope_claim", files=["cca-loop/"],
            path=self.path,
        )
        conflicts = ciq.check_scope_conflict("desktop", ["agent-guard/foo.py"], self.path)
        self.assertEqual(len(conflicts), 0)

    def test_own_scope_not_conflict(self):
        ciq.send_message(
            "desktop", "terminal", "Working on CI/CD",
            category="scope_claim", files=[".github/"],
            path=self.path,
        )
        conflicts = ciq.check_scope_conflict("desktop", [".github/workflows/tests.yml"], self.path)
        self.assertEqual(len(conflicts), 0)

    def test_no_claims_no_conflicts(self):
        conflicts = ciq.check_scope_conflict("desktop", ["anything.py"], self.path)
        self.assertEqual(len(conflicts), 0)

    def test_exact_file_match_conflict(self):
        ciq.send_message(
            "terminal", "desktop", "Editing bash_guard",
            category="scope_claim", files=["agent-guard/bash_guard.py"],
            path=self.path,
        )
        conflicts = ciq.check_scope_conflict("desktop", ["agent-guard/bash_guard.py"], self.path)
        self.assertEqual(len(conflicts), 1)


class TestFormatUnreadContext(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_no_unread_returns_empty(self):
        ctx = ciq.format_unread_context("desktop", self.path)
        self.assertEqual(ctx, "")

    def test_unread_returns_context_string(self):
        ciq.send_message("terminal", "desktop", "Scope claim", category="scope_claim",
                         priority="high", path=self.path)
        ctx = ciq.format_unread_context("desktop", self.path)
        self.assertIn("[cca-internal]", ctx)
        self.assertIn("1 unread", ctx)
        self.assertIn("CCA Terminal", ctx)
        self.assertIn("Scope claim", ctx)

    def test_multiple_unread_shows_count(self):
        ciq.send_message("terminal", "desktop", "First", path=self.path)
        ciq.send_message("terminal", "desktop", "Second", path=self.path)
        ctx = ciq.format_unread_context("desktop", self.path)
        self.assertIn("2 unread", ctx)

    def test_top_message_is_highest_priority(self):
        ciq.send_message("terminal", "desktop", "Low one", priority="low", path=self.path)
        ciq.send_message("terminal", "desktop", "Critical one", priority="critical", path=self.path)
        ctx = ciq.format_unread_context("desktop", self.path)
        self.assertIn("Critical one", ctx)

    def test_scope_warning_included(self):
        ciq.send_message("terminal", "desktop", "cca-loop scope",
                         category="scope_claim", priority="high", path=self.path)
        ctx = ciq.format_unread_context("desktop", self.path)
        self.assertIn("Active scope claims", ctx)


class TestFormatScopeWarning(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_no_scopes_returns_empty(self):
        warning = ciq.format_scope_warning(self.path)
        self.assertEqual(warning, "")

    def test_active_scope_shows_warning(self):
        ciq.send_message("terminal", "desktop", "cca-loop work",
                         category="scope_claim", files=["cca-loop/"],
                         path=self.path)
        warning = ciq.format_scope_warning(self.path)
        self.assertIn("SCOPE CLAIMS ACTIVE", warning)
        self.assertIn("CCA Terminal", warning)
        self.assertIn("cca-loop work", warning)

    def test_files_included_in_warning(self):
        ciq.send_message("terminal", "desktop", "cca-loop work",
                         category="scope_claim", files=["cca-loop/", "SESSION_RESUME.md"],
                         path=self.path)
        warning = ciq.format_scope_warning(self.path)
        self.assertIn("cca-loop/", warning)


class TestLoadSaveQueue(unittest.TestCase):
    def test_load_nonexistent_returns_empty(self):
        msgs = ciq._load_queue("/nonexistent/path.jsonl")
        self.assertEqual(msgs, [])

    def test_load_malformed_lines_skipped(self):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        tmp.write('{"valid": true}\n')
        tmp.write('not json\n')
        tmp.write('{"also_valid": true}\n')
        tmp.close()
        msgs = ciq._load_queue(tmp.name)
        self.assertEqual(len(msgs), 2)
        os.unlink(tmp.name)

    def test_roundtrip_preserves_data(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        tmp.close()
        original = [{"id": "test1", "data": "hello"}, {"id": "test2", "data": "world"}]
        ciq._save_queue(original, tmp.name)
        loaded = ciq._load_queue(tmp.name)
        self.assertEqual(loaded, original)
        os.unlink(tmp.name)


class TestMakeId(unittest.TestCase):
    def test_id_starts_with_cca(self):
        id1 = ciq._make_id("desktop", "test")
        self.assertTrue(id1.startswith("cca_"))

    def test_ids_are_unique(self):
        ids = {ciq._make_id("desktop", f"test_{i}") for i in range(10)}
        self.assertEqual(len(ids), 10)


class TestValidConstants(unittest.TestCase):
    def test_valid_chats_has_two(self):
        self.assertEqual(len(ciq.VALID_CHATS), 2)
        self.assertIn("desktop", ciq.VALID_CHATS)
        self.assertIn("terminal", ciq.VALID_CHATS)

    def test_valid_priorities(self):
        self.assertEqual(ciq.VALID_PRIORITIES, ["critical", "high", "medium", "low"])

    def test_valid_categories(self):
        self.assertIn("scope_claim", ciq.VALID_CATEGORIES)
        self.assertIn("scope_release", ciq.VALID_CATEGORIES)
        self.assertIn("conflict_alert", ciq.VALID_CATEGORIES)
        self.assertIn("handoff", ciq.VALID_CATEGORIES)
        self.assertIn("status_update", ciq.VALID_CATEGORIES)
        self.assertIn("question", ciq.VALID_CATEGORIES)
        self.assertIn("fyi", ciq.VALID_CATEGORIES)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
