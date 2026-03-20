#!/usr/bin/env python3
"""
Tests for cross_chat_queue.py — Bidirectional Cross-Chat Message Queue.
Run: python3 tests/test_cross_chat_queue.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import cross_chat_queue as ccq


class TestSendMessage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_send_creates_message(self):
        msg = ccq.send_message("cca", "km", "Test subject", path=self.path)
        self.assertIn("id", msg)
        self.assertEqual(msg["sender"], "cca")
        self.assertEqual(msg["target"], "km")
        self.assertEqual(msg["subject"], "Test subject")
        self.assertEqual(msg["status"], "unread")

    def test_send_writes_to_file(self):
        ccq.send_message("cca", "km", "Test", path=self.path)
        with open(self.path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        msg = json.loads(lines[0])
        self.assertEqual(msg["subject"], "Test")

    def test_send_appends_multiple(self):
        ccq.send_message("cca", "km", "First", path=self.path)
        ccq.send_message("cca", "kr", "Second", path=self.path)
        msgs = ccq._load_queue(self.path)
        self.assertEqual(len(msgs), 2)

    def test_send_with_body_and_refs(self):
        msg = ccq.send_message(
            "cca", "km", "Block 08:xx",
            body="z=-4.30, p<0.0001",
            ref_file="KALSHI_INTEL.md",
            ref_line="lines 100-110",
            path=self.path,
        )
        self.assertEqual(msg["body"], "z=-4.30, p<0.0001")
        self.assertEqual(msg["ref_file"], "KALSHI_INTEL.md")
        self.assertEqual(msg["ref_line"], "lines 100-110")

    def test_send_with_priority(self):
        msg = ccq.send_message("cca", "km", "Urgent", priority="critical", path=self.path)
        self.assertEqual(msg["priority"], "critical")

    def test_send_with_category(self):
        msg = ccq.send_message("cca", "km", "FYI", category="fyi", path=self.path)
        self.assertEqual(msg["category"], "fyi")

    def test_invalid_sender_raises(self):
        with self.assertRaises(ValueError):
            ccq.send_message("invalid", "km", "Test", path=self.path)

    def test_invalid_target_raises(self):
        with self.assertRaises(ValueError):
            ccq.send_message("cca", "invalid", "Test", path=self.path)

    def test_self_send_raises(self):
        with self.assertRaises(ValueError):
            ccq.send_message("cca", "cca", "Test", path=self.path)

    def test_empty_subject_raises(self):
        with self.assertRaises(ValueError):
            ccq.send_message("cca", "km", "", path=self.path)

    def test_invalid_priority_raises(self):
        with self.assertRaises(ValueError):
            ccq.send_message("cca", "km", "Test", priority="urgent", path=self.path)

    def test_invalid_category_raises(self):
        with self.assertRaises(ValueError):
            ccq.send_message("cca", "km", "Test", category="unknown", path=self.path)

    def test_id_format(self):
        msg = ccq.send_message("cca", "km", "Test", path=self.path)
        self.assertTrue(msg["id"].startswith("msg_"))
        self.assertGreater(len(msg["id"]), 15)

    def test_created_at_is_iso(self):
        msg = ccq.send_message("cca", "km", "Test", path=self.path)
        self.assertIn("T", msg["created_at"])
        self.assertTrue(msg["created_at"].endswith("Z"))

    def test_read_at_is_none(self):
        msg = ccq.send_message("cca", "km", "Test", path=self.path)
        self.assertIsNone(msg["read_at"])

    def test_km_can_send_to_cca(self):
        msg = ccq.send_message("km", "cca", "Response", path=self.path)
        self.assertEqual(msg["sender"], "km")
        self.assertEqual(msg["target"], "cca")

    def test_kr_can_send_to_cca(self):
        msg = ccq.send_message("kr", "cca", "Research update", path=self.path)
        self.assertEqual(msg["sender"], "kr")


class TestGetUnread(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_returns_unread_for_target(self):
        ccq.send_message("cca", "km", "For main", path=self.path)
        ccq.send_message("cca", "kr", "For research", path=self.path)
        unread = ccq.get_unread("km", self.path)
        self.assertEqual(len(unread), 1)
        self.assertEqual(unread[0]["subject"], "For main")

    def test_empty_queue_returns_empty(self):
        unread = ccq.get_unread("km", self.path)
        self.assertEqual(unread, [])

    def test_read_messages_excluded(self):
        ccq.send_message("cca", "km", "Test", path=self.path)
        msgs = ccq._load_queue(self.path)
        msgs[0]["status"] = "read"
        ccq._save_queue(msgs, self.path)
        unread = ccq.get_unread("km", self.path)
        self.assertEqual(len(unread), 0)


class TestAcknowledge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_ack_marks_as_read(self):
        msg = ccq.send_message("cca", "km", "Test", path=self.path)
        result = ccq.acknowledge(msg["id"], self.path)
        self.assertTrue(result)
        msgs = ccq._load_queue(self.path)
        self.assertEqual(msgs[0]["status"], "read")
        self.assertIsNotNone(msgs[0]["read_at"])

    def test_ack_nonexistent_returns_false(self):
        result = ccq.acknowledge("nonexistent_id", self.path)
        self.assertFalse(result)

    def test_ack_already_read_returns_false(self):
        msg = ccq.send_message("cca", "km", "Test", path=self.path)
        ccq.acknowledge(msg["id"], self.path)
        result = ccq.acknowledge(msg["id"], self.path)
        self.assertFalse(result)

    def test_ack_all_marks_all_for_target(self):
        ccq.send_message("cca", "km", "First", path=self.path)
        ccq.send_message("cca", "km", "Second", path=self.path)
        ccq.send_message("cca", "kr", "For research", path=self.path)
        count = ccq.acknowledge_all("km", self.path)
        self.assertEqual(count, 2)
        unread_km = ccq.get_unread("km", self.path)
        unread_kr = ccq.get_unread("kr", self.path)
        self.assertEqual(len(unread_km), 0)
        self.assertEqual(len(unread_kr), 1)

    def test_ack_all_empty_returns_zero(self):
        count = ccq.acknowledge_all("km", self.path)
        self.assertEqual(count, 0)


class TestGetUnreadSummary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_summary_groups_by_chat(self):
        ccq.send_message("cca", "km", "A", priority="high", path=self.path)
        ccq.send_message("cca", "km", "B", priority="critical", path=self.path)
        ccq.send_message("cca", "kr", "C", priority="low", path=self.path)
        summary = ccq.get_unread_summary(self.path)
        self.assertEqual(summary["km"]["total"], 2)
        self.assertEqual(summary["km"]["high"], 1)
        self.assertEqual(summary["km"]["critical"], 1)
        self.assertEqual(summary["kr"]["total"], 1)

    def test_empty_queue_returns_empty(self):
        summary = ccq.get_unread_summary(self.path)
        self.assertEqual(summary, {})

    def test_all_read_returns_empty(self):
        ccq.send_message("cca", "km", "Test", path=self.path)
        ccq.acknowledge_all("km", self.path)
        summary = ccq.get_unread_summary(self.path)
        self.assertEqual(summary, {})


class TestListMessages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_list_all(self):
        ccq.send_message("cca", "km", "A", path=self.path)
        ccq.send_message("cca", "kr", "B", path=self.path)
        msgs = ccq.list_messages(path=self.path)
        self.assertEqual(len(msgs), 2)

    def test_list_by_target(self):
        ccq.send_message("cca", "km", "A", path=self.path)
        ccq.send_message("cca", "kr", "B", path=self.path)
        msgs = ccq.list_messages(target="km", path=self.path)
        self.assertEqual(len(msgs), 1)

    def test_list_by_status(self):
        ccq.send_message("cca", "km", "A", path=self.path)
        msg = ccq.send_message("cca", "km", "B", path=self.path)
        ccq.acknowledge(msg["id"], self.path)
        unread = ccq.list_messages(status="unread", path=self.path)
        read = ccq.list_messages(status="read", path=self.path)
        self.assertEqual(len(unread), 1)
        self.assertEqual(len(read), 1)

    def test_list_empty(self):
        msgs = ccq.list_messages(path=self.path)
        self.assertEqual(msgs, [])


class TestFormatUnreadContext(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_no_unread_returns_empty(self):
        ctx = ccq.format_unread_context("km", self.path)
        self.assertEqual(ctx, "")

    def test_unread_returns_context_string(self):
        ccq.send_message("cca", "km", "Block 08:xx", priority="critical", path=self.path)
        ctx = ccq.format_unread_context("km", self.path)
        self.assertIn("[cross-chat]", ctx)
        self.assertIn("1 unread message", ctx)
        self.assertIn("Kalshi Main", ctx)
        self.assertIn("Block 08:xx", ctx)
        self.assertIn("critical", ctx)

    def test_multiple_unread_shows_count(self):
        ccq.send_message("cca", "km", "First", priority="high", path=self.path)
        ccq.send_message("cca", "km", "Second", priority="medium", path=self.path)
        ctx = ccq.format_unread_context("km", self.path)
        self.assertIn("2 unread messages", ctx)

    def test_top_message_is_highest_priority(self):
        ccq.send_message("cca", "km", "Low priority", priority="low", path=self.path)
        ccq.send_message("cca", "km", "Critical one", priority="critical", path=self.path)
        ctx = ccq.format_unread_context("km", self.path)
        self.assertIn("Critical one", ctx)


class TestLoadSaveQueue(unittest.TestCase):
    def test_load_nonexistent_returns_empty(self):
        msgs = ccq._load_queue("/nonexistent/path.jsonl")
        self.assertEqual(msgs, [])

    def test_load_malformed_lines_skipped(self):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        tmp.write('{"valid": true}\n')
        tmp.write('not json\n')
        tmp.write('{"also_valid": true}\n')
        tmp.close()
        msgs = ccq._load_queue(tmp.name)
        self.assertEqual(len(msgs), 2)
        os.unlink(tmp.name)

    def test_roundtrip_preserves_data(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        tmp.close()
        original = [{"id": "test1", "data": "hello"}, {"id": "test2", "data": "world"}]
        ccq._save_queue(original, tmp.name)
        loaded = ccq._load_queue(tmp.name)
        self.assertEqual(loaded, original)
        os.unlink(tmp.name)


class TestMakeId(unittest.TestCase):
    def test_id_starts_with_msg(self):
        id1 = ccq._make_id("cca", "test")
        self.assertTrue(id1.startswith("msg_"))

    def test_ids_are_unique(self):
        ids = {ccq._make_id("cca", f"test_{i}") for i in range(10)}
        self.assertEqual(len(ids), 10)


class TestValidConstants(unittest.TestCase):
    def test_valid_chats_has_three(self):
        self.assertEqual(len(ccq.VALID_CHATS), 3)
        self.assertIn("cca", ccq.VALID_CHATS)
        self.assertIn("km", ccq.VALID_CHATS)
        self.assertIn("kr", ccq.VALID_CHATS)

    def test_valid_priorities(self):
        self.assertEqual(ccq.VALID_PRIORITIES, ["critical", "high", "medium", "low"])

    def test_valid_categories(self):
        self.assertIn("action_item", ccq.VALID_CATEGORIES)
        self.assertIn("research_finding", ccq.VALID_CATEGORIES)
        self.assertIn("status_update", ccq.VALID_CATEGORIES)
        self.assertIn("question", ccq.VALID_CATEGORIES)
        self.assertIn("fyi", ccq.VALID_CATEGORIES)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
