"""Tests for SVG chart generator (MT-17 Phase 4).

Verifies chart_generator.py produces valid SVG charts following
the CCA design language (colors, typography, layout rules).
"""

import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from chart_generator import (
    BarChart,
    HorizontalBarChart,
    LineChart,
    Sparkline,
    DonutChart,
    CCA_COLORS,
    render_svg,
    save_svg,
    _format_tick_value,
    _abbreviate_label,
)


class TestCCAColors(unittest.TestCase):
    """Test design language color constants."""

    def test_primary_color(self):
        self.assertEqual(CCA_COLORS["primary"], "#1a1a2e")

    def test_accent_color(self):
        self.assertEqual(CCA_COLORS["accent"], "#0f3460")

    def test_highlight_color(self):
        self.assertEqual(CCA_COLORS["highlight"], "#e94560")

    def test_success_color(self):
        self.assertEqual(CCA_COLORS["success"], "#16c79a")

    def test_muted_color(self):
        self.assertEqual(CCA_COLORS["muted"], "#6b7280")

    def test_all_required_colors_present(self):
        required = {"primary", "accent", "highlight", "success", "muted",
                     "background", "surface", "border"}
        self.assertTrue(required.issubset(set(CCA_COLORS.keys())))


class TestBarChart(unittest.TestCase):
    """Test vertical bar chart generation."""

    def setUp(self):
        self.data = [
            ("S45", 800), ("S46", 1200), ("S47", 1500), ("S48", 1686),
        ]

    def test_returns_valid_svg(self):
        chart = BarChart(self.data, title="Tests Over Sessions")
        svg = render_svg(chart)
        # Should parse as XML
        ET.fromstring(svg)

    def test_svg_has_svg_namespace(self):
        chart = BarChart(self.data, title="X")
        svg = render_svg(chart)
        self.assertIn("xmlns", svg)

    def test_contains_title(self):
        chart = BarChart(self.data, title="Test Count")
        svg = render_svg(chart)
        self.assertIn("Test Count", svg)

    def test_contains_labels(self):
        chart = BarChart(self.data, title="X")
        svg = render_svg(chart)
        for label, _ in self.data:
            self.assertIn(label, svg)

    def test_contains_bars(self):
        chart = BarChart(self.data, title="X")
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_uses_accent_color(self):
        chart = BarChart(self.data, title="X")
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["accent"], svg)

    def test_custom_color(self):
        chart = BarChart(self.data, title="X", color=CCA_COLORS["success"])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["success"], svg)

    def test_empty_data(self):
        chart = BarChart([], title="Empty")
        svg = render_svg(chart)
        ET.fromstring(svg)  # Should still be valid SVG

    def test_single_bar(self):
        chart = BarChart([("A", 100)], title="One")
        svg = render_svg(chart)
        ET.fromstring(svg)

    def test_custom_dimensions(self):
        chart = BarChart(self.data, title="X", width=800, height=400)
        svg = render_svg(chart)
        self.assertIn('width="800"', svg)
        self.assertIn('height="400"', svg)

    def test_y_axis_label(self):
        chart = BarChart(self.data, title="X", y_label="Count")
        svg = render_svg(chart)
        self.assertIn("Count", svg)

    def test_value_labels_on_bars(self):
        chart = BarChart(self.data, title="X", show_values=True)
        svg = render_svg(chart)
        self.assertIn("1686", svg)


class TestHorizontalBarChart(unittest.TestCase):
    """Test horizontal bar chart generation."""

    def setUp(self):
        self.data = [
            ("Memory", 94), ("Spec", 90), ("Context", 232),
            ("Agent Guard", 264), ("Reddit Intel", 263),
        ]

    def test_returns_valid_svg(self):
        chart = HorizontalBarChart(self.data, title="Tests by Module")
        svg = render_svg(chart)
        ET.fromstring(svg)

    def test_contains_labels(self):
        chart = HorizontalBarChart(self.data, title="X")
        svg = render_svg(chart)
        self.assertIn("Memory", svg)
        self.assertIn("Agent Guard", svg)

    def test_bars_are_horizontal(self):
        """Horizontal bars should have varying width, not height."""
        chart = HorizontalBarChart(self.data, title="X")
        svg = render_svg(chart)
        # All bars exist
        root = ET.fromstring(svg)
        rects = root.findall(".//{http://www.w3.org/2000/svg}rect")
        self.assertTrue(len(rects) >= len(self.data))

    def test_show_values(self):
        chart = HorizontalBarChart(self.data, title="X", show_values=True)
        svg = render_svg(chart)
        self.assertIn("264", svg)


class TestLineChart(unittest.TestCase):
    """Test line chart generation."""

    def setUp(self):
        self.data = [
            ("S44", 600), ("S45", 800), ("S46", 1200),
            ("S47", 1500), ("S48", 1686),
        ]

    def test_returns_valid_svg(self):
        chart = LineChart(self.data, title="Test Growth")
        svg = render_svg(chart)
        ET.fromstring(svg)

    def test_contains_polyline_or_path(self):
        chart = LineChart(self.data, title="X")
        svg = render_svg(chart)
        self.assertTrue("<polyline" in svg or "<path" in svg)

    def test_contains_title(self):
        chart = LineChart(self.data, title="Growth Trend")
        svg = render_svg(chart)
        self.assertIn("Growth Trend", svg)

    def test_contains_data_points(self):
        chart = LineChart(self.data, title="X", show_points=True)
        svg = render_svg(chart)
        self.assertIn("<circle", svg)

    def test_contains_labels(self):
        chart = LineChart(self.data, title="X")
        svg = render_svg(chart)
        self.assertIn("S44", svg)

    def test_multiple_series(self):
        series2 = [("S44", 10), ("S45", 15), ("S46", 18), ("S47", 20), ("S48", 22)]
        chart = LineChart(
            self.data, title="X",
            extra_series=[("Suites", series2, CCA_COLORS["success"])],
        )
        svg = render_svg(chart)
        ET.fromstring(svg)

    def test_y_axis_label(self):
        chart = LineChart(self.data, title="X", y_label="Tests")
        svg = render_svg(chart)
        self.assertIn("Tests", svg)


class TestSparkline(unittest.TestCase):
    """Test compact sparkline generation."""

    def setUp(self):
        self.values = [10, 15, 12, 18, 22, 20, 25]

    def test_returns_valid_svg(self):
        spark = Sparkline(self.values)
        svg = render_svg(spark)
        ET.fromstring(svg)

    def test_compact_dimensions(self):
        spark = Sparkline(self.values, width=100, height=20)
        svg = render_svg(spark)
        self.assertIn('width="100"', svg)
        self.assertIn('height="20"', svg)

    def test_contains_line(self):
        spark = Sparkline(self.values)
        svg = render_svg(spark)
        self.assertTrue("<polyline" in svg or "<path" in svg)

    def test_empty_values(self):
        spark = Sparkline([])
        svg = render_svg(spark)
        ET.fromstring(svg)

    def test_single_value(self):
        spark = Sparkline([42])
        svg = render_svg(spark)
        ET.fromstring(svg)

    def test_custom_color(self):
        spark = Sparkline(self.values, color=CCA_COLORS["highlight"])
        svg = render_svg(spark)
        self.assertIn(CCA_COLORS["highlight"], svg)


class TestDonutChart(unittest.TestCase):
    """Test donut chart (the one exception to bar-chart-over-pie rule,
    used for completion/progress indicators)."""

    def setUp(self):
        self.data = [
            ("Complete", 15, CCA_COLORS["success"]),
            ("In Progress", 3, CCA_COLORS["accent"]),
            ("Not Started", 2, CCA_COLORS["muted"]),
        ]

    def test_returns_valid_svg(self):
        chart = DonutChart(self.data, title="MT Status")
        svg = render_svg(chart)
        ET.fromstring(svg)

    def test_contains_arcs(self):
        chart = DonutChart(self.data, title="X")
        svg = render_svg(chart)
        self.assertIn("<path", svg)

    def test_contains_title(self):
        chart = DonutChart(self.data, title="Task Completion")
        svg = render_svg(chart)
        self.assertIn("Task Completion", svg)

    def test_contains_legend(self):
        chart = DonutChart(self.data, title="X")
        svg = render_svg(chart)
        self.assertIn("Complete", svg)
        self.assertIn("In Progress", svg)

    def test_center_text(self):
        chart = DonutChart(self.data, title="X", center_text="75%")
        svg = render_svg(chart)
        self.assertIn("75%", svg)


class TestSaveSVG(unittest.TestCase):
    """Test SVG file saving."""

    def test_saves_to_file(self):
        chart = BarChart([("A", 10)], title="Save Test")
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            save_svg(chart, path)
            self.assertTrue(os.path.isfile(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("<svg", content)
        finally:
            os.unlink(path)

    def test_saved_file_is_valid_xml(self):
        chart = LineChart([("A", 1), ("B", 2)], title="XML Test")
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            save_svg(chart, path)
            with open(path) as f:
                ET.parse(f)  # Should not raise
        finally:
            os.unlink(path)


class TestFormatTickValue(unittest.TestCase):
    """Test the shared y-axis tick formatter (MT-48)."""

    def test_integer_mode_whole_number(self):
        self.assertEqual(_format_tick_value(100.0, True), "100")

    def test_integer_mode_fractional_rounds(self):
        # 400 * 1/4 = 100.0, 400 * 3/4 = 300.0 — always exact for /4 ticks
        self.assertEqual(_format_tick_value(300.0, True), "300")

    def test_integer_mode_non_exact_quarter(self):
        # e.g. max_val=7, tick at 7*1/4 = 1.75 -> rounds to 2
        result = _format_tick_value(1.75, True)
        self.assertEqual(result, "2")

    def test_float_mode_whole_number(self):
        self.assertEqual(_format_tick_value(5.0, False), "5")

    def test_float_mode_fractional(self):
        self.assertEqual(_format_tick_value(2.5, False), "2.5")

    def test_zero(self):
        self.assertEqual(_format_tick_value(0.0, True), "0")
        self.assertEqual(_format_tick_value(0.0, False), "0")


class TestAbbreviateLabel(unittest.TestCase):
    """Test smart label truncation (MT-48)."""

    def test_short_label_unchanged(self):
        self.assertEqual(_abbreviate_label("MT-7", 10), "MT-7")

    def test_exact_length_unchanged(self):
        self.assertEqual(_abbreviate_label("1234567890", 10), "1234567890")

    def test_long_label_truncated_with_ellipsis(self):
        result = _abbreviate_label("Very Long Label Name", 10)
        self.assertEqual(len(result), 10)
        self.assertTrue(result.endswith("\u2026"))

    def test_non_string_input(self):
        self.assertEqual(_abbreviate_label(42, 10), "42")

    def test_empty_string(self):
        self.assertEqual(_abbreviate_label("", 10), "")


class TestLineChartIntegerYAxis(unittest.TestCase):
    """Test that LineChart uses integer y-axis ticks for integer data (MT-48)."""

    def test_integer_data_no_decimal_ticks(self):
        data = [("A", 100), ("B", 200), ("C", 400)]
        chart = LineChart(data, title="Integer Test")
        svg = render_svg(chart)
        # Should NOT contain decimal ticks like "100.0" or "200.0"
        self.assertNotIn(">100.0<", svg)
        self.assertNotIn(">200.0<", svg)
        # Should contain clean integer ticks
        self.assertIn(">100<", svg)
        self.assertIn(">200<", svg)

    def test_bar_chart_integer_ticks(self):
        data = [("X", 50), ("Y", 100)]
        chart = BarChart(data, title="Bar Int Test")
        svg = render_svg(chart)
        self.assertNotIn(">50.0<", svg)
        self.assertIn(">50<", svg)


if __name__ == "__main__":
    unittest.main()
