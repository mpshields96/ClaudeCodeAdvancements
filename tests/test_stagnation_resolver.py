"""
test_stagnation_resolver.py — Tests for stagnation_resolver.py

Formalizes decisions for stagnating MTs: archive, reduce priority, or schedule.
MT-18 (98 sessions untouched) and MT-13 (49 sessions) need resolution.

TDD: tests first.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestStagnationClassifier(unittest.TestCase):
    """Test classifying MTs by stagnation severity."""

    def test_not_stagnating(self):
        from stagnation_resolver import classify_stagnation
        result = classify_stagnation(sessions_untouched=2, completion_pct=50, base_value=7)
        self.assertEqual(result["severity"], "none")

    def test_mild_stagnation(self):
        from stagnation_resolver import classify_stagnation
        result = classify_stagnation(sessions_untouched=15, completion_pct=33, base_value=5)
        self.assertEqual(result["severity"], "mild")

    def test_moderate_stagnation(self):
        from stagnation_resolver import classify_stagnation
        result = classify_stagnation(sessions_untouched=30, completion_pct=0, base_value=4)
        self.assertEqual(result["severity"], "moderate")

    def test_severe_stagnation(self):
        from stagnation_resolver import classify_stagnation
        result = classify_stagnation(sessions_untouched=50, completion_pct=0, base_value=4)
        self.assertEqual(result["severity"], "severe")

    def test_critical_stagnation(self):
        from stagnation_resolver import classify_stagnation
        result = classify_stagnation(sessions_untouched=98, completion_pct=0, base_value=4)
        self.assertEqual(result["severity"], "critical")

    def test_high_value_resists_severity(self):
        """High base_value MTs get lower severity for same untouched count."""
        from stagnation_resolver import classify_stagnation
        low_val = classify_stagnation(sessions_untouched=30, completion_pct=0, base_value=3)
        high_val = classify_stagnation(sessions_untouched=30, completion_pct=0, base_value=8)
        # High value should be less severe
        severity_order = ["none", "mild", "moderate", "severe", "critical"]
        self.assertGreaterEqual(
            severity_order.index(low_val["severity"]),
            severity_order.index(high_val["severity"]),
        )

    def test_partial_completion_resists_severity(self):
        """Started MTs (some completion) get lower severity."""
        from stagnation_resolver import classify_stagnation
        not_started = classify_stagnation(sessions_untouched=40, completion_pct=0, base_value=5)
        partial = classify_stagnation(sessions_untouched=40, completion_pct=50, base_value=5)
        severity_order = ["none", "mild", "moderate", "severe", "critical"]
        self.assertGreaterEqual(
            severity_order.index(not_started["severity"]),
            severity_order.index(partial["severity"]),
        )


class TestRecommendAction(unittest.TestCase):
    """Test action recommendations for stagnating MTs."""

    def test_none_severity_no_action(self):
        from stagnation_resolver import recommend_action
        result = recommend_action("MT-22", "none", sessions_untouched=2, completion_pct=67)
        self.assertEqual(result["action"], "none")

    def test_mild_reduce_priority(self):
        from stagnation_resolver import recommend_action
        result = recommend_action("MT-13", "mild", sessions_untouched=15, completion_pct=0)
        self.assertIn(result["action"], ["reduce_priority", "schedule"])

    def test_moderate_schedule_or_reduce(self):
        from stagnation_resolver import recommend_action
        result = recommend_action("MT-13", "moderate", sessions_untouched=30, completion_pct=0)
        self.assertIn(result["action"], ["reduce_priority", "schedule", "archive"])

    def test_severe_archive_recommended(self):
        from stagnation_resolver import recommend_action
        result = recommend_action("MT-13", "severe", sessions_untouched=50, completion_pct=0)
        self.assertIn(result["action"], ["archive", "reduce_priority"])

    def test_critical_archive_strongly(self):
        from stagnation_resolver import recommend_action
        result = recommend_action("MT-18", "critical", sessions_untouched=98, completion_pct=0)
        self.assertEqual(result["action"], "archive")
        self.assertIn("98 sessions", result["reason"])

    def test_partial_completion_prefers_schedule(self):
        """If MT is 50%+ done, prefer scheduling over archiving."""
        from stagnation_resolver import recommend_action
        result = recommend_action("MT-X", "moderate", sessions_untouched=30, completion_pct=60)
        self.assertIn(result["action"], ["schedule", "reduce_priority"])
        self.assertNotEqual(result["action"], "archive")

    def test_recommendation_has_reason(self):
        from stagnation_resolver import recommend_action
        result = recommend_action("MT-18", "critical", sessions_untouched=98, completion_pct=0)
        self.assertTrue(len(result["reason"]) > 0)


class TestResolutionRecord(unittest.TestCase):
    """Test recording stagnation resolution decisions."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_file = Path(self.tmpdir) / "stagnation_log.jsonl"

    def tearDown(self):
        if self.log_file.exists():
            self.log_file.unlink()
        os.rmdir(self.tmpdir)

    def test_record_decision(self):
        from stagnation_resolver import record_decision
        record_decision(
            mt_id="MT-18",
            action="archive",
            reason="98 sessions untouched, 0% complete, base_value 4",
            log_file=self.log_file,
        )
        self.assertTrue(self.log_file.exists())
        lines = self.log_file.read_text().strip().split("\n")
        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0])
        self.assertEqual(data["mt_id"], "MT-18")
        self.assertEqual(data["action"], "archive")

    def test_record_multiple(self):
        from stagnation_resolver import record_decision
        record_decision("MT-18", "archive", "too old", log_file=self.log_file)
        record_decision("MT-13", "reduce_priority", "low value", log_file=self.log_file)
        lines = self.log_file.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)

    def test_load_decisions(self):
        from stagnation_resolver import record_decision, load_decisions
        record_decision("MT-18", "archive", "too old", log_file=self.log_file)
        decisions = load_decisions(log_file=self.log_file)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["mt_id"], "MT-18")

    def test_load_empty(self):
        from stagnation_resolver import load_decisions
        decisions = load_decisions(log_file=self.log_file)
        self.assertEqual(decisions, [])


class TestBatchAnalysis(unittest.TestCase):
    """Test analyzing multiple stagnating MTs at once."""

    def test_analyze_batch(self):
        from stagnation_resolver import analyze_batch
        mts = [
            {"mt_id": "MT-18", "sessions_untouched": 98, "completion_pct": 0, "base_value": 4},
            {"mt_id": "MT-13", "sessions_untouched": 49, "completion_pct": 0, "base_value": 4},
            {"mt_id": "MT-22", "sessions_untouched": 2, "completion_pct": 67, "base_value": 9},
        ]
        results = analyze_batch(mts)
        self.assertEqual(len(results), 3)
        # MT-22 should have no action
        mt22 = next(r for r in results if r["mt_id"] == "MT-22")
        self.assertEqual(mt22["action"], "none")
        # MT-18 should recommend archive
        mt18 = next(r for r in results if r["mt_id"] == "MT-18")
        self.assertEqual(mt18["action"], "archive")

    def test_analyze_empty(self):
        from stagnation_resolver import analyze_batch
        results = analyze_batch([])
        self.assertEqual(results, [])

    def test_format_report(self):
        from stagnation_resolver import format_report
        results = [
            {"mt_id": "MT-18", "severity": "critical", "action": "archive",
             "reason": "98 sessions untouched"},
            {"mt_id": "MT-13", "severity": "severe", "action": "reduce_priority",
             "reason": "49 sessions untouched"},
        ]
        report = format_report(results)
        self.assertIn("MT-18", report)
        self.assertIn("archive", report.lower())
        self.assertIn("MT-13", report)


class TestEdgeCases(unittest.TestCase):
    """Edge cases."""

    def test_zero_sessions_untouched(self):
        from stagnation_resolver import classify_stagnation
        result = classify_stagnation(sessions_untouched=0, completion_pct=50, base_value=7)
        self.assertEqual(result["severity"], "none")

    def test_negative_sessions_untouched(self):
        from stagnation_resolver import classify_stagnation
        result = classify_stagnation(sessions_untouched=-1, completion_pct=50, base_value=7)
        self.assertEqual(result["severity"], "none")

    def test_100_percent_completion(self):
        from stagnation_resolver import classify_stagnation
        result = classify_stagnation(sessions_untouched=20, completion_pct=100, base_value=5)
        self.assertEqual(result["severity"], "none")

    def test_zero_base_value(self):
        from stagnation_resolver import classify_stagnation
        result = classify_stagnation(sessions_untouched=20, completion_pct=0, base_value=0)
        # Zero value task stagnating = should be severe faster
        severity_order = ["none", "mild", "moderate", "severe", "critical"]
        self.assertGreaterEqual(severity_order.index(result["severity"]), 2)


if __name__ == "__main__":
    unittest.main()
