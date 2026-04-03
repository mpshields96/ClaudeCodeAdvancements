#!/usr/bin/env python3
"""Tests for cross_chat_board.py."""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cross_chat_board


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestCrossChatBoard(unittest.TestCase):
    def test_kalshi_check_surfaces_latest_headings_and_req66(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            queue = root / "REQUEST_QUEUE.md"
            cca_to_bot = root / "CCA_TO_POLYBOT.md"
            bot_to_cca = root / "POLYBOT_TO_CCA.md"
            delivery_flag = root / ".new_cca_delivery"
            last_check = root / ".kalshi_last_cca_check"

            _write(
                queue,
                "### REQ-066 | URGENT | Status: PENDING\n"
                "Topic: April 13 deadline market diversification\n"
                "Submitted: 2026-04-03\n",
            )
            _write(
                cca_to_bot,
                "## [2026-04-03 16:05 UTC] — REQ-66 DELIVERY — Sports Timing / UCL / CPI / Combo Verdict\n"
                "Body\n",
            )
            _write(
                bot_to_cca,
                "## [2026-04-03 05:10 UTC] — REQUEST 66 — URGENT: NEW MARKET EDGES FOR APRIL 13 DEADLINE\n"
                "Body\n",
            )
            _write(delivery_flag, "2026-04-03T16:05:00+00:00")
            _write(last_check, "2026-04-03T05:15:00+00:00")

            with (
                patch.object(cross_chat_board, "QUEUE_FILE", queue),
                patch.object(cross_chat_board, "CCA_TO_BOT", cca_to_bot),
                patch.object(cross_chat_board, "BOT_TO_CCA", bot_to_cca),
                patch.object(cross_chat_board, "DELIVERY_FLAG", delivery_flag),
                patch.object(cross_chat_board, "KALSHI_LAST_CHECK", last_check),
                patch("sys.stdout", new_callable=io.StringIO) as stdout,
            ):
                result = cross_chat_board.kalshi_check()

            self.assertTrue(result["has_new_delivery"])
            self.assertTrue(result["req66_answered"])
            self.assertTrue(result["should_read_outbox"])
            self.assertIn("REQ-66 DELIVERY", result["latest_delivery_heading"])
            self.assertIn("REQUEST 66", result["latest_request_heading"])
            self.assertEqual(result["latest_delivery_req_ids"], ["REQ-066"])
            self.assertEqual(result["latest_request_req_ids"], ["REQ-066"])
            self.assertIn("Read CCA_TO_POLYBOT.md now", result["action_hint"])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["latest_delivery_heading"], result["latest_delivery_heading"])

    def test_kalshi_check_falls_back_to_req66_hint_without_new_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            queue = root / "REQUEST_QUEUE.md"
            cca_to_bot = root / "CCA_TO_POLYBOT.md"
            bot_to_cca = root / "POLYBOT_TO_CCA.md"
            delivery_flag = root / ".new_cca_delivery"
            last_check = root / ".kalshi_last_cca_check"

            _write(queue, "")
            _write(
                cca_to_bot,
                "## [2026-04-03 16:05 UTC] — REQ-66 DELIVERY — Sports Timing / UCL / CPI / Combo Verdict\n",
            )
            _write(
                bot_to_cca,
                "## [2026-04-03 05:10 UTC] — REQUEST 66 — URGENT: NEW MARKET EDGES FOR APRIL 13 DEADLINE\n",
            )
            _write(delivery_flag, "2026-04-03T16:05:00+00:00")
            _write(last_check, "2026-04-03T16:10:00+00:00")

            with (
                patch.object(cross_chat_board, "QUEUE_FILE", queue),
                patch.object(cross_chat_board, "CCA_TO_BOT", cca_to_bot),
                patch.object(cross_chat_board, "BOT_TO_CCA", bot_to_cca),
                patch.object(cross_chat_board, "DELIVERY_FLAG", delivery_flag),
                patch.object(cross_chat_board, "KALSHI_LAST_CHECK", last_check),
                patch("sys.stdout", new_callable=io.StringIO),
            ):
                result = cross_chat_board.kalshi_check()

            self.assertFalse(result["has_new_delivery"])
            self.assertTrue(result["req66_answered"])
            self.assertFalse(result["should_read_outbox"])
            self.assertEqual(result["latest_delivery_req_ids"], ["REQ-066"])
            self.assertEqual(result["latest_request_req_ids"], ["REQ-066"])
            self.assertIn("REQ-66 has a CCA answer", result["action_hint"])


if __name__ == "__main__":
    unittest.main()
