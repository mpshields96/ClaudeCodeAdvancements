"""Tests for RadarChart in chart_generator.py."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from chart_generator import RadarChart, render_svg, CCA_COLORS


class TestRadarChartDataclass(unittest.TestCase):
    """Tests for the RadarChart dataclass."""

    def test_defaults(self):
        chart = RadarChart(data=[("A", 80), ("B", 60), ("C", 90)])
        self.assertEqual(chart.title, "")
        self.assertEqual(chart.width, 400)
        self.assertEqual(chart.height, 400)
        self.assertEqual(chart.max_value, 0.0)
        self.assertEqual(chart.fill_opacity, 0.2)
        self.assertEqual(chart.extra_series, [])
        self.assertEqual(chart.color, CCA_COLORS["accent"])

    def test_custom_dimensions(self):
        chart = RadarChart(data=[("A", 80), ("B", 60), ("C", 90)],
                           width=600, height=600)
        self.assertEqual(chart.width, 600)
        self.assertEqual(chart.height, 600)

    def test_custom_title(self):
        chart = RadarChart(data=[("A", 80), ("B", 60), ("C", 90)],
                           title="Quality Scores")
        self.assertEqual(chart.title, "Quality Scores")

    def test_custom_max_value(self):
        chart = RadarChart(data=[("A", 80), ("B", 60), ("C", 90)],
                           max_value=100.0)
        self.assertEqual(chart.max_value, 100.0)

    def test_custom_fill_opacity(self):
        chart = RadarChart(data=[("A", 80), ("B", 60), ("C", 90)],
                           fill_opacity=0.4)
        self.assertEqual(chart.fill_opacity, 0.4)

    def test_custom_color(self):
        chart = RadarChart(data=[("A", 80), ("B", 60), ("C", 90)],
                           color="#ff0000")
        self.assertEqual(chart.color, "#ff0000")

    def test_extra_series(self):
        chart = RadarChart(
            data=[("A", 80), ("B", 60), ("C", 90)],
            extra_series=[("Baseline", [("A", 50), ("B", 50), ("C", 50)], "#aabbcc")]
        )
        self.assertEqual(len(chart.extra_series), 1)


class TestRadarChartNoData(unittest.TestCase):
    """Tests for empty data handling."""

    def test_empty_data_returns_svg(self):
        chart = RadarChart(data=[])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_empty_data_shows_no_data(self):
        chart = RadarChart(data=[])
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_empty_data_uses_font_size_14(self):
        chart = RadarChart(data=[])
        svg = render_svg(chart)
        self.assertIn('font-size="14"', svg)


class TestRadarChartSVGStructure(unittest.TestCase):
    """Tests for SVG structure correctness."""

    def setUp(self):
        self.data = [("Speed", 80), ("Power", 60), ("Range", 90),
                     ("Accuracy", 75), ("Cost", 50)]
        self.chart = RadarChart(data=self.data, title="Robot Skills")

    def test_svg_header(self):
        svg = render_svg(self.chart)
        self.assertTrue(svg.strip().startswith("<svg"))

    def test_svg_footer(self):
        svg = render_svg(self.chart)
        self.assertTrue(svg.strip().endswith("</svg>"))

    def test_viewbox_matches_dimensions(self):
        svg = render_svg(self.chart)
        self.assertIn('viewBox="0 0 400 400"', svg)

    def test_custom_viewbox(self):
        chart = RadarChart(data=self.data, width=600, height=600)
        svg = render_svg(chart)
        self.assertIn('viewBox="0 0 600 600"', svg)

    def test_title_rendered(self):
        svg = render_svg(self.chart)
        self.assertIn("Robot Skills", svg)

    def test_background_rect(self):
        svg = render_svg(self.chart)
        self.assertIn(CCA_COLORS["background"], svg)

    def test_has_polygon_elements(self):
        svg = render_svg(self.chart)
        self.assertIn("<polygon", svg)

    def test_has_line_elements_for_axes(self):
        svg = render_svg(self.chart)
        self.assertIn("<line", svg)

    def test_has_text_elements_for_labels(self):
        svg = render_svg(self.chart)
        self.assertIn("<text", svg)

    def test_has_circle_elements_for_points(self):
        svg = render_svg(self.chart)
        self.assertIn("<circle", svg)


class TestRadarChartAxes(unittest.TestCase):
    """Tests for axis/grid rendering."""

    def test_axis_labels_rendered(self):
        data = [("Speed", 80), ("Power", 60), ("Range", 90)]
        chart = RadarChart(data=data)
        svg = render_svg(chart)
        self.assertIn("Speed", svg)
        self.assertIn("Power", svg)
        self.assertIn("Range", svg)

    def test_min_three_axes(self):
        # Data with fewer than 3 items still renders (clamped to 3)
        data = [("A", 50), ("B", 75)]
        chart = RadarChart(data=data)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_max_eight_axes(self):
        # Data with more than 8 items is truncated to 8
        data = [(f"Axis{i}", i * 10) for i in range(10)]
        chart = RadarChart(data=data)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        # Only first 8 labels should appear
        self.assertIn("Axis0", svg)
        self.assertIn("Axis7", svg)

    def test_five_axes(self):
        data = [("A", 80), ("B", 60), ("C", 90), ("D", 75), ("E", 50)]
        chart = RadarChart(data=data)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_grid_polygons_at_four_levels(self):
        data = [("A", 80), ("B", 60), ("C", 90)]
        chart = RadarChart(data=data)
        svg = render_svg(chart)
        # 4 grid polygons (25%, 50%, 75%, 100%) + 1 data polygon = 5+ polygons
        self.assertGreaterEqual(svg.count("<polygon"), 5)

    def test_special_chars_in_labels_escaped(self):
        data = [("R&D", 80), ("Cost<>", 60), ("Power", 90)]
        chart = RadarChart(data=data)
        svg = render_svg(chart)
        self.assertIn("R&amp;D", svg)
        self.assertIn("Cost&lt;&gt;", svg)


class TestRadarChartSeries(unittest.TestCase):
    """Tests for multi-series support."""

    def test_single_series_renders(self):
        data = [("A", 80), ("B", 60), ("C", 90)]
        chart = RadarChart(data=data)
        svg = render_svg(chart)
        self.assertIn("<polygon", svg)

    def test_primary_series_color_used(self):
        data = [("A", 80), ("B", 60), ("C", 90)]
        chart = RadarChart(data=data, color=CCA_COLORS["accent"])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["accent"], svg)

    def test_extra_series_rendered(self):
        data = [("A", 80), ("B", 60), ("C", 90)]
        extra = [("Baseline", [("A", 50), ("B", 50), ("C", 50)], "#ff5500")]
        chart = RadarChart(data=data, extra_series=extra)
        svg = render_svg(chart)
        self.assertIn("#ff5500", svg)

    def test_extra_series_adds_more_polygons(self):
        data = [("A", 80), ("B", 60), ("C", 90)]
        chart_single = RadarChart(data=data)
        svg_single = render_svg(chart_single)
        extra = [("B", [("A", 50), ("B", 50), ("C", 50)], "#ff5500")]
        chart_multi = RadarChart(data=data, extra_series=extra)
        svg_multi = render_svg(chart_multi)
        # More polygon elements with extra series
        self.assertGreater(svg_multi.count("<polygon"), svg_single.count("<polygon"))

    def test_custom_max_value_scales_chart(self):
        data = [("A", 50), ("B", 50), ("C", 50)]
        chart = RadarChart(data=data, max_value=100.0)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)


class TestRadarChartTextHelper(unittest.TestCase):
    """Tests confirming _text() is used for all text rendering."""

    def test_all_text_has_font_family(self):
        data = [("Speed", 80), ("Power", 60), ("Range", 90)]
        chart = RadarChart(data=data, title="Test")
        svg = render_svg(chart)
        self.assertIn("font-family", svg)

    def test_no_title_no_title_text(self):
        data = [("Speed", 80), ("Power", 60), ("Range", 90)]
        chart = RadarChart(data=data)
        svg = render_svg(chart)
        # No bold title text
        self.assertNotIn('font-weight="bold"', svg)


if __name__ == "__main__":
    unittest.main()
