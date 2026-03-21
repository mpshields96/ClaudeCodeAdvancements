"""
test_confidence_calibrator.py — Tests for confidence_calibrator.py

Implements methodology from ConfTuner (arXiv, Li et al. 2025):
verbal confidence calibration for LLM outputs. Adapted for CCA's
use case — no fine-tuning, just prompt-based confidence extraction
+ historical calibration tracking.

TDD: tests written first, implementation follows.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "self-learning"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestConfidenceExtraction(unittest.TestCase):
    """Test extracting confidence scores from LLM text responses."""

    def test_extract_numeric_confidence(self):
        from confidence_calibrator import extract_confidence
        text = "I am 85% confident that this code has a bug in the loop."
        result = extract_confidence(text)
        self.assertAlmostEqual(result, 0.85, places=2)

    def test_extract_fraction_confidence(self):
        from confidence_calibrator import extract_confidence
        text = "Confidence: 7/10. The function handles edge cases."
        result = extract_confidence(text)
        self.assertAlmostEqual(result, 0.70, places=2)

    def test_extract_decimal_confidence(self):
        from confidence_calibrator import extract_confidence
        text = "Confidence: 0.92. This approach is correct."
        result = extract_confidence(text)
        self.assertAlmostEqual(result, 0.92, places=2)

    def test_extract_word_high(self):
        from confidence_calibrator import extract_confidence
        text = "I am highly confident this is the right approach."
        result = extract_confidence(text)
        self.assertGreaterEqual(result, 0.8)

    def test_extract_word_low(self):
        from confidence_calibrator import extract_confidence
        text = "I have low confidence in this assessment."
        result = extract_confidence(text)
        self.assertLessEqual(result, 0.4)

    def test_extract_word_moderate(self):
        from confidence_calibrator import extract_confidence
        text = "I am moderately confident about this finding."
        result = extract_confidence(text)
        self.assertTrue(0.4 <= result <= 0.7)

    def test_no_confidence_returns_none(self):
        from confidence_calibrator import extract_confidence
        text = "The function returns a list of integers."
        result = extract_confidence(text)
        self.assertIsNone(result)

    def test_extract_confidence_label_format(self):
        from confidence_calibrator import extract_confidence
        text = "[Confidence: HIGH] The architecture is sound."
        result = extract_confidence(text)
        self.assertGreaterEqual(result, 0.8)

    def test_percentage_without_percent_sign(self):
        from confidence_calibrator import extract_confidence
        text = "Confidence level: 65 out of 100."
        result = extract_confidence(text)
        self.assertAlmostEqual(result, 0.65, places=2)


class TestPredictionLogging(unittest.TestCase):
    """Test logging predictions with confidence for later calibration."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = Path(self.tmpdir) / "predictions.jsonl"

    def test_log_prediction(self):
        from confidence_calibrator import PredictionLog
        log = PredictionLog(self.log_path)
        pid = log.log_prediction(
            source="senior_dev",
            prediction="Bug in loop at line 42",
            confidence=0.85,
            context={"file": "main.py", "line": 42},
        )
        self.assertTrue(pid.startswith("pred_"))
        self.assertTrue(self.log_path.exists())

    def test_log_prediction_has_timestamp(self):
        from confidence_calibrator import PredictionLog
        log = PredictionLog(self.log_path)
        log.log_prediction("test", "something", 0.5)
        with open(self.log_path) as f:
            entry = json.loads(f.readline())
        self.assertIn("timestamp", entry)

    def test_log_prediction_has_id(self):
        from confidence_calibrator import PredictionLog
        log = PredictionLog(self.log_path)
        pid = log.log_prediction("test", "something", 0.5)
        with open(self.log_path) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["prediction_id"], pid)

    def test_confidence_clamped_to_0_1(self):
        from confidence_calibrator import PredictionLog
        log = PredictionLog(self.log_path)
        log.log_prediction("test", "high", 1.5)
        log.log_prediction("test", "low", -0.3)
        entries = []
        with open(self.log_path) as f:
            for line in f:
                entries.append(json.loads(line))
        self.assertEqual(entries[0]["confidence"], 1.0)
        self.assertEqual(entries[1]["confidence"], 0.0)

    def test_record_outcome(self):
        from confidence_calibrator import PredictionLog
        log = PredictionLog(self.log_path)
        pid = log.log_prediction("test", "will pass", 0.9)
        log.record_outcome(pid, correct=True, notes="Test passed")
        entries = []
        with open(self.log_path) as f:
            for line in f:
                entries.append(json.loads(line))
        # Should have prediction + outcome
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["type"], "outcome")
        self.assertTrue(entries[1]["correct"])

    def test_record_outcome_unknown_id_raises(self):
        from confidence_calibrator import PredictionLog
        log = PredictionLog(self.log_path)
        with self.assertRaises(ValueError):
            log.record_outcome("pred_nonexistent", correct=True)

    def test_multiple_predictions(self):
        from confidence_calibrator import PredictionLog
        log = PredictionLog(self.log_path)
        ids = []
        for i in range(5):
            pid = log.log_prediction("test", f"pred_{i}", 0.5 + i * 0.1)
            ids.append(pid)
        self.assertEqual(len(set(ids)), 5)  # All unique


class TestCalibrationMetrics(unittest.TestCase):
    """Test calibration computation from prediction+outcome data."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = Path(self.tmpdir) / "predictions.jsonl"

    def _make_log_with_outcomes(self, pairs):
        """Helper: create a log with (confidence, correct) pairs."""
        from confidence_calibrator import PredictionLog
        log = PredictionLog(self.log_path)
        for conf, correct in pairs:
            pid = log.log_prediction("test", "pred", conf)
            log.record_outcome(pid, correct=correct)
        return log

    def test_perfect_calibration(self):
        from confidence_calibrator import CalibrationMetrics
        # 80% confident, 80% correct = perfectly calibrated
        log = self._make_log_with_outcomes(
            [(0.8, True)] * 8 + [(0.8, False)] * 2
        )
        metrics = CalibrationMetrics(self.log_path)
        result = metrics.compute()
        # ECE should be near 0 for perfect calibration
        self.assertLess(result["ece"], 0.1)

    def test_overconfident_detection(self):
        from confidence_calibrator import CalibrationMetrics
        # 90% confident but only 50% correct = overconfident
        log = self._make_log_with_outcomes(
            [(0.9, True)] * 5 + [(0.9, False)] * 5
        )
        metrics = CalibrationMetrics(self.log_path)
        result = metrics.compute()
        self.assertGreater(result["ece"], 0.2)
        self.assertEqual(result["bias"], "overconfident")

    def test_underconfident_detection(self):
        from confidence_calibrator import CalibrationMetrics
        # 30% confident but 80% correct = underconfident
        log = self._make_log_with_outcomes(
            [(0.3, True)] * 8 + [(0.3, False)] * 2
        )
        metrics = CalibrationMetrics(self.log_path)
        result = metrics.compute()
        self.assertEqual(result["bias"], "underconfident")

    def test_no_outcomes_returns_empty(self):
        from confidence_calibrator import CalibrationMetrics
        from confidence_calibrator import PredictionLog
        log = PredictionLog(self.log_path)
        log.log_prediction("test", "pred", 0.7)  # No outcome
        metrics = CalibrationMetrics(self.log_path)
        result = metrics.compute()
        self.assertEqual(result["total_predictions"], 0)

    def test_calibration_by_source(self):
        from confidence_calibrator import CalibrationMetrics, PredictionLog
        log = PredictionLog(self.log_path)
        # Senior dev: well-calibrated
        for _ in range(5):
            pid = log.log_prediction("senior_dev", "finding", 0.8)
            log.record_outcome(pid, correct=True)
        # Paper scorer: overconfident
        for _ in range(5):
            pid = log.log_prediction("paper_scorer", "score", 0.9)
            log.record_outcome(pid, correct=False)

        metrics = CalibrationMetrics(self.log_path)
        by_source = metrics.compute_by_source()
        self.assertIn("senior_dev", by_source)
        self.assertIn("paper_scorer", by_source)

    def test_calibration_bins(self):
        from confidence_calibrator import CalibrationMetrics
        log = self._make_log_with_outcomes(
            [(0.1, False)] * 3 + [(0.5, True)] * 3 + [(0.9, True)] * 3 + [(0.9, False)] * 1
        )
        metrics = CalibrationMetrics(self.log_path)
        result = metrics.compute()
        self.assertIn("bins", result)
        self.assertGreater(len(result["bins"]), 0)

    def test_total_predictions_count(self):
        from confidence_calibrator import CalibrationMetrics
        log = self._make_log_with_outcomes(
            [(0.7, True)] * 10
        )
        metrics = CalibrationMetrics(self.log_path)
        result = metrics.compute()
        self.assertEqual(result["total_predictions"], 10)


class TestConfidenceAdjuster(unittest.TestCase):
    """Test adjusting raw confidence based on historical calibration."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = Path(self.tmpdir) / "predictions.jsonl"

    def test_adjust_overconfident_source(self):
        from confidence_calibrator import PredictionLog, ConfidenceAdjuster
        log = PredictionLog(self.log_path)
        # Source is 90% confident but only 50% correct
        for _ in range(10):
            pid = log.log_prediction("buggy_source", "pred", 0.9)
            log.record_outcome(pid, correct=(_ < 5))

        adjuster = ConfidenceAdjuster(self.log_path)
        adjusted = adjuster.adjust("buggy_source", 0.9)
        self.assertLess(adjusted, 0.9)

    def test_adjust_well_calibrated_stays_similar(self):
        from confidence_calibrator import PredictionLog, ConfidenceAdjuster
        log = PredictionLog(self.log_path)
        # Source is 80% confident and ~80% correct
        for i in range(10):
            pid = log.log_prediction("good_source", "pred", 0.8)
            log.record_outcome(pid, correct=(i < 8))

        adjuster = ConfidenceAdjuster(self.log_path)
        adjusted = adjuster.adjust("good_source", 0.8)
        self.assertAlmostEqual(adjusted, 0.8, delta=0.15)

    def test_adjust_unknown_source_returns_raw(self):
        from confidence_calibrator import ConfidenceAdjuster
        adjuster = ConfidenceAdjuster(self.log_path)
        adjusted = adjuster.adjust("unknown_source", 0.75)
        self.assertEqual(adjusted, 0.75)

    def test_adjust_too_few_samples_returns_raw(self):
        from confidence_calibrator import PredictionLog, ConfidenceAdjuster
        log = PredictionLog(self.log_path)
        # Only 2 samples — not enough for calibration
        for _ in range(2):
            pid = log.log_prediction("sparse_source", "pred", 0.9)
            log.record_outcome(pid, correct=True)

        adjuster = ConfidenceAdjuster(self.log_path, min_samples=5)
        adjusted = adjuster.adjust("sparse_source", 0.9)
        self.assertEqual(adjusted, 0.9)  # Raw, not adjusted


class TestCLI(unittest.TestCase):
    """Test CLI interface."""

    def test_module_has_main(self):
        import confidence_calibrator
        self.assertTrue(hasattr(confidence_calibrator, 'main'))

    def test_extract_subcommand(self):
        from confidence_calibrator import extract_confidence
        # Should not crash
        result = extract_confidence("I am 70% confident.")
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
