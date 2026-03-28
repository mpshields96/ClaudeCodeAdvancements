#!/usr/bin/env python3
"""Tests for research_roi_resolver.py — MT-49 Phase 5."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), "..", "self-learning")))
from research_roi_resolver import (
    AckEntry,
    ROIResolver,
    _fuzzy_match_score,
    _load_outcomes,
    _normalize_status,
    parse_delivery_acks,
    resolve_deliveries,
    roi_by_category,
    scan_cca_to_polybot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_outcomes_file(*entries) -> str:
    """Write entries to a temp JSONL file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return path


def _delivery(delivery_id, req_id=None, title="Test", status="delivered", session=None):
    d = {
        "delivery_id": delivery_id,
        "title": title,
        "category": "academic_paper",
        "description": "test",
        "target_chat": "kalshi_monitoring",
        "status": status,
        "session": session,
    }
    if req_id:
        d["req_id"] = req_id
    return d


# ---------------------------------------------------------------------------
# parse_delivery_acks
# ---------------------------------------------------------------------------

class TestParseDeliveryAcks(unittest.TestCase):

    def test_empty_text(self):
        acks = parse_delivery_acks("")
        self.assertEqual(acks, [])

    def test_single_implemented(self):
        text = """
## [2026-03-25 12:00 UTC] — ACK REQ-025 IMPLEMENTED (S134)
Delivery: Second edge research
"""
        acks = parse_delivery_acks(text)
        self.assertEqual(len(acks), 1)
        self.assertEqual(acks[0].req_id, "REQ-025")
        self.assertEqual(acks[0].status, "implemented")
        self.assertEqual(acks[0].session, "S134")

    def test_single_acknowledged(self):
        text = """
## [2026-03-25 12:00 UTC] — ACK REQ-037 ACKNOWLEDGED (S136)
Maker-side limit order feasibility noted.
"""
        acks = parse_delivery_acks(text)
        self.assertEqual(len(acks), 1)
        self.assertEqual(acks[0].req_id, "REQ-037")
        self.assertEqual(acks[0].status, "acknowledged")

    def test_bulk_ack_range(self):
        text = """
### REQ-001 through REQ-009 | IMPLEMENTED | Various commits | March 2026
SPRT/CUSUM framework built and running.
"""
        acks = parse_delivery_acks(text)
        # Should produce 9 acks for REQ-001 through REQ-009
        req_ids = {a.req_id for a in acks}
        for n in range(1, 10):
            self.assertIn(f"REQ-{n:03d}", req_ids)

    def test_multiple_acks(self):
        text = """
## [2026-03-25 12:00 UTC] — ACK REQ-025 IMPLEMENTED (S134)
text1
## [2026-03-25 12:01 UTC] — ACK REQ-027 ACKNOWLEDGED (S134)
text2
"""
        acks = parse_delivery_acks(text)
        self.assertEqual(len(acks), 2)
        self.assertEqual({a.req_id for a in acks}, {"REQ-025", "REQ-027"})


# ---------------------------------------------------------------------------
# resolve_deliveries
# ---------------------------------------------------------------------------

class TestResolveDeliveries(unittest.TestCase):

    def test_req_id_exact_match(self):
        path = _make_outcomes_file(
            _delivery("d-001", req_id="REQ-025", title="REQ-025: Second edge research")
        )
        acks = [AckEntry(req_id="REQ-025", status="implemented", date="2026-03-25")]
        updates = resolve_deliveries(acks, path)
        os.unlink(path)
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["new_status"], "implemented")
        self.assertEqual(updates[0]["matched_by"], "req_id")

    def test_no_match_when_req_id_missing(self):
        # Delivery has no req_id field and title doesn't match the ACK
        path = _make_outcomes_file(
            _delivery("d-001", title="Kelly criterion paper")
        )
        acks = [AckEntry(req_id="REQ-025", status="implemented", date="2026-03-25")]
        updates = resolve_deliveries(acks, path)
        os.unlink(path)
        self.assertEqual(len(updates), 0)

    def test_already_matched_not_rematched(self):
        path = _make_outcomes_file(
            _delivery("d-001", req_id="REQ-025", status="implemented")
        )
        acks = [
            AckEntry(req_id="REQ-025", status="implemented", date="2026-03-25"),
            AckEntry(req_id="REQ-025", status="acknowledged", date="2026-03-26"),
        ]
        updates = resolve_deliveries(acks, path)
        os.unlink(path)
        # Only one update — second ack doesn't re-match the same delivery
        ids = [u["delivery_id"] for u in updates]
        self.assertEqual(ids.count("d-001"), 1)

    def test_session_match(self):
        path = _make_outcomes_file(
            _delivery("d-session-match", session="134", title="REQ-032 economics sniper")
        )
        acks = [AckEntry(req_id=None, status="implemented", date="2026-03-25", session="S134")]
        updates = resolve_deliveries(acks, path)
        os.unlink(path)
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["matched_by"], "session")


# ---------------------------------------------------------------------------
# scan_cca_to_polybot — new Phase 5 source
# ---------------------------------------------------------------------------

class TestScanCcaToPolybot(unittest.TestCase):
    """scan_cca_to_polybot extracts REQ delivery evidence from CCA_TO_POLYBOT.md."""

    CCA_SAMPLE = """
## [2026-03-28 01:15 UTC] — UPDATE 68 — REQ-060: Tier 1 Domain Knowledge Strategy Architecture
Content here.

## [2026-03-28 01:25 UTC] — UPDATE 69 — REQ-016C: Agentic-RD-Sandbox Sports Model Assessment
Notes here.

## [2026-03-28 03:45 UTC] — UPDATE 70 — REQ-61: Daily Sniper Hour Analysis + Sports Game Calibration
Something delivered.

## [2026-03-28 04:10 UTC] — UPDATE 71 — REQ-60: domain_knowledge_scanner.py DELIVERED
Confirmed DELIVERED.

## [2026-03-28 18:00 UTC] — UPDATE 74 — REQ-017: Kalshi Political Series Research DELIVERED
Political research delivered.

## [2026-03-27 01:20 UTC] — DELIVERY — REQ-58 RESPONSE: 5-DAY MANDATE ANALYSIS
Mandate analysis.
"""

    def test_extracts_req_ids(self):
        """scan_cca_to_polybot returns req IDs found in UPDATE entries."""
        result = scan_cca_to_polybot(self.CCA_SAMPLE)
        req_ids = {r["req_id"] for r in result}
        self.assertIn("REQ-060", req_ids)
        self.assertIn("REQ-061", req_ids)
        self.assertIn("REQ-017", req_ids)
        self.assertIn("REQ-058", req_ids)

    def test_delivered_flag(self):
        """Entries with DELIVERED in body/title get delivered=True."""
        result = scan_cca_to_polybot(self.CCA_SAMPLE)
        by_req = {r["req_id"]: r for r in result}
        self.assertTrue(by_req.get("REQ-060", {}).get("delivered"))
        self.assertTrue(by_req.get("REQ-017", {}).get("delivered"))
        self.assertTrue(by_req.get("REQ-058", {}).get("delivered"))

    def test_returns_list_of_dicts(self):
        result = scan_cca_to_polybot(self.CCA_SAMPLE)
        self.assertIsInstance(result, list)
        for item in result:
            self.assertIn("req_id", item)
            self.assertIn("date", item)
            self.assertIn("delivered", item)

    def test_empty_text(self):
        result = scan_cca_to_polybot("")
        self.assertEqual(result, [])

    def test_no_updates(self):
        result = scan_cca_to_polybot("# Some file\nNo updates here.")
        self.assertEqual(result, [])

    def test_deduplication(self):
        """Multiple UPDATE entries for the same REQ produce one result (latest wins)."""
        text = """
## [2026-03-28 01:00 UTC] — UPDATE 1 — REQ-060: First mention
## [2026-03-28 04:00 UTC] — UPDATE 2 — REQ-060: Second mention DELIVERED
"""
        result = scan_cca_to_polybot(text)
        matching = [r for r in result if r["req_id"] == "REQ-060"]
        self.assertEqual(len(matching), 1)
        # Latest entry (with DELIVERED) should win
        self.assertTrue(matching[0]["delivered"])


# ---------------------------------------------------------------------------
# ROIResolver — integration of all three sources
# ---------------------------------------------------------------------------

class TestROIResolverIntegration(unittest.TestCase):

    def _make_resolver(self, outcomes_path, ack_text="", cca_text="", commits=None):
        """Create ROIResolver with mocked file reads."""
        r = ROIResolver(outcomes_path=outcomes_path)

        def mock_read_ack():
            return ack_text

        def mock_read_cca():
            return cca_text

        r._read_ack_text = mock_read_ack
        r._read_cca_text = mock_read_cca
        if commits is not None:
            r._scan_commits = lambda: commits
        return r

    def test_run_returns_required_keys(self):
        path = _make_outcomes_file(_delivery("d-001"))
        r = self._make_resolver(path)
        result = r.run()
        os.unlink(path)
        self.assertIn("total_deliveries", result)
        self.assertIn("resolved", result)
        self.assertIn("by_status", result)

    def test_cca_cross_chat_source_resolves_outcomes(self):
        """CCA_TO_POLYBOT.md scan elevates matching outcomes to sent_confirmed."""
        path = _make_outcomes_file(
            _delivery("d-req60", req_id="REQ-060", title="REQ-060: Domain knowledge strategy"),
            _delivery("d-other", title="Other delivery"),
        )
        cca_text = """
## [2026-03-28 04:10 UTC] — UPDATE 71 — REQ-60: domain_knowledge_scanner.py DELIVERED
"""
        r = self._make_resolver(path, cca_text=cca_text)
        result = r.run()
        os.unlink(path)
        # REQ-060 should be resolved via cca_cross_chat
        cross_chat_updates = [u for u in result["updates"] if u.get("matched_by") == "cca_cross_chat"]
        self.assertGreater(len(cross_chat_updates), 0)

    def test_no_double_counting(self):
        """Same delivery resolved by both ACK and CCA cross-chat only counted once."""
        path = _make_outcomes_file(
            _delivery("d-025", req_id="REQ-025", title="REQ-025: Second edge research"),
        )
        ack_text = """
## [2026-03-25 12:00 UTC] — ACK REQ-025 IMPLEMENTED (S134)
text
"""
        cca_text = """
## [2026-03-28 01:00 UTC] — UPDATE 1 — REQ-025: Second edge research DELIVERED
"""
        r = self._make_resolver(path, ack_text=ack_text, cca_text=cca_text)
        result = r.run()
        os.unlink(path)
        matched_ids = [u["delivery_id"] for u in result["updates"]]
        # d-025 should appear exactly once in updates
        self.assertEqual(matched_ids.count("d-025"), 1)

    def test_total_deliveries_count(self):
        path = _make_outcomes_file(
            _delivery("d-001"),
            _delivery("d-002"),
            _delivery("d-003"),
        )
        r = self._make_resolver(path)
        result = r.run()
        os.unlink(path)
        self.assertEqual(result["total_deliveries"], 3)


# ---------------------------------------------------------------------------
# _normalize_status
# ---------------------------------------------------------------------------

class TestNormalizeStatus(unittest.TestCase):

    def test_implemented(self):
        self.assertEqual(_normalize_status("IMPLEMENTED"), "implemented")
        self.assertEqual(_normalize_status("implemented"), "implemented")

    def test_acknowledged(self):
        self.assertEqual(_normalize_status("ACKNOWLEDGED"), "acknowledged")
        self.assertEqual(_normalize_status("NOTED"), "acknowledged")
        self.assertEqual(_normalize_status("REVIEWED"), "acknowledged")

    def test_rejected(self):
        self.assertEqual(_normalize_status("REJECTED"), "rejected")

    def test_partial(self):
        self.assertEqual(_normalize_status("PARTIAL"), "acknowledged")

    def test_unknown_falls_back(self):
        # Unknown status should not crash
        result = _normalize_status("UNKNOWN_XYZ")
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# _fuzzy_match_score
# ---------------------------------------------------------------------------

class TestFuzzyMatchScore(unittest.TestCase):

    def test_exact_title_match(self):
        score = _fuzzy_match_score("Kelly criterion", "Kelly criterion paper", "")
        self.assertGreater(score, 0.5)

    def test_no_overlap(self):
        score = _fuzzy_match_score("XYZ12345", "Kelly criterion", "Bayesian methods")
        self.assertLess(score, 0.15)

    def test_partial_overlap(self):
        score = _fuzzy_match_score("Monte Carlo simulation", "Monte Carlo bankroll", "bankroll")
        self.assertGreater(score, 0.15)


# ---------------------------------------------------------------------------
# roi_by_category
# ---------------------------------------------------------------------------

class TestRoiByCategory(unittest.TestCase):

    def test_groups_by_category(self):
        deliveries = [
            {"category": "academic_paper", "status": "implemented", "profit_impact_cents": 100},
            {"category": "academic_paper", "status": "delivered", "profit_impact_cents": None},
            {"category": "tool", "status": "implemented", "profit_impact_cents": 50},
        ]
        result = roi_by_category(deliveries)
        self.assertIn("academic_paper", result)
        self.assertIn("tool", result)
        self.assertEqual(result["academic_paper"]["total"], 2)
        self.assertEqual(result["academic_paper"]["implemented"], 1)

    def test_empty_deliveries(self):
        result = roi_by_category([])
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
