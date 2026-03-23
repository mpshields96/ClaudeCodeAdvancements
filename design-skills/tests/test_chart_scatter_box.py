"""Tests for ScatterPlot and BoxPlot in chart_generator.py."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chart_generator import (
    BoxPlot,
    ScatterPlot,
    CCA_COLORS,
    SERIES_PALETTE,
    render_svg,
    save_svg,
)


class TestScatterPlot(unittest.TestCase):
    """Tests for ScatterPlot — XY correlation with optional trend lines."""

    def test_basic_render(self):
        """Renders SVG with scatter points."""
        chart = ScatterPlot(
            series=[{"name": "Tests", "points": [(1, 10), (2, 20), (3, 15)]}],
            title="Test Scatter",
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertIn("<circle", svg)

    def test_empty_series(self):
        """Renders 'No data' for empty series list."""
        chart = ScatterPlot(series=[], title="Empty")
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_empty_points(self):
        """Renders 'No data' when series has no points."""
        chart = ScatterPlot(series=[{"name": "A", "points": []}])
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_single_point(self):
        """Renders a single point without error."""
        chart = ScatterPlot(
            series=[{"name": "One", "points": [(5, 5)]}],
        )
        svg = render_svg(chart)
        self.assertIn("<circle", svg)

    def test_multiple_series(self):
        """Multiple series render with different colors and legend."""
        chart = ScatterPlot(
            series=[
                {"name": "A", "points": [(1, 2), (3, 4)]},
                {"name": "B", "points": [(5, 6), (7, 8)]},
            ],
            title="Multi-Series",
        )
        svg = render_svg(chart)
        # Should have circles for all 4 points
        self.assertEqual(svg.count("<circle"), 4 + 2)  # 4 data + 2 legend

    def test_legend_only_for_multiple_series(self):
        """Single series should not render a legend."""
        chart = ScatterPlot(
            series=[{"name": "Solo", "points": [(1, 2), (3, 4)]}],
        )
        svg = render_svg(chart)
        # Only 2 data circles, no legend circles
        self.assertEqual(svg.count("<circle"), 2)

    def test_custom_colors(self):
        """Series with custom colors uses those colors."""
        chart = ScatterPlot(
            series=[{"name": "Red", "points": [(1, 2)], "color": "#ff0000"}],
        )
        svg = render_svg(chart)
        self.assertIn("#ff0000", svg)

    def test_trend_line(self):
        """show_trend=True renders a dashed trend line."""
        chart = ScatterPlot(
            series=[{"name": "T", "points": [(1, 1), (2, 2), (3, 3)]}],
            show_trend=True,
        )
        svg = render_svg(chart)
        # Trend line uses stroke-dasharray="6,3" (grid uses "3,3")
        self.assertIn('stroke-dasharray="6,3"', svg)

    def test_trend_line_single_point_no_crash(self):
        """Trend line with 1 point should not crash (needs 2+ points)."""
        chart = ScatterPlot(
            series=[{"name": "T", "points": [(5, 5)]}],
            show_trend=True,
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        # No trend line since only 1 point (only grid dasharray "3,3")
        self.assertNotIn('stroke-dasharray="6,3"', svg)

    def test_trend_line_vertical_data(self):
        """Trend line with all same x values (vertical line, denom=0) is skipped."""
        chart = ScatterPlot(
            series=[{"name": "V", "points": [(5, 1), (5, 2), (5, 3)]}],
            show_trend=True,
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        # denom would be zero, so no trend line rendered (only grid dasharray)
        self.assertNotIn('stroke-dasharray="6,3"', svg)

    def test_axis_labels(self):
        """X and Y axis labels appear in SVG."""
        chart = ScatterPlot(
            series=[{"name": "D", "points": [(1, 2)]}],
            x_label="Duration (min)",
            y_label="Score",
        )
        svg = render_svg(chart)
        self.assertIn("Duration (min)", svg)
        self.assertIn("Score", svg)

    def test_title_rendered(self):
        """Title appears in SVG."""
        chart = ScatterPlot(
            series=[{"name": "D", "points": [(1, 2)]}],
            title="My Scatter",
        )
        svg = render_svg(chart)
        self.assertIn("My Scatter", svg)

    def test_custom_dimensions(self):
        """Custom width/height respected."""
        chart = ScatterPlot(
            series=[{"name": "D", "points": [(1, 2)]}],
            width=800,
            height=600,
        )
        svg = render_svg(chart)
        self.assertIn('width="800"', svg)
        self.assertIn('height="600"', svg)

    def test_custom_point_radius(self):
        """Point radius is configurable."""
        chart = ScatterPlot(
            series=[{"name": "D", "points": [(1, 2)]}],
            point_radius=8.0,
        )
        svg = render_svg(chart)
        self.assertIn('r="8.0"', svg)

    def test_save_svg(self):
        """save_svg writes file to disk."""
        chart = ScatterPlot(
            series=[{"name": "D", "points": [(1, 2), (3, 4)]}],
        )
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
        """Handles negative x and y values."""
        chart = ScatterPlot(
            series=[{"name": "N", "points": [(-5, -10), (5, 10)]}],
        )
        svg = render_svg(chart)
        self.assertIn("<circle", svg)

    def test_identical_points(self):
        """All points at same location renders without error."""
        chart = ScatterPlot(
            series=[{"name": "Same", "points": [(3, 3), (3, 3), (3, 3)]}],
        )
        svg = render_svg(chart)
        self.assertEqual(svg.count("<circle"), 3)

    def test_large_dataset(self):
        """Handles 100 points without error."""
        pts = [(i, i * 2 + (i % 7)) for i in range(100)]
        chart = ScatterPlot(series=[{"name": "Big", "points": pts}])
        svg = render_svg(chart)
        self.assertEqual(svg.count("<circle"), 100)

    def test_series_default_name(self):
        """Series without name gets default 'Series N'."""
        chart = ScatterPlot(
            series=[{"points": [(1, 2)]}, {"points": [(3, 4)]}],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_three_series_legend(self):
        """Three series shows 3 legend entries."""
        chart = ScatterPlot(
            series=[
                {"name": "A", "points": [(1, 2)]},
                {"name": "B", "points": [(3, 4)]},
                {"name": "C", "points": [(5, 6)]},
            ],
        )
        svg = render_svg(chart)
        self.assertIn("A", svg)
        self.assertIn("B", svg)
        self.assertIn("C", svg)

    def test_trend_with_multiple_series(self):
        """Trend lines rendered for each series independently."""
        chart = ScatterPlot(
            series=[
                {"name": "A", "points": [(1, 1), (2, 2)]},
                {"name": "B", "points": [(1, 3), (2, 1)]},
            ],
            show_trend=True,
        )
        svg = render_svg(chart)
        # Two trend lines with "6,3" dash pattern (grid uses "3,3")
        self.assertEqual(svg.count('stroke-dasharray="6,3"'), 2)


class TestBoxPlot(unittest.TestCase):
    """Tests for BoxPlot — box-and-whisker distribution comparison."""

    def test_basic_render(self):
        """Renders SVG with box elements."""
        chart = BoxPlot(
            data=[("Group A", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])],
            title="Test Box",
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertIn("<rect", svg)

    def test_empty_data(self):
        """Renders 'No data' for empty input."""
        chart = BoxPlot(data=[], title="Empty")
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_empty_values(self):
        """Category with empty values list is skipped."""
        chart = BoxPlot(data=[("Empty", [])])
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_single_value(self):
        """Single value: median=q1=q3, no whiskers needed."""
        chart = BoxPlot(data=[("Solo", [5])])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_two_values(self):
        """Two values renders without error."""
        chart = BoxPlot(data=[("Pair", [3, 7])])
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_multiple_categories(self):
        """Multiple categories render side by side."""
        chart = BoxPlot(
            data=[
                ("A", [1, 2, 3, 4, 5]),
                ("B", [10, 20, 30, 40, 50]),
                ("C", [2, 4, 6, 8, 10]),
            ],
            title="Comparison",
        )
        svg = render_svg(chart)
        self.assertIn("A", svg)
        self.assertIn("B", svg)
        self.assertIn("C", svg)

    def test_outlier_detection(self):
        """Outliers beyond 1.5*IQR rendered as circles."""
        # [1,2,3,4,5,6,7,8,9,100] — 100 is an outlier
        chart = BoxPlot(
            data=[("Outlier", [1, 2, 3, 4, 5, 6, 7, 8, 9, 100])],
            show_outliers=True,
        )
        svg = render_svg(chart)
        # Outlier circle should have highlight color
        self.assertIn(CCA_COLORS["highlight"], svg)

    def test_no_outliers_flag(self):
        """show_outliers=False suppresses outlier dots."""
        chart = BoxPlot(
            data=[("No Out", [1, 2, 3, 4, 5, 6, 7, 8, 9, 100])],
            show_outliers=False,
        )
        svg = render_svg(chart)
        # Should not have open circles for outliers
        # The highlight color still appears for the median line
        # Count circles — should be 0 (no outlier dots)
        # Median uses <line>, whisker caps use <line>, so no <circle> expected
        self.assertNotIn('fill="none"', svg)

    def test_median_line(self):
        """Median line uses highlight color."""
        chart = BoxPlot(data=[("Med", [1, 2, 3, 4, 5])])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["highlight"], svg)

    def test_custom_color(self):
        """Custom box color is used."""
        chart = BoxPlot(
            data=[("Custom", [1, 2, 3, 4, 5])],
            color="#336699",
        )
        svg = render_svg(chart)
        self.assertIn("#336699", svg)

    def test_default_color(self):
        """Default color is CCA accent."""
        chart = BoxPlot(data=[("Default", [1, 2, 3, 4, 5])])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["accent"], svg)

    def test_y_label(self):
        """Y-axis label is rendered."""
        chart = BoxPlot(
            data=[("G", [1, 2, 3, 4, 5])],
            y_label="Duration (ms)",
        )
        svg = render_svg(chart)
        self.assertIn("Duration (ms)", svg)

    def test_title_rendered(self):
        """Title appears in SVG."""
        chart = BoxPlot(
            data=[("G", [1, 2, 3, 4, 5])],
            title="My Box Plot",
        )
        svg = render_svg(chart)
        self.assertIn("My Box Plot", svg)

    def test_custom_dimensions(self):
        """Custom width/height respected."""
        chart = BoxPlot(
            data=[("G", [1, 2, 3, 4, 5])],
            width=700, height=500,
        )
        svg = render_svg(chart)
        self.assertIn('width="700"', svg)
        self.assertIn('height="500"', svg)

    def test_save_svg(self):
        """save_svg writes file to disk."""
        chart = BoxPlot(data=[("G", [1, 2, 3, 4, 5, 6, 7])])
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
        chart = BoxPlot(data=[("Neg", [-10, -5, 0, 5, 10])])
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_uniform_distribution(self):
        """All same values: q1=median=q3, zero IQR, no outliers."""
        chart = BoxPlot(data=[("Flat", [5, 5, 5, 5, 5])])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_large_dataset(self):
        """Handles 1000 values per category."""
        import random
        random.seed(42)
        vals = [random.gauss(50, 10) for _ in range(1000)]
        chart = BoxPlot(data=[("Large", vals)])
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_whisker_caps(self):
        """Whisker caps (horizontal lines) are rendered."""
        chart = BoxPlot(data=[("W", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])])
        svg = render_svg(chart)
        # Should have multiple line elements for whiskers + caps
        self.assertGreater(svg.count("<line"), 4)

    def test_no_outliers_in_clean_data(self):
        """Data with no outliers has no open circles."""
        chart = BoxPlot(data=[("Clean", [1, 2, 3, 4, 5])])
        svg = render_svg(chart)
        self.assertNotIn('fill="none"', svg)

    def test_five_categories(self):
        """Five categories all render."""
        data = [(f"Cat{i}", list(range(i, i + 10))) for i in range(5)]
        chart = BoxPlot(data=data, title="Five")
        svg = render_svg(chart)
        for i in range(5):
            self.assertIn(f"Cat{i}", svg)


if __name__ == "__main__":
    unittest.main()
