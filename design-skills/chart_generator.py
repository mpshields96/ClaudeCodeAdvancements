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
    StackedAreaChart  — stacked filled areas for multiple series over time
    GroupedBarChart   — side-by-side bars for direct multi-series comparison
    WaterfallChart    — cumulative P&L waterfall (green positive, red negative)
    RadarChart        — spider/radar chart for multi-dimensional comparison
    GaugeChart        — semicircular speedometer for single metric vs target
    BubbleChart       — scatter plot with sized circles for 3D data
    TreemapChart      — nested rectangles sized by value for hierarchical data
    SankeyChart       — flow diagram showing value transfers between nodes
    FunnelChart       — conversion funnel (wide-to-narrow trapezoids, % labels)
    ScatterPlot       — XY scatter with optional trend lines, multiple series
    BoxPlot           — box-and-whisker for distribution comparison (median, IQR, outliers)
    HistogramChart    — frequency distribution from raw values (auto-binning, Sturges' rule)
    ViolinPlot        — KDE-based distribution shape with embedded quartile lines

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


@dataclass
class StackedAreaChart:
    """Stacked area chart — multiple filled areas layered cumulatively.

    Each series is drawn as a filled polygon whose baseline is the cumulative
    sum of all series beneath it, producing a stacked effect. Good for showing
    how multiple components contribute to a total over time.

    Unlike StackedBarChart (discrete categories), StackedAreaChart connects
    data points with lines — appropriate for continuous/time-series data.

    Single-series degenerates to a plain AreaChart rendering.

    Args:
        series: [(name, [values]), ...] — ordered bottom-to-top
        labels: X-axis labels, length should match len(values) in each series
        colors: Per-series fill colors (default: SERIES_PALETTE)
        fill_opacity: Opacity of filled areas (0.0–1.0, default 0.5)
        show_points: If True, draw dots at each data point
        title: Optional chart title
        y_label: Optional y-axis label
        width: SVG width (px)
        height: SVG height (px)
    """
    series: list   # [(name, [values]), ...]
    labels: list   # [label, ...]
    title: str = ""
    width: int = 500
    height: int = 300
    colors: list = field(default_factory=list)
    fill_opacity: float = 0.5
    y_label: str = ""
    show_points: bool = False

    def __post_init__(self):
        if not self.colors:
            self.colors = [SERIES_PALETTE[i % len(SERIES_PALETTE)]
                          for i in range(len(self.series))]


@dataclass
class GroupedBarChart:
    """Grouped bar chart — multiple series rendered as side-by-side bars.

    Each category (x-axis label) displays one bar per series, grouped
    together. Unlike StackedBarChart (cumulative), grouped bars show
    absolute values side-by-side for direct comparison.

    Good for comparing the same metric across multiple modules or
    sessions where absolute values matter more than composition.

    Args:
        data: [(label, [val_series_0, val_series_1, ...]), ...]
        series_names: ["Series A", "Series B", ...] — legend labels
        colors: Custom colors per series (default: SERIES_PALETTE)
        show_values: Show value labels above each bar
        title: Optional chart title
        y_label: Optional y-axis label
        width: SVG width (px)
        height: SVG height (px)
    """
    data: list         # [(label, [values_per_series]), ...]
    series_names: list  # ["Memory", "Agent Guard", ...]
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
class WaterfallChart:
    """Waterfall chart — cumulative positive/negative contributions.

    Each bar floats from the running cumulative total. Positive bars are
    green, negative bars are red. A final 'Total' bar shows the sum of all
    contributions. Connector lines link adjacent bars to make the flow clear.

    Useful for financial P&L breakdowns, before/after comparisons, or any
    scenario where you want to show how individual items contribute to a total.

    Args:
        data: [(label, value), ...] — positive or negative numeric values
        title: Optional chart title
        total_label: Label for the final total bar (default: "Total")
        show_values: If True, render value labels above/below each bar
        width: SVG width (px)
        height: SVG height (px)
    """
    data: list          # [(label, value), ...]
    title: str = ""
    total_label: str = "Total"
    show_values: bool = True
    width: int = 500
    height: int = 300


@dataclass
class RadarChart:
    """Radar (spider) chart — multi-dimensional comparison on radial axes.

    Each axis radiates from the center at equal angular spacing. Values are
    plotted along their axis and connected into a polygon. Multiple series
    can be overlaid for direct comparison. Grid circles at 25/50/75/100%
    of the max value provide reference.

    Args:
        data: [(label, value), ...] — single series (3–8 axes)
        title: Optional chart title
        max_value: Scale max (default: auto from data)
        extra_series: [("name", [(label, value)], color), ...] — overlay series
        fill_opacity: Fill opacity for polygon (default 0.2)
        width: SVG width (px)
        height: SVG height (px)
    """
    data: list          # [(label, value), ...] — 3-8 items
    title: str = ""
    max_value: float = 0.0
    extra_series: list = field(default_factory=list)
    fill_opacity: float = 0.2
    color: str = ""
    width: int = 400
    height: int = 400

    def __post_init__(self):
        if not self.color:
            self.color = CCA_COLORS["accent"]


@dataclass
class GaugeChart:
    """Gauge (speedometer) chart — single metric against a target range.

    A semicircular arc is divided into color zones (red/yellow/green) based on
    configurable thresholds. A needle points to the current value. The value
    is displayed as text in the center. Min/max markers are shown at arc ends.

    Args:
        value: Current value to display
        min_value: Minimum of the scale (default: 0)
        max_value: Maximum of the scale (default: 100)
        thresholds: (low, high) — below low=red, low–high=yellow, above high=green
        title: Optional chart title
        label: Optional sub-label below value (e.g., "% coverage")
        width: SVG width (px)
        height: SVG height (px)
    """
    value: float
    min_value: float = 0.0
    max_value: float = 100.0
    thresholds: tuple = (33.0, 66.0)   # (low_threshold, high_threshold)
    title: str = ""
    label: str = ""
    width: int = 400
    height: int = 280


@dataclass
class BubbleChart:
    """Bubble chart — scatter plot with sized circles for 3-dimensional data.

    Each data point has x, y, and size (radius). Useful for showing relationships
    between three variables (e.g., module LOC vs tests vs files).

    Args:
        data: [(label, x, y, size), ...] or [(label, x, y, size, color), ...]
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        min_radius: Minimum bubble radius in px
        max_radius: Maximum bubble radius in px
    """
    data: list  # [(label, x, y, size), ...] or [(label, x, y, size, color), ...]
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    width: int = 500
    height: int = 400
    min_radius: float = 8.0
    max_radius: float = 40.0


@dataclass
class TreemapChart:
    """Treemap chart — nested rectangles sized by value.

    Good for showing hierarchical data where area = proportion. Each rectangle
    represents a category, sized by its value relative to the total.

    Args:
        data: [(label, value), ...] or [(label, value, color), ...]
        title: Chart title
    """
    data: list  # [(label, value), ...] or [(label, value, color), ...]
    title: str = ""
    width: int = 500
    height: int = 400


@dataclass
class SankeyChart:
    """Sankey diagram — flow visualization between nodes.

    Shows how values flow from source nodes to target nodes through
    connecting bands. Useful for showing conversion funnels, intelligence
    scan pipelines (Scanned -> BUILD/SKIP/REFERENCE), or budget flows.

    Nodes are automatically arranged in columns (stages) based on the
    flow topology: source-only nodes on the left, sink-only on the right,
    intermediate nodes in between.

    Args:
        flows: [(source, target, value), ...] — directed weighted edges
        title: Chart title
        node_width: Width of node rectangles in px
        node_padding: Vertical gap between nodes in same column
        node_colors: Optional dict mapping node names to hex colors
    """
    flows: list  # [(source, target, value), ...]
    title: str = ""
    width: int = 600
    height: int = 400
    node_width: int = 20
    node_padding: int = 10
    node_colors: dict = field(default_factory=dict)


@dataclass
class FunnelChart:
    """Conversion funnel chart — wide-to-narrow trapezoids for stage drop-off.

    Each stage is rendered as a centered trapezoid whose width is proportional
    to its value relative to the first (widest) stage. Stage labels appear on
    the left and values on the right. Optional percentage labels show each
    stage's conversion rate relative to the top of the funnel.

    Args:
        data: [(label, value), ...] — stages in order from top (widest) to bottom
        title: Optional chart title
        show_percentages: If True, render % of first stage for each stage
        color: Base hex color for the funnel bars (default: CCA accent)
        width: SVG width in px (default: 400)
        height: SVG height in px (default: 350)
    """
    data: list              # [(label, value), ...]
    title: str = ""
    show_percentages: bool = True
    color: str = ""
    width: int = 400
    height: int = 350


@dataclass
class ScatterPlot:
    """Scatter plot for correlation analysis between two variables.

    Supports multiple series with distinct colors and optional linear
    trend line (least-squares regression). Each series is a named group
    of (x, y) points rendered with filled circles.

    Args:
        series: [{"name": str, "points": [(x, y), ...], "color": str (optional)}, ...]
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        show_trend: If True, draw least-squares regression line per series
        point_radius: Radius of scatter dots in px
    """
    series: list  # [{"name": ..., "points": [...], "color": ...}, ...]
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    width: int = 500
    height: int = 400
    show_trend: bool = False
    point_radius: float = 4.0


@dataclass
class BoxPlot:
    """Box-and-whisker plot for distribution comparison.

    Each category shows median, Q1, Q3, whiskers (1.5*IQR), and outliers.
    Standard statistical visualization for comparing distributions across
    groups (e.g., session durations, test counts per module).

    Args:
        data: [(label, [values...]), ...] — each category with raw numeric values
        title: Chart title
        y_label: Y-axis label
        show_outliers: If True (default), render outlier dots beyond whiskers
        color: Base color for boxes (default: CCA accent)
    """
    data: list  # [(label, [values...]), ...]
    title: str = ""
    y_label: str = ""
    width: int = 500
    height: int = 400
    show_outliers: bool = True
    color: str = ""


@dataclass
class HistogramChart:
    """Histogram — frequency distribution from raw numeric values.

    Automatically bins raw values into equal-width intervals and renders
    vertical bars showing count per bin. Pairs naturally with BoxPlot for
    distribution analysis.

    Args:
        values: [float, ...] — raw numeric values to bin
        title: Chart title
        x_label: X-axis label (what the values represent)
        y_label: Y-axis label (default: "Frequency")
        bins: Number of bins (default: auto based on Sturges' rule)
        color: Bar color (default: CCA accent)
    """
    values: list  # [float, ...]
    title: str = ""
    x_label: str = ""
    y_label: str = "Frequency"
    width: int = 500
    height: int = 400
    bins: int = 0  # 0 = auto (Sturges' rule)
    color: str = ""


@dataclass
class ViolinPlot:
    """Violin plot — KDE-based distribution shape with embedded quartile lines.

    Each category shows a mirrored kernel density estimate (KDE) with
    internal lines at Q1, median, and Q3. Richer than BoxPlot — shows
    the full shape of the distribution (bimodal, skewed, etc.).

    Uses a Gaussian KDE computed with Silverman's rule-of-thumb bandwidth.

    Args:
        data: [(label, [values...]), ...] — each category with raw numeric values
        title: Chart title
        y_label: Y-axis label
        color: Base color for violin fill (default: CCA accent)
    """
    data: list  # [(label, [values...]), ...]
    title: str = ""
    y_label: str = ""
    width: int = 500
    height: int = 400
    color: str = ""


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
                           font_size=14, fill=CCA_COLORS["muted"]))
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
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    margin_top = 40 if chart.title else 20
    margin_bottom = 20
    # Dynamic left margin: ~6px per character at font_size=10, min 120
    max_label_len = max((len(str(label)) for label, _ in chart.data), default=10)
    margin_left = max(120, int(max_label_len * 6.2) + 16)
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
                           font_size=14, fill=CCA_COLORS["muted"]))
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
                           font_size=14, fill=CCA_COLORS["muted"]))
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
                           font_size=14, fill=CCA_COLORS["muted"]))
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
                           font_size=14, font_weight="bold"))

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
    # Force integer display when max is a whole number
    all_int_bar = max_val == int(max_val)
    for i in range(5):
        y = margin_top + plot_h - (plot_h * i / 4)
        val = max_val * i / 4
        if all_int_bar:
            label = str(int(val)) if val == int(val) else str(int(round(val)))
        else:
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
    # Force integer display when max_total is a whole number (LOC, tests, phases)
    all_integer = max_total == int(max_total)
    n_ticks = 5
    for i in range(n_ticks + 1):
        val = max_total * i / n_ticks
        y = plot_y + plot_h - (plot_h * i / n_ticks)
        parts.append(_line(plot_x, y, plot_x + plot_w, y,
                          stroke=CCA_COLORS["border"]))
        if all_integer:
            label = str(int(val))
        else:
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

        # Category label — rotate when many categories to prevent overlap
        label_x = plot_x + cat_idx * bar_spacing + bar_spacing / 2
        label_y = plot_y + plot_h + 16
        if n_categories > 12:
            # Very crowded: -90 degrees, skip every other label
            if cat_idx % 2 == 0:
                display_label = str(label)[:10]
                parts.append(_text(label_x, label_y, display_label,
                                  font_size=8, fill=CCA_COLORS["muted"], anchor="end",
                                  transform=f"rotate(-90, {label_x}, {label_y})"))
        elif n_categories > 8:
            # Crowded: -90 degrees, all labels
            display_label = str(label)[:10]
            parts.append(_text(label_x, label_y, display_label,
                              font_size=8, fill=CCA_COLORS["muted"], anchor="end",
                              transform=f"rotate(-90, {label_x}, {label_y})"))
        elif n_categories > 4:
            # Moderate: -45 degrees
            display_label = str(label)[:12]
            parts.append(_text(label_x, label_y, display_label,
                              font_size=9, fill=CCA_COLORS["muted"], anchor="end",
                              transform=f"rotate(-45, {label_x}, {label_y})"))
        else:
            parts.append(_text(label_x, label_y, str(label),
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


def _render_stacked_area_chart(chart: StackedAreaChart) -> str:
    """Render a stacked area chart to SVG.

    Each series is drawn as a filled polygon. The bottom series sits on the
    x-axis baseline; each subsequent series is offset upward by the cumulative
    sum of the series beneath it. Lines are drawn on top of each fill.
    """
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.series:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                          font_size=14, fill=CCA_COLORS["muted"], anchor="middle"))
        parts.append(_svg_footer())
        return "".join(parts)

    # Layout constants
    margin_top = 40 if chart.title else 20
    margin_bottom = 50
    margin_left = 60
    margin_right = 20
    legend_height = 20

    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom - legend_height

    n_points = len(chart.labels)
    n_series = len(chart.series)

    # Normalise each series to exactly n_points values (pad with 0 if shorter)
    series_values = []
    for _, raw_vals in chart.series:
        vals = list(raw_vals)[:n_points]  # truncate if longer
        while len(vals) < n_points:       # pad with 0 if shorter
            vals.append(0)
        series_values.append(vals)

    # Compute cumulative stacks — cumulative[i][j] = sum of series 0..i at point j
    cum_stacks = []  # cum_stacks[series_idx][point_idx]
    running = [0.0] * n_points
    for s_idx in range(n_series):
        layer = []
        for j in range(n_points):
            running[j] += max(0, series_values[s_idx][j])
            layer.append(running[j])
        cum_stacks.append(layer[:])

    max_val = max(cum_stacks[-1]) if cum_stacks else 0
    if max_val == 0:
        max_val = 1  # avoid division by zero on all-zero data

    # Helper: map (point_index, y_value) → SVG (x, y)
    def px(j):
        if n_points == 1:
            return margin_left + plot_w / 2
        return margin_left + (j / (n_points - 1)) * plot_w

    def py(val):
        return margin_top + plot_h - (max(0, val) / max_val) * plot_h

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                          font_size=14, font_weight="bold"))

    # Y-axis label
    if chart.y_label:
        parts.append(_text(14, margin_top + plot_h / 2, chart.y_label,
                          font_size=10, fill=CCA_COLORS["muted"], anchor="middle",
                          transform=f"rotate(-90, 14, {margin_top + plot_h / 2})"))

    # Y-axis gridlines + labels
    # Force integer display when all data values are whole numbers
    all_integer = max_val == int(max_val)
    for i in range(5):
        val = max_val * i / 4
        y = py(val)
        parts.append(_line(margin_left, y, margin_left + plot_w, y,
                          CCA_COLORS["border"], 0.5))
        if all_integer:
            label = str(int(val)) if val == int(val) else str(int(round(val)))
        else:
            label = str(int(val)) if val == int(val) else f"{val:.1f}"
        parts.append(_text(margin_left - 8, y + 4, label,
                          font_size=9, fill=CCA_COLORS["muted"], anchor="end"))

    # Draw series from top-to-bottom so lower series are painted over higher ones
    baseline_y = margin_top + plot_h  # the x-axis line (y = 0 in data space)

    for s_idx in range(n_series - 1, -1, -1):
        color = chart.colors[s_idx % len(chart.colors)]
        top_ys = [py(cum_stacks[s_idx][j]) for j in range(n_points)]

        if s_idx == 0:
            # Bottom series: lower boundary is the x-axis baseline
            bottom_xs = [px(j) for j in range(n_points)]
            bottom_ys = [baseline_y] * n_points
        else:
            # Lower boundary is the cumulative stack of the series below
            bottom_xs = [px(j) for j in range(n_points)]
            bottom_ys = [py(cum_stacks[s_idx - 1][j]) for j in range(n_points)]

        # Build filled polygon: top edge (left→right) + bottom edge (right→left)
        top_pts = [(px(j), top_ys[j]) for j in range(n_points)]
        bottom_pts = [(bottom_xs[j], bottom_ys[j]) for j in range(n_points - 1, -1, -1)]
        poly_pts = top_pts + bottom_pts
        coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in poly_pts)
        parts.append(
            f'<polygon points="{coords}" fill="{color}" '
            f'fill-opacity="{chart.fill_opacity}" stroke="none"/>\n'
        )

        # Line on top of this series
        parts.append(_polyline(top_pts, color, 2.0))

        # Data points (dots)
        if chart.show_points:
            for x, y in top_pts:
                parts.append(_circle(x, y, 3, color))

    # X-axis labels (thinned for dense data)
    step = max(1, n_points // 10)
    for j in range(n_points):
        if j % step == 0 or j == n_points - 1:
            parts.append(_text(px(j), margin_top + plot_h + 16, str(chart.labels[j]),
                              font_size=9, fill=CCA_COLORS["muted"], anchor="middle"))

    # Legend
    legend_y = chart.height - legend_height + 4
    lx = margin_left
    for s_idx, (name, _) in enumerate(chart.series):
        color = chart.colors[s_idx % len(chart.colors)]
        parts.append(_rect(lx, legend_y, 12, 12, color))
        parts.append(_text(lx + 16, legend_y + 10, name,
                          font_size=9, fill=CCA_COLORS["muted"]))
        lx += max(60, len(name) * 7 + 20)

    parts.append(_svg_footer())
    return "".join(parts)


def _render_grouped_bar_chart(chart: GroupedBarChart) -> str:
    """Render a grouped bar chart to SVG.

    Each category produces a cluster of bars, one per series, arranged
    side-by-side within the cluster. All bars share the same y-axis scale
    (global max across all categories and series).
    """
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
    legend_height = 20

    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom - legend_height

    n_categories = len(chart.data)
    n_series = len(chart.series_names)

    # Global max across all series and categories
    max_val = 0
    for _, values in chart.data:
        for s_idx in range(n_series):
            if s_idx < len(values):
                max_val = max(max_val, max(0, values[s_idx]))
    if max_val == 0:
        max_val = 1

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                          font_size=14, font_weight="bold"))

    # Y-axis label
    if chart.y_label:
        parts.append(_text(14, margin_top + plot_h / 2, chart.y_label,
                          font_size=10, fill=CCA_COLORS["muted"], anchor="middle",
                          transform=f"rotate(-90, 14, {margin_top + plot_h / 2})"))

    # Y-axis gridlines + labels
    # Force integer display when all data values are whole numbers
    all_integer_g = max_val == int(max_val)
    for i in range(5):
        val = max_val * i / 4
        y = margin_top + plot_h - (plot_h * i / 4)
        parts.append(_line(margin_left, y, margin_left + plot_w, y,
                          CCA_COLORS["border"], 0.5))
        if all_integer_g:
            label = str(int(val)) if val == int(val) else str(int(round(val)))
        else:
            label = str(int(val)) if val == int(val) else f"{val:.1f}"
        parts.append(_text(margin_left - 8, y + 4, label,
                          font_size=9, fill=CCA_COLORS["muted"], anchor="end"))

    # Grouped bars
    cluster_w = plot_w / n_categories
    bar_w = cluster_w * 0.8 / max(n_series, 1)
    cluster_gap = cluster_w * 0.1  # left padding within cluster

    for cat_idx, (label, values) in enumerate(chart.data):
        cluster_x = margin_left + cat_idx * cluster_w

        for s_idx in range(n_series):
            val = max(0, values[s_idx]) if s_idx < len(values) else 0
            bar_h = (val / max_val) * plot_h
            bx = cluster_x + cluster_gap + s_idx * bar_w
            by = margin_top + plot_h - bar_h
            color = chart.colors[s_idx % len(chart.colors)]

            parts.append(_rect(bx, by, bar_w * 0.9, bar_h, color, rx=1))

            if chart.show_values and val > 0 and bar_h > 10:
                lbl = str(int(val)) if val == int(val) else f"{val:.1f}"
                parts.append(_text(bx + bar_w * 0.45, by - 3, lbl,
                                  font_size=8, fill=CCA_COLORS["muted"],
                                  anchor="middle"))

        # Category label centered under the cluster
        cx = cluster_x + cluster_w / 2
        parts.append(_text(cx, margin_top + plot_h + 16, str(label),
                          font_size=9, fill=CCA_COLORS["muted"], anchor="middle"))

    # Legend
    legend_y = chart.height - legend_height + 4
    lx = margin_left
    for s_idx, name in enumerate(chart.series_names):
        color = chart.colors[s_idx % len(chart.colors)]
        parts.append(_rect(lx, legend_y, 12, 12, color))
        parts.append(_text(lx + 16, legend_y + 10, name,
                          font_size=9, fill=CCA_COLORS["muted"]))
        lx += max(60, len(name) * 7 + 20)

    parts.append(_svg_footer())
    return "".join(parts)


def _render_waterfall_chart(chart: WaterfallChart) -> str:
    """Render a waterfall chart to SVG."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Layout
    margin_top = 40 if chart.title else 20
    margin_bottom = 40
    margin_left = 55
    margin_right = 20
    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    # Build cumulative running totals
    # Each bar: (label, value, start, end) — bar floats from start to end
    bars = []
    running = 0.0
    for label, value in chart.data:
        start = running
        end = running + value
        running = end
        bars.append((label, value, start, end))

    total = running
    # Add the total bar at the end: spans from 0 to total
    bars.append((chart.total_label, total, 0.0, total))

    # Compute y-axis scale: need to cover all starts/ends including 0
    all_vals = [0.0]
    for _, _, start, end in bars:
        all_vals.extend([start, end])
    y_min = min(all_vals)
    y_max = max(all_vals)
    y_range = y_max - y_min
    if y_range == 0:
        y_range = 1

    def to_svg_y(val: float) -> float:
        """Map a data value to SVG y coordinate (y increases downward)."""
        return margin_top + plot_h - ((val - y_min) / y_range) * plot_h

    # Y-axis gridlines (5 lines)
    for i in range(5):
        val = y_min + (y_range * i / 4)
        y = to_svg_y(val)
        parts.append(_line(margin_left, y, margin_left + plot_w, y,
                           CCA_COLORS["border"], 0.5))
        label_str = str(int(val)) if val == int(val) else f"{val:.1f}"
        parts.append(_text(margin_left - 6, y + 4, label_str,
                           font_size=9, fill=CCA_COLORS["muted"], anchor="end"))

    # Zero line (if y_min < 0 < y_max)
    if y_min < 0 < y_max:
        zero_y = to_svg_y(0)
        parts.append(_line(margin_left, zero_y, margin_left + plot_w, zero_y,
                           CCA_COLORS["muted"], 1))

    # Bars
    n_bars = len(bars)
    bar_slot = plot_w / n_bars
    bar_w = bar_slot * 0.55

    prev_right_x = None
    prev_end_y = None
    is_total_idx = n_bars - 1

    for i, (label, value, start, end) in enumerate(bars):
        is_total = (i == is_total_idx)
        positive = (value >= 0)

        # Color: total bar = accent, positive = success, negative = highlight
        if is_total:
            color = CCA_COLORS["accent"]
        elif positive:
            color = CCA_COLORS["success"]
        else:
            color = CCA_COLORS["highlight"]

        bx = margin_left + i * bar_slot + (bar_slot - bar_w) / 2
        y_start = to_svg_y(start)
        y_end = to_svg_y(end)
        bar_top = min(y_start, y_end)
        bar_bot = max(y_start, y_end)
        bar_h = max(bar_bot - bar_top, 1)

        parts.append(_rect(bx, bar_top, bar_w, bar_h, color, rx=2))

        # Connector line from previous bar's end to this bar's start
        if prev_right_x is not None and prev_end_y is not None and not is_total:
            connector_y = to_svg_y(start)
            parts.append(_line(prev_right_x, connector_y, bx, connector_y,
                               CCA_COLORS["muted"], 0.8))

        # Value label
        if chart.show_values:
            sign = "+" if (value > 0 and not is_total) else ""
            val_str = f"{sign}{int(value)}" if value == int(value) else f"{sign}{value:.1f}"
            label_y = bar_top - 4 if positive else bar_bot + 12
            parts.append(_text(bx + bar_w / 2, label_y, val_str,
                               font_size=9, fill=color, anchor="middle",
                               font_weight="bold"))

        # Category label
        parts.append(_text(bx + bar_w / 2, margin_top + plot_h + 16,
                           str(label), font_size=9, fill=CCA_COLORS["muted"],
                           anchor="middle"))

        prev_right_x = bx + bar_w
        prev_end_y = to_svg_y(end)

    # Axes
    parts.append(_line(margin_left, margin_top, margin_left,
                       margin_top + plot_h, CCA_COLORS["border"]))
    parts.append(_line(margin_left, margin_top + plot_h,
                       margin_left + plot_w, margin_top + plot_h,
                       CCA_COLORS["border"]))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_radar_chart(chart: RadarChart) -> str:
    """Render a radar/spider chart to SVG."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    n_axes = max(3, min(8, len(chart.data)))
    data = chart.data[:n_axes]

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 20, chart.title,
                           font_size=14, font_weight="bold"))

    title_offset = 30 if chart.title else 10
    cx = chart.width / 2
    cy = (chart.height - title_offset) / 2 + title_offset

    # Radius: leave room for axis labels
    label_margin = 40
    r_max = min(chart.width / 2, (chart.height - title_offset) / 2) - label_margin

    # Scale
    max_val = chart.max_value if chart.max_value > 0 else max(v for _, v in data)
    if max_val == 0:
        max_val = 1

    def axis_angle(i: int) -> float:
        """Angle in radians for axis i (0 = top, clockwise)."""
        return math.pi * 2 * i / n_axes - math.pi / 2

    def polar_point(i: int, value: float):
        """SVG (x, y) for axis i at given value (0..max_val)."""
        r = (value / max_val) * r_max
        angle = axis_angle(i)
        return cx + r * math.cos(angle), cy + r * math.sin(angle)

    # Grid circles at 25%, 50%, 75%, 100%
    for pct in [0.25, 0.5, 0.75, 1.0]:
        r = pct * r_max
        pts = []
        for i in range(n_axes):
            angle = axis_angle(i)
            pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        # Polygon for grid
        pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<polygon points="{pts_str}" fill="none" '
                     f'stroke="{CCA_COLORS["border"]}" stroke-width="0.8"/>\n')

    # Axis lines from center to edge
    for i in range(n_axes):
        ex, ey = polar_point(i, max_val)
        parts.append(_line(cx, cy, ex, ey, CCA_COLORS["border"], 0.8))

    # Axis labels
    for i, (label, _) in enumerate(data):
        angle = axis_angle(i)
        lx = cx + (r_max + label_margin * 0.7) * math.cos(angle)
        ly = cy + (r_max + label_margin * 0.7) * math.sin(angle)
        # Determine text anchor based on position
        if abs(math.cos(angle)) < 0.2:
            anchor = "middle"
        elif math.cos(angle) < 0:
            anchor = "end"
        else:
            anchor = "start"
        parts.append(_text(lx, ly + 4, str(label), font_size=10,
                           fill=CCA_COLORS["muted"], anchor=anchor))

    def _draw_series_polygon(series_data: list, color: str, opacity: float):
        pts = []
        for i, (_, value) in enumerate(series_data[:n_axes]):
            px_val, py_val = polar_point(i, max(0, value))
            pts.append((px_val, py_val))
        if not pts:
            return ""
        pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        result = (f'<polygon points="{pts_str}" fill="{color}" '
                  f'fill-opacity="{opacity}" stroke="{color}" '
                  f'stroke-width="2"/>\n')
        # Dots at each vertex
        for px_val, py_val in pts:
            result += _circle(px_val, py_val, 3, color)
        return result

    # Extra series (drawn first, underneath primary)
    for name, s_data, s_color in chart.extra_series:
        parts.append(_draw_series_polygon(s_data, s_color, chart.fill_opacity))

    # Primary series
    parts.append(_draw_series_polygon(data, chart.color, chart.fill_opacity))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_gauge_chart(chart: GaugeChart) -> str:
    """Render a gauge/speedometer chart to SVG."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    # Gauge is always rendered (even with zero value); only "No data" if value is None
    if chart.value is None:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Layout: semicircle centered horizontally, sitting in upper 2/3
    title_h = 30 if chart.title else 10
    cx = chart.width / 2
    arc_margin = 30
    r_outer = min(chart.width / 2 - arc_margin, (chart.height - title_h) * 0.7)
    r_inner = r_outer * 0.65
    cy = title_h + r_outer + 10

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 22, chart.title,
                           font_size=14, font_weight="bold"))

    # Semicircle spans 180° — from 180° to 360° (left to right, across bottom)
    # In SVG coords: angle 0° = right, increases clockwise
    # We want arc from left (180°) to right (0°/360°) going through top
    # Map: arc_start=180°, arc_end=360°
    ARC_START = 180.0
    ARC_SWEEP = 180.0

    low_thresh, high_thresh = chart.thresholds
    val_range = chart.max_value - chart.min_value
    if val_range == 0:
        val_range = 1

    def val_to_angle(v: float) -> float:
        """Map value to SVG angle in degrees (180=left, 360=right)."""
        pct = max(0.0, min(1.0, (v - chart.min_value) / val_range))
        return ARC_START + pct * ARC_SWEEP

    def arc_xy(angle_deg: float, r: float):
        rad = math.radians(angle_deg)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    def arc_segment(a_start: float, a_end: float, color: str) -> str:
        """Draw a filled arc segment (annular sector)."""
        large = 1 if (a_end - a_start) > 180 else 0
        ox1, oy1 = arc_xy(a_start, r_outer)
        ox2, oy2 = arc_xy(a_end, r_outer)
        ix1, iy1 = arc_xy(a_end, r_inner)
        ix2, iy2 = arc_xy(a_start, r_inner)
        d = (f"M {ox1:.1f} {oy1:.1f} "
             f"A {r_outer:.1f} {r_outer:.1f} 0 {large} 1 {ox2:.1f} {oy2:.1f} "
             f"L {ix1:.1f} {iy1:.1f} "
             f"A {r_inner:.1f} {r_inner:.1f} 0 {large} 0 {ix2:.1f} {iy2:.1f} Z")
        return f'<path d="{d}" fill="{color}"/>\n'

    # Zone boundaries in data-value space
    low_angle = val_to_angle(chart.min_value + (low_thresh - chart.min_value)
                             if low_thresh > chart.min_value else low_thresh)
    high_angle = val_to_angle(chart.min_value + (high_thresh - chart.min_value)
                              if high_thresh > chart.min_value else high_thresh)

    # Recompute using percentage thresholds relative to min/max
    low_pct = (low_thresh - chart.min_value) / val_range
    high_pct = (high_thresh - chart.min_value) / val_range
    low_angle = ARC_START + low_pct * ARC_SWEEP
    high_angle = ARC_START + high_pct * ARC_SWEEP

    # Draw three color zones: red / yellow / green
    parts.append(arc_segment(ARC_START, low_angle, CCA_COLORS["highlight"]))
    parts.append(arc_segment(low_angle, high_angle, CCA_COLORS["warning"]))
    parts.append(arc_segment(high_angle, ARC_START + ARC_SWEEP, CCA_COLORS["success"]))

    # Thin border ring
    ox_left, oy_left = arc_xy(ARC_START, r_outer)
    ox_right, oy_right = arc_xy(ARC_START + ARC_SWEEP, r_outer)
    ix_right, iy_right = arc_xy(ARC_START + ARC_SWEEP, r_inner)
    ix_left, iy_left = arc_xy(ARC_START, r_inner)
    parts.append(f'<path d="M {ox_left:.1f} {oy_left:.1f} '
                 f'A {r_outer:.1f} {r_outer:.1f} 0 1 1 {ox_right:.1f} {oy_right:.1f}" '
                 f'fill="none" stroke="{CCA_COLORS["border"]}" stroke-width="1"/>\n')

    # Min/max markers
    parts.append(_text(cx - r_outer - 5, cy + 16,
                       str(int(chart.min_value) if chart.min_value == int(chart.min_value)
                           else f"{chart.min_value:.1f}"),
                       font_size=9, fill=CCA_COLORS["muted"], anchor="end"))
    parts.append(_text(cx + r_outer + 5, cy + 16,
                       str(int(chart.max_value) if chart.max_value == int(chart.max_value)
                           else f"{chart.max_value:.1f}"),
                       font_size=9, fill=CCA_COLORS["muted"], anchor="start"))

    # Needle
    needle_angle = val_to_angle(max(chart.min_value, min(chart.max_value, chart.value)))
    needle_len = r_inner * 0.9
    nx, ny = arc_xy(needle_angle, needle_len)
    parts.append(_line(cx, cy, nx, ny, CCA_COLORS["primary"], 2.5))
    parts.append(_circle(cx, cy, 5, CCA_COLORS["primary"]))

    # Center value text
    val_str = (str(int(chart.value)) if chart.value == int(chart.value)
               else f"{chart.value:.1f}")
    parts.append(_text(cx, cy + 30, val_str, font_size=22,
                       fill=CCA_COLORS["primary"], font_weight="bold"))

    # Sub-label
    if chart.label:
        parts.append(_text(cx, cy + 50, chart.label, font_size=11,
                           fill=CCA_COLORS["muted"]))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_bubble_chart(chart: BubbleChart) -> str:
    """Render a bubble chart to SVG."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Layout
    margin_top = 40 if chart.title else 20
    margin_bottom = 50 if chart.x_label else 35
    margin_left = 60 if chart.y_label else 50
    margin_right = 20
    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    # Parse data — handle optional color
    parsed = []
    for item in chart.data:
        if len(item) == 5:
            label, x, y, size, color = item
        else:
            label, x, y, size = item
            color = SERIES_PALETTE[len(parsed) % len(SERIES_PALETTE)]
        parsed.append((label, float(x), float(y), float(size), color))

    if not parsed:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Scale
    xs = [p[1] for p in parsed]
    ys = [p[2] for p in parsed]
    sizes = [p[3] for p in parsed]

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    s_min, s_max = min(sizes), max(sizes)

    # Add padding to ranges
    x_range = x_max - x_min if x_max != x_min else 1
    y_range = y_max - y_min if y_max != y_min else 1
    s_range = s_max - s_min if s_max != s_min else 1

    x_min -= x_range * 0.05
    x_max += x_range * 0.05
    y_min -= y_range * 0.05
    y_max += y_range * 0.05

    def scale_x(v):
        return margin_left + ((v - x_min) / (x_max - x_min)) * plot_w

    def scale_y(v):
        return margin_top + plot_h - ((v - y_min) / (y_max - y_min)) * plot_h

    def scale_r(v):
        if s_range == 0:
            return (chart.min_radius + chart.max_radius) / 2
        t = (v - s_min) / s_range
        return chart.min_radius + t * (chart.max_radius - chart.min_radius)

    # Axes
    parts.append(f'<line x1="{margin_left}" y1="{margin_top + plot_h}" '
                 f'x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" '
                 f'stroke="{CCA_COLORS["border"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top}" '
                 f'x2="{margin_left}" y2="{margin_top + plot_h}" '
                 f'stroke="{CCA_COLORS["border"]}" stroke-width="1"/>')

    # Y-axis labels (5 ticks)
    for i in range(6):
        val = y_min + (y_max - y_min) * i / 5
        yp = scale_y(val)
        label_text = str(int(val)) if val == int(val) else f"{val:.1f}"
        parts.append(_text(margin_left - 8, yp + 3, label_text,
                           font_size=8, fill=CCA_COLORS["muted"], anchor="end"))
        if i > 0:
            parts.append(f'<line x1="{margin_left}" y1="{yp}" '
                         f'x2="{margin_left + plot_w}" y2="{yp}" '
                         f'stroke="{CCA_COLORS["border"]}" stroke-width="0.5" '
                         f'stroke-dasharray="3,3"/>')

    # X-axis labels (5 ticks)
    for i in range(6):
        val = x_min + (x_max - x_min) * i / 5
        xp = scale_x(val)
        label_text = str(int(val)) if val == int(val) else f"{val:.1f}"
        parts.append(_text(xp, margin_top + plot_h + 15, label_text,
                           font_size=8, fill=CCA_COLORS["muted"]))

    # Axis labels
    if chart.x_label:
        parts.append(_text(margin_left + plot_w / 2, chart.height - 8,
                           chart.x_label, font_size=9, fill=CCA_COLORS["muted"]))
    if chart.y_label:
        parts.append(f'<text x="14" y="{margin_top + plot_h / 2}" '
                     f'text-anchor="middle" font-size="9" '
                     f'font-family="sans-serif" fill="{CCA_COLORS["muted"]}" '
                     f'transform="rotate(-90, 14, {margin_top + plot_h / 2})">'
                     f'{_escape(chart.y_label)}</text>')

    # Bubbles (draw largest first so small bubbles aren't hidden)
    sorted_parsed = sorted(parsed, key=lambda p: p[3], reverse=True)
    for label, x, y, size, color in sorted_parsed:
        cx = scale_x(x)
        cy = scale_y(y)
        r = scale_r(size)
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                     f'fill="{color}" fill-opacity="0.7" '
                     f'stroke="{color}" stroke-width="1"/>')
        # Label
        if r >= 15:
            parts.append(_text(cx, cy + 3, label, font_size=7,
                               fill="#ffffff", font_weight="bold"))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_treemap_chart(chart: TreemapChart) -> str:
    """Render a treemap chart to SVG using simple squarified layout."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Title
    margin_top = 35 if chart.title else 5
    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    # Parse data
    parsed = []
    for item in chart.data:
        if len(item) == 3:
            label, value, color = item
        else:
            label, value = item
            color = SERIES_PALETTE[len(parsed) % len(SERIES_PALETTE)]
        if value > 0:
            parsed.append((label, float(value), color))

    if not parsed:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Sort by value descending
    parsed.sort(key=lambda p: p[1], reverse=True)
    total = sum(p[1] for p in parsed)

    # Simple slice-and-dice layout (alternating horizontal/vertical splits)
    plot_x = 5
    plot_y = margin_top
    plot_w = chart.width - 10
    plot_h = chart.height - margin_top - 5

    def _layout_rects(items, x, y, w, h, horizontal=True):
        """Recursively layout rectangles using slice-and-dice."""
        if not items:
            return []
        if len(items) == 1:
            return [(items[0][0], items[0][2], x, y, w, h)]

        item_total = sum(it[1] for it in items)
        if item_total == 0:
            return []

        # Split items into two groups of roughly equal total value
        half = item_total / 2
        running = 0
        split_idx = 0
        for i, (_, val, _) in enumerate(items):
            running += val
            if running >= half:
                split_idx = i + 1
                break
        split_idx = max(1, min(split_idx, len(items) - 1))

        left_items = items[:split_idx]
        right_items = items[split_idx:]
        left_total = sum(it[1] for it in left_items)
        ratio = left_total / item_total if item_total > 0 else 0.5

        rects = []
        if horizontal:
            split_w = w * ratio
            rects.extend(_layout_rects(left_items, x, y, split_w, h, not horizontal))
            rects.extend(_layout_rects(right_items, x + split_w, y, w - split_w, h, not horizontal))
        else:
            split_h = h * ratio
            rects.extend(_layout_rects(left_items, x, y, w, split_h, not horizontal))
            rects.extend(_layout_rects(right_items, x, y + split_h, w, h - split_h, not horizontal))

        return rects

    rects = _layout_rects(parsed, plot_x, plot_y, plot_w, plot_h)

    for label, color, rx, ry, rw, rh in rects:
        # Rectangle with gap
        gap = 1.5
        parts.append(_rect(rx + gap, ry + gap, max(0, rw - 2 * gap),
                           max(0, rh - 2 * gap), color, rx=3))

        # Label (only if rectangle is large enough)
        if rw > 40 and rh > 20:
            # Determine text color based on background luminance
            text_color = "#ffffff"
            # Find value for this label
            val = next((v for l, v, _ in parsed if l == label), 0)
            pct = (val / total * 100) if total > 0 else 0

            font_size = min(11, max(7, min(rw, rh) / 5))
            parts.append(_text(rx + rw / 2, ry + rh / 2 - 2, label,
                               font_size=font_size, fill=text_color,
                               font_weight="bold"))
            if rh > 35:
                parts.append(_text(rx + rw / 2, ry + rh / 2 + 12,
                                   f"{pct:.0f}%", font_size=max(7, font_size - 1),
                                   fill=text_color))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_sankey_chart(chart: SankeyChart) -> str:
    """Render a Sankey flow diagram to SVG.

    Nodes are arranged in columns by topological stage. Flows are drawn as
    curved bands (cubic bezier paths) connecting source to target nodes,
    with band thickness proportional to flow value.
    """
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    # Filter valid flows (skip self-loops, zero values)
    valid_flows = [
        (src, tgt, float(val))
        for src, tgt, val in chart.flows
        if src != tgt and float(val) > 0
    ]

    if not valid_flows:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Title
    margin_top = 40 if chart.title else 15
    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    margin_bottom = 15
    margin_left = 80
    margin_right = 80
    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom

    # --- Build node graph and assign columns via topological ordering ---
    all_nodes = set()
    sources_of = {}  # node -> set of nodes that flow INTO it
    targets_of = {}  # node -> set of nodes it flows TO
    for src, tgt, _ in valid_flows:
        all_nodes.add(src)
        all_nodes.add(tgt)
        targets_of.setdefault(src, set()).add(tgt)
        sources_of.setdefault(tgt, set()).add(src)

    # Assign columns: BFS from pure sources (nodes with no incoming flows)
    pure_sources = [n for n in all_nodes if n not in sources_of]
    if not pure_sources:
        # Cyclic — just pick alphabetically first
        pure_sources = [sorted(all_nodes)[0]]

    node_col = {}
    queue = [(n, 0) for n in pure_sources]
    visited = set()
    while queue:
        node, col = queue.pop(0)
        if node in visited:
            node_col[node] = max(node_col.get(node, 0), col)
            continue
        visited.add(node)
        node_col[node] = max(node_col.get(node, 0), col)
        for tgt in targets_of.get(node, []):
            queue.append((tgt, col + 1))

    # Ensure all nodes are assigned
    for n in all_nodes:
        if n not in node_col:
            node_col[n] = 0

    max_col = max(node_col.values()) if node_col else 0

    # Group nodes by column
    columns = {}
    for node, col in node_col.items():
        columns.setdefault(col, []).append(node)
    for col in columns:
        columns[col].sort()

    # Calculate node values (total flow through each node)
    node_out = {}
    node_in = {}
    for src, tgt, val in valid_flows:
        node_out[src] = node_out.get(src, 0) + val
        node_in[tgt] = node_in.get(tgt, 0) + val
    node_value = {n: max(node_out.get(n, 0), node_in.get(n, 0)) for n in all_nodes}

    # --- Layout: compute x and y positions ---
    num_cols = max_col + 1
    if num_cols == 1:
        col_x = {0: margin_left}
    else:
        col_spacing = (plot_w - chart.node_width) / (num_cols - 1)
        col_x = {c: margin_left + c * col_spacing for c in range(num_cols)}

    # For each column, distribute nodes vertically proportional to value
    node_y = {}  # node -> (y_top, height)
    max_total = max(
        (sum(node_value[n] for n in columns.get(c, [])) for c in range(num_cols)),
        default=1,
    )
    if max_total == 0:
        max_total = 1

    for col_idx in range(num_cols):
        nodes = columns.get(col_idx, [])
        col_total = sum(node_value[n] for n in nodes)
        padding_total = chart.node_padding * max(0, len(nodes) - 1)
        available_h = plot_h - padding_total

        y_cursor = margin_top
        for node in nodes:
            frac = node_value[node] / col_total if col_total > 0 else 1.0 / max(len(nodes), 1)
            h = max(4, frac * available_h)
            node_y[node] = (y_cursor, h)
            y_cursor += h + chart.node_padding

    # Assign colors to nodes
    node_color = {}
    color_idx = 0
    for col_idx in range(num_cols):
        for node in columns.get(col_idx, []):
            if node in chart.node_colors:
                node_color[node] = chart.node_colors[node]
            else:
                node_color[node] = SERIES_PALETTE[color_idx % len(SERIES_PALETTE)]
                color_idx += 1

    # --- Draw flow bands (curved paths) ---
    # Track how much of each node's vertical space has been used for outgoing/incoming
    out_offset = {n: 0.0 for n in all_nodes}
    in_offset = {n: 0.0 for n in all_nodes}

    for src, tgt, val in valid_flows:
        src_y_top, src_h = node_y[src]
        tgt_y_top, tgt_h = node_y[tgt]

        src_total = node_out.get(src, 1)
        tgt_total = node_in.get(tgt, 1)

        band_h_src = (val / src_total) * src_h if src_total > 0 else src_h
        band_h_tgt = (val / tgt_total) * tgt_h if tgt_total > 0 else tgt_h

        src_col = node_col[src]
        tgt_col = node_col[tgt]

        x0 = col_x[src_col] + chart.node_width
        x1 = col_x[tgt_col]

        y0_top = src_y_top + out_offset[src]
        y0_bot = y0_top + band_h_src
        y1_top = tgt_y_top + in_offset[tgt]
        y1_bot = y1_top + band_h_tgt

        out_offset[src] += band_h_src
        in_offset[tgt] += band_h_tgt

        # Cubic bezier control points for smooth curve
        cx = (x0 + x1) / 2
        color = node_color[src]

        path_d = (
            f"M {x0:.1f} {y0_top:.1f} "
            f"C {cx:.1f} {y0_top:.1f}, {cx:.1f} {y1_top:.1f}, {x1:.1f} {y1_top:.1f} "
            f"L {x1:.1f} {y1_bot:.1f} "
            f"C {cx:.1f} {y1_bot:.1f}, {cx:.1f} {y0_bot:.1f}, {x0:.1f} {y0_bot:.1f} Z"
        )
        parts.append(f'<path d="{path_d}" fill="{color}" opacity="0.35"/>\n')

    # --- Draw node rectangles ---
    for node in all_nodes:
        col_idx = node_col[node]
        x = col_x[col_idx]
        y_top, h = node_y[node]
        color = node_color[node]
        parts.append(_rect(x, y_top, chart.node_width, h, color, rx=2))

    # --- Draw node labels ---
    for node in all_nodes:
        col_idx = node_col[node]
        x = col_x[col_idx]
        y_top, h = node_y[node]

        if col_idx == 0:
            # Left column: label to the left
            parts.append(_text(x - 5, y_top + h / 2 + 4, str(node),
                               font_size=10, fill=CCA_COLORS["primary"],
                               anchor="end"))
        elif col_idx == max_col:
            # Right column: label to the right
            parts.append(_text(x + chart.node_width + 5, y_top + h / 2 + 4,
                               str(node), font_size=10,
                               fill=CCA_COLORS["primary"], anchor="start"))
        else:
            # Middle column: label above
            parts.append(_text(x + chart.node_width / 2, y_top - 4, str(node),
                               font_size=10, fill=CCA_COLORS["primary"],
                               anchor="middle"))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_funnel_chart(chart: FunnelChart) -> str:
    """Render a funnel chart to SVG."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    base_color = chart.color or CCA_COLORS["accent"]

    # Layout
    margin_top = 40 if chart.title else 16
    margin_bottom = 16
    margin_left = 90   # room for stage labels on the left
    margin_right = 70  # room for value labels on the right
    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    n = len(chart.data)
    top_value = chart.data[0][1] if chart.data else 1

    slot_h = plot_h / n
    bar_h = max(slot_h * 0.72, 8)   # height of each trapezoid
    gap_h = slot_h - bar_h           # vertical gap between stages

    for i, (label, value) in enumerate(chart.data):
        # Width fraction relative to first (top) stage
        frac = (value / top_value) if top_value > 0 else 0.0
        frac = max(0.0, min(1.0, frac))

        bar_w = max(plot_w * frac, 4)
        bar_x = margin_left + (plot_w - bar_w) / 2
        bar_y = margin_top + i * slot_h + gap_h / 2

        # Slight color darkening for deeper stages (lerp toward primary)
        t = i / max(n - 1, 1) * 0.35
        fill = _lerp_color(base_color, CCA_COLORS["primary"], t)

        # Trapezoid: if not last, taper toward next stage's width
        if i < n - 1:
            next_frac = (chart.data[i + 1][1] / top_value) if top_value > 0 else 0.0
            next_frac = max(0.0, min(1.0, next_frac))
            next_w = max(plot_w * next_frac, 4)
            next_x = margin_left + (plot_w - next_w) / 2

            pts = [
                (bar_x, bar_y),
                (bar_x + bar_w, bar_y),
                (next_x + next_w, bar_y + bar_h),
                (next_x, bar_y + bar_h),
            ]
        else:
            # Last stage: simple rectangle
            pts = [
                (bar_x, bar_y),
                (bar_x + bar_w, bar_y),
                (bar_x + bar_w, bar_y + bar_h),
                (bar_x, bar_y + bar_h),
            ]

        pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<polygon points="{pts_str}" fill="{fill}"/>\n')

        # Stage label (left side, vertically centered on bar)
        label_y = bar_y + bar_h / 2 + 4
        parts.append(_text(margin_left - 6, label_y, label,
                           font_size=10, fill=CCA_COLORS["primary"], anchor="end"))

        # Value label (right side)
        val_str = str(int(value)) if value == int(value) else f"{value:.1f}"
        parts.append(_text(margin_left + plot_w + 6, label_y, val_str,
                           font_size=10, fill=CCA_COLORS["primary"], anchor="start"))

        # Percentage label (inside bar, centered)
        if chart.show_percentages:
            pct = round(frac * 100)
            pct_str = f"{pct}%"
            if bar_w > 30:
                parts.append(_text(margin_left + plot_w / 2, label_y, pct_str,
                                   font_size=10, fill=CCA_COLORS["background"],
                                   font_weight="bold"))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_scatter_plot(chart: ScatterPlot) -> str:
    """Render a scatter plot to SVG with optional trend lines."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.series:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Layout
    margin_top = 40 if chart.title else 20
    margin_bottom = 50 if chart.x_label else 35
    margin_left = 60 if chart.y_label else 50
    margin_right = 20
    # Reserve space for legend if multiple series
    has_legend = len(chart.series) > 1
    if has_legend:
        margin_right = 120
    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    # Collect all points to find global range
    all_x = []
    all_y = []
    parsed_series = []
    for i, s in enumerate(chart.series):
        name = s.get("name", f"Series {i + 1}")
        points = s.get("points", [])
        color = s.get("color", SERIES_PALETTE[i % len(SERIES_PALETTE)])
        pts = [(float(p[0]), float(p[1])) for p in points]
        parsed_series.append((name, pts, color))
        for x, y in pts:
            all_x.append(x)
            all_y.append(y)

    if not all_x:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = min(all_y), max(all_y)

    # Add padding to ranges
    x_range = x_max - x_min if x_max != x_min else 1
    y_range = y_max - y_min if y_max != y_min else 1
    x_min -= x_range * 0.05
    x_max += x_range * 0.05
    y_min -= y_range * 0.05
    y_max += y_range * 0.05

    def sx(v):
        return margin_left + ((v - x_min) / (x_max - x_min)) * plot_w

    def sy(v):
        return margin_top + plot_h - ((v - y_min) / (y_max - y_min)) * plot_h

    # Axes
    parts.append(f'<line x1="{margin_left}" y1="{margin_top + plot_h}" '
                 f'x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" '
                 f'stroke="{CCA_COLORS["border"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top}" '
                 f'x2="{margin_left}" y2="{margin_top + plot_h}" '
                 f'stroke="{CCA_COLORS["border"]}" stroke-width="1"/>')

    # Y-axis ticks (6 values)
    for i in range(6):
        val = y_min + (y_max - y_min) * i / 5
        yp = sy(val)
        label_text = str(int(val)) if val == int(val) else f"{val:.1f}"
        parts.append(_text(margin_left - 8, yp + 3, label_text,
                           font_size=8, fill=CCA_COLORS["muted"], anchor="end"))
        if i > 0:
            parts.append(f'<line x1="{margin_left}" y1="{yp}" '
                         f'x2="{margin_left + plot_w}" y2="{yp}" '
                         f'stroke="{CCA_COLORS["border"]}" stroke-width="0.5" '
                         f'stroke-dasharray="3,3"/>')

    # X-axis ticks (6 values)
    for i in range(6):
        val = x_min + (x_max - x_min) * i / 5
        xp = sx(val)
        label_text = str(int(val)) if val == int(val) else f"{val:.1f}"
        parts.append(_text(xp, margin_top + plot_h + 15, label_text,
                           font_size=8, fill=CCA_COLORS["muted"]))

    # Axis labels
    if chart.x_label:
        parts.append(_text(margin_left + plot_w / 2, chart.height - 8,
                           chart.x_label, font_size=9, fill=CCA_COLORS["muted"]))
    if chart.y_label:
        parts.append(f'<text x="14" y="{margin_top + plot_h / 2}" '
                     f'text-anchor="middle" font-size="9" '
                     f'font-family="sans-serif" fill="{CCA_COLORS["muted"]}" '
                     f'transform="rotate(-90, 14, {margin_top + plot_h / 2})">'
                     f'{_escape(chart.y_label)}</text>')

    # Render each series
    for si, (name, pts, color) in enumerate(parsed_series):
        # Trend line (least-squares linear regression)
        if chart.show_trend and len(pts) >= 2:
            n = len(pts)
            sum_x = sum(p[0] for p in pts)
            sum_y = sum(p[1] for p in pts)
            sum_xy = sum(p[0] * p[1] for p in pts)
            sum_x2 = sum(p[0] ** 2 for p in pts)
            denom = n * sum_x2 - sum_x ** 2
            if abs(denom) > 1e-10:
                slope = (n * sum_xy - sum_x * sum_y) / denom
                intercept = (sum_y - slope * sum_x) / n
                # Draw line across the plot range
                lx1 = x_min
                lx2 = x_max
                ly1 = slope * lx1 + intercept
                ly2 = slope * lx2 + intercept
                parts.append(f'<line x1="{sx(lx1):.1f}" y1="{sy(ly1):.1f}" '
                             f'x2="{sx(lx2):.1f}" y2="{sy(ly2):.1f}" '
                             f'stroke="{color}" stroke-width="1.5" '
                             f'stroke-dasharray="6,3" stroke-opacity="0.6"/>')

        # Points
        for x, y in pts:
            parts.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" '
                         f'r="{chart.point_radius}" '
                         f'fill="{color}" fill-opacity="0.8" '
                         f'stroke="{color}" stroke-width="1"/>')

    # Legend (if multiple series)
    if has_legend:
        lx = margin_left + plot_w + 15
        ly = margin_top + 10
        for si, (name, pts, color) in enumerate(parsed_series):
            parts.append(f'<circle cx="{lx + 5}" cy="{ly - 3}" r="4" fill="{color}"/>')
            parts.append(_text(lx + 14, ly, name, font_size=8,
                               fill=CCA_COLORS["primary"], anchor="start"))
            ly += 16

    parts.append(_svg_footer())
    return "".join(parts)


def _render_box_plot(chart: BoxPlot) -> str:
    """Render a box-and-whisker plot to SVG."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Layout
    margin_top = 40 if chart.title else 20
    margin_bottom = 45
    margin_left = 60 if chart.y_label else 50
    margin_right = 20
    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    base_color = chart.color if chart.color else CCA_COLORS["accent"]

    # Compute stats for each category
    stats = []
    all_vals = []
    for item in chart.data:
        label = item[0]
        values = sorted([float(v) for v in item[1]])
        if not values:
            continue
        n = len(values)
        q1_idx = n * 0.25
        q2_idx = n * 0.5
        q3_idx = n * 0.75

        def percentile(vals, p):
            k = (len(vals) - 1) * p
            f = int(k)
            c = f + 1 if f + 1 < len(vals) else f
            d = k - f
            return vals[f] + d * (vals[c] - vals[f])

        q1 = percentile(values, 0.25)
        median = percentile(values, 0.5)
        q3 = percentile(values, 0.75)
        iqr = q3 - q1
        whisker_lo = max(min(values), q1 - 1.5 * iqr)
        whisker_hi = min(max(values), q3 + 1.5 * iqr)
        # Find actual whisker endpoints (nearest data point within range)
        whisker_lo = min(v for v in values if v >= q1 - 1.5 * iqr)
        whisker_hi = max(v for v in values if v <= q3 + 1.5 * iqr)
        outliers = [v for v in values if v < whisker_lo or v > whisker_hi]
        stats.append((label, q1, median, q3, whisker_lo, whisker_hi, outliers))
        all_vals.extend(values)

    if not stats:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Y scale
    y_min = min(all_vals)
    y_max = max(all_vals)
    y_range = y_max - y_min if y_max != y_min else 1
    y_min -= y_range * 0.08
    y_max += y_range * 0.08

    def sy(v):
        return margin_top + plot_h - ((v - y_min) / (y_max - y_min)) * plot_h

    # Axes
    parts.append(f'<line x1="{margin_left}" y1="{margin_top + plot_h}" '
                 f'x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" '
                 f'stroke="{CCA_COLORS["border"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top}" '
                 f'x2="{margin_left}" y2="{margin_top + plot_h}" '
                 f'stroke="{CCA_COLORS["border"]}" stroke-width="1"/>')

    # Y-axis ticks
    for i in range(6):
        val = y_min + (y_max - y_min) * i / 5
        yp = sy(val)
        label_text = str(int(val)) if val == int(val) else f"{val:.1f}"
        parts.append(_text(margin_left - 8, yp + 3, label_text,
                           font_size=8, fill=CCA_COLORS["muted"], anchor="end"))
        if i > 0:
            parts.append(f'<line x1="{margin_left}" y1="{yp}" '
                         f'x2="{margin_left + plot_w}" y2="{yp}" '
                         f'stroke="{CCA_COLORS["border"]}" stroke-width="0.5" '
                         f'stroke-dasharray="3,3"/>')

    # Y-axis label
    if chart.y_label:
        parts.append(f'<text x="14" y="{margin_top + plot_h / 2}" '
                     f'text-anchor="middle" font-size="9" '
                     f'font-family="sans-serif" fill="{CCA_COLORS["muted"]}" '
                     f'transform="rotate(-90, 14, {margin_top + plot_h / 2})">'
                     f'{_escape(chart.y_label)}</text>')

    # Draw boxes
    n_cats = len(stats)
    cat_w = plot_w / n_cats
    box_w = min(cat_w * 0.5, 60)

    for i, (label, q1, median, q3, wlo, whi, outliers) in enumerate(stats):
        cx = margin_left + cat_w * i + cat_w / 2
        bx = cx - box_w / 2

        # Whisker lines (vertical thin line)
        parts.append(f'<line x1="{cx:.1f}" y1="{sy(whi):.1f}" '
                     f'x2="{cx:.1f}" y2="{sy(q3):.1f}" '
                     f'stroke="{CCA_COLORS["primary"]}" stroke-width="1"/>')
        parts.append(f'<line x1="{cx:.1f}" y1="{sy(q1):.1f}" '
                     f'x2="{cx:.1f}" y2="{sy(wlo):.1f}" '
                     f'stroke="{CCA_COLORS["primary"]}" stroke-width="1"/>')

        # Whisker caps (horizontal)
        cap_w = box_w * 0.4
        parts.append(f'<line x1="{cx - cap_w / 2:.1f}" y1="{sy(whi):.1f}" '
                     f'x2="{cx + cap_w / 2:.1f}" y2="{sy(whi):.1f}" '
                     f'stroke="{CCA_COLORS["primary"]}" stroke-width="1"/>')
        parts.append(f'<line x1="{cx - cap_w / 2:.1f}" y1="{sy(wlo):.1f}" '
                     f'x2="{cx + cap_w / 2:.1f}" y2="{sy(wlo):.1f}" '
                     f'stroke="{CCA_COLORS["primary"]}" stroke-width="1"/>')

        # Box (Q1 to Q3)
        box_y = sy(q3)
        box_h = sy(q1) - sy(q3)
        parts.append(f'<rect x="{bx:.1f}" y="{box_y:.1f}" '
                     f'width="{box_w:.1f}" height="{max(box_h, 1):.1f}" '
                     f'fill="{base_color}" fill-opacity="0.3" '
                     f'stroke="{base_color}" stroke-width="1.5"/>')

        # Median line
        parts.append(f'<line x1="{bx:.1f}" y1="{sy(median):.1f}" '
                     f'x2="{bx + box_w:.1f}" y2="{sy(median):.1f}" '
                     f'stroke="{CCA_COLORS["highlight"]}" stroke-width="2"/>')

        # Outliers
        if chart.show_outliers:
            for ov in outliers:
                parts.append(f'<circle cx="{cx:.1f}" cy="{sy(ov):.1f}" r="3" '
                             f'fill="none" stroke="{CCA_COLORS["highlight"]}" '
                             f'stroke-width="1.5"/>')

        # Category label
        parts.append(_text(cx, margin_top + plot_h + 15, label,
                           font_size=9, fill=CCA_COLORS["primary"]))

    parts.append(_svg_footer())
    return "".join(parts)


def _render_histogram_chart(chart: HistogramChart) -> str:
    """Render a histogram to SVG."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    vals = [float(v) for v in chart.values]
    if not vals:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Layout
    margin_top = 40 if chart.title else 20
    margin_bottom = 50 if chart.x_label else 40
    margin_left = 60 if chart.y_label else 50
    margin_right = 20
    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom

    # Title
    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    base_color = chart.color if chart.color else CCA_COLORS["accent"]

    # Determine bins
    n_bins = chart.bins
    if n_bins <= 0:
        # Sturges' rule: ceil(1 + log2(n))
        n_bins = max(1, int(math.ceil(1 + math.log2(len(vals)))) if len(vals) > 1 else 1)

    v_min = min(vals)
    v_max = max(vals)
    v_range = v_max - v_min if v_max != v_min else 1
    bin_width = v_range / n_bins

    # Count values per bin
    counts = [0] * n_bins
    for v in vals:
        idx = int((v - v_min) / bin_width)
        if idx >= n_bins:
            idx = n_bins - 1
        counts[idx] = counts[idx] + 1

    max_count = max(counts) if counts else 1

    # Y scale
    def sy(count):
        return margin_top + plot_h - (count / max_count) * plot_h

    # Axes
    parts.append(f'<line x1="{margin_left}" y1="{margin_top + plot_h}" '
                 f'x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" '
                 f'stroke="{CCA_COLORS["border"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top}" '
                 f'x2="{margin_left}" y2="{margin_top + plot_h}" '
                 f'stroke="{CCA_COLORS["border"]}" stroke-width="1"/>')

    # Y-axis ticks (5 values) — counts are always integers
    for i in range(6):
        val = max_count * i / 5
        yp = sy(val)
        label_text = str(int(round(val)))
        parts.append(_text(margin_left - 8, yp + 3, label_text,
                           font_size=8, fill=CCA_COLORS["muted"], anchor="end"))
        if i > 0:
            parts.append(f'<line x1="{margin_left}" y1="{yp}" '
                         f'x2="{margin_left + plot_w}" y2="{yp}" '
                         f'stroke="{CCA_COLORS["border"]}" stroke-width="0.5" '
                         f'stroke-dasharray="3,3"/>')

    # Y-axis label
    if chart.y_label:
        parts.append(f'<text x="14" y="{margin_top + plot_h / 2}" '
                     f'text-anchor="middle" font-size="9" '
                     f'font-family="sans-serif" fill="{CCA_COLORS["muted"]}" '
                     f'transform="rotate(-90, 14, {margin_top + plot_h / 2})">'
                     f'{_escape(chart.y_label)}</text>')

    # X-axis label
    if chart.x_label:
        parts.append(_text(margin_left + plot_w / 2, chart.height - 8,
                           chart.x_label, font_size=9, fill=CCA_COLORS["muted"]))

    # Bars (no gap — histogram bars are contiguous)
    bar_w = plot_w / n_bins
    for i, count in enumerate(counts):
        if count == 0:
            continue
        bx = margin_left + i * bar_w
        by = sy(count)
        bh = margin_top + plot_h - by
        parts.append(f'<rect x="{bx:.1f}" y="{by:.1f}" '
                     f'width="{bar_w:.1f}" height="{bh:.1f}" '
                     f'fill="{base_color}" fill-opacity="0.8" '
                     f'stroke="{CCA_COLORS["background"]}" stroke-width="0.5"/>')

    # X-axis tick labels (bin edges)
    # Detect all-integer input data — show integer bin edges
    all_int_data = all(v == int(v) for v in vals)
    max_labels = min(n_bins + 1, 8)
    step = max(1, (n_bins + 1) // max_labels)
    for i in range(0, n_bins + 1, step):
        val = v_min + i * bin_width
        xp = margin_left + i * bar_w
        if all_int_data:
            label_text = str(int(round(val)))
        else:
            label_text = str(int(val)) if val == int(val) else f"{val:.1f}"
        parts.append(_text(xp, margin_top + plot_h + 15, label_text,
                           font_size=8, fill=CCA_COLORS["muted"]))

    parts.append(_svg_footer())
    return "".join(parts)


def _gaussian_kde(values, grid, bandwidth):
    """Compute Gaussian KDE on a grid. Returns density values."""
    n = len(values)
    densities = []
    coeff = 1.0 / (n * bandwidth * math.sqrt(2 * math.pi))
    for x in grid:
        total = 0.0
        for v in values:
            z = (x - v) / bandwidth
            total += math.exp(-0.5 * z * z)
        densities.append(coeff * total)
    return densities


def _render_violin_plot(chart: ViolinPlot) -> str:
    """Render a violin plot to SVG."""
    parts = [_svg_header(chart.width, chart.height)]
    parts.append(_rect(0, 0, chart.width, chart.height, CCA_COLORS["background"]))

    if not chart.data:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Layout
    margin_top = 40 if chart.title else 20
    margin_bottom = 45
    margin_left = 60 if chart.y_label else 50
    margin_right = 20
    plot_w = chart.width - margin_left - margin_right
    plot_h = chart.height - margin_top - margin_bottom

    if chart.title:
        parts.append(_text(chart.width / 2, 24, chart.title,
                           font_size=14, font_weight="bold"))

    base_color = chart.color if chart.color else CCA_COLORS["accent"]

    # Filter categories with actual values
    categories = []
    all_vals = []
    for item in chart.data:
        label = item[0]
        values = sorted([float(v) for v in item[1]])
        if values:
            categories.append((label, values))
            all_vals.extend(values)

    if not categories:
        parts.append(_text(chart.width / 2, chart.height / 2, "No data",
                           font_size=14, fill=CCA_COLORS["muted"]))
        parts.append(_svg_footer())
        return "".join(parts)

    # Y scale (global across all categories)
    y_min = min(all_vals)
    y_max = max(all_vals)
    y_range = y_max - y_min if y_max != y_min else 1
    y_min -= y_range * 0.08
    y_max += y_range * 0.08

    def sy(v):
        return margin_top + plot_h - ((v - y_min) / (y_max - y_min)) * plot_h

    # Axes
    parts.append(f'<line x1="{margin_left}" y1="{margin_top + plot_h}" '
                 f'x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" '
                 f'stroke="{CCA_COLORS["border"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top}" '
                 f'x2="{margin_left}" y2="{margin_top + plot_h}" '
                 f'stroke="{CCA_COLORS["border"]}" stroke-width="1"/>')

    # Y-axis ticks
    for i in range(6):
        val = y_min + (y_max - y_min) * i / 5
        yp = sy(val)
        label_text = str(int(val)) if val == int(val) else f"{val:.1f}"
        parts.append(_text(margin_left - 8, yp + 3, label_text,
                           font_size=8, fill=CCA_COLORS["muted"], anchor="end"))
        if i > 0:
            parts.append(f'<line x1="{margin_left}" y1="{yp}" '
                         f'x2="{margin_left + plot_w}" y2="{yp}" '
                         f'stroke="{CCA_COLORS["border"]}" stroke-width="0.5" '
                         f'stroke-dasharray="3,3"/>')

    if chart.y_label:
        parts.append(f'<text x="14" y="{margin_top + plot_h / 2}" '
                     f'text-anchor="middle" font-size="9" '
                     f'font-family="sans-serif" fill="{CCA_COLORS["muted"]}" '
                     f'transform="rotate(-90, 14, {margin_top + plot_h / 2})">'
                     f'{_escape(chart.y_label)}</text>')

    # Draw violins
    n_cats = len(categories)
    cat_w = plot_w / n_cats
    max_half_w = min(cat_w * 0.4, 50)

    for i, (label, values) in enumerate(categories):
        cx = margin_left + cat_w * i + cat_w / 2
        n = len(values)

        # Silverman bandwidth
        std = (sum((v - sum(values) / n) ** 2 for v in values) / n) ** 0.5 if n > 1 else 1
        bw = 1.06 * std * n ** (-0.2) if std > 0 else 1

        # KDE on a grid of 50 points spanning the data range
        v_min, v_max = min(values), max(values)
        v_range_local = v_max - v_min if v_max != v_min else 1
        grid_lo = v_min - v_range_local * 0.15
        grid_hi = v_max + v_range_local * 0.15
        n_grid = 50
        grid = [grid_lo + (grid_hi - grid_lo) * j / (n_grid - 1) for j in range(n_grid)]
        densities = _gaussian_kde(values, grid, bw)

        max_density = max(densities) if densities else 1

        # Build mirrored polygon path
        # Right side (top to bottom in SVG = high to low values)
        right_points = []
        left_points = []
        for j in range(n_grid):
            yp = sy(grid[j])
            half_w = (densities[j] / max_density) * max_half_w if max_density > 0 else 0
            right_points.append((cx + half_w, yp))
            left_points.append((cx - half_w, yp))

        # Polygon: right side top-to-bottom, then left side bottom-to-top
        path_parts = []
        all_points = right_points + list(reversed(left_points))
        for k, (px, py) in enumerate(all_points):
            cmd = "M" if k == 0 else "L"
            path_parts.append(f"{cmd}{px:.1f},{py:.1f}")
        path_parts.append("Z")
        path_d = "".join(path_parts)

        parts.append(f'<path d="{path_d}" fill="{base_color}" '
                     f'fill-opacity="0.3" stroke="{base_color}" stroke-width="1"/>')

        # Quartile lines
        def percentile(vals, p):
            k = (len(vals) - 1) * p
            f = int(k)
            c = f + 1 if f + 1 < len(vals) else f
            d = k - f
            return vals[f] + d * (vals[c] - vals[f])

        q1 = percentile(values, 0.25)
        median = percentile(values, 0.5)
        q3 = percentile(values, 0.75)

        # Width at each quartile (interpolate from KDE)
        def width_at(val):
            # Find nearest grid index
            idx = int((val - grid_lo) / (grid_hi - grid_lo) * (n_grid - 1))
            idx = max(0, min(idx, n_grid - 1))
            return (densities[idx] / max_density) * max_half_w if max_density > 0 else 0

        # Q1 and Q3 lines (thin)
        for qv in [q1, q3]:
            w = width_at(qv)
            yp = sy(qv)
            parts.append(f'<line x1="{cx - w:.1f}" y1="{yp:.1f}" '
                         f'x2="{cx + w:.1f}" y2="{yp:.1f}" '
                         f'stroke="{CCA_COLORS["primary"]}" stroke-width="1" '
                         f'stroke-dasharray="3,2"/>')

        # Median line (bold)
        mw = width_at(median)
        parts.append(f'<line x1="{cx - mw:.1f}" y1="{sy(median):.1f}" '
                     f'x2="{cx + mw:.1f}" y2="{sy(median):.1f}" '
                     f'stroke="{CCA_COLORS["highlight"]}" stroke-width="2"/>')

        # Category label
        parts.append(_text(cx, margin_top + plot_h + 15, label,
                           font_size=9, fill=CCA_COLORS["primary"]))

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
    elif isinstance(chart, StackedAreaChart):
        return _render_stacked_area_chart(chart)
    elif isinstance(chart, GroupedBarChart):
        return _render_grouped_bar_chart(chart)
    elif isinstance(chart, WaterfallChart):
        return _render_waterfall_chart(chart)
    elif isinstance(chart, RadarChart):
        return _render_radar_chart(chart)
    elif isinstance(chart, GaugeChart):
        return _render_gauge_chart(chart)
    elif isinstance(chart, BubbleChart):
        return _render_bubble_chart(chart)
    elif isinstance(chart, TreemapChart):
        return _render_treemap_chart(chart)
    elif isinstance(chart, SankeyChart):
        return _render_sankey_chart(chart)
    elif isinstance(chart, FunnelChart):
        return _render_funnel_chart(chart)
    elif isinstance(chart, ScatterPlot):
        return _render_scatter_plot(chart)
    elif isinstance(chart, BoxPlot):
        return _render_box_plot(chart)
    elif isinstance(chart, HistogramChart):
        return _render_histogram_chart(chart)
    elif isinstance(chart, ViolinPlot):
        return _render_violin_plot(chart)
    else:
        raise TypeError(f"Unknown chart type: {type(chart)}")


def generate_grouped_bar(data: list, series_names: list, title: str = "", **kwargs) -> str:
    """Convenience function: render a grouped bar chart and return SVG string.

    Args:
        data: [(label, [val_series_0, val_series_1, ...]), ...]
        series_names: ["Series A", "Series B", ...] — legend labels
        title: Chart title (optional)
        **kwargs: Additional GroupedBarChart constructor args (width, height, colors, etc.)

    Returns:
        SVG string ready to embed or save.
    """
    chart = GroupedBarChart(data=data, series_names=series_names, title=title, **kwargs)
    return render_svg(chart)


def generate_stacked_area(series: list, labels: list, title: str = "", **kwargs) -> str:
    """Convenience function: render a stacked area chart and return SVG string.

    Args:
        series: [(name, [values]), ...] — ordered bottom-to-top
        labels: X-axis labels
        title: Chart title (optional)
        **kwargs: Additional StackedAreaChart constructor args (width, height, colors, etc.)

    Returns:
        SVG string ready to embed or save.
    """
    chart = StackedAreaChart(series=series, labels=labels, title=title, **kwargs)
    return render_svg(chart)


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
