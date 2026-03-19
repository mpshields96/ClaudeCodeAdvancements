#!/usr/bin/env python3
"""SVG chart generator using CCA design language (MT-17 Phase 4).

Generates clean, professional SVG charts without external dependencies.
All charts follow the CCA design guide: accent colors, Source Sans 3 typography,
no 3D effects or gradients, always-labeled axes.

Chart types:
    BarChart          — vertical bars for time series
    HorizontalBarChart — horizontal bars for category comparison
    LineChart         — line/area for trends (supports multiple series)
    Sparkline         — compact inline trend indicator
    DonutChart        — progress/completion indicator (NOT for data comparison)

Usage:
    from chart_generator import BarChart, render_svg, save_svg

    chart = BarChart([("S45", 800), ("S48", 1686)], title="Tests")
    svg_string = render_svg(chart)
    save_svg(chart, "tests.svg")
"""

import math
import os
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# CCA Design Language colors (from design-guide.md)
# ---------------------------------------------------------------------------

CCA_COLORS = {
    "primary": "#1a1a2e",
    "accent": "#0f3460",
    "highlight": "#e94560",
    "success": "#16c79a",
    "muted": "#6b7280",
    "background": "#ffffff",
    "surface": "#f8f9fa",
    "border": "#e5e7eb",
    "warning": "#f59e0b",
}

# Chart series palette (accent first, then distinguishable colors)
SERIES_PALETTE = [
    CCA_COLORS["accent"],
    CCA_COLORS["highlight"],
    CCA_COLORS["success"],
    CCA_COLORS["warning"],
    CCA_COLORS["muted"],
]

SVG_NS = "http://www.w3.org/2000/svg"

# Font stack matching design guide
FONT_FAMILY = "'Source Sans 3', 'Helvetica Neue', Arial, sans-serif"
CODE_FONT = "'Source Code Pro', 'Courier New', monospace"


# ---------------------------------------------------------------------------
# XML/SVG helpers
# ---------------------------------------------------------------------------

def _escape(text: str) -> str:
    """Escape text for XML attributes and content."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _svg_header(width: int, height: int) -> str:
    return (f'<svg xmlns="{SVG_NS}" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">\n')


def _svg_footer() -> str:
    return "</svg>\n"


def _text(x: float, y: float, text: str, font_size: int = 11,
          fill: str = None, anchor: str = "middle",
          font_weight: str = "normal", font_family: str = None,
          transform: str = None) -> str:
    fill = fill or CCA_COLORS["primary"]
    font_family = font_family or FONT_FAMILY
    parts = [f'<text x="{x:.1f}" y="{y:.1f}" '
             f'font-family="{font_family}" font-size="{font_size}" '
             f'fill="{fill}" text-anchor="{anchor}" '
             f'font-weight="{font_weight}"']
    if transform:
        parts.append(f' transform="{transform}"')
    parts.append(f">{_escape(text)}</text>\n")
    return "".join(parts)


def _rect(x: float, y: float, w: float, h: float, fill: str,
          rx: float = 0) -> str:
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" '
            f'height="{h:.1f}" fill="{fill}" rx="{rx}"/>\n')


def _line(x1: float, y1: float, x2: float, y2: float,
          stroke: str, stroke_width: float = 1) -> str:
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
            f'y2="{y2:.1f}" stroke="{stroke}" '
            f'stroke-width="{stroke_width}"/>\n')


def _circle(cx: float, cy: float, r: float, fill: str) -> str:
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"/>\n'


def _polyline(points: list, stroke: str, stroke_width: float = 2,
              fill: str = "none") -> str:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return (f'<polyline points="{pts}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{stroke_width}" '
            f'stroke-linejoin="round" stroke-linecap="round"/>\n')


def _arc_path(cx: float, cy: float, r: float, start_angle: float,
              end_angle: float, inner_r: float = 0) -> str:
    """Generate SVG path for an arc segment (donut slice)."""
    def polar_to_cart(angle):
        rad = math.radians(angle - 90)  # Start from top
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    def inner_polar(angle):
        rad = math.radians(angle - 90)
        return cx + inner_r * math.cos(rad), cy + inner_r * math.sin(rad)

    large = 1 if (end_angle - start_angle) > 180 else 0

    sx, sy = polar_to_cart(start_angle)
    ex, ey = polar_to_cart(end_angle)

    if inner_r > 0:
        isx, isy = inner_polar(end_angle)
        iex, iey = inner_polar(start_angle)
        return (f"M {sx:.1f} {sy:.1f} "
                f"A {r} {r} 0 {large} 1 {ex:.1f} {ey:.1f} "
                f"L {isx:.1f} {isy:.1f} "
                f"A {inner_r} {inner_r} 0 {large} 0 {iex:.1f} {iey:.1f} Z")
    else:
        return (f"M {cx} {cy} "
                f"L {sx:.1f} {sy:.1f} "
                f"A {r} {r} 0 {large} 1 {ex:.1f} {ey:.1f} Z")


# ---------------------------------------------------------------------------
# Chart classes
# ---------------------------------------------------------------------------

@dataclass
class BarChart:
    """Vertical bar chart for time series data."""
    data: list  # [(label, value), ...]
    title: str = ""
    width: int = 500
    height: int = 300
    color: str = ""
    y_label: str = ""
    show_values: bool = False

    def __post_init__(self):
        if not self.color:
            self.color = CCA_COLORS["accent"]


@dataclass
class HorizontalBarChart:
    """Horizontal bar chart for category comparison."""
    data: list  # [(label, value), ...]
    title: str = ""
    width: int = 500
    height: int = 300
    color: str = ""
    show_values: bool = False

    def __post_init__(self):
        if not self.color:
            self.color = CCA_COLORS["accent"]


@dataclass
class LineChart:
    """Line chart for trend data, supports multiple series."""
    data: list  # [(label, value), ...] — primary series
    title: str = ""
    width: int = 500
    height: int = 300
    color: str = ""
    y_label: str = ""
    show_points: bool = False
    extra_series: list = field(default_factory=list)
    # extra_series: [("name", [(label, value)], color), ...]

    def __post_init__(self):
        if not self.color:
            self.color = CCA_COLORS["accent"]


@dataclass
class Sparkline:
    """Compact inline sparkline (no axes, no labels)."""
    values: list  # [value, ...]
    width: int = 100
    height: int = 24
    color: str = ""

    def __post_init__(self):
        if not self.color:
            self.color = CCA_COLORS["accent"]


@dataclass
class DonutChart:
    """Donut chart for progress/completion display."""
    data: list  # [(label, value, color), ...]
    title: str = ""
    width: int = 300
    height: int = 300
    center_text: str = ""


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def _render_bar_chart(chart: BarChart) -> str:
    """Render a vertical bar chart to SVG."""
    parts = [_svg_header(chart.width, chart.height)]

    # Background
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=12, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Layout
    margin_top = 40 if chart.title else 20
    margin_bottom = 40
    margin_left = 60
    margin_right = 20
    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    # Scale
    max_val = max(v for _, v in chart.data)
    if max_val == 0:
        max_val = 1

    # Y-axis gridlines (4 lines)
    for i in range(5):
        y = margin_top + plot_h - (plot_h * i / 4)
        val = int(max_val * i / 4)
        parts.append(_line(margin_left, y, margin_left + plot_w, y,
                           CCA_COLORS["border"], 0.5))
        parts.append(_text(margin_left - 8, y + 4, str(val),
                           font_size=9, fill=CCA_COLORS["muted"],
                           anchor="end"))

    # Y-axis label
    if chart.y_label:
        parts.append(_text(14, margin_top + plot_h / 2, chart.y_label,
                           font_size=10, fill=CCA_COLORS["muted"],
                           transform=f"rotate(-90, 14, {margin_top + plot_h / 2})"))

    # Bars
    n = len(chart.data)
    bar_spacing = plot_w / n
    bar_width = bar_spacing * 0.6

    for i, (label, value) in enumerate(chart.data):
        bar_h = (value / max_val) * plot_h
        x = margin_left + i * bar_spacing + (bar_spacing - bar_width) / 2
        y = margin_top + plot_h - bar_h

        parts.append(_rect(x, y, bar_width, bar_h, chart.color, rx=2))

        # Label below bar
        parts.append(_text(x + bar_width / 2, margin_top + plot_h + 16,
                           str(label), font_size=9, fill=CCA_COLORS["muted"]))

        # Value on bar
        if chart.show_values:
            parts.append(_text(x + bar_width / 2, y - 4, str(value),
                               font_size=9, fill=CCA_COLORS["primary"],
                               font_weight="bold"))

    # Axes
    parts.append(_line(margin_left, margin_top, margin_left,
                       margin_top + plot_h, CCA_COLORS["border"]))
    parts.append(_line(margin_left, margin_top + plot_h,
                       margin_left + plot_w, margin_top + plot_h,
                       CCA_COLORS["border"]))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_horizontal_bar_chart(chart: HorizontalBarChart) -> str:
    """Render a horizontal bar chart to SVG."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=12, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    margin_top = 40 if chart.title else 20
    margin_bottom = 20
    margin_left = 120  # Space for labels
    margin_right = 60 if chart.show_values else 20
    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom

    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    max_val = max(v for _, v in chart.data)
    if max_val == 0:
        max_val = 1

    n = len(chart.data)
    bar_spacing = plot_h / n
    bar_height = bar_spacing * 0.6

    for i, (label, value) in enumerate(chart.data):
        bar_w = (value / max_val) * plot_w
        y = margin_top + i * bar_spacing + (bar_spacing - bar_height) / 2

        parts.append(_rect(margin_left, y, bar_w, bar_height,
                           chart.color, rx=2))

        # Label to the left
        parts.append(_text(margin_left - 8, y + bar_height / 2 + 4,
                           str(label), font_size=10,
                           fill=CCA_COLORS["primary"], anchor="end"))

        # Value after bar
        if chart.show_values:
            parts.append(_text(margin_left + bar_w + 6,
                               y + bar_height / 2 + 4,
                               str(value), font_size=9,
                               fill=CCA_COLORS["muted"], anchor="start"))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_line_chart(chart: LineChart) -> str:
    """Render a line chart to SVG."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=12, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    margin_top = 40 if chart.title else 20
    margin_bottom = 40
    margin_left = 60
    margin_right = 20
    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom

    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    # Find global max across all series
    all_values = [v for _, v in chart.data]
    for _, series_data, _ in chart.extra_series:
        all_values.extend(v for _, v in series_data)
    max_val = max(all_values) if all_values else 1
    if max_val == 0:
        max_val = 1

    # Y-axis gridlines
    for i in range(5):
        y = margin_top + plot_h - (plot_h * i / 4)
        val = int(max_val * i / 4)
        parts.append(_line(margin_left, y, margin_left + plot_w, y,
                           CCA_COLORS["border"], 0.5))
        parts.append(_text(margin_left - 8, y + 4, str(val),
                           font_size=9, fill=CCA_COLORS["muted"],
                           anchor="end"))

    # Y-axis label
    if chart.y_label:
        parts.append(_text(14, margin_top + plot_h / 2, chart.y_label,
                           font_size=10, fill=CCA_COLORS["muted"],
                           transform=f"rotate(-90, 14, {margin_top + plot_h / 2})"))

    def series_to_points(series_data):
        n = len(series_data)
        if n == 1:
            return [(margin_left + plot_w / 2,
                     margin_top + plot_h - (series_data[0][1] / max_val) * plot_h)]
        points = []
        for i, (_, value) in enumerate(series_data):
            x = margin_left + (i / (n - 1)) * plot_w
            y = margin_top + plot_h - (value / max_val) * plot_h
            points.append((x, y))
        return points

    # Render extra series first (behind primary)
    for _, series_data, series_color in chart.extra_series:
        points = series_to_points(series_data)
        if points:
            parts.append(_polyline(points, series_color, 2))

    # Primary series
    points = series_to_points(chart.data)
    if points:
        parts.append(_polyline(points, chart.color, 2.5))

    # Data points
    if chart.show_points:
        for px, py in points:
            parts.append(_circle(px, py, 3, chart.color))

    # X-axis labels
    n = len(chart.data)
    for i, (label, _) in enumerate(chart.data):
        if n == 1:
            x = margin_left + plot_w / 2
        else:
            x = margin_left + (i / (n - 1)) * plot_w
        parts.append(_text(x, margin_top + plot_h + 16, str(label),
                           font_size=9, fill=CCA_COLORS["muted"]))

    # Axes
    parts.append(_line(margin_left, margin_top, margin_left,
                       margin_top + plot_h, CCA_COLORS["border"]))
    parts.append(_line(margin_left, margin_top + plot_h,
                       margin_left + plot_w, margin_top + plot_h,
                       CCA_COLORS["border"]))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_sparkline(chart: Sparkline) -> str:
    """Render a compact sparkline to SVG."""
    parts = [_svg_header(chart.width, chart.height)]

    if not chart.values:
        parts.append(_svg_footer())
        return "".join(parts)

    padding = 2
    plot_w = chart.width - padding * 2
    plot_h = chart.height - padding * 2

    min_val = min(chart.values)
    max_val = max(chart.values)
    val_range = max_val - min_val
    if val_range == 0:
        val_range = 1

    n = len(chart.values)
    points = []
    for i, v in enumerate(chart.values):
        if n == 1:
            x = padding + plot_w / 2
        else:
            x = padding + (i / (n - 1)) * plot_w
        y = padding + plot_h - ((v - min_val) / val_range) * plot_h
        points.append((x, y))

    parts.append(_polyline(points, chart.color, 1.5))
    parts.append(_svg_footer())
    return "".join(parts)


def _render_donut_chart(chart: DonutChart) -> str:
    """Render a donut chart to SVG."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=12, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    margin_top = 40 if chart.title else 20

    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    # Donut dimensions
    cx = chart.width / 2
    available_h = chart.height - margin_top - 60  # Leave space for legend
    cy = margin_top + available_h / 2
    r = min(available_h / 2, (chart.width - 40) / 2)
    inner_r = r * 0.55

    total = sum(v for _, v, _ in chart.data)
    if total == 0:
        total = 1

    start_angle = 0
    for label, value, color in chart.data:
        sweep = (value / total) * 360
        end_angle = start_angle + sweep

        if sweep > 0.5:  # Skip tiny slices
            # Prevent full-circle single-segment rendering issue
            if sweep >= 359.9:
                end_angle = start_angle + 359.9

            path_d = _arc_path(cx, cy, r, start_angle, end_angle, inner_r)
            parts.append(f'<path d="{path_d}" fill="{color}"/>\n')

        start_angle = end_angle

    # Center text
    if chart.center_text:
        parts.append(_text(cx, cy + 6, chart.center_text,
                           font_size=18, font_weight="bold",
                           fill=CCA_COLORS["primary"]))

    # Legend below chart
    legend_y = chart.height - 40
    legend_x_start = 20
    x_pos = legend_x_start
    for label, value, color in chart.data:
        # Color swatch
        parts.append(_rect(x_pos, legend_y - 8, 10, 10, color, rx=2))
        # Label
        parts.append(_text(x_pos + 14, legend_y, f"{label} ({value})",
                           font_size=9, fill=CCA_COLORS["muted"],
                           anchor="start"))
        x_pos += len(f"{label} ({value})") * 6 + 30

    parts.append(_svg_footer())
    return "".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_svg(chart) -> str:
    """Render any chart object to an SVG string."""
    if isinstance(chart, BarChart):
        return _render_bar_chart(chart)
    elif isinstance(chart, HorizontalBarChart):
        return _render_horizontal_bar_chart(chart)
    elif isinstance(chart, LineChart):
        return _render_line_chart(chart)
    elif isinstance(chart, Sparkline):
        return _render_sparkline(chart)
    elif isinstance(chart, DonutChart):
        return _render_donut_chart(chart)
    else:
        raise TypeError(f"Unknown chart type: {type(chart)}")


def save_svg(chart, path: str) -> str:
    """Render chart and save to SVG file.

    Args:
        chart: Any chart object (BarChart, LineChart, etc.)
        path: Output file path.

    Returns:
        The file path written to.
    """
    svg = render_svg(chart)
    with open(path, "w") as f:
        f.write(svg)
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Demo: generate sample charts to /tmp/cca-charts/."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate CCA-styled SVG charts.")
    parser.add_argument("--output", "-o", default="/tmp/cca-charts",
                        help="Output directory")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # Demo: test growth bar chart
    test_data = [
        ("S44", 600), ("S45", 800), ("S46", 1200),
        ("S47", 1500), ("S48", 1686), ("S49", 1726),
    ]
    save_svg(
        BarChart(test_data, title="Test Count Growth", y_label="Tests",
                 show_values=True),
        os.path.join(args.output, "test_growth.svg"),
    )

    # Demo: module tests horizontal bar
    module_data = [
        ("Self-Learning", 355), ("Agent Guard", 264),
        ("Reddit Intel", 263), ("Context Monitor", 232),
        ("Usage Dashboard", 196), ("Memory", 94),
        ("Spec System", 90), ("Research", 86),
        ("Design Skills", 79),
    ]
    save_svg(
        HorizontalBarChart(module_data, title="Tests by Module",
                           show_values=True, color=CCA_COLORS["accent"]),
        os.path.join(args.output, "module_tests.svg"),
    )

    # Demo: line chart with two series
    save_svg(
        LineChart(test_data, title="Test Growth Trend", y_label="Count",
                  show_points=True,
                  extra_series=[
                      ("Suites", [("S44", 15), ("S45", 18), ("S46", 20),
                                  ("S47", 22), ("S48", 42), ("S49", 44)],
                       CCA_COLORS["success"]),
                  ]),
        os.path.join(args.output, "test_trend.svg"),
    )

    # Demo: sparkline
    save_svg(
        Sparkline([600, 800, 1200, 1500, 1686, 1726]),
        os.path.join(args.output, "sparkline.svg"),
    )

    # Demo: donut chart
    save_svg(
        DonutChart([
            ("Complete", 12, CCA_COLORS["success"]),
            ("In Progress", 4, CCA_COLORS["accent"]),
            ("Not Started", 2, CCA_COLORS["muted"]),
        ], title="Master Task Status", center_text="67%"),
        os.path.join(args.output, "mt_status.svg"),
    )

    print(f"Generated 5 demo charts in {args.output}/")


if __name__ == "__main__":
    main()
