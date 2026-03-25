#!/usr/bin/env python3
"""Tests for figure preset layouts — MT-32 Phase 6 extension.

Tests convenience functions for common figure layouts.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chart_generator import BarChart, LineChart, DonutChart, ScatterPlot, GaugeChart
from figure_generator import (
    Figure,
    FigurePanel,
    TextAnnotation,
    render_figure,
    save_figure,
    quick_figure,
    comparison_figure,
    dashboard_figure,
)


class TestQuickFigure(unittest.TestCase):
    """Test quick_figure() convenience function."""

    def test_single_chart(self):
        chart = BarChart(data=[("A", 10), ("B", 20)], title="Test")
        fig = quick_figure([chart])
        self.assertEqual(len(fig.panels), 1)
        svg = render_figure(fig)
        self.assertIn("<svg", svg)

    def test_two_charts_auto_layout(self):
        charts = [
            BarChart(data=[("A", 10)], title="1"),
            BarChart(data=[("B", 20)], title="2"),
        ]
        fig = quick_figure(charts)
        self.assertEqual(len(fig.panels), 2)
        self.assertEqual(fig._effective_cols(), 2)

    def test_auto_labels(self):
        charts = [
            BarChart(data=[("A", 10)], title="1"),
            BarChart(data=[("B", 20)], title="2"),
            BarChart(data=[("C", 30)], title="3"),
        ]
        fig = quick_figure(charts)
        labels = [p.label for p in fig.panels]
        self.assertEqual(labels, ["a", "b", "c"])

    def test_with_title(self):
        chart = BarChart(data=[("A", 10)], title="T")
        fig = quick_figure([chart], title="Figure 1")
        self.assertEqual(fig.title, "Figure 1")

    def test_no_labels_option(self):
        charts = [BarChart(data=[("A", 10)], title="T")]
        fig = quick_figure(charts, labels=False)
        self.assertIsNone(fig.panels[0].label)

    def test_custom_cols(self):
        charts = [BarChart(data=[("A", i)], title=str(i)) for i in range(4)]
        fig = quick_figure(charts, cols=4)
        self.assertEqual(fig.cols, 4)

    def test_renders_valid_svg(self):
        charts = [
            BarChart(data=[("A", 10)], title="1"),
            BarChart(data=[("B", 20)], title="2"),
        ]
        fig = quick_figure(charts, title="Quick")
        svg = render_figure(fig)
        self.assertIn("(a)", svg)
        self.assertIn("(b)", svg)
        self.assertIn("Quick", svg)


class TestComparisonFigure(unittest.TestCase):
    """Test side-by-side comparison layout."""

    def test_two_panel_comparison(self):
        left = BarChart(data=[("A", 10), ("B", 20)], title="Before")
        right = BarChart(data=[("A", 30), ("B", 40)], title="After")
        fig = comparison_figure(left, right)
        self.assertEqual(len(fig.panels), 2)
        self.assertEqual(fig._effective_cols(), 2)

    def test_comparison_labels(self):
        left = BarChart(data=[("A", 10)], title="Before")
        right = BarChart(data=[("A", 30)], title="After")
        fig = comparison_figure(left, right)
        labels = [p.label for p in fig.panels]
        self.assertEqual(labels, ["a", "b"])

    def test_comparison_with_title(self):
        left = BarChart(data=[("A", 10)], title="Before")
        right = BarChart(data=[("A", 30)], title="After")
        fig = comparison_figure(left, right, title="Before vs After")
        self.assertEqual(fig.title, "Before vs After")

    def test_comparison_renders(self):
        left = BarChart(data=[("A", 10)], title="Before")
        right = BarChart(data=[("A", 30)], title="After")
        fig = comparison_figure(left, right, title="Comparison")
        svg = render_figure(fig)
        self.assertIn("(a)", svg)
        self.assertIn("(b)", svg)
        self.assertIn("Comparison", svg)


class TestDashboardFigure(unittest.TestCase):
    """Test 2x2 dashboard layout."""

    def test_four_panel_dashboard(self):
        charts = [BarChart(data=[("A", i * 10)], title=f"Panel {i}") for i in range(4)]
        fig = dashboard_figure(charts)
        self.assertEqual(len(fig.panels), 4)
        self.assertEqual(fig._effective_cols(), 2)

    def test_dashboard_with_title(self):
        charts = [BarChart(data=[("A", i)], title=str(i)) for i in range(4)]
        fig = dashboard_figure(charts, title="Dashboard")
        self.assertEqual(fig.title, "Dashboard")

    def test_dashboard_auto_labels(self):
        charts = [BarChart(data=[("A", i)], title=str(i)) for i in range(4)]
        fig = dashboard_figure(charts)
        labels = [p.label for p in fig.panels]
        self.assertEqual(labels, ["a", "b", "c", "d"])

    def test_dashboard_renders_all_panels(self):
        charts = [BarChart(data=[("A", i * 10)], title=f"P{i}") for i in range(4)]
        fig = dashboard_figure(charts, title="Dash")
        svg = render_figure(fig)
        for c in "abcd":
            self.assertIn(f"({c})", svg)

    def test_dashboard_fewer_than_four(self):
        """Should work with 2-3 charts too."""
        charts = [BarChart(data=[("A", i)], title=str(i)) for i in range(3)]
        fig = dashboard_figure(charts)
        self.assertEqual(len(fig.panels), 3)

    def test_dashboard_mixed_types(self):
        charts = [
            BarChart(data=[("A", 10)], title="Bar"),
            GaugeChart(value=75, max_value=100, title="Gauge"),
            BarChart(data=[("B", 20)], title="Bar2"),
            GaugeChart(value=50, max_value=100, title="Gauge2"),
        ]
        fig = dashboard_figure(charts)
        svg = render_figure(fig)
        self.assertIn("<svg", svg)


class TestFigurePresetEdgeCases(unittest.TestCase):
    """Edge cases for preset functions."""

    def test_quick_figure_empty_raises(self):
        with self.assertRaises(ValueError):
            quick_figure([])

    def test_dashboard_empty_raises(self):
        with self.assertRaises(ValueError):
            dashboard_figure([])

    def test_quick_figure_single_no_label_option(self):
        fig = quick_figure([BarChart(data=[("A", 1)], title="T")], labels=False)
        self.assertIsNone(fig.panels[0].label)

    def test_save_quick_figure(self):
        charts = [BarChart(data=[("A", 10)], title="1")]
        fig = quick_figure(charts, title="Saved")
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            save_figure(fig, path)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                self.assertIn("Saved", f.read())
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
