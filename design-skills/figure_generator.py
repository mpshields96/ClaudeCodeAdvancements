#!/usr/bin/env python3
"""Multi-panel figure generator — MT-32 Phase 6.

Composes multiple chart objects into publication-quality figures with:
- Grid layout (configurable rows x cols)
- Panel labels (a, b, c, ...)
- Per-panel captions
- Figure-level title
- Annotations (text, arrows, highlights) at figure or panel level
- SVG export

Usage:
    from chart_generator import BarChart, LineChart
    from figure_generator import Figure, FigurePanel, TextAnnotation, render_figure, save_figure

    fig = Figure(
        panels=[
            FigurePanel(chart=BarChart(data=[("A", 10)], title="Bar"), label="a"),
            FigurePanel(chart=LineChart(series=[("S", [1,2,3])], labels=["x","y","z"]), label="b"),
        ],
        cols=2,
        title="Figure 1: Overview",
    )
    svg = render_figure(fig)
    save_figure(fig, "figure1.svg")
"""

import math
import os
from dataclasses import dataclass, field
from typing import List, Optional

# Import chart rendering from sibling module
from chart_generator import render_svg, _escape, SVG_NS, FONT_FAMILY, CCA_COLORS


# ---------------------------------------------------------------------------
# Annotation types
# ---------------------------------------------------------------------------

@dataclass
class Annotation:
    """Base annotation class."""
    pass


@dataclass
class TextAnnotation(Annotation):
    """Text label placed at absolute coordinates."""
    x: float = 0
    y: float = 0
    text: str = ""
    font_size: int = 11
    color: str = CCA_COLORS["primary"]
    font_weight: str = "bold"


@dataclass
class ArrowAnnotation(Annotation):
    """Arrow with optional text label from (x1,y1) to (x2,y2)."""
    x1: float = 0
    y1: float = 0
    x2: float = 0
    y2: float = 0
    text: Optional[str] = None
    color: str = CCA_COLORS["primary"]
    font_size: int = 10


@dataclass
class HighlightAnnotation(Annotation):
    """Semi-transparent rectangle highlight region."""
    x: float = 0
    y: float = 0
    width: float = 100
    height: float = 100
    color: str = CCA_COLORS["warning"]
    opacity: float = 0.15


# ---------------------------------------------------------------------------
# Figure panel and figure
# ---------------------------------------------------------------------------

DEFAULT_PANEL_WIDTH = 480
DEFAULT_PANEL_HEIGHT = 320


@dataclass
class FigurePanel:
    """One panel in a multi-panel figure."""
    chart: object = None
    label: Optional[str] = None
    caption: Optional[str] = None
    width: int = DEFAULT_PANEL_WIDTH
    height: int = DEFAULT_PANEL_HEIGHT
    annotations: List[Annotation] = field(default_factory=list)


@dataclass
class Figure:
    """Multi-panel figure with optional title and annotations."""
    panels: List[FigurePanel] = field(default_factory=list)
    title: Optional[str] = None
    cols: Optional[int] = None
    padding: int = 20
    annotations: List[Annotation] = field(default_factory=list)

    def __post_init__(self):
        if not self.panels:
            raise ValueError("Figure must have at least one panel")

    def _effective_cols(self) -> int:
        if self.cols is not None:
            return self.cols
        n = len(self.panels)
        if n <= 1:
            return 1
        if n <= 4:
            return 2
        return 3


# ---------------------------------------------------------------------------
# SVG rendering helpers
# ---------------------------------------------------------------------------

def _render_annotation(ann: Annotation, offset_x: float = 0, offset_y: float = 0) -> str:
    """Render a single annotation to SVG elements."""
    parts = []

    if isinstance(ann, TextAnnotation):
        ax = ann.x + offset_x
        ay = ann.y + offset_y
        parts.append(
            f'<text x="{ax}" y="{ay}" font-family="{FONT_FAMILY}" '
            f'font-size="{ann.font_size}" font-weight="{ann.font_weight}" '
            f'fill="{_escape(ann.color)}" text-anchor="start">'
            f'{_escape(ann.text)}</text>\n'
        )

    elif isinstance(ann, ArrowAnnotation):
        ax1 = ann.x1 + offset_x
        ay1 = ann.y1 + offset_y
        ax2 = ann.x2 + offset_x
        ay2 = ann.y2 + offset_y
        # Arrowhead marker is defined in defs
        parts.append(
            f'<line x1="{ax1}" y1="{ay1}" x2="{ax2}" y2="{ay2}" '
            f'stroke="{_escape(ann.color)}" stroke-width="1.5" '
            f'marker-end="url(#arrowhead)"/>\n'
        )
        if ann.text:
            # Place text near the start of the arrow
            tx = ax1
            ty = ay1 - 6
            parts.append(
                f'<text x="{tx}" y="{ty}" font-family="{FONT_FAMILY}" '
                f'font-size="{ann.font_size}" fill="{_escape(ann.color)}" '
                f'text-anchor="start">{_escape(ann.text)}</text>\n'
            )

    elif isinstance(ann, HighlightAnnotation):
        ax = ann.x + offset_x
        ay = ann.y + offset_y
        parts.append(
            f'<rect x="{ax}" y="{ay}" width="{ann.width}" height="{ann.height}" '
            f'fill="{_escape(ann.color)}" opacity="{ann.opacity}" rx="4"/>\n'
        )

    return "".join(parts)


def _render_panel_svg_content(panel: FigurePanel) -> str:
    """Render a panel's chart as SVG content (inner elements only, no wrapper)."""
    # Get the full SVG of the chart
    chart_svg = render_svg(panel.chart)
    # Extract inner content between <svg...> and </svg>
    # Find the end of the opening <svg> tag
    start = chart_svg.find(">")
    if start == -1:
        return ""
    start += 1
    end = chart_svg.rfind("</svg>")
    if end == -1:
        return chart_svg[start:]
    return chart_svg[start:end]


def render_figure(fig: Figure) -> str:
    """Render a Figure to a complete SVG string."""
    cols = fig._effective_cols()
    rows = math.ceil(len(fig.panels) / cols)
    pad = fig.padding

    # Determine panel sizes (use first panel's size as reference, or defaults)
    panel_w = fig.panels[0].width if fig.panels else DEFAULT_PANEL_WIDTH
    panel_h = fig.panels[0].height if fig.panels else DEFAULT_PANEL_HEIGHT

    # Calculate total figure dimensions
    title_height = 40 if fig.title else 0
    caption_height = 24  # space for captions below panels
    label_height = 20  # space for panel labels above panels

    total_w = cols * panel_w + (cols + 1) * pad
    total_h = (
        title_height
        + rows * (label_height + panel_h + caption_height)
        + (rows + 1) * pad
    )

    parts = []
    # SVG header
    parts.append(
        f'<svg xmlns="{SVG_NS}" width="{total_w}" height="{total_h}" '
        f'viewBox="0 0 {total_w} {total_h}">\n'
    )

    # Defs (arrowhead marker for annotations)
    parts.append('<defs>\n')
    parts.append(
        '<marker id="arrowhead" markerWidth="10" markerHeight="7" '
        'refX="10" refY="3.5" orient="auto">\n'
        f'  <polygon points="0 0, 10 3.5, 0 7" fill="{CCA_COLORS["primary"]}"/>\n'
        '</marker>\n'
    )
    parts.append('</defs>\n')

    # Background
    parts.append(
        f'<rect width="{total_w}" height="{total_h}" fill="{CCA_COLORS["background"]}"/>\n'
    )

    # Figure title
    y_cursor = pad
    if fig.title:
        parts.append(
            f'<text x="{total_w / 2}" y="{y_cursor + 20}" '
            f'font-family="{FONT_FAMILY}" font-size="16" font-weight="bold" '
            f'fill="{CCA_COLORS["primary"]}" text-anchor="middle">'
            f'{_escape(fig.title)}</text>\n'
        )
        y_cursor += title_height

    # Render panels in grid
    for idx, panel in enumerate(fig.panels):
        col = idx % cols
        row = idx // cols

        px = pad + col * (panel_w + pad)
        py = y_cursor + row * (label_height + panel_h + caption_height + pad)

        # Panel label (e.g., "(a)")
        if panel.label is not None:
            parts.append(
                f'<text x="{px + 4}" y="{py + 14}" '
                f'font-family="{FONT_FAMILY}" font-size="13" font-weight="bold" '
                f'fill="{CCA_COLORS["primary"]}" text-anchor="start">'
                f'({_escape(panel.label)})</text>\n'
            )

        # Panel border
        panel_y = py + label_height
        parts.append(
            f'<rect x="{px}" y="{panel_y}" width="{panel_w}" height="{panel_h}" '
            f'fill="none" stroke="{CCA_COLORS["border"]}" stroke-width="1" rx="4"/>\n'
        )

        # Embed chart content inside a group with translate
        chart_w = panel.width
        chart_h = panel.height
        # Scale chart to fit panel
        scale_x = panel_w / chart_w if chart_w > 0 else 1
        scale_y = panel_h / chart_h if chart_h > 0 else 1
        scale = min(scale_x, scale_y)

        parts.append(
            f'<g transform="translate({px},{panel_y}) scale({scale:.4f})">\n'
        )
        parts.append(_render_panel_svg_content(panel))
        parts.append('</g>\n')

        # Panel-level annotations
        for ann in panel.annotations:
            parts.append(_render_annotation(ann, offset_x=px, offset_y=panel_y))

        # Caption
        if panel.caption:
            cap_y = panel_y + panel_h + 16
            parts.append(
                f'<text x="{px + panel_w / 2}" y="{cap_y}" '
                f'font-family="{FONT_FAMILY}" font-size="10" '
                f'fill="{CCA_COLORS["muted"]}" text-anchor="middle">'
                f'{_escape(panel.caption)}</text>\n'
            )

    # Figure-level annotations
    for ann in fig.annotations:
        parts.append(_render_annotation(ann))

    parts.append('</svg>\n')
    return "".join(parts)


def save_figure(fig: Figure, path: str) -> str:
    """Render figure and save to SVG file.

    Creates parent directories if needed.

    Args:
        fig: Figure object to render.
        path: Output file path (.svg).

    Returns:
        The file path written to.
    """
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    svg = render_figure(fig)
    with open(path, "w") as f:
        f.write(svg)
    return path


# ---------------------------------------------------------------------------
# Convenience / preset functions
# ---------------------------------------------------------------------------

def quick_figure(
    charts: list,
    title: Optional[str] = None,
    cols: Optional[int] = None,
    labels: bool = True,
) -> Figure:
    """Create a figure from a list of charts with automatic layout.

    Args:
        charts: List of chart objects (BarChart, LineChart, etc.)
        title: Optional figure title.
        cols: Number of columns (auto-detected if None).
        labels: Whether to add automatic (a), (b), (c) labels.

    Returns:
        Figure ready to render.
    """
    if not charts:
        raise ValueError("quick_figure requires at least one chart")

    panels = []
    for i, chart in enumerate(charts):
        label = chr(97 + i) if labels else None
        panels.append(FigurePanel(chart=chart, label=label))

    return Figure(panels=panels, title=title, cols=cols)


def comparison_figure(
    left: object,
    right: object,
    title: Optional[str] = None,
) -> Figure:
    """Create a side-by-side comparison of two charts.

    Args:
        left: Left chart object.
        right: Right chart object.
        title: Optional figure title.

    Returns:
        Figure with two panels in a 1x2 layout.
    """
    return Figure(
        panels=[
            FigurePanel(chart=left, label="a"),
            FigurePanel(chart=right, label="b"),
        ],
        cols=2,
        title=title,
    )


def dashboard_figure(
    charts: list,
    title: Optional[str] = None,
) -> Figure:
    """Create a 2-column dashboard layout from charts.

    Args:
        charts: List of 2-6 chart objects.
        title: Optional figure title.

    Returns:
        Figure with 2-column grid layout and auto-labels.
    """
    if not charts:
        raise ValueError("dashboard_figure requires at least one chart")

    panels = [
        FigurePanel(chart=c, label=chr(97 + i))
        for i, c in enumerate(charts)
    ]
    return Figure(panels=panels, cols=2, title=title)
