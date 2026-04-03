#!/usr/bin/env python3
"""Tests for kalshi_cpi_readiness.py."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kalshi_cpi_readiness import collect_cpi_readiness, format_report, main


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _seed_polybot(tmpdir: str) -> None:
    _write(
        os.path.join(tmpdir, "src/strategies/economics_sniper.py"),
        "\n".join(
            [
                "PAPER_CALIBRATION_USD: float = 0.50",
                "_DEFAULT_TRIGGER_PRICE_CENTS = 88.0",
                "_DEFAULT_MAX_SECONDS_REMAINING = 172800",
                "_DEFAULT_HARD_SKIP_SECONDS = 300",
            ]
        ),
    )
    _write(
        os.path.join(tmpdir, "main.py"),
        "\n".join(
            [
                "async def economics_sniper_loop(",
                "PaperExecutor",
                "check_paper_order_allowed",
                "strategy.PAPER_CALIBRATION_USD",
                'name=\"economics_sniper_loop\"',
                'logger.info(\"Economics sniper loop started',
            ]
        ),
    )
    _write(
        os.path.join(tmpdir, "config.yaml"),
        "\n".join(
            [
                "kalshi:",
                "  mode: demo",
            ]
        ),
    )
    _write(
        os.path.join(tmpdir, "scripts/cpi_release_monitor.py"),
        "\n".join(
            [
                "NOT a trading bot",
                "NEXT CPI RELEASE: 2026-04-10 at 08:30 ET (13:30 UTC)",
            ]
        ),
    )
    _write(
        os.path.join(tmpdir, "tests/test_economics_sniper.py"),
        "class TestEconomicsSniperTimeGate:\n    pass\n",
    )
    _write(
        os.path.join(tmpdir, "tests/test_cpi_monitor.py"),
        "class TestDetectPriceChange:\n    pass\n",
    )


class TestKalshiCPIReadiness(unittest.TestCase):
    def test_collect_cpi_readiness_reports_watch_when_structure_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _seed_polybot(tmpdir)
            report = collect_cpi_readiness(
                polybot_root=tmpdir,
                now=datetime(2026, 4, 3, 18, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(report.overall, "watch")
            self.assertEqual(report.release_label, "2026-04-10 at 08:30 ET (13:30 UTC)")
            self.assertTrue(any(check.name == "config_mode" and check.status == "pass" for check in report.checks))
            self.assertTrue(any("Confirm open KXCPI contracts" in blocker for blocker in report.blockers))

    def test_collect_cpi_readiness_blocks_when_structure_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _seed_polybot(tmpdir)
            os.remove(os.path.join(tmpdir, "src/strategies/economics_sniper.py"))
            report = collect_cpi_readiness(
                polybot_root=tmpdir,
                now=datetime(2026, 4, 3, 18, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(report.overall, "blocked")
            self.assertTrue(any(check.name == "economics_strategy" and check.status == "fail" for check in report.checks))

    def test_format_report_contains_release_and_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _seed_polybot(tmpdir)
            report = collect_cpi_readiness(
                polybot_root=tmpdir,
                now=datetime(2026, 4, 3, 18, 0, tzinfo=timezone.utc),
            )

            text = format_report(report)
            self.assertIn("CPI READINESS: WATCH", text)
            self.assertIn("2026-04-10 at 08:30 ET", text)
            self.assertIn("Next Actions", text)

    def test_main_json_emits_structured_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _seed_polybot(tmpdir)

            with patch("sys.stdout.write") as mock_write:
                exit_code = main(["--polybot-root", tmpdir, "--json"])

            self.assertEqual(exit_code, 0)
            payload = "".join(call.args[0] for call in mock_write.call_args_list)
            data = json.loads(payload)
            self.assertEqual(data["overall"], "watch")
            self.assertEqual(data["release_label"], "2026-04-10 at 08:30 ET (13:30 UTC)")
            self.assertGreater(len(data["checks"]), 0)


if __name__ == "__main__":
    unittest.main()
