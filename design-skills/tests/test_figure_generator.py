#!/usr/bin/env python3
"""Tests for figure_generator.py — MT-32 Phase 6: Figure/image generation pipeline.

Tests multi-panel figure composition, annotations, panel labels, shared legends,
and SVG export.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chart_generator import BarChart, LineChart, DonutChart, ScatterPlot
from figure_generator import (
    Figure,
    FigurePanel,
    Annotation,
    ArrowAnnotation,
    TextAnnotation,
    HighlightAnnotation,
    render_figure,
    save_figure,
)


class TestFigurePanel(unittest.TestCase):
    """Test individual panel creation."""

    def test_panel_with_chart(self):
        chart = BarChart(data=[("A", 10), ("B", 20)], title="Test")
        panel = FigurePanel(chart=chart, label="a")
        self.assertEqual(panel.label, "a")
        self.assertIs(panel.chart, chart)

    def test_panel_default_label(self):
        chart = BarChart(data=[("A", 10)], title="Test")
        panel = FigurePanel(chart=chart)
        self.assertIsNone(panel.label)

    def test_panel_with_caption(self):
        chart = BarChart(data=[("A", 10)], title="Test")
        panel = FigurePanel(chart=chart, label="a", caption="Test counts")
        self.assertEqual(panel.caption, "Test counts")

    def test_panel_custom_size(self):
        chart = BarChart(data=[("A", 10)], title="Test")
        panel = FigurePanel(chart=chart, width=300, height=200)
        self.assertEqual(panel.width, 300)
        self.assertEqual(panel.height, 200)


class TestFigureCreation(unittest.TestCase):
    """Test Figure object creation and layout."""

    def test_single_panel_figure(self):
        chart = BarChart(data=[("A", 10), ("B", 20)], title="Test")
        fig = Figure(panels=[FigurePanel(chart=chart, label="a")])
        self.assertEqual(len(fig.panels), 1)

    def test_multi_panel_figure(self):
        panels = [
            FigurePanel(chart=BarChart(data=[("A", 10)], title="Bar"), label="a"),
            FigurePanel(chart=LineChart(data=[("x", 1), ("y", 2), ("z", 3)], title="Line"), label="b"),
        ]
        fig = Figure(panels=panels, title="Multi-panel")
        self.assertEqual(len(fig.panels), 2)
        self.assertEqual(fig.title, "Multi-panel")

    def test_figure_grid_layout_1x2(self):
        panels = [
            FigurePanel(chart=BarChart(data=[("A", 10)], title="1"), label="a"),
            FigurePanel(chart=BarChart(data=[("B", 20)], title="2"), label="b"),
        ]
        fig = Figure(panels=panels, cols=2)
        self.assertEqual(fig.cols, 2)

    def test_figure_grid_layout_2x2(self):
        panels = [
            FigurePanel(chart=BarChart(data=[("A", i)], title=str(i)), label=chr(97 + i))
            for i in range(4)
        ]
        fig = Figure(panels=panels, cols=2)
        self.assertEqual(fig.cols, 2)
        self.assertEqual(len(fig.panels), 4)

    def test_figure_grid_layout_3x1(self):
        panels = [
            FigurePanel(chart=BarChart(data=[("A", i)], title=str(i)), label=chr(97 + i))
            for i in range(3)
        ]
        fig = Figure(panels=panels, cols=1)
        self.assertEqual(fig.cols, 1)

    def test_figure_auto_cols(self):
        """Default cols=None should auto-detect: 1 panel=1col, 2=2, 3=2, 4=2."""
        fig1 = Figure(panels=[FigurePanel(chart=BarChart(data=[("A", 1)], title="1"))])
        self.assertEqual(fig1._effective_cols(), 1)

        panels2 = [FigurePanel(chart=BarChart(data=[("A", 1)], title=str(i))) for i in range(2)]
        fig2 = Figure(panels=panels2)
        self.assertEqual(fig2._effective_cols(), 2)

        panels4 = [FigurePanel(chart=BarChart(data=[("A", 1)], title=str(i))) for i in range(4)]
        fig4 = Figure(panels=panels4)
        self.assertEqual(fig4._effective_cols(), 2)

    def test_figure_title(self):
        fig = Figure(
            panels=[FigurePanel(chart=BarChart(data=[("A", 10)], title="1"))],
            title="Figure 1: Test Growth",
        )
        self.assertEqual(fig.title, "Figure 1: Test Growth")


class TestRenderFigure(unittest.TestCase):
    """Test SVG rendering of figures."""

    def test_render_single_panel(self):
        chart = BarChart(data=[("A", 10), ("B", 20)], title="Test")
        fig = Figure(panels=[FigurePanel(chart=chart, label="a")])
        svg = render_figure(fig)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_render_contains_panel_label(self):
        chart = BarChart(data=[("A", 10)], title="Test")
        fig = Figure(panels=[FigurePanel(chart=chart, label="a")])
        svg = render_figure(fig)
        self.assertIn("(a)", svg)

    def test_render_multi_panel_contains_all_labels(self):
        panels = [
            FigurePanel(chart=BarChart(data=[("A", 10)], title="1"), label="a"),
            FigurePanel(chart=BarChart(data=[("B", 20)], title="2"), label="b"),
        ]
        fig = Figure(panels=panels, cols=2)
        svg = render_figure(fig)
        self.assertIn("(a)", svg)
        self.assertIn("(b)", svg)

    def test_render_contains_figure_title(self):
        fig = Figure(
            panels=[FigurePanel(chart=BarChart(data=[("A", 10)], title="1"))],
            title="Figure 1: Overview",
        )
        svg = render_figure(fig)
        self.assertIn("Figure 1: Overview", svg)

    def test_render_contains_caption(self):
        panel = FigurePanel(
            chart=BarChart(data=[("A", 10)], title="1"),
            label="a",
            caption="Test counts by session",
        )
        fig = Figure(panels=[panel])
        svg = render_figure(fig)
        self.assertIn("Test counts by session", svg)

    def test_render_2x2_grid(self):
        panels = [
            FigurePanel(chart=BarChart(data=[("A", i * 10)], title=f"P{i}"), label=chr(97 + i))
            for i in range(4)
        ]
        fig = Figure(panels=panels, cols=2)
        svg = render_figure(fig)
        # Should contain all 4 panel labels
        for i in range(4):
            self.assertIn(f"({chr(97 + i)})", svg)

    def test_render_mixed_chart_types(self):
        panels = [
            FigurePanel(chart=BarChart(data=[("A", 10)], title="Bar"), label="a"),
            FigurePanel(chart=DonutChart(data=[("X", 60, "#0f3460"), ("Y", 40, "#e94560")], title="Donut"), label="b"),
        ]
        fig = Figure(panels=panels, cols=2)
        svg = render_figure(fig)
        self.assertIn("<svg", svg)
        self.assertIn("(a)", svg)
        self.assertIn("(b)", svg)

    def test_render_valid_svg(self):
        """Output should be valid SVG (has xmlns, viewBox)."""
        chart = BarChart(data=[("A", 10)], title="T")
        fig = Figure(panels=[FigurePanel(chart=chart)])
        svg = render_figure(fig)
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', svg)
        self.assertIn("viewBox=", svg)

    def test_render_panel_without_label(self):
        """Panels without labels should not have (None) in SVG."""
        chart = BarChart(data=[("A", 10)], title="T")
        fig = Figure(panels=[FigurePanel(chart=chart)])
        svg = render_figure(fig)
        self.assertNotIn("(None)", svg)

    def test_render_with_custom_panel_size(self):
        panel = FigurePanel(chart=BarChart(data=[("A", 10)], title="T"), width=400, height=300)
        fig = Figure(panels=[panel])
        svg = render_figure(fig)
        self.assertIn("<svg", svg)


class TestAnnotations(unittest.TestCase):
    """Test figure annotation support."""

    def test_text_annotation(self):
        ann = TextAnnotation(x=100, y=50, text="Peak value")
        self.assertEqual(ann.text, "Peak value")
        self.assertEqual(ann.x, 100)
        self.assertEqual(ann.y, 50)

    def test_arrow_annotation(self):
        ann = ArrowAnnotation(x1=50, y1=50, x2=100, y2=100, text="Important")
        self.assertEqual(ann.text, "Important")
        self.assertEqual(ann.x1, 50)
        self.assertEqual(ann.x2, 100)

    def test_highlight_annotation(self):
        ann = HighlightAnnotation(x=50, y=50, width=100, height=80, color="#e94560")
        self.assertEqual(ann.width, 100)
        self.assertEqual(ann.color, "#e94560")

    def test_figure_with_annotations(self):
        chart = BarChart(data=[("A", 10), ("B", 20)], title="Test")
        fig = Figure(
            panels=[FigurePanel(chart=chart, label="a")],
            annotations=[TextAnnotation(x=200, y=30, text="Key finding")],
        )
        self.assertEqual(len(fig.annotations), 1)

    def test_render_text_annotation(self):
        chart = BarChart(data=[("A", 10)], title="T")
        fig = Figure(
            panels=[FigurePanel(chart=chart)],
            annotations=[TextAnnotation(x=200, y=30, text="Note here")],
        )
        svg = render_figure(fig)
        self.assertIn("Note here", svg)

    def test_render_arrow_annotation(self):
        chart = BarChart(data=[("A", 10)], title="T")
        fig = Figure(
            panels=[FigurePanel(chart=chart)],
            annotations=[ArrowAnnotation(x1=50, y1=50, x2=150, y2=100, text="Trend")],
        )
        svg = render_figure(fig)
        self.assertIn("Trend", svg)
        # Arrow should have a line element
        self.assertIn("<line", svg)

    def test_render_highlight_annotation(self):
        chart = BarChart(data=[("A", 10)], title="T")
        fig = Figure(
            panels=[FigurePanel(chart=chart)],
            annotations=[HighlightAnnotation(x=50, y=50, width=100, height=80)],
        )
        svg = render_figure(fig)
        # Should have a rect for the highlight
        self.assertIn("opacity", svg)

    def test_panel_level_annotations(self):
        """Annotations can be attached to individual panels."""
        chart = BarChart(data=[("A", 10)], title="T")
        panel = FigurePanel(
            chart=chart,
            label="a",
            annotations=[TextAnnotation(x=50, y=50, text="Panel note")],
        )
        fig = Figure(panels=[panel])
        svg = render_figure(fig)
        self.assertIn("Panel note", svg)

    def test_multiple_annotations(self):
        chart = BarChart(data=[("A", 10)], title="T")
        fig = Figure(
            panels=[FigurePanel(chart=chart)],
            annotations=[
                TextAnnotation(x=100, y=30, text="Note 1"),
                TextAnnotation(x=200, y=30, text="Note 2"),
            ],
        )
        svg = render_figure(fig)
        self.assertIn("Note 1", svg)
        self.assertIn("Note 2", svg)


class TestSaveFigure(unittest.TestCase):
    """Test figure export to file."""

    def test_save_svg(self):
        chart = BarChart(data=[("A", 10), ("B", 20)], title="Test")
        fig = Figure(panels=[FigurePanel(chart=chart, label="a")])
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            result = save_figure(fig, path)
            self.assertEqual(result, path)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("<svg", content)
        finally:
            os.unlink(path)

    def test_save_creates_parent_dirs(self):
        chart = BarChart(data=[("A", 10)], title="T")
        fig = Figure(panels=[FigurePanel(chart=chart)])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub", "fig.svg")
            result = save_figure(fig, path)
            self.assertTrue(os.path.exists(path))

    def test_save_multi_panel(self):
        panels = [
            FigurePanel(chart=BarChart(data=[("A", 10)], title="1"), label="a"),
            FigurePanel(chart=BarChart(data=[("B", 20)], title="2"), label="b"),
        ]
        fig = Figure(panels=panels, cols=2, title="Multi")
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            save_figure(fig, path)
            with open(path) as f:
                content = f.read()
            self.assertIn("(a)", content)
            self.assertIn("(b)", content)
            self.assertIn("Multi", content)
        finally:
            os.unlink(path)


class TestFigureEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_empty_panels_raises(self):
        with self.assertRaises(ValueError):
            Figure(panels=[])

    def test_single_panel_no_label_no_title(self):
        chart = BarChart(data=[("A", 10)], title="T")
        fig = Figure(panels=[FigurePanel(chart=chart)])
        svg = render_figure(fig)
        self.assertIn("<svg", svg)

    def test_large_grid_6_panels(self):
        panels = [
            FigurePanel(chart=BarChart(data=[("A", i)], title=str(i)), label=chr(97 + i))
            for i in range(6)
        ]
        fig = Figure(panels=panels, cols=3)
        svg = render_figure(fig)
        for i in range(6):
            self.assertIn(f"({chr(97 + i)})", svg)

    def test_figure_padding(self):
        fig = Figure(
            panels=[FigurePanel(chart=BarChart(data=[("A", 10)], title="T"))],
            padding=30,
        )
        self.assertEqual(fig.padding, 30)

    def test_annotation_font_size(self):
        ann = TextAnnotation(x=100, y=50, text="Big", font_size=16)
        self.assertEqual(ann.font_size, 16)

    def test_annotation_color(self):
        ann = TextAnnotation(x=100, y=50, text="Red", color="#e94560")
        self.assertEqual(ann.color, "#e94560")

    def test_arrow_annotation_defaults(self):
        ann = ArrowAnnotation(x1=0, y1=0, x2=100, y2=100)
        self.assertIsNone(ann.text)

    def test_highlight_default_color(self):
        ann = HighlightAnnotation(x=0, y=0, width=100, height=100)
        # Should have a default highlight color
        self.assertIsNotNone(ann.color)


if __name__ == "__main__":
    unittest.main()
