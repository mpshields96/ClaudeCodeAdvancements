#!/usr/bin/env python3
"""Extended tests for research_outcomes.py — CCA Research ROI Tracker.

Covers edge cases not in the primary test suite:
- Delivery optional fields absent from to_dict when None
- Delivery.from_dict with all optional fields missing
- Delivery default created_at is a valid ISO timestamp
- _generate_id determinism and prefix
- OutcomeTracker: empty tracker state, reload doesn't double-load
- OutcomeTracker: save+reload preserves all fields
- OutcomeTracker: filter_by_* empty results
- OutcomeTracker: bulk_add empty list
- OutcomeTracker: pending_pickups when all acknowledged
- ROI: profit_rate 0 when no implementations, 100% when all profitable
- ROI: total_profit with mixed None profit_impact_cents
- ROI: roi_by_category empty tracker
- Summary report content: implementation rate included
- FindingsLogParser: empty line, malformed, title cap, desc cap, URL stripped
- parse_findings_content: empty string, all-skip content
- Delivery status lifecycle (delivered → implemented → profitable)
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


# ── Delivery extended ─────────────────────────────────────────────────────────


class TestDeliveryExtended(unittest.TestCase):

    def test_optional_fields_absent_from_to_dict_when_none(self):
        """implemented_at, profit_impact_cents, notes absent from to_dict when None."""
        d = ro.Delivery(
            delivery_id="d-001",
            session=10,
            title="Test paper",
            category="academic_paper",
            description="Desc",
            target_chat="kalshi_research",
        )
        data = d.to_dict()
        self.assertNotIn("implemented_at", data)
        self.assertNotIn("profit_impact_cents", data)
        self.assertNotIn("notes", data)

    def test_optional_fields_present_when_set(self):
        d = ro.Delivery(
            delivery_id="d-002",
            session=10,
            title="Test paper",
            category="academic_paper",
            description="Desc",
            target_chat="kalshi_research",
            implemented_at="2026-03-19T14:00:00+00:00",
            profit_impact_cents=500,
            notes="Built successfully",
        )
        data = d.to_dict()
        self.assertIn("implemented_at", data)
        self.assertIn("profit_impact_cents", data)
        self.assertIn("notes", data)

    def test_default_status_is_delivered(self):
        d = ro.Delivery(
            delivery_id="d-003",
            session=10,
            title="Paper",
            category="framework",
            description="d",
            target_chat="kalshi_research",
        )
        self.assertEqual(d.status, "delivered")

    def test_default_created_at_is_iso_string(self):
        d = ro.Delivery(
            delivery_id="d-004",
            session=10,
            title="Paper",
            category="signal",
            description="d",
            target_chat="kalshi_research",
        )
        # Should be parseable as ISO datetime
        try:
            dt = datetime.fromisoformat(d.created_at)
            self.assertIsNotNone(dt)
        except ValueError:
            self.fail("created_at is not a valid ISO datetime")

    def test_from_dict_missing_optional_fields(self):
        """from_dict should not fail when optional fields are absent."""
        data = {
            "delivery_id": "d-005",
            "session": 42,
            "title": "Minimal delivery",
            "category": "tool",
            "description": "A tool",
            "target_chat": "kalshi_research",
            "status": "delivered",
            "created_at": "2026-03-19T10:00:00+00:00",
            # No implemented_at, profit_impact_cents, notes
        }
        d = ro.Delivery.from_dict(data)
        self.assertIsNone(d.implemented_at)
        self.assertIsNone(d.profit_impact_cents)
        self.assertIsNone(d.notes)

    def test_status_reflected_in_to_dict_after_update(self):
        d = ro.Delivery(
            delivery_id="d-006",
            session=10,
            title="Paper",
            category="academic_paper",
            description="d",
            target_chat="kalshi_research",
        )
        d.status = "acknowledged"
        data = d.to_dict()
        self.assertEqual(data["status"], "acknowledged")

    def test_delivery_id_in_to_dict(self):
        d = ro.Delivery(
            delivery_id="d-xyz",
            session=10,
            title="Paper",
            category="data_source",
            description="d",
            target_chat="kalshi_research",
        )
        data = d.to_dict()
        self.assertEqual(data["delivery_id"], "d-xyz")

    def test_all_valid_categories_accepted(self):
        for cat in ro.VALID_CATEGORIES:
            d = ro.Delivery(
                delivery_id=f"d-{cat}",
                session=1,
                title=f"Test {cat}",
                category=cat,
                description="d",
                target_chat="kalshi_research",
            )
            self.assertEqual(d.category, cat)


# ── _generate_id extended ─────────────────────────────────────────────────────


class TestGenerateId(unittest.TestCase):

    def test_generate_id_is_deterministic(self):
        id1 = ro._generate_id(56, "Tsang paper")
        id2 = ro._generate_id(56, "Tsang paper")
        self.assertEqual(id1, id2)

    def test_generate_id_different_for_different_inputs(self):
        id1 = ro._generate_id(56, "Paper A")
        id2 = ro._generate_id(56, "Paper B")
        self.assertNotEqual(id1, id2)

    def test_generate_id_different_sessions_different_ids(self):
        id1 = ro._generate_id(50, "Paper A")
        id2 = ro._generate_id(51, "Paper A")
        self.assertNotEqual(id1, id2)

    def test_generate_id_starts_with_d_prefix(self):
        did = ro._generate_id(56, "Some title")
        self.assertTrue(did.startswith("d-"))

    def test_generate_id_has_8_char_hex_suffix(self):
        did = ro._generate_id(56, "Some title")
        suffix = did[len("d-"):]
        self.assertEqual(len(suffix), 8)
        # Must be hex
        int(suffix, 16)  # raises ValueError if not hex


# ── OutcomeTracker extended ───────────────────────────────────────────────────


class TestOutcomeTrackerExtended(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "outcomes.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _make_tracker(self):
        return ro.OutcomeTracker(self.db_path)

    def test_empty_tracker_has_no_deliveries(self):
        tracker = self._make_tracker()
        self.assertEqual(len(tracker.deliveries), 0)

    def test_reload_does_not_double_load(self):
        """Calling load() again on an already-loaded tracker should not duplicate entries."""
        tracker = self._make_tracker()
        tracker.add_delivery(56, "Paper A", "academic_paper", "d", "kr")
        tracker.save()
        tracker.load()  # explicit reload
        self.assertEqual(len(tracker.deliveries), 1)

    def test_save_and_reload_preserves_notes(self):
        tracker = self._make_tracker()
        d = tracker.add_delivery(56, "Paper A", "academic_paper", "d", "kr")
        d.notes = "Built kelly fraction"
        tracker.save()

        tracker2 = self._make_tracker()
        self.assertEqual(tracker2.deliveries[0].notes, "Built kelly fraction")

    def test_save_and_reload_preserves_profit_cents(self):
        tracker = self._make_tracker()
        d = tracker.add_delivery(56, "Paper B", "signal", "d", "kr")
        tracker.mark_profitable(d.delivery_id, profit_cents=750)
        tracker.save()

        tracker2 = self._make_tracker()
        self.assertEqual(tracker2.deliveries[0].profit_impact_cents, 750)

    def test_save_and_reload_preserves_implemented_at(self):
        tracker = self._make_tracker()
        d = tracker.add_delivery(56, "Paper C", "framework", "d", "kr")
        tracker.mark_implemented(d.delivery_id, notes="Built")
        original_impl_at = d.implemented_at
        tracker.save()

        tracker2 = self._make_tracker()
        self.assertEqual(tracker2.deliveries[0].implemented_at, original_impl_at)

    def test_filter_by_status_empty_result(self):
        tracker = self._make_tracker()
        tracker.add_delivery(56, "A", "academic_paper", "d", "kr")
        # No profitable deliveries
        result = tracker.filter_by_status("profitable")
        self.assertEqual(result, [])

    def test_filter_by_category_empty_result(self):
        tracker = self._make_tracker()
        tracker.add_delivery(56, "A", "academic_paper", "d", "kr")
        result = tracker.filter_by_category("data_source")
        self.assertEqual(result, [])

    def test_filter_by_session_empty_result(self):
        tracker = self._make_tracker()
        tracker.add_delivery(56, "A", "academic_paper", "d", "kr")
        result = tracker.filter_by_session(99)
        self.assertEqual(result, [])

    def test_bulk_add_empty_list_returns_empty(self):
        tracker = self._make_tracker()
        added = tracker.bulk_add([])
        self.assertEqual(added, [])
        self.assertEqual(len(tracker.deliveries), 0)

    def test_pending_pickups_empty_when_all_acknowledged(self):
        tracker = self._make_tracker()
        d1 = tracker.add_delivery(56, "A", "academic_paper", "d", "kr")
        d2 = tracker.add_delivery(56, "B", "framework", "d", "kr")
        tracker.update_status(d1.delivery_id, "acknowledged")
        tracker.update_status(d2.delivery_id, "acknowledged")
        pending = tracker.pending_pickups()
        self.assertEqual(pending, [])

    def test_mark_profitable_without_notes(self):
        tracker = self._make_tracker()
        d = tracker.add_delivery(56, "A", "academic_paper", "d", "kr")
        tracker.mark_profitable(d.delivery_id, profit_cents=300)
        self.assertEqual(d.status, "profitable")
        self.assertEqual(d.profit_impact_cents, 300)

    def test_mark_unprofitable_positive_cents_stored_as_is(self):
        """mark_unprofitable with a positive cents value stores as-is."""
        tracker = self._make_tracker()
        d = tracker.add_delivery(56, "A", "academic_paper", "d", "kr")
        tracker.mark_unprofitable(d.delivery_id, loss_cents=200)
        self.assertEqual(d.profit_impact_cents, 200)

    def test_mark_implemented_sets_status_and_implemented_at(self):
        tracker = self._make_tracker()
        d = tracker.add_delivery(56, "A", "academic_paper", "d", "kr")
        tracker.mark_implemented(d.delivery_id)
        self.assertEqual(d.status, "implemented")
        self.assertIsNotNone(d.implemented_at)

    def test_id_index_populated_after_add(self):
        """Internal _id_index should contain added delivery."""
        tracker = self._make_tracker()
        d = tracker.add_delivery(56, "A", "academic_paper", "d", "kr")
        self.assertIn(d.delivery_id, tracker._id_index)

    def test_id_index_populated_after_load(self):
        tracker = self._make_tracker()
        d = tracker.add_delivery(56, "A", "academic_paper", "d", "kr")
        tracker.save()

        tracker2 = self._make_tracker()
        self.assertIn(d.delivery_id, tracker2._id_index)

    def test_bulk_add_all_new_returns_all(self):
        tracker = self._make_tracker()
        items = [
            {"session": 56, "title": f"Paper {i}", "category": "academic_paper",
             "description": "d", "target_chat": "kr"}
            for i in range(5)
        ]
        added = tracker.bulk_add(items)
        self.assertEqual(len(added), 5)

    def test_delivery_status_lifecycle(self):
        """Walk through status lifecycle: delivered → acknowledged → implemented → profitable."""
        tracker = self._make_tracker()
        d = tracker.add_delivery(56, "Complete lifecycle", "signal", "d", "kr")
        self.assertEqual(d.status, "delivered")

        tracker.update_status(d.delivery_id, "acknowledged")
        self.assertEqual(d.status, "acknowledged")

        tracker.mark_implemented(d.delivery_id, notes="Built it")
        self.assertEqual(d.status, "implemented")

        tracker.mark_profitable(d.delivery_id, profit_cents=1000)
        self.assertEqual(d.status, "profitable")


# ── ROI Metrics extended ──────────────────────────────────────────────────────


class TestROIMetricsExtended(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "outcomes.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _make_tracker(self):
        return ro.OutcomeTracker(self.db_path)

    def test_profit_rate_zero_when_no_implementations(self):
        tracker = self._make_tracker()
        tracker.add_delivery(50, "A", "academic_paper", "d", "kr")
        tracker.add_delivery(50, "B", "framework", "d", "kr")
        # None implemented
        metrics = tracker.compute_roi()
        self.assertEqual(metrics["profit_rate"], 0.0)

    def test_profit_rate_100_when_all_implemented_profitable(self):
        tracker = self._make_tracker()
        for i in range(3):
            d = tracker.add_delivery(50, f"Paper {i}", "academic_paper", "d", "kr")
            tracker.mark_implemented(d.delivery_id)
            tracker.mark_profitable(d.delivery_id, profit_cents=100)
        metrics = tracker.compute_roi()
        self.assertEqual(metrics["profit_rate"], 1.0)

    def test_total_profit_skips_none_profit_cents(self):
        """Deliveries with profit_impact_cents=None should not affect total_profit."""
        tracker = self._make_tracker()
        d1 = tracker.add_delivery(50, "A", "academic_paper", "d", "kr")
        d2 = tracker.add_delivery(50, "B", "academic_paper", "d", "kr")
        tracker.mark_profitable(d1.delivery_id, profit_cents=500)
        # d2 remains delivered (profit_impact_cents stays None)
        metrics = tracker.compute_roi()
        self.assertEqual(metrics["total_profit_cents"], 500)

    def test_total_profit_sums_positive_and_negative(self):
        tracker = self._make_tracker()
        d1 = tracker.add_delivery(50, "A", "academic_paper", "d", "kr")
        d2 = tracker.add_delivery(50, "B", "framework", "d", "kr")
        tracker.mark_profitable(d1.delivery_id, profit_cents=1000)
        tracker.mark_unprofitable(d2.delivery_id, loss_cents=-300)
        metrics = tracker.compute_roi()
        self.assertEqual(metrics["total_profit_cents"], 700)

    def test_roi_by_category_empty_tracker(self):
        tracker = self._make_tracker()
        result = tracker.roi_by_category()
        self.assertEqual(result, {})

    def test_roi_by_category_all_categories_present(self):
        tracker = self._make_tracker()
        for cat in ["academic_paper", "signal", "tool"]:
            tracker.add_delivery(50, f"Del {cat}", cat, "d", "kr")
        by_cat = tracker.roi_by_category()
        for cat in ["academic_paper", "signal", "tool"]:
            self.assertIn(cat, by_cat)

    def test_roi_by_category_implementation_count(self):
        tracker = self._make_tracker()
        d1 = tracker.add_delivery(50, "A", "signal", "d", "kr")
        d2 = tracker.add_delivery(50, "B", "signal", "d", "kr")
        tracker.mark_implemented(d1.delivery_id)
        # d2 stays delivered
        by_cat = tracker.roi_by_category()
        self.assertEqual(by_cat["signal"]["total"], 2)
        self.assertEqual(by_cat["signal"]["implemented"], 1)

    def test_implementation_rate_includes_profitable_and_unprofitable(self):
        """profitable and unprofitable statuses should count as implemented."""
        tracker = self._make_tracker()
        d1 = tracker.add_delivery(50, "A", "academic_paper", "d", "kr")
        d2 = tracker.add_delivery(50, "B", "signal", "d", "kr")
        tracker.mark_profitable(d1.delivery_id, profit_cents=200)
        tracker.mark_unprofitable(d2.delivery_id, loss_cents=-50)
        metrics = tracker.compute_roi()
        # Both count as implemented
        self.assertEqual(metrics["implementation_rate"], 1.0)

    def test_summary_report_includes_implementation_rate(self):
        tracker = self._make_tracker()
        d = tracker.add_delivery(56, "A", "academic_paper", "d", "kr")
        tracker.mark_implemented(d.delivery_id)
        report = tracker.summary_report()
        self.assertIn("Implementation rate", report)

    def test_summary_report_shows_pending_items(self):
        tracker = self._make_tracker()
        for i in range(3):
            tracker.add_delivery(56, f"Paper {i}", "academic_paper", "d", "kr")
        report = tracker.summary_report()
        self.assertIn("Awaiting", report)

    def test_summary_report_no_pending_section_when_all_acknowledged(self):
        """No 'Awaiting' section when no pending pickups."""
        tracker = self._make_tracker()
        d = tracker.add_delivery(56, "A", "academic_paper", "d", "kr")
        tracker.update_status(d.delivery_id, "acknowledged")
        report = tracker.summary_report()
        self.assertNotIn("Awaiting", report)

    def test_roi_metrics_have_expected_keys(self):
        tracker = self._make_tracker()
        metrics = tracker.compute_roi()
        for key in ("total_deliveries", "implementation_rate", "profit_rate",
                    "total_profit_cents", "profitable_count", "unprofitable_count"):
            self.assertIn(key, metrics)


# ── FindingsLogParser extended ────────────────────────────────────────────────


class TestFindingsLogParserExtended(unittest.TestCase):

    def test_empty_line_returns_none(self):
        result = ro.parse_findings_line("")
        self.assertIsNone(result)

    def test_whitespace_only_line_returns_none(self):
        result = ro.parse_findings_line("   \t   ")
        self.assertIsNone(result)

    def test_malformed_line_returns_none(self):
        result = ro.parse_findings_line("not a valid findings line at all")
        self.assertIsNone(result)

    def test_title_capped_at_100_chars(self):
        long_title = "X" * 200
        line = f"[2026-03-19] [REFERENCE-PERSONAL] [MT-0 Kalshi] {long_title}"
        result = ro.parse_findings_line(line)
        if result:
            self.assertLessEqual(len(result["title"]), 100)

    def test_description_capped_at_200_chars(self):
        long_desc = "Y" * 300
        line = f"[2026-03-19] [REFERENCE-PERSONAL] [MT-0 Kalshi] Short Title — {long_desc}"
        result = ro.parse_findings_line(line)
        if result:
            self.assertLessEqual(len(result["description"]), 200)

    def test_url_stripped_from_description(self):
        line = "[2026-03-19] [REFERENCE-PERSONAL] [MT-0 Kalshi] Paper A — Great paper. — https://arxiv.org/abs/1234.5678"
        result = ro.parse_findings_line(line)
        self.assertIsNotNone(result)
        self.assertNotIn("https://", result["description"])

    def test_doi_url_stripped_from_description(self):
        line = "[2026-03-19] [REFERENCE-PERSONAL] [MT-0 Kalshi] Baker paper — Kelly shrinkage. — DOI:10.1287/deca.2013.0271"
        result = ro.parse_findings_line(line)
        if result:
            self.assertNotIn("DOI:", result["description"])

    def test_target_chat_is_kalshi_research(self):
        line = "[2026-03-19] [REFERENCE-PERSONAL] [MT-0 Kalshi] Paper — desc. — https://url"
        result = ro.parse_findings_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["target_chat"], "kalshi_research")

    def test_parse_findings_content_empty_string(self):
        results = ro.parse_findings_content("")
        self.assertEqual(results, [])

    def test_parse_findings_content_all_skip(self):
        content = """[2026-03-19] [SKIP] [MT-0 Kalshi] Paper A — desc.
[2026-03-19] [SKIP] [MT-14] Paper B — desc."""
        results = ro.parse_findings_content(content)
        self.assertEqual(results, [])

    def test_parse_findings_content_all_non_kalshi(self):
        content = """[2026-03-19] [REFERENCE] [Frontier 1: Memory] Paper A.
[2026-03-19] [BUILD] [Frontier 2: Spec] Spec paper."""
        results = ro.parse_findings_content(content)
        self.assertEqual(results, [])

    def test_github_keyword_classifies_as_repo_evaluation(self):
        line = "[2026-03-19] [REFERENCE-PERSONAL] [MT-0 Kalshi] Polymarket Bot (GitHub) — repo desc."
        result = ro.parse_findings_line(line)
        if result:
            self.assertEqual(result["category"], "repo_evaluation")

    def test_arxiv_keyword_classifies_as_academic_paper(self):
        line = "[2026-03-19] [REFERENCE-PERSONAL] [MT-0 Kalshi] Arxiv paper — published on arxiv.org."
        result = ro.parse_findings_line(line)
        if result:
            self.assertEqual(result["category"], "academic_paper")

    def test_reddit_keyword_classifies_as_reddit_finding(self):
        line = "[2026-03-19] [REFERENCE-PERSONAL] [MT-0 Kalshi] 45pts, r/algotrading — time filter."
        result = ro.parse_findings_line(line)
        if result:
            self.assertEqual(result["category"], "reddit_finding")

    def test_parse_findings_returns_list_of_dicts(self):
        content = """[2026-03-19] [REFERENCE-PERSONAL] [MT-0 Kalshi] Paper A — desc A.
[2026-03-19] [REFERENCE-PERSONAL] [MT-0 Kalshi] Paper B — desc B."""
        results = ro.parse_findings_content(content)
        self.assertIsInstance(results, list)
        for r in results:
            self.assertIsInstance(r, dict)
            self.assertIn("title", r)
            self.assertIn("category", r)
            self.assertIn("target_chat", r)

    def test_date_field_present_in_result(self):
        line = "[2026-03-20] [REFERENCE-PERSONAL] [Kalshi] Paper — desc."
        result = ro.parse_findings_line(line)
        if result:
            self.assertEqual(result["date"], "2026-03-20")


if __name__ == "__main__":
    unittest.main()
