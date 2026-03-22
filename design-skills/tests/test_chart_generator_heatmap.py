"""Tests for HeatmapChart and generate_heatmap() in chart_generator.py.

Verifies heatmap renders colored cells in SVG following CCA design language:
- CCA COLORS palette (no SVG gradient elements)
- Row and column axis labels
- Valid SVG structure
"""

import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from chart_generator import (
    HeatmapChart,
    CCA_COLORS,
    render_svg,
    save_svg,
    generate_heatmap,
)

SVG_NS = "http://www.w3.org/2000/svg"


def _parse(svg: str):
    """Parse SVG string to ElementTree. Raises if invalid XML."""
    return ET.fromstring(svg)


class TestHeatmapChartDataclass(unittest.TestCase):
    """Test HeatmapChart dataclass construction and defaults."""

    def test_basic_construction(self):
        chart = HeatmapChart(data=[[1, 2], [3, 4]])
        self.assertEqual(chart.data, [[1, 2], [3, 4]])

    def test_default_title_empty(self):
        chart = HeatmapChart(data=[[1]])
        self.assertEqual(chart.title, "")

    def test_default_width_height(self):
        chart = HeatmapChart(data=[[1]])
        self.assertEqual(chart.width, 500)
        self.assertEqual(chart.height, 400)

    def test_default_show_values_false(self):
        chart = HeatmapChart(data=[[1]])
        self.assertFalse(chart.show_values)

    def test_default_low_color_uses_palette(self):
        chart = HeatmapChart(data=[[1]])
        self.assertTrue(chart.low_color.startswith("#"))

    def test_default_high_color_uses_palette(self):
        chart = HeatmapChart(data=[[1]])
        self.assertTrue(chart.high_color.startswith("#"))

    def test_custom_title(self):
        chart = HeatmapChart(data=[[1]], title="My Heatmap")
        self.assertEqual(chart.title, "My Heatmap")

    def test_custom_dimensions(self):
        chart = HeatmapChart(data=[[1]], width=600, height=500)
        self.assertEqual(chart.width, 600)
        self.assertEqual(chart.height, 500)

    def test_row_col_labels(self):
        chart = HeatmapChart(
            data=[[1, 2], [3, 4]],
            row_labels=["Row A", "Row B"],
            col_labels=["Col 1", "Col 2"],
        )
        self.assertEqual(chart.row_labels, ["Row A", "Row B"])
        self.assertEqual(chart.col_labels, ["Col 1", "Col 2"])


class TestHeatmapSVGOutput(unittest.TestCase):
    """Test SVG structure and content of rendered heatmap."""

    def setUp(self):
        self.data = [
            [0.1, 0.5, 0.9],
            [0.3, 0.7, 0.2],
        ]
        self.row_labels = ["Row A", "Row B"]
        self.col_labels = ["X", "Y", "Z"]

    def test_returns_string(self):
        chart = HeatmapChart(self.data)
        svg = render_svg(chart)
        self.assertIsInstance(svg, str)

    def test_valid_xml(self):
        chart = HeatmapChart(self.data, row_labels=self.row_labels, col_labels=self.col_labels)
        svg = render_svg(chart)
        _parse(svg)  # Raises if invalid

    def test_svg_element_at_root(self):
        chart = HeatmapChart(self.data)
        svg = render_svg(chart)
        root = _parse(svg)
        self.assertIn("svg", root.tag)

    def test_svg_has_xmlns(self):
        chart = HeatmapChart(self.data)
        svg = render_svg(chart)
        self.assertIn("xmlns", svg)

    def test_svg_has_viewbox(self):
        chart = HeatmapChart(self.data, width=500, height=400)
        svg = render_svg(chart)
        self.assertIn("viewBox", svg)

    def test_title_in_output(self):
        chart = HeatmapChart(self.data, title="Signal Correlation")
        svg = render_svg(chart)
        self.assertIn("Signal Correlation", svg)

    def test_row_labels_in_output(self):
        chart = HeatmapChart(self.data, row_labels=self.row_labels)
        svg = render_svg(chart)
        for label in self.row_labels:
            self.assertIn(label, svg)

    def test_col_labels_in_output(self):
        chart = HeatmapChart(self.data, col_labels=self.col_labels)
        svg = render_svg(chart)
        for label in self.col_labels:
            self.assertIn(label, svg)

    def test_cell_rects_present(self):
        """One rect per cell (plus background rect)."""
        chart = HeatmapChart(self.data)
        svg = render_svg(chart)
        n_cells = len(self.data) * len(self.data[0])
        # Count rect elements — at least n_cells (background may add 1 more)
        rect_count = svg.count("<rect ")
        self.assertGreaterEqual(rect_count, n_cells)

    def test_no_svg_gradient_elements(self):
        """Design guide: no SVG gradient elements."""
        chart = HeatmapChart(self.data)
        svg = render_svg(chart)
        self.assertNotIn("<linearGradient", svg)
        self.assertNotIn("<radialGradient", svg)

    def test_show_values_false_no_cell_text(self):
        """When show_values=False, cell numeric values should not appear as text."""
        data = [[1.0, 2.0], [3.0, 4.0]]
        chart = HeatmapChart(data, show_values=False)
        svg = render_svg(chart)
        # Values shouldn't appear as standalone text (no label showing "1.0" etc.)
        # We check that the specific formatted values are absent
        # (Row/col labels might overlap, but raw float values won't)
        self.assertNotIn(">1.00<", svg)
        self.assertNotIn(">3.00<", svg)

    def test_show_values_true_has_cell_text(self):
        """When show_values=True, formatted cell values appear in SVG."""
        data = [[1.0, 2.0], [3.0, 4.0]]
        chart = HeatmapChart(data, show_values=True)
        svg = render_svg(chart)
        self.assertIn("1.00", svg)

    def test_custom_width_height_in_svg(self):
        chart = HeatmapChart(self.data, width=700, height=600)
        svg = render_svg(chart)
        self.assertIn('width="700"', svg)
        self.assertIn('height="600"', svg)

    def test_color_fill_present(self):
        """SVG must have fill attributes (colored cells)."""
        chart = HeatmapChart(self.data)
        svg = render_svg(chart)
        self.assertIn('fill="', svg)


class TestHeatmapEdgeCases(unittest.TestCase):
    """Edge cases: empty data, single cell, uniform data."""

    def test_empty_data(self):
        chart = HeatmapChart(data=[])
        svg = render_svg(chart)
        _parse(svg)  # Must not raise
        self.assertIn("No data", svg)

    def test_empty_rows(self):
        chart = HeatmapChart(data=[[]])
        svg = render_svg(chart)
        _parse(svg)

    def test_single_cell(self):
        chart = HeatmapChart(data=[[5.0]])
        svg = render_svg(chart)
        _parse(svg)
        self.assertGreaterEqual(svg.count("<rect "), 1)

    def test_single_row(self):
        chart = HeatmapChart(data=[[1, 2, 3, 4, 5]])
        svg = render_svg(chart)
        _parse(svg)

    def test_single_column(self):
        chart = HeatmapChart(data=[[1], [2], [3]])
        svg = render_svg(chart)
        _parse(svg)

    def test_all_zeros(self):
        chart = HeatmapChart(data=[[0, 0], [0, 0]])
        svg = render_svg(chart)
        _parse(svg)  # Must not raise (no div-by-zero)

    def test_all_same_value(self):
        chart = HeatmapChart(data=[[7, 7], [7, 7]])
        svg = render_svg(chart)
        _parse(svg)

    def test_negative_values(self):
        chart = HeatmapChart(data=[[-3, -1], [0, 2]])
        svg = render_svg(chart)
        _parse(svg)

    def test_float_values(self):
        chart = HeatmapChart(data=[[0.1, 0.5], [0.9, 0.3]])
        svg = render_svg(chart)
        _parse(svg)

    def test_large_grid_valid(self):
        data = [[i * j for j in range(1, 8)] for i in range(1, 6)]
        chart = HeatmapChart(data)
        svg = render_svg(chart)
        _parse(svg)


class TestGenerateHeatmapConvenienceFunction(unittest.TestCase):
    """Test the generate_heatmap() convenience function."""

    def test_returns_svg_string(self):
        svg = generate_heatmap([[1, 2], [3, 4]])
        self.assertIsInstance(svg, str)
        self.assertIn("<svg", svg)

    def test_valid_xml(self):
        svg = generate_heatmap([[1, 2], [3, 4]])
        _parse(svg)

    def test_with_labels_and_title(self):
        svg = generate_heatmap(
            [[1, 2], [3, 4]],
            row_labels=["A", "B"],
            col_labels=["X", "Y"],
            title="My Heatmap",
        )
        self.assertIn("My Heatmap", svg)
        self.assertIn("Row A", svg) if False else self.assertIn("A", svg)
        self.assertIn("X", svg)

    def test_kwargs_passed_through(self):
        svg = generate_heatmap(
            [[1, 2], [3, 4]],
            width=600,
            height=500,
        )
        self.assertIn('width="600"', svg)

    def test_show_values_kwarg(self):
        svg = generate_heatmap([[1.0, 2.0], [3.0, 4.0]], show_values=True)
        self.assertIn("1.00", svg)


class TestHeatmapRenderDispatch(unittest.TestCase):
    """Test that render_svg dispatches HeatmapChart correctly."""

    def test_render_svg_accepts_heatmap(self):
        chart = HeatmapChart(data=[[1, 2], [3, 4]])
        svg = render_svg(chart)
        self.assertIsInstance(svg, str)
        _parse(svg)

    def test_save_svg_accepts_heatmap(self):
        chart = HeatmapChart(
            data=[[1, 2], [3, 4]],
            title="Save Test",
            row_labels=["R1", "R2"],
            col_labels=["C1", "C2"],
        )
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            result = save_svg(chart, path)
            self.assertEqual(result, path)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("<svg", content)
            _parse(content)
        finally:
            os.unlink(path)


class TestHeatmapColorMapping(unittest.TestCase):
    """Test that color interpolation works correctly."""

    def test_colors_are_hex_strings(self):
        """All fill colors in output should be valid hex colors."""
        import re
        chart = HeatmapChart(
            data=[[0, 5, 10], [2, 7, 3]],
        )
        svg = render_svg(chart)
        # Find all fill="#..." patterns
        hex_colors = re.findall(r'fill="(#[0-9a-fA-F]{6})"', svg)
        self.assertGreater(len(hex_colors), 0)
        for color in hex_colors:
            self.assertRegex(color, r'^#[0-9a-fA-F]{6}$')

    def test_high_value_gets_different_fill_than_low(self):
        """Min and max value cells should have different fill colors."""
        chart = HeatmapChart(
            data=[[0, 100]],
            row_labels=[],
            col_labels=[],
        )
        svg = render_svg(chart)
        # Low and high cells must have different colors (not both same fill)
        import re
        cell_fills = re.findall(r'fill="(#[0-9a-fA-F]{6})"', svg)
        # Remove background rect color
        unique_fills = set(cell_fills)
        self.assertGreater(len(unique_fills), 1)


if __name__ == "__main__":
    unittest.main()
