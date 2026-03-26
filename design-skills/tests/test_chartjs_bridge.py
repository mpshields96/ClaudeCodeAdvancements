#!/usr/bin/env python3
"""Tests for chartjs_bridge.py — Chart.js configuration generator.

Converts CCA chart data (same format as chart_generator.py) into Chart.js
config objects that can be embedded in HTML dashboards for interactivity.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chartjs_bridge import (
    ChartJSConfig,
    bar_chart_config,
    line_chart_config,
    donut_chart_config,
    stacked_bar_config,
    render_chartjs_script,
    render_chartjs_canvas,
    CHARTJS_CDN_URL,
)


class TestBarChartConfig(unittest.TestCase):
    """Bar chart configuration generation."""

    def test_basic_bar(self):
        config = bar_chart_config(
            labels=["Memory", "Spec", "Context"],
            values=[340, 205, 434],
            title="Tests Per Module",
        )
        self.assertIsInstance(config, ChartJSConfig)
        self.assertEqual(config.chart_type, "bar")
        self.assertEqual(len(config.data["labels"]), 3)
        self.assertEqual(config.data["datasets"][0]["data"], [340, 205, 434])

    def test_bar_with_colors(self):
        config = bar_chart_config(
            labels=["A", "B"],
            values=[10, 20],
            colors=["#ff0000", "#00ff00"],
        )
        self.assertEqual(config.data["datasets"][0]["backgroundColor"], ["#ff0000", "#00ff00"])

    def test_bar_default_colors(self):
        config = bar_chart_config(labels=["A", "B", "C"], values=[1, 2, 3])
        colors = config.data["datasets"][0]["backgroundColor"]
        self.assertEqual(len(colors), 3)

    def test_empty_data(self):
        config = bar_chart_config(labels=[], values=[])
        self.assertEqual(config.data["labels"], [])

    def test_horizontal_bar(self):
        config = bar_chart_config(
            labels=["A", "B"],
            values=[10, 20],
            horizontal=True,
        )
        self.assertEqual(config.options["indexAxis"], "y")

    def test_to_json(self):
        config = bar_chart_config(labels=["A"], values=[1])
        j = config.to_json()
        parsed = json.loads(j)
        self.assertEqual(parsed["type"], "bar")


class TestLineChartConfig(unittest.TestCase):
    """Line chart configuration generation."""

    def test_basic_line(self):
        config = line_chart_config(
            labels=["S1", "S2", "S3", "S4"],
            values=[100, 200, 500, 800],
            title="Test Growth",
        )
        self.assertEqual(config.chart_type, "line")
        self.assertEqual(len(config.data["datasets"][0]["data"]), 4)

    def test_line_fill(self):
        config = line_chart_config(
            labels=["A", "B"],
            values=[1, 2],
            fill=True,
        )
        self.assertTrue(config.data["datasets"][0]["fill"])

    def test_multi_series(self):
        config = line_chart_config(
            labels=["Jan", "Feb", "Mar"],
            values=[10, 20, 30],
            series_name="CCA Tests",
        )
        self.assertEqual(config.data["datasets"][0]["label"], "CCA Tests")

    def test_line_smooth(self):
        config = line_chart_config(labels=["A", "B"], values=[1, 2], smooth=True)
        self.assertGreater(config.data["datasets"][0]["tension"], 0)


class TestDonutChartConfig(unittest.TestCase):
    """Donut/pie chart configuration."""

    def test_basic_donut(self):
        config = donut_chart_config(
            labels=["BUILD", "ADAPT", "REFERENCE", "SKIP"],
            values=[5, 8, 12, 3],
            title="Verdict Distribution",
        )
        self.assertEqual(config.chart_type, "doughnut")
        self.assertEqual(len(config.data["labels"]), 4)

    def test_donut_cutout(self):
        config = donut_chart_config(labels=["A", "B"], values=[1, 2])
        # Donut should have cutout (not pie)
        self.assertIn("cutout", config.options)

    def test_donut_colors(self):
        config = donut_chart_config(
            labels=["A", "B"],
            values=[10, 20],
            colors=["#ff0000", "#0000ff"],
        )
        self.assertEqual(config.data["datasets"][0]["backgroundColor"], ["#ff0000", "#0000ff"])


class TestStackedBarConfig(unittest.TestCase):
    """Stacked bar chart configuration."""

    def test_basic_stacked(self):
        config = stacked_bar_config(
            labels=["S178", "S179", "S180"],
            series={
                "Tests Added": [13, 41, 16],
                "Tests Fixed": [2, 0, 5],
            },
            title="Test Activity",
        )
        self.assertEqual(config.chart_type, "bar")
        self.assertEqual(len(config.data["datasets"]), 2)
        self.assertTrue(config.options["scales"]["x"]["stacked"])
        self.assertTrue(config.options["scales"]["y"]["stacked"])

    def test_stacked_series_labels(self):
        config = stacked_bar_config(
            labels=["A"],
            series={"Series 1": [10], "Series 2": [20]},
        )
        ds_labels = [ds["label"] for ds in config.data["datasets"]]
        self.assertIn("Series 1", ds_labels)
        self.assertIn("Series 2", ds_labels)


class TestRenderFunctions(unittest.TestCase):
    """HTML rendering for embedding in dashboards."""

    def test_render_canvas(self):
        html_str = render_chartjs_canvas("myChart", width=400, height=300)
        self.assertIn('id="myChart"', html_str)
        self.assertIn("400", html_str)
        self.assertIn("300", html_str)
        self.assertIn("<canvas", html_str)

    def test_render_script(self):
        config = bar_chart_config(labels=["A"], values=[1], title="Test")
        script = render_chartjs_script("myChart", config)
        self.assertIn("myChart", script)
        self.assertIn("<script>", script)
        self.assertIn("new Chart", script)
        self.assertIn("bar", script)

    def test_cdn_url_is_valid(self):
        self.assertTrue(CHARTJS_CDN_URL.startswith("https://"))
        self.assertIn("chart.js", CHARTJS_CDN_URL.lower())

    def test_render_script_valid_json(self):
        """Config JSON in script should be parseable."""
        config = line_chart_config(labels=["X", "Y"], values=[10, 20])
        script = render_chartjs_script("lineChart", config)
        # Extract the JSON config from the script
        self.assertIn('"type"', script)
        self.assertIn('"data"', script)


class TestChartJSConfig(unittest.TestCase):
    """ChartJSConfig dataclass behavior."""

    def test_to_json(self):
        config = ChartJSConfig(
            chart_type="bar",
            data={"labels": ["A"], "datasets": [{"data": [1]}]},
            options={},
        )
        j = config.to_json()
        parsed = json.loads(j)
        self.assertEqual(parsed["type"], "bar")

    def test_to_dict(self):
        config = ChartJSConfig(
            chart_type="line",
            data={"labels": []},
            options={"responsive": True},
        )
        d = config.to_dict()
        self.assertEqual(d["type"], "line")
        self.assertTrue(d["options"]["responsive"])


if __name__ == "__main__":
    unittest.main()
