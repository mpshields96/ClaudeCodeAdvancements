#!/usr/bin/env python3
"""Tests for research_roi_resolver.py — MT-49 Phase 5: Research-to-production ROI tracking."""
import json
import os
import shutil
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

from research_roi_resolver import (
    AckEntry,
    parse_delivery_acks,
    resolve_deliveries,
    roi_by_category,
    roi_by_principle,
    ROIResolver,
)


SAMPLE_ACK_MD = """# DELIVERY_ACK.md — Implementation Acknowledgments

---

## ACK LOG

### REQ-001 through REQ-009 | IMPLEMENTED | Various commits | March 2026
The SPRT/Wilson CI/CUSUM framework was built and is running in production.

## [2026-03-25 02:30 UTC] — ACK REQ-032 IMPLEMENTED (S134)
Delivery: CCA S156 economics sniper questions (5 Qs answered)
Commit: 101dd75
Status: FULLY IMPLEMENTED

## [2026-03-25 02:30 UTC] — ACK REQ-027 PARTIAL (S134)
Delivery: Monte Carlo + Synthetic + Edge Stability (S151)
Status: NOT YET INTEGRATED

## [2026-03-24 04:55 UTC] — ACK — CCA S141 Analysis
Received and reviewed S141 delivery.
Status: REVIEWED — no code changes needed.
"""


class TestParseDeliveryAcks(unittest.TestCase):
    """Test parsing DELIVERY_ACK.md into structured entries."""

    def test_parse_returns_list(self):
        entries = parse_delivery_acks(SAMPLE_ACK_MD)
        self.assertIsInstance(entries, list)

    def test_parse_finds_implemented(self):
        entries = parse_delivery_acks(SAMPLE_ACK_MD)
        implemented = [e for e in entries if e.status == "implemented"]
        self.assertGreater(len(implemented), 0)

    def test_parse_finds_partial_as_acknowledged(self):
        entries = parse_delivery_acks(SAMPLE_ACK_MD)
        # PARTIAL is normalized to "acknowledged" in the research_outcomes vocabulary
        acked = [e for e in entries if e.status == "acknowledged"]
        self.assertGreater(len(acked), 0)

    def test_ack_entry_has_req_id(self):
        entries = parse_delivery_acks(SAMPLE_ACK_MD)
        req_entries = [e for e in entries if e.req_id]
        self.assertGreater(len(req_entries), 0)

    def test_ack_entry_has_date(self):
        entries = parse_delivery_acks(SAMPLE_ACK_MD)
        dated = [e for e in entries if e.date]
        self.assertGreater(len(dated), 0)

    def test_empty_text_returns_empty(self):
        entries = parse_delivery_acks("")
        self.assertEqual(entries, [])

    def test_ack_entry_has_session(self):
        entries = parse_delivery_acks(SAMPLE_ACK_MD)
        sessioned = [e for e in entries if e.session]
        self.assertGreater(len(sessioned), 0)


class TestResolveDeliveries(unittest.TestCase):
    """Test matching ACK entries to research_outcomes deliveries."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.outcomes_path = os.path.join(self.tmpdir, "research_outcomes.jsonl")
        deliveries = [
            {
                "delivery_id": "d-aaa",
                "session": 50,
                "title": "SPRT framework",
                "category": "framework",
                "description": "SPRT/Wilson CI/CUSUM",
                "target_chat": "kalshi_main",
                "status": "delivered",
                "created_at": "2026-03-19T00:00:00Z",
            },
            {
                "delivery_id": "d-bbb",
                "session": 134,
                "title": "Economics sniper",
                "category": "signal",
                "description": "Economics sniper questions",
                "target_chat": "kalshi_main",
                "status": "delivered",
                "created_at": "2026-03-25T00:00:00Z",
            },
            {
                "delivery_id": "d-ccc",
                "session": 151,
                "title": "Monte Carlo simulator",
                "category": "tool",
                "description": "Monte Carlo + Synthetic + Edge Stability",
                "target_chat": "kalshi_main",
                "status": "delivered",
                "created_at": "2026-03-25T00:00:00Z",
            },
        ]
        with open(self.outcomes_path, "w") as f:
            for d in deliveries:
                f.write(json.dumps(d) + "\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_resolve_matches_implemented(self):
        acks = [AckEntry(req_id="REQ-032", status="implemented", date="2026-03-25", session="S134")]
        updates = resolve_deliveries(acks, self.outcomes_path)
        self.assertGreater(len(updates), 0)

    def test_resolve_updates_status(self):
        acks = [AckEntry(req_id="REQ-032", status="implemented", date="2026-03-25", session="S134")]
        updates = resolve_deliveries(acks, self.outcomes_path)
        matched = [u for u in updates if u["new_status"] == "implemented"]
        self.assertGreater(len(matched), 0)

    def test_resolve_fuzzy_matches_by_title(self):
        """Deliveries without REQ-ID should match by title similarity."""
        acks = [AckEntry(req_id=None, status="implemented", date="2026-03-25",
                         session=None, description="SPRT/Wilson CI/CUSUM framework")]
        updates = resolve_deliveries(acks, self.outcomes_path)
        matched = [u for u in updates if u.get("delivery_id") == "d-aaa"]
        self.assertGreater(len(matched), 0)

    def test_resolve_returns_empty_for_no_match(self):
        acks = [AckEntry(req_id="REQ-999", status="implemented", date="2026-03-25", session="S200")]
        updates = resolve_deliveries(acks, self.outcomes_path)
        self.assertEqual(len(updates), 0)

    def test_resolve_partial_status(self):
        acks = [AckEntry(req_id="REQ-027", status="acknowledged", date="2026-03-25",
                         session="S134", description="Monte Carlo Synthetic Edge Stability")]
        updates = resolve_deliveries(acks, self.outcomes_path)
        acked = [u for u in updates if u["new_status"] == "acknowledged"]
        self.assertGreater(len(acked), 0)


class TestROIByCategory(unittest.TestCase):
    """Test ROI aggregation by research category."""

    def setUp(self):
        self.deliveries = [
            {"delivery_id": "d-1", "category": "academic_paper", "status": "profitable", "profit_impact_cents": 500},
            {"delivery_id": "d-2", "category": "academic_paper", "status": "unprofitable", "profit_impact_cents": -200},
            {"delivery_id": "d-3", "category": "framework", "status": "implemented", "profit_impact_cents": None},
            {"delivery_id": "d-4", "category": "signal", "status": "delivered", "profit_impact_cents": None},
        ]

    def test_roi_by_category_returns_dict(self):
        result = roi_by_category(self.deliveries)
        self.assertIsInstance(result, dict)

    def test_roi_includes_all_categories(self):
        result = roi_by_category(self.deliveries)
        self.assertIn("academic_paper", result)
        self.assertIn("framework", result)

    def test_roi_net_profit_correct(self):
        result = roi_by_category(self.deliveries)
        self.assertEqual(result["academic_paper"]["net_profit_cents"], 300)

    def test_roi_counts_correct(self):
        result = roi_by_category(self.deliveries)
        self.assertEqual(result["academic_paper"]["total"], 2)
        self.assertEqual(result["academic_paper"]["profitable"], 1)
        self.assertEqual(result["academic_paper"]["unprofitable"], 1)

    def test_roi_implementation_rate(self):
        result = roi_by_category(self.deliveries)
        # academic_paper: 2 with profit outcome = 100% impl rate for those
        self.assertGreater(result["academic_paper"]["implementation_rate"], 0)


class TestROIByPrinciple(unittest.TestCase):
    """Test ROI aggregation by linked principles."""

    def setUp(self):
        self.feedback_entries = [
            {"delivery_id": "d-1", "principle_ids": ["prin_aaa", "prin_bbb"],
             "outcome": "profitable", "profit_cents": 500},
            {"delivery_id": "d-2", "principle_ids": ["prin_aaa"],
             "outcome": "unprofitable", "profit_cents": -200},
        ]

    def test_roi_by_principle_returns_dict(self):
        result = roi_by_principle(self.feedback_entries)
        self.assertIsInstance(result, dict)

    def test_principle_net_profit(self):
        result = roi_by_principle(self.feedback_entries)
        self.assertEqual(result["prin_aaa"]["net_profit_cents"], 300)
        self.assertEqual(result["prin_bbb"]["net_profit_cents"], 500)

    def test_principle_win_rate(self):
        result = roi_by_principle(self.feedback_entries)
        self.assertAlmostEqual(result["prin_aaa"]["win_rate"], 0.5)
        self.assertAlmostEqual(result["prin_bbb"]["win_rate"], 1.0)

    def test_empty_feedback(self):
        result = roi_by_principle([])
        self.assertEqual(result, {})


class TestROIResolver(unittest.TestCase):
    """Test the full ROI resolver pipeline."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.outcomes_path = os.path.join(self.tmpdir, "research_outcomes.jsonl")
        self.ack_path = os.path.join(self.tmpdir, "DELIVERY_ACK.md")
        self.feedback_path = os.path.join(self.tmpdir, "outcome_feedback.jsonl")

        deliveries = [
            {"delivery_id": "d-aaa", "session": 50, "title": "SPRT framework",
             "category": "framework", "description": "SPRT/CUSUM", "target_chat": "km",
             "status": "delivered", "created_at": "2026-03-19T00:00:00Z"},
        ]
        with open(self.outcomes_path, "w") as f:
            for d in deliveries:
                f.write(json.dumps(d) + "\n")

        with open(self.ack_path, "w") as f:
            f.write("## [2026-03-25] — ACK REQ-001 IMPLEMENTED\nSPRT framework running.\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_resolver_init(self):
        r = ROIResolver(self.outcomes_path, self.ack_path)
        self.assertIsNotNone(r)

    def test_resolver_run_produces_report(self):
        r = ROIResolver(self.outcomes_path, self.ack_path)
        report = r.run()
        self.assertIn("total_deliveries", report)
        self.assertIn("resolved", report)
        self.assertIn("by_category", report)

    def test_resolver_report_json_serializable(self):
        r = ROIResolver(self.outcomes_path, self.ack_path)
        report = r.run()
        # Should not raise
        json.dumps(report)


if __name__ == "__main__":
    unittest.main()
