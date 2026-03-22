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
    AreaChart         — line with gradient fill below for volume/magnitude
    StackedBarChart   — stacked vertical bars for composition comparison
    HeatmapChart      — 2D grid of colored cells for correlation/intensity data

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


def _lerp_color(color_a: str, color_b: str, t: float) -> str:
    """Interpolate between two hex colors. t=0 → color_a, t=1 → color_b."""
    t = max(0.0, min(1.0, t))
    ra, ga, ba = int(color_a[1:3], 16), int(color_a[3:5], 16), int(color_a[5:7], 16)
    rb, gb, bb = int(color_b[1:3], 16), int(color_b[3:5], 16), int(color_b[5:7], 16)
    r = int(ra + (rb - ra) * t)
    g = int(ga + (gb - ga) * t)
    b = int(ba + (bb - ba) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


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


@dataclass
class AreaChart:
    """Area chart — line chart with gradient fill below.

    Essentially a LineChart with a filled region between the line and x-axis.
    Good for showing volume/magnitude over time.

    Args:
        data: [(label, value), ...] — single series
        fill_opacity: Opacity of the filled area (0.0-1.0)
    """
    data: list  # [(label, value), ...]
    title: str = ""
    width: int = 500
    height: int = 300
    color: str = ""
    y_label: str = ""
    show_points: bool = False
    fill_opacity: float = 0.3

    def __post_init__(self):
        if not self.color:
            self.color = CCA_COLORS["accent"]


@dataclass
class StackedBarChart:
    """Stacked vertical bar chart for comparing composition across categories.

    Each category has a bar divided into segments, one per series.
    Useful for showing how totals break down (e.g., BUILD/ADAPT/SKIP per session).

    Args:
        data: [(label, [val_series_0, val_series_1, ...]), ...]
        series_names: ["Series A", "Series B", ...] — legend labels
        colors: Custom colors per series (default: SERIES_PALETTE)
        show_values: Show segment values inside bars
    """
    data: list  # [(label, [values_per_series]), ...]
    series_names: list  # ["Build", "Adapt", "Skip"]
    title: str = ""
    width: int = 500
    height: int = 300
    colors: list = field(default_factory=list)
    show_values: bool = False
    y_label: str = ""

    def __post_init__(self):
        if not self.colors:
            self.colors = [SERIES_PALETTE[i % len(SERIES_PALETTE)]
                          for i in range(len(self.series_names))]


@dataclass
class HeatmapChart:
    """Heatmap chart: 2D grid of colored cells for correlation/intensity data.

    Colors are computed by interpolating between low_color and high_color
    using the value's position in [min, max] range. No SVG gradients — each
    cell gets a computed fill color from the CCA palette.

    Args:
        data: 2D list of numeric values [[row0_col0, ...], [row1_col0, ...]]
        row_labels: Labels for rows (y-axis), length must match len(data)
        col_labels: Labels for columns (x-axis), length must match len(data[0])
        title: Optional chart title
        width: SVG width in pixels
        height: SVG height in pixels
        show_values: If True, render each cell's value as text
        low_color: Hex color for minimum values (default: CCA surface)
        high_color: Hex color for maximum values (default: CCA accent)
    """
    data: list  # [[row0_col0, row0_col1, ...], [row1_col0, ...]]
    row_labels: list = field(default_factory=list)
    col_labels: list = field(default_factory=list)
    title: str = ""
    width: int = 500
    height: int = 400
    show_values: bool = False
    low_color: str = ""
    high_color: str = ""

    def __post_init__(self):
        if not self.low_color:
            self.low_color = CCA_COLORS["surface"]
        if not self.high_color:
            self.high_color = CCA_COLORS["accent"]


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


def _render_heatmap_chart(chart: HeatmapChart) -> str:
    """Render a heatmap chart to SVG.

    Each cell is colored by interpolating between chart.low_color and
    chart.high_color based on the cell's position in [global_min, global_max].
    No SVG gradient elements are used — colors are computed per-cell.
    """
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    # Guard: empty data
    rows = [r for r in chart.data if r]
    if not rows:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=12, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    n_rows = len(rows)
    n_cols = max(len(r) for r in rows)

    # Margins: leave space for title, row labels (left), col labels (bottom)
    has_row_labels = bool(chart.row_labels)
    has_col_labels = bool(chart.col_labels)

    margin_top = 36 if chart.title else 16
    margin_bottom = 28 if has_col_labels else 10
    margin_left = 80 if has_row_labels else 10
    margin_right = 16

    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom

    cell_w = plot_w / n_cols if n_cols else plot_w
    cell_h = plot_h / n_rows if n_rows else plot_h

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 22, chart.title,
                           font_size=13, font_weight="bold"))

    # Compute global min/max for color normalization
    all_vals = [v for row in rows for v in row]
    v_min = min(all_vals)
    v_max = max(all_vals)
    v_range = v_max - v_min if v_max != v_min else 1.0

    # Render cells
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            t = (val - v_min) / v_range
            fill = _lerp_color(chart.low_color, chart.high_color, t)
            x = margin_left + ci * cell_w
            y = margin_top + ri * cell_h
            parts.append(_rect(x, y, cell_w, cell_h, fill))
            # Cell border (subtle)
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w:.1f}" '
                f'height="{cell_h:.1f}" fill="none" '
                f'stroke="{CCA_COLORS["background"]}" stroke-width="1"/>\n'
            )
            # Value text inside cell
            if chart.show_values:
                # Pick text color for contrast: light text on dark fill, dark on light
                r_int = int(fill[1:3], 16)
                g_int = int(fill[3:5], 16)
                b_int = int(fill[5:7], 16)
                luminance = 0.299 * r_int + 0.587 * g_int + 0.114 * b_int
                text_color = CCA_COLORS["background"] if luminance < 128 else CCA_COLORS["primary"]
                parts.append(_text(
                    x + cell_w / 2, y + cell_h / 2 + 4,
                    f"{val:.2f}", font_size=9, fill=text_color,
                ))

    # Row labels (left side)
    if has_row_labels:
        for ri, label in enumerate(chart.row_labels[:n_rows]):
            y = margin_top + ri * cell_h + cell_h / 2 + 4
            parts.append(_text(
                margin_left - 6, y, str(label),
                font_size=10, fill=CCA_COLORS["muted"], anchor="end",
            ))

    # Column labels (bottom)
    if has_col_labels:
        for ci, label in enumerate(chart.col_labels[:n_cols]):
            x = margin_left + ci * cell_w + cell_w / 2
            y = margin_top + plot_h + 18
            parts.append(_text(
                x, y, str(label),
                font_size=10, fill=CCA_COLORS["muted"],
            ))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_area_chart(chart: AreaChart) -> str:
    """Render an area chart to SVG — line with filled region below."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                          font_size=14, fill=CCA_COLORS["muted"], anchor="middle"))
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

    values = [v for _, v in chart.data]
    max_val = max(values) if values else 1
    if max_val == 0:
        max_val = 1

    # Y-axis gridlines
    for i in range(5):
        y = margin_top + plot_h - (plot_h * i / 4)
        val = max_val * i / 4
        label = str(int(val)) if val == int(val) else f"{val:.1f}"
        parts.append(_line(margin_left, y, margin_left + plot_w, y,
                          CCA_COLORS["border"], 0.5))
        parts.append(_text(margin_left - 8, y + 4, label,
                          font_size=9, fill=CCA_COLORS["muted"], anchor="end"))

    # Y-axis label
    if chart.y_label:
        parts.append(_text(14, margin_top + plot_h / 2, chart.y_label,
                          font_size=10, fill=CCA_COLORS["muted"], anchor="middle",
                          transform=f"rotate(-90, 14, {margin_top + plot_h / 2})"))

    # Compute points
    n = len(chart.data)
    points = []
    for i, (_, value) in enumerate(chart.data):
        if n == 1:
            x = margin_left + plot_w / 2
        else:
            x = margin_left + (i / (n - 1)) * plot_w
        y = margin_top + plot_h - (max(0, value) / max_val) * plot_h
        points.append((x, y))

    # Filled area polygon (line points + bottom corners)
    if points:
        baseline_y = margin_top + plot_h
        poly_points = list(points)
        poly_points.append((points[-1][0], baseline_y))
        poly_points.append((points[0][0], baseline_y))

        coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in poly_points)
        parts.append(
            f'<polygon points="{coords}" '
            f'fill="{chart.color}" fill-opacity="{chart.fill_opacity}" '
            f'stroke="none"/>\n'
        )

        # Line on top
        parts.append(_polyline(points, chart.color, 2.5))

    # Data points
    if chart.show_points:
        for x, y in points:
            parts.append(_circle(x, y, 3, chart.color))

    # X-axis labels
    step = max(1, n // 10)  # Show at most ~10 labels
    for i, (label, _) in enumerate(chart.data):
        if i % step == 0 or i == n - 1:
            if n == 1:
                x = margin_left + plot_w / 2
            else:
                x = margin_left + (i / (n - 1)) * plot_w
            parts.append(_text(x, margin_top + plot_h + 16, str(label),
                              font_size=9, fill=CCA_COLORS["muted"], anchor="middle"))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_stacked_bar_chart(chart: StackedBarChart) -> str:
    """Render a stacked vertical bar chart to SVG."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                          font_size=14, fill=CCA_COLORS["muted"], anchor="middle"))
        parts.append(_svg_footer())
        return "".join(parts)

    # Layout constants
    margin_top = 40 if chart.title else 20
    margin_bottom = 50
    margin_left = 60
    margin_right = 20
    legend_height = 25

    plot_x = margin_left
    plot_y = margin_top
    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom - legend_height

    n_categories = len(chart.data)
    n_series = len(chart.series_names)

    # Compute max stack height
    max_total = 0
    for _, values in chart.data:
        total = sum(max(0, v) for v in values[:n_series])
        max_total = max(max_total, total)

    if max_total == 0:
        max_total = 1  # Avoid division by zero

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 22, chart.title,
                          font_size=14, fill=CCA_COLORS["primary"],
                          anchor="middle", font_weight="600"))

    # Y-axis label
    if chart.y_label:
        parts.append(
            _text(14, plot_y + plot_h / 2, chart.y_label,
                  font_size=10, fill=CCA_COLORS["muted"], anchor="middle",
                  transform=f"rotate(-90, 14, {plot_y + plot_h / 2})")
        )

    # Y-axis gridlines + labels
    n_ticks = 5
    for i in range(n_ticks + 1):
        val = max_total * i / n_ticks
        y = plot_y + plot_h - (plot_h * i / n_ticks)
        parts.append(_line(plot_x, y, plot_x + plot_w, y,
                          stroke=CCA_COLORS["border"]))
        label = str(int(val)) if val == int(val) else f"{val:.1f}"
        parts.append(_text(plot_x - 8, y + 4, label,
                          font_size=9, fill=CCA_COLORS["muted"], anchor="end"))

    # Bars
    bar_spacing = plot_w / n_categories
    bar_width = bar_spacing * 0.7

    for cat_idx, (label, values) in enumerate(chart.data):
        bar_x = plot_x + cat_idx * bar_spacing + (bar_spacing - bar_width) / 2
        cumulative_height = 0

        for s_idx in range(min(n_series, len(values))):
            val = max(0, values[s_idx])
            seg_height = (val / max_total) * plot_h
            seg_y = plot_y + plot_h - cumulative_height - seg_height

            color = chart.colors[s_idx % len(chart.colors)]
            parts.append(_rect(bar_x, seg_y, bar_width, seg_height, color))

            # Value label inside segment
            if chart.show_values and val > 0 and seg_height > 14:
                parts.append(_text(bar_x + bar_width / 2, seg_y + seg_height / 2 + 4,
                                  str(int(val)) if val == int(val) else f"{val:.1f}",
                                  font_size=9, fill="#ffffff", anchor="middle"))

            cumulative_height += seg_height

        # Category label
        parts.append(_text(plot_x + cat_idx * bar_spacing + bar_spacing / 2,
                          plot_y + plot_h + 16, str(label),
                          font_size=10, fill=CCA_COLORS["muted"], anchor="middle"))

    # Legend
    legend_y = chart.height - legend_height + 5
    legend_x_start = plot_x
    for s_idx, name in enumerate(chart.series_names):
        lx = legend_x_start + s_idx * 100
        parts.append(_rect(lx, legend_y, 12, 12, chart.colors[s_idx % len(chart.colors)]))
        parts.append(_text(lx + 16, legend_y + 10, name,
                          font_size=9, fill=CCA_COLORS["muted"]))

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
    elif isinstance(chart, AreaChart):
        return _render_area_chart(chart)
    elif isinstance(chart, StackedBarChart):
        return _render_stacked_bar_chart(chart)
    elif isinstance(chart, HeatmapChart):
        return _render_heatmap_chart(chart)
    else:
        raise TypeError(f"Unknown chart type: {type(chart)}")


def generate_heatmap(data: list, row_labels: list = None, col_labels: list = None,
                     title: str = "", **kwargs) -> str:
    """Convenience function: render a heatmap and return SVG string.

    Args:
        data: 2D list of numeric values [[row0_col0, ...], ...]
        row_labels: Labels for rows (optional)
        col_labels: Labels for columns (optional)
        title: Chart title (optional)
        **kwargs: Additional HeatmapChart constructor args (width, height, show_values, etc.)

    Returns:
        SVG string ready to embed or save.
    """
    chart = HeatmapChart(
        data=data,
        row_labels=row_labels or [],
        col_labels=col_labels or [],
        title=title,
        **kwargs,
    )
    return render_svg(chart)


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
