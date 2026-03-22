"""Tests for FunnelChart in chart_generator.py."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chart_generator import FunnelChart, render_svg, save_svg


class TestFunnelChartDataclass(unittest.TestCase):
    """FunnelChart dataclass construction and defaults."""

    def test_basic_construction(self):
        chart = FunnelChart([("Scanned", 100), ("Reviewed", 60), ("Built", 20)])
        self.assertEqual(len(chart.data), 3)

    def test_default_title_empty(self):
        chart = FunnelChart([("A", 100)])
        self.assertEqual(chart.title, "")

    def test_default_dimensions(self):
        chart = FunnelChart([("A", 100)])
        self.assertEqual(chart.width, 400)
        self.assertEqual(chart.height, 350)

    def test_custom_title(self):
        chart = FunnelChart([("A", 100)], title="Conversion")
        self.assertEqual(chart.title, "Conversion")

    def test_custom_dimensions(self):
        chart = FunnelChart([("A", 100)], width=600, height=400)
        self.assertEqual(chart.width, 600)
        self.assertEqual(chart.height, 400)

    def test_show_percentages_default_true(self):
        chart = FunnelChart([("A", 100)])
        self.assertTrue(chart.show_percentages)

    def test_show_percentages_false(self):
        chart = FunnelChart([("A", 100)], show_percentages=False)
        self.assertFalse(chart.show_percentages)

    def test_color_default_empty(self):
        chart = FunnelChart([("A", 100)])
        self.assertEqual(chart.color, "")

    def test_color_custom(self):
        chart = FunnelChart([("A", 100)], color="#ff0000")
        self.assertEqual(chart.color, "#ff0000")

    def test_accepts_single_stage(self):
        chart = FunnelChart([("Only", 500)])
        self.assertEqual(len(chart.data), 1)

    def test_accepts_many_stages(self):
        data = [(f"Stage {i}", 100 - i * 10) for i in range(8)]
        chart = FunnelChart(data)
        self.assertEqual(len(chart.data), 8)


class TestFunnelChartRenderBasics(unittest.TestCase):
    """render_svg() produces valid SVG content."""

    def setUp(self):
        self.data = [("Scanned", 150), ("Reviewed", 90), ("Built", 30)]
        self.chart = FunnelChart(self.data)
        self.svg = render_svg(self.chart)

    def test_renders_without_error(self):
        self.assertIsInstance(self.svg, str)
        self.assertTrue(len(self.svg) > 0)

    def test_valid_svg_wrapper(self):
        self.assertIn("<svg", self.svg)
        self.assertIn("</svg>", self.svg)

    def test_width_in_svg(self):
        self.assertIn('width="400"', self.svg)

    def test_height_in_svg(self):
        self.assertIn('height="350"', self.svg)

    def test_viewbox_present(self):
        self.assertIn("viewBox", self.svg)

    def test_stage_labels_present(self):
        for label, _ in self.data:
            self.assertIn(label, self.svg)

    def test_values_rendered(self):
        for _, value in self.data:
            self.assertIn(str(value), self.svg)

    def test_contains_polygon_or_path(self):
        # Funnel stages rendered as polygon or path elements
        has_poly = "<polygon" in self.svg
        has_path = "<path" in self.svg
        self.assertTrue(has_poly or has_path)


class TestFunnelChartEmptyData(unittest.TestCase):
    """Empty data produces 'No data' fallback."""

    def test_empty_data_no_error(self):
        chart = FunnelChart([])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_empty_data_shows_no_data(self):
        chart = FunnelChart([])
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_empty_data_valid_svg(self):
        chart = FunnelChart([])
        svg = render_svg(chart)
        self.assertIn("viewBox", svg)


class TestFunnelChartTitle(unittest.TestCase):
    """Title rendering."""

    def test_title_in_svg_when_set(self):
        chart = FunnelChart([("A", 100)], title="My Funnel")
        svg = render_svg(chart)
        self.assertIn("My Funnel", svg)

    def test_no_title_element_when_empty(self):
        chart = FunnelChart([("A", 100)], title="")
        svg = render_svg(chart)
        # No title text, but SVG still valid
        self.assertNotIn("My Funnel", svg)

    def test_title_escaped(self):
        chart = FunnelChart([("A", 100)], title="<Script>")
        svg = render_svg(chart)
        self.assertNotIn("<Script>", svg)
        self.assertIn("&lt;Script&gt;", svg)


class TestFunnelChartPercentages(unittest.TestCase):
    """Percentage labels."""

    def test_shows_100_percent_for_first_stage(self):
        chart = FunnelChart([("Top", 200), ("Mid", 100)], show_percentages=True)
        svg = render_svg(chart)
        self.assertIn("100%", svg)

    def test_shows_50_percent_for_half(self):
        chart = FunnelChart([("Top", 200), ("Mid", 100)], show_percentages=True)
        svg = render_svg(chart)
        self.assertIn("50%", svg)

    def test_no_percent_when_disabled(self):
        chart = FunnelChart([("Top", 200), ("Mid", 100)], show_percentages=False)
        svg = render_svg(chart)
        self.assertNotIn("50%", svg)

    def test_zero_value_stage_shows_zero_percent(self):
        chart = FunnelChart([("Top", 100), ("Empty", 0)], show_percentages=True)
        svg = render_svg(chart)
        self.assertIn("0%", svg)


class TestFunnelChartSpecialChars(unittest.TestCase):
    """Special characters in stage names are escaped."""

    def test_ampersand_escaped(self):
        chart = FunnelChart([("A & B", 100)])
        svg = render_svg(chart)
        self.assertNotIn("A & B", svg)
        self.assertIn("A &amp; B", svg)

    def test_less_than_escaped(self):
        chart = FunnelChart([("<Stage>", 100)])
        svg = render_svg(chart)
        self.assertNotIn("<Stage>", svg)
        self.assertIn("&lt;Stage&gt;", svg)

    def test_quote_in_label_escaped(self):
        chart = FunnelChart([('Say "hi"', 50)])
        svg = render_svg(chart)
        self.assertNotIn('"hi"', svg)


class TestFunnelChartCustomColor(unittest.TestCase):
    """Custom color applied to funnel bars."""

    def test_custom_color_present_in_svg(self):
        chart = FunnelChart([("A", 100), ("B", 60)], color="#e94560")
        svg = render_svg(chart)
        self.assertIn("#e94560", svg)

    def test_default_color_uses_cca_accent(self):
        chart = FunnelChart([("A", 100)])
        svg = render_svg(chart)
        # Should use some color from CCA palette
        self.assertIn("#", svg)


class TestFunnelChartSingleStage(unittest.TestCase):
    """Single-stage funnel edge case."""

    def test_single_stage_renders(self):
        chart = FunnelChart([("Solo", 500)])
        svg = render_svg(chart)
        self.assertIn("Solo", svg)
        self.assertIn("500", svg)

    def test_single_stage_100_percent(self):
        chart = FunnelChart([("Solo", 500)], show_percentages=True)
        svg = render_svg(chart)
        self.assertIn("100%", svg)


class TestFunnelChartDimensions(unittest.TestCase):
    """Custom width/height respected."""

    def test_custom_width(self):
        chart = FunnelChart([("A", 100)], width=800)
        svg = render_svg(chart)
        self.assertIn('width="800"', svg)

    def test_custom_height(self):
        chart = FunnelChart([("A", 100)], height=500)
        svg = render_svg(chart)
        self.assertIn('height="500"', svg)


class TestFunnelChartSaveIntegration(unittest.TestCase):
    """save_svg() integration."""

    def test_save_svg_creates_file(self):
        import tempfile
        chart = FunnelChart([("A", 100), ("B", 50)], title="Save Test")
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            save_svg(chart, path)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("<svg", content)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
