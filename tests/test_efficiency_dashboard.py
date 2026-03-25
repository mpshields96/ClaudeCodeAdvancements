#!/usr/bin/env python3
"""Tests for efficiency_dashboard.py — MT-36 Phase 5."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from efficiency_dashboard import (
    EfficiencyDashboard,
    load_session_data,
    merge_timing_and_outcomes,
    compute_dashboard_stats,
    generate_html,
)


def make_timing_entry(session_id, init_s=30, wrap_s=60, test_s=20, code_s=300, doc_s=15):
    """Create a timing JSONL entry with standard categories."""
    steps = []
    if init_s > 0:
        steps.append({"name": f"init:read_context", "category": "init", "duration_s": init_s})
    if wrap_s > 0:
        steps.append({"name": f"wrap:update_docs", "category": "wrap", "duration_s": wrap_s})
    if test_s > 0:
        steps.append({"name": f"test:run_suites", "category": "test", "duration_s": test_s})
    if code_s > 0:
        steps.append({"name": f"code:implement", "category": "code", "duration_s": code_s})
    if doc_s > 0:
        steps.append({"name": f"doc:project_index", "category": "doc", "duration_s": doc_s})
    total = sum(s["duration_s"] for s in steps)
    return {
        "session_id": session_id,
        "timestamp": f"2026-03-24T{10 + session_id}:00:00Z",
        "total_duration_s": total,
        "steps": steps,
        "by_category": {
            "init": init_s, "wrap": wrap_s, "test": test_s,
            "code": code_s, "doc": doc_s,
        },
    }


def make_outcome_entry(session_id, grade="B+", commits=2, tests_total=8959):
    """Create a session outcome JSONL entry."""
    return {
        "session_id": session_id,
        "grade": grade,
        "commits": commits,
        "tests_total": tests_total,
        "completed_tasks": ["task1", "task2"],
        "timestamp": f"2026-03-24T{10 + session_id}:30:00Z",
    }


def write_jsonl(path, entries):
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


class TestLoadSessionData(unittest.TestCase):
    """Test data loading from JSONL files."""

    def test_load_timings(self):
        with tempfile.TemporaryDirectory() as d:
            tp = os.path.join(d, "timings.jsonl")
            write_jsonl(tp, [make_timing_entry(1), make_timing_entry(2)])
            data = load_session_data(timing_path=tp)
            self.assertEqual(len(data["timings"]), 2)

    def test_load_outcomes(self):
        with tempfile.TemporaryDirectory() as d:
            op = os.path.join(d, "outcomes.jsonl")
            write_jsonl(op, [make_outcome_entry(1)])
            data = load_session_data(outcome_path=op)
            self.assertEqual(len(data["outcomes"]), 1)

    def test_load_missing_files(self):
        data = load_session_data(
            timing_path="/nonexistent/t.jsonl",
            outcome_path="/nonexistent/o.jsonl",
        )
        self.assertEqual(data["timings"], [])
        self.assertEqual(data["outcomes"], [])

    def test_load_empty_files(self):
        with tempfile.TemporaryDirectory() as d:
            tp = os.path.join(d, "timings.jsonl")
            with open(tp, "w") as f:
                f.write("")
            data = load_session_data(timing_path=tp)
            self.assertEqual(data["timings"], [])

    def test_load_corrupt_lines_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            tp = os.path.join(d, "timings.jsonl")
            with open(tp, "w") as f:
                f.write(json.dumps(make_timing_entry(1)) + "\n")
                f.write("NOT JSON\n")
                f.write(json.dumps(make_timing_entry(2)) + "\n")
            data = load_session_data(timing_path=tp)
            self.assertEqual(len(data["timings"]), 2)


class TestMergeData(unittest.TestCase):
    """Test merging timing and outcome data."""

    def test_merge_matching_sessions(self):
        timings = [make_timing_entry(1), make_timing_entry(2)]
        outcomes = [make_outcome_entry(1), make_outcome_entry(2)]
        merged = merge_timing_and_outcomes(timings, outcomes)
        self.assertEqual(len(merged), 2)
        self.assertIn("grade", merged[0])
        self.assertIn("overhead_ratio", merged[0])

    def test_merge_partial_overlap(self):
        timings = [make_timing_entry(1), make_timing_entry(2)]
        outcomes = [make_outcome_entry(1)]
        merged = merge_timing_and_outcomes(timings, outcomes)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["grade"], "B+")
        self.assertIsNone(merged[1]["grade"])

    def test_merge_empty(self):
        merged = merge_timing_and_outcomes([], [])
        self.assertEqual(merged, [])

    def test_overhead_ratio_computed(self):
        timings = [make_timing_entry(1, init_s=50, wrap_s=50, test_s=0, code_s=100, doc_s=0)]
        merged = merge_timing_and_outcomes(timings, [])
        ratio = merged[0]["overhead_ratio"]
        self.assertAlmostEqual(ratio, 0.5, places=2)

    def test_overhead_ratio_all_code(self):
        timings = [make_timing_entry(1, init_s=0, wrap_s=0, test_s=0, code_s=500, doc_s=0)]
        merged = merge_timing_and_outcomes(timings, [])
        self.assertAlmostEqual(merged[0]["overhead_ratio"], 0.0, places=2)


class TestComputeStats(unittest.TestCase):
    """Test dashboard statistics computation."""

    def _make_merged(self, n=5):
        timings = [make_timing_entry(i, code_s=300 - i * 10) for i in range(1, n + 1)]
        outcomes = [make_outcome_entry(i) for i in range(1, n + 1)]
        return merge_timing_and_outcomes(timings, outcomes)

    def test_stats_with_data(self):
        merged = self._make_merged(5)
        stats = compute_dashboard_stats(merged)
        self.assertEqual(stats["session_count"], 5)
        self.assertIn("avg_overhead_ratio", stats)
        self.assertIn("avg_overhead_pct", stats)
        self.assertIn("trend", stats)
        self.assertIn("category_totals", stats)

    def test_stats_empty(self):
        stats = compute_dashboard_stats([])
        self.assertEqual(stats["session_count"], 0)
        self.assertEqual(stats["avg_overhead_ratio"], 0.0)

    def test_category_totals(self):
        merged = self._make_merged(3)
        stats = compute_dashboard_stats(merged)
        cats = stats["category_totals"]
        self.assertIn("init", cats)
        self.assertIn("code", cats)
        self.assertGreater(cats["code"], cats["init"])

    def test_trend_computation(self):
        # Improving: later sessions have lower overhead ratios
        timings = []
        for i in range(1, 11):
            # Overhead shrinks over time, code stays same
            timings.append(make_timing_entry(i, init_s=50 - i * 3, wrap_s=60 - i * 3,
                                              test_s=20, code_s=300, doc_s=15))
        merged = merge_timing_and_outcomes(timings, [])
        stats = compute_dashboard_stats(merged)
        self.assertEqual(stats["trend"], "improving")

    def test_top_sinks(self):
        merged = self._make_merged(3)
        stats = compute_dashboard_stats(merged)
        sinks = stats["top_sinks"]
        self.assertIsInstance(sinks, list)
        self.assertGreater(len(sinks), 0)
        # Should be sorted descending by avg duration
        if len(sinks) >= 2:
            self.assertGreaterEqual(sinks[0]["avg_s"], sinks[1]["avg_s"])

    def test_per_session_data(self):
        merged = self._make_merged(3)
        stats = compute_dashboard_stats(merged)
        per_session = stats["per_session"]
        self.assertEqual(len(per_session), 3)
        for s in per_session:
            self.assertIn("session_id", s)
            self.assertIn("overhead_ratio", s)
            self.assertIn("total_s", s)


class TestGenerateHTML(unittest.TestCase):
    """Test HTML generation."""

    def _make_stats(self):
        timings = [make_timing_entry(i) for i in range(1, 6)]
        outcomes = [make_outcome_entry(i) for i in range(1, 6)]
        merged = merge_timing_and_outcomes(timings, outcomes)
        return compute_dashboard_stats(merged)

    def test_generates_html_string(self):
        stats = self._make_stats()
        html = generate_html(stats)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Session Efficiency", html)

    def test_html_contains_chart_data(self):
        stats = self._make_stats()
        html = generate_html(stats)
        # Should embed the data as JSON for JS charts
        self.assertIn("per_session", html)

    def test_html_contains_summary(self):
        stats = self._make_stats()
        html = generate_html(stats)
        self.assertIn("Overhead", html)

    def test_empty_data_still_renders(self):
        stats = compute_dashboard_stats([])
        html = generate_html(stats)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("No data", html)

    def test_html_self_contained(self):
        stats = self._make_stats()
        html = generate_html(stats)
        # No external CSS/JS links
        self.assertNotIn('href="http', html)
        self.assertNotIn('src="http', html)

    def test_html_has_dark_mode(self):
        stats = self._make_stats()
        html = generate_html(stats)
        # Should have dark background color
        self.assertIn("#1a1a2e", html)


class TestEfficiencyDashboard(unittest.TestCase):
    """Test the main dashboard class."""

    def _setup_files(self, d, n=5):
        tp = os.path.join(d, "timings.jsonl")
        op = os.path.join(d, "outcomes.jsonl")
        write_jsonl(tp, [make_timing_entry(i) for i in range(1, n + 1)])
        write_jsonl(op, [make_outcome_entry(i) for i in range(1, n + 1)])
        return tp, op

    def test_generate_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            tp, op = self._setup_files(d)
            out = os.path.join(d, "dashboard.html")
            dash = EfficiencyDashboard(timing_path=tp, outcome_path=op)
            path = dash.generate(output_path=out)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("<!DOCTYPE html>", content)

    def test_generate_default_output(self):
        with tempfile.TemporaryDirectory() as d:
            tp, op = self._setup_files(d)
            dash = EfficiencyDashboard(timing_path=tp, outcome_path=op)
            path = dash.generate(output_path=os.path.join(d, "out.html"))
            self.assertTrue(path.endswith(".html"))

    def test_stats_accessible(self):
        with tempfile.TemporaryDirectory() as d:
            tp, op = self._setup_files(d)
            dash = EfficiencyDashboard(timing_path=tp, outcome_path=op)
            dash.generate(output_path=os.path.join(d, "out.html"))
            self.assertIsNotNone(dash.stats)
            self.assertEqual(dash.stats["session_count"], 5)

    def test_no_data(self):
        dash = EfficiencyDashboard(
            timing_path="/nonexistent/t.jsonl",
            outcome_path="/nonexistent/o.jsonl",
        )
        with tempfile.TemporaryDirectory() as d:
            path = dash.generate(output_path=os.path.join(d, "out.html"))
            self.assertTrue(os.path.exists(path))


class TestGradeCorrelation(unittest.TestCase):
    """Test quality-speed correlation analysis."""

    def test_grade_to_numeric(self):
        from efficiency_dashboard import grade_to_numeric
        self.assertEqual(grade_to_numeric("A+"), 4.3)
        self.assertEqual(grade_to_numeric("A"), 4.0)
        self.assertEqual(grade_to_numeric("B+"), 3.3)
        self.assertEqual(grade_to_numeric("C"), 2.0)
        self.assertIsNone(grade_to_numeric(None))
        self.assertIsNone(grade_to_numeric("X"))

    def test_correlation_in_stats(self):
        timings = [make_timing_entry(i, code_s=300) for i in range(1, 6)]
        outcomes = [
            make_outcome_entry(1, grade="A"),
            make_outcome_entry(2, grade="B+"),
            make_outcome_entry(3, grade="A-"),
            make_outcome_entry(4, grade="B"),
            make_outcome_entry(5, grade="A+"),
        ]
        merged = merge_timing_and_outcomes(timings, outcomes)
        stats = compute_dashboard_stats(merged)
        # Should have quality_speed data points
        self.assertIn("quality_speed", stats)
        self.assertEqual(len(stats["quality_speed"]), 5)


if __name__ == "__main__":
    unittest.main()
