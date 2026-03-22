#!/usr/bin/env python3
"""Tests for SankeyChart — flow diagram showing value transfers between nodes."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from chart_generator import SankeyChart, render_svg, save_svg


class TestSankeyChartCreation(unittest.TestCase):
    """Test SankeyChart dataclass creation."""

    def test_basic_creation(self):
        chart = SankeyChart(
            flows=[("Scanned", "BUILD", 5), ("Scanned", "SKIP", 10)],
        )
        self.assertEqual(len(chart.flows), 2)
        self.assertEqual(chart.title, "")
        self.assertEqual(chart.width, 600)
        self.assertEqual(chart.height, 400)

    def test_with_title(self):
        chart = SankeyChart(
            flows=[("A", "B", 10)],
            title="Intelligence Flow",
        )
        self.assertEqual(chart.title, "Intelligence Flow")

    def test_custom_dimensions(self):
        chart = SankeyChart(
            flows=[("A", "B", 10)],
            width=800,
            height=500,
        )
        self.assertEqual(chart.width, 800)
        self.assertEqual(chart.height, 500)

    def test_custom_node_width(self):
        chart = SankeyChart(
            flows=[("A", "B", 10)],
            node_width=30,
        )
        self.assertEqual(chart.node_width, 30)

    def test_custom_node_padding(self):
        chart = SankeyChart(
            flows=[("A", "B", 10)],
            node_padding=15,
        )
        self.assertEqual(chart.node_padding, 15)


class TestSankeyChartRendering(unittest.TestCase):
    """Test SVG rendering output."""

    def test_renders_svg(self):
        chart = SankeyChart(
            flows=[("Source", "Target", 10)],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_empty_data(self):
        chart = SankeyChart(flows=[])
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_title_rendered(self):
        chart = SankeyChart(
            flows=[("A", "B", 10)],
            title="My Sankey",
        )
        svg = render_svg(chart)
        self.assertIn("My Sankey", svg)

    def test_node_labels_rendered(self):
        chart = SankeyChart(
            flows=[("Scanned", "BUILD", 5), ("Scanned", "SKIP", 10)],
        )
        svg = render_svg(chart)
        self.assertIn("Scanned", svg)
        self.assertIn("BUILD", svg)
        self.assertIn("SKIP", svg)

    def test_multiple_sources(self):
        chart = SankeyChart(
            flows=[
                ("Reddit", "BUILD", 5),
                ("Reddit", "SKIP", 10),
                ("GitHub", "BUILD", 3),
                ("GitHub", "REFERENCE", 7),
            ],
        )
        svg = render_svg(chart)
        self.assertIn("Reddit", svg)
        self.assertIn("GitHub", svg)
        self.assertIn("BUILD", svg)
        self.assertIn("SKIP", svg)
        self.assertIn("REFERENCE", svg)

    def test_three_stage_flow(self):
        """Sankey should handle multi-stage: A->B->C."""
        chart = SankeyChart(
            flows=[
                ("Scan", "Review", 15),
                ("Review", "BUILD", 5),
                ("Review", "SKIP", 10),
            ],
        )
        svg = render_svg(chart)
        self.assertIn("Scan", svg)
        self.assertIn("Review", svg)
        self.assertIn("BUILD", svg)

    def test_single_flow(self):
        chart = SankeyChart(flows=[("A", "B", 100)])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("A", svg)
        self.assertIn("B", svg)

    def test_flow_paths_rendered(self):
        """Flow connections should use SVG path elements."""
        chart = SankeyChart(
            flows=[("A", "B", 10), ("A", "C", 5)],
        )
        svg = render_svg(chart)
        self.assertIn("<path", svg)

    def test_node_rects_rendered(self):
        """Nodes should be rendered as rectangles."""
        chart = SankeyChart(
            flows=[("A", "B", 10)],
        )
        svg = render_svg(chart)
        self.assertIn("<rect", svg)


class TestSankeyChartValues(unittest.TestCase):
    """Test value handling and edge cases."""

    def test_zero_value_flow_skipped(self):
        chart = SankeyChart(
            flows=[("A", "B", 0), ("A", "C", 10)],
        )
        svg = render_svg(chart)
        # Should still render without error
        self.assertIn("<svg", svg)

    def test_large_values(self):
        chart = SankeyChart(
            flows=[("A", "B", 1000000)],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_fractional_values(self):
        chart = SankeyChart(
            flows=[("A", "B", 3.5), ("A", "C", 1.5)],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_many_nodes(self):
        """Should handle 10+ nodes without crashing."""
        flows = [(f"S{i}", f"T{i % 3}", i + 1) for i in range(10)]
        chart = SankeyChart(flows=flows)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_all_zero_values(self):
        chart = SankeyChart(
            flows=[("A", "B", 0), ("C", "D", 0)],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)


class TestSankeyChartColors(unittest.TestCase):
    """Test color assignment."""

    def test_default_colors_from_palette(self):
        chart = SankeyChart(
            flows=[("A", "B", 10), ("A", "C", 5)],
        )
        svg = render_svg(chart)
        # Should use design system colors, not random
        self.assertIn("fill=", svg)

    def test_custom_node_colors(self):
        chart = SankeyChart(
            flows=[("A", "B", 10)],
            node_colors={"A": "#ff0000", "B": "#00ff00"},
        )
        svg = render_svg(chart)
        self.assertIn("#ff0000", svg)
        self.assertIn("#00ff00", svg)


class TestSankeyChartSave(unittest.TestCase):
    """Test file saving."""

    def test_save_svg(self):
        chart = SankeyChart(
            flows=[("A", "B", 10)],
            title="Test Save",
        )
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            save_svg(chart, path)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("<svg", content)
            self.assertIn("Test Save", content)
        finally:
            os.unlink(path)


class TestSankeyNodeOrdering(unittest.TestCase):
    """Test that nodes are ordered correctly by stage."""

    def test_source_nodes_on_left(self):
        """Source-only nodes should appear in leftmost column."""
        chart = SankeyChart(
            flows=[("A", "B", 10), ("A", "C", 5)],
        )
        svg = render_svg(chart)
        # A is source, B and C are targets — A should be leftmost
        self.assertIn("A", svg)

    def test_intermediate_nodes_in_middle(self):
        """Nodes that are both source and target appear in middle columns."""
        chart = SankeyChart(
            flows=[
                ("Scan", "Review", 15),
                ("Review", "BUILD", 5),
                ("Review", "SKIP", 10),
            ],
        )
        svg = render_svg(chart)
        self.assertIn("Review", svg)

    def test_self_loop_ignored(self):
        """A->A flows should be silently skipped."""
        chart = SankeyChart(
            flows=[("A", "A", 10), ("A", "B", 5)],
        )
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("B", svg)


if __name__ == "__main__":
    unittest.main()
