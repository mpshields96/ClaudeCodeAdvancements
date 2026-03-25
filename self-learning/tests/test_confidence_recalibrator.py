"""
test_confidence_recalibrator.py — MT-49 Phase 4: Confidence recalibration tests.

TDD: tests written first, implementation follows.

Tests Bayesian decay/boost on principle scores based on staleness
and prediction accuracy.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_principle(pid="prin_test1234", text="Test principle",
                    source_domain="cca_operations",
                    success_count=5, usage_count=10,
                    last_used_session=100, created_session=80,
                    updated_at=None, pruned=False):
    """Helper to create a principle dict for JSONL."""
    if updated_at is None:
        updated_at = datetime.now(timezone.utc).isoformat()
    return {
        "id": pid,
        "text": text,
        "source_domain": source_domain,
        "applicable_domains": [source_domain],
        "success_count": success_count,
        "usage_count": usage_count,
        "created_session": created_session,
        "last_used_session": last_used_session,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": updated_at,
        "pruned": pruned,
        "source_context": "test",
        "score": round((success_count + 1) / (usage_count + 2), 4),
    }


def _write_principles(path, principles):
    with open(path, "w") as f:
        for p in principles:
            f.write(json.dumps(p) + "\n")


class TestStalenessCalculation(unittest.TestCase):
    """Test staleness scoring based on session gap."""

    def test_recent_principle_low_staleness(self):
        from confidence_recalibrator import staleness_factor
        # Used 2 sessions ago — very fresh
        factor = staleness_factor(last_used_session=170, current_session=172)
        self.assertGreaterEqual(factor, 0.95)

    def test_old_principle_high_staleness(self):
        from confidence_recalibrator import staleness_factor
        # Used 50 sessions ago — very stale
        factor = staleness_factor(last_used_session=120, current_session=172)
        self.assertLess(factor, 0.8)

    def test_very_old_principle_floors(self):
        from confidence_recalibrator import staleness_factor
        # Used 200 sessions ago — floor should apply
        factor = staleness_factor(last_used_session=1, current_session=172)
        self.assertGreater(factor, 0.0)
        self.assertLessEqual(factor, 1.0)

    def test_never_used_principle(self):
        from confidence_recalibrator import staleness_factor
        # Session 0 means never used
        factor = staleness_factor(last_used_session=0, current_session=172)
        self.assertGreater(factor, 0.0)

    def test_same_session_no_decay(self):
        from confidence_recalibrator import staleness_factor
        factor = staleness_factor(last_used_session=172, current_session=172)
        self.assertAlmostEqual(factor, 1.0, places=2)


class TestRecalibratedScore(unittest.TestCase):
    """Test the recalibrated score computation."""

    def test_fresh_high_success_stays_high(self):
        from confidence_recalibrator import recalibrated_score
        # Fresh principle with good track record
        score = recalibrated_score(
            success_count=9, usage_count=10,
            last_used_session=170, current_session=172
        )
        self.assertGreater(score, 0.7)

    def test_stale_high_success_decays(self):
        from confidence_recalibrator import recalibrated_score
        # Same success rate but very stale
        score = recalibrated_score(
            success_count=9, usage_count=10,
            last_used_session=50, current_session=172
        )
        # Should be lower than a fresh one
        fresh_score = recalibrated_score(
            success_count=9, usage_count=10,
            last_used_session=170, current_session=172
        )
        self.assertLess(score, fresh_score)

    def test_low_usage_conservative(self):
        from confidence_recalibrator import recalibrated_score
        # Very few usages — Laplace smoothing dominates
        score = recalibrated_score(
            success_count=1, usage_count=1,
            last_used_session=170, current_session=172
        )
        # Should be moderate (Laplace: (1+1)/(1+2) = 0.667)
        self.assertGreater(score, 0.4)
        self.assertLess(score, 0.8)

    def test_score_bounded_0_1(self):
        from confidence_recalibrator import recalibrated_score
        score = recalibrated_score(
            success_count=0, usage_count=100,
            last_used_session=1, current_session=172
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestRecalibrateAll(unittest.TestCase):
    """Test batch recalibration of all principles."""

    def test_recalibrate_returns_results(self):
        from confidence_recalibrator import recalibrate_all
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            p1 = _make_principle("prin_aaa11111", success_count=8, usage_count=10,
                                 last_used_session=170)
            p2 = _make_principle("prin_bbb22222", success_count=2, usage_count=10,
                                 last_used_session=50)
            _write_principles(f.name, [p1, p2])
            path = f.name
        try:
            results = recalibrate_all(path, current_session=172)
            self.assertEqual(len(results), 2)
            self.assertIn("prin_aaa11111", results)
            self.assertIn("prin_bbb22222", results)
        finally:
            os.unlink(path)

    def test_recalibrate_returns_original_and_adjusted(self):
        from confidence_recalibrator import recalibrate_all
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            p1 = _make_principle("prin_ccc33333", success_count=5, usage_count=10,
                                 last_used_session=100)
            _write_principles(f.name, [p1])
            path = f.name
        try:
            results = recalibrate_all(path, current_session=172)
            entry = results["prin_ccc33333"]
            self.assertIn("original_score", entry)
            self.assertIn("recalibrated_score", entry)
            self.assertIn("staleness_factor", entry)
        finally:
            os.unlink(path)

    def test_skips_pruned_principles(self):
        from confidence_recalibrator import recalibrate_all
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            p1 = _make_principle("prin_ddd44444", pruned=True)
            _write_principles(f.name, [p1])
            path = f.name
        try:
            results = recalibrate_all(path, current_session=172)
            self.assertEqual(len(results), 0)
        finally:
            os.unlink(path)

    def test_empty_file(self):
        from confidence_recalibrator import recalibrate_all
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            results = recalibrate_all(path, current_session=172)
            self.assertEqual(len(results), 0)
        finally:
            os.unlink(path)


class TestDecayBoostCategories(unittest.TestCase):
    """Test categorization of principles into decay/stable/boost."""

    def test_categorize_decay(self):
        from confidence_recalibrator import categorize_change
        # Score dropped significantly
        cat = categorize_change(original=0.8, recalibrated=0.55)
        self.assertEqual(cat, "decay")

    def test_categorize_boost(self):
        from confidence_recalibrator import categorize_change
        # Fresh and high — stays high
        cat = categorize_change(original=0.7, recalibrated=0.72)
        self.assertEqual(cat, "stable")

    def test_categorize_stable(self):
        from confidence_recalibrator import categorize_change
        cat = categorize_change(original=0.6, recalibrated=0.58)
        self.assertEqual(cat, "stable")

    def test_big_decay(self):
        from confidence_recalibrator import categorize_change
        cat = categorize_change(original=0.8, recalibrated=0.4)
        self.assertEqual(cat, "decay")


class TestRecalibrationSummary(unittest.TestCase):
    """Test the summary output."""

    def test_summary_counts(self):
        from confidence_recalibrator import recalibration_summary
        results = {
            "a": {"original_score": 0.8, "recalibrated_score": 0.5, "staleness_factor": 0.6},
            "b": {"original_score": 0.6, "recalibrated_score": 0.58, "staleness_factor": 0.95},
            "c": {"original_score": 0.7, "recalibrated_score": 0.68, "staleness_factor": 0.97},
        }
        summary = recalibration_summary(results)
        self.assertIn("total", summary)
        self.assertEqual(summary["total"], 3)
        self.assertIn("decayed", summary)
        self.assertIn("stable", summary)

    def test_summary_empty(self):
        from confidence_recalibrator import recalibration_summary
        summary = recalibration_summary({})
        self.assertEqual(summary["total"], 0)


class TestFormatReport(unittest.TestCase):
    """Test human-readable report formatting."""

    def test_format_includes_counts(self):
        from confidence_recalibrator import format_report
        results = {
            "prin_a": {"original_score": 0.8, "recalibrated_score": 0.5,
                       "staleness_factor": 0.6, "text": "Principle A",
                       "last_used_session": 50},
        }
        text = format_report(results, current_session=172)
        self.assertIn("1 principle", text.lower())

    def test_format_shows_decayed(self):
        from confidence_recalibrator import format_report
        results = {
            "prin_a": {"original_score": 0.8, "recalibrated_score": 0.5,
                       "staleness_factor": 0.6, "text": "Principle A",
                       "last_used_session": 50},
        }
        text = format_report(results, current_session=172)
        self.assertIn("decay", text.lower())

    def test_format_empty(self):
        from confidence_recalibrator import format_report
        text = format_report({}, current_session=172)
        self.assertIn("0", text)


if __name__ == "__main__":
    unittest.main()
