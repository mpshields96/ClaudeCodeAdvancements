"""
test_polybot_comm_learning.py — Tests for polybot_comm.py learning loop functions.

Tests send_outcome_report() and parse_research_priorities() — the Kalshi-side
helpers that complement CCA's learning_loop.py.

S164 — REQ-038 cross-chat learning loop implementation.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add polybot scripts to path
POLYBOT_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "polymarket-bot", "scripts"
)
sys.path.insert(0, POLYBOT_SCRIPTS)


class TestSendOutcomeReport(unittest.TestCase):
    """Test send_outcome_report() writes correct queue messages."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        if os.path.exists(self.queue_path):
            os.remove(self.queue_path)
        os.rmdir(self.tmpdir)

    @patch("polybot_comm.CROSS_CHAT_QUEUE")
    def test_basic_outcome_report(self, mock_path):
        from polybot_comm import send_outcome_report
        mock_path.__str__ = lambda s: self.queue_path
        # Patch to use our temp path
        with patch("polybot_comm.CROSS_CHAT_QUEUE", Path(self.queue_path)):
            msg_id = send_outcome_report("UPDATE-33", "profitable", profit_cents=500, bet_count=15)

        self.assertTrue(msg_id.startswith("msg_"))
        with open(self.queue_path) as f:
            msg = json.loads(f.readline())
        self.assertEqual(msg["category"], "outcome_report")
        self.assertEqual(msg["sender"], "km")
        self.assertEqual(msg["target"], "cca")
        self.assertEqual(msg["status"], "unread")
        body = json.loads(msg["body"])
        self.assertEqual(body["delivery_id"], "UPDATE-33")
        self.assertEqual(body["status"], "profitable")
        self.assertEqual(body["profit_cents"], 500)
        self.assertEqual(body["bet_count"], 15)

    @patch("polybot_comm.CROSS_CHAT_QUEUE")
    def test_minimal_outcome_report(self, mock_path):
        from polybot_comm import send_outcome_report
        with patch("polybot_comm.CROSS_CHAT_QUEUE", Path(self.queue_path)):
            send_outcome_report("UPDATE-10", "rejected")

        with open(self.queue_path) as f:
            msg = json.loads(f.readline())
        body = json.loads(msg["body"])
        self.assertEqual(body["delivery_id"], "UPDATE-10")
        self.assertEqual(body["status"], "rejected")
        self.assertNotIn("profit_cents", body)
        self.assertNotIn("bet_count", body)

    @patch("polybot_comm.CROSS_CHAT_QUEUE")
    def test_outcome_report_with_notes(self, mock_path):
        from polybot_comm import send_outcome_report
        with patch("polybot_comm.CROSS_CHAT_QUEUE", Path(self.queue_path)):
            send_outcome_report("UPDATE-5", "unprofitable", profit_cents=-200, notes="Edge disappeared after FOMC")

        with open(self.queue_path) as f:
            body = json.loads(json.loads(f.readline())["body"])
        self.assertEqual(body["notes"], "Edge disappeared after FOMC")
        self.assertEqual(body["profit_cents"], -200)

    def test_invalid_status_raises(self):
        from polybot_comm import send_outcome_report
        with self.assertRaises(ValueError):
            send_outcome_report("UPDATE-1", "invalid_status")

    @patch("polybot_comm.CROSS_CHAT_QUEUE")
    def test_multiple_reports_appended(self, mock_path):
        from polybot_comm import send_outcome_report
        with patch("polybot_comm.CROSS_CHAT_QUEUE", Path(self.queue_path)):
            send_outcome_report("UPDATE-1", "profitable", profit_cents=100)
            send_outcome_report("UPDATE-2", "unprofitable", profit_cents=-50)

        with open(self.queue_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(json.loads(lines[0])["body"])["delivery_id"], "UPDATE-1")
        self.assertEqual(json.loads(json.loads(lines[1])["body"])["delivery_id"], "UPDATE-2")


class TestParseResearchPriorities(unittest.TestCase):
    """Test parse_research_priorities() reads CCA priority messages."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        if os.path.exists(self.queue_path):
            os.remove(self.queue_path)
        os.rmdir(self.tmpdir)

    def _write_queue(self, messages):
        with open(self.queue_path, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

    @patch("polybot_comm.CROSS_CHAT_QUEUE")
    def test_no_queue_file(self, mock_path):
        from polybot_comm import parse_research_priorities
        with patch("polybot_comm.CROSS_CHAT_QUEUE", Path(os.path.join(self.tmpdir, "nonexistent.jsonl"))):
            result = parse_research_priorities()
        self.assertEqual(result, [])

    @patch("polybot_comm.CROSS_CHAT_QUEUE")
    def test_single_priority(self, mock_path):
        from polybot_comm import parse_research_priorities
        self._write_queue([{
            "id": "msg_1", "sender": "cca", "target": "km",
            "category": "research_priority",
            "body": json.dumps({"category": "FLB_research", "score": 75.0,
                               "recommendation": "HIGH — FLB: 80% hit rate"}),
        }])
        with patch("polybot_comm.CROSS_CHAT_QUEUE", Path(self.queue_path)):
            result = parse_research_priorities()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["category"], "FLB_research")
        self.assertEqual(result[0]["score"], 75.0)

    @patch("polybot_comm.CROSS_CHAT_QUEUE")
    def test_multiple_priorities_sorted_by_score(self, mock_path):
        from polybot_comm import parse_research_priorities
        self._write_queue([
            {"id": "msg_1", "sender": "cca", "target": "km", "category": "research_priority",
             "body": json.dumps({"category": "guard_discovery", "score": 30.0})},
            {"id": "msg_2", "sender": "cca", "target": "km", "category": "research_priority",
             "body": json.dumps({"category": "FLB_research", "score": 75.0})},
            {"id": "msg_3", "sender": "cca", "target": "km", "category": "research_priority",
             "body": json.dumps({"category": "maker_orders", "score": 55.0})},
        ])
        with patch("polybot_comm.CROSS_CHAT_QUEUE", Path(self.queue_path)):
            result = parse_research_priorities()
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["category"], "FLB_research")
        self.assertEqual(result[1]["category"], "maker_orders")
        self.assertEqual(result[2]["category"], "guard_discovery")

    @patch("polybot_comm.CROSS_CHAT_QUEUE")
    def test_latest_per_category_wins(self, mock_path):
        from polybot_comm import parse_research_priorities
        self._write_queue([
            {"id": "msg_1", "sender": "cca", "target": "km", "category": "research_priority",
             "body": json.dumps({"category": "FLB_research", "score": 50.0})},
            {"id": "msg_2", "sender": "cca", "target": "km", "category": "research_priority",
             "body": json.dumps({"category": "FLB_research", "score": 80.0})},
        ])
        with patch("polybot_comm.CROSS_CHAT_QUEUE", Path(self.queue_path)):
            result = parse_research_priorities()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["score"], 80.0)

    @patch("polybot_comm.CROSS_CHAT_QUEUE")
    def test_ignores_non_priority_messages(self, mock_path):
        from polybot_comm import parse_research_priorities
        self._write_queue([
            {"id": "msg_1", "sender": "cca", "target": "km", "category": "action_item",
             "body": json.dumps({"subject": "Block 08:xx"})},
            {"id": "msg_2", "sender": "cca", "target": "km", "category": "research_priority",
             "body": json.dumps({"category": "FLB", "score": 70.0})},
        ])
        with patch("polybot_comm.CROSS_CHAT_QUEUE", Path(self.queue_path)):
            result = parse_research_priorities()
        self.assertEqual(len(result), 1)

    @patch("polybot_comm.CROSS_CHAT_QUEUE")
    def test_ignores_messages_from_other_senders(self, mock_path):
        from polybot_comm import parse_research_priorities
        self._write_queue([
            {"id": "msg_1", "sender": "km", "target": "cca", "category": "research_priority",
             "body": json.dumps({"category": "FLB", "score": 70.0})},
        ])
        with patch("polybot_comm.CROSS_CHAT_QUEUE", Path(self.queue_path)):
            result = parse_research_priorities()
        self.assertEqual(result, [])

    @patch("polybot_comm.CROSS_CHAT_QUEUE")
    def test_handles_malformed_body(self, mock_path):
        from polybot_comm import parse_research_priorities
        self._write_queue([
            {"id": "msg_1", "sender": "cca", "target": "km", "category": "research_priority",
             "body": "not json"},
        ])
        with patch("polybot_comm.CROSS_CHAT_QUEUE", Path(self.queue_path)):
            result = parse_research_priorities()
        self.assertEqual(result, [])


class TestOutcomeReportIntegration(unittest.TestCase):
    """Test that outcome reports written by polybot can be read by CCA's learning_loop."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        if os.path.exists(self.queue_path):
            os.remove(self.queue_path)
        os.rmdir(self.tmpdir)

    @patch("polybot_comm.CROSS_CHAT_QUEUE")
    def test_polybot_write_cca_read(self, mock_path):
        """Verify polybot's send_outcome_report produces messages CCA's learning_loop can parse."""
        from polybot_comm import send_outcome_report

        with patch("polybot_comm.CROSS_CHAT_QUEUE", Path(self.queue_path)):
            send_outcome_report("UPDATE-33", "profitable", profit_cents=500, bet_count=15)

        # Now read the queue the way learning_loop does
        with open(self.queue_path) as f:
            msg = json.loads(f.readline())

        self.assertEqual(msg["category"], "outcome_report")
        self.assertEqual(msg["target"], "cca")
        self.assertEqual(msg["status"], "unread")

        body = json.loads(msg["body"])
        self.assertEqual(body["delivery_id"], "UPDATE-33")
        self.assertEqual(body["status"], "profitable")


if __name__ == "__main__":
    unittest.main()
