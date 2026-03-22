"""Tests for WaterfallChart in chart_generator.py."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from chart_generator import WaterfallChart, render_svg, CCA_COLORS


class TestWaterfallChartDataclass(unittest.TestCase):
    """Tests for the WaterfallChart dataclass."""

    def test_defaults(self):
        chart = WaterfallChart(data=[("A", 100)])
        self.assertEqual(chart.title, "")
        self.assertEqual(chart.width, 500)
        self.assertEqual(chart.height, 300)
        self.assertTrue(chart.show_values)
        self.assertEqual(chart.total_label, "Total")

    def test_custom_dimensions(self):
        chart = WaterfallChart(data=[("A", 50)], width=800, height=400)
        self.assertEqual(chart.width, 800)
        self.assertEqual(chart.height, 400)

    def test_custom_title(self):
        chart = WaterfallChart(data=[("A", 10)], title="P&L Breakdown")
        self.assertEqual(chart.title, "P&L Breakdown")

    def test_custom_total_label(self):
        chart = WaterfallChart(data=[("A", 10)], total_label="Net")
        self.assertEqual(chart.total_label, "Net")

    def test_show_values_default_true(self):
        chart = WaterfallChart(data=[("A", 10)])
        self.assertTrue(chart.show_values)

    def test_show_values_false(self):
        chart = WaterfallChart(data=[("A", 10)], show_values=False)
        self.assertFalse(chart.show_values)


class TestWaterfallChartNoData(unittest.TestCase):
    """Tests for empty data handling."""

    def test_empty_data_returns_svg(self):
        chart = WaterfallChart(data=[])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_empty_data_shows_no_data_text(self):
        chart = WaterfallChart(data=[])
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_empty_data_uses_font_size_14(self):
        chart = WaterfallChart(data=[])
        svg = render_svg(chart)
        self.assertIn('font-size="14"', svg)


class TestWaterfallChartSVGStructure(unittest.TestCase):
    """Tests for SVG structure correctness."""

    def setUp(self):
        self.data = [("Revenue", 500), ("COGS", -200), ("OpEx", -100)]
        self.chart = WaterfallChart(data=self.data, title="P&L")

    def test_svg_header(self):
        svg = render_svg(self.chart)
        self.assertTrue(svg.strip().startswith("<svg"))

    def test_svg_footer(self):
        svg = render_svg(self.chart)
        self.assertTrue(svg.strip().endswith("</svg>"))

    def test_viewbox_matches_dimensions(self):
        svg = render_svg(self.chart)
        self.assertIn('viewBox="0 0 500 300"', svg)

    def test_custom_viewbox(self):
        chart = WaterfallChart(data=self.data, width=700, height=400)
        svg = render_svg(chart)
        self.assertIn('viewBox="0 0 700 400"', svg)

    def test_title_rendered(self):
        svg = render_svg(self.chart)
        self.assertIn("P&amp;L", svg)

    def test_no_title_still_valid(self):
        chart = WaterfallChart(data=self.data)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_background_rect(self):
        svg = render_svg(self.chart)
        self.assertIn(CCA_COLORS["background"], svg)

    def test_uses_rect_elements(self):
        svg = render_svg(self.chart)
        self.assertIn("<rect", svg)

    def test_uses_line_elements_for_connectors(self):
        svg = render_svg(self.chart)
        self.assertIn("<line", svg)

    def test_uses_text_elements(self):
        svg = render_svg(self.chart)
        self.assertIn("<text", svg)


class TestWaterfallChartColors(unittest.TestCase):
    """Tests for positive/negative/total color coding."""

    def test_positive_bar_uses_success_color(self):
        chart = WaterfallChart(data=[("Revenue", 500)])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["success"], svg)

    def test_negative_bar_uses_highlight_color(self):
        chart = WaterfallChart(data=[("Cost", -200)])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["highlight"], svg)

    def test_mixed_data_has_both_colors(self):
        chart = WaterfallChart(data=[("Rev", 500), ("Cost", -200)])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["success"], svg)
        self.assertIn(CCA_COLORS["highlight"], svg)

    def test_total_bar_uses_accent_color(self):
        chart = WaterfallChart(data=[("Rev", 500), ("Cost", -100)])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["accent"], svg)


class TestWaterfallChartLabels(unittest.TestCase):
    """Tests for bar labels and value rendering."""

    def test_bar_labels_rendered(self):
        chart = WaterfallChart(data=[("Revenue", 500), ("COGS", -200)])
        svg = render_svg(chart)
        self.assertIn("Revenue", svg)
        self.assertIn("COGS", svg)

    def test_total_label_rendered(self):
        chart = WaterfallChart(data=[("Rev", 500)], total_label="Total")
        svg = render_svg(chart)
        self.assertIn("Total", svg)

    def test_custom_total_label_rendered(self):
        chart = WaterfallChart(data=[("Rev", 500)], total_label="Net P&L")
        svg = render_svg(chart)
        self.assertIn("Net P&amp;L", svg)

    def test_values_shown_when_enabled(self):
        chart = WaterfallChart(data=[("Rev", 500)], show_values=True)
        svg = render_svg(chart)
        self.assertIn("500", svg)

    def test_values_shown_for_negative(self):
        chart = WaterfallChart(data=[("Cost", -200)], show_values=True)
        svg = render_svg(chart)
        # Value labels may show -200 or 200 above bar
        self.assertIn("200", svg)

    def test_values_hidden_when_disabled(self):
        chart = WaterfallChart(data=[("Rev", 12345)], show_values=False)
        svg = render_svg(chart)
        # Value labels for positives use a "+" prefix — "+12345" should not appear
        self.assertNotIn("+12345", svg)

    def test_special_chars_in_label_escaped(self):
        chart = WaterfallChart(data=[("R&D", 100)])
        svg = render_svg(chart)
        self.assertNotIn(">R&D<", svg)
        self.assertIn("R&amp;D", svg)


class TestWaterfallChartCumulativeLogic(unittest.TestCase):
    """Tests for waterfall cumulative calculation logic."""

    def test_single_positive(self):
        chart = WaterfallChart(data=[("A", 100)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_single_negative(self):
        chart = WaterfallChart(data=[("A", -100)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_all_positives(self):
        chart = WaterfallChart(data=[("A", 100), ("B", 200), ("C", 300)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_all_negatives(self):
        chart = WaterfallChart(data=[("A", -100), ("B", -50), ("C", -25)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_mixed_ending_positive(self):
        chart = WaterfallChart(data=[("Rev", 500), ("Cost", -200), ("Other", 50)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_zero_value_bar(self):
        chart = WaterfallChart(data=[("A", 100), ("B", 0), ("C", -50)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_many_bars(self):
        data = [(f"Item{i}", 100 if i % 2 == 0 else -30) for i in range(10)]
        chart = WaterfallChart(data=data)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)


class TestWaterfallChartTextHelper(unittest.TestCase):
    """Tests confirming _text() is used for all text rendering."""

    def test_all_text_has_font_family(self):
        chart = WaterfallChart(data=[("Rev", 500), ("Cost", -100)])
        svg = render_svg(chart)
        # _text() always includes font-family
        self.assertIn("font-family", svg)

    def test_uses_escape_for_special_chars(self):
        chart = WaterfallChart(data=[('<Cost>', -100)])
        svg = render_svg(chart)
        self.assertIn("&lt;Cost&gt;", svg)
        self.assertNotIn("<Cost>", svg.replace("<svg", "").replace("</svg>", ""))


if __name__ == "__main__":
    unittest.main()
