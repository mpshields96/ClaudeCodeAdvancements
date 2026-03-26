#!/usr/bin/env python3
"""chartjs_bridge.py — Chart.js configuration generator for CCA dashboards.

Converts CCA chart data (same data format used by chart_generator.py SVG charts)
into Chart.js config objects embeddable in HTML dashboards for interactivity
(hover tooltips, click events, animations, responsive sizing).

Usage:
    from chartjs_bridge import bar_chart_config, render_chartjs_script, render_chartjs_canvas

    config = bar_chart_config(labels=["A", "B"], values=[10, 20], title="Test")
    html = render_chartjs_canvas("chart1") + render_chartjs_script("chart1", config)

Stdlib only. No external dependencies. One file = one job.
Chart.js itself is loaded via CDN in the HTML output.
"""

import json
from dataclasses import dataclass, field
from typing import Optional

# Chart.js CDN — pinned to v4.4 for stability
CHARTJS_CDN_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"

# CCA color palette (synced with design-guide.md)
CCA_CHART_COLORS = [
    "#0f3460",  # blue (primary)
    "#16c79a",  # green (success)
    "#f59e0b",  # orange (warning)
    "#e94560",  # red (highlight)
    "#5ac8fa",  # teal
    "#636366",  # mid grey
    "#8b5cf6",  # purple
    "#ec4899",  # pink
]


@dataclass
class ChartJSConfig:
    """Chart.js configuration object."""
    chart_type: str
    data: dict
    options: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.chart_type,
            "data": self.data,
            "options": self.options,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


def _default_colors(n: int) -> list[str]:
    """Return n colors cycling through the CCA palette."""
    return [CCA_CHART_COLORS[i % len(CCA_CHART_COLORS)] for i in range(n)]


def _base_options(title: Optional[str] = None, responsive: bool = True) -> dict:
    """Common Chart.js options."""
    opts: dict = {
        "responsive": responsive,
        "maintainAspectRatio": False,
    }
    if title:
        opts["plugins"] = {
            "title": {"display": True, "text": title, "font": {"size": 14}},
            "legend": {"display": False},
        }
    return opts


def bar_chart_config(
    labels: list[str],
    values: list[float],
    title: Optional[str] = None,
    colors: Optional[list[str]] = None,
    horizontal: bool = False,
) -> ChartJSConfig:
    """Generate a bar chart configuration.

    Args:
        labels: Category labels (x-axis for vertical, y-axis for horizontal)
        values: Numeric values per category
        title: Optional chart title
        colors: Optional list of colors (one per bar). Defaults to CCA palette.
        horizontal: If True, renders horizontal bars (indexAxis: 'y')
    """
    if colors is None:
        colors = _default_colors(len(labels))

    data = {
        "labels": labels,
        "datasets": [{
            "data": values,
            "backgroundColor": colors,
            "borderRadius": 4,
        }],
    }

    options = _base_options(title)
    if horizontal:
        options["indexAxis"] = "y"

    return ChartJSConfig(chart_type="bar", data=data, options=options)


def line_chart_config(
    labels: list[str],
    values: list[float],
    title: Optional[str] = None,
    color: Optional[str] = None,
    fill: bool = False,
    smooth: bool = False,
    series_name: Optional[str] = None,
) -> ChartJSConfig:
    """Generate a line chart configuration.

    Args:
        labels: X-axis labels (e.g. session names, dates)
        values: Y-axis values
        title: Optional chart title
        color: Line color. Defaults to CCA blue.
        fill: If True, fill area under the line
        smooth: If True, use bezier curve smoothing
        series_name: Label for the dataset in legend
    """
    if color is None:
        color = CCA_CHART_COLORS[0]

    dataset: dict = {
        "label": series_name or "Value",
        "data": values,
        "borderColor": color,
        "backgroundColor": color + "33",  # 20% opacity for fill
        "fill": fill,
        "tension": 0.3 if smooth else 0,
        "pointRadius": 3,
        "pointHoverRadius": 6,
    }

    data = {"labels": labels, "datasets": [dataset]}
    options = _base_options(title)

    if series_name:
        options.setdefault("plugins", {})["legend"] = {"display": True}

    return ChartJSConfig(chart_type="line", data=data, options=options)


def donut_chart_config(
    labels: list[str],
    values: list[float],
    title: Optional[str] = None,
    colors: Optional[list[str]] = None,
) -> ChartJSConfig:
    """Generate a donut (doughnut) chart configuration.

    Args:
        labels: Segment labels
        values: Segment values
        title: Optional chart title
        colors: Optional colors per segment. Defaults to CCA palette.
    """
    if colors is None:
        colors = _default_colors(len(labels))

    data = {
        "labels": labels,
        "datasets": [{
            "data": values,
            "backgroundColor": colors,
            "borderWidth": 2,
            "borderColor": "#ffffff",
        }],
    }

    options = _base_options(title)
    options["cutout"] = "60%"
    options.setdefault("plugins", {})["legend"] = {
        "display": True,
        "position": "right",
    }

    return ChartJSConfig(chart_type="doughnut", data=data, options=options)


def stacked_bar_config(
    labels: list[str],
    series: dict[str, list[float]],
    title: Optional[str] = None,
    colors: Optional[list[str]] = None,
) -> ChartJSConfig:
    """Generate a stacked bar chart configuration.

    Args:
        labels: X-axis labels
        series: Dict mapping series name -> values list
        title: Optional chart title
        colors: Optional colors per series. Defaults to CCA palette.
    """
    if colors is None:
        colors = _default_colors(len(series))

    datasets = []
    for i, (name, vals) in enumerate(series.items()):
        datasets.append({
            "label": name,
            "data": vals,
            "backgroundColor": colors[i % len(colors)],
            "borderRadius": 2,
        })

    data = {"labels": labels, "datasets": datasets}

    options = _base_options(title)
    options["scales"] = {
        "x": {"stacked": True},
        "y": {"stacked": True},
    }
    options.setdefault("plugins", {})["legend"] = {"display": True}

    return ChartJSConfig(chart_type="bar", data=data, options=options)


def scatter_chart_config(
    points: list[dict],
    title: Optional[str] = None,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    color: Optional[str] = None,
) -> ChartJSConfig:
    """Generate a scatter plot chart configuration.

    Args:
        points: [{"x": float, "y": float, "label": str (optional)}, ...]
        title: Optional chart title
        x_label: Optional x-axis label
        y_label: Optional y-axis label
        color: Optional point color. Defaults to CCA primary.
    """
    color = color or CCA_CHART_COLORS[0]

    data = {
        "datasets": [{
            "data": [{"x": p["x"], "y": p["y"]} for p in points],
            "backgroundColor": color,
            "pointRadius": 5,
            "pointHoverRadius": 7,
        }],
    }

    options = _base_options(title)
    options["scales"] = {}
    if x_label:
        options["scales"]["x"] = {"title": {"display": True, "text": x_label}}
    if y_label:
        options["scales"]["y"] = {"title": {"display": True, "text": y_label}}
    options.setdefault("plugins", {})["legend"] = {"display": False}
    options.setdefault("plugins", {})["tooltip"] = {
        "callbacks": {},
    }

    return ChartJSConfig(chart_type="scatter", data=data, options=options)


def horizontal_bar_config(
    labels: list[str],
    values: list[float],
    title: Optional[str] = None,
    colors: Optional[list[str]] = None,
) -> ChartJSConfig:
    """Generate a horizontal bar chart configuration.

    Args:
        labels: Y-axis category labels
        values: Bar values
        title: Optional chart title
        colors: Optional colors per bar. Defaults to CCA palette.
    """
    if colors is None:
        colors = _default_colors(len(labels))

    data = {
        "labels": labels,
        "datasets": [{
            "data": values,
            "backgroundColor": colors,
            "borderRadius": 3,
        }],
    }

    options = _base_options(title)
    options["indexAxis"] = "y"
    options.setdefault("plugins", {})["legend"] = {"display": False}

    return ChartJSConfig(chart_type="bar", data=data, options=options)


def render_chartjs_canvas(
    chart_id: str,
    width: int = 400,
    height: int = 300,
) -> str:
    """Render an HTML canvas element for a Chart.js chart.

    Args:
        chart_id: Unique ID for the canvas element
        width: Canvas width in pixels
        height: Canvas height in pixels
    """
    return (
        f'<div style="width:{width}px;height:{height}px;position:relative">'
        f'<canvas id="{chart_id}" width="{width}" height="{height}"></canvas>'
        f'</div>'
    )


def render_chartjs_script(chart_id: str, config: ChartJSConfig) -> str:
    """Render a <script> block that creates a Chart.js chart.

    Args:
        chart_id: Must match the canvas element ID
        config: ChartJSConfig object
    """
    config_json = config.to_json()
    return (
        f'<script>\n'
        f'new Chart(document.getElementById("{chart_id}"), {config_json});\n'
        f'</script>'
    )


def render_chartjs_cdn_tag() -> str:
    """Render the <script> tag to load Chart.js from CDN."""
    return f'<script src="{CHARTJS_CDN_URL}"></script>'
