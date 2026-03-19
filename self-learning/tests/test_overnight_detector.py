#!/usr/bin/env python3
"""Tests for overnight_detector.py — objective signal detection."""

import unittest
import os
import sys
import json
import tempfile
import shutil
import math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

import journal
import overnight_detector as od


class TestWilsonCI(unittest.TestCase):
    """Test Wilson score confidence interval calculation."""

    def test_perfect_wr(self):
        lo, hi = od.wilson_ci(20, 20)
        self.assertGreater(lo, 0.80)
        self.assertAlmostEqual(hi, 1.0, places=2)

    def test_zero_wr(self):
        lo, hi = od.wilson_ci(20, 0)
        self.assertAlmostEqual(lo, 0.0, places=2)
        self.assertLess(hi, 0.20)

    def test_50_pct_wr(self):
        lo, hi = od.wilson_ci(100, 50)
        self.assertGreater(lo, 0.39)
        self.assertLess(hi, 0.61)

    def test_empty_sample(self):
        lo, hi = od.wilson_ci(0, 0)
        self.assertEqual(lo, 0.0)
        self.assertEqual(hi, 1.0)

    def test_large_sample_narrow_ci(self):
        lo, hi = od.wilson_ci(1000, 950)
        # 95% WR with n=1000 should have tight CI
        self.assertGreater(lo, 0.93)
        self.assertLess(hi, 0.97)

    def test_small_sample_wide_ci(self):
        lo, hi = od.wilson_ci(5, 4)
        # 80% WR with n=5 — wide CI
        self.assertLess(lo, 0.40)
        self.assertGreater(hi, 0.90)


class TestCUSUM(unittest.TestCase):
    """Test CUSUM changepoint detection."""

    def test_no_signal_all_wins(self):
        outcomes = [1] * 50
        signaled, max_s, idx = od.cusum_signal(outcomes, 0.90, 0.70)
        self.assertFalse(signaled)

    def test_signal_on_loss_streak(self):
        outcomes = [1] * 10 + [0] * 20
        signaled, max_s, idx = od.cusum_signal(outcomes, 0.90, 0.70)
        self.assertTrue(signaled)
        self.assertIsNotNone(idx)

    def test_no_signal_few_losses(self):
        outcomes = [1] * 20 + [0, 1, 1, 1, 1]
        signaled, max_s, idx = od.cusum_signal(outcomes, 0.90, 0.70)
        self.assertFalse(signaled)

    def test_signal_index_accuracy(self):
        # 10 wins, then losses — trigger should be in the loss region
        outcomes = [1] * 10 + [0] * 20
        signaled, _, idx = od.cusum_signal(outcomes, 0.90, 0.70)
        self.assertTrue(signaled)
        self.assertGreaterEqual(idx, 10)

    def test_empty_outcomes(self):
        signaled, max_s, idx = od.cusum_signal([], 0.90, 0.70)
        self.assertFalse(signaled)
        self.assertIsNone(idx)


class TestCIsOverlap(unittest.TestCase):
    """Test confidence interval overlap check."""

    def test_overlapping(self):
        self.assertTrue(od.cis_overlap((0.3, 0.7), (0.5, 0.9)))

    def test_not_overlapping(self):
        self.assertFalse(od.cis_overlap((0.1, 0.3), (0.5, 0.9)))

    def test_touching(self):
        self.assertTrue(od.cis_overlap((0.1, 0.5), (0.5, 0.9)))


class TestAnalyzeJournalTimePatterns(unittest.TestCase):
    """Test time pattern analysis on journal data."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({"version": 1, "updated_at": "2026-03-19T00:00:00Z"}, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def _log_bet(self, hour, result="win", pnl=100):
        entry = {
            "timestamp": f"2026-03-19T{hour:02d}:30:00Z",
            "event_type": "bet_outcome",
            "domain": "trading",
            "metrics": {"result": result, "pnl_cents": pnl,
                        "strategy_name": "sniper", "market_type": "crypto_15m"},
            "strategy_version": "v1",
        }
        with open(journal.JOURNAL_PATH, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    def test_no_data_returns_no_data(self):
        result = od.analyze_journal_time_patterns()
        self.assertEqual(result["status"], "no_data")

    def test_basic_analysis(self):
        for _ in range(10):
            self._log_bet(3, "win", 100)
        for _ in range(10):
            self._log_bet(15, "win", 200)
        result = od.analyze_journal_time_patterns()
        self.assertEqual(result["status"], "analyzed")
        self.assertEqual(result["total_bets"], 20)

    def test_signals_on_degradation(self):
        # Overnight: all losses
        for _ in range(20):
            self._log_bet(2, "loss", -100)
        # Daytime: all wins
        for _ in range(20):
            self._log_bet(15, "win", 100)
        result = od.analyze_journal_time_patterns()
        actionable = [s for s in result["signals"] if s["severity"] == "actionable"]
        self.assertGreater(len(actionable), 0)

    def test_no_signal_when_similar_wr(self):
        for _ in range(15):
            self._log_bet(2, "win", 100)
        for _ in range(5):
            self._log_bet(3, "loss", -100)
        for _ in range(14):
            self._log_bet(15, "win", 100)
        for _ in range(6):
            self._log_bet(16, "loss", -100)
        result = od.analyze_journal_time_patterns()
        actionable = [s for s in result["signals"]
                      if s["type"] == "overnight_degradation"]
        self.assertEqual(len(actionable), 0)

    def test_negative_pnl_hour_detected(self):
        for _ in range(10):
            self._log_bet(3, "loss", -200)
        result = od.analyze_journal_time_patterns()
        neg_hours = [s for s in result["signals"] if s["type"] == "negative_pnl_hour"]
        self.assertGreater(len(neg_hours), 0)


class TestAuditDataTracking(unittest.TestCase):
    """Test data tracking completeness audit."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({"version": 1}, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_audit_returns_coverage(self):
        report = od.audit_data_tracking()
        self.assertIn("coverage_pct", report)
        self.assertIn("missing_fields", report)
        self.assertIn("tracked_fields", report)
        self.assertGreater(report["total_optimal_fields"], 0)

    def test_audit_identifies_critical_gaps(self):
        report = od.audit_data_tracking()
        critical = report["impact_assessment"]["critical"]["fields"]
        # These must be flagged as critical missing
        self.assertIn("hour_utc", critical)
        self.assertIn("is_overnight", critical)

    def test_audit_coverage_not_100(self):
        # Current schema doesn't cover everything
        report = od.audit_data_tracking()
        self.assertLess(report["coverage_pct"], 100)

    def test_audit_with_actual_entries(self):
        entry = {
            "timestamp": "2026-03-19T10:00:00Z",
            "event_type": "bet_outcome",
            "domain": "trading",
            "metrics": {"result": "win", "pnl_cents": 100,
                        "strategy_name": "sniper"},
        }
        with open(journal.JOURNAL_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
        report = od.audit_data_tracking()
        self.assertEqual(report["total_bet_entries"], 1)


class TestSQLTemplates(unittest.TestCase):
    """Test SQL template availability."""

    def test_templates_exist(self):
        self.assertIn("time_stratified_pnl", od.SQL_TEMPLATES)
        self.assertIn("hourly_breakdown", od.SQL_TEMPLATES)
        self.assertIn("strategy_by_time", od.SQL_TEMPLATES)
        self.assertIn("daily_pnl_trend", od.SQL_TEMPLATES)

    def test_templates_are_valid_sql(self):
        for name, sql in od.SQL_TEMPLATES.items():
            self.assertIn("SELECT", sql.upper(), f"{name} missing SELECT")
            self.assertIn("FROM", sql.upper(), f"{name} missing FROM")


class TestRecommendations(unittest.TestCase):
    """Test evidence-based recommendation generation."""

    def test_recs_from_actionable_signal(self):
        analysis = {
            "total_bets": 100,
            "signals": [{"type": "overnight_degradation", "severity": "actionable",
                         "detail": "test detail", "evidence": "test evidence"}],
        }
        audit = {"coverage_pct": 80, "impact_assessment": {
            "critical": {"fields": []}, "high": {"fields": []}, "medium": {"fields": []}
        }}
        recs = od.generate_recommendations(analysis, audit)
        high_recs = [r for r in recs if r["priority"] == "HIGH"]
        self.assertGreater(len(high_recs), 0)

    def test_recs_from_low_coverage(self):
        analysis = {"total_bets": 100, "signals": []}
        audit = {"coverage_pct": 30, "impact_assessment": {
            "critical": {"fields": ["hour_utc"]}, "high": {"fields": []},
            "medium": {"fields": []}
        }}
        recs = od.generate_recommendations(analysis, audit)
        infra_recs = [r for r in recs if r["type"] == "infrastructure"]
        self.assertGreater(len(infra_recs), 0)

    def test_recs_from_insufficient_data(self):
        analysis = {"total_bets": 10, "signals": []}
        audit = {"coverage_pct": 80, "impact_assessment": {
            "critical": {"fields": []}, "high": {"fields": []}, "medium": {"fields": []}
        }}
        recs = od.generate_recommendations(analysis, audit)
        data_recs = [r for r in recs if r["type"] == "data_collection"]
        self.assertGreater(len(data_recs), 0)

    def test_no_recs_when_clean(self):
        analysis = {"total_bets": 200, "signals": []}
        audit = {"coverage_pct": 90, "impact_assessment": {
            "critical": {"fields": []}, "high": {"fields": []}, "medium": {"fields": []}
        }}
        recs = od.generate_recommendations(analysis, audit)
        self.assertEqual(len(recs), 0)


if __name__ == "__main__":
    unittest.main()
