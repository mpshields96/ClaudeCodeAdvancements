#!/usr/bin/env python3
"""Tests for outcome_feedback.py — MT-28 Phase 4: Research Outcomes Feedback Loop.

Bridges research_outcomes.py (delivery tracking) with principle_registry.py
(principle scoring). When a research delivery produces profit/loss, the
principles that led to it get scored accordingly.

The closed loop:
  CCA delivers research → Kalshi implements → Outcome measured
  → Principles updated → Future research prioritization improves
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from outcome_feedback import (
    OutcomeFeedback,
    FeedbackEvent,
)
from research_outcomes import OutcomeTracker, Delivery
from principle_registry import Principle, _save_principle, _load_principles


class TestFeedbackEvent(unittest.TestCase):
    """Test FeedbackEvent data structure."""

    def test_create_event(self):
        event = FeedbackEvent(
            delivery_id="d-abc12345",
            outcome="profitable",
            principle_ids=["prin_abc12345"],
            profit_cents=450,
        )
        self.assertEqual(event.delivery_id, "d-abc12345")
        self.assertEqual(event.outcome, "profitable")
        self.assertEqual(event.profit_cents, 450)

    def test_event_to_dict(self):
        event = FeedbackEvent(
            delivery_id="d-abc12345",
            outcome="unprofitable",
            principle_ids=["prin_abc12345", "prin_def67890"],
            profit_cents=-200,
        )
        d = event.to_dict()
        self.assertIn("delivery_id", d)
        self.assertIn("outcome", d)
        self.assertIn("principle_ids", d)
        self.assertIn("timestamp", d)

    def test_event_json_serializable(self):
        event = FeedbackEvent(
            delivery_id="d-abc",
            outcome="profitable",
            principle_ids=["p1"],
            profit_cents=100,
        )
        json_str = json.dumps(event.to_dict())
        self.assertIsInstance(json_str, str)


class TestOutcomeFeedback(unittest.TestCase):
    """Test the feedback loop engine."""

    def setUp(self):
        # Create temp files for outcomes and principles
        self.tmpdir = tempfile.mkdtemp()
        self.outcomes_path = os.path.join(self.tmpdir, "outcomes.jsonl")
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.feedback_log_path = os.path.join(self.tmpdir, "feedback_log.jsonl")

        # Create a tracker with test data
        self.tracker = OutcomeTracker(db_path=self.outcomes_path)
        self.delivery = self.tracker.add_delivery(
            session=104,
            title="Bayesian calibration paper",
            category="academic_paper",
            description="arXiv:2602.19520 calibration bias",
            target_chat="kalshi_main",
        )
        self.tracker.save()

        # Create test principles
        self.principle1 = Principle(
            id="prin_bayesian_01",
            text="Bayesian calibration improves prediction accuracy",
            source_domain="trading_research",
            applicable_domains=["trading_research", "trading_execution"],
            success_count=3,
            usage_count=5,
            created_session=100,
            last_used_session=104,
            created_at="2026-03-20T10:00:00Z",
            updated_at="2026-03-21T10:00:00Z",
        )
        self.principle2 = Principle(
            id="prin_cross_plat_01",
            text="Cross-platform divergence signals have edge",
            source_domain="trading_research",
            applicable_domains=["trading_research"],
            success_count=1,
            usage_count=2,
            created_session=105,
            last_used_session=105,
            created_at="2026-03-21T10:00:00Z",
            updated_at="2026-03-21T10:00:00Z",
        )
        _save_principle(self.principle1, path=self.principles_path)
        _save_principle(self.principle2, path=self.principles_path)

        self.feedback = OutcomeFeedback(
            outcomes_path=self.outcomes_path,
            principles_path=self.principles_path,
            feedback_log_path=self.feedback_log_path,
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # --- Core feedback loop ---

    def test_record_profitable_outcome(self):
        """Profitable outcome should score SUCCESS on linked principles."""
        event = self.feedback.record_outcome(
            delivery_id=self.delivery.delivery_id,
            outcome="profitable",
            profit_cents=450,
            principle_ids=["prin_bayesian_01"],
        )
        self.assertEqual(event.outcome, "profitable")
        self.assertEqual(len(event.principle_ids), 1)

        # Verify principle was scored
        principles = _load_principles(path=self.principles_path)
        p = principles["prin_bayesian_01"]
        self.assertEqual(p.success_count, 4)  # Was 3, now 4
        self.assertEqual(p.usage_count, 6)     # Was 5, now 6

    def test_record_unprofitable_outcome(self):
        """Unprofitable outcome should score FAILURE on linked principles."""
        event = self.feedback.record_outcome(
            delivery_id=self.delivery.delivery_id,
            outcome="unprofitable",
            profit_cents=-200,
            principle_ids=["prin_bayesian_01"],
        )
        self.assertEqual(event.outcome, "unprofitable")

        principles = _load_principles(path=self.principles_path)
        p = principles["prin_bayesian_01"]
        self.assertEqual(p.success_count, 3)   # Unchanged
        self.assertEqual(p.usage_count, 6)      # Was 5, now 6 (counted as usage)

    def test_multiple_principles_updated(self):
        """Outcome can update multiple principles."""
        self.feedback.record_outcome(
            delivery_id=self.delivery.delivery_id,
            outcome="profitable",
            profit_cents=300,
            principle_ids=["prin_bayesian_01", "prin_cross_plat_01"],
        )

        principles = _load_principles(path=self.principles_path)
        p1 = principles["prin_bayesian_01"]
        p2 = principles["prin_cross_plat_01"]
        self.assertEqual(p1.success_count, 4)
        self.assertEqual(p2.success_count, 2)  # Was 1, now 2

    def test_no_principles_still_records(self):
        """Outcome with no linked principles should still be logged."""
        event = self.feedback.record_outcome(
            delivery_id=self.delivery.delivery_id,
            outcome="profitable",
            profit_cents=100,
            principle_ids=[],
        )
        self.assertEqual(event.principle_ids, [])
        # Feedback log should still have the event
        self.assertTrue(os.path.exists(self.feedback_log_path))

    def test_unknown_principle_skipped(self):
        """Unknown principle IDs should be skipped without error."""
        event = self.feedback.record_outcome(
            delivery_id=self.delivery.delivery_id,
            outcome="profitable",
            profit_cents=100,
            principle_ids=["prin_nonexistent_01"],
        )
        self.assertEqual(len(event.skipped_principles), 1)
        self.assertEqual(event.skipped_principles[0], "prin_nonexistent_01")

    # --- Delivery status update ---

    def test_delivery_status_updated(self):
        """Recording outcome should also update the delivery status."""
        self.feedback.record_outcome(
            delivery_id=self.delivery.delivery_id,
            outcome="profitable",
            profit_cents=450,
            principle_ids=["prin_bayesian_01"],
        )
        # Reload and check
        tracker = OutcomeTracker(db_path=self.outcomes_path)
        d = tracker._get_delivery(self.delivery.delivery_id)
        self.assertEqual(d.status, "profitable")
        self.assertEqual(d.profit_impact_cents, 450)

    # --- Feedback log ---

    def test_feedback_log_written(self):
        self.feedback.record_outcome(
            delivery_id=self.delivery.delivery_id,
            outcome="profitable",
            profit_cents=450,
            principle_ids=["prin_bayesian_01"],
        )
        self.assertTrue(os.path.exists(self.feedback_log_path))
        with open(self.feedback_log_path) as f:
            events = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["outcome"], "profitable")

    def test_multiple_events_appended(self):
        # Add a second delivery
        d2 = self.tracker.add_delivery(
            session=105, title="Cross-platform paper",
            category="academic_paper",
            description="SSRN:5331995",
            target_chat="kalshi_main",
        )
        self.tracker.save()

        self.feedback.record_outcome(
            delivery_id=self.delivery.delivery_id,
            outcome="profitable", profit_cents=450,
            principle_ids=["prin_bayesian_01"],
        )
        self.feedback.record_outcome(
            delivery_id=d2.delivery_id,
            outcome="unprofitable", profit_cents=-100,
            principle_ids=["prin_cross_plat_01"],
        )

        with open(self.feedback_log_path) as f:
            events = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(events), 2)

    # --- Batch processing ---

    def test_process_pending_outcomes(self):
        """Process all deliveries that have outcome status but no principle update."""
        self.tracker.mark_profitable(self.delivery.delivery_id, 450)
        self.tracker.save()

        results = self.feedback.process_pending(
            principle_mapping={
                self.delivery.delivery_id: ["prin_bayesian_01"],
            }
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].outcome, "profitable")

    # --- ROI summary with principle scores ---

    def test_roi_with_principle_context(self):
        """ROI summary should include principle score impact."""
        self.feedback.record_outcome(
            delivery_id=self.delivery.delivery_id,
            outcome="profitable", profit_cents=450,
            principle_ids=["prin_bayesian_01"],
        )
        summary = self.feedback.roi_summary()
        self.assertIn("total_feedback_events", summary)
        self.assertIn("profitable_count", summary)
        self.assertIn("total_profit_cents", summary)
        self.assertIn("principles_updated", summary)

    # --- Edge cases ---

    def test_invalid_outcome_raises(self):
        with self.assertRaises(ValueError):
            self.feedback.record_outcome(
                delivery_id=self.delivery.delivery_id,
                outcome="magic",
                profit_cents=100,
                principle_ids=[],
            )

    def test_invalid_delivery_raises(self):
        with self.assertRaises(KeyError):
            self.feedback.record_outcome(
                delivery_id="d-nonexistent",
                outcome="profitable",
                profit_cents=100,
                principle_ids=[],
            )

    def test_empty_principles_path(self):
        """Should work even if principles file doesn't exist yet."""
        empty_path = os.path.join(self.tmpdir, "empty_principles.jsonl")
        fb = OutcomeFeedback(
            outcomes_path=self.outcomes_path,
            principles_path=empty_path,
            feedback_log_path=self.feedback_log_path,
        )
        event = fb.record_outcome(
            delivery_id=self.delivery.delivery_id,
            outcome="profitable",
            profit_cents=100,
            principle_ids=["prin_nonexistent"],
        )
        self.assertEqual(len(event.skipped_principles), 1)


if __name__ == "__main__":
    unittest.main()
