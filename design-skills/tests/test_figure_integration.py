"""Tests for figure_generator integration into slides, dashboard, and website — MT-32 Phase 7.

Tests that figure_generator multi-panel figures are properly wired into:
1. slide_generator — build_chart_slide() for SVG chart embedding
2. dashboard_generator — summary figure in _render_charts()
3. website_generator — optional figure support in landing page
"""
import os
import sys
import tempfile
import unittest

# Add parent dir to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chart_generator import BarChart, HorizontalBarChart, DonutChart, render_svg
from figure_generator import (
    Figure, FigurePanel, TextAnnotation, render_figure,
)
from slide_generator import SlideDataCollector, SlideGenerator
from dashboard_generator import DashboardData, DashboardRenderer, ModuleCard, MasterTaskRow, MetricCard
from website_generator import LandingPage, FeatureCard, MetricCard as WebMetricCard


# ── Slide Generator: Chart Slide ─────────────────────────────────────────────


class TestSlideChartSlide(unittest.TestCase):
    """Test build_chart_slide() for embedding SVG charts in slide decks."""

    def setUp(self):
        self.collector = SlideDataCollector(project_root="/tmp/test")
        self.sample_chart = BarChart(data=[("A", 10), ("B", 20)], title="Test")
        self.sample_svg = render_svg(self.sample_chart)

    def test_build_chart_slide_returns_dict(self):
        slide = self.collector.build_chart_slide("Test Chart", self.sample_svg)
        self.assertIsInstance(slide, dict)

    def test_build_chart_slide_type_is_chart(self):
        slide = self.collector.build_chart_slide("Test Chart", self.sample_svg)
        self.assertEqual(slide["type"], "chart")

    def test_build_chart_slide_has_title(self):
        slide = self.collector.build_chart_slide("My Chart Title", self.sample_svg)
        self.assertEqual(slide["title"], "My Chart Title")

    def test_build_chart_slide_has_svg_content(self):
        slide = self.collector.build_chart_slide("Test", self.sample_svg)
        self.assertIn("svg_content", slide)
        self.assertIn("<svg", slide["svg_content"])

    def test_build_chart_slide_has_caption(self):
        slide = self.collector.build_chart_slide("Test", self.sample_svg, caption="Fig 1")
        self.assertEqual(slide["caption"], "Fig 1")

    def test_build_chart_slide_caption_defaults_empty(self):
        slide = self.collector.build_chart_slide("Test", self.sample_svg)
        self.assertEqual(slide["caption"], "")

    def test_build_chart_slide_with_figure(self):
        """Test with a multi-panel figure SVG."""
        fig = Figure(
            panels=[FigurePanel(chart=self.sample_chart, label="a")],
            cols=1, title="Figure 1",
        )
        svg = render_figure(fig)
        slide = self.collector.build_chart_slide("Overview", svg)
        self.assertIn("<svg", slide["svg_content"])
        self.assertEqual(slide["type"], "chart")

    def test_build_chart_slide_in_deck_assembly(self):
        """Chart slides can be assembled into a deck."""
        metadata = self.collector.collect_metadata(title="Test Deck")
        slides = [
            self.collector.build_section_slide("Charts"),
            self.collector.build_chart_slide("Bar Chart", self.sample_svg),
        ]
        deck = self.collector.assemble_deck(metadata, slides)
        self.assertEqual(len(deck["slides"]), 2)
        self.assertEqual(deck["slides"][1]["type"], "chart")

    def test_build_chart_slide_svg_is_preserved_exactly(self):
        """SVG content should be stored as-is, not modified."""
        slide = self.collector.build_chart_slide("Test", self.sample_svg)
        self.assertEqual(slide["svg_content"], self.sample_svg)


class TestSlideChartSlideJSON(unittest.TestCase):
    """Test that chart slides serialize properly for Typst pipeline."""

    def setUp(self):
        self.collector = SlideDataCollector(project_root="/tmp/test")
        self.sample_svg = render_svg(BarChart(data=[("X", 5)], title="T"))

    def test_chart_slide_json_serializable(self):
        """Chart slide data must be JSON-serializable for Typst pipeline."""
        import json
        slide = self.collector.build_chart_slide("Test", self.sample_svg)
        serialized = json.dumps(slide)
        self.assertIsInstance(serialized, str)

    def test_chart_slide_in_full_deck_json(self):
        """Full deck with chart slide must be JSON-serializable."""
        import json
        metadata = self.collector.collect_metadata()
        slides = [self.collector.build_chart_slide("Test", self.sample_svg)]
        deck = self.collector.assemble_deck(metadata, slides)
        serialized = json.dumps(deck)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["slides"][0]["type"], "chart")


# ── Dashboard Generator: Figure Integration ──────────────────────────────────


class TestDashboardFigureSection(unittest.TestCase):
    """Test figure_generator integration in dashboard _render_charts()."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.data = DashboardData(title="Test Dashboard", session_number=99)
        self.data.modules = [
            ModuleCard(name="Memory", path="memory/", status="COMPLETE", tests=340, items="MEM-1-5"),
            ModuleCard(name="Agent Guard", path="agent-guard/", status="ACTIVE", tests=1073, items="AG-1-9"),
            ModuleCard(name="Self-Learning", path="self-learning/", status="ACTIVE", tests=1885, items="MT-7+"),
        ]
        self.data.master_tasks = [
            MasterTaskRow(id="MT-32", name="Design Pipeline", score=12.0, status="Phase 7 IN PROGRESS"),
            MasterTaskRow(id="MT-28", name="EvolveR", score=10.0, status="Phase 6 COMPLETE"),
        ]
        self.data.metrics = [
            MetricCard(label="Tests", value="9393", status="success"),
        ]

    def test_render_charts_includes_figure_section(self):
        """_render_charts should include a summary figure when modules exist."""
        html = self.renderer._render_charts(self.data)
        self.assertIn("chart-card", html)

    def test_render_charts_has_summary_figure(self):
        """Dashboard should include a multi-panel summary figure."""
        html = self.renderer._render_charts(self.data)
        # The summary figure uses figure_generator — should produce SVG with panel labels
        self.assertIn("svg", html.lower())

    def test_render_charts_figure_has_module_data(self):
        """Summary figure should reflect module test data."""
        html = self.renderer._render_charts(self.data)
        # The horizontal bar chart should contain module names
        self.assertIn("Memory", html)

    def test_render_charts_empty_modules_no_figure(self):
        """No figure rendered when modules list is empty."""
        self.data.modules = []
        html = self.renderer._render_charts(self.data)
        self.assertEqual(html, "")

    def test_render_charts_figure_is_valid_svg(self):
        """Figure section should contain valid SVG markup."""
        html = self.renderer._render_charts(self.data)
        self.assertIn("xmlns", html)

    def test_dashboard_render_full_includes_charts_section(self):
        """Full dashboard render includes the Charts section header."""
        html = self.renderer.render(self.data)
        self.assertIn("Charts", html)

    def test_dashboard_figure_alongside_existing_charts(self):
        """Figure should appear alongside existing bar/donut charts."""
        html = self.renderer._render_charts(self.data)
        # Should have both the existing module bar chart and task donut
        svg_count = html.lower().count("<svg")
        self.assertGreaterEqual(svg_count, 2, "Should have at least 2 SVG charts")


class TestDashboardSummaryFigure(unittest.TestCase):
    """Test the dedicated summary figure generation for dashboard."""

    def setUp(self):
        self.renderer = DashboardRenderer()

    def test_generate_dashboard_figure_returns_svg(self):
        modules = [
            ModuleCard(name="Mod A", path="a/", status="COMPLETE", tests=100, items=""),
            ModuleCard(name="Mod B", path="b/", status="ACTIVE", tests=200, items=""),
        ]
        svg = self.renderer._render_summary_figure(modules)
        self.assertIn("<svg", svg)

    def test_generate_dashboard_figure_has_panels(self):
        modules = [
            ModuleCard(name="X", path="x/", status="COMPLETE", tests=50, items=""),
            ModuleCard(name="Y", path="y/", status="ACTIVE", tests=75, items=""),
        ]
        svg = self.renderer._render_summary_figure(modules)
        # Figure should have panel labels
        self.assertIn("(a)", svg)

    def test_generate_dashboard_figure_empty_modules(self):
        svg = self.renderer._render_summary_figure([])
        self.assertEqual(svg, "")

    def test_generate_dashboard_figure_single_module(self):
        modules = [ModuleCard(name="Solo", path="s/", status="ACTIVE", tests=10, items="")]
        svg = self.renderer._render_summary_figure(modules)
        self.assertIn("<svg", svg)


# ── Website Generator: Figure Support ────────────────────────────────────────


class TestWebsiteFigureSupport(unittest.TestCase):
    """Test optional figure/chart embedding in website landing page."""

    def test_landing_page_accepts_figures(self):
        """LandingPage should accept an optional figures list."""
        sample_svg = render_svg(BarChart(data=[("A", 10)], title="T"))
        page = LandingPage(
            title="CCA", tagline="Test", hero_cta_text="Go", hero_cta_url="#",
            figures=[{"title": "Overview", "svg": sample_svg}],
        )
        self.assertEqual(len(page.figures), 1)

    def test_landing_page_figures_default_empty(self):
        page = LandingPage(
            title="CCA", tagline="Test", hero_cta_text="Go", hero_cta_url="#",
        )
        self.assertEqual(len(page.figures), 0)

    def test_render_landing_page_includes_figure_section(self):
        from website_generator import render_landing_page
        sample_svg = render_svg(BarChart(data=[("A", 10)], title="Test"))
        page = LandingPage(
            title="CCA", tagline="Test", hero_cta_text="Go", hero_cta_url="#",
            figures=[{"title": "Overview", "svg": sample_svg}],
        )
        html = render_landing_page(page)
        self.assertIn("Overview", html)
        self.assertIn("<svg", html)

    def test_render_landing_page_no_figures_no_section(self):
        from website_generator import render_landing_page
        page = LandingPage(
            title="CCA", tagline="Test", hero_cta_text="Go", hero_cta_url="#",
        )
        html = render_landing_page(page)
        # Should not have a figures section when none provided
        self.assertNotIn("figure-section", html)

    def test_render_landing_page_multiple_figures(self):
        from website_generator import render_landing_page
        svg1 = render_svg(BarChart(data=[("A", 10)], title="Chart 1"))
        svg2 = render_svg(BarChart(data=[("B", 20)], title="Chart 2"))
        page = LandingPage(
            title="CCA", tagline="Test", hero_cta_text="Go", hero_cta_url="#",
            figures=[
                {"title": "First", "svg": svg1},
                {"title": "Second", "svg": svg2},
            ],
        )
        html = render_landing_page(page)
        self.assertIn("First", html)
        self.assertIn("Second", html)

    def test_render_landing_page_figure_title_escaped(self):
        """Figure titles should be XSS-safe."""
        from website_generator import render_landing_page
        svg = render_svg(BarChart(data=[("A", 1)], title="T"))
        page = LandingPage(
            title="CCA", tagline="Test", hero_cta_text="Go", hero_cta_url="#",
            figures=[{"title": "<script>alert(1)</script>", "svg": svg}],
        )
        html = render_landing_page(page)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_landing_page_figure_with_multi_panel(self):
        """Website should handle multi-panel figure SVGs."""
        chart = BarChart(data=[("A", 10)], title="Panel")
        fig = Figure(
            panels=[FigurePanel(chart=chart, label="a")],
            cols=1, title="Multi-panel",
        )
        svg = render_figure(fig)
        page = LandingPage(
            title="CCA", tagline="Test", hero_cta_text="Go", hero_cta_url="#",
            figures=[{"title": "Summary", "svg": svg}],
        )
        from website_generator import render_landing_page
        html = render_landing_page(page)
        self.assertIn("<svg", html)


if __name__ == "__main__":
    unittest.main()
