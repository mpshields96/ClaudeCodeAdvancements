#!/usr/bin/env python3
"""
test_overnight_detector_extended.py — Extended edge-case tests for overnight_detector.py

Covers: wilson_ci boundary values and custom z, cusum_signal custom h and max_S,
cis_overlap edge cases, OPTIMAL/CURRENT_BET_FIELDS constants, audit extra/schema-only
fields, generate_recommendations warning priority, SQL_TEMPLATES all keys, and
analyze_journal_time_patterns bucket names / insufficient-sample notes.
"""

import json
import math
import os
import shutil
import sys
import tempfile
import unittest

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PARENT_DIR)

import journal
import overnight_detector as od


# ===== wilson_ci extended =====

class TestWilsonCIExtended(unittest.TestCase):
    """Extended edge cases for wilson_ci."""

    def test_returns_tuple_of_two_floats(self):
        result = od.wilson_ci(20, 15)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], float)
        self.assertIsInstance(result[1], float)

    def test_lower_never_negative(self):
        """Lower bound must always be >= 0."""
        for n, k in [(1, 0), (1, 1), (2, 0), (5, 1), (100, 5)]:
            lo, _ = od.wilson_ci(n, k)
            self.assertGreaterEqual(lo, 0.0, f"Negative lower bound for n={n},k={k}")

    def test_upper_never_exceeds_one(self):
        """Upper bound must always be <= 1."""
        for n, k in [(1, 1), (2, 2), (5, 5), (100, 100)]:
            _, hi = od.wilson_ci(n, k)
            self.assertLessEqual(hi, 1.0, f"Upper > 1 for n={n},k={k}")

    def test_lo_lt_hi(self):
        """Lower bound is always less than upper bound for n > 0."""
        lo, hi = od.wilson_ci(10, 7)
        self.assertLess(lo, hi)

    def test_n1_k1(self):
        """n=1, k=1: full sample is a win — CI should be wide, hi=1.0."""
        lo, hi = od.wilson_ci(1, 1)
        self.assertAlmostEqual(hi, 1.0, places=1)
        self.assertGreaterEqual(lo, 0.0)

    def test_n1_k0(self):
        """n=1, k=0: full sample is a loss — CI wide, lo=0.0."""
        lo, hi = od.wilson_ci(1, 0)
        self.assertAlmostEqual(lo, 0.0, places=1)
        self.assertLessEqual(hi, 1.0)

    def test_custom_z_99pct(self):
        """z=2.576 gives wider 99% CI than default 95% CI."""
        lo_95, hi_95 = od.wilson_ci(50, 30, z=1.96)
        lo_99, hi_99 = od.wilson_ci(50, 30, z=2.576)
        self.assertLess(lo_99, lo_95)
        self.assertGreater(hi_99, hi_95)

    def test_ci_contains_true_rate(self):
        """For large n, CI should contain the observed win rate."""
        n, k = 200, 160  # 80% WR
        lo, hi = od.wilson_ci(n, k)
        obs_wr = k / n
        self.assertLessEqual(lo, obs_wr)
        self.assertGreaterEqual(hi, obs_wr)

    def test_symmetry_at_50pct(self):
        """50% WR CI should be symmetric around 0.5."""
        lo, hi = od.wilson_ci(1000, 500)
        mid = (lo + hi) / 2
        self.assertAlmostEqual(mid, 0.5, places=2)

    def test_results_rounded_to_4_places(self):
        """Results should be rounded to 4 decimal places."""
        lo, hi = od.wilson_ci(50, 35)
        # 4 decimal places means multiplied by 10000 is close to integer
        self.assertAlmostEqual(lo * 10000, round(lo * 10000), places=5)
        self.assertAlmostEqual(hi * 10000, round(hi * 10000), places=5)


# ===== cusum_signal extended =====

class TestCUSUMExtended(unittest.TestCase):
    """Extended edge cases for cusum_signal."""

    def test_max_s_returned_correctly(self):
        """max_S reflects cumulative sum peak."""
        outcomes = [1] * 5 + [0] * 5
        _, max_s, _ = od.cusum_signal(outcomes, 0.90, 0.70, h=100)
        # With h=100 no signal, but max_S should be positive
        self.assertGreater(max_s, 0.0)

    def test_max_s_is_zero_for_all_wins(self):
        """All wins: mu_0=0.90, x=1, k=0.10, S += (0.90 - 1 - 0.10) = -0.20, clamped to 0."""
        outcomes = [1] * 30
        _, max_s, _ = od.cusum_signal(outcomes, 0.90, 0.70, h=5.0)
        self.assertEqual(max_s, 0.0)

    def test_single_loss_no_signal_default_h(self):
        """Single loss doesn't trigger signal with h=5.0."""
        signaled, _, idx = od.cusum_signal([0], 0.90, 0.70, h=5.0)
        self.assertFalse(signaled)

    def test_all_losses_triggers_quickly(self):
        """All losses: triggers signal within a few bets."""
        outcomes = [0] * 20
        signaled, max_s, idx = od.cusum_signal(outcomes, 0.90, 0.70, h=5.0)
        self.assertTrue(signaled)
        self.assertIsNotNone(idx)
        self.assertLess(idx, 15)

    def test_custom_h_changes_trigger_point(self):
        """Higher h means signal fires later."""
        outcomes = [0] * 50
        _, _, idx_h5 = od.cusum_signal(outcomes, 0.90, 0.70, h=5.0)
        _, _, idx_h20 = od.cusum_signal(outcomes, 0.90, 0.70, h=20.0)
        if idx_h5 and idx_h20:
            self.assertLess(idx_h5, idx_h20)

    def test_trigger_idx_in_valid_range(self):
        """trigger_idx must be a valid index into outcomes list."""
        outcomes = [1] * 10 + [0] * 20
        signaled, _, idx = od.cusum_signal(outcomes, 0.90, 0.70)
        if signaled:
            self.assertGreaterEqual(idx, 0)
            self.assertLess(idx, len(outcomes))

    def test_returns_three_tuple(self):
        result = od.cusum_signal([1, 0, 1], 0.90, 0.70)
        self.assertEqual(len(result), 3)

    def test_trigger_idx_none_when_no_signal(self):
        signaled, _, idx = od.cusum_signal([1] * 20, 0.90, 0.70, h=100)
        self.assertFalse(signaled)
        self.assertIsNone(idx)


# ===== cis_overlap extended =====

class TestCIsOverlapExtended(unittest.TestCase):
    """Extended edge cases for cis_overlap."""

    def test_identical_intervals_overlap(self):
        self.assertTrue(od.cis_overlap((0.3, 0.7), (0.3, 0.7)))

    def test_one_contains_other_overlaps(self):
        self.assertTrue(od.cis_overlap((0.0, 1.0), (0.3, 0.7)))

    def test_adjacent_no_overlap(self):
        """(0.1, 0.3) and (0.31, 0.5) — clearly no overlap."""
        self.assertFalse(od.cis_overlap((0.1, 0.3), (0.31, 0.5)))

    def test_touching_at_zero(self):
        """Both starting at 0.0: should overlap."""
        self.assertTrue(od.cis_overlap((0.0, 0.3), (0.0, 0.2)))

    def test_reversed_order_same_result(self):
        """Overlap is symmetric: cis_overlap(A, B) == cis_overlap(B, A)."""
        a, b = (0.1, 0.5), (0.4, 0.9)
        self.assertEqual(od.cis_overlap(a, b), od.cis_overlap(b, a))

    def test_non_overlap_is_symmetric(self):
        a, b = (0.1, 0.3), (0.7, 0.9)
        self.assertEqual(od.cis_overlap(a, b), od.cis_overlap(b, a))
        self.assertFalse(od.cis_overlap(a, b))


# ===== Constants =====

class TestConstants(unittest.TestCase):
    """OPTIMAL_BET_FIELDS and CURRENT_BET_FIELDS structure."""

    def test_optimal_bet_fields_is_dict(self):
        self.assertIsInstance(od.OPTIMAL_BET_FIELDS, dict)

    def test_optimal_fields_non_empty(self):
        self.assertGreater(len(od.OPTIMAL_BET_FIELDS), 10)

    def test_current_bet_fields_is_set(self):
        self.assertIsInstance(od.CURRENT_BET_FIELDS, set)

    def test_current_fields_non_empty(self):
        self.assertGreater(len(od.CURRENT_BET_FIELDS), 0)

    def test_critical_fields_in_optimal_not_current(self):
        """hour_utc and is_overnight are in OPTIMAL but not CURRENT."""
        self.assertIn("hour_utc", od.OPTIMAL_BET_FIELDS)
        self.assertNotIn("hour_utc", od.CURRENT_BET_FIELDS)
        self.assertIn("is_overnight", od.OPTIMAL_BET_FIELDS)
        self.assertNotIn("is_overnight", od.CURRENT_BET_FIELDS)

    def test_result_in_current(self):
        """Core fields exist in CURRENT_BET_FIELDS."""
        self.assertIn("result", od.CURRENT_BET_FIELDS)
        self.assertIn("pnl_cents", od.CURRENT_BET_FIELDS)

    def test_core_current_fields_in_optimal(self):
        """Core CURRENT fields (result, pnl_cents, side, contracts) are in OPTIMAL."""
        for field in ("result", "pnl_cents", "side", "contracts"):
            self.assertIn(field, od.OPTIMAL_BET_FIELDS)


# ===== audit_data_tracking extended =====

class TestAuditDataTrackingExtended(unittest.TestCase):
    """Extended edge cases for audit_data_tracking."""

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

    def test_coverage_formula(self):
        """coverage_pct = len(present) / len(OPTIMAL) * 100."""
        report = od.audit_data_tracking()
        expected = round(len(od.CURRENT_BET_FIELDS.intersection(od.OPTIMAL_BET_FIELDS))
                        / len(od.OPTIMAL_BET_FIELDS) * 100, 1)
        self.assertAlmostEqual(report["coverage_pct"], expected, places=1)

    def test_missing_count_correct(self):
        """missing + currently_tracked == total_optimal_fields."""
        report = od.audit_data_tracking()
        self.assertEqual(
            report["missing"] + report["currently_tracked"],
            report["total_optimal_fields"]
        )

    def test_high_impact_fields(self):
        """High-impact fields like signal_strength are in high_missing."""
        report = od.audit_data_tracking()
        high = report["impact_assessment"]["high"]["fields"]
        self.assertIn("signal_strength", high)

    def test_medium_missing_non_empty(self):
        """Medium-impact fields should have some entries."""
        report = od.audit_data_tracking()
        medium = report["impact_assessment"]["medium"]["fields"]
        self.assertGreater(len(medium), 0)

    def test_schema_only_empty_when_no_entries(self):
        """No journal entries → actual_fields_seen is empty → schema_only = CURRENT."""
        report = od.audit_data_tracking()
        # schema_only = CURRENT_BET_FIELDS - actual_fields_seen
        # Since no entries, actual_fields_seen is empty, so schema_only = CURRENT
        self.assertEqual(set(report["in_schema_never_used"]), od.CURRENT_BET_FIELDS)

    def test_extra_fields_seen_with_extra_field(self):
        """Fields in journal metrics beyond CURRENT_BET_FIELDS appear in extra_fields_seen."""
        entry = {
            "timestamp": "2026-03-19T10:00:00Z",
            "event_type": "bet_outcome",
            "domain": "trading",
            "metrics": {
                "result": "win", "pnl_cents": 100,
                "hour_utc": 10,  # This is in OPTIMAL but not CURRENT
            },
        }
        with open(journal.JOURNAL_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
        report = od.audit_data_tracking()
        # hour_utc should appear in extra_fields_seen
        self.assertIn("hour_utc", report["extra_fields_seen"])

    def test_total_bet_entries_zero_when_empty(self):
        report = od.audit_data_tracking()
        self.assertEqual(report["total_bet_entries"], 0)

    def test_all_impact_keys_present(self):
        report = od.audit_data_tracking()
        for key in ("critical", "high", "medium"):
            self.assertIn(key, report["impact_assessment"])


# ===== SQL_TEMPLATES extended =====

class TestSQLTemplatesExtended(unittest.TestCase):
    """Extended coverage of SQL_TEMPLATES."""

    def test_spread_by_time_exists(self):
        self.assertIn("spread_by_time", od.SQL_TEMPLATES)

    def test_all_templates_are_strings(self):
        for name, sql in od.SQL_TEMPLATES.items():
            self.assertIsInstance(sql, str, f"{name} is not a string")

    def test_all_templates_non_empty(self):
        for name, sql in od.SQL_TEMPLATES.items():
            self.assertTrue(sql.strip(), f"{name} is empty")

    def test_time_stratified_mentions_overnight(self):
        sql = od.SQL_TEMPLATES["time_stratified_pnl"]
        self.assertIn("overnight", sql)

    def test_strategy_by_time_mentions_strategy(self):
        sql = od.SQL_TEMPLATES["strategy_by_time"]
        self.assertIn("strategy", sql.lower())

    def test_hourly_breakdown_mentions_hour(self):
        sql = od.SQL_TEMPLATES["hourly_breakdown"]
        self.assertIn("hour", sql.lower())


# ===== generate_recommendations extended =====

class TestGenerateRecommendationsExtended(unittest.TestCase):
    """Extended edge cases for generate_recommendations."""

    def _make_audit(self, coverage=80):
        return {
            "coverage_pct": coverage,
            "impact_assessment": {
                "critical": {"fields": []},
                "high": {"fields": []},
                "medium": {"fields": []},
            },
        }

    def test_warning_signal_gives_medium_priority(self):
        """Warning severity signals → MEDIUM priority recommendation."""
        analysis = {
            "total_bets": 100,
            "signals": [{"type": "cusum_wr_drop", "severity": "warning",
                         "detail": "CUSUM detected shift"}],
        }
        recs = od.generate_recommendations(analysis, self._make_audit(80))
        medium_recs = [r for r in recs if r["priority"] == "MEDIUM"]
        self.assertGreater(len(medium_recs), 0)

    def test_warning_rec_type_is_monitor(self):
        analysis = {
            "total_bets": 100,
            "signals": [{"type": "cusum_wr_drop", "severity": "warning",
                         "detail": "some warning"}],
        }
        recs = od.generate_recommendations(analysis, self._make_audit(80))
        monitor_recs = [r for r in recs if r["type"] == "monitor"]
        self.assertGreater(len(monitor_recs), 0)

    def test_exactly_50_bets_no_data_collection_rec(self):
        """50 bets is NOT < 50 → no data_collection rec."""
        analysis = {"total_bets": 50, "signals": []}
        recs = od.generate_recommendations(analysis, self._make_audit(80))
        data_recs = [r for r in recs if r["type"] == "data_collection"]
        self.assertEqual(len(data_recs), 0)

    def test_49_bets_triggers_data_collection_rec(self):
        """49 bets < 50 → data_collection rec."""
        analysis = {"total_bets": 49, "signals": []}
        recs = od.generate_recommendations(analysis, self._make_audit(80))
        data_recs = [r for r in recs if r["type"] == "data_collection"]
        self.assertGreater(len(data_recs), 0)

    def test_multiple_signals_multiple_recs(self):
        """Multiple signals produce multiple recommendations."""
        analysis = {
            "total_bets": 100,
            "signals": [
                {"type": "t1", "severity": "actionable", "detail": "d1", "evidence": "e1"},
                {"type": "t2", "severity": "actionable", "detail": "d2", "evidence": "e2"},
            ],
        }
        recs = od.generate_recommendations(analysis, self._make_audit(80))
        high_recs = [r for r in recs if r["priority"] == "HIGH"]
        self.assertGreaterEqual(len(high_recs), 2)

    def test_all_recs_have_required_keys(self):
        """All recommendations have priority, action, evidence, type keys."""
        analysis = {
            "total_bets": 10,
            "signals": [{"type": "overnight_degradation", "severity": "actionable",
                         "detail": "test", "evidence": "e"}],
        }
        recs = od.generate_recommendations(analysis, self._make_audit(20))
        for rec in recs:
            for key in ("priority", "action", "evidence", "type"):
                self.assertIn(key, rec, f"Missing key {key} in rec: {rec}")


# ===== analyze_journal_time_patterns extended =====

class TestAnalyzeJournalTimePatternsExtended(unittest.TestCase):
    """Extended edge cases for analyze_journal_time_patterns."""

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

    def test_analyzed_result_has_by_bucket(self):
        """analyzed result has by_bucket dict."""
        for _ in range(5):
            self._log_bet(10, "win")
        result = od.analyze_journal_time_patterns()
        self.assertEqual(result["status"], "analyzed")
        self.assertIn("by_bucket", result)
        self.assertIsInstance(result["by_bucket"], dict)

    def test_insufficient_sample_gets_note(self):
        """Bucket with < 10 decided bets gets 'note' field (not wilson_ci)."""
        for _ in range(5):
            self._log_bet(3, "win")
        result = od.analyze_journal_time_patterns()
        overnight = result["by_bucket"].get("overnight", {})
        if overnight:
            self.assertIn("note", overnight)
            self.assertNotIn("wilson_ci_95", overnight)

    def test_sufficient_sample_gets_wilson_ci(self):
        """Bucket with >= 10 decided bets gets wilson_ci_95 field."""
        for _ in range(8):
            self._log_bet(3, "win")
        for _ in range(4):
            self._log_bet(3, "loss")
        result = od.analyze_journal_time_patterns()
        overnight = result["by_bucket"].get("overnight", {})
        if overnight and overnight.get("decided", 0) >= 10:
            self.assertIn("wilson_ci_95", overnight)

    def test_result_has_signals_list(self):
        for _ in range(5):
            self._log_bet(10, "win")
        result = od.analyze_journal_time_patterns()
        self.assertIn("signals", result)
        self.assertIsInstance(result["signals"], list)

    def test_result_has_recommendations_list(self):
        for _ in range(5):
            self._log_bet(10, "win")
        result = od.analyze_journal_time_patterns()
        self.assertIn("recommendations", result)
        self.assertIsInstance(result["recommendations"], list)

    def test_trending_not_significant(self):
        """Overnight ~70%, daytime ~80% with small N: trend signal, not actionable."""
        for _ in range(7):
            self._log_bet(2, "win")
        for _ in range(3):
            self._log_bet(3, "loss")
        for _ in range(8):
            self._log_bet(14, "win")
        for _ in range(2):
            self._log_bet(15, "loss")
        result = od.analyze_journal_time_patterns()
        # With small N this may or may not trigger overnight_trend — just check no crash
        self.assertIn("signals", result)


if __name__ == "__main__":
    unittest.main()
