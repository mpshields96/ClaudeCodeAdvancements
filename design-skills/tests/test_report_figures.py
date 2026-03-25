#!/usr/bin/env python3
"""Tests for report figure integration — MT-32 Phase 7.

Tests ReportChartGenerator.generate_summary_figure() which composes
multiple report charts into multi-panel figures using figure_generator.py.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from report_charts import ReportChartGenerator


def _make_report_data(**overrides):
    """Build minimal report data dict for testing."""
    data = {
        "modules": [
            {"name": "memory-system", "tests": 340, "loc": 1200, "files": 8},
            {"name": "spec-system", "tests": 205, "loc": 800, "files": 6},
            {"name": "context-monitor", "tests": 434, "loc": 1500, "files": 10},
            {"name": "agent-guard", "tests": 1073, "loc": 3200, "files": 20},
        ],
        "master_tasks": [
            {"id": "MT-32", "title": "Visual", "status": "IN_PROGRESS", "completion": 75},
            {"id": "MT-33", "title": "Reports", "status": "COMPLETE", "completion": 100},
            {"id": "MT-41", "title": "Originator", "status": "IN_PROGRESS", "completion": 40},
        ],
        "intelligence": {
            "findings_total": 50,
            "verdicts": {"BUILD": 8, "ADAPT": 5, "REFERENCE": 20, "SKIP": 17},
        },
        "session": {"number": 166, "date": "2026-03-25"},
        "total_tests": 9380,
        "total_suites": 239,
    }
    data.update(overrides)
    return data


class TestGenerateSummaryFigure(unittest.TestCase):
    """Test summary figure generation."""

    def test_returns_svg_string(self):
        gen = ReportChartGenerator()
        data = _make_report_data()
        svg = gen.generate_summary_figure(data)
        self.assertIsInstance(svg, str)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_contains_panel_labels(self):
        gen = ReportChartGenerator()
        svg = gen.generate_summary_figure(_make_report_data())
        self.assertIn("(a)", svg)
        self.assertIn("(b)", svg)

    def test_contains_figure_title(self):
        gen = ReportChartGenerator()
        svg = gen.generate_summary_figure(_make_report_data())
        self.assertIn("Project Overview", svg)

    def test_with_empty_modules(self):
        gen = ReportChartGenerator()
        data = _make_report_data(modules=[])
        svg = gen.generate_summary_figure(data)
        self.assertIn("<svg", svg)

    def test_with_empty_master_tasks(self):
        gen = ReportChartGenerator()
        data = _make_report_data(master_tasks=[])
        svg = gen.generate_summary_figure(data)
        self.assertIn("<svg", svg)

    def test_with_no_intelligence(self):
        gen = ReportChartGenerator()
        data = _make_report_data(intelligence={"findings_total": 0, "verdicts": {}})
        svg = gen.generate_summary_figure(data)
        self.assertIn("<svg", svg)

    def test_valid_svg_structure(self):
        gen = ReportChartGenerator()
        svg = gen.generate_summary_figure(_make_report_data())
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', svg)
        self.assertIn("viewBox=", svg)


class TestSaveSummaryFigure(unittest.TestCase):
    """Test saving summary figure to file."""

    def test_save_to_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportChartGenerator(output_dir=tmpdir)
            data = _make_report_data()
            path = gen.save_summary_figure(data)
            self.assertTrue(os.path.exists(path))
            self.assertTrue(path.endswith(".svg"))
            with open(path) as f:
                content = f.read()
            self.assertIn("<svg", content)
            self.assertIn("(a)", content)

    def test_save_custom_filename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportChartGenerator(output_dir=tmpdir)
            path = gen.save_summary_figure(_make_report_data(), filename="overview.svg")
            self.assertTrue(path.endswith("overview.svg"))
            self.assertTrue(os.path.exists(path))

    def test_save_requires_output_dir(self):
        gen = ReportChartGenerator()
        with self.assertRaises(ValueError):
            gen.save_summary_figure(_make_report_data())


class TestGenerateAllIncludesFigure(unittest.TestCase):
    """Test that generate_all includes the summary figure."""

    def test_generate_all_has_summary_figure(self):
        gen = ReportChartGenerator()
        data = _make_report_data()
        charts = gen.generate_all(data)
        self.assertIn("summary_figure", charts)
        self.assertIn("<svg", charts["summary_figure"])

    def test_save_all_has_summary_figure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportChartGenerator(output_dir=tmpdir)
            paths = gen.save_all(_make_report_data())
            self.assertIn("summary_figure", paths)
            self.assertTrue(os.path.exists(paths["summary_figure"]))


class TestFigureWithKalshiData(unittest.TestCase):
    """Test summary figure with Kalshi analytics present."""

    def test_kalshi_data_included(self):
        gen = ReportChartGenerator()
        data = _make_report_data(
            kalshi_analytics={
                "available": True,
                "cumulative_pnl": [(1, 5.0), (2, 8.0), (3, 12.0)],
                "strategies": [
                    {"name": "sniper", "win_rate": 95.7, "pnl": 26.0, "bets": 964},
                ],
                "daily_pnl": [0.5, -0.2, 1.0, 0.8, -0.1],
                "bankroll_history": [(1, 100), (2, 105), (3, 112)],
                "trade_volume": [(1, 30), (2, 28), (3, 35)],
            }
        )
        svg = gen.generate_summary_figure(data)
        self.assertIn("<svg", svg)


if __name__ == "__main__":
    unittest.main()
