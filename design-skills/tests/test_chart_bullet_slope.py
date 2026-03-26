"""Tests for BulletChart + SlopeChart — MT-32 Visual Excellence.

BulletChart: Stephen Few's bullet graph for KPI dashboards.
  Shows actual value vs target with qualitative range bands.
  Perfect for bankroll target, WR vs break-even, etc.

SlopeChart: Before/after comparison lines (slopegraph).
  Shows paired values connected by lines for trend comparison.
  Great for strategy performance before/after guard changes.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chart_generator import render_svg, save_svg, CCA_COLORS


# ---------------------------------------------------------------------------
# BulletChart tests
# ---------------------------------------------------------------------------

class TestBulletChartDataclass(unittest.TestCase):
    """Test BulletChart construction and defaults."""

    def test_basic_creation(self):
        from chart_generator import BulletChart
        chart = BulletChart(
            actual=75.0,
            target=90.0,
            title="Win Rate",
        )
        self.assertEqual(chart.actual, 75.0)
        self.assertEqual(chart.target, 90.0)
        self.assertEqual(chart.title, "Win Rate")

    def test_defaults(self):
        from chart_generator import BulletChart
        chart = BulletChart(actual=50.0, target=80.0)
        self.assertEqual(chart.width, 500)
        self.assertEqual(chart.height, 80)
        self.assertEqual(chart.title, "")
        self.assertEqual(chart.subtitle, "")
        self.assertEqual(chart.unit, "")
        self.assertEqual(len(chart.ranges), 0)

    def test_custom_ranges(self):
        """Qualitative ranges: poor/satisfactory/good."""
        from chart_generator import BulletChart
        chart = BulletChart(
            actual=75.0,
            target=90.0,
            ranges=[(60, "poor"), (80, "satisfactory"), (100, "good")],
        )
        self.assertEqual(len(chart.ranges), 3)

    def test_with_subtitle_and_unit(self):
        from chart_generator import BulletChart
        chart = BulletChart(
            actual=642.0,
            target=1000.0,
            title="Bankroll",
            subtitle="30-day target",
            unit="USD",
        )
        self.assertEqual(chart.subtitle, "30-day target")
        self.assertEqual(chart.unit, "USD")


class TestBulletChartRendering(unittest.TestCase):
    """Test SVG rendering of bullet charts."""

    def _make_chart(self, **kwargs):
        from chart_generator import BulletChart
        defaults = {
            "actual": 75.0,
            "target": 90.0,
            "ranges": [(60, "poor"), (80, "satisfactory"), (100, "good")],
            "title": "Win Rate",
            "unit": "%",
        }
        defaults.update(kwargs)
        return BulletChart(**defaults)

    def test_renders_valid_svg(self):
        svg = render_svg(self._make_chart())
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_contains_title(self):
        svg = render_svg(self._make_chart())
        self.assertIn("Win Rate", svg)

    def test_contains_actual_bar(self):
        """Actual value renders as a rect element."""
        svg = render_svg(self._make_chart())
        self.assertIn("<rect", svg)

    def test_contains_target_marker(self):
        """Target renders as a line marker."""
        svg = render_svg(self._make_chart())
        self.assertIn("<line", svg)

    def test_range_bands_rendered(self):
        """Qualitative ranges render as background rects."""
        svg = render_svg(self._make_chart())
        # 3 range bands + actual bar = at least 4 rects
        rect_count = svg.count("<rect")
        self.assertGreaterEqual(rect_count, 4)

    def test_empty_ranges_uses_auto(self):
        """No explicit ranges => auto-generate from 0 to max(actual, target)."""
        svg = render_svg(self._make_chart(ranges=[]))
        self.assertIn("<svg", svg)

    def test_save_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bullet.svg")
            save_svg(self._make_chart(), path)
            self.assertTrue(os.path.exists(path))
            content = open(path).read()
            self.assertIn("<svg", content)

    def test_actual_exceeds_target(self):
        """Actual > target should still render."""
        svg = render_svg(self._make_chart(actual=110.0, target=90.0))
        self.assertIn("<svg", svg)

    def test_zero_actual(self):
        svg = render_svg(self._make_chart(actual=0.0))
        self.assertIn("<svg", svg)

    def test_subtitle_rendered(self):
        svg = render_svg(self._make_chart(subtitle="vs break-even"))
        self.assertIn("vs break-even", svg)

    def test_unit_rendered(self):
        svg = render_svg(self._make_chart(unit="%"))
        self.assertIn("%", svg)

    def test_custom_dimensions(self):
        svg = render_svg(self._make_chart(width=600, height=100))
        self.assertIn("600", svg)


# ---------------------------------------------------------------------------
# SlopeChart tests
# ---------------------------------------------------------------------------

class TestSlopeChartDataclass(unittest.TestCase):
    """Test SlopeChart construction and defaults."""

    def test_basic_creation(self):
        from chart_generator import SlopeChart
        chart = SlopeChart(
            data=[("BTC", 92.3, 96.0), ("ETH", 88.5, 95.4)],
            left_label="Before Guards",
            right_label="After Guards",
        )
        self.assertEqual(len(chart.data), 2)

    def test_defaults(self):
        from chart_generator import SlopeChart
        chart = SlopeChart(data=[])
        self.assertEqual(chart.width, 400)
        self.assertEqual(chart.height, 300)
        self.assertEqual(chart.title, "")
        self.assertEqual(chart.left_label, "Before")
        self.assertEqual(chart.right_label, "After")

    def test_custom_labels(self):
        from chart_generator import SlopeChart
        chart = SlopeChart(
            data=[("SOL", 85.0, 93.2)],
            left_label="Pre-Sizing",
            right_label="Post-Sizing",
            title="WR Impact",
        )
        self.assertEqual(chart.left_label, "Pre-Sizing")
        self.assertEqual(chart.right_label, "Post-Sizing")


class TestSlopeChartRendering(unittest.TestCase):
    """Test SVG rendering of slope charts."""

    def _make_chart(self, **kwargs):
        from chart_generator import SlopeChart
        defaults = {
            "data": [
                ("BTC", 92.3, 96.0),
                ("ETH", 88.5, 95.4),
                ("SOL", 83.3, 93.2),
            ],
            "left_label": "Before Guards",
            "right_label": "After Guards",
            "title": "Win Rate Impact",
        }
        defaults.update(kwargs)
        return SlopeChart(**defaults)

    def test_renders_valid_svg(self):
        svg = render_svg(self._make_chart())
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_contains_title(self):
        svg = render_svg(self._make_chart())
        self.assertIn("Win Rate Impact", svg)

    def test_contains_labels(self):
        svg = render_svg(self._make_chart())
        self.assertIn("Before Guards", svg)
        self.assertIn("After Guards", svg)

    def test_contains_series_names(self):
        svg = render_svg(self._make_chart())
        self.assertIn("BTC", svg)
        self.assertIn("ETH", svg)
        self.assertIn("SOL", svg)

    def test_lines_rendered(self):
        """Each data point produces a connecting line."""
        svg = render_svg(self._make_chart())
        line_count = svg.count("<line")
        self.assertGreaterEqual(line_count, 3)

    def test_circles_rendered(self):
        """Each endpoint has a circle marker."""
        svg = render_svg(self._make_chart())
        circle_count = svg.count("<circle")
        # 3 series * 2 endpoints = 6 circles
        self.assertGreaterEqual(circle_count, 6)

    def test_empty_data(self):
        svg = render_svg(self._make_chart(data=[]))
        self.assertIn("<svg", svg)

    def test_single_item(self):
        svg = render_svg(self._make_chart(data=[("BTC", 90.0, 95.0)]))
        self.assertIn("BTC", svg)

    def test_negative_slope(self):
        """Lines where value decreases (right < left)."""
        svg = render_svg(self._make_chart(data=[("XRP", 95.0, 88.0)]))
        self.assertIn("XRP", svg)

    def test_save_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "slope.svg")
            save_svg(self._make_chart(), path)
            self.assertTrue(os.path.exists(path))

    def test_custom_dimensions(self):
        svg = render_svg(self._make_chart(width=600, height=400))
        self.assertIn("600", svg)

    def test_color_by_direction(self):
        """Positive slope = success color, negative = highlight."""
        svg = render_svg(self._make_chart(data=[
            ("Up", 50.0, 80.0),
            ("Down", 80.0, 50.0),
        ]))
        self.assertIn(CCA_COLORS["success"], svg)
        self.assertIn(CCA_COLORS["highlight"], svg)

    def test_values_displayed(self):
        """Left and right values should appear as text."""
        svg = render_svg(self._make_chart(data=[("BTC", 92.3, 96.0)]))
        self.assertIn("92.3", svg)
        # 96.0 renders as "96" (integer formatting strips .0)
        self.assertIn("96", svg)


if __name__ == "__main__":
    unittest.main()
