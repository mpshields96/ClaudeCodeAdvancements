#!/usr/bin/env python3
"""
test_meta_learning_dashboard.py — MT-49 Phase 1 test coverage.

Tests for self-learning/meta_learning_dashboard.py components:
- PrincipleAnalyzer: metrics on principle registry
- SessionTrendAnalyzer: session grade trends
- ImprovementTracker: improvement proposal success
- ResearchROITracker: research delivery ROI
- JournalAnalyzer: journal event coverage
- MetaLearningDashboard: top-level aggregator + CLI
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Set up path for self-learning submodule
sys.path.insert(0, str(Path(__file__).parent.parent / "self-learning"))
sys.path.insert(0, str(Path(__file__).parent.parent))
from meta_learning_dashboard import (
    PrincipleAnalyzer,
    SessionTrendAnalyzer,
    ImprovementTracker,
    ResearchROITracker,
    JournalAnalyzer,
    MetaLearningDashboard,
    _laplace_score,
    _load_jsonl,
)

# Real method names (verified against implementation)
# SessionTrendAnalyzer: total_sessions, grade_counts, trend_direction, avg_tests_per_session
# ImprovementTracker: total_proposals, implemented_count, success_rate
# ResearchROITracker: total_deliveries, status_counts, implementation_rate
# JournalAnalyzer: total_events, event_type_counts, domains_covered
# MetaLearningDashboard: generate_report(), brief_summary(), _compute_health()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: str, records: list) -> None:
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _principle(pid, domain="cca", usage=0, success=0, pruned=False, last_used=100):
    return {
        "id": pid, "text": f"Principle {pid}", "source_domain": domain,
        "usage_count": usage, "success_count": success,
        "pruned": pruned, "last_used_session": last_used,
        "created_session": 50,
    }


def _session(sid, grade, commits=2, tests=100):
    return {
        "session_id": sid, "grade": grade,
        "commits": commits, "tests": tests,
        "timestamp": f"2026-03-{sid:02d}T10:00:00Z",
    }


# ---------------------------------------------------------------------------
# LaPlace score
# ---------------------------------------------------------------------------

class TestLaplaceScore(unittest.TestCase):
    def test_zero_usage(self):
        """Zero usage → 0.5 (uniform prior)."""
        self.assertAlmostEqual(_laplace_score(0, 0), 0.5)

    def test_all_success(self):
        """All successes → approaches 1.0."""
        score = _laplace_score(10, 10)
        self.assertGreater(score, 0.9)

    def test_no_success(self):
        """No successes → approaches 0.0."""
        score = _laplace_score(0, 10)
        self.assertLess(score, 0.15)

    def test_half_success(self):
        """50% success → near 0.5."""
        score = _laplace_score(5, 10)
        self.assertAlmostEqual(score, 0.5, delta=0.1)


# ---------------------------------------------------------------------------
# PrincipleAnalyzer
# ---------------------------------------------------------------------------

class TestPrincipleAnalyzer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        records = [
            _principle("P1", domain="cca", usage=10, success=8),
            _principle("P2", domain="kalshi", usage=5, success=2),
            _principle("P3", domain="cca", pruned=True),
        ]
        _write_jsonl(self.tmp.name, records)
        self.pa = PrincipleAnalyzer(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_total_principles(self):
        self.assertEqual(self.pa.total_principles, 3)

    def test_active_principles(self):
        """Pruned principles excluded from active count."""
        self.assertEqual(self.pa.active_principles, 2)

    def test_pruned_principles(self):
        self.assertEqual(self.pa.pruned_principles, 1)

    def test_average_score_non_zero(self):
        """Average score should be > 0 with usage data."""
        self.assertGreater(self.pa.average_score, 0.0)

    def test_domain_distribution(self):
        dist = self.pa.domain_distribution
        self.assertIn("cca", dist)
        self.assertIn("kalshi", dist)
        self.assertEqual(dist["cca"], 1)   # P3 is pruned, only P1 active for cca
        self.assertEqual(dist["kalshi"], 1)

    def test_top_principles_ordering(self):
        """Top principles ordered by descending score."""
        tops = self.pa.top_principles(2)
        self.assertEqual(len(tops), 2)
        score0 = tops[0].get("success_count", 0) / max(tops[0].get("usage_count", 1), 1)
        score1 = tops[1].get("success_count", 0) / max(tops[1].get("usage_count", 1), 1)
        self.assertGreaterEqual(score0, score1)

    def test_stale_principles(self):
        """Principles with last_used far below current session are stale."""
        stale = self.pa.stale_principles(current_session=200, staleness_threshold=50)
        # Both active principles have last_used=100, 200-100=100 >= 50 → stale
        self.assertEqual(len(stale), 2)

    def test_not_stale_when_recent(self):
        """Principles used recently are not stale."""
        stale = self.pa.stale_principles(current_session=110, staleness_threshold=50)
        self.assertEqual(len(stale), 0)

    def test_to_dict_has_required_keys(self):
        d = self.pa.to_dict()
        for key in ("total", "active", "pruned", "average_score", "domain_distribution"):
            self.assertIn(key, d)

    def test_empty_file(self):
        """Empty principle file should not crash."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            fname = f.name
        try:
            pa = PrincipleAnalyzer(fname)
            self.assertEqual(pa.total_principles, 0)
            self.assertEqual(pa.average_score, 0.0)
        finally:
            os.unlink(fname)

    def test_missing_file(self):
        """Missing file should not crash."""
        pa = PrincipleAnalyzer("/tmp/does_not_exist_xyz_abc.jsonl")
        self.assertEqual(pa.total_principles, 0)


# ---------------------------------------------------------------------------
# SessionTrendAnalyzer
# ---------------------------------------------------------------------------

class TestSessionTrendAnalyzer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        records = [
            _session(1, "B"), _session(2, "B+"), _session(3, "A-"),
            _session(4, "A"), _session(5, "A+"),
        ]
        _write_jsonl(self.tmp.name, records)
        self.sta = SessionTrendAnalyzer(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_total_sessions(self):
        self.assertEqual(self.sta.total_sessions, 5)

    def test_trend_improving(self):
        """Grades consistently rising should give 'improving' trend."""
        self.assertEqual(self.sta.trend_direction, "improving")

    def test_trend_declining(self):
        """Grades consistently falling should give 'declining' trend."""
        tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        _write_jsonl(tmp.name, [
            _session(1, "A+"), _session(2, "A"), _session(3, "B+"),
            _session(4, "B"), _session(5, "C"),
        ])
        sta = SessionTrendAnalyzer(tmp.name)
        self.assertEqual(sta.trend_direction, "declining")
        os.unlink(tmp.name)

    def test_trend_stable(self):
        """Flat grades should give 'stable' trend."""
        tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        _write_jsonl(tmp.name, [
            _session(1, "B"), _session(2, "B"), _session(3, "B"),
        ])
        sta = SessionTrendAnalyzer(tmp.name)
        self.assertEqual(sta.trend_direction, "stable")
        os.unlink(tmp.name)

    def test_average_gpa_non_zero(self):
        """Average GPA from grade_counts should be > 0 with passing grades."""
        counts = self.sta.grade_counts
        self.assertGreater(sum(counts.values()), 0)

    def test_empty_file_no_crash(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        sta = SessionTrendAnalyzer(tmp.name)
        self.assertEqual(sta.total_sessions, 0)
        self.assertIn(sta.trend_direction, ("insufficient_data", "unknown", "stable"))
        os.unlink(tmp.name)

    def test_to_dict(self):
        d = self.sta.to_dict()
        self.assertIn("total", d)
        self.assertIn("trend", d)


# ---------------------------------------------------------------------------
# ImprovementTracker
# ---------------------------------------------------------------------------

class TestImprovementTracker(unittest.TestCase):
    def _write_improvements(self, records):
        f = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        _write_jsonl(f.name, records)
        return f.name

    def test_success_rate_calculated(self):
        # success_rate = successes among implemented / total implemented
        path = self._write_improvements([
            {"id": "I1", "status": "implemented", "outcome": "success"},
            {"id": "I2", "status": "implemented", "outcome": "failure"},
            {"id": "I3", "status": "implemented", "outcome": "success"},
        ])
        it = ImprovementTracker(path)
        self.assertIsNotNone(it.success_rate)
        self.assertAlmostEqual(it.success_rate, 2 / 3, delta=0.05)
        os.unlink(path)

    def test_success_rate_none_when_no_implemented(self):
        """success_rate is None when no implemented proposals."""
        path = self._write_improvements([
            {"id": "I1", "status": "pending"},
        ])
        it = ImprovementTracker(path)
        self.assertIsNone(it.success_rate)
        os.unlink(path)

    def test_total_proposals_count(self):
        path = self._write_improvements([
            {"id": "I1", "status": "implemented"},
            {"id": "I2", "status": "pending"},
        ])
        it = ImprovementTracker(path)
        self.assertEqual(it.total_proposals, 2)
        os.unlink(path)

    def test_missing_file_no_crash(self):
        it = ImprovementTracker("/tmp/does_not_exist_improvement.jsonl")
        self.assertIsNone(it.success_rate)


# ---------------------------------------------------------------------------
# ResearchROITracker
# ---------------------------------------------------------------------------

class TestResearchROITracker(unittest.TestCase):
    def _write_research(self, records):
        f = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        _write_jsonl(f.name, records)
        return f.name

    def test_implementation_rate_calculated(self):
        path = self._write_research([
            {"id": "R1", "status": "implemented"},
            {"id": "R2", "status": "sent"},
            {"id": "R3", "status": "pending"},
            {"id": "R4", "status": "implemented"},
        ])
        rt = ResearchROITracker(path)
        # 2 implemented / 4 total = 0.5
        self.assertAlmostEqual(rt.implementation_rate, 0.5, delta=0.05)
        os.unlink(path)

    def test_total_deliveries(self):
        path = self._write_research([
            {"id": "R1", "status": "implemented"},
            {"id": "R2", "status": "pending"},
        ])
        rt = ResearchROITracker(path)
        self.assertEqual(rt.total_deliveries, 2)
        os.unlink(path)

    def test_missing_file_no_crash(self):
        rt = ResearchROITracker("/tmp/does_not_exist_research.jsonl")
        self.assertEqual(rt.total_deliveries, 0)
        self.assertAlmostEqual(rt.implementation_rate, 0.0)


# ---------------------------------------------------------------------------
# JournalAnalyzer
# ---------------------------------------------------------------------------

class TestJournalAnalyzer(unittest.TestCase):
    def _write_journal(self, events):
        f = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        records = [{"event_type": e, "session": i+1} for i, e in enumerate(events)]
        _write_jsonl(f.name, records)
        return f.name

    def test_event_counts(self):
        path = self._write_journal(["task_start", "task_complete", "task_start", "error"])
        ja = JournalAnalyzer(path)
        counts = ja.event_type_counts
        self.assertEqual(counts.get("task_start", 0), 2)
        self.assertEqual(counts.get("task_complete", 0), 1)
        self.assertEqual(counts.get("error", 0), 1)
        os.unlink(path)

    def test_total_events(self):
        path = self._write_journal(["a", "b", "c"])
        ja = JournalAnalyzer(path)
        self.assertEqual(ja.total_events, 3)
        os.unlink(path)

    def test_empty_journal_no_crash(self):
        f = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        ja = JournalAnalyzer(f.name)
        self.assertEqual(ja.total_events, 0)
        os.unlink(f.name)


# ---------------------------------------------------------------------------
# MetaLearningDashboard
# ---------------------------------------------------------------------------

class TestMetaLearningDashboard(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Write minimal data for each component
        _write_jsonl(os.path.join(self.tmpdir, "principles.jsonl"), [
            _principle("P1", usage=5, success=4),
            _principle("P2", usage=2, success=1),
        ])
        _write_jsonl(os.path.join(self.tmpdir, "session_outcomes.jsonl"), [
            _session(1, "B"), _session(2, "A-"), _session(3, "A"),
        ])
        _write_jsonl(os.path.join(self.tmpdir, "improvements.jsonl"), [])
        _write_jsonl(os.path.join(self.tmpdir, "research_outcomes.jsonl"), [])
        _write_jsonl(os.path.join(self.tmpdir, "journal.jsonl"), [
            {"event_type": "task_complete", "session": 1},
        ])
        self.dashboard = MetaLearningDashboard(data_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_health_not_unknown(self):
        """With data present, health should not be UNKNOWN."""
        health = self.dashboard._compute_health()
        self.assertIn(health, ("HEALTHY", "MONITOR", "NEEDS_ATTENTION", "UNKNOWN"))
        # With 3 sessions and active principles, should not be UNKNOWN
        if self.dashboard._principles.total_principles > 0:
            self.assertNotEqual(health, "UNKNOWN")

    def test_report_returns_dict(self):
        """generate_report() must return a non-empty dict."""
        report = self.dashboard.generate_report()
        self.assertIsInstance(report, dict)
        self.assertGreater(len(report), 0)

    def test_brief_returns_string(self):
        """brief_summary() must return a non-empty string."""
        brief = self.dashboard.brief_summary()
        self.assertIsInstance(brief, str)
        self.assertGreater(len(brief), 5)

    def test_json_output_has_required_keys(self):
        """generate_report() must include top-level keys for all sub-analyzers."""
        d = self.dashboard.generate_report()
        for key in ("principles", "sessions", "summary"):
            self.assertIn(key, d, f"Missing key: {key}")
        # health lives under summary
        self.assertIn("overall_health", d["summary"])

    def test_empty_data_dir_no_crash(self):
        """Dashboard with all-empty files should not crash."""
        empty_dir = tempfile.mkdtemp()
        try:
            for fname in ("principles.jsonl", "session_outcomes.jsonl",
                          "improvements.jsonl", "research_outcomes.jsonl",
                          "journal.jsonl"):
                open(os.path.join(empty_dir, fname), "w").close()
            d = MetaLearningDashboard(data_dir=empty_dir)
            self.assertEqual(d._compute_health(), "UNKNOWN")
        finally:
            import shutil
            shutil.rmtree(empty_dir, ignore_errors=True)


class TestMetaLearningDashboardCLI(unittest.TestCase):
    """Test the CLI main() entry point."""

    def test_brief_flag(self):
        """--brief flag should produce output without crashing."""
        import subprocess
        result = subprocess.run(
            [sys.executable,
             str(Path(__file__).parent.parent / "self-learning" / "meta_learning_dashboard.py"),
             "--brief"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertGreater(len(result.stdout.strip()), 0)

    def test_json_flag(self):
        """--json flag should produce valid JSON output."""
        import subprocess
        result = subprocess.run(
            [sys.executable,
             str(Path(__file__).parent.parent / "self-learning" / "meta_learning_dashboard.py"),
             "--json"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        try:
            parsed = json.loads(result.stdout)
            self.assertIsInstance(parsed, dict)
        except json.JSONDecodeError as e:
            self.fail(f"--json produced invalid JSON: {e}")


if __name__ == "__main__":
    unittest.main()
