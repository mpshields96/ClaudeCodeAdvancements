#!/usr/bin/env python3
"""Tests for meta_learning_dashboard.py — MT-49 Phase 1.

Tracks self-learning system effectiveness across sessions.
Reads all self-learning JSONL files and computes meta-metrics:
- Principle accuracy trend (are high-scored principles actually correct?)
- Session grade trend (are sessions getting better over time?)
- Improvement success rate (do proposed improvements actually help?)
- Research ROI (which CCA deliveries led to Kalshi profits?)
- Data freshness (when was each data source last updated?)
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add parent dirs to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestPrincipleEffectiveness(unittest.TestCase):
    """Test principle registry effectiveness analysis."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_file = os.path.join(self.tmpdir, "principles.jsonl")

    def _write_principles(self, entries):
        with open(self.principles_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_load_principles_empty_file(self):
        from meta_learning_dashboard import PrincipleAnalyzer
        with open(self.principles_file, "w") as f:
            pass
        pa = PrincipleAnalyzer(self.principles_file)
        self.assertEqual(pa.total_principles, 0)

    def test_load_principles_counts(self):
        from meta_learning_dashboard import PrincipleAnalyzer
        self._write_principles([
            {"id": "p1", "text": "Test first", "success_count": 5, "usage_count": 6,
             "source_domain": "cca", "applicable_domains": ["cca"], "pruned": False,
             "created_session": 10, "last_used_session": 50},
            {"id": "p2", "text": "Commit often", "success_count": 3, "usage_count": 10,
             "source_domain": "cca", "applicable_domains": ["cca"], "pruned": False,
             "created_session": 20, "last_used_session": 40},
            {"id": "p3", "text": "Old bad", "success_count": 1, "usage_count": 10,
             "source_domain": "cca", "applicable_domains": ["cca"], "pruned": True,
             "created_session": 5, "last_used_session": 15},
        ])
        pa = PrincipleAnalyzer(self.principles_file)
        self.assertEqual(pa.total_principles, 3)
        self.assertEqual(pa.active_principles, 2)
        self.assertEqual(pa.pruned_principles, 1)

    def test_average_score(self):
        from meta_learning_dashboard import PrincipleAnalyzer
        self._write_principles([
            {"id": "p1", "text": "A", "success_count": 8, "usage_count": 10,
             "source_domain": "cca", "applicable_domains": ["cca"], "pruned": False,
             "created_session": 10, "last_used_session": 50},
            {"id": "p2", "text": "B", "success_count": 2, "usage_count": 10,
             "source_domain": "cca", "applicable_domains": ["cca"], "pruned": False,
             "created_session": 20, "last_used_session": 40},
        ])
        pa = PrincipleAnalyzer(self.principles_file)
        # Laplace: (8+1)/(10+2)=0.75, (2+1)/(10+2)=0.25 -> avg 0.5
        self.assertAlmostEqual(pa.average_score, 0.5, places=2)

    def test_domain_distribution(self):
        from meta_learning_dashboard import PrincipleAnalyzer
        self._write_principles([
            {"id": "p1", "text": "A", "success_count": 5, "usage_count": 6,
             "source_domain": "cca", "applicable_domains": ["cca"], "pruned": False,
             "created_session": 10, "last_used_session": 50},
            {"id": "p2", "text": "B", "success_count": 3, "usage_count": 4,
             "source_domain": "trading", "applicable_domains": ["trading"], "pruned": False,
             "created_session": 20, "last_used_session": 40},
            {"id": "p3", "text": "C", "success_count": 2, "usage_count": 3,
             "source_domain": "trading", "applicable_domains": ["trading"], "pruned": False,
             "created_session": 30, "last_used_session": 45},
        ])
        pa = PrincipleAnalyzer(self.principles_file)
        dist = pa.domain_distribution
        self.assertEqual(dist["cca"], 1)
        self.assertEqual(dist["trading"], 2)

    def test_top_principles(self):
        from meta_learning_dashboard import PrincipleAnalyzer
        self._write_principles([
            {"id": "p1", "text": "High scorer", "success_count": 9, "usage_count": 10,
             "source_domain": "cca", "applicable_domains": ["cca"], "pruned": False,
             "created_session": 10, "last_used_session": 50},
            {"id": "p2", "text": "Low scorer", "success_count": 1, "usage_count": 10,
             "source_domain": "cca", "applicable_domains": ["cca"], "pruned": False,
             "created_session": 20, "last_used_session": 40},
        ])
        pa = PrincipleAnalyzer(self.principles_file)
        top = pa.top_principles(n=1)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0]["id"], "p1")

    def test_stale_principles(self):
        """Principles not used in 50+ sessions should be flagged stale."""
        from meta_learning_dashboard import PrincipleAnalyzer
        self._write_principles([
            {"id": "p1", "text": "Fresh", "success_count": 5, "usage_count": 6,
             "source_domain": "cca", "applicable_domains": ["cca"], "pruned": False,
             "created_session": 10, "last_used_session": 160},
            {"id": "p2", "text": "Stale", "success_count": 5, "usage_count": 6,
             "source_domain": "cca", "applicable_domains": ["cca"], "pruned": False,
             "created_session": 10, "last_used_session": 50},
        ])
        pa = PrincipleAnalyzer(self.principles_file)
        stale = pa.stale_principles(current_session=169, staleness_threshold=50)
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["id"], "p2")


class TestSessionGradeTrend(unittest.TestCase):
    """Test session outcome trend analysis."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.outcomes_file = os.path.join(self.tmpdir, "session_outcomes.jsonl")

    def _write_outcomes(self, entries):
        with open(self.outcomes_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_load_empty(self):
        from meta_learning_dashboard import SessionTrendAnalyzer
        with open(self.outcomes_file, "w") as f:
            pass
        sta = SessionTrendAnalyzer(self.outcomes_file)
        self.assertEqual(sta.total_sessions, 0)

    def test_grade_counts(self):
        from meta_learning_dashboard import SessionTrendAnalyzer
        self._write_outcomes([
            {"session_id": 1, "grade": "A", "commits": 3, "tests_added": 10, "tests_total": 100,
             "timestamp": "2026-03-20T00:00:00Z"},
            {"session_id": 2, "grade": "A", "commits": 2, "tests_added": 5, "tests_total": 105,
             "timestamp": "2026-03-21T00:00:00Z"},
            {"session_id": 3, "grade": "B", "commits": 1, "tests_added": 3, "tests_total": 108,
             "timestamp": "2026-03-22T00:00:00Z"},
        ])
        sta = SessionTrendAnalyzer(self.outcomes_file)
        self.assertEqual(sta.total_sessions, 3)
        self.assertEqual(sta.grade_counts["A"], 2)
        self.assertEqual(sta.grade_counts["B"], 1)

    def test_grade_trend_improving(self):
        """Grade numeric values should show improving trend."""
        from meta_learning_dashboard import SessionTrendAnalyzer
        self._write_outcomes([
            {"session_id": 1, "grade": "C", "commits": 1, "tests_added": 1, "tests_total": 50,
             "timestamp": "2026-03-18T00:00:00Z"},
            {"session_id": 2, "grade": "B", "commits": 2, "tests_added": 5, "tests_total": 55,
             "timestamp": "2026-03-19T00:00:00Z"},
            {"session_id": 3, "grade": "A", "commits": 3, "tests_added": 10, "tests_total": 65,
             "timestamp": "2026-03-20T00:00:00Z"},
        ])
        sta = SessionTrendAnalyzer(self.outcomes_file)
        self.assertEqual(sta.trend_direction, "improving")

    def test_grade_trend_stable(self):
        from meta_learning_dashboard import SessionTrendAnalyzer
        self._write_outcomes([
            {"session_id": 1, "grade": "A", "commits": 3, "tests_added": 10, "tests_total": 100,
             "timestamp": "2026-03-18T00:00:00Z"},
            {"session_id": 2, "grade": "A", "commits": 3, "tests_added": 10, "tests_total": 110,
             "timestamp": "2026-03-19T00:00:00Z"},
            {"session_id": 3, "grade": "A", "commits": 3, "tests_added": 10, "tests_total": 120,
             "timestamp": "2026-03-20T00:00:00Z"},
        ])
        sta = SessionTrendAnalyzer(self.outcomes_file)
        self.assertEqual(sta.trend_direction, "stable")

    def test_test_velocity(self):
        """Tests per session average."""
        from meta_learning_dashboard import SessionTrendAnalyzer
        self._write_outcomes([
            {"session_id": 1, "grade": "A", "commits": 3, "tests_added": 20, "tests_total": 100,
             "timestamp": "2026-03-18T00:00:00Z"},
            {"session_id": 2, "grade": "A", "commits": 2, "tests_added": 30, "tests_total": 130,
             "timestamp": "2026-03-19T00:00:00Z"},
        ])
        sta = SessionTrendAnalyzer(self.outcomes_file)
        self.assertAlmostEqual(sta.avg_tests_per_session, 25.0, places=1)

    def test_commit_velocity(self):
        from meta_learning_dashboard import SessionTrendAnalyzer
        self._write_outcomes([
            {"session_id": 1, "grade": "A", "commits": 4, "tests_added": 10, "tests_total": 100,
             "timestamp": "2026-03-18T00:00:00Z"},
            {"session_id": 2, "grade": "A", "commits": 6, "tests_added": 10, "tests_total": 110,
             "timestamp": "2026-03-19T00:00:00Z"},
        ])
        sta = SessionTrendAnalyzer(self.outcomes_file)
        self.assertAlmostEqual(sta.avg_commits_per_session, 5.0, places=1)


class TestImprovementTracker(unittest.TestCase):
    """Test improvement proposal success rate tracking."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.improvements_file = os.path.join(self.tmpdir, "improvements.jsonl")

    def _write_improvements(self, entries):
        with open(self.improvements_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_empty_file(self):
        from meta_learning_dashboard import ImprovementTracker
        with open(self.improvements_file, "w") as f:
            pass
        it = ImprovementTracker(self.improvements_file)
        self.assertEqual(it.total_proposals, 0)
        self.assertIsNone(it.success_rate)

    def test_success_rate(self):
        from meta_learning_dashboard import ImprovementTracker
        self._write_improvements([
            {"id": "i1", "status": "implemented", "outcome": "success", "pattern_type": "retry_loop",
             "session_id": 30},
            {"id": "i2", "status": "implemented", "outcome": "failure", "pattern_type": "doc_drift",
             "session_id": 31},
            {"id": "i3", "status": "implemented", "outcome": "success", "pattern_type": "retry_loop",
             "session_id": 32},
            {"id": "i4", "status": "proposed", "outcome": None, "pattern_type": "waste",
             "session_id": 33},
        ])
        it = ImprovementTracker(self.improvements_file)
        self.assertEqual(it.total_proposals, 4)
        self.assertEqual(it.implemented_count, 3)
        # 2 success out of 3 implemented
        self.assertAlmostEqual(it.success_rate, 2/3, places=2)

    def test_pattern_type_distribution(self):
        from meta_learning_dashboard import ImprovementTracker
        self._write_improvements([
            {"id": "i1", "status": "implemented", "outcome": "success", "pattern_type": "retry_loop",
             "session_id": 30},
            {"id": "i2", "status": "implemented", "outcome": "success", "pattern_type": "retry_loop",
             "session_id": 31},
            {"id": "i3", "status": "proposed", "outcome": None, "pattern_type": "doc_drift",
             "session_id": 32},
        ])
        it = ImprovementTracker(self.improvements_file)
        dist = it.pattern_type_distribution
        self.assertEqual(dist["retry_loop"], 2)
        self.assertEqual(dist["doc_drift"], 1)


class TestResearchROI(unittest.TestCase):
    """Test research delivery ROI tracking."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.research_file = os.path.join(self.tmpdir, "research_outcomes.jsonl")

    def _write_research(self, entries):
        with open(self.research_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_empty(self):
        from meta_learning_dashboard import ResearchROITracker
        with open(self.research_file, "w") as f:
            pass
        rt = ResearchROITracker(self.research_file)
        self.assertEqual(rt.total_deliveries, 0)

    def test_delivery_status_counts(self):
        from meta_learning_dashboard import ResearchROITracker
        self._write_research([
            {"delivery_id": "d1", "status": "delivered", "category": "academic_paper",
             "title": "Paper A", "session": 50},
            {"delivery_id": "d2", "status": "implemented", "category": "code",
             "title": "Tool B", "session": 55},
            {"delivery_id": "d3", "status": "rejected", "category": "framework",
             "title": "Framework C", "session": 60},
            {"delivery_id": "d4", "status": "delivered", "category": "detector",
             "title": "Detector D", "session": 65},
        ])
        rt = ResearchROITracker(self.research_file)
        self.assertEqual(rt.total_deliveries, 4)
        self.assertEqual(rt.status_counts["delivered"], 2)
        self.assertEqual(rt.status_counts["implemented"], 1)
        self.assertEqual(rt.status_counts["rejected"], 1)

    def test_implementation_rate(self):
        from meta_learning_dashboard import ResearchROITracker
        self._write_research([
            {"delivery_id": "d1", "status": "implemented", "category": "code",
             "title": "A", "session": 50},
            {"delivery_id": "d2", "status": "delivered", "category": "code",
             "title": "B", "session": 55},
        ])
        rt = ResearchROITracker(self.research_file)
        self.assertAlmostEqual(rt.implementation_rate, 0.5, places=2)


class TestMetaLearningDashboard(unittest.TestCase):
    """Test the top-level dashboard aggregator."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create minimal data files
        for fname in ["principles.jsonl", "improvements.jsonl",
                      "research_outcomes.jsonl", "session_outcomes.jsonl",
                      "journal.jsonl"]:
            with open(os.path.join(self.tmpdir, fname), "w") as f:
                pass

    def test_dashboard_from_empty_data(self):
        from meta_learning_dashboard import MetaLearningDashboard
        d = MetaLearningDashboard(data_dir=self.tmpdir)
        report = d.generate_report()
        self.assertIn("principles", report)
        self.assertIn("sessions", report)
        self.assertIn("improvements", report)
        self.assertIn("research", report)
        self.assertIn("summary", report)

    def test_dashboard_summary_keys(self):
        from meta_learning_dashboard import MetaLearningDashboard
        d = MetaLearningDashboard(data_dir=self.tmpdir)
        report = d.generate_report()
        summary = report["summary"]
        self.assertIn("overall_health", summary)
        self.assertIn("data_sources_active", summary)
        self.assertIn("recommendations", summary)

    def test_dashboard_health_with_no_data(self):
        from meta_learning_dashboard import MetaLearningDashboard
        d = MetaLearningDashboard(data_dir=self.tmpdir)
        report = d.generate_report()
        # No data = UNKNOWN health
        self.assertEqual(report["summary"]["overall_health"], "UNKNOWN")

    def test_dashboard_json_serializable(self):
        from meta_learning_dashboard import MetaLearningDashboard
        d = MetaLearningDashboard(data_dir=self.tmpdir)
        report = d.generate_report()
        # Must be JSON-serializable
        json_str = json.dumps(report)
        self.assertIsInstance(json_str, str)

    def test_dashboard_with_real_data(self):
        """Test with minimal real-looking data."""
        from meta_learning_dashboard import MetaLearningDashboard
        # Write principle data
        with open(os.path.join(self.tmpdir, "principles.jsonl"), "w") as f:
            f.write(json.dumps({"id": "p1", "text": "TDD always", "success_count": 8,
                                "usage_count": 10, "source_domain": "cca",
                                "applicable_domains": ["cca"], "pruned": False,
                                "created_session": 10, "last_used_session": 160}) + "\n")
        # Write session data
        with open(os.path.join(self.tmpdir, "session_outcomes.jsonl"), "w") as f:
            f.write(json.dumps({"session_id": 168, "grade": "A", "commits": 3,
                                "tests_added": 50, "tests_total": 9473,
                                "timestamp": "2026-03-26T00:00:00Z"}) + "\n")
        d = MetaLearningDashboard(data_dir=self.tmpdir)
        report = d.generate_report()
        self.assertEqual(report["principles"]["total"], 1)
        self.assertEqual(report["sessions"]["total"], 1)


class TestJournalAnalyzer(unittest.TestCase):
    """Test journal event analysis."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.journal_file = os.path.join(self.tmpdir, "journal.jsonl")

    def _write_journal(self, entries):
        with open(self.journal_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_empty_journal(self):
        from meta_learning_dashboard import JournalAnalyzer
        with open(self.journal_file, "w") as f:
            pass
        ja = JournalAnalyzer(self.journal_file)
        self.assertEqual(ja.total_events, 0)

    def test_event_type_counts(self):
        from meta_learning_dashboard import JournalAnalyzer
        self._write_journal([
            {"event_type": "session_outcome", "timestamp": "2026-03-20T00:00:00Z",
             "session_id": 1, "domain": "cca"},
            {"event_type": "session_outcome", "timestamp": "2026-03-21T00:00:00Z",
             "session_id": 2, "domain": "cca"},
            {"event_type": "pattern_detected", "timestamp": "2026-03-22T00:00:00Z",
             "session_id": 3, "domain": "trading"},
        ])
        ja = JournalAnalyzer(self.journal_file)
        self.assertEqual(ja.total_events, 3)
        self.assertEqual(ja.event_type_counts["session_outcome"], 2)
        self.assertEqual(ja.event_type_counts["pattern_detected"], 1)

    def test_domain_coverage(self):
        from meta_learning_dashboard import JournalAnalyzer
        self._write_journal([
            {"event_type": "session_outcome", "timestamp": "2026-03-20T00:00:00Z",
             "session_id": 1, "domain": "cca"},
            {"event_type": "session_outcome", "timestamp": "2026-03-21T00:00:00Z",
             "session_id": 2, "domain": "trading"},
            {"event_type": "pattern_detected", "timestamp": "2026-03-22T00:00:00Z",
             "session_id": 3, "domain": "code_quality"},
        ])
        ja = JournalAnalyzer(self.journal_file)
        domains = ja.domains_covered
        self.assertIn("cca", domains)
        self.assertIn("trading", domains)
        self.assertIn("code_quality", domains)


class TestCLI(unittest.TestCase):
    """Test CLI output modes."""

    def test_cli_json_flag(self):
        """--json flag should produce valid JSON."""
        from meta_learning_dashboard import MetaLearningDashboard
        # Just verify the report is JSON-serializable (CLI wraps this)
        tmpdir = tempfile.mkdtemp()
        for fname in ["principles.jsonl", "improvements.jsonl",
                      "research_outcomes.jsonl", "session_outcomes.jsonl",
                      "journal.jsonl"]:
            with open(os.path.join(tmpdir, fname), "w") as f:
                pass
        d = MetaLearningDashboard(data_dir=tmpdir)
        report = d.generate_report()
        self.assertIsInstance(json.dumps(report), str)

    def test_cli_brief_output(self):
        """Brief mode should return a short string."""
        from meta_learning_dashboard import MetaLearningDashboard
        tmpdir = tempfile.mkdtemp()
        for fname in ["principles.jsonl", "improvements.jsonl",
                      "research_outcomes.jsonl", "session_outcomes.jsonl",
                      "journal.jsonl"]:
            with open(os.path.join(tmpdir, fname), "w") as f:
                pass
        d = MetaLearningDashboard(data_dir=tmpdir)
        brief = d.brief_summary()
        self.assertIsInstance(brief, str)
        self.assertGreater(len(brief), 10)


if __name__ == "__main__":
    unittest.main()
