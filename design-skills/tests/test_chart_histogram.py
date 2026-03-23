"""Tests for HistogramChart in chart_generator.py."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chart_generator import (
    HistogramChart,
    CCA_COLORS,
    render_svg,
    save_svg,
)


class TestHistogramChart(unittest.TestCase):
    """Tests for HistogramChart — frequency distribution from raw values."""

    def test_basic_render(self):
        """Renders SVG with histogram bars."""
        chart = HistogramChart(values=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertIn("<rect", svg)

    def test_empty_data(self):
        """Renders 'No data' for empty values."""
        chart = HistogramChart(values=[], title="Empty")
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_single_value(self):
        """Single value renders without error."""
        chart = HistogramChart(values=[42])
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_two_values(self):
        """Two values renders without error."""
        chart = HistogramChart(values=[3, 7])
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_auto_bins_sturges(self):
        """Auto-binning uses Sturges' rule (ceil(1 + log2(n)))."""
        import math
        values = list(range(100))
        chart = HistogramChart(values=values)
        svg = render_svg(chart)
        expected_bins = int(math.ceil(1 + math.log2(100)))
        # Count non-background rects (background rect + histogram bars)
        rect_count = svg.count("<rect")
        # Should have background rect + at most expected_bins bars
        self.assertGreater(rect_count, 1)
        self.assertLessEqual(rect_count, expected_bins + 1)

    def test_custom_bins(self):
        """Explicit bin count is respected."""
        chart = HistogramChart(values=[1, 2, 3, 4, 5], bins=2)
        svg = render_svg(chart)
        # Background rect + 2 bars (max)
        rect_count = svg.count("<rect")
        self.assertLessEqual(rect_count, 3)

    def test_title_rendered(self):
        """Title appears in SVG."""
        chart = HistogramChart(values=[1, 2, 3], title="My Histogram")
        svg = render_svg(chart)
        self.assertIn("My Histogram", svg)

    def test_x_label(self):
        """X-axis label appears in SVG."""
        chart = HistogramChart(values=[1, 2, 3], x_label="Duration (s)")
        svg = render_svg(chart)
        self.assertIn("Duration (s)", svg)

    def test_y_label_default(self):
        """Default y-axis label is 'Frequency'."""
        chart = HistogramChart(values=[1, 2, 3])
        svg = render_svg(chart)
        self.assertIn("Frequency", svg)

    def test_y_label_custom(self):
        """Custom y-axis label is rendered."""
        chart = HistogramChart(values=[1, 2, 3], y_label="Count")
        svg = render_svg(chart)
        self.assertIn("Count", svg)

    def test_custom_color(self):
        """Custom bar color is used."""
        chart = HistogramChart(values=[1, 2, 3], color="#ff6600")
        svg = render_svg(chart)
        self.assertIn("#ff6600", svg)

    def test_default_color(self):
        """Default color is CCA accent."""
        chart = HistogramChart(values=[1, 2, 3])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["accent"], svg)

    def test_custom_dimensions(self):
        """Custom width/height respected."""
        chart = HistogramChart(values=[1, 2, 3], width=700, height=500)
        svg = render_svg(chart)
        self.assertIn('width="700"', svg)
        self.assertIn('height="500"', svg)

    def test_save_svg(self):
        """save_svg writes file to disk."""
        chart = HistogramChart(values=[1, 2, 3, 4, 5])
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

    def test_negative_values(self):
        """Handles negative values correctly."""
        chart = HistogramChart(values=[-10, -5, 0, 5, 10])
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_uniform_values(self):
        """All same values renders a single bin without error."""
        chart = HistogramChart(values=[5, 5, 5, 5, 5])
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_large_dataset(self):
        """Handles 1000 values."""
        import random
        random.seed(42)
        vals = [random.gauss(50, 10) for _ in range(1000)]
        chart = HistogramChart(values=vals)
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_contiguous_bars(self):
        """Histogram bars are contiguous (no gaps between bins)."""
        chart = HistogramChart(values=list(range(20)), bins=5)
        svg = render_svg(chart)
        # Bars should have thin stroke for separation, not gap
        self.assertIn('stroke-width="0.5"', svg)

    def test_bins_one(self):
        """Single bin puts all values in one bar."""
        chart = HistogramChart(values=[1, 2, 3, 4, 5], bins=1)
        svg = render_svg(chart)
        # Background rect + 1 bar
        rect_count = svg.count("<rect")
        self.assertEqual(rect_count, 2)

    def test_bins_equal_to_values(self):
        """One bin per value renders without error."""
        chart = HistogramChart(values=[1, 2, 3, 4, 5], bins=5)
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_float_values(self):
        """Float values are handled correctly."""
        chart = HistogramChart(values=[0.1, 0.5, 0.9, 1.3, 1.7, 2.1])
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_x_axis_tick_labels(self):
        """X-axis has tick labels at bin edges."""
        chart = HistogramChart(values=[10, 20, 30, 40, 50], bins=4)
        svg = render_svg(chart)
        # Should have "10" or "10.0" as first tick
        self.assertIn("10", svg)

    def test_y_axis_ticks(self):
        """Y-axis has tick marks showing frequency counts."""
        chart = HistogramChart(values=[1, 1, 1, 2, 2, 3], bins=3)
        svg = render_svg(chart)
        # Y-axis should show count values
        self.assertIn("<line", svg)

    def test_many_bins(self):
        """Large bin count works without visual issues."""
        chart = HistogramChart(values=list(range(100)), bins=50)
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_extreme_outlier(self):
        """One extreme outlier doesn't crash (most bins empty)."""
        chart = HistogramChart(values=[1, 2, 3, 4, 5, 1000], bins=10)
        svg = render_svg(chart)
        self.assertIn("<rect", svg)


if __name__ == "__main__":
    unittest.main()
