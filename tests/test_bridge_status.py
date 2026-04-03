#!/usr/bin/env python3
"""Tests for bridge_status.py."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge_status import collect_bridge_status, format_report, main


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _set_mtime(path: str, when: datetime) -> None:
    ts = when.timestamp()
    os.utime(path, (ts, ts))


class TestBridgeStatus(unittest.TestCase):
    def test_collect_bridge_status_flags_missing_and_lagging(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cca_root = os.path.join(tmpdir, "cca")
            polybot_root = os.path.join(tmpdir, "poly")
            cross_chat_dir = os.path.join(tmpdir, "cross")
            os.makedirs(cca_root, exist_ok=True)
            os.makedirs(polybot_root, exist_ok=True)
            os.makedirs(cross_chat_dir, exist_ok=True)

            _write(
                os.path.join(cca_root, "CLAUDE_TO_CODEX.md"),
                "## [2026-04-03 00:00 UTC] — MESSAGE — Claude note\n",
            )
            _set_mtime(
                os.path.join(cca_root, "CLAUDE_TO_CODEX.md"),
                datetime(2026, 4, 3, 0, 0, tzinfo=timezone.utc),
            )
            _write(
                os.path.join(cca_root, "CODEX_TO_CLAUDE.md"),
                "## [2026-04-03 01:00 UTC] — UPDATE — Codex note\n",
            )
            _set_mtime(
                os.path.join(cca_root, "CODEX_TO_CLAUDE.md"),
                datetime(2026, 4, 3, 1, 0, tzinfo=timezone.utc),
            )
            _write(
                os.path.join(cross_chat_dir, "CCA_TO_POLYBOT.md"),
                "## [2026-04-02 10:00 UTC] — DELIVERY — Old delivery\n",
            )
            _set_mtime(
                os.path.join(cross_chat_dir, "CCA_TO_POLYBOT.md"),
                datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
            )
            _write(
                os.path.join(cross_chat_dir, "POLYBOT_TO_CCA.md"),
                "## [2026-04-03 02:00 UTC] — REQUEST — Fresh request\n",
            )
            _set_mtime(
                os.path.join(cross_chat_dir, "POLYBOT_TO_CCA.md"),
                datetime(2026, 4, 3, 2, 0, tzinfo=timezone.utc),
            )
            _write(
                os.path.join(polybot_root, "CODEX_OBSERVATIONS.md"),
                "## [2026-04-03] — BUG-FLAG — Fresh Kalshi note\n",
            )
            _set_mtime(
                os.path.join(polybot_root, "CODEX_OBSERVATIONS.md"),
                datetime(2026, 4, 3, 6, 0, tzinfo=timezone.utc),
            )

            now = datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)

            status = collect_bridge_status(
                cca_root=cca_root,
                polybot_root=polybot_root,
                cross_chat_dir=cross_chat_dir,
                stale_hours=6.0,
                response_gap_hours=4.0,
                now=now,
            )

            self.assertEqual(status.overall, "attention")
            self.assertTrue(any("CCA -> Kalshi" in item for item in status.attention))
            self.assertTrue(any("Kalshi -> CCA is newer" in item for item in status.attention))
            self.assertTrue(any("Kalshi -> Codex is newer" in item for item in status.attention))

    def test_format_report_contains_latest_headings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cca_root = os.path.join(tmpdir, "cca")
            polybot_root = os.path.join(tmpdir, "poly")
            cross_chat_dir = os.path.join(tmpdir, "cross")
            os.makedirs(cca_root, exist_ok=True)
            os.makedirs(polybot_root, exist_ok=True)
            os.makedirs(cross_chat_dir, exist_ok=True)

            _write(
                os.path.join(cca_root, "CLAUDE_TO_CODEX.md"),
                "## [2026-04-03 00:00 UTC] — MESSAGE — Claude note\n",
            )
            _write(
                os.path.join(cca_root, "CODEX_TO_CLAUDE.md"),
                "## [2026-04-03 01:00 UTC] — UPDATE — Codex note\n",
            )
            _write(
                os.path.join(cross_chat_dir, "CCA_TO_POLYBOT.md"),
                "## [2026-04-03 02:00 UTC] — DELIVERY — Kalshi delivery\n",
            )
            _write(
                os.path.join(cross_chat_dir, "POLYBOT_TO_CCA.md"),
                "## [2026-04-03 03:00 UTC] — REQUEST — Kalshi request\n",
            )
            _write(
                os.path.join(polybot_root, "CODEX_OBSERVATIONS.md"),
                "## [2026-04-03] — ARCHITECTURE — Codex observation\n",
            )

            now = datetime(2026, 4, 3, 4, 0, tzinfo=timezone.utc)
            status = collect_bridge_status(
                cca_root=cca_root,
                polybot_root=polybot_root,
                cross_chat_dir=cross_chat_dir,
                now=now,
            )

            report = format_report(status)
            self.assertIn("3-WAY BRIDGE STATUS", report)
            self.assertIn("Claude note", report)
            self.assertIn("Kalshi delivery", report)
            self.assertIn("Codex observation", report)

    def test_main_json_emits_structured_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cca_root = os.path.join(tmpdir, "cca")
            polybot_root = os.path.join(tmpdir, "poly")
            cross_chat_dir = os.path.join(tmpdir, "cross")
            os.makedirs(cca_root, exist_ok=True)
            os.makedirs(polybot_root, exist_ok=True)
            os.makedirs(cross_chat_dir, exist_ok=True)

            _write(os.path.join(cca_root, "CLAUDE_TO_CODEX.md"), "")
            _write(os.path.join(cca_root, "CODEX_TO_CLAUDE.md"), "")
            _write(os.path.join(cross_chat_dir, "CCA_TO_POLYBOT.md"), "")
            _write(os.path.join(cross_chat_dir, "POLYBOT_TO_CCA.md"), "")
            _write(os.path.join(polybot_root, "CODEX_OBSERVATIONS.md"), "")

            with patch("sys.stdout.write") as mock_write:
                exit_code = main(
                    [
                        "--cca-root",
                        cca_root,
                        "--polybot-root",
                        polybot_root,
                        "--cross-chat-dir",
                        cross_chat_dir,
                        "--json",
                    ]
                )
            self.assertEqual(exit_code, 0)
            payload = "".join(call.args[0] for call in mock_write.call_args_list)
            data = json.loads(payload)
            self.assertEqual(data["overall"], "healthy")
            self.assertEqual(len(data["lanes"]), 5)


if __name__ == "__main__":
    unittest.main()
