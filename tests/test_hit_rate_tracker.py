"""
test_hit_rate_tracker.py — Tests for hit_rate_tracker.py (MT-12 Phase 6)

Tests APF computation, frontier breakdown, trend analysis, and parsing.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "self-learning"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SAMPLE_LOG = """[2026-03-20] [BUILD] [Frontier 1: Memory] "Memory store v2" (87pts, 45c, r/ClaudeCode). Built it.
[2026-03-20] [ADAPT] [Frontier 2: Spec] "Spec framework" (52pts, 31c, r/ClaudeCode). Adapted.
[2026-03-20] [REFERENCE] [Frontier 3: Context] "Context tool" (53pts, 52c, r/ClaudeCode). Reference only.
[2026-03-20] [SKIP] [Frontier 5: Dashboard] "Dashboard thing" (3pts, 1c, r/ClaudeCode). Skipped.
[2026-03-19] [BUILD] [Frontier 4: Agent Guard] "Guard tool" (17pts, 90c, r/ClaudeCode). Built it.
[2026-03-19] [REFERENCE-PERSONAL] [MT-0 Kalshi] "Trading idea" (35pts, 100c, r/algotrading). Personal.
[2026-03-19] [ADAPT] [Frontier 1: Memory] "Memory helper" (11pts, 49c, r/ClaudeCode). Adapted.
[2026-03-19] [SKIP] [Other] "Generic tool" (165pts, 47c, r/ClaudeCode). Skipped.
[2026-03-18] [BUILD] [Frontier 2: Spec] "Spec tool" (45pts, 0c, r/ClaudeCode). Built it.
[2026-03-18] [REFERENCE] [MT-21 Hivemind] "Hivemind approach" (4pts, 15c, r/ClaudeCode). Reference.
"""


class TestParsing(unittest.TestCase):
    """Test FINDINGS_LOG.md parsing."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = Path(self.tmpdir) / "FINDINGS_LOG.md"
        self.log_path.write_text(SAMPLE_LOG)

    def test_parse_count(self):
        from hit_rate_tracker import parse_findings
        entries = parse_findings(self.log_path)
        self.assertEqual(len(entries), 10)

    def test_parse_verdict(self):
        from hit_rate_tracker import parse_findings
        entries = parse_findings(self.log_path)
        verdicts = [e["verdict"] for e in entries]
        self.assertEqual(verdicts.count("BUILD"), 3)
        self.assertEqual(verdicts.count("ADAPT"), 2)
        self.assertEqual(verdicts.count("SKIP"), 2)

    def test_parse_date(self):
        from hit_rate_tracker import parse_findings
        entries = parse_findings(self.log_path)
        self.assertEqual(entries[0]["date"], "2026-03-20")

    def test_parse_title(self):
        from hit_rate_tracker import parse_findings
        entries = parse_findings(self.log_path)
        self.assertEqual(entries[0]["title"], "Memory store v2")

    def test_parse_score(self):
        from hit_rate_tracker import parse_findings
        entries = parse_findings(self.log_path)
        self.assertEqual(entries[0]["score"], 87)

    def test_parse_frontier(self):
        from hit_rate_tracker import parse_findings
        entries = parse_findings(self.log_path)
        self.assertEqual(entries[0]["frontier"], "Frontier 1: Memory")

    def test_empty_file(self):
        from hit_rate_tracker import parse_findings
        empty = Path(self.tmpdir) / "empty.md"
        empty.write_text("")
        entries = parse_findings(empty)
        self.assertEqual(len(entries), 0)

    def test_missing_file(self):
        from hit_rate_tracker import parse_findings
        missing = Path(self.tmpdir) / "missing.md"
        entries = parse_findings(missing)
        self.assertEqual(len(entries), 0)

    def test_ignores_invalid_verdicts(self):
        from hit_rate_tracker import parse_findings
        bad = Path(self.tmpdir) / "bad.md"
        bad.write_text('[2026-03-20] [INVALID] [Test] "Bad entry" (1pts)\n')
        entries = parse_findings(bad)
        self.assertEqual(len(entries), 0)


class TestAPFComputation(unittest.TestCase):
    """Test APF metric computation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = Path(self.tmpdir) / "FINDINGS_LOG.md"
        self.log_path.write_text(SAMPLE_LOG)

    def test_apf_value(self):
        from hit_rate_tracker import parse_findings, compute_apf
        entries = parse_findings(self.log_path)
        metrics = compute_apf(entries)
        # 3 BUILD + 2 ADAPT = 5 signal / 10 total = 50%
        self.assertEqual(metrics["apf"], 50.0)

    def test_signal_count(self):
        from hit_rate_tracker import parse_findings, compute_apf
        entries = parse_findings(self.log_path)
        metrics = compute_apf(entries)
        self.assertEqual(metrics["signal"], 5)

    def test_total_count(self):
        from hit_rate_tracker import parse_findings, compute_apf
        entries = parse_findings(self.log_path)
        metrics = compute_apf(entries)
        self.assertEqual(metrics["total"], 10)

    def test_useful_rate(self):
        from hit_rate_tracker import parse_findings, compute_apf
        entries = parse_findings(self.log_path)
        metrics = compute_apf(entries)
        # (3 BUILD + 2 ADAPT + 2 REFERENCE) / 10 = 70%
        self.assertEqual(metrics["useful_rate"], 70.0)

    def test_empty_entries(self):
        from hit_rate_tracker import compute_apf
        metrics = compute_apf([])
        self.assertEqual(metrics["apf"], 0.0)
        self.assertEqual(metrics["total"], 0)

    def test_all_builds(self):
        from hit_rate_tracker import compute_apf
        entries = [{"verdict": "BUILD"} for _ in range(5)]
        metrics = compute_apf(entries)
        self.assertEqual(metrics["apf"], 100.0)

    def test_all_skips(self):
        from hit_rate_tracker import compute_apf
        entries = [{"verdict": "SKIP"} for _ in range(5)]
        metrics = compute_apf(entries)
        self.assertEqual(metrics["apf"], 0.0)

    def test_verdict_breakdown(self):
        from hit_rate_tracker import parse_findings, compute_apf
        entries = parse_findings(self.log_path)
        metrics = compute_apf(entries)
        self.assertEqual(metrics["build"], 3)
        self.assertEqual(metrics["adapt"], 2)
        self.assertEqual(metrics["reference"], 2)
        self.assertEqual(metrics["reference_personal"], 1)
        self.assertEqual(metrics["skip"], 2)


class TestByFrontier(unittest.TestCase):
    """Test frontier breakdown."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = Path(self.tmpdir) / "FINDINGS_LOG.md"
        self.log_path.write_text(SAMPLE_LOG)

    def test_has_frontiers(self):
        from hit_rate_tracker import parse_findings, compute_by_frontier
        entries = parse_findings(self.log_path)
        by_frontier = compute_by_frontier(entries)
        self.assertIn("Frontier 1: Memory", by_frontier)
        self.assertIn("Frontier 2: Spec", by_frontier)

    def test_frontier_1_apf(self):
        from hit_rate_tracker import parse_findings, compute_by_frontier
        entries = parse_findings(self.log_path)
        by_frontier = compute_by_frontier(entries)
        f1 = by_frontier["Frontier 1: Memory"]
        # 1 BUILD + 1 ADAPT / 2 total = 100%
        self.assertEqual(f1["signal"], 2)
        self.assertEqual(f1["total"], 2)

    def test_kalshi_category(self):
        from hit_rate_tracker import parse_findings, compute_by_frontier
        entries = parse_findings(self.log_path)
        by_frontier = compute_by_frontier(entries)
        self.assertIn("MT-0 Kalshi", by_frontier)

    def test_other_category(self):
        from hit_rate_tracker import parse_findings, compute_by_frontier
        entries = parse_findings(self.log_path)
        by_frontier = compute_by_frontier(entries)
        self.assertIn("Other", by_frontier)


class TestTrend(unittest.TestCase):
    """Test APF trend computation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = Path(self.tmpdir) / "FINDINGS_LOG.md"
        self.log_path.write_text(SAMPLE_LOG)

    def test_trend_has_dates(self):
        from hit_rate_tracker import parse_findings, compute_trend
        entries = parse_findings(self.log_path)
        trend = compute_trend(entries)
        self.assertGreater(len(trend), 0)
        dates = [t["date"] for t in trend]
        self.assertIn("2026-03-20", dates)

    def test_trend_sorted_ascending(self):
        from hit_rate_tracker import parse_findings, compute_trend
        entries = parse_findings(self.log_path)
        trend = compute_trend(entries)
        dates = [t["date"] for t in trend]
        self.assertEqual(dates, sorted(dates))

    def test_trend_daily_count(self):
        from hit_rate_tracker import parse_findings, compute_trend
        entries = parse_findings(self.log_path)
        trend = compute_trend(entries)
        # March 20 has 4 entries
        mar20 = [t for t in trend if t["date"] == "2026-03-20"][0]
        self.assertEqual(mar20["daily_count"], 4)

    def test_trend_rolling_window(self):
        from hit_rate_tracker import parse_findings, compute_trend
        entries = parse_findings(self.log_path)
        trend = compute_trend(entries, window=3)
        # Last entry should have rolling window covering all 3 dates
        self.assertEqual(trend[-1]["rolling_window"], 3)

    def test_empty_trend(self):
        from hit_rate_tracker import compute_trend
        trend = compute_trend([])
        self.assertEqual(len(trend), 0)


class TestFormatReport(unittest.TestCase):
    """Test report formatting."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = Path(self.tmpdir) / "FINDINGS_LOG.md"
        self.log_path.write_text(SAMPLE_LOG)

    def test_report_has_apf(self):
        from hit_rate_tracker import parse_findings, format_report
        entries = parse_findings(self.log_path)
        report = format_report(entries)
        self.assertIn("APF:", report)
        self.assertIn("50.0%", report)

    def test_report_has_frontiers(self):
        from hit_rate_tracker import parse_findings, format_report
        entries = parse_findings(self.log_path)
        report = format_report(entries)
        self.assertIn("By Frontier:", report)

    def test_report_has_totals(self):
        from hit_rate_tracker import parse_findings, format_report
        entries = parse_findings(self.log_path)
        report = format_report(entries)
        self.assertIn("Total findings: 10", report)


class TestRealData(unittest.TestCase):
    """Test against the actual FINDINGS_LOG.md if it exists."""

    def test_real_findings_log_parseable(self):
        from hit_rate_tracker import parse_findings, FINDINGS_LOG_PATH
        if not FINDINGS_LOG_PATH.exists():
            self.skipTest("No real FINDINGS_LOG.md")
        entries = parse_findings()
        self.assertGreater(len(entries), 0)

    def test_real_apf_in_range(self):
        from hit_rate_tracker import parse_findings, compute_apf, FINDINGS_LOG_PATH
        if not FINDINGS_LOG_PATH.exists():
            self.skipTest("No real FINDINGS_LOG.md")
        entries = parse_findings()
        metrics = compute_apf(entries)
        self.assertGreaterEqual(metrics["apf"], 0)
        self.assertLessEqual(metrics["apf"], 100)

    def test_main_callable(self):
        import hit_rate_tracker
        self.assertTrue(hasattr(hit_rate_tracker, "main"))


if __name__ == "__main__":
    unittest.main()
