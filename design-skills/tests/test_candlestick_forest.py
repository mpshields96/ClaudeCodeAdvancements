"""Tests for CandlestickChart and ForestPlot (MT-32 Visual Excellence).

CandlestickChart: OHLC price bars for Kalshi contract price visualization.
ForestPlot: Confidence interval display for statistical meta-analysis.
"""
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from chart_generator import (
    CandlestickChart,
    ForestPlot,
    CCA_COLORS,
    render_svg,
    save_svg,
)


class TestCandlestickChart(unittest.TestCase):
    """Test OHLC candlestick chart."""

    def _sample_data(self):
        # (label, open, high, low, close)
        return [
            ("09:00", 92.0, 95.0, 91.0, 94.0),  # bullish (close > open)
            ("10:00", 94.0, 96.0, 93.0, 93.5),   # bearish (close < open)
            ("11:00", 93.5, 94.0, 92.0, 93.8),    # bullish
            ("12:00", 93.8, 93.8, 90.0, 91.0),    # bearish
        ]

    def test_returns_valid_svg(self):
        chart = CandlestickChart(data=self._sample_data(), title="BTC Sniper Prices")
        svg = render_svg(chart)
        root = ET.fromstring(svg)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")

    def test_contains_title(self):
        chart = CandlestickChart(data=self._sample_data(), title="BTC Prices")
        svg = render_svg(chart)
        self.assertIn("BTC Prices", svg)

    def test_bullish_uses_success_color(self):
        # Single bullish candle (close > open)
        chart = CandlestickChart(data=[("09:00", 90.0, 95.0, 89.0, 94.0)])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["success"], svg)

    def test_bearish_uses_highlight_color(self):
        # Single bearish candle (close < open)
        chart = CandlestickChart(data=[("09:00", 94.0, 95.0, 89.0, 90.0)])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["highlight"], svg)

    def test_doji_uses_muted_color(self):
        # Doji: open == close
        chart = CandlestickChart(data=[("09:00", 92.0, 95.0, 90.0, 92.0)])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["muted"], svg)

    def test_empty_data_shows_no_data(self):
        chart = CandlestickChart(data=[])
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_contains_labels(self):
        chart = CandlestickChart(data=self._sample_data())
        svg = render_svg(chart)
        self.assertIn("09:00", svg)

    def test_has_wicks(self):
        """Each candle should have a wick line (high-low)."""
        chart = CandlestickChart(data=[("09:00", 92.0, 96.0, 89.0, 94.0)])
        svg = render_svg(chart)
        # Should have at least one line element for the wick
        self.assertIn("<line", svg)

    def test_has_body_rect(self):
        """Each candle should have a body rectangle (open-close range)."""
        chart = CandlestickChart(data=[("09:00", 92.0, 96.0, 89.0, 94.0)])
        svg = render_svg(chart)
        # Body is a rect element
        root = ET.fromstring(svg)
        rects = root.findall(".//{http://www.w3.org/2000/svg}rect")
        # At least 2 rects: background + body
        self.assertGreaterEqual(len(rects), 2)

    def test_custom_dimensions(self):
        chart = CandlestickChart(data=self._sample_data(), width=600, height=350)
        svg = render_svg(chart)
        self.assertIn('width="600"', svg)
        self.assertIn('height="350"', svg)

    def test_save_svg(self):
        import tempfile
        chart = CandlestickChart(data=self._sample_data(), title="Test")
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

    def test_y_axis_has_gridlines(self):
        chart = CandlestickChart(data=self._sample_data())
        svg = render_svg(chart)
        # Should have gridline lines
        root = ET.fromstring(svg)
        lines = root.findall(".//{http://www.w3.org/2000/svg}line")
        self.assertGreater(len(lines), 4)  # wicks + gridlines

    def test_single_candle(self):
        chart = CandlestickChart(data=[("09:00", 92.0, 95.0, 91.0, 94.0)])
        svg = render_svg(chart)
        root = ET.fromstring(svg)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")


class TestForestPlot(unittest.TestCase):
    """Test forest plot (confidence interval display)."""

    def _sample_data(self):
        # (label, estimate, ci_lower, ci_upper)
        return [
            ("BTC 93c", 0.028, 0.005, 0.051),
            ("ETH 93c", 0.029, 0.008, 0.050),
            ("SOL 93c", 0.021, -0.003, 0.045),
            ("BTC 94c", -0.027, -0.076, 0.022),
            ("ETH 94c", 0.028, 0.004, 0.052),
        ]

    def test_returns_valid_svg(self):
        chart = ForestPlot(data=self._sample_data(), title="Alpha by Asset/Price")
        svg = render_svg(chart)
        root = ET.fromstring(svg)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")

    def test_contains_title(self):
        chart = ForestPlot(data=self._sample_data(), title="Edge Analysis")
        svg = render_svg(chart)
        self.assertIn("Edge Analysis", svg)

    def test_contains_labels(self):
        chart = ForestPlot(data=self._sample_data())
        svg = render_svg(chart)
        self.assertIn("BTC 93c", svg)
        self.assertIn("SOL 93c", svg)

    def test_empty_data_shows_no_data(self):
        chart = ForestPlot(data=[])
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_has_reference_line(self):
        """Should have a vertical reference line at zero (or custom value)."""
        chart = ForestPlot(data=self._sample_data())
        svg = render_svg(chart)
        # Reference line should be present
        self.assertIn("<line", svg)

    def test_custom_reference_line(self):
        chart = ForestPlot(data=self._sample_data(), reference_value=0.05)
        svg = render_svg(chart)
        root = ET.fromstring(svg)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")

    def test_has_ci_lines(self):
        """Each study should have a horizontal CI line."""
        chart = ForestPlot(data=self._sample_data())
        svg = render_svg(chart)
        root = ET.fromstring(svg)
        lines = root.findall(".//{http://www.w3.org/2000/svg}line")
        # At least 5 CI lines + reference line + axis
        self.assertGreaterEqual(len(lines), 5)

    def test_has_estimate_markers(self):
        """Each study should have a circle/diamond at the estimate point."""
        chart = ForestPlot(data=self._sample_data())
        svg = render_svg(chart)
        root = ET.fromstring(svg)
        # Should have diamond paths or circles for each estimate
        # We use rect rotated 45deg as diamonds
        self.assertTrue(
            len(root.findall(".//{http://www.w3.org/2000/svg}rect")) >= 1 + len(self._sample_data())
            or len(root.findall(".//{http://www.w3.org/2000/svg}circle")) >= len(self._sample_data())
        )

    def test_positive_estimate_uses_success(self):
        chart = ForestPlot(data=[("Test", 0.05, 0.01, 0.09)])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["success"], svg)

    def test_negative_estimate_uses_highlight(self):
        chart = ForestPlot(data=[("Test", -0.05, -0.09, -0.01)])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["highlight"], svg)

    def test_ci_crossing_zero_uses_muted(self):
        """CI spanning zero = inconclusive, should use muted color."""
        chart = ForestPlot(data=[("Test", 0.01, -0.05, 0.07)])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["muted"], svg)

    def test_custom_dimensions(self):
        chart = ForestPlot(data=self._sample_data(), width=700, height=500)
        svg = render_svg(chart)
        self.assertIn('width="700"', svg)
        self.assertIn('height="500"', svg)

    def test_single_study(self):
        chart = ForestPlot(data=[("BTC 93c", 0.028, 0.005, 0.051)])
        svg = render_svg(chart)
        root = ET.fromstring(svg)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")

    def test_save_svg(self):
        import tempfile
        chart = ForestPlot(data=self._sample_data(), title="Test")
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            save_svg(chart, path)
            self.assertTrue(os.path.exists(path))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
