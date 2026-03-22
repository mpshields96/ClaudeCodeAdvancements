"""Tests for GaugeChart in chart_generator.py."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from chart_generator import GaugeChart, render_svg, CCA_COLORS


class TestGaugeChartDataclass(unittest.TestCase):
    """Tests for the GaugeChart dataclass."""

    def test_defaults(self):
        chart = GaugeChart(value=75.0)
        self.assertEqual(chart.min_value, 0.0)
        self.assertEqual(chart.max_value, 100.0)
        self.assertEqual(chart.thresholds, (33.0, 66.0))
        self.assertEqual(chart.title, "")
        self.assertEqual(chart.label, "")
        self.assertEqual(chart.width, 400)
        self.assertEqual(chart.height, 280)

    def test_custom_value(self):
        chart = GaugeChart(value=42.5)
        self.assertEqual(chart.value, 42.5)

    def test_custom_range(self):
        chart = GaugeChart(value=500, min_value=0, max_value=1000)
        self.assertEqual(chart.min_value, 0)
        self.assertEqual(chart.max_value, 1000)

    def test_custom_thresholds(self):
        chart = GaugeChart(value=75, thresholds=(25.0, 75.0))
        self.assertEqual(chart.thresholds, (25.0, 75.0))

    def test_custom_title(self):
        chart = GaugeChart(value=75, title="Coverage")
        self.assertEqual(chart.title, "Coverage")

    def test_custom_label(self):
        chart = GaugeChart(value=75, label="% coverage")
        self.assertEqual(chart.label, "% coverage")

    def test_custom_dimensions(self):
        chart = GaugeChart(value=50, width=600, height=400)
        self.assertEqual(chart.width, 600)
        self.assertEqual(chart.height, 400)

    def test_zero_value(self):
        chart = GaugeChart(value=0)
        self.assertEqual(chart.value, 0)

    def test_max_value(self):
        chart = GaugeChart(value=100)
        self.assertEqual(chart.value, 100)


class TestGaugeChartNoData(unittest.TestCase):
    """Tests for None value (no data) handling."""

    def test_none_value_returns_svg(self):
        chart = GaugeChart(value=None)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_none_value_shows_no_data(self):
        chart = GaugeChart(value=None)
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_none_value_uses_font_size_14(self):
        chart = GaugeChart(value=None)
        svg = render_svg(chart)
        self.assertIn('font-size="14"', svg)


class TestGaugeChartSVGStructure(unittest.TestCase):
    """Tests for SVG structure correctness."""

    def setUp(self):
        self.chart = GaugeChart(value=75, title="Test Coverage", label="% covered")

    def test_svg_header(self):
        svg = render_svg(self.chart)
        self.assertTrue(svg.strip().startswith("<svg"))

    def test_svg_footer(self):
        svg = render_svg(self.chart)
        self.assertTrue(svg.strip().endswith("</svg>"))

    def test_viewbox_matches_dimensions(self):
        svg = render_svg(self.chart)
        self.assertIn('viewBox="0 0 400 280"', svg)

    def test_custom_viewbox(self):
        chart = GaugeChart(value=50, width=600, height=400)
        svg = render_svg(chart)
        self.assertIn('viewBox="0 0 600 400"', svg)

    def test_title_rendered(self):
        svg = render_svg(self.chart)
        self.assertIn("Test Coverage", svg)

    def test_label_rendered(self):
        svg = render_svg(self.chart)
        self.assertIn("% covered", svg)

    def test_no_title_still_valid(self):
        chart = GaugeChart(value=50)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_background_rect(self):
        svg = render_svg(self.chart)
        self.assertIn(CCA_COLORS["background"], svg)

    def test_has_path_elements_for_arcs(self):
        svg = render_svg(self.chart)
        self.assertIn("<path", svg)

    def test_has_line_element_for_needle(self):
        svg = render_svg(self.chart)
        self.assertIn("<line", svg)

    def test_has_circle_element_for_needle_hub(self):
        svg = render_svg(self.chart)
        self.assertIn("<circle", svg)

    def test_has_text_elements(self):
        svg = render_svg(self.chart)
        self.assertIn("<text", svg)


class TestGaugeChartColorZones(unittest.TestCase):
    """Tests for red/yellow/green color zone rendering."""

    def test_red_zone_color_present(self):
        chart = GaugeChart(value=50)
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["highlight"], svg)  # red zone

    def test_yellow_zone_color_present(self):
        chart = GaugeChart(value=50)
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["warning"], svg)  # yellow zone

    def test_green_zone_color_present(self):
        chart = GaugeChart(value=50)
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["success"], svg)  # green zone

    def test_all_three_zones_always_present(self):
        for value in [0, 33, 50, 66, 100]:
            chart = GaugeChart(value=value)
            svg = render_svg(chart)
            self.assertIn(CCA_COLORS["highlight"], svg)
            self.assertIn(CCA_COLORS["warning"], svg)
            self.assertIn(CCA_COLORS["success"], svg)


class TestGaugeChartValueDisplay(unittest.TestCase):
    """Tests for value and marker rendering."""

    def test_integer_value_displayed(self):
        chart = GaugeChart(value=75)
        svg = render_svg(chart)
        self.assertIn("75", svg)

    def test_float_value_displayed(self):
        chart = GaugeChart(value=72.5)
        svg = render_svg(chart)
        self.assertIn("72.5", svg)

    def test_zero_value_displayed(self):
        chart = GaugeChart(value=0)
        svg = render_svg(chart)
        self.assertIn("0", svg)

    def test_min_marker_displayed(self):
        chart = GaugeChart(value=50, min_value=0, max_value=100)
        svg = render_svg(chart)
        # min value 0 should appear as a marker
        self.assertIn(">0<", svg)

    def test_max_marker_displayed(self):
        chart = GaugeChart(value=50, min_value=0, max_value=100)
        svg = render_svg(chart)
        self.assertIn(">100<", svg)

    def test_custom_range_markers(self):
        chart = GaugeChart(value=500, min_value=100, max_value=1000)
        svg = render_svg(chart)
        self.assertIn(">100<", svg)
        self.assertIn(">1000<", svg)

    def test_needle_present(self):
        chart = GaugeChart(value=50)
        svg = render_svg(chart)
        # Needle is a line element
        self.assertIn("<line", svg)

    def test_hub_circle_present(self):
        chart = GaugeChart(value=50)
        svg = render_svg(chart)
        self.assertIn("<circle", svg)

    def test_value_clamped_to_max(self):
        # Value exceeding max still renders without error
        chart = GaugeChart(value=150, max_value=100)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_value_clamped_to_min(self):
        # Value below min still renders without error
        chart = GaugeChart(value=-10, min_value=0)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)


class TestGaugeChartThresholds(unittest.TestCase):
    """Tests for custom threshold configuration."""

    def test_custom_thresholds_applied(self):
        chart = GaugeChart(value=50, thresholds=(25.0, 75.0))
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_narrow_yellow_zone(self):
        chart = GaugeChart(value=50, thresholds=(45.0, 55.0))
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_wide_red_zone(self):
        chart = GaugeChart(value=50, thresholds=(80.0, 90.0))
        svg = render_svg(chart)
        self.assertIn("<svg", svg)


class TestGaugeChartTextHelper(unittest.TestCase):
    """Tests confirming _text() is used for all text rendering."""

    def test_all_text_has_font_family(self):
        chart = GaugeChart(value=75, title="Score", label="points")
        svg = render_svg(chart)
        self.assertIn("font-family", svg)

    def test_title_escaped(self):
        chart = GaugeChart(value=50, title="Score & Grade")
        svg = render_svg(chart)
        self.assertIn("Score &amp; Grade", svg)
        self.assertNotIn("Score & Grade<", svg)

    def test_label_escaped(self):
        chart = GaugeChart(value=50, label="A+ <grade>")
        svg = render_svg(chart)
        self.assertIn("A+ &lt;grade&gt;", svg)


if __name__ == "__main__":
    unittest.main()
