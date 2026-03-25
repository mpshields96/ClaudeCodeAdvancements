"""Tests for outcomes_enricher.py — Enrich research_outcomes.jsonl with missing REQ entries."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from outcomes_enricher import (
    parse_req_deliveries,
    find_missing_reqs,
    build_outcome_entry,
    enrich_outcomes_file,
)


class TestParseReqDeliveries(unittest.TestCase):
    """Parse REQ delivery headers from CCA_TO_POLYBOT.md text."""

    def test_basic_delivery_header(self):
        text = "## [2026-03-24 16:00 UTC] — REQ-027 DELIVERY + TOPICS A-D RESPONSE — S151\n"
        result = parse_req_deliveries(text)
        self.assertIn("REQ-027", [r["req_id"] for r in result])

    def test_response_header(self):
        text = "## [2026-03-26 05:15 UTC] — REQ-037 RESPONSE — Maker-Side Limit Order Feasibility\n"
        result = parse_req_deliveries(text)
        found = [r for r in result if r["req_id"] == "REQ-037"]
        self.assertEqual(len(found), 1)
        self.assertIn("Maker-Side Limit Order", found[0]["title"])

    def test_complete_header(self):
        text = "## [2026-03-24 16:30 UTC] — REQ-028 COMPLETE DELIVERY: FLB Confirmed for Economic Data Contracts\n"
        result = parse_req_deliveries(text)
        found = [r for r in result if r["req_id"] == "REQ-028"]
        self.assertEqual(len(found), 1)

    def test_deduplicates_same_req(self):
        """Multiple headers for same REQ = one entry (first seen)."""
        text = (
            "## [2026-03-24 16:00 UTC] — REQ-027 DELIVERY — S151\n"
            "## [2026-03-24 15:27 UTC] — ACK: REQ-027 DELIVERY — S133\n"
        )
        result = parse_req_deliveries(text)
        req_027 = [r for r in result if r["req_id"] == "REQ-027"]
        self.assertEqual(len(req_027), 1)

    def test_extracts_session(self):
        text = "## [2026-03-24 16:00 UTC] — REQ-027 DELIVERY — S151\n"
        result = parse_req_deliveries(text)
        found = [r for r in result if r["req_id"] == "REQ-027"]
        self.assertEqual(found[0]["session"], 151)

    def test_extracts_date(self):
        text = "## [2026-03-26 04:30 UTC] — REQ-025 RESPONSE — Second Edge Research\n"
        result = parse_req_deliveries(text)
        found = [r for r in result if r["req_id"] == "REQ-025"]
        self.assertIn("2026-03-26", found[0]["date"])

    def test_empty_text(self):
        self.assertEqual(parse_req_deliveries(""), [])

    def test_no_req_headers(self):
        text = "## Just some random header\nSome body text\n"
        self.assertEqual(parse_req_deliveries(text), [])

    def test_update_header(self):
        text = "## [2026-03-25 ~UTC] — UPDATE 34 — REQ-034 + REQ-035 RESPONSES\n"
        result = parse_req_deliveries(text)
        ids = [r["req_id"] for r in result]
        self.assertIn("REQ-034", ids)
        self.assertIn("REQ-035", ids)

    def test_status_update_header(self):
        text = "## [2026-03-25 05:25 UTC] — STATUS UPDATE — Responding to: REQ-040 (2026-03-25 05:07 UTC)\n"
        result = parse_req_deliveries(text)
        ids = [r["req_id"] for r in result]
        self.assertIn("REQ-040", ids)


class TestFindMissingReqs(unittest.TestCase):
    """Identify REQ deliveries not yet in research_outcomes.jsonl."""

    def test_all_missing(self):
        deliveries = [{"req_id": "REQ-025"}, {"req_id": "REQ-027"}]
        existing = [{"delivery_id": "d-abc", "title": "something"}]
        missing = find_missing_reqs(deliveries, existing)
        self.assertEqual(len(missing), 2)

    def test_none_missing(self):
        deliveries = [{"req_id": "REQ-042"}]
        existing = [{"delivery_id": "d-abc", "req_id": "REQ-042"}]
        missing = find_missing_reqs(deliveries, existing)
        self.assertEqual(len(missing), 0)

    def test_partial_missing(self):
        deliveries = [{"req_id": "REQ-025"}, {"req_id": "REQ-042"}]
        existing = [{"delivery_id": "d-abc", "req_id": "REQ-042"}]
        missing = find_missing_reqs(deliveries, existing)
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["req_id"], "REQ-025")

    def test_empty_deliveries(self):
        self.assertEqual(find_missing_reqs([], [{"delivery_id": "d-abc"}]), [])

    def test_empty_existing(self):
        deliveries = [{"req_id": "REQ-025"}]
        missing = find_missing_reqs(deliveries, [])
        self.assertEqual(len(missing), 1)


class TestBuildOutcomeEntry(unittest.TestCase):
    """Build a properly formatted research_outcomes entry."""

    def test_has_required_fields(self):
        delivery = {"req_id": "REQ-027", "title": "Monte Carlo", "session": 151, "date": "2026-03-24"}
        entry = build_outcome_entry(delivery, category="tool")
        self.assertIn("delivery_id", entry)
        self.assertEqual(entry["req_id"], "REQ-027")
        self.assertEqual(entry["title"], "REQ-027: Monte Carlo")
        self.assertEqual(entry["session"], 151)
        self.assertEqual(entry["status"], "delivered")
        self.assertEqual(entry["category"], "tool")

    def test_delivery_id_format(self):
        delivery = {"req_id": "REQ-025", "title": "Edge Research", "session": 161}
        entry = build_outcome_entry(delivery)
        self.assertTrue(entry["delivery_id"].startswith("d-"))
        self.assertGreaterEqual(len(entry["delivery_id"]), 10)

    def test_has_created_at(self):
        delivery = {"req_id": "REQ-030", "title": "Spec", "session": 151}
        entry = build_outcome_entry(delivery)
        self.assertIn("created_at", entry)

    def test_default_category(self):
        delivery = {"req_id": "REQ-033", "title": "Analysis", "session": 155}
        entry = build_outcome_entry(delivery)
        self.assertEqual(entry["category"], "signal")

    def test_target_chat(self):
        delivery = {"req_id": "REQ-036", "title": "CLV Design", "session": 155}
        entry = build_outcome_entry(delivery)
        self.assertEqual(entry["target_chat"], "kalshi_monitoring")


class TestEnrichOutcomesFile(unittest.TestCase):
    """End-to-end enrichment of research_outcomes.jsonl."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.outcomes_path = os.path.join(self.tmpdir, "research_outcomes.jsonl")
        # Write one existing entry with req_id
        existing = {"delivery_id": "d-existing", "req_id": "REQ-042", "title": "Existing",
                     "session": 174, "status": "delivered", "category": "tool",
                     "target_chat": "kalshi_monitoring", "created_at": "2026-03-25"}
        with open(self.outcomes_path, "w") as f:
            f.write(json.dumps(existing) + "\n")

    def test_adds_missing_entries(self):
        deliveries = [
            {"req_id": "REQ-025", "title": "Second Edge Research", "session": 161, "date": "2026-03-26"},
            {"req_id": "REQ-042", "title": "Fill rate sim", "session": 174, "date": "2026-03-25"},
        ]
        added = enrich_outcomes_file(deliveries, self.outcomes_path)
        self.assertEqual(added, 1)  # Only REQ-025 is new
        with open(self.outcomes_path) as f:
            lines = [l for l in f if l.strip()]
        self.assertEqual(len(lines), 2)

    def test_does_not_duplicate(self):
        deliveries = [{"req_id": "REQ-042", "title": "Already exists", "session": 174}]
        added = enrich_outcomes_file(deliveries, self.outcomes_path)
        self.assertEqual(added, 0)

    def test_preserves_existing_entries(self):
        deliveries = [{"req_id": "REQ-027", "title": "New", "session": 151}]
        enrich_outcomes_file(deliveries, self.outcomes_path)
        with open(self.outcomes_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        self.assertEqual(lines[0]["delivery_id"], "d-existing")  # Original preserved

    def test_new_entries_have_req_id(self):
        deliveries = [{"req_id": "REQ-027", "title": "Monte Carlo", "session": 151}]
        enrich_outcomes_file(deliveries, self.outcomes_path)
        with open(self.outcomes_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        new_entry = lines[-1]
        self.assertEqual(new_entry["req_id"], "REQ-027")

    def test_returns_count_of_added(self):
        deliveries = [
            {"req_id": "REQ-025", "title": "A", "session": 161},
            {"req_id": "REQ-027", "title": "B", "session": 151},
            {"req_id": "REQ-028", "title": "C", "session": 151},
        ]
        added = enrich_outcomes_file(deliveries, self.outcomes_path)
        self.assertEqual(added, 3)


if __name__ == "__main__":
    unittest.main()
