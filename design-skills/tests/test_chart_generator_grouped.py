#!/usr/bin/env python3
"""Tests for GroupedBarChart in chart_generator.py — S116 worker cli1."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chart_generator import GroupedBarChart, render_svg, generate_grouped_bar, CCA_COLORS, SERIES_PALETTE


class TestGroupedBarChartDataclass(unittest.TestCase):
    """Test GroupedBarChart dataclass creation and defaults."""

    def _make(self, **kwargs):
        return GroupedBarChart(
            data=[("S113", [100, 200, 150]), ("S114", [120, 180, 160])],
            series_names=["Memory", "Agent Guard", "Context Monitor"],
            **kwargs,
        )

    def test_basic_creation(self):
        chart = self._make()
        self.assertEqual(len(chart.data), 2)
        self.assertEqual(len(chart.series_names), 3)

    def test_default_dimensions(self):
        chart = self._make()
        self.assertEqual(chart.width, 500)
        self.assertEqual(chart.height, 300)

    def test_default_colors_match_series_count(self):
        chart = self._make()
        self.assertEqual(len(chart.colors), 3)

    def test_default_colors_from_palette(self):
        chart = self._make()
        self.assertEqual(chart.colors[0], SERIES_PALETTE[0])
        self.assertEqual(chart.colors[1], SERIES_PALETTE[1])

    def test_custom_colors(self):
        chart = self._make(colors=["#FF0000", "#00FF00", "#0000FF"])
        self.assertEqual(chart.colors[0], "#FF0000")

    def test_default_title_empty(self):
        chart = self._make()
        self.assertEqual(chart.title, "")

    def test_custom_title(self):
        chart = self._make(title="Test Growth by Module")
        self.assertEqual(chart.title, "Test Growth by Module")

    def test_default_y_label_empty(self):
        chart = self._make()
        self.assertEqual(chart.y_label, "")

    def test_custom_y_label(self):
        chart = self._make(y_label="Tests")
        self.assertEqual(chart.y_label, "Tests")

    def test_show_values_default_false(self):
        chart = self._make()
        self.assertFalse(chart.show_values)

    def test_show_values_true(self):
        chart = self._make(show_values=True)
        self.assertTrue(chart.show_values)

    def test_empty_data_allowed(self):
        chart = GroupedBarChart(data=[], series_names=[])
        self.assertEqual(chart.data, [])

    def test_single_series(self):
        chart = GroupedBarChart(
            data=[("A", [10]), ("B", [20])],
            series_names=["Count"],
        )
        self.assertEqual(len(chart.series_names), 1)

    def test_single_category(self):
        chart = GroupedBarChart(
            data=[("Only", [5, 10, 15])],
            series_names=["X", "Y", "Z"],
        )
        self.assertEqual(len(chart.data), 1)


class TestGroupedBarChartRendering(unittest.TestCase):
    """Test SVG rendering of grouped bar charts."""

    def _make_svg(self, **kwargs):
        chart = GroupedBarChart(
            data=[("S113", [100, 200]), ("S114", [120, 180]), ("S115", [150, 220])],
            series_names=["Memory", "Agent Guard"],
            **kwargs,
        )
        return render_svg(chart)

    def test_renders_valid_svg(self):
        svg = self._make_svg()
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_renders_title(self):
        svg = self._make_svg(title="Module Tests")
        self.assertIn("Module Tests", svg)

    def test_no_title_when_empty(self):
        svg = self._make_svg()
        self.assertNotIn("Module Tests", svg)

    def test_renders_category_labels(self):
        svg = self._make_svg()
        self.assertIn("S113", svg)
        self.assertIn("S114", svg)
        self.assertIn("S115", svg)

    def test_renders_series_legend(self):
        svg = self._make_svg()
        self.assertIn("Memory", svg)
        self.assertIn("Agent Guard", svg)

    def test_renders_bars(self):
        svg = self._make_svg()
        # Each of 3 categories × 2 series = 6 bars minimum
        self.assertGreaterEqual(svg.count("<rect"), 6)

    def test_renders_y_label(self):
        svg = self._make_svg(y_label="Tests")
        self.assertIn("Tests", svg)

    def test_renders_gridlines(self):
        svg = self._make_svg()
        self.assertGreaterEqual(svg.count("<line"), 4)

    def test_show_values_adds_text(self):
        # With show_values=True there should be more text elements than without
        svg_with = self._make_svg(show_values=True)
        svg_without = self._make_svg(show_values=False)
        self.assertGreater(svg_with.count("<text"), svg_without.count("<text"))

    def test_custom_dimensions(self):
        svg = self._make_svg(width=700, height=450)
        self.assertIn('width="700"', svg)
        self.assertIn('height="450"', svg)

    def test_viewbox_matches_dimensions(self):
        svg = self._make_svg(width=600, height=400)
        self.assertIn('viewBox="0 0 600 400"', svg)

    def test_custom_colors_in_svg(self):
        svg = render_svg(GroupedBarChart(
            data=[("A", [5, 10])],
            series_names=["X", "Y"],
            colors=["#AABBCC", "#DDEEFF"],
        ))
        self.assertIn("#AABBCC", svg)
        self.assertIn("#DDEEFF", svg)

    def test_title_font_size_14(self):
        svg = self._make_svg(title="Chart Title")
        self.assertIn('font-size="14"', svg)

    def test_empty_data_no_data_message(self):
        chart = GroupedBarChart(data=[], series_names=[])
        svg = render_svg(chart)
        self.assertIn("No data", svg)
        self.assertIn('font-size="14"', svg)


class TestGroupedBarChartEdgeCases(unittest.TestCase):
    """Edge cases for grouped bar chart."""

    def test_single_category_renders(self):
        chart = GroupedBarChart(
            data=[("Only", [5, 10])],
            series_names=["X", "Y"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("<rect", svg)

    def test_single_series_renders(self):
        chart = GroupedBarChart(
            data=[("A", [10]), ("B", [20])],
            series_names=["Count"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("<rect", svg)

    def test_all_zero_values(self):
        chart = GroupedBarChart(
            data=[("A", [0, 0]), ("B", [0, 0])],
            series_names=["X", "Y"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_negative_values_clamped(self):
        chart = GroupedBarChart(
            data=[("A", [-5, 10]), ("B", [3, -2])],
            series_names=["X", "Y"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_very_large_values(self):
        chart = GroupedBarChart(
            data=[("Q1", [1000000, 2000000])],
            series_names=["X", "Y"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_many_categories(self):
        data = [(f"S{i}", [i * 10, i * 5]) for i in range(1, 20)]
        chart = GroupedBarChart(data=data, series_names=["A", "B"])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_many_series(self):
        chart = GroupedBarChart(
            data=[("Cat", [i * 10 for i in range(6)])],
            series_names=[f"S{i}" for i in range(6)],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_series_values_shorter_than_series_names(self):
        # Values list shorter than series_names — should not crash
        chart = GroupedBarChart(
            data=[("A", [10])],  # Only 1 value but 3 series names
            series_names=["X", "Y", "Z"],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_special_chars_in_title_escaped(self):
        chart = GroupedBarChart(
            data=[("A", [1, 2])],
            series_names=["X", "Y"],
            title="<Test> & Chart",
        )
        svg = render_svg(chart)
        self.assertIn("&amp;", svg)
        self.assertIn("&lt;", svg)

    def test_special_chars_in_labels_escaped(self):
        chart = GroupedBarChart(
            data=[("A & B", [1, 2])],
            series_names=["X & Y", "Z"],
        )
        svg = render_svg(chart)
        self.assertIn("&amp;", svg)

    def test_special_chars_in_series_names_escaped(self):
        chart = GroupedBarChart(
            data=[("Cat", [5, 10])],
            series_names=["<Alpha>", "Beta & Gamma"],
        )
        svg = render_svg(chart)
        self.assertIn("&lt;", svg)
        self.assertIn("&amp;", svg)


class TestGenerateGroupedBarConvenience(unittest.TestCase):
    """Test generate_grouped_bar() convenience function."""

    def test_returns_svg_string(self):
        svg = generate_grouped_bar(
            data=[("S113", [100, 200]), ("S114", [120, 180])],
            series_names=["Memory", "Agent Guard"],
        )
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_accepts_title(self):
        svg = generate_grouped_bar(
            data=[("A", [1, 2])],
            series_names=["X", "Y"],
            title="My Chart",
        )
        self.assertIn("My Chart", svg)

    def test_accepts_kwargs(self):
        svg = generate_grouped_bar(
            data=[("A", [1, 2])],
            series_names=["X", "Y"],
            width=700,
            height=400,
        )
        self.assertIn('width="700"', svg)

    def test_empty_data(self):
        svg = generate_grouped_bar(data=[], series_names=[])
        self.assertIn("No data", svg)


class TestGroupedVsStackedSemantics(unittest.TestCase):
    """GroupedBarChart produces multiple side-by-side bars, not stacked."""

    def test_groups_bars_side_by_side(self):
        """With 2 categories × 3 series, expect at least 6 rects."""
        chart = GroupedBarChart(
            data=[("A", [10, 20, 30]), ("B", [15, 25, 35])],
            series_names=["S1", "S2", "S3"],
        )
        svg = render_svg(chart)
        # background + 6 data bars + legend swatches = many rects
        self.assertGreaterEqual(svg.count("<rect"), 6)

    def test_one_series_still_renders_bars(self):
        chart = GroupedBarChart(
            data=[("A", [10]), ("B", [20]), ("C", [15])],
            series_names=["Count"],
        )
        svg = render_svg(chart)
        self.assertGreaterEqual(svg.count("<rect"), 3)


if __name__ == "__main__":
    unittest.main()
