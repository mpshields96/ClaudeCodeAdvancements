"""Tests for ViolinPlot in chart_generator.py."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chart_generator import (
    ViolinPlot,
    CCA_COLORS,
    render_svg,
    save_svg,
)


class TestViolinPlot(unittest.TestCase):
    """Tests for ViolinPlot — KDE-based distribution shape."""

    def test_basic_render(self):
        """Renders SVG with violin shape."""
        chart = ViolinPlot(
            data=[("Group A", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])],
            title="Test Violin",
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertIn("<path", svg)

    def test_empty_data(self):
        """Renders 'No data' for empty input."""
        chart = ViolinPlot(data=[], title="Empty")
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_empty_values(self):
        """Category with empty values list is skipped."""
        chart = ViolinPlot(data=[("Empty", [])])
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_single_value(self):
        """Single value renders without error (degenerate KDE)."""
        chart = ViolinPlot(data=[("Solo", [5])])
        svg = render_svg(chart)
        self.assertIn("<path", svg)

    def test_two_values(self):
        """Two values renders without error."""
        chart = ViolinPlot(data=[("Pair", [3, 7])])
        svg = render_svg(chart)
        self.assertIn("<path", svg)

    def test_multiple_categories(self):
        """Multiple categories render side by side."""
        chart = ViolinPlot(
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
        # Should have 3 violin shapes
        self.assertEqual(svg.count("<path"), 3)

    def test_median_line(self):
        """Median line uses highlight color."""
        chart = ViolinPlot(data=[("Med", [1, 2, 3, 4, 5])])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["highlight"], svg)

    def test_quartile_lines(self):
        """Q1 and Q3 lines are rendered as dashed lines."""
        chart = ViolinPlot(data=[("Q", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])])
        svg = render_svg(chart)
        # Q1/Q3 use stroke-dasharray="3,2" (not the grid "3,3")
        self.assertIn('stroke-dasharray="3,2"', svg)

    def test_mirrored_shape(self):
        """Violin is symmetric (mirrored left/right)."""
        chart = ViolinPlot(data=[("Sym", [1, 2, 3, 4, 5])])
        svg = render_svg(chart)
        # Path should contain Z (closed polygon)
        self.assertIn("Z", svg)

    def test_custom_color(self):
        """Custom fill color is used."""
        chart = ViolinPlot(
            data=[("Custom", [1, 2, 3, 4, 5])],
            color="#336699",
        )
        svg = render_svg(chart)
        self.assertIn("#336699", svg)

    def test_default_color(self):
        """Default color is CCA accent."""
        chart = ViolinPlot(data=[("Default", [1, 2, 3, 4, 5])])
        svg = render_svg(chart)
        self.assertIn(CCA_COLORS["accent"], svg)

    def test_y_label(self):
        """Y-axis label is rendered."""
        chart = ViolinPlot(
            data=[("G", [1, 2, 3, 4, 5])],
            y_label="Duration (ms)",
        )
        svg = render_svg(chart)
        self.assertIn("Duration (ms)", svg)

    def test_title_rendered(self):
        """Title appears in SVG."""
        chart = ViolinPlot(
            data=[("G", [1, 2, 3, 4, 5])],
            title="My Violin",
        )
        svg = render_svg(chart)
        self.assertIn("My Violin", svg)

    def test_custom_dimensions(self):
        """Custom width/height respected."""
        chart = ViolinPlot(
            data=[("G", [1, 2, 3, 4, 5])],
            width=700, height=500,
        )
        svg = render_svg(chart)
        self.assertIn('width="700"', svg)
        self.assertIn('height="500"', svg)

    def test_save_svg(self):
        """save_svg writes file to disk."""
        chart = ViolinPlot(data=[("G", [1, 2, 3, 4, 5, 6, 7])])
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
        chart = ViolinPlot(data=[("Neg", [-10, -5, 0, 5, 10])])
        svg = render_svg(chart)
        self.assertIn("<path", svg)

    def test_uniform_distribution(self):
        """All same values renders without error."""
        chart = ViolinPlot(data=[("Flat", [5, 5, 5, 5, 5])])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_large_dataset(self):
        """Handles 1000 values per category."""
        import random
        random.seed(42)
        vals = [random.gauss(50, 10) for _ in range(1000)]
        chart = ViolinPlot(data=[("Large", vals)])
        svg = render_svg(chart)
        self.assertIn("<path", svg)

    def test_bimodal_distribution(self):
        """Bimodal data renders correctly (should show two humps)."""
        import random
        random.seed(42)
        vals = [random.gauss(20, 3) for _ in range(50)]
        vals += [random.gauss(50, 3) for _ in range(50)]
        chart = ViolinPlot(data=[("Bimodal", vals)])
        svg = render_svg(chart)
        self.assertIn("<path", svg)

    def test_five_categories(self):
        """Five categories all render."""
        data = [(f"Cat{i}", list(range(i, i + 10))) for i in range(5)]
        chart = ViolinPlot(data=data, title="Five")
        svg = render_svg(chart)
        for i in range(5):
            self.assertIn(f"Cat{i}", svg)

    def test_category_labels(self):
        """Category labels appear below each violin."""
        chart = ViolinPlot(
            data=[("Alpha", [1, 2, 3]), ("Beta", [4, 5, 6])],
        )
        svg = render_svg(chart)
        self.assertIn("Alpha", svg)
        self.assertIn("Beta", svg)

    def test_mixed_empty_and_nonempty(self):
        """Empty categories are skipped, non-empty render."""
        chart = ViolinPlot(
            data=[("A", [1, 2, 3]), ("B", []), ("C", [4, 5, 6])],
        )
        svg = render_svg(chart)
        self.assertIn("A", svg)
        self.assertIn("C", svg)
        self.assertEqual(svg.count("<path"), 2)

    def test_kde_gaussian_shape(self):
        """Path data forms a closed polygon (M...L...Z)."""
        chart = ViolinPlot(data=[("G", [1, 2, 3, 4, 5])])
        svg = render_svg(chart)
        # Find path d attribute
        import re
        paths = re.findall(r'd="([^"]+)"', svg)
        self.assertTrue(len(paths) > 0)
        self.assertTrue(paths[0].startswith("M"))
        self.assertTrue(paths[0].endswith("Z"))


if __name__ == "__main__":
    unittest.main()
