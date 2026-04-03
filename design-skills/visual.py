"""visual.py — MT-32 Phase 7: Unified visual integration layer.

Single-import façade over all MT-32 design pillars:
  - Charts    (chart_generator)
  - Components (component_library)
  - Diagrams  (diagram_generator)
  - Figures   (figure_generator)
  - Dashboard (dashboard_generator)
  - Slides    (slide_generator)

Usage
-----
    from visual import (
        # Charts
        BarChart, LineChart, DonutChart,
        # Diagrams
        FlowDiagram, SequenceDiagram, render_diagram, save_diagram,
        # Figures
        Figure, FigurePanel, render_figure, save_figure,
        # Components
        card, stat_card, data_table, page,
        # High-level helpers
        make_flow, make_sequence, make_chart,
    )

    # Or grab everything at once:
    import visual as V
    fd = V.FlowDiagram()
    ...
    svg = V.render_diagram(fd)
"""

# ---------------------------------------------------------------------------
# Charts (chart_generator) — 25 chart types
# ---------------------------------------------------------------------------
from chart_generator import (
    BarChart,
    HorizontalBarChart,
    GroupedBarChart,
    StackedBarChart,
    LineChart,
    AreaChart,
    StackedAreaChart,
    ScatterPlot,
    BubbleChart,
    DonutChart,
    GaugeChart,
    HistogramChart,
    HeatmapChart,
    TreemapChart,
    SankeyChart,
    BoxPlot,
    ViolinPlot,
    RadarChart,
    WaterfallChart,
    BulletChart,
    LollipopChart,
    DumbbellChart,
    SlopeChart,
    Sparkline,
    ParetoChart,
    CalibrationPlot,
    ForestPlot,
    CandlestickChart,
    # Helpers
    render_svg as render_chart_svg,
    save_svg as save_chart_svg,
)

# ---------------------------------------------------------------------------
# Components (component_library) — 8 UI components
# ---------------------------------------------------------------------------
from component_library import (
    card,
    stat_card,
    data_table,
    badge,
    button,
    alert,
    progress_bar,
    tabs,
    annotations,
    page,
    component_stylesheet,
    to_css_vars,
)

# ---------------------------------------------------------------------------
# Diagrams (diagram_generator) — FlowDiagram + SequenceDiagram
# ---------------------------------------------------------------------------
from diagram_generator import (
    FlowDiagram,
    FlowNode,
    FlowEdge,
    SequenceDiagram,
    SequenceActor,
    SequenceMessage,
    render_diagram,
    render_flow_diagram,
    render_sequence_diagram,
    save_diagram,
)

# ---------------------------------------------------------------------------
# Figures (figure_generator) — multi-panel SVG compositions
# ---------------------------------------------------------------------------
from figure_generator import (
    Figure,
    FigurePanel,
    Annotation,
    TextAnnotation,
    ArrowAnnotation,
    HighlightAnnotation,
    render_figure,
    render_svg as render_figure_svg,
    save_figure,
    quick_figure,
    comparison_figure,
    dashboard_figure,
)

# ---------------------------------------------------------------------------
# Dashboard (dashboard_generator) — HTML dashboard builder
# ---------------------------------------------------------------------------
from dashboard_generator import (
    DashboardData,
    DashboardRenderer,
)

# ---------------------------------------------------------------------------
# Slides (slide_generator) — presentation builder
# ---------------------------------------------------------------------------
from slide_generator import (
    SlideGenerator,
    SlideDataCollector,
    collect_slides_from_project,
)

# ---------------------------------------------------------------------------
# Convenience factories
# ---------------------------------------------------------------------------

def make_flow(title: str = "") -> FlowDiagram:
    """Return a new FlowDiagram, optionally titled."""
    return FlowDiagram(title=title)


def make_sequence(title: str = "") -> SequenceDiagram:
    """Return a new SequenceDiagram, optionally titled."""
    return SequenceDiagram(title=title)


def make_chart(kind: str, **kwargs):
    """Instantiate a chart by name (e.g. 'bar', 'line', 'donut').

    Parameters
    ----------
    kind : str
        Chart type name — case-insensitive, hyphens/underscores normalised.
        Supported: bar, hbar, grouped_bar, stacked_bar, line, area,
        stacked_area, scatter, bubble, donut, gauge, histogram, heatmap,
        treemap, sankey, boxplot, violin, radar, waterfall, bullet, lollipop,
        dumbbell, slope, sparkline, pareto, calibration, forest, candlestick.
    **kwargs
        Passed straight through to the chart constructor.

    Returns
    -------
    Chart instance (the exact type depends on *kind*).
    """
    _CHART_MAP = {
        "bar": BarChart,
        "hbar": HorizontalBarChart,
        "horizontal_bar": HorizontalBarChart,
        "grouped_bar": GroupedBarChart,
        "stacked_bar": StackedBarChart,
        "line": LineChart,
        "area": AreaChart,
        "stacked_area": StackedAreaChart,
        "scatter": ScatterPlot,
        "bubble": BubbleChart,
        "donut": DonutChart,
        "gauge": GaugeChart,
        "histogram": HistogramChart,
        "heatmap": HeatmapChart,
        "treemap": TreemapChart,
        "sankey": SankeyChart,
        "boxplot": BoxPlot,
        "box_plot": BoxPlot,
        "violin": ViolinPlot,
        "radar": RadarChart,
        "waterfall": WaterfallChart,
        "bullet": BulletChart,
        "lollipop": LollipopChart,
        "dumbbell": DumbbellChart,
        "slope": SlopeChart,
        "sparkline": Sparkline,
        "pareto": ParetoChart,
        "calibration": CalibrationPlot,
        "forest": ForestPlot,
        "candlestick": CandlestickChart,
    }
    normalised = kind.lower().replace("-", "_")
    cls = _CHART_MAP.get(normalised)
    if cls is None:
        raise ValueError(
            f"Unknown chart kind '{kind}'. "
            f"Available: {sorted(_CHART_MAP)}"
        )
    return cls(**kwargs)


# ---------------------------------------------------------------------------
# __all__ — explicit export list so `from visual import *` is safe
# ---------------------------------------------------------------------------

__all__ = [
    # Charts
    "BarChart", "HorizontalBarChart", "GroupedBarChart", "StackedBarChart",
    "LineChart", "AreaChart", "StackedAreaChart", "ScatterPlot", "BubbleChart",
    "DonutChart", "GaugeChart", "HistogramChart", "HeatmapChart", "TreemapChart",
    "SankeyChart", "BoxPlot", "ViolinPlot", "RadarChart", "WaterfallChart",
    "BulletChart", "LollipopChart", "DumbbellChart", "SlopeChart", "Sparkline",
    "ParetoChart", "CalibrationPlot", "ForestPlot", "CandlestickChart",
    "render_chart_svg", "save_chart_svg",
    # Components
    "card", "stat_card", "data_table", "badge", "button", "alert",
    "progress_bar", "tabs", "annotations", "page", "component_stylesheet", "to_css_vars",
    # Diagrams
    "FlowDiagram", "FlowNode", "FlowEdge",
    "SequenceDiagram", "SequenceActor", "SequenceMessage",
    "render_diagram", "render_flow_diagram", "render_sequence_diagram", "save_diagram",
    # Figures
    "Figure", "FigurePanel", "Annotation", "TextAnnotation",
    "ArrowAnnotation", "HighlightAnnotation",
    "render_figure", "render_figure_svg", "save_figure",
    "quick_figure", "comparison_figure", "dashboard_figure",
    # Dashboard
    "DashboardData", "DashboardRenderer",
    # Slides
    "SlideGenerator", "SlideDataCollector", "collect_slides_from_project",
    # Convenience factories
    "make_flow", "make_sequence", "make_chart",
]
