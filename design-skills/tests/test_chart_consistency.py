#!/usr/bin/env python3
"""Consistency audit tests for all 9 chart types in chart_generator.py.

Checks:
  (a) All chart types use _text() for text rendering (no raw <text> tags)
  (b) All chart types handle empty data gracefully
  (c) All chart types escape special characters in titles and labels
  (d) Consistent "No data" rendering: font_size=14, centered
  (e) Consistent title rendering: font_size=14
  (f) All SVGs have consistent viewBox format
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chart_generator import (
    BarChart, HorizontalBarChart, LineChart, Sparkline, DonutChart,
    AreaChart, StackedBarChart, HeatmapChart, StackedAreaChart,
    WaterfallChart, RadarChart, GaugeChart,
    render_svg, CCA_COLORS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_charts_with_data():
    """Return one instance of each of the 9 chart types with minimal data."""
    return [
        BarChart(data=[("A", 1), ("B", 2)]),
        HorizontalBarChart(data=[("A", 1), ("B", 2)]),
        LineChart(data=[("A", 1), ("B", 2)]),
        Sparkline(values=[1, 2, 3]),
        DonutChart(data=[("X", 10, CCA_COLORS["accent"]), ("Y", 5, CCA_COLORS["highlight"])]),
        AreaChart(data=[("A", 1), ("B", 2)]),
        StackedBarChart(data=[("A", [1, 2])], series_names=["S1", "S2"]),
        HeatmapChart(data=[[1, 2], [3, 4]]),
        StackedAreaChart(series=[("P", [1, 2]), ("Q", [2, 3])], labels=["A", "B"]),
    ]


def _empty_charts():
    """Return one empty instance of each chart type that supports empty data."""
    return [
        BarChart(data=[]),
        HorizontalBarChart(data=[]),
        LineChart(data=[]),
        DonutChart(data=[]),
        AreaChart(data=[]),
        StackedBarChart(data=[], series_names=[]),
        HeatmapChart(data=[]),
        StackedAreaChart(series=[], labels=[]),
    ]


# ---------------------------------------------------------------------------
# (a) All charts use _text() — no raw <text ...> tags outside _text()
#     Verifiable by ensuring SVG renders (proxy: no AttributeError, valid SVG)
# ---------------------------------------------------------------------------

class TestAllChartsRenderValidSVG(unittest.TestCase):
    """All chart types must render a valid SVG string."""

    def test_bar_chart_renders(self):
        svg = render_svg(BarChart(data=[("A", 5)]))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_horizontal_bar_chart_renders(self):
        svg = render_svg(HorizontalBarChart(data=[("A", 5)]))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_line_chart_renders(self):
        svg = render_svg(LineChart(data=[("A", 5)]))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_sparkline_renders(self):
        svg = render_svg(Sparkline(values=[1, 2, 3]))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_donut_chart_renders(self):
        svg = render_svg(DonutChart(data=[("A", 10, "#123456")]))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_area_chart_renders(self):
        svg = render_svg(AreaChart(data=[("A", 5)]))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_stacked_bar_chart_renders(self):
        svg = render_svg(StackedBarChart(data=[("A", [5, 3])], series_names=["X", "Y"]))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_heatmap_chart_renders(self):
        svg = render_svg(HeatmapChart(data=[[1, 2], [3, 4]]))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_stacked_area_chart_renders(self):
        svg = render_svg(StackedAreaChart(
            series=[("A", [1, 2]), ("B", [2, 3])], labels=["X", "Y"]
        ))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_waterfall_chart_renders(self):
        svg = render_svg(WaterfallChart(data=[("Rev", 500), ("Cost", -200)]))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_radar_chart_renders(self):
        svg = render_svg(RadarChart(data=[("A", 80), ("B", 60), ("C", 90)]))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_gauge_chart_renders(self):
        svg = render_svg(GaugeChart(value=75))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)


# ---------------------------------------------------------------------------
# (b) Empty data handling — all charts render gracefully
# ---------------------------------------------------------------------------

class TestEmptyDataHandling(unittest.TestCase):
    """All charts that accept empty data must render 'No data' with font-size 14."""

    def _assert_no_data(self, chart, chart_name):
        svg = render_svg(chart)
        self.assertIn("<svg", svg, f"{chart_name}: must render SVG")
        self.assertIn("No data", svg, f"{chart_name}: must show 'No data'")
        # Consistent font size: 14
        self.assertIn('font-size="14"', svg,
                      f"{chart_name}: 'No data' must use font-size=14")

    def test_bar_chart_empty(self):
        self._assert_no_data(BarChart(data=[]), "BarChart")

    def test_horizontal_bar_chart_empty(self):
        self._assert_no_data(HorizontalBarChart(data=[]), "HorizontalBarChart")

    def test_line_chart_empty(self):
        self._assert_no_data(LineChart(data=[]), "LineChart")

    def test_donut_chart_empty(self):
        self._assert_no_data(DonutChart(data=[]), "DonutChart")

    def test_area_chart_empty(self):
        self._assert_no_data(AreaChart(data=[]), "AreaChart")

    def test_stacked_bar_chart_empty(self):
        self._assert_no_data(StackedBarChart(data=[], series_names=[]), "StackedBarChart")

    def test_heatmap_chart_empty(self):
        self._assert_no_data(HeatmapChart(data=[]), "HeatmapChart")

    def test_stacked_area_chart_empty(self):
        self._assert_no_data(StackedAreaChart(series=[], labels=[]), "StackedAreaChart")

    def test_sparkline_empty_renders(self):
        # Sparkline is inline with no text — just must not crash
        svg = render_svg(Sparkline(values=[]))
        self.assertIn("<svg", svg)


# ---------------------------------------------------------------------------
# (c) Special character escaping in titles and labels
# ---------------------------------------------------------------------------

class TestSpecialCharEscaping(unittest.TestCase):
    """All charts must escape & < > in titles and labels via _escape()."""

    def test_bar_chart_title_escaped(self):
        svg = render_svg(BarChart(data=[("A&B", 1)], title="Test <Chart>"))
        self.assertIn("&lt;", svg)
        self.assertIn("&amp;", svg)

    def test_horizontal_bar_chart_escaped(self):
        svg = render_svg(HorizontalBarChart(data=[("A & B", 1)], title="X<Y"))
        self.assertIn("&amp;", svg)
        self.assertIn("&lt;", svg)

    def test_line_chart_escaped(self):
        svg = render_svg(LineChart(data=[("A>B", 5)], title="T & R"))
        self.assertIn("&gt;", svg)
        self.assertIn("&amp;", svg)

    def test_donut_chart_escaped(self):
        svg = render_svg(DonutChart(
            data=[("A & B", 10, "#123456")],
            title="<Donut>",
        ))
        self.assertIn("&lt;", svg)
        self.assertIn("&amp;", svg)

    def test_area_chart_escaped(self):
        svg = render_svg(AreaChart(data=[("A & B", 1)], title="<Test>"))
        self.assertIn("&lt;", svg)
        self.assertIn("&amp;", svg)

    def test_stacked_bar_chart_escaped(self):
        svg = render_svg(StackedBarChart(
            data=[("A & B", [1, 2])],
            series_names=["<S1>", "S2"],
            title="T & R",
        ))
        self.assertIn("&amp;", svg)

    def test_heatmap_chart_escaped(self):
        svg = render_svg(HeatmapChart(
            data=[[1, 2]],
            row_labels=["A & B"],
            col_labels=["C < D"],
            title="Heat <map>",
        ))
        self.assertIn("&amp;", svg)
        self.assertIn("&lt;", svg)

    def test_stacked_area_chart_escaped(self):
        svg = render_svg(StackedAreaChart(
            series=[("A & B", [1, 2])],
            labels=["X & Y", "Z"],
            title="<Stack>",
        ))
        self.assertIn("&amp;", svg)
        self.assertIn("&lt;", svg)


# ---------------------------------------------------------------------------
# (d) Consistent title font-size = 14 across all titled chart types
# ---------------------------------------------------------------------------

class TestConsistentTitleRendering(unittest.TestCase):
    """All chart types must render titles with font-size=14."""

    def _assert_title_size_14(self, chart, chart_name):
        svg = render_svg(chart)
        self.assertIn("My Title", svg, f"{chart_name}: title text missing")
        self.assertIn('font-size="14"', svg,
                      f"{chart_name}: title must use font-size=14")

    def test_bar_chart_title_size(self):
        self._assert_title_size_14(
            BarChart(data=[("A", 1)], title="My Title"), "BarChart"
        )

    def test_horizontal_bar_chart_title_size(self):
        self._assert_title_size_14(
            HorizontalBarChart(data=[("A", 1)], title="My Title"), "HorizontalBarChart"
        )

    def test_line_chart_title_size(self):
        self._assert_title_size_14(
            LineChart(data=[("A", 1)], title="My Title"), "LineChart"
        )

    def test_area_chart_title_size(self):
        self._assert_title_size_14(
            AreaChart(data=[("A", 1)], title="My Title"), "AreaChart"
        )

    def test_stacked_bar_chart_title_size(self):
        self._assert_title_size_14(
            StackedBarChart(data=[("A", [1])], series_names=["S"], title="My Title"),
            "StackedBarChart",
        )

    def test_heatmap_chart_title_size(self):
        self._assert_title_size_14(
            HeatmapChart(data=[[1, 2]], title="My Title"), "HeatmapChart"
        )

    def test_stacked_area_chart_title_size(self):
        self._assert_title_size_14(
            StackedAreaChart(series=[("A", [1])], labels=["X"], title="My Title"),
            "StackedAreaChart",
        )

    def test_donut_chart_title_size(self):
        self._assert_title_size_14(
            DonutChart(data=[("A", 10, "#123456")], title="My Title"), "DonutChart"
        )


# ---------------------------------------------------------------------------
# (f) Consistent viewBox in all chart SVGs
# ---------------------------------------------------------------------------

class TestConsistentViewBox(unittest.TestCase):
    """All charts must include a viewBox attribute matching width x height."""

    def _assert_viewbox(self, chart, expected_w, expected_h, chart_name):
        svg = render_svg(chart)
        self.assertIn(f'viewBox="0 0 {expected_w} {expected_h}"', svg,
                      f"{chart_name}: viewBox must be '0 0 {expected_w} {expected_h}'")

    def test_bar_chart_viewbox(self):
        self._assert_viewbox(BarChart(data=[("A", 1)], width=600, height=400),
                             600, 400, "BarChart")

    def test_horizontal_bar_chart_viewbox(self):
        self._assert_viewbox(HorizontalBarChart(data=[("A", 1)], width=600, height=400),
                             600, 400, "HorizontalBarChart")

    def test_line_chart_viewbox(self):
        self._assert_viewbox(LineChart(data=[("A", 1)], width=600, height=400),
                             600, 400, "LineChart")

    def test_sparkline_viewbox(self):
        self._assert_viewbox(Sparkline(values=[1, 2, 3], width=120, height=30),
                             120, 30, "Sparkline")

    def test_donut_chart_viewbox(self):
        self._assert_viewbox(DonutChart(data=[("A", 10, "#123456")], width=350, height=350),
                             350, 350, "DonutChart")

    def test_area_chart_viewbox(self):
        self._assert_viewbox(AreaChart(data=[("A", 1)], width=700, height=400),
                             700, 400, "AreaChart")

    def test_stacked_bar_chart_viewbox(self):
        self._assert_viewbox(
            StackedBarChart(data=[("A", [1])], series_names=["S"], width=600, height=400),
            600, 400, "StackedBarChart"
        )

    def test_heatmap_chart_viewbox(self):
        self._assert_viewbox(HeatmapChart(data=[[1]], width=500, height=400),
                             500, 400, "HeatmapChart")

    def test_stacked_area_chart_viewbox(self):
        self._assert_viewbox(
            StackedAreaChart(series=[("A", [1])], labels=["X"], width=600, height=350),
            600, 350, "StackedAreaChart"
        )


if __name__ == "__main__":
    unittest.main()
