#!/usr/bin/env python3
"""Tests for efficiency_analyzer.py — MT-36 Phase 2.

Analyzes session overhead patterns and recommends optimizations.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from efficiency_analyzer import (
    SessionProfile,
    OverheadAnalyzer,
    Recommendation,
    analyze_command_overhead,
    compute_overhead_ratio,
    format_analysis_report,
)


class TestSessionProfile(unittest.TestCase):
    """Test SessionProfile — captures one session's overhead breakdown."""

    def test_create_from_steps(self):
        steps = [
            {"name": "init:read_files", "category": "init", "duration_s": 5.0},
            {"name": "test:run_suites", "category": "test", "duration_s": 90.0},
            {"name": "code:implement", "category": "code", "duration_s": 300.0},
            {"name": "wrap:update_docs", "category": "wrap", "duration_s": 20.0},
        ]
        profile = SessionProfile(session_id=100, steps=steps)
        self.assertEqual(profile.session_id, 100)
        self.assertEqual(profile.total_duration, 415.0)

    def test_overhead_vs_productive(self):
        """Overhead = init + wrap + test + doc. Productive = code."""
        steps = [
            {"name": "init:read", "category": "init", "duration_s": 10.0},
            {"name": "test:smoke", "category": "test", "duration_s": 30.0},
            {"name": "code:build", "category": "code", "duration_s": 200.0},
            {"name": "wrap:docs", "category": "wrap", "duration_s": 40.0},
            {"name": "doc:update", "category": "doc", "duration_s": 15.0},
        ]
        profile = SessionProfile(session_id=101, steps=steps)
        self.assertEqual(profile.overhead_duration, 95.0)  # init+test+wrap+doc
        self.assertEqual(profile.productive_duration, 200.0)  # code only

    def test_overhead_ratio(self):
        steps = [
            {"name": "init:read", "category": "init", "duration_s": 20.0},
            {"name": "code:build", "category": "code", "duration_s": 80.0},
        ]
        profile = SessionProfile(session_id=102, steps=steps)
        self.assertAlmostEqual(profile.overhead_ratio, 0.2, places=2)

    def test_empty_steps(self):
        profile = SessionProfile(session_id=103, steps=[])
        self.assertEqual(profile.total_duration, 0.0)
        self.assertEqual(profile.overhead_ratio, 0.0)

    def test_all_overhead_no_code(self):
        steps = [
            {"name": "init:read", "category": "init", "duration_s": 30.0},
            {"name": "wrap:docs", "category": "wrap", "duration_s": 20.0},
        ]
        profile = SessionProfile(session_id=104, steps=steps)
        self.assertAlmostEqual(profile.overhead_ratio, 1.0, places=2)

    def test_category_breakdown(self):
        steps = [
            {"name": "init:a", "category": "init", "duration_s": 5.0},
            {"name": "init:b", "category": "init", "duration_s": 3.0},
            {"name": "code:c", "category": "code", "duration_s": 100.0},
        ]
        profile = SessionProfile(session_id=105, steps=steps)
        breakdown = profile.category_breakdown()
        self.assertAlmostEqual(breakdown["init"], 8.0)
        self.assertAlmostEqual(breakdown["code"], 100.0)

    def test_top_overhead_steps(self):
        steps = [
            {"name": "test:all_suites", "category": "test", "duration_s": 90.0},
            {"name": "init:read", "category": "init", "duration_s": 5.0},
            {"name": "wrap:self_learning", "category": "wrap", "duration_s": 60.0},
            {"name": "code:build", "category": "code", "duration_s": 300.0},
        ]
        profile = SessionProfile(session_id=106, steps=steps)
        top = profile.top_overhead_steps(n=2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0]["name"], "test:all_suites")
        self.assertEqual(top[1]["name"], "wrap:self_learning")


class TestOverheadAnalyzer(unittest.TestCase):
    """Test OverheadAnalyzer — multi-session trend analysis."""

    def _make_history(self, n=5):
        """Generate n synthetic timing entries."""
        entries = []
        for i in range(n):
            entries.append({
                "session_id": 100 + i,
                "timestamp": f"2026-03-2{i}T10:00:00Z",
                "total_duration_s": 400 + i * 10,
                "steps": [
                    {"name": "init:read_files", "category": "init", "duration_s": 8.0 + i},
                    {"name": "test:run_suites", "category": "test", "duration_s": 90.0 + i * 5},
                    {"name": "code:implement", "category": "code", "duration_s": 250.0 + i * 3},
                    {"name": "wrap:self_learning", "category": "wrap", "duration_s": 50.0 + i * 2},
                ],
                "by_category": {
                    "init": 8.0 + i,
                    "test": 90.0 + i * 5,
                    "code": 250.0 + i * 3,
                    "wrap": 50.0 + i * 2,
                },
            })
        return entries

    def test_analyze_empty(self):
        analyzer = OverheadAnalyzer([])
        result = analyzer.analyze()
        self.assertEqual(result["sessions_analyzed"], 0)
        self.assertEqual(result["recommendations"], [])

    def test_analyze_single_session(self):
        history = self._make_history(1)
        analyzer = OverheadAnalyzer(history)
        result = analyzer.analyze()
        self.assertEqual(result["sessions_analyzed"], 1)
        self.assertIn("avg_overhead_ratio", result)

    def test_analyze_multiple_sessions(self):
        history = self._make_history(5)
        analyzer = OverheadAnalyzer(history)
        result = analyzer.analyze()
        self.assertEqual(result["sessions_analyzed"], 5)
        self.assertIn("avg_overhead_ratio", result)
        self.assertIn("worst_overhead_ratio", result)
        self.assertIn("best_overhead_ratio", result)

    def test_trend_detection(self):
        """Detect if overhead is getting worse over time."""
        history = self._make_history(5)
        analyzer = OverheadAnalyzer(history)
        result = analyzer.analyze()
        self.assertIn("overhead_trend", result)
        # trend should be one of: improving, stable, worsening
        self.assertIn(result["overhead_trend"], ["improving", "stable", "worsening"])

    def test_top_sinks_identified(self):
        history = self._make_history(3)
        analyzer = OverheadAnalyzer(history)
        result = analyzer.analyze()
        self.assertIn("top_sinks", result)
        self.assertGreater(len(result["top_sinks"]), 0)
        # Each sink should have name and avg_duration
        sink = result["top_sinks"][0]
        self.assertIn("name", sink)
        self.assertIn("avg_duration_s", sink)

    def test_recommendations_generated(self):
        history = self._make_history(5)
        analyzer = OverheadAnalyzer(history)
        result = analyzer.analyze()
        self.assertIsInstance(result["recommendations"], list)

    def test_category_trend(self):
        """Track per-category overhead trend."""
        history = self._make_history(5)
        analyzer = OverheadAnalyzer(history)
        result = analyzer.analyze()
        self.assertIn("category_trends", result)
        self.assertIn("test", result["category_trends"])


class TestRecommendation(unittest.TestCase):
    """Test Recommendation dataclass."""

    def test_create(self):
        rec = Recommendation(
            title="Parallelize test suite",
            category="test",
            current_cost_s=90.0,
            estimated_savings_s=50.0,
            difficulty="medium",
            description="Run test suites in parallel with 4 workers.",
        )
        self.assertEqual(rec.title, "Parallelize test suite")
        self.assertAlmostEqual(rec.savings_pct, 55.6, places=1)

    def test_to_dict(self):
        rec = Recommendation(
            title="Cache resurfacer",
            category="init",
            current_cost_s=10.0,
            estimated_savings_s=8.0,
            difficulty="low",
            description="Skip if unchanged.",
        )
        d = rec.to_dict()
        self.assertEqual(d["title"], "Cache resurfacer")
        self.assertAlmostEqual(d["savings_pct"], 80.0)


class TestAnalyzeCommandOverhead(unittest.TestCase):
    """Test the command-level overhead analyzer."""

    def test_analyze_init(self):
        steps = [
            {"name": "init:read_files", "category": "init", "duration_s": 5.0},
            {"name": "init:enrichment", "category": "init", "duration_s": 15.0},
            {"name": "init:smoke_test", "category": "test", "duration_s": 10.0},
        ]
        result = analyze_command_overhead(steps, command="init")
        self.assertEqual(result["command"], "init")
        self.assertGreater(result["total_s"], 0)
        self.assertIn("steps", result)

    def test_analyze_wrap(self):
        steps = [
            {"name": "wrap:full_tests", "category": "test", "duration_s": 90.0},
            {"name": "wrap:self_learning", "category": "wrap", "duration_s": 60.0},
            {"name": "wrap:docs", "category": "doc", "duration_s": 10.0},
        ]
        result = analyze_command_overhead(steps, command="wrap")
        self.assertEqual(result["command"], "wrap")
        self.assertAlmostEqual(result["total_s"], 160.0)


class TestComputeOverheadRatio(unittest.TestCase):
    """Test compute_overhead_ratio helper."""

    def test_basic(self):
        ratio = compute_overhead_ratio(
            overhead_s=50.0, productive_s=200.0
        )
        self.assertAlmostEqual(ratio, 0.2)

    def test_zero_productive(self):
        ratio = compute_overhead_ratio(overhead_s=50.0, productive_s=0.0)
        self.assertAlmostEqual(ratio, 1.0)

    def test_zero_both(self):
        ratio = compute_overhead_ratio(overhead_s=0.0, productive_s=0.0)
        self.assertAlmostEqual(ratio, 0.0)


class TestFormatAnalysisReport(unittest.TestCase):
    """Test report formatter."""

    def test_format_nonempty(self):
        analysis = {
            "sessions_analyzed": 5,
            "avg_overhead_ratio": 0.35,
            "worst_overhead_ratio": 0.5,
            "best_overhead_ratio": 0.2,
            "overhead_trend": "stable",
            "top_sinks": [
                {"name": "test:run_suites", "avg_duration_s": 90.0, "category": "test", "occurrences": 5},
            ],
            "category_trends": {"test": "stable", "init": "improving"},
            "recommendations": [],
        }
        report = format_analysis_report(analysis)
        self.assertIn("Sessions analyzed: 5", report)
        self.assertIn("35.0%", report)
        self.assertIn("test:run_suites", report)

    def test_format_empty(self):
        analysis = {
            "sessions_analyzed": 0,
            "avg_overhead_ratio": 0.0,
            "recommendations": [],
        }
        report = format_analysis_report(analysis)
        self.assertIn("No timing data", report)


class TestAnalyzeWrapOverhead(unittest.TestCase):
    """Test static wrap overhead analysis."""

    def test_returns_valid_structure(self):
        from efficiency_analyzer import analyze_wrap_overhead
        result = analyze_wrap_overhead()
        self.assertIn("total_estimated_tokens", result)
        self.assertIn("critical_tokens", result)
        self.assertIn("deferrable_tokens", result)
        self.assertIn("savings_pct", result)
        self.assertIn("slim_wrap_proposal", result)

    def test_critical_less_than_total(self):
        from efficiency_analyzer import analyze_wrap_overhead
        result = analyze_wrap_overhead()
        self.assertLess(result["critical_tokens"], result["total_estimated_tokens"])

    def test_deferrable_plus_critical_equals_total(self):
        from efficiency_analyzer import analyze_wrap_overhead
        result = analyze_wrap_overhead()
        self.assertEqual(
            result["critical_tokens"] + result["deferrable_tokens"],
            result["total_estimated_tokens"],
        )

    def test_savings_pct_reasonable(self):
        from efficiency_analyzer import analyze_wrap_overhead
        result = analyze_wrap_overhead()
        # Should save at least 30% by deferring non-critical steps
        self.assertGreater(result["savings_pct"], 30.0)
        self.assertLess(result["savings_pct"], 90.0)

    def test_slim_wrap_proposal_has_keep_and_defer(self):
        from efficiency_analyzer import analyze_wrap_overhead
        result = analyze_wrap_overhead()
        slim = result["slim_wrap_proposal"]
        self.assertGreater(len(slim["keep"]), 0)
        self.assertGreater(len(slim["defer_to_next_init"]), 0)

    def test_slim_wrap_estimated_tokens_less_than_current(self):
        from efficiency_analyzer import analyze_wrap_overhead
        result = analyze_wrap_overhead()
        slim = result["slim_wrap_proposal"]
        self.assertLess(slim["estimated_slim_tokens"], result["total_estimated_tokens"])


class TestFormatWrapAnalysis(unittest.TestCase):
    """Test wrap analysis report formatting."""

    def test_format_contains_key_sections(self):
        from efficiency_analyzer import format_wrap_analysis
        report = format_wrap_analysis()
        self.assertIn("CRITICAL STEPS", report)
        self.assertIn("DEFERRABLE", report)
        self.assertIn("SLIM WRAP PROPOSAL", report)

    def test_format_shows_token_counts(self):
        from efficiency_analyzer import format_wrap_analysis
        report = format_wrap_analysis()
        self.assertIn("tokens", report)

    def test_cli_wrap_analysis(self):
        """Test CLI --wrap-analysis flag works."""
        import subprocess
        result = subprocess.run(
            ["python3", "efficiency_analyzer.py", "--wrap-analysis"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("SLIM WRAP PROPOSAL", result.stdout)


if __name__ == "__main__":
    unittest.main()
