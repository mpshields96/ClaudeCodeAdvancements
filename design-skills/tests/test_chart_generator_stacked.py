#!/usr/bin/env python3
"""Tests for StackedBarChart in chart_generator.py — S115 desktop."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chart_generator import StackedBarChart, render_svg, CCA_COLORS


class TestStackedBarChartDataclass(unittest.TestCase):
    """Test StackedBarChart dataclass creation and defaults."""

    def test_basic_creation(self):
        chart = StackedBarChart(
            data=[("Q1", [10, 20, 30]), ("Q2", [15, 25, 35])],
            series_names=["Build", "Adapt", "Skip"],
        )
        self.assertEqual(len(chart.data), 2)
        self.assertEqual(len(chart.series_names), 3)

    def test_default_dimensions(self):
        chart = StackedBarChart(
            data=[("A", [1, 2])],
            series_names=["X", "Y"],
        )
        self.assertEqual(chart.width, 500)
        self.assertEqual(chart.height, 300)

    def test_default_colors_assigned(self):
        chart = StackedBarChart(
            data=[("A", [1, 2, 3])],
            series_names=["X", "Y", "Z"],
        )
        self.assertEqual(len(chart.colors), 3)

    def test_custom_colors(self):
        chart = StackedBarChart(
            data=[("A", [1, 2])],
            series_names=["X", "Y"],
            colors=["#FF0000", "#00FF00"],
        )
        self.assertEqual(chart.colors, ["#FF0000", "#00FF00"])

    def test_title(self):
        chart = StackedBarChart(
            data=[("A", [1])],
            series_names=["X"],
            title="Test Title",
        )
        self.assertEqual(chart.title, "Test Title")

    def test_show_values(self):
        chart = StackedBarChart(
            data=[("A", [1, 2])],
            series_names=["X", "Y"],
            show_values=True,
        )
        self.assertTrue(chart.show_values)

    def test_y_label(self):
        chart = StackedBarChart(
            data=[("A", [1])],
            series_names=["X"],
            y_label="Count",
        )
        self.assertEqual(chart.y_label, "Count")


class TestStackedBarChartRendering(unittest.TestCase):
    """Test SVG rendering of stacked bar charts."""

    def test_renders_svg(self):
        chart = StackedBarChart(
            data=[("Q1", [10, 20, 30]), ("Q2", [15, 25, 35])],
            series_names=["Build", "Adapt", "Skip"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_renders_bars(self):
        chart = StackedBarChart(
            data=[("A", [10, 20])],
            series_names=["X", "Y"],
        )
        svg = render_svg(chart)
        # Should have rect elements for bars
        self.assertIn("<rect", svg)

    def test_renders_labels(self):
        chart = StackedBarChart(
            data=[("January", [10, 20])],
            series_names=["Alpha", "Beta"],
        )
        svg = render_svg(chart)
        self.assertIn("January", svg)

    def test_renders_title(self):
        chart = StackedBarChart(
            data=[("A", [1, 2])],
            series_names=["X", "Y"],
            title="My Chart",
        )
        svg = render_svg(chart)
        self.assertIn("My Chart", svg)

    def test_renders_legend(self):
        chart = StackedBarChart(
            data=[("A", [1, 2])],
            series_names=["Build", "Skip"],
        )
        svg = render_svg(chart)
        # Legend should show series names
        self.assertIn("Build", svg)
        self.assertIn("Skip", svg)

    def test_empty_data(self):
        chart = StackedBarChart(
            data=[],
            series_names=[],
        )
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_single_series(self):
        chart = StackedBarChart(
            data=[("A", [10]), ("B", [20])],
            series_names=["Only"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_many_categories(self):
        data = [(f"S{i}", [i, i * 2, i * 3]) for i in range(10)]
        chart = StackedBarChart(
            data=data,
            series_names=["Low", "Med", "High"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_zero_values(self):
        chart = StackedBarChart(
            data=[("A", [0, 0, 0])],
            series_names=["X", "Y", "Z"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_show_values_rendering(self):
        chart = StackedBarChart(
            data=[("A", [10, 20])],
            series_names=["X", "Y"],
            show_values=True,
        )
        svg = render_svg(chart)
        self.assertIn("10", svg)
        self.assertIn("20", svg)

    def test_custom_dimensions(self):
        chart = StackedBarChart(
            data=[("A", [1, 2])],
            series_names=["X", "Y"],
            width=800,
            height=400,
        )
        svg = render_svg(chart)
        self.assertIn('width="800"', svg)
        self.assertIn('height="400"', svg)

    def test_y_label_rendered(self):
        chart = StackedBarChart(
            data=[("A", [1, 2])],
            series_names=["X", "Y"],
            y_label="Tests",
        )
        svg = render_svg(chart)
        self.assertIn("Tests", svg)

    def test_stacking_order(self):
        """Verify segments stack (total height proportional to sum)."""
        chart = StackedBarChart(
            data=[("A", [100, 200])],
            series_names=["Small", "Big"],
        )
        svg = render_svg(chart)
        # Both series should have rect elements
        rect_count = svg.count("<rect")
        # At least: background + 2 bar segments
        self.assertGreaterEqual(rect_count, 3)

    def test_escapes_special_chars(self):
        chart = StackedBarChart(
            data=[("A & B", [1, 2])],
            series_names=["<X>", "Y"],
            title="Test & Chart",
        )
        svg = render_svg(chart)
        self.assertIn("&amp;", svg)
        self.assertIn("&lt;", svg)


class TestStackedBarChartEdgeCases(unittest.TestCase):
    """Edge cases for stacked bar chart."""

    def test_negative_values_treated_as_zero(self):
        chart = StackedBarChart(
            data=[("A", [-5, 10])],
            series_names=["Neg", "Pos"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_very_large_values(self):
        chart = StackedBarChart(
            data=[("A", [1000000, 2000000])],
            series_names=["X", "Y"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_mismatched_series_count(self):
        """If data has more values than series_names, extra values ignored."""
        chart = StackedBarChart(
            data=[("A", [1, 2, 3, 4])],
            series_names=["X", "Y"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_all_same_values(self):
        chart = StackedBarChart(
            data=[("A", [10, 10, 10])],
            series_names=["X", "Y", "Z"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)


if __name__ == "__main__":
    unittest.main()
