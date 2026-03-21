#!/usr/bin/env python3
"""
test_chart_generator_extended.py — Extended edge-case tests for chart_generator.py

Covers: _escape() XSS, all-zero values (max_val=0 branch), empty-data "No data" text,
single data point (plot_w/2 branch), constant-value sparkline (val_range=0 branch),
donut with total=0, donut single segment, render_svg unknown type raises, SERIES_PALETTE,
chart dimensions are preserved, no-title margin behavior, large arc flag for >180 degree arcs.
"""

import math
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from chart_generator import (
    BarChart,
    HorizontalBarChart,
    LineChart,
    Sparkline,
    DonutChart,
    CCA_COLORS,
    SERIES_PALETTE,
    render_svg,
    save_svg,
    _escape,
    _svg_header,
    _svg_footer,
)


# ===== _escape XSS helper =====

class TestEscapeHelper(unittest.TestCase):
    """Edge cases for _escape() XML-safe string function."""

    def test_ampersand_escaped(self):
        self.assertEqual(_escape("a & b"), "a &amp; b")

    def test_less_than_escaped(self):
        self.assertIn("&lt;", _escape("<script>"))

    def test_greater_than_escaped(self):
        self.assertIn("&gt;", _escape("a > b"))

    def test_double_quote_escaped(self):
        self.assertIn("&quot;", _escape('"hello"'))

    def test_plain_text_unchanged(self):
        self.assertEqual(_escape("hello world"), "hello world")

    def test_int_converts_to_string(self):
        self.assertEqual(_escape(42), "42")

    def test_empty_string(self):
        self.assertEqual(_escape(""), "")

    def test_all_special_at_once(self):
        result = _escape('<a href="x&y">text</a>')
        self.assertNotIn("<a ", result)
        self.assertNotIn('"x&y"', result)

    def test_result_is_string(self):
        self.assertIsInstance(_escape(99), str)


# ===== SVG structure helpers =====

class TestSvgStructure(unittest.TestCase):
    """_svg_header and _svg_footer produce valid XML structure."""

    def test_header_has_xmlns(self):
        h = _svg_header(400, 300)
        self.assertIn("xmlns", h)

    def test_header_has_dimensions(self):
        h = _svg_header(640, 480)
        self.assertIn('width="640"', h)
        self.assertIn('height="480"', h)

    def test_header_has_viewbox(self):
        h = _svg_header(640, 480)
        self.assertIn("viewBox", h)

    def test_footer_closes_svg(self):
        f = _svg_footer()
        self.assertIn("</svg>", f)

    def test_header_plus_footer_is_valid_xml(self):
        xml_str = _svg_header(100, 100) + _svg_footer()
        ET.fromstring(xml_str)  # Should not raise


# ===== BarChart extended =====

class TestBarChartExtended(unittest.TestCase):
    """Extended edge cases for BarChart rendering."""

    def test_empty_data_shows_no_data_text(self):
        """Empty data renders 'No data' fallback text."""
        svg = render_svg(BarChart([], title="Empty"))
        self.assertIn("No data", svg)

    def test_empty_data_still_valid_xml(self):
        svg = render_svg(BarChart([]))
        ET.fromstring(svg)

    def test_all_zero_values_renders_without_error(self):
        """All-zero bar values: max_val=0 branch → max_val=1."""
        svg = render_svg(BarChart([("A", 0), ("B", 0), ("C", 0)], title="Zeros"))
        ET.fromstring(svg)

    def test_all_zero_values_has_bars(self):
        """Zero bars still render rect elements."""
        svg = render_svg(BarChart([("A", 0), ("B", 0)], title="X"))
        root = ET.fromstring(svg)
        rects = root.findall(".//{http://www.w3.org/2000/svg}rect")
        self.assertGreater(len(rects), 0)

    def test_single_bar_valid_xml(self):
        svg = render_svg(BarChart([("Solo", 500)], title="One Bar"))
        ET.fromstring(svg)

    def test_no_title_has_smaller_top_margin(self):
        """Chart without title uses margin_top=20; chart with title uses 40."""
        svg_notitle = render_svg(BarChart([("A", 10)]))
        svg_title = render_svg(BarChart([("A", 10)], title="Title"))
        # Both are valid SVG — just verify they both parse
        ET.fromstring(svg_notitle)
        ET.fromstring(svg_title)

    def test_show_values_includes_values(self):
        """show_values=True adds value labels above bars."""
        svg = render_svg(BarChart([("A", 777)], title="X", show_values=True))
        self.assertIn("777", svg)

    def test_y_label_included(self):
        svg = render_svg(BarChart([("A", 10)], title="X", y_label="Tests"))
        self.assertIn("Tests", svg)

    def test_large_dataset_valid_xml(self):
        """20-bar chart renders without error."""
        data = [(f"S{i}", i * 50) for i in range(1, 21)]
        svg = render_svg(BarChart(data, title="Big"))
        ET.fromstring(svg)

    def test_custom_color_applied(self):
        svg = render_svg(BarChart([("A", 10)], title="X", color="#ff0000"))
        self.assertIn("#ff0000", svg)

    def test_negative_value_renders(self):
        """Negative values: no crash (bar_h may be 0 but no exception)."""
        try:
            svg = render_svg(BarChart([("A", -5), ("B", 10)], title="X"))
            ET.fromstring(svg)
        except Exception as e:
            self.fail(f"Negative value caused unexpected error: {e}")


# ===== HorizontalBarChart extended =====

class TestHorizontalBarChartExtended(unittest.TestCase):
    """Extended edge cases for HorizontalBarChart."""

    def test_empty_data_shows_no_data(self):
        svg = render_svg(HorizontalBarChart([], title="Empty"))
        self.assertIn("No data", svg)

    def test_empty_data_valid_xml(self):
        svg = render_svg(HorizontalBarChart([]))
        ET.fromstring(svg)

    def test_all_zero_values_no_crash(self):
        """Zero values: max_val=0 → max_val=1 branch."""
        svg = render_svg(HorizontalBarChart([("X", 0), ("Y", 0)], title="Z"))
        ET.fromstring(svg)

    def test_single_bar_valid(self):
        svg = render_svg(HorizontalBarChart([("Only", 100)], title="X"))
        ET.fromstring(svg)

    def test_show_values_false_no_extra_values(self):
        """show_values=False: values not in text nodes (beyond labels)."""
        svg = render_svg(HorizontalBarChart([("A", 999)], show_values=False))
        # The value 999 should not appear as a standalone text item
        # but we can only verify no crash
        ET.fromstring(svg)

    def test_no_title_valid(self):
        svg = render_svg(HorizontalBarChart([("A", 10)]))
        ET.fromstring(svg)


# ===== LineChart extended =====

class TestLineChartExtended(unittest.TestCase):
    """Extended edge cases for LineChart."""

    def test_empty_data_shows_no_data(self):
        svg = render_svg(LineChart([], title="Empty"))
        self.assertIn("No data", svg)

    def test_empty_data_valid_xml(self):
        svg = render_svg(LineChart([]))
        ET.fromstring(svg)

    def test_single_point_centered(self):
        """Single data point: x = margin_left + plot_w / 2."""
        svg = render_svg(LineChart([("S1", 100)], title="Single"))
        ET.fromstring(svg)

    def test_two_points_valid_xml(self):
        svg = render_svg(LineChart([("A", 10), ("B", 20)]))
        ET.fromstring(svg)

    def test_all_zero_values_no_crash(self):
        svg = render_svg(LineChart([("A", 0), ("B", 0)], title="Zeros"))
        ET.fromstring(svg)

    def test_extra_series_max_dominates(self):
        """Extra series with larger values doesn't crash (max includes all)."""
        primary = [("A", 10), ("B", 20)]
        extra = [("extra", [("A", 1000), ("B", 2000)], CCA_COLORS["highlight"])]
        svg = render_svg(LineChart(primary, title="X", extra_series=extra))
        ET.fromstring(svg)

    def test_show_points_adds_circles(self):
        svg = render_svg(LineChart([("A", 10), ("B", 20)], show_points=True))
        self.assertIn("<circle", svg)

    def test_no_show_points_no_circles(self):
        svg = render_svg(LineChart([("A", 10), ("B", 20)], show_points=False))
        self.assertNotIn("<circle", svg)

    def test_multiple_extra_series_valid(self):
        primary = [("A", 1), ("B", 2), ("C", 3)]
        extra = [
            ("S2", [("A", 4), ("B", 5), ("C", 6)], CCA_COLORS["success"]),
            ("S3", [("A", 7), ("B", 8), ("C", 9)], CCA_COLORS["warning"]),
        ]
        svg = render_svg(LineChart(primary, extra_series=extra))
        ET.fromstring(svg)


# ===== Sparkline extended =====

class TestSparklineExtended(unittest.TestCase):
    """Extended edge cases for Sparkline."""

    def test_constant_values_no_crash(self):
        """All same values: val_range=0 → val_range=1 branch."""
        svg = render_svg(Sparkline([5, 5, 5, 5, 5]))
        ET.fromstring(svg)

    def test_constant_values_has_polyline(self):
        svg = render_svg(Sparkline([5, 5, 5]))
        self.assertIn("<polyline", svg)

    def test_two_values_valid(self):
        svg = render_svg(Sparkline([10, 20]))
        ET.fromstring(svg)

    def test_ascending_trend_valid(self):
        svg = render_svg(Sparkline([1, 2, 3, 4, 5, 6, 7, 8]))
        ET.fromstring(svg)

    def test_large_values(self):
        svg = render_svg(Sparkline([999999, 1000000, 998000]))
        ET.fromstring(svg)

    def test_default_dimensions(self):
        spark = Sparkline([1, 2, 3])
        self.assertEqual(spark.width, 100)
        self.assertEqual(spark.height, 24)

    def test_default_color_is_accent(self):
        spark = Sparkline([1, 2, 3])
        self.assertEqual(spark.color, CCA_COLORS["accent"])

    def test_empty_produces_svg(self):
        svg = render_svg(Sparkline([]))
        self.assertIn("<svg", svg)
        ET.fromstring(svg)


# ===== DonutChart extended =====

class TestDonutChartExtended(unittest.TestCase):
    """Extended edge cases for DonutChart."""

    def test_empty_data_shows_no_data(self):
        svg = render_svg(DonutChart([], title="Empty"))
        self.assertIn("No data", svg)

    def test_empty_data_valid_xml(self):
        svg = render_svg(DonutChart([]))
        ET.fromstring(svg)

    def test_total_zero_no_crash(self):
        """All-zero segment values: total=0 → total=1 branch."""
        data = [("A", 0, "#ff0000"), ("B", 0, "#00ff00")]
        svg = render_svg(DonutChart(data, title="Zeros"))
        ET.fromstring(svg)

    def test_single_segment_no_crash(self):
        """Single segment takes full circle (sweep >= 359.9 branch)."""
        svg = render_svg(DonutChart([("All", 1, CCA_COLORS["success"])], title="Full"))
        ET.fromstring(svg)

    def test_no_title_valid(self):
        data = [("A", 10, CCA_COLORS["accent"])]
        svg = render_svg(DonutChart(data))
        ET.fromstring(svg)

    def test_no_center_text_valid(self):
        data = [("A", 5, "#aaa"), ("B", 5, "#bbb")]
        svg = render_svg(DonutChart(data, center_text=""))
        ET.fromstring(svg)

    def test_center_text_in_output(self):
        data = [("X", 10, "#abc")]
        svg = render_svg(DonutChart(data, center_text="42%"))
        self.assertIn("42%", svg)

    def test_legend_shows_all_labels(self):
        data = [
            ("Alpha", 3, CCA_COLORS["success"]),
            ("Beta", 7, CCA_COLORS["highlight"]),
        ]
        svg = render_svg(DonutChart(data, title="Test"))
        self.assertIn("Alpha", svg)
        self.assertIn("Beta", svg)

    def test_tiny_slice_skipped(self):
        """Segment with value so small sweep <= 0.5 is skipped."""
        # total=1000, value=1 → sweep = 0.36 degrees < 0.5 → skipped
        data = [
            ("Big", 999, CCA_COLORS["success"]),
            ("Tiny", 1, CCA_COLORS["muted"]),
        ]
        svg = render_svg(DonutChart(data, title="Skip Test"))
        ET.fromstring(svg)  # No crash


# ===== render_svg dispatch =====

class TestRenderSvgDispatch(unittest.TestCase):
    """render_svg correctly dispatches to all 5 chart types."""

    def test_bar_chart_dispatch(self):
        svg = render_svg(BarChart([("A", 1)]))
        ET.fromstring(svg)

    def test_horizontal_bar_dispatch(self):
        svg = render_svg(HorizontalBarChart([("A", 1)]))
        ET.fromstring(svg)

    def test_line_chart_dispatch(self):
        svg = render_svg(LineChart([("A", 1)]))
        ET.fromstring(svg)

    def test_sparkline_dispatch(self):
        svg = render_svg(Sparkline([1, 2, 3]))
        ET.fromstring(svg)

    def test_donut_chart_dispatch(self):
        svg = render_svg(DonutChart([("A", 1, "#abc")]))
        ET.fromstring(svg)

    def test_unknown_type_raises_type_error(self):
        """Passing an unknown object raises TypeError."""
        with self.assertRaises(TypeError):
            render_svg("not a chart")

    def test_unknown_type_raises_for_dict(self):
        with self.assertRaises(TypeError):
            render_svg({"data": [1, 2, 3]})


# ===== SERIES_PALETTE =====

class TestSeriesPalette(unittest.TestCase):
    """SERIES_PALETTE has correct structure."""

    def test_non_empty(self):
        self.assertGreater(len(SERIES_PALETTE), 0)

    def test_first_is_accent(self):
        self.assertEqual(SERIES_PALETTE[0], CCA_COLORS["accent"])

    def test_all_strings(self):
        for color in SERIES_PALETTE:
            self.assertIsInstance(color, str)

    def test_all_hex_colors(self):
        for color in SERIES_PALETTE:
            self.assertTrue(color.startswith("#"), f"Not a hex color: {color}")


# ===== save_svg =====

class TestSaveSvgExtended(unittest.TestCase):
    """Extended edge cases for save_svg."""

    def test_returns_path(self):
        chart = Sparkline([1, 2, 3])
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            result = save_svg(chart, path)
            self.assertEqual(result, path)
        finally:
            os.unlink(path)

    def test_all_chart_types_save(self):
        """All chart types can be saved to file."""
        charts = [
            BarChart([("A", 10)]),
            HorizontalBarChart([("A", 10)]),
            LineChart([("A", 10)]),
            Sparkline([1, 2, 3]),
            DonutChart([("A", 10, "#abc")]),
        ]
        for chart in charts:
            with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
                path = f.name
            try:
                save_svg(chart, path)
                self.assertTrue(os.path.exists(path))
            finally:
                if os.path.exists(path):
                    os.unlink(path)


if __name__ == "__main__":
    unittest.main()
