"""Tests for ParetoChart — MT-32 Visual Excellence.

ParetoChart: Combined bar + cumulative line (80/20 analysis).
Shows individual values as bars and cumulative percentage as a line overlay.
Classic quality management tool for identifying the vital few.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chart_generator import render_svg, save_svg, CCA_COLORS


class TestParetoChartDataclass(unittest.TestCase):
    """Test ParetoChart construction and defaults."""

    def test_basic_creation(self):
        from chart_generator import ParetoChart
        chart = ParetoChart(
            data=[("BTC", 150), ("ETH", 80), ("SOL", 40)],
            title="Profit by Asset",
        )
        self.assertEqual(len(chart.data), 3)

    def test_defaults(self):
        from chart_generator import ParetoChart
        chart = ParetoChart(data=[])
        self.assertEqual(chart.width, 500)
        self.assertEqual(chart.height, 350)
        self.assertEqual(chart.title, "")
        self.assertEqual(chart.bar_color, "")
        self.assertEqual(chart.line_color, "")

    def test_custom_colors(self):
        from chart_generator import ParetoChart
        chart = ParetoChart(
            data=[("A", 10)],
            bar_color="#ff0000",
            line_color="#00ff00",
        )
        self.assertEqual(chart.bar_color, "#ff0000")
        self.assertEqual(chart.line_color, "#00ff00")


class TestParetoChartRendering(unittest.TestCase):
    """Test SVG rendering of Pareto charts."""

    def _make_chart(self, **kwargs):
        from chart_generator import ParetoChart
        defaults = {
            "data": [
                ("Self-Learning", 2141),
                ("Design Skills", 1530),
                ("Agent Guard", 1102),
                ("Reddit Intel", 498),
                ("Context Mon", 434),
                ("Usage Dash", 369),
                ("Memory", 340),
                ("Spec System", 205),
            ],
            "title": "Tests by Module (Pareto)",
        }
        defaults.update(kwargs)
        return ParetoChart(**defaults)

    def test_renders_valid_svg(self):
        svg = render_svg(self._make_chart())
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_contains_title(self):
        svg = render_svg(self._make_chart())
        self.assertIn("Tests by Module (Pareto)", svg)

    def test_contains_labels(self):
        svg = render_svg(self._make_chart())
        # Long labels get truncated by _abbreviate_label (max 12 chars)
        self.assertIn("Agent Guard", svg)

    def test_bars_rendered(self):
        """Each data point gets a bar."""
        svg = render_svg(self._make_chart())
        rect_count = svg.count("<rect")
        # Background rect + 8 bars = at least 9
        self.assertGreaterEqual(rect_count, 9)

    def test_cumulative_line_rendered(self):
        """Cumulative percentage line is drawn."""
        svg = render_svg(self._make_chart())
        # Polyline or line elements for the cumulative curve
        self.assertTrue(
            "<polyline" in svg or "<path" in svg,
            "Cumulative line not found"
        )

    def test_cumulative_dots(self):
        """Circle markers at each cumulative point."""
        svg = render_svg(self._make_chart())
        circle_count = svg.count("<circle")
        self.assertGreaterEqual(circle_count, 8)

    def test_percentage_labels(self):
        """100% should appear (final cumulative point)."""
        svg = render_svg(self._make_chart())
        self.assertIn("100%", svg)

    def test_empty_data(self):
        svg = render_svg(self._make_chart(data=[]))
        self.assertIn("<svg", svg)

    def test_single_item(self):
        svg = render_svg(self._make_chart(data=[("Only", 42)]))
        self.assertIn("Only", svg)
        self.assertIn("100%", svg)

    def test_save_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pareto.svg")
            save_svg(self._make_chart(), path)
            self.assertTrue(os.path.exists(path))

    def test_custom_dimensions(self):
        svg = render_svg(self._make_chart(width=600, height=400))
        self.assertIn("600", svg)

    def test_80_20_line(self):
        """80% threshold line should be rendered."""
        svg = render_svg(self._make_chart())
        self.assertIn("80%", svg)


if __name__ == "__main__":
    unittest.main()
