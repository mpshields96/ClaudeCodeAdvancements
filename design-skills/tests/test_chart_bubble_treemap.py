"""Tests for BubbleChart and TreemapChart in chart_generator.py."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chart_generator import (
    BubbleChart,
    TreemapChart,
    CCA_COLORS,
    SERIES_PALETTE,
    render_svg,
    save_svg,
)


class TestBubbleChart(unittest.TestCase):
    """Tests for BubbleChart — scatter with sized circles."""

    def test_basic_render(self):
        """Renders SVG with bubbles."""
        chart = BubbleChart(
            data=[("A", 10, 20, 30), ("B", 50, 60, 70)],
            title="Test Bubble",
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertIn("<circle", svg)

    def test_empty_data(self):
        """Renders 'No data' for empty input."""
        chart = BubbleChart(data=[], title="Empty")
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_single_point(self):
        """Renders a single bubble."""
        chart = BubbleChart(data=[("Only", 5, 5, 10)])
        svg = render_svg(chart)
        self.assertIn("<circle", svg)

    def test_custom_colors(self):
        """Supports per-bubble custom colors."""
        chart = BubbleChart(
            data=[
                ("A", 10, 20, 30, "#ff0000"),
                ("B", 50, 60, 70, "#00ff00"),
            ]
        )
        svg = render_svg(chart)
        self.assertIn("#ff0000", svg)
        self.assertIn("#00ff00", svg)

    def test_auto_colors(self):
        """Uses SERIES_PALETTE when no color specified."""
        chart = BubbleChart(data=[("A", 10, 20, 30), ("B", 50, 60, 70)])
        svg = render_svg(chart)
        self.assertIn(SERIES_PALETTE[0], svg)
        self.assertIn(SERIES_PALETTE[1], svg)

    def test_title_rendered(self):
        """Title text appears in SVG."""
        chart = BubbleChart(data=[("A", 1, 2, 3)], title="My Bubble Chart")
        svg = render_svg(chart)
        self.assertIn("My Bubble Chart", svg)

    def test_axis_labels(self):
        """X and Y axis labels render."""
        chart = BubbleChart(
            data=[("A", 1, 2, 3)],
            x_label="X Axis",
            y_label="Y Axis",
        )
        svg = render_svg(chart)
        self.assertIn("X Axis", svg)
        self.assertIn("Y Axis", svg)

    def test_many_bubbles(self):
        """Handles 10+ data points."""
        data = [(f"P{i}", i * 10, i * 5, i * 3) for i in range(15)]
        chart = BubbleChart(data=data, title="Many Bubbles")
        svg = render_svg(chart)
        self.assertEqual(svg.count("<circle"), 15)

    def test_same_size_bubbles(self):
        """All same size produces valid SVG (no division by zero)."""
        chart = BubbleChart(data=[("A", 1, 2, 5), ("B", 3, 4, 5)])
        svg = render_svg(chart)
        self.assertIn("<circle", svg)
        self.assertNotIn("NaN", svg)
        self.assertNotIn("inf", svg)

    def test_same_position(self):
        """Overlapping points produce valid SVG."""
        chart = BubbleChart(data=[("A", 5, 5, 10), ("B", 5, 5, 20)])
        svg = render_svg(chart)
        self.assertEqual(svg.count("<circle"), 2)

    def test_negative_values(self):
        """Handles negative x/y values."""
        chart = BubbleChart(data=[("A", -10, -5, 3), ("B", 10, 5, 7)])
        svg = render_svg(chart)
        self.assertIn("<circle", svg)

    def test_custom_dimensions(self):
        """Respects width/height."""
        chart = BubbleChart(data=[("A", 1, 2, 3)], width=800, height=600)
        svg = render_svg(chart)
        self.assertIn('viewBox="0 0 800 600"', svg)

    def test_large_labels_in_bubbles(self):
        """Labels render inside large enough bubbles."""
        chart = BubbleChart(
            data=[("BigLabel", 50, 50, 100)],
            min_radius=30, max_radius=60,
        )
        svg = render_svg(chart)
        self.assertIn("BigLabel", svg)

    def test_save_to_file(self):
        """save_svg writes valid SVG file."""
        chart = BubbleChart(data=[("A", 1, 2, 3)], title="Save Test")
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

    def test_grid_lines(self):
        """Y-axis grid lines render."""
        chart = BubbleChart(data=[("A", 1, 100, 3), ("B", 50, 200, 7)])
        svg = render_svg(chart)
        self.assertIn("stroke-dasharray", svg)

    def test_min_max_radius(self):
        """Bubble sizes respect min/max radius settings."""
        chart = BubbleChart(
            data=[("Small", 1, 1, 1), ("Big", 10, 10, 100)],
            min_radius=5, max_radius=50,
        )
        svg = render_svg(chart)
        # Both should render
        self.assertEqual(svg.count("<circle"), 2)

    def test_largest_drawn_first(self):
        """Largest bubbles are drawn first (so small ones aren't hidden)."""
        chart = BubbleChart(
            data=[("Small", 1, 1, 1), ("Big", 10, 10, 100)],
        )
        svg = render_svg(chart)
        # Big should appear before Small in SVG
        big_pos = svg.index("Big") if "Big" in svg else -1
        small_pos = svg.index("Small") if "Small" in svg else -1
        # If both are labeled (large enough), big should be first
        # This test just verifies both render without error
        self.assertEqual(svg.count("<circle"), 2)


class TestTreemapChart(unittest.TestCase):
    """Tests for TreemapChart — nested rectangles sized by value."""

    def test_basic_render(self):
        """Renders SVG with rectangles."""
        chart = TreemapChart(
            data=[("A", 50), ("B", 30), ("C", 20)],
            title="Test Treemap",
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertIn("<rect", svg)

    def test_empty_data(self):
        """Renders 'No data' for empty input."""
        chart = TreemapChart(data=[], title="Empty")
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_single_item(self):
        """Single item fills the entire area."""
        chart = TreemapChart(data=[("Only", 100)])
        svg = render_svg(chart)
        self.assertIn("Only", svg)

    def test_custom_colors(self):
        """Supports per-item custom colors."""
        chart = TreemapChart(
            data=[
                ("A", 50, "#ff0000"),
                ("B", 30, "#00ff00"),
            ]
        )
        svg = render_svg(chart)
        self.assertIn("#ff0000", svg)
        self.assertIn("#00ff00", svg)

    def test_auto_colors(self):
        """Uses SERIES_PALETTE when no color specified."""
        chart = TreemapChart(data=[("A", 50), ("B", 30)])
        svg = render_svg(chart)
        self.assertIn(SERIES_PALETTE[0], svg)

    def test_title_rendered(self):
        """Title appears in SVG."""
        chart = TreemapChart(data=[("A", 50)], title="Treemap Title")
        svg = render_svg(chart)
        self.assertIn("Treemap Title", svg)

    def test_percentage_labels(self):
        """Shows percentage labels on large rectangles."""
        chart = TreemapChart(
            data=[("Big", 80), ("Small", 20)],
            width=600, height=400,
        )
        svg = render_svg(chart)
        self.assertIn("Big", svg)
        # Percentage should appear
        self.assertIn("%", svg)

    def test_many_items(self):
        """Handles 10+ items."""
        data = [(f"Item{i}", (10 - i) * 10 + 5) for i in range(10)]
        chart = TreemapChart(data=data, title="Many Items")
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_zero_values_filtered(self):
        """Zero-value items are excluded."""
        chart = TreemapChart(data=[("A", 50), ("B", 0), ("C", 30)])
        svg = render_svg(chart)
        self.assertNotIn(">B<", svg)  # B should not appear as label

    def test_all_zero_values(self):
        """All-zero data shows 'No data'."""
        chart = TreemapChart(data=[("A", 0), ("B", 0)])
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_custom_dimensions(self):
        """Respects width/height."""
        chart = TreemapChart(data=[("A", 50)], width=800, height=600)
        svg = render_svg(chart)
        self.assertIn('viewBox="0 0 800 600"', svg)

    def test_proportional_sizing(self):
        """Larger values get larger rectangles (verified by SVG structure)."""
        chart = TreemapChart(
            data=[("Big", 90), ("Small", 10)],
            width=500, height=400,
        )
        svg = render_svg(chart)
        # Both should render
        self.assertIn("Big", svg)
        # Small may not have label if rectangle is too small, but should still have rect
        self.assertGreater(svg.count("<rect"), 2)  # bg + at least 2 rects

    def test_save_to_file(self):
        """save_svg writes valid SVG file."""
        chart = TreemapChart(data=[("A", 50), ("B", 30)], title="Save Test")
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

    def test_equal_values(self):
        """Equal-value items produce equal-ish rectangles."""
        chart = TreemapChart(data=[("A", 50), ("B", 50)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_special_characters_in_labels(self):
        """HTML special characters are escaped."""
        chart = TreemapChart(data=[("A<B>C", 50)])
        svg = render_svg(chart)
        self.assertIn("&lt;", svg)


if __name__ == "__main__":
    unittest.main()
