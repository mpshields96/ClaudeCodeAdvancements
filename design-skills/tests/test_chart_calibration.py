"""Tests for CalibrationPlot — predicted vs actual probability curve.

Publication-quality calibration chart for evaluating prediction markets,
FLB analysis, and probability model assessment. MT-32 Visual Excellence.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chart_generator import CalibrationPlot, render_svg, save_svg, CCA_COLORS


class TestCalibrationPlotDataclass(unittest.TestCase):
    """Test CalibrationPlot construction and defaults."""

    def test_basic_creation(self):
        """Create a calibration plot with minimal data."""
        chart = CalibrationPlot(
            bins=[(0.5, 0.48, 20), (0.6, 0.55, 30), (0.9, 0.92, 50)],
        )
        self.assertEqual(len(chart.bins), 3)
        self.assertEqual(chart.width, 500)
        self.assertEqual(chart.height, 400)

    def test_defaults(self):
        chart = CalibrationPlot(bins=[])
        self.assertEqual(chart.title, "")
        self.assertTrue(chart.show_diagonal)
        self.assertTrue(chart.show_sample_sizes)
        self.assertEqual(chart.point_radius, 5.0)

    def test_custom_title(self):
        chart = CalibrationPlot(
            bins=[(0.9, 0.95, 100)],
            title="Sniper Calibration Curve",
        )
        self.assertEqual(chart.title, "Sniper Calibration Curve")


class TestCalibrationPlotRendering(unittest.TestCase):
    """Test SVG rendering of calibration plots."""

    def _make_chart(self, **kwargs):
        default_bins = [
            (0.50, 0.48, 20),
            (0.60, 0.55, 30),
            (0.70, 0.68, 40),
            (0.80, 0.78, 60),
            (0.90, 0.93, 100),
            (0.95, 0.97, 80),
        ]
        defaults = {"bins": default_bins, "title": "Calibration"}
        defaults.update(kwargs)
        return CalibrationPlot(**defaults)

    def test_renders_valid_svg(self):
        """Output is valid SVG."""
        svg = render_svg(self._make_chart())
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.strip().endswith("</svg>"))
        self.assertIn("xmlns", svg)

    def test_contains_title(self):
        svg = render_svg(self._make_chart(title="FLB Analysis"))
        self.assertIn("FLB Analysis", svg)

    def test_no_title_when_empty(self):
        svg = render_svg(self._make_chart(title=""))
        # Should not have a bold title text element (just axes)
        self.assertNotIn('font-weight="bold"', svg.split("</text>")[0] if "</text>" in svg else "")

    def test_contains_diagonal_line(self):
        """Perfect calibration diagonal should be rendered."""
        svg = render_svg(self._make_chart(show_diagonal=True))
        # Diagonal is a dashed line from (0,0) to (1,1) in data coords
        self.assertIn("stroke-dasharray", svg)

    def test_no_diagonal_when_disabled(self):
        svg = render_svg(self._make_chart(show_diagonal=False))
        self.assertNotIn("stroke-dasharray", svg)

    def test_contains_data_points(self):
        """Each bin should be rendered as a circle."""
        chart = self._make_chart()
        svg = render_svg(chart)
        # Count circles — at least one per bin
        circle_count = svg.count("<circle")
        self.assertGreaterEqual(circle_count, len(chart.bins))

    def test_contains_sample_size_labels(self):
        """Sample sizes should appear as text labels when enabled."""
        svg = render_svg(self._make_chart(show_sample_sizes=True))
        self.assertIn("n=20", svg)
        self.assertIn("n=100", svg)

    def test_no_sample_sizes_when_disabled(self):
        svg = render_svg(self._make_chart(show_sample_sizes=False))
        self.assertNotIn("n=20", svg)
        self.assertNotIn("n=100", svg)

    def test_axis_labels(self):
        """X and Y axis labels should be present."""
        svg = render_svg(self._make_chart())
        self.assertIn("Predicted", svg)
        self.assertIn("Actual", svg)

    def test_custom_axis_labels(self):
        svg = render_svg(self._make_chart(
            x_label="Contract Price", y_label="Win Rate"
        ))
        self.assertIn("Contract Price", svg)
        self.assertIn("Win Rate", svg)

    def test_point_color_default(self):
        """Points should use CCA accent color by default."""
        svg = render_svg(self._make_chart())
        self.assertIn(CCA_COLORS["accent"], svg)

    def test_custom_color(self):
        svg = render_svg(self._make_chart(color="#ff0000"))
        self.assertIn("#ff0000", svg)

    def test_gridlines_present(self):
        """Should have gridlines at regular intervals."""
        svg = render_svg(self._make_chart())
        # Multiple light lines for grid
        self.assertGreater(svg.count(CCA_COLORS["border"]), 2)


class TestCalibrationPlotEdgeCases(unittest.TestCase):
    """Edge cases and special inputs."""

    def test_empty_bins(self):
        """Empty bins should render a 'No data' placeholder."""
        svg = render_svg(CalibrationPlot(bins=[]))
        self.assertIn("No data", svg)

    def test_single_bin(self):
        """Single data point should still render."""
        svg = render_svg(CalibrationPlot(bins=[(0.90, 0.95, 50)]))
        self.assertIn("<circle", svg)

    def test_perfect_calibration(self):
        """All points on the diagonal."""
        bins = [(0.5, 0.5, 10), (0.7, 0.7, 10), (0.9, 0.9, 10)]
        svg = render_svg(CalibrationPlot(bins=bins))
        self.assertIn("<svg", svg)

    def test_extreme_miscalibration(self):
        """Points far from diagonal."""
        bins = [(0.9, 0.5, 10), (0.5, 0.9, 10)]
        svg = render_svg(CalibrationPlot(bins=bins))
        self.assertIn("<svg", svg)

    def test_save_to_file(self):
        """save_svg works with CalibrationPlot."""
        chart = CalibrationPlot(
            bins=[(0.90, 0.95, 50)],
            title="Test Save",
        )
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            save_svg(chart, path)
            with open(path) as fh:
                content = fh.read()
            self.assertIn("<svg", content)
            self.assertIn("Test Save", content)
        finally:
            os.unlink(path)

    def test_zero_sample_size(self):
        """Bins with n=0 should still render (just small dots)."""
        bins = [(0.5, 0.45, 0), (0.9, 0.92, 50)]
        svg = render_svg(CalibrationPlot(bins=bins))
        self.assertIn("<svg", svg)

    def test_special_chars_in_title(self):
        """Special characters should be escaped."""
        svg = render_svg(CalibrationPlot(
            bins=[(0.9, 0.95, 50)],
            title="FLB <90c> & Calibration",
        ))
        self.assertIn("&lt;90c&gt;", svg)
        self.assertIn("&amp;", svg)


class TestCalibrationPlotMultiSeries(unittest.TestCase):
    """Test multi-series calibration (e.g. per-asset comparison)."""

    def test_multi_series_creation(self):
        chart = CalibrationPlot(
            bins=[(0.9, 0.95, 50)],
            extra_series=[
                ("SOL", [(0.9, 0.88, 30), (0.95, 0.91, 20)], "#e94560"),
                ("ETH", [(0.9, 0.93, 40), (0.95, 0.96, 35)], "#16c79a"),
            ],
        )
        self.assertEqual(len(chart.extra_series), 2)

    def test_multi_series_renders_legend(self):
        chart = CalibrationPlot(
            bins=[(0.9, 0.95, 50)],
            series_name="BTC",
            extra_series=[
                ("SOL", [(0.9, 0.88, 30)], "#e94560"),
            ],
        )
        svg = render_svg(chart)
        self.assertIn("BTC", svg)
        self.assertIn("SOL", svg)

    def test_multi_series_distinct_colors(self):
        chart = CalibrationPlot(
            bins=[(0.9, 0.95, 50)],
            extra_series=[
                ("SOL", [(0.9, 0.88, 30)], "#e94560"),
            ],
        )
        svg = render_svg(chart)
        self.assertIn("#e94560", svg)


if __name__ == "__main__":
    unittest.main()
