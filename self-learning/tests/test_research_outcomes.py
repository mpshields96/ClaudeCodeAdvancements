#!/usr/bin/env python3
"""Tests for research_outcomes.py — CCA research ROI tracker.

Tracks which CCA research deliveries (papers, repos, signals) got implemented
by Kalshi chats and whether they produced profit. Closes the ROI loop.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, MODULE_DIR)

import research_outcomes as ro


class TestDelivery(unittest.TestCase):
    """Test Delivery dataclass-like creation and serialization."""

    def test_create_delivery(self):
        d = ro.Delivery(
            delivery_id="d-001",
            session=56,
            title="Tsang intraday seasonality paper",
            category="academic_paper",
            description="Validates overnight liquidity thinning in prediction markets",
            target_chat="kalshi_research",
        )
        self.assertEqual(d.delivery_id, "d-001")
        self.assertEqual(d.session, 56)
        self.assertEqual(d.category, "academic_paper")
        self.assertEqual(d.status, "delivered")  # default

    def test_delivery_to_dict(self):
        d = ro.Delivery(
            delivery_id="d-002",
            session=52,
            title="SPRT framework",
            category="framework",
            description="Sequential testing for edge detection",
            target_chat="kalshi_research",
        )
        data = d.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["delivery_id"], "d-002")
        self.assertIn("created_at", data)
        self.assertEqual(data["status"], "delivered")

    def test_delivery_from_dict(self):
        data = {
            "delivery_id": "d-003",
            "session": 50,
            "title": "Kelly criterion paper",
            "category": "academic_paper",
            "description": "Meister 2024 optimal bet fraction",
            "target_chat": "kalshi_research",
            "status": "implemented",
            "created_at": "2026-03-19T10:00:00+00:00",
            "implemented_at": "2026-03-19T14:00:00+00:00",
            "profit_impact_cents": 500,
            "notes": "Implemented kelly_fraction() in bot",
        }
        d = ro.Delivery.from_dict(data)
        self.assertEqual(d.delivery_id, "d-003")
        self.assertEqual(d.status, "implemented")
        self.assertEqual(d.profit_impact_cents, 500)

    def test_valid_categories(self):
        self.assertIn("academic_paper", ro.VALID_CATEGORIES)
        self.assertIn("repo_evaluation", ro.VALID_CATEGORIES)
        self.assertIn("framework", ro.VALID_CATEGORIES)
        self.assertIn("signal", ro.VALID_CATEGORIES)
        self.assertIn("reddit_finding", ro.VALID_CATEGORIES)

    def test_valid_statuses(self):
        self.assertIn("delivered", ro.VALID_STATUSES)
        self.assertIn("acknowledged", ro.VALID_STATUSES)
        self.assertIn("implemented", ro.VALID_STATUSES)
        self.assertIn("rejected", ro.VALID_STATUSES)
        self.assertIn("profitable", ro.VALID_STATUSES)
        self.assertIn("unprofitable", ro.VALID_STATUSES)


class TestOutcomeTracker(unittest.TestCase):
    """Test OutcomeTracker — the main tracking engine."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "outcomes.jsonl")
        self.tracker = ro.OutcomeTracker(self.db_path)

    def test_add_delivery(self):
        d = self.tracker.add_delivery(
            session=56,
            title="Tsang overnight paper",
            category="academic_paper",
            description="Validates overnight liquidity thinning",
            target_chat="kalshi_research",
        )
        self.assertIsNotNone(d.delivery_id)
        self.assertEqual(len(self.tracker.deliveries), 1)

    def test_delivery_id_uniqueness(self):
        d1 = self.tracker.add_delivery(56, "Paper A", "academic_paper", "desc", "kalshi_research")
        d2 = self.tracker.add_delivery(56, "Paper B", "academic_paper", "desc", "kalshi_research")
        self.assertNotEqual(d1.delivery_id, d2.delivery_id)

    def test_persistence_save_load(self):
        self.tracker.add_delivery(56, "Paper A", "academic_paper", "desc", "kalshi_research")
        self.tracker.add_delivery(56, "Paper B", "framework", "desc", "kalshi_main")
        self.tracker.save()

        tracker2 = ro.OutcomeTracker(self.db_path)
        tracker2.load()
        self.assertEqual(len(tracker2.deliveries), 2)
        self.assertEqual(tracker2.deliveries[0].title, "Paper A")

    def test_update_status(self):
        d = self.tracker.add_delivery(56, "Paper A", "academic_paper", "desc", "kalshi_research")
        self.tracker.update_status(d.delivery_id, "acknowledged")
        self.assertEqual(d.status, "acknowledged")

    def test_update_status_invalid(self):
        d = self.tracker.add_delivery(56, "Paper A", "academic_paper", "desc", "kalshi_research")
        with self.assertRaises(ValueError):
            self.tracker.update_status(d.delivery_id, "bogus_status")

    def test_update_status_not_found(self):
        with self.assertRaises(KeyError):
            self.tracker.update_status("nonexistent-id", "acknowledged")

    def test_mark_implemented(self):
        d = self.tracker.add_delivery(56, "Paper A", "academic_paper", "desc", "kalshi_research")
        self.tracker.mark_implemented(d.delivery_id, notes="Built kelly_fraction()")
        self.assertEqual(d.status, "implemented")
        self.assertIsNotNone(d.implemented_at)
        self.assertEqual(d.notes, "Built kelly_fraction()")

    def test_mark_profitable(self):
        d = self.tracker.add_delivery(56, "Paper A", "academic_paper", "desc", "kalshi_research")
        self.tracker.mark_implemented(d.delivery_id)
        self.tracker.mark_profitable(d.delivery_id, profit_cents=1200, notes="Net +$12 from Kelly sizing")
        self.assertEqual(d.status, "profitable")
        self.assertEqual(d.profit_impact_cents, 1200)

    def test_mark_unprofitable(self):
        d = self.tracker.add_delivery(56, "Paper A", "academic_paper", "desc", "kalshi_research")
        self.tracker.mark_implemented(d.delivery_id)
        self.tracker.mark_unprofitable(d.delivery_id, loss_cents=-300, notes="Spread too wide")
        self.assertEqual(d.status, "unprofitable")
        self.assertEqual(d.profit_impact_cents, -300)

    def test_filter_by_status(self):
        self.tracker.add_delivery(56, "A", "academic_paper", "d", "kalshi_research")
        d2 = self.tracker.add_delivery(56, "B", "framework", "d", "kalshi_research")
        self.tracker.update_status(d2.delivery_id, "acknowledged")

        delivered = self.tracker.filter_by_status("delivered")
        self.assertEqual(len(delivered), 1)
        acknowledged = self.tracker.filter_by_status("acknowledged")
        self.assertEqual(len(acknowledged), 1)

    def test_filter_by_category(self):
        self.tracker.add_delivery(56, "A", "academic_paper", "d", "kalshi_research")
        self.tracker.add_delivery(56, "B", "repo_evaluation", "d", "kalshi_research")
        self.tracker.add_delivery(56, "C", "academic_paper", "d", "kalshi_main")

        papers = self.tracker.filter_by_category("academic_paper")
        self.assertEqual(len(papers), 2)

    def test_filter_by_session(self):
        self.tracker.add_delivery(50, "A", "academic_paper", "d", "kalshi_research")
        self.tracker.add_delivery(56, "B", "framework", "d", "kalshi_research")

        s50 = self.tracker.filter_by_session(50)
        self.assertEqual(len(s50), 1)
        self.assertEqual(s50[0].title, "A")


class TestROIMetrics(unittest.TestCase):
    """Test ROI calculation and reporting."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "outcomes.jsonl")
        self.tracker = ro.OutcomeTracker(self.db_path)

    def test_roi_empty(self):
        metrics = self.tracker.compute_roi()
        self.assertEqual(metrics["total_deliveries"], 0)
        self.assertEqual(metrics["implementation_rate"], 0.0)
        self.assertEqual(metrics["profit_rate"], 0.0)

    def test_roi_with_data(self):
        d1 = self.tracker.add_delivery(50, "A", "academic_paper", "d", "kr")
        d2 = self.tracker.add_delivery(50, "B", "framework", "d", "kr")
        d3 = self.tracker.add_delivery(50, "C", "signal", "d", "kr")

        self.tracker.mark_implemented(d1.delivery_id)
        self.tracker.mark_profitable(d1.delivery_id, profit_cents=500)
        self.tracker.mark_implemented(d2.delivery_id)
        self.tracker.mark_unprofitable(d2.delivery_id, loss_cents=-100)
        # d3 stays delivered (not implemented)

        metrics = self.tracker.compute_roi()
        self.assertEqual(metrics["total_deliveries"], 3)
        self.assertAlmostEqual(metrics["implementation_rate"], 2/3)
        self.assertEqual(metrics["total_profit_cents"], 400)  # 500 - 100
        self.assertEqual(metrics["profitable_count"], 1)
        self.assertEqual(metrics["unprofitable_count"], 1)
        self.assertAlmostEqual(metrics["profit_rate"], 0.5)  # 1 of 2 implemented

    def test_roi_by_category(self):
        d1 = self.tracker.add_delivery(50, "A", "academic_paper", "d", "kr")
        d2 = self.tracker.add_delivery(50, "B", "academic_paper", "d", "kr")
        d3 = self.tracker.add_delivery(50, "C", "repo_evaluation", "d", "kr")

        self.tracker.mark_implemented(d1.delivery_id)
        self.tracker.mark_profitable(d1.delivery_id, profit_cents=1000)
        self.tracker.mark_implemented(d3.delivery_id)
        self.tracker.mark_unprofitable(d3.delivery_id, loss_cents=-200)

        by_cat = self.tracker.roi_by_category()
        self.assertIn("academic_paper", by_cat)
        self.assertEqual(by_cat["academic_paper"]["total"], 2)
        self.assertEqual(by_cat["academic_paper"]["implemented"], 1)
        self.assertEqual(by_cat["academic_paper"]["profit_cents"], 1000)

    def test_pending_pickup_list(self):
        """List deliveries that Kalshi chats haven't acknowledged yet."""
        self.tracker.add_delivery(50, "A", "academic_paper", "d", "kr")
        d2 = self.tracker.add_delivery(50, "B", "framework", "d", "kr")
        self.tracker.update_status(d2.delivery_id, "acknowledged")

        pending = self.tracker.pending_pickups()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].title, "A")

    def test_summary_report(self):
        """Generate a human-readable summary."""
        self.tracker.add_delivery(56, "Tsang paper", "academic_paper", "overnight", "kr")
        self.tracker.add_delivery(56, "Kelly paper", "academic_paper", "bet sizing", "kr")

        report = self.tracker.summary_report()
        self.assertIsInstance(report, str)
        self.assertIn("Total deliveries:", report)
        self.assertIn("Pending pickup:", report)


class TestBulkImport(unittest.TestCase):
    """Test importing deliveries from KALSHI_INTEL.md / CROSS_CHAT_INBOX.md."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "outcomes.jsonl")
        self.tracker = ro.OutcomeTracker(self.db_path)

    def test_bulk_add(self):
        items = [
            {"session": 56, "title": "Tsang paper", "category": "academic_paper",
             "description": "Overnight liquidity", "target_chat": "kr"},
            {"session": 56, "title": "Baker-McHale paper", "category": "academic_paper",
             "description": "Kelly shrinkage", "target_chat": "kr"},
            {"session": 56, "title": "Polymarket bot eval", "category": "repo_evaluation",
             "description": "Drawdown heat system", "target_chat": "kr"},
        ]
        added = self.tracker.bulk_add(items)
        self.assertEqual(len(added), 3)
        self.assertEqual(len(self.tracker.deliveries), 3)

    def test_bulk_add_deduplication(self):
        """Don't add duplicate titles for same session."""
        self.tracker.add_delivery(56, "Tsang paper", "academic_paper", "d", "kr")
        items = [
            {"session": 56, "title": "Tsang paper", "category": "academic_paper",
             "description": "d", "target_chat": "kr"},
            {"session": 56, "title": "NEW paper", "category": "academic_paper",
             "description": "d", "target_chat": "kr"},
        ]
        added = self.tracker.bulk_add(items)
        self.assertEqual(len(added), 1)  # Only the new one
        self.assertEqual(len(self.tracker.deliveries), 2)


if __name__ == "__main__":
    unittest.main()
