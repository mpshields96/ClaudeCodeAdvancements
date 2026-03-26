"""Tests for LollipopChart + DumbbellChart — MT-32 Visual Excellence.

LollipopChart: Horizontal lollipop (stem + circle) for ranked category display.
  Cleaner alternative to horizontal bar charts when values vary widely.

DumbbellChart: Horizontal range comparison showing two values per row.
  Shows min/max, before/after, or any paired values as connected dots.
  Great for showing confidence intervals or range comparisons.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chart_generator import render_svg, save_svg, CCA_COLORS


# ---------------------------------------------------------------------------
# LollipopChart tests
# ---------------------------------------------------------------------------

class TestLollipopChartDataclass(unittest.TestCase):
    """Test LollipopChart construction and defaults."""

    def test_basic_creation(self):
        from chart_generator import LollipopChart
        chart = LollipopChart(
            data=[("BTC", 96.0), ("ETH", 95.4), ("SOL", 93.2)],
            title="Win Rate by Asset",
        )
        self.assertEqual(len(chart.data), 3)

    def test_defaults(self):
        from chart_generator import LollipopChart
        chart = LollipopChart(data=[])
        self.assertEqual(chart.width, 500)
        self.assertEqual(chart.height, 300)
        self.assertEqual(chart.title, "")
        self.assertEqual(chart.dot_radius, 6)

    def test_custom_color(self):
        from chart_generator import LollipopChart
        chart = LollipopChart(
            data=[("A", 10)],
            color=CCA_COLORS["success"],
        )
        self.assertEqual(chart.color, CCA_COLORS["success"])


class TestLollipopChartRendering(unittest.TestCase):
    """Test SVG rendering of lollipop charts."""

    def _make_chart(self, **kwargs):
        from chart_generator import LollipopChart
        defaults = {
            "data": [
                ("Self-Learning", 2141),
                ("Design Skills", 1530),
                ("Agent Guard", 1102),
                ("Reddit Intel", 498),
                ("Context Mon", 434),
            ],
            "title": "Tests by Module",
        }
        defaults.update(kwargs)
        return LollipopChart(**defaults)

    def test_renders_valid_svg(self):
        svg = render_svg(self._make_chart())
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_contains_title(self):
        svg = render_svg(self._make_chart())
        self.assertIn("Tests by Module", svg)

    def test_contains_labels(self):
        svg = render_svg(self._make_chart())
        self.assertIn("Self-Learning", svg)
        self.assertIn("Agent Guard", svg)

    def test_circles_rendered(self):
        """Each data point gets a circle (lollipop head)."""
        svg = render_svg(self._make_chart())
        circle_count = svg.count("<circle")
        self.assertEqual(circle_count, 5)

    def test_lines_rendered(self):
        """Each data point gets a stem line."""
        svg = render_svg(self._make_chart())
        line_count = svg.count("<line")
        self.assertGreaterEqual(line_count, 5)

    def test_empty_data(self):
        svg = render_svg(self._make_chart(data=[]))
        self.assertIn("<svg", svg)

    def test_single_item(self):
        svg = render_svg(self._make_chart(data=[("Only", 42)]))
        self.assertIn("Only", svg)

    def test_show_values(self):
        svg = render_svg(self._make_chart(show_values=True))
        self.assertIn("2141", svg)

    def test_save_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lollipop.svg")
            save_svg(self._make_chart(), path)
            self.assertTrue(os.path.exists(path))

    def test_custom_dimensions(self):
        svg = render_svg(self._make_chart(width=600, height=400))
        self.assertIn("600", svg)


# ---------------------------------------------------------------------------
# DumbbellChart tests
# ---------------------------------------------------------------------------

class TestDumbbellChartDataclass(unittest.TestCase):
    """Test DumbbellChart construction and defaults."""

    def test_basic_creation(self):
        from chart_generator import DumbbellChart
        chart = DumbbellChart(
            data=[("BTC", 91.3, 96.0), ("ETH", 88.5, 96.8)],
            left_label="Min WR",
            right_label="Max WR",
        )
        self.assertEqual(len(chart.data), 2)

    def test_defaults(self):
        from chart_generator import DumbbellChart
        chart = DumbbellChart(data=[])
        self.assertEqual(chart.width, 500)
        self.assertEqual(chart.height, 300)
        self.assertEqual(chart.title, "")
        self.assertEqual(chart.left_label, "Start")
        self.assertEqual(chart.right_label, "End")

    def test_custom_title(self):
        from chart_generator import DumbbellChart
        chart = DumbbellChart(
            data=[("SOL", 83.3, 95.4)],
            title="WR Range by Asset",
        )
        self.assertEqual(chart.title, "WR Range by Asset")


class TestDumbbellChartRendering(unittest.TestCase):
    """Test SVG rendering of dumbbell charts."""

    def _make_chart(self, **kwargs):
        from chart_generator import DumbbellChart
        defaults = {
            "data": [
                ("BTC", 91.3, 96.0),
                ("ETH", 88.5, 96.8),
                ("SOL", 83.3, 95.4),
            ],
            "left_label": "Early WR",
            "right_label": "Current WR",
            "title": "Asset WR Range",
        }
        defaults.update(kwargs)
        return DumbbellChart(**defaults)

    def test_renders_valid_svg(self):
        svg = render_svg(self._make_chart())
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_contains_title(self):
        svg = render_svg(self._make_chart())
        self.assertIn("Asset WR Range", svg)

    def test_contains_labels(self):
        svg = render_svg(self._make_chart())
        self.assertIn("BTC", svg)
        self.assertIn("ETH", svg)
        self.assertIn("SOL", svg)

    def test_contains_column_labels(self):
        svg = render_svg(self._make_chart())
        self.assertIn("Early WR", svg)
        self.assertIn("Current WR", svg)

    def test_circles_rendered(self):
        """2 circles per data point (left + right endpoints)."""
        svg = render_svg(self._make_chart())
        circle_count = svg.count("<circle")
        self.assertEqual(circle_count, 6)  # 3 items * 2

    def test_connecting_lines(self):
        """Each row has a connecting line between the two dots."""
        svg = render_svg(self._make_chart())
        line_count = svg.count("<line")
        self.assertGreaterEqual(line_count, 3)

    def test_empty_data(self):
        svg = render_svg(self._make_chart(data=[]))
        self.assertIn("<svg", svg)

    def test_single_item(self):
        svg = render_svg(self._make_chart(data=[("BTC", 90.0, 96.0)]))
        self.assertIn("BTC", svg)

    def test_reversed_values(self):
        """left_value > right_value should still render."""
        svg = render_svg(self._make_chart(data=[("XRP", 95.0, 85.0)]))
        self.assertIn("XRP", svg)

    def test_save_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "dumbbell.svg")
            save_svg(self._make_chart(), path)
            self.assertTrue(os.path.exists(path))

    def test_color_by_improvement(self):
        """Positive change = success color, negative = highlight."""
        svg = render_svg(self._make_chart(data=[
            ("Up", 50.0, 80.0),
            ("Down", 80.0, 50.0),
        ]))
        self.assertIn(CCA_COLORS["success"], svg)
        self.assertIn(CCA_COLORS["highlight"], svg)

    def test_custom_dimensions(self):
        svg = render_svg(self._make_chart(width=600, height=400))
        self.assertIn("600", svg)


if __name__ == "__main__":
    unittest.main()
