#!/usr/bin/env python3
"""Tests for predictive_recommender.py — MT-28 Phase 5."""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from predictive_recommender import (
    PredictiveRecommender, Recommendation, RiskWarning, SessionProfile,
    MIN_RELEVANCE, MAX_RECOMMENDATIONS, RISK_THRESHOLD,
)
from principle_registry import Principle, _save_principle, VALID_DOMAINS


def _make_principle(text="Test principle", domain="cca_operations",
                    success=5, usage=10, last_session=100, **overrides):
    """Create a Principle with defaults."""
    from principle_registry import _generate_id, _now_iso
    pid = _generate_id(text, domain)
    p = Principle(
        id=pid,
        text=text,
        source_domain=domain,
        applicable_domains=[domain],
        success_count=success,
        usage_count=usage,
        created_session=50,
        last_used_session=last_session,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def _write_principles(principles: list, path: str):
    """Write principles to a JSONL file."""
    with open(path, 'w') as f:
        for p in principles:
            f.write(json.dumps(p.to_dict()) + "\n")


def _write_journal(entries: list, path: str):
    """Write journal entries to a JSONL file."""
    with open(path, 'w') as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


class TestRecommendBasics(unittest.TestCase):
    """Test basic recommendation generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")

    def tearDown(self):
        for f in [self.principles_path, self.journal_path]:
            if os.path.exists(f):
                os.unlink(f)
        os.rmdir(self.tmpdir)

    def test_no_principles_returns_empty(self):
        _write_principles([], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        result = rec.recommend(["cca_operations"])
        self.assertEqual(result, [])

    def test_no_domains_returns_empty(self):
        _write_principles([_make_principle()], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        result = rec.recommend([])
        self.assertEqual(result, [])

    def test_direct_domain_match(self):
        p = _make_principle(text="Always run tests", domain="cca_operations",
                            success=8, usage=10)
        _write_principles([p], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        result = rec.recommend(["cca_operations"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].principle_text, "Always run tests")
        self.assertGreater(result[0].relevance, 0.5)

    def test_no_match_filtered_out(self):
        p = _make_principle(text="Trading tip", domain="trading_execution",
                            success=8, usage=10)
        _write_principles([p], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        # nuclear_scan has low affinity to trading_execution
        result = rec.recommend(["nuclear_scan"])
        # Should be filtered or very low relevance
        if result:
            self.assertLess(result[0].relevance, 0.5)

    def test_pruned_principles_excluded(self):
        p = _make_principle(text="Pruned one", domain="cca_operations",
                            pruned=True)
        _write_principles([p], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        result = rec.recommend(["cca_operations"])
        self.assertEqual(result, [])

    def test_multiple_principles_sorted_by_relevance(self):
        p1 = _make_principle(text="Strong principle", domain="cca_operations",
                             success=9, usage=10, last_session=108)
        p2 = _make_principle(text="Weak principle", domain="cca_operations",
                             success=3, usage=10, last_session=50)
        _write_principles([p1, p2], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        result = rec.recommend(["cca_operations"], current_session=110)
        self.assertEqual(len(result), 2)
        self.assertGreater(result[0].relevance, result[1].relevance)

    def test_max_results_respected(self):
        principles = []
        for i in range(15):
            p = _make_principle(text=f"Principle {i}", domain="cca_operations",
                                success=5+i, usage=10+i)
            principles.append(p)
        _write_principles(principles, self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        result = rec.recommend(["cca_operations"], max_results=5)
        self.assertLessEqual(len(result), 5)


class TestDomainRelevance(unittest.TestCase):
    """Test domain relevance scoring."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")

    def tearDown(self):
        for f in [self.principles_path, self.journal_path]:
            if os.path.exists(f):
                os.unlink(f)
        os.rmdir(self.tmpdir)

    def test_direct_match_is_1(self):
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        p = _make_principle(domain="cca_operations")
        relevance = rec._domain_relevance(p, ["cca_operations"])
        self.assertEqual(relevance, 1.0)

    def test_applicable_domain_match(self):
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        p = _make_principle(domain="cca_operations",
                            applicable_domains=["cca_operations", "session_management"])
        relevance = rec._domain_relevance(p, ["session_management"])
        self.assertEqual(relevance, 1.0)

    def test_affinity_based_match(self):
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        p = _make_principle(domain="trading_research")
        relevance = rec._domain_relevance(p, ["trading_execution"])
        # trading_research -> trading_execution has high affinity
        self.assertGreater(relevance, 0.5)

    def test_no_match_is_zero(self):
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        p = _make_principle(domain="trading_execution",
                            applicable_domains=["trading_execution"])
        # If no affinity defined between these specific domains
        relevance = rec._domain_relevance(p, ["nuclear_scan"])
        self.assertLessEqual(relevance, 0.3)

    def test_multiple_planned_domains_max(self):
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        p = _make_principle(domain="cca_operations")
        # One direct match + one no match = should return 1.0 (max)
        relevance = rec._domain_relevance(p, ["cca_operations", "trading_execution"])
        self.assertEqual(relevance, 1.0)


class TestRecencyWeight(unittest.TestCase):
    """Test recency-based weighting."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.rec = PredictiveRecommender(
            os.path.join(self.tmpdir, "p.jsonl"),
            os.path.join(self.tmpdir, "j.jsonl")
        )

    def tearDown(self):
        os.rmdir(self.tmpdir)

    def test_recent_principle_high_weight(self):
        p = _make_principle(last_session=109)
        weight = self.rec._recency_weight(p, current_session=110)
        self.assertGreater(weight, 0.9)

    def test_old_principle_low_weight(self):
        p = _make_principle(last_session=10)
        weight = self.rec._recency_weight(p, current_session=110)
        self.assertLess(weight, 0.5)

    def test_no_session_info_neutral(self):
        p = _make_principle(last_session=0)
        weight = self.rec._recency_weight(p, current_session=0)
        self.assertEqual(weight, 0.5)

    def test_same_session_max_weight(self):
        p = _make_principle(last_session=110)
        weight = self.rec._recency_weight(p, current_session=110)
        self.assertEqual(weight, 1.0)

    def test_weight_never_below_floor(self):
        p = _make_principle(last_session=1)
        weight = self.rec._recency_weight(p, current_session=10000)
        self.assertGreaterEqual(weight, 0.1)


class TestCategories(unittest.TestCase):
    """Test recommendation categorization."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.rec = PredictiveRecommender(
            os.path.join(self.tmpdir, "p.jsonl"),
            os.path.join(self.tmpdir, "j.jsonl")
        )

    def tearDown(self):
        os.rmdir(self.tmpdir)

    def test_reinforced_direct_match(self):
        p = _make_principle(domain="cca_operations", success=8, usage=10)
        cat = self.rec._categorize(p, 1.0, ["cca_operations"])
        self.assertEqual(cat, "reinforce")

    def test_caution_low_score(self):
        p = _make_principle(domain="cca_operations", success=1, usage=10)
        cat = self.rec._categorize(p, 1.0, ["cca_operations"])
        self.assertEqual(cat, "caution")

    def test_transfer_indirect_match(self):
        p = _make_principle(domain="trading_research", success=8, usage=10)
        cat = self.rec._categorize(p, 0.5, ["cca_operations"])
        self.assertEqual(cat, "transfer")

    def test_emerging_low_usage(self):
        p = _make_principle(domain="cca_operations", success=2, usage=3)
        cat = self.rec._categorize(p, 1.0, ["cca_operations"])
        self.assertEqual(cat, "emerging")


class TestRiskWarnings(unittest.TestCase):
    """Test risk identification."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")

    def tearDown(self):
        for f in [self.principles_path, self.journal_path]:
            if os.path.exists(f):
                os.unlink(f)
        if os.path.exists(self.tmpdir):
            os.rmdir(self.tmpdir)

    def test_no_risks_when_all_good(self):
        p = _make_principle(success=8, usage=10, domain="cca_operations")
        _write_principles([p], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        risks = rec.get_risks(["cca_operations"])
        self.assertEqual(risks, [])

    def test_high_risk_flagged(self):
        p = _make_principle(text="Bad approach", domain="cca_operations",
                            success=0, usage=12)
        _write_principles([p], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        risks = rec.get_risks(["cca_operations"])
        self.assertEqual(len(risks), 1)
        self.assertEqual(risks[0].risk_level, "high")
        self.assertIn("Consistently fails", risks[0].warning)

    def test_medium_risk_flagged(self):
        p = _make_principle(text="Weak approach", domain="cca_operations",
                            success=1, usage=8)
        _write_principles([p], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        risks = rec.get_risks(["cca_operations"])
        self.assertEqual(len(risks), 1)
        self.assertEqual(risks[0].risk_level, "medium")

    def test_low_usage_not_flagged(self):
        p = _make_principle(text="New bad", domain="cca_operations",
                            success=0, usage=2)
        _write_principles([p], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        risks = rec.get_risks(["cca_operations"])
        self.assertEqual(risks, [])

    def test_irrelevant_domain_not_flagged(self):
        p = _make_principle(text="Bad trading", domain="trading_execution",
                            success=0, usage=12,
                            applicable_domains=["trading_execution"])
        _write_principles([p], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        risks = rec.get_risks(["nuclear_scan"])
        # trading_execution has very low affinity to nuclear_scan
        self.assertEqual(risks, [])

    def test_risks_sorted_by_severity(self):
        p1 = _make_principle(text="Medium risk", domain="cca_operations",
                             success=1, usage=8)
        p2 = _make_principle(text="High risk", domain="cca_operations",
                             success=0, usage=15)
        _write_principles([p1, p2], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        risks = rec.get_risks(["cca_operations"])
        self.assertEqual(len(risks), 2)
        self.assertEqual(risks[0].risk_level, "high")
        self.assertEqual(risks[1].risk_level, "medium")

    def test_no_domains_returns_empty(self):
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        self.assertEqual(rec.get_risks([]), [])


class TestFormatInjection(unittest.TestCase):
    """Test injectable text generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")

    def tearDown(self):
        for f in [self.principles_path, self.journal_path]:
            if os.path.exists(f):
                os.unlink(f)
        if os.path.exists(self.tmpdir):
            os.rmdir(self.tmpdir)

    def test_empty_when_no_data(self):
        _write_principles([], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        text = rec.format_injection(["cca_operations"])
        self.assertEqual(text, "")

    def test_includes_proven_section(self):
        p = _make_principle(text="Commit after tests", domain="cca_operations",
                            success=9, usage=10)
        _write_principles([p], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        text = rec.format_injection(["cca_operations"])
        self.assertIn("Proven principles", text)
        self.assertIn("Commit after tests", text)

    def test_includes_risk_section(self):
        p = _make_principle(text="Rush shipping", domain="cca_operations",
                            success=0, usage=12)
        _write_principles([p], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        text = rec.format_injection(["cca_operations"])
        self.assertIn("Risk warnings", text)
        self.assertIn("Rush shipping", text)


class TestSessionProfiles(unittest.TestCase):
    """Test journal-based session profile extraction."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")

    def tearDown(self):
        for f in [self.journal_path, self.principles_path]:
            if os.path.exists(f):
                os.unlink(f)
        if os.path.exists(self.tmpdir):
            os.rmdir(self.tmpdir)

    def test_no_journal_returns_empty(self):
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        profiles = rec._get_session_profiles()
        self.assertEqual(profiles, [])

    def test_extracts_sessions(self):
        entries = [
            {"session": 100, "type": "task_complete", "domain": "cca_operations",
             "timestamp": "2026-03-20T10:00:00Z"},
            {"session": 100, "type": "test_run", "test_count": 6000,
             "timestamp": "2026-03-20T11:00:00Z"},
            {"session": 101, "type": "task_complete", "domain": "trading_research",
             "timestamp": "2026-03-21T10:00:00Z", "grade": "A"},
        ]
        _write_journal(entries, self.journal_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        profiles = rec._get_session_profiles()
        self.assertEqual(len(profiles), 2)
        # Most recent first
        self.assertEqual(profiles[0].session_number, 101)
        self.assertEqual(profiles[0].grade, "A")
        self.assertEqual(profiles[1].session_number, 100)
        self.assertIn("cca_operations", profiles[1].domains_touched)

    def test_skips_invalid_json(self):
        with open(self.journal_path, 'w') as f:
            f.write('{"session": 1, "type": "ok"}\n')
            f.write('not json\n')
            f.write('{"session": 2, "type": "ok"}\n')
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        profiles = rec._get_session_profiles()
        self.assertEqual(len(profiles), 2)

    def test_limit_respected(self):
        entries = [{"session": i, "type": "task"} for i in range(1, 101)]
        _write_journal(entries, self.journal_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        profiles = rec._get_session_profiles(limit=10)
        self.assertEqual(len(profiles), 10)
        self.assertEqual(profiles[0].session_number, 100)

    def test_deduplicates_event_types(self):
        entries = [
            {"session": 1, "type": "task_complete"},
            {"session": 1, "type": "task_complete"},
            {"session": 1, "type": "test_run"},
        ]
        _write_journal(entries, self.journal_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        profiles = rec._get_session_profiles()
        self.assertEqual(len(profiles[0].event_types), 2)


class TestSerialization(unittest.TestCase):
    """Test to_dict methods."""

    def test_recommendation_to_dict(self):
        r = Recommendation(
            principle_id="prin_test1234",
            principle_text="Test",
            source_domain="cca_operations",
            relevance=0.85,
            reason="good",
            category="reinforce",
            principle_score=0.9,
            usage_count=10,
        )
        d = r.to_dict()
        self.assertEqual(d["principle_id"], "prin_test1234")
        self.assertEqual(d["relevance"], 0.85)
        self.assertEqual(d["category"], "reinforce")

    def test_risk_warning_to_dict(self):
        r = RiskWarning(
            principle_id="prin_bad12345",
            principle_text="Bad idea",
            domain="cca_operations",
            score=0.15,
            usage_count=20,
            risk_level="high",
            warning="Don't do this",
        )
        d = r.to_dict()
        self.assertEqual(d["risk_level"], "high")
        self.assertEqual(d["score"], 0.15)


class TestSummary(unittest.TestCase):
    """Test summary output."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")

    def tearDown(self):
        for f in [self.principles_path, self.journal_path]:
            if os.path.exists(f):
                os.unlink(f)
        if os.path.exists(self.tmpdir):
            os.rmdir(self.tmpdir)

    def test_summary_with_data(self):
        p = _make_principle(text="Good practice", domain="cca_operations",
                            success=8, usage=10)
        _write_principles([p], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        summary = rec.summary(["cca_operations"], current_session=111)
        self.assertIn("Recommendations", summary)
        self.assertIn("Good practice", summary)

    def test_summary_empty(self):
        _write_principles([], self.principles_path)
        rec = PredictiveRecommender(self.principles_path, self.journal_path)
        summary = rec.summary(["cca_operations"])
        self.assertIn("No principles found", summary)


if __name__ == "__main__":
    unittest.main()
