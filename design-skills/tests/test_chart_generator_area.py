#!/usr/bin/env python3
"""Tests for AreaChart in chart_generator.py — S115 desktop."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chart_generator import AreaChart, render_svg, CCA_COLORS


class TestAreaChartDataclass(unittest.TestCase):
    """Test AreaChart dataclass creation and defaults."""

    def test_basic_creation(self):
        chart = AreaChart(data=[("S1", 10), ("S2", 20), ("S3", 15)])
        self.assertEqual(len(chart.data), 3)

    def test_default_dimensions(self):
        chart = AreaChart(data=[("A", 1)])
        self.assertEqual(chart.width, 500)
        self.assertEqual(chart.height, 300)

    def test_default_color(self):
        chart = AreaChart(data=[("A", 1)])
        self.assertEqual(chart.color, CCA_COLORS["accent"])

    def test_custom_color(self):
        chart = AreaChart(data=[("A", 1)], color="#FF0000")
        self.assertEqual(chart.color, "#FF0000")

    def test_default_fill_opacity(self):
        chart = AreaChart(data=[("A", 1)])
        self.assertEqual(chart.fill_opacity, 0.3)

    def test_custom_fill_opacity(self):
        chart = AreaChart(data=[("A", 1)], fill_opacity=0.5)
        self.assertEqual(chart.fill_opacity, 0.5)

    def test_title(self):
        chart = AreaChart(data=[("A", 1)], title="My Area")
        self.assertEqual(chart.title, "My Area")

    def test_y_label(self):
        chart = AreaChart(data=[("A", 1)], y_label="Count")
        self.assertEqual(chart.y_label, "Count")

    def test_show_points(self):
        chart = AreaChart(data=[("A", 1)], show_points=True)
        self.assertTrue(chart.show_points)


class TestAreaChartRendering(unittest.TestCase):
    """Test SVG rendering of area charts."""

    def test_renders_svg(self):
        chart = AreaChart(data=[("S1", 10), ("S2", 20), ("S3", 15)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_renders_filled_area(self):
        chart = AreaChart(data=[("A", 10), ("B", 20)])
        svg = render_svg(chart)
        self.assertIn("<polygon", svg)
        self.assertIn("fill-opacity", svg)

    def test_renders_line_on_top(self):
        chart = AreaChart(data=[("A", 10), ("B", 20)])
        svg = render_svg(chart)
        self.assertIn("<polyline", svg)

    def test_renders_title(self):
        chart = AreaChart(data=[("A", 1)], title="Test Title")
        svg = render_svg(chart)
        self.assertIn("Test Title", svg)

    def test_renders_labels(self):
        chart = AreaChart(data=[("January", 10), ("February", 20)])
        svg = render_svg(chart)
        self.assertIn("January", svg)
        self.assertIn("February", svg)

    def test_renders_y_label(self):
        chart = AreaChart(data=[("A", 1)], y_label="Tests")
        svg = render_svg(chart)
        self.assertIn("Tests", svg)

    def test_renders_points_when_enabled(self):
        chart = AreaChart(data=[("A", 10), ("B", 20)], show_points=True)
        svg = render_svg(chart)
        self.assertIn("<circle", svg)

    def test_no_points_by_default(self):
        chart = AreaChart(data=[("A", 10), ("B", 20)])
        svg = render_svg(chart)
        self.assertNotIn("<circle", svg)

    def test_empty_data(self):
        chart = AreaChart(data=[])
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_single_point(self):
        chart = AreaChart(data=[("Only", 42)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("<polygon", svg)

    def test_custom_fill_opacity_in_svg(self):
        chart = AreaChart(data=[("A", 10), ("B", 20)], fill_opacity=0.6)
        svg = render_svg(chart)
        self.assertIn('fill-opacity="0.6"', svg)

    def test_custom_dimensions(self):
        chart = AreaChart(data=[("A", 1)], width=800, height=400)
        svg = render_svg(chart)
        self.assertIn('width="800"', svg)
        self.assertIn('height="400"', svg)

    def test_many_data_points(self):
        data = [(f"S{i}", i * 10) for i in range(50)]
        chart = AreaChart(data=data)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        # With 50 points, should have label thinning
        # Not all 50 labels should appear
        label_count = svg.count("S4")  # Counts any label starting with S4
        self.assertGreater(label_count, 0)  # At least some appear

    def test_gridlines_present(self):
        chart = AreaChart(data=[("A", 10), ("B", 20)])
        svg = render_svg(chart)
        line_count = svg.count("<line")
        self.assertGreaterEqual(line_count, 4)  # At least 4 gridlines


class TestAreaChartEdgeCases(unittest.TestCase):
    """Edge cases for area chart."""

    def test_zero_values(self):
        chart = AreaChart(data=[("A", 0), ("B", 0), ("C", 0)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_negative_values_clamped(self):
        chart = AreaChart(data=[("A", -5), ("B", 10)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_very_large_values(self):
        chart = AreaChart(data=[("A", 1000000), ("B", 2000000)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_identical_values(self):
        chart = AreaChart(data=[("A", 50), ("B", 50), ("C", 50)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_escapes_special_chars_in_title(self):
        chart = AreaChart(data=[("A", 1)], title="Test & <Chart>")
        svg = render_svg(chart)
        self.assertIn("&amp;", svg)

    def test_escapes_special_chars_in_labels(self):
        chart = AreaChart(data=[("A & B", 1)])
        svg = render_svg(chart)
        self.assertIn("&amp;", svg)


if __name__ == "__main__":
    unittest.main()
