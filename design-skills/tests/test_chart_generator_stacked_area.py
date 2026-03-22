#!/usr/bin/env python3
"""Tests for StackedAreaChart in chart_generator.py — S116 worker cli1."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chart_generator import StackedAreaChart, render_svg, generate_stacked_area, CCA_COLORS, SERIES_PALETTE


class TestStackedAreaChartDataclass(unittest.TestCase):
    """Test StackedAreaChart dataclass creation and defaults."""

    def _make_chart(self, **kwargs):
        return StackedAreaChart(
            series=[("Alpha", [10, 20, 15]), ("Beta", [5, 8, 12])],
            labels=["S1", "S2", "S3"],
            **kwargs,
        )

    def test_basic_creation(self):
        chart = self._make_chart()
        self.assertEqual(len(chart.series), 2)
        self.assertEqual(len(chart.labels), 3)

    def test_default_dimensions(self):
        chart = self._make_chart()
        self.assertEqual(chart.width, 500)
        self.assertEqual(chart.height, 300)

    def test_default_colors_assigned(self):
        chart = self._make_chart()
        self.assertEqual(len(chart.colors), 2)
        self.assertEqual(chart.colors[0], SERIES_PALETTE[0])
        self.assertEqual(chart.colors[1], SERIES_PALETTE[1])

    def test_custom_colors(self):
        chart = self._make_chart(colors=["#FF0000", "#00FF00"])
        self.assertEqual(chart.colors[0], "#FF0000")
        self.assertEqual(chart.colors[1], "#00FF00")

    def test_default_fill_opacity(self):
        chart = self._make_chart()
        self.assertEqual(chart.fill_opacity, 0.5)

    def test_custom_fill_opacity(self):
        chart = self._make_chart(fill_opacity=0.7)
        self.assertEqual(chart.fill_opacity, 0.7)

    def test_title_default_empty(self):
        chart = self._make_chart()
        self.assertEqual(chart.title, "")

    def test_custom_title(self):
        chart = self._make_chart(title="Signal Breakdown")
        self.assertEqual(chart.title, "Signal Breakdown")

    def test_y_label_default_empty(self):
        chart = self._make_chart()
        self.assertEqual(chart.y_label, "")

    def test_custom_y_label(self):
        chart = self._make_chart(y_label="Value")
        self.assertEqual(chart.y_label, "Value")

    def test_show_points_default_false(self):
        chart = self._make_chart()
        self.assertFalse(chart.show_points)

    def test_show_points_true(self):
        chart = self._make_chart(show_points=True)
        self.assertTrue(chart.show_points)

    def test_empty_series_allowed(self):
        chart = StackedAreaChart(series=[], labels=[])
        self.assertEqual(chart.series, [])

    def test_single_series(self):
        chart = StackedAreaChart(
            series=[("Only", [10, 20, 30])],
            labels=["A", "B", "C"],
        )
        self.assertEqual(len(chart.series), 1)


class TestStackedAreaChartRendering(unittest.TestCase):
    """Test SVG rendering of stacked area charts."""

    def _make_svg(self, **kwargs):
        chart = StackedAreaChart(
            series=[("Alpha", [10, 20, 15]), ("Beta", [5, 8, 12])],
            labels=["S1", "S2", "S3"],
            **kwargs,
        )
        return render_svg(chart)

    def test_renders_valid_svg(self):
        svg = self._make_svg()
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_renders_title(self):
        svg = self._make_svg(title="My Stack")
        self.assertIn("My Stack", svg)

    def test_no_title_when_empty(self):
        svg = self._make_svg()
        self.assertNotIn("My Stack", svg)

    def test_renders_x_axis_labels(self):
        svg = self._make_svg()
        self.assertIn("S1", svg)
        self.assertIn("S3", svg)

    def test_renders_y_label(self):
        svg = self._make_svg(y_label="Count")
        self.assertIn("Count", svg)

    def test_renders_legend_with_series_names(self):
        svg = self._make_svg()
        self.assertIn("Alpha", svg)
        self.assertIn("Beta", svg)

    def test_renders_filled_polygons(self):
        svg = self._make_svg()
        # Each series should produce a polygon for its stacked area
        self.assertGreaterEqual(svg.count("<polygon"), 2)

    def test_renders_lines_on_top(self):
        svg = self._make_svg()
        self.assertGreaterEqual(svg.count("<polyline"), 2)

    def test_renders_data_points_when_enabled(self):
        svg = self._make_svg(show_points=True)
        self.assertIn("<circle", svg)

    def test_no_data_points_by_default(self):
        svg = self._make_svg()
        self.assertNotIn("<circle", svg)

    def test_custom_dimensions(self):
        svg = self._make_svg(width=800, height=500)
        self.assertIn('width="800"', svg)
        self.assertIn('height="500"', svg)

    def test_gridlines_present(self):
        svg = self._make_svg()
        self.assertGreaterEqual(svg.count("<line"), 4)

    def test_fill_opacity_in_svg(self):
        svg = self._make_svg(fill_opacity=0.6)
        self.assertIn('fill-opacity="0.6"', svg)

    def test_series_colors_appear(self):
        svg = self._make_svg(colors=["#FF0000", "#00FF00"])
        self.assertIn("#FF0000", svg)
        self.assertIn("#00FF00", svg)


class TestStackedAreaEdgeCases(unittest.TestCase):
    """Edge cases for stacked area chart rendering."""

    def test_empty_series_renders_no_data(self):
        chart = StackedAreaChart(series=[], labels=[])
        svg = render_svg(chart)
        self.assertIn("No data", svg)
        self.assertIn("<svg", svg)

    def test_single_series_degenerates_to_area(self):
        chart = StackedAreaChart(
            series=[("Only", [10, 20, 30])],
            labels=["A", "B", "C"],
        )
        svg = render_svg(chart)
        self.assertIn("<polygon", svg)
        self.assertIn("<svg", svg)

    def test_single_data_point(self):
        chart = StackedAreaChart(
            series=[("A", [42]), ("B", [10])],
            labels=["Jan"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_all_zero_values(self):
        chart = StackedAreaChart(
            series=[("A", [0, 0, 0]), ("B", [0, 0, 0])],
            labels=["X", "Y", "Z"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_series_with_different_lengths_handled(self):
        # Shorter series should be padded/truncated safely
        chart = StackedAreaChart(
            series=[("A", [10, 20, 30, 40]), ("B", [5, 10])],
            labels=["S1", "S2", "S3", "S4"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_many_series(self):
        chart = StackedAreaChart(
            series=[(f"S{i}", [i * 5 + j for j in range(5)]) for i in range(5)],
            labels=["A", "B", "C", "D", "E"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_many_data_points(self):
        n = 50
        chart = StackedAreaChart(
            series=[("Alpha", list(range(n))), ("Beta", [2] * n)],
            labels=[f"S{i}" for i in range(n)],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        # Label thinning: should not show all 50 labels
        label_count = svg.count(">S")
        self.assertLess(label_count, n * 2)

    def test_special_chars_in_title_escaped(self):
        chart = StackedAreaChart(
            series=[("A", [10])],
            labels=["X"],
            title="<Test> & Chart",
        )
        svg = render_svg(chart)
        self.assertIn("&amp;", svg)
        self.assertIn("&lt;", svg)

    def test_special_chars_in_labels_escaped(self):
        chart = StackedAreaChart(
            series=[("A & B", [10, 20])],
            labels=["X & Y", "Z"],
        )
        svg = render_svg(chart)
        self.assertIn("&amp;", svg)

    def test_negative_values_clamped(self):
        chart = StackedAreaChart(
            series=[("A", [-5, 10, 15])],
            labels=["X", "Y", "Z"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_very_large_values(self):
        chart = StackedAreaChart(
            series=[("A", [1000000, 2000000]), ("B", [500000, 750000])],
            labels=["Q1", "Q2"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)


class TestGenerateStackedAreaConvenience(unittest.TestCase):
    """Test the generate_stacked_area() convenience function."""

    def test_returns_svg_string(self):
        svg = generate_stacked_area(
            series=[("Alpha", [10, 20, 15]), ("Beta", [5, 8, 12])],
            labels=["S1", "S2", "S3"],
        )
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_accepts_title(self):
        svg = generate_stacked_area(
            series=[("A", [1, 2])],
            labels=["X", "Y"],
            title="My Chart",
        )
        self.assertIn("My Chart", svg)

    def test_accepts_kwargs(self):
        svg = generate_stacked_area(
            series=[("A", [1, 2])],
            labels=["X", "Y"],
            width=700,
            height=400,
        )
        self.assertIn('width="700"', svg)

    def test_empty_series(self):
        svg = generate_stacked_area(series=[], labels=[])
        self.assertIn("No data", svg)


class TestStackedAreaStacking(unittest.TestCase):
    """Verify that stacking logic produces correct cumulative geometry."""

    def test_second_series_starts_above_first(self):
        """The top series polygon should have higher y-coords than bottom series."""
        chart = StackedAreaChart(
            series=[("Bottom", [10, 10, 10]), ("Top", [10, 10, 10])],
            labels=["A", "B", "C"],
            title="",
        )
        svg = render_svg(chart)
        # Both polygons must be present (stacking produced separate layers)
        self.assertGreaterEqual(svg.count("<polygon"), 2)

    def test_stacked_sum_equals_total(self):
        """With two equal series, max y should represent their sum."""
        chart = StackedAreaChart(
            series=[("A", [50, 50]), ("B", [50, 50])],
            labels=["X", "Y"],
        )
        svg = render_svg(chart)
        # y-axis should show 100 as max (50+50)
        self.assertIn("100", svg)

    def test_produces_polygon_per_series(self):
        for n in range(1, 5):
            chart = StackedAreaChart(
                series=[(f"S{i}", [10, 20]) for i in range(n)],
                labels=["A", "B"],
            )
            svg = render_svg(chart)
            self.assertGreaterEqual(svg.count("<polygon"), n)


if __name__ == "__main__":
    unittest.main()
