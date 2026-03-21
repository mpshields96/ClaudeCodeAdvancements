#!/usr/bin/env python3
"""Extended edge-case tests for stagnation_resolver.py.

Targets: very high base_value (10) interactions, completion_pct==50 boundary,
batch with all same severity, format_report with empty reasons, log_file
permission errors.

Complements tests/test_stagnation_resolver.py (28 tests — base coverage).
"""

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from stagnation_resolver import (
    classify_stagnation, recommend_action, record_decision,
    load_decisions, analyze_batch, format_report,
)


# ---------------------------------------------------------------------------
# Very high base_value (10) — value_factor cap behavior
# ---------------------------------------------------------------------------

class TestHighBaseValueClassification(unittest.TestCase):
    """base_value=10 triggers the max value_factor=2.0 cap."""

    def test_base_value_10_value_factor_caps_at_2(self):
        """base=10 and base=20 produce the same severity — both hit the 2.0 cap."""
        # value_factor = min(2.0, base/5). base=10 → 2.0, base=20 → also 2.0
        result_10 = classify_stagnation(sessions_untouched=100, completion_pct=0, base_value=10)
        result_20 = classify_stagnation(sessions_untouched=100, completion_pct=0, base_value=20)
        self.assertEqual(result_10["severity"], result_20["severity"])

    def test_base_value_10_resists_severity_vs_low_value(self):
        """base=10 (2x patience) vs base=1 (0.5x patience) at same session count."""
        # base=1: value_factor=max(0.5, 0.2)=0.5, adjusted=98/0.5=196 → CRITICAL
        # base=10: value_factor=2.0, adjusted=98/2.0=49 → SEVERE
        low = classify_stagnation(sessions_untouched=98, completion_pct=0, base_value=1)
        high = classify_stagnation(sessions_untouched=98, completion_pct=0, base_value=10)
        severity_order = ["none", "mild", "moderate", "severe", "critical"]
        self.assertGreater(severity_order.index(low["severity"]),
                           severity_order.index(high["severity"]))

    def test_base_value_10_at_98_sessions_is_severe(self):
        """98 sessions, base=10 → adjusted=49 → SEVERE (not CRITICAL yet)."""
        # adjusted = 98 / (2.0 * 1.0) = 49.0 → SEVERE (40 <= 49 < 75)
        result = classify_stagnation(sessions_untouched=98, completion_pct=0, base_value=10)
        self.assertEqual(result["severity"], "severe")

    def test_base_value_10_at_150_sessions_is_critical(self):
        """150 sessions, base=10 → adjusted=75 → CRITICAL (>=75 threshold)."""
        # adjusted = 150 / (2.0 * 1.0) = 75.0 → CRITICAL
        result = classify_stagnation(sessions_untouched=150, completion_pct=0, base_value=10)
        self.assertEqual(result["severity"], "critical")

    def test_base_value_10_score_field_is_numeric(self):
        """classify_stagnation always returns a numeric score."""
        result = classify_stagnation(sessions_untouched=98, completion_pct=0, base_value=10)
        self.assertIsInstance(result["score"], (int, float))
        self.assertGreater(result["score"], 0)

    def test_high_base_critical_with_50pct_done_schedules(self):
        """Critical severity + 50% completion → schedule, not archive (even with base=10)."""
        result = recommend_action("MT-X", "critical", sessions_untouched=150, completion_pct=50)
        self.assertEqual(result["action"], "schedule")


# ---------------------------------------------------------------------------
# completion_pct exactly at 50% boundary
# ---------------------------------------------------------------------------

class TestCompletionBoundary(unittest.TestCase):
    """50% completion is a bifurcation point for both classification and recommendation."""

    def test_classify_at_50_percent_uses_1_5_factor(self):
        """50% completion → completion_factor=1.5 (more patient than 49%)."""
        # 49%: factor=1.2 → adjusted=30/(1.0*1.2)=25 → might be mild or moderate
        # 50%: factor=1.5 → adjusted=30/(1.0*1.5)=20 → might be mild or none
        at_50 = classify_stagnation(sessions_untouched=30, completion_pct=50, base_value=5)
        under_50 = classify_stagnation(sessions_untouched=30, completion_pct=49, base_value=5)
        severity_order = ["none", "mild", "moderate", "severe", "critical"]
        # 50% must be at most as severe as 49%
        self.assertLessEqual(severity_order.index(at_50["severity"]),
                             severity_order.index(under_50["severity"]))

    def test_recommend_moderate_at_50pct_is_schedule(self):
        """Moderate severity + completion_pct==50 → schedule (>=50 threshold)."""
        result = recommend_action("MT-X", "moderate", sessions_untouched=30, completion_pct=50)
        self.assertEqual(result["action"], "schedule")

    def test_recommend_moderate_at_49pct_is_reduce_priority(self):
        """Moderate severity + completion_pct==49 → reduce_priority (below 50 threshold)."""
        result = recommend_action("MT-X", "moderate", sessions_untouched=30, completion_pct=49)
        self.assertEqual(result["action"], "reduce_priority")

    def test_recommend_severe_at_50pct_is_schedule(self):
        """Severe severity + 50% done → schedule, not archive."""
        result = recommend_action("MT-X", "severe", sessions_untouched=50, completion_pct=50)
        self.assertEqual(result["action"], "schedule")

    def test_recommend_severe_at_49pct_is_reduce_not_schedule(self):
        """Severe + 49% done: has_progress=True but <50 → reduce_priority."""
        result = recommend_action("MT-X", "severe", sessions_untouched=50, completion_pct=49)
        # has_progress=True, completion<50 → archive if not has_progress else reduce_priority
        self.assertEqual(result["action"], "reduce_priority")

    def test_recommend_critical_at_50pct_is_schedule(self):
        """Critical + 50% done → schedule (not archive)."""
        result = recommend_action("MT-X", "critical", sessions_untouched=100, completion_pct=50)
        self.assertEqual(result["action"], "schedule")
        self.assertIn("50", result["reason"])

    def test_recommend_critical_at_0pct_is_archive(self):
        """Critical + 0% done → archive (no progress)."""
        result = recommend_action("MT-X", "critical", sessions_untouched=100, completion_pct=0)
        self.assertEqual(result["action"], "archive")


# ---------------------------------------------------------------------------
# Batch with all same severity
# ---------------------------------------------------------------------------

class TestBatchSameSeverity(unittest.TestCase):
    """analyze_batch when all input MTs land on the same severity."""

    def test_batch_all_critical_returns_three(self):
        """All MTs with 200 sessions and low base → all critical."""
        mts = [
            {"mt_id": "MT-A", "sessions_untouched": 200, "completion_pct": 0, "base_value": 4},
            {"mt_id": "MT-B", "sessions_untouched": 180, "completion_pct": 0, "base_value": 4},
            {"mt_id": "MT-C", "sessions_untouched": 160, "completion_pct": 0, "base_value": 4},
        ]
        results = analyze_batch(mts)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(r["severity"], "critical")

    def test_batch_all_none_produces_no_action_report(self):
        """Non-stagnating MTs → format_report says no action required."""
        mts = [
            {"mt_id": "MT-A", "sessions_untouched": 1, "completion_pct": 67, "base_value": 9},
            {"mt_id": "MT-B", "sessions_untouched": 0, "completion_pct": 50, "base_value": 8},
        ]
        results = analyze_batch(mts)
        report = format_report(results)
        self.assertIn("No stagnating", report)

    def test_batch_all_moderate_all_in_report(self):
        """All moderate → both appear in the formatted report."""
        mts = [
            {"mt_id": "MT-A", "sessions_untouched": 30, "completion_pct": 0, "base_value": 5},
            {"mt_id": "MT-B", "sessions_untouched": 35, "completion_pct": 0, "base_value": 5},
        ]
        results = analyze_batch(mts)
        report = format_report(results)
        self.assertIn("MT-A", report)
        self.assertIn("MT-B", report)

    def test_batch_preserves_one_result_per_mt(self):
        """analyze_batch returns exactly one result per input MT."""
        mts = [
            {"mt_id": f"MT-{i}", "sessions_untouched": 50, "completion_pct": 0, "base_value": 4}
            for i in range(5)
        ]
        results = analyze_batch(mts)
        self.assertEqual(len(results), 5)
        result_ids = {r["mt_id"] for r in results}
        expected_ids = {m["mt_id"] for m in mts}
        self.assertEqual(result_ids, expected_ids)

    def test_batch_results_have_required_fields(self):
        """Every result from analyze_batch has severity, score, action, reason, mt_id."""
        mts = [{"mt_id": "MT-X", "sessions_untouched": 50, "completion_pct": 0, "base_value": 4}]
        results = analyze_batch(mts)
        r = results[0]
        for field in ("mt_id", "action", "reason", "severity", "score"):
            self.assertIn(field, r, f"Missing field: {field}")


# ---------------------------------------------------------------------------
# format_report edge cases — empty reasons, ordering, empty inputs
# ---------------------------------------------------------------------------

class TestFormatReportEdgeCases(unittest.TestCase):
    """format_report handles unusual inputs without crashing."""

    def test_format_empty_list_returns_message(self):
        report = format_report([])
        self.assertIn("No stagnating", report)

    def test_format_all_action_none_returns_message(self):
        results = [
            {"mt_id": "MT-X", "severity": "none", "action": "none", "reason": "Not stagnating"},
            {"mt_id": "MT-Y", "severity": "none", "action": "none", "reason": "Not stagnating"},
        ]
        report = format_report(results)
        self.assertIn("No stagnating", report)

    def test_format_report_empty_reason_does_not_crash(self):
        """Empty reason string produces 'Reason:' line without crashing."""
        results = [
            {"mt_id": "MT-A", "severity": "critical", "action": "archive", "reason": ""},
        ]
        report = format_report(results)
        self.assertIn("MT-A", report)
        self.assertIn("archive", report.lower())
        self.assertIn("Reason:", report)

    def test_format_report_critical_before_mild_in_output(self):
        """Critical appears before mild (reverse=True sort on severity index)."""
        results = [
            {"mt_id": "MT-MILD", "severity": "mild", "action": "reduce_priority", "reason": "mild"},
            {"mt_id": "MT-CRIT", "severity": "critical", "action": "archive", "reason": "critical"},
        ]
        report = format_report(results)
        crit_idx = report.index("MT-CRIT")
        mild_idx = report.index("MT-MILD")
        self.assertLess(crit_idx, mild_idx)

    def test_format_report_has_header(self):
        """Report includes 'Stagnation Report:' header when there are actionable items."""
        results = [
            {"mt_id": "MT-A", "severity": "severe", "action": "archive", "reason": "too long"},
        ]
        report = format_report(results)
        self.assertIn("Stagnation Report:", report)

    def test_format_report_mixed_action_none_filtered(self):
        """Results with action='none' are filtered from the report."""
        results = [
            {"mt_id": "MT-SKIP", "severity": "none", "action": "none", "reason": "ok"},
            {"mt_id": "MT-ACT", "severity": "moderate", "action": "reduce_priority", "reason": "stale"},
        ]
        report = format_report(results)
        self.assertIn("MT-ACT", report)
        self.assertNotIn("MT-SKIP", report)


# ---------------------------------------------------------------------------
# log_file edge cases — permission errors, malformed JSON, nested dirs
# ---------------------------------------------------------------------------

class TestLogFileEdgeCases(unittest.TestCase):
    """record_decision and load_decisions behavior with filesystem edge cases."""

    def test_record_decision_creates_nested_parent_dirs(self):
        """record_decision creates nested parent directories on demand."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "nested" / "dir" / "stagnation.jsonl"
            record_decision("MT-X", "archive", "test nested", log_file=log_file)
            self.assertTrue(log_file.exists())
            data = json.loads(log_file.read_text().strip())
            self.assertEqual(data["mt_id"], "MT-X")

    def test_record_decision_permission_error_on_readonly_file(self):
        """PermissionError propagates when log file exists but is read-only (0o444)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "stagnation.jsonl"
            log_file.write_text("")  # Create it first
            log_file.chmod(0o444)   # Make read-only
            try:
                with self.assertRaises((PermissionError, OSError)):
                    record_decision("MT-X", "archive", "test", log_file=log_file)
            finally:
                log_file.chmod(0o644)  # Restore so TemporaryDirectory cleanup works

    def test_load_decisions_ignores_malformed_json_lines(self):
        """load_decisions skips lines that fail JSON parsing without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "stagnation.jsonl"
            log_file.write_text(
                '{"mt_id": "MT-A", "action": "archive"}\n'
                'NOT VALID JSON AT ALL\n'
                '{"mt_id": "MT-B", "action": "schedule"}\n'
            )
            decisions = load_decisions(log_file=log_file)
            self.assertEqual(len(decisions), 2)
            ids = {d["mt_id"] for d in decisions}
            self.assertEqual(ids, {"MT-A", "MT-B"})

    def test_load_decisions_skips_empty_lines(self):
        """load_decisions skips blank lines in the JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "stagnation.jsonl"
            log_file.write_text('\n\n{"mt_id": "MT-A", "action": "archive"}\n\n')
            decisions = load_decisions(log_file=log_file)
            self.assertEqual(len(decisions), 1)
            self.assertEqual(decisions[0]["mt_id"], "MT-A")

    def test_record_then_load_roundtrip(self):
        """record_decision + load_decisions roundtrip preserves all fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "stagnation.jsonl"
            record_decision("MT-18", "archive", "98 sessions untouched", log_file=log_file)
            decisions = load_decisions(log_file=log_file)
            self.assertEqual(len(decisions), 1)
            d = decisions[0]
            self.assertEqual(d["mt_id"], "MT-18")
            self.assertEqual(d["action"], "archive")
            self.assertEqual(d["reason"], "98 sessions untouched")
            self.assertIn("timestamp", d)


if __name__ == "__main__":
    unittest.main()
