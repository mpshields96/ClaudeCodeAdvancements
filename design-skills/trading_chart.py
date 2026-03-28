#!/usr/bin/env python3
"""
trading_chart.py — MT-24 Phase 1: Trading-specific SVG chart generators.

Builds on chart_generator.py's design language to produce trading analytics
visualizations. These charts are designed for:
- Kalshi bot performance dashboards
- Session-over-session P&L tracking
- Strategy comparison and health monitoring
- Academic presentations (publication-quality)

Chart types:
    PnLCurve       — Cumulative P&L line with win/loss markers
    WinRateChart   — Rolling win rate with confidence band
    StrategyMatrix — Multi-strategy comparison grid
    DrawdownChart  — Max drawdown waterfall visualization
    HeatmapChart   — Hour-of-day / day-of-week performance heatmap

Usage:
    from trading_chart import PnLCurve, render_svg, save_svg

    curve = PnLCurve(
        trades=[{"pnl": 35}, {"pnl": -65}, {"pnl": 35}, {"pnl": 35}],
        title="Expiry Sniper P&L"
    )
    svg = render_svg(curve)

Stdlib only. No external dependencies.
"""

import math
import os
from dataclasses import dataclass, field
from typing import Optional

# Import design language from canonical source
try:
    from chart_generator import CCA_COLORS, SERIES_PALETTE
except ImportError:
    # Fallback: build from design_tokens if chart_generator unavailable
    import design_tokens
    CCA_COLORS = {
        **design_tokens.CCA_PALETTE,
        "background": design_tokens.CCA_PALETTE["bg"],
    }
    SERIES_PALETTE = design_tokens.SERIES_COLORS[:5]

# Trading-specific colors
TRADE_COLORS = {
    "profit": "#16c79a",    # Green for wins
    "loss": "#e94560",      # Red for losses
    "neutral": "#6b7280",   # Gray for break-even
    "drawdown": "#ff6b6b",  # Light red for drawdown area
    "band_fill": "#e8f4fd", # Light blue for confidence bands
    "grid": "#f0f0f0",      # Light gray for grid lines
    "zero_line": "#d1d5db", # Gray for zero reference
}

# Standard chart dimensions
DEFAULT_WIDTH = 800
DEFAULT_HEIGHT = 400
MARGIN = {"top": 50, "right": 40, "bottom": 60, "left": 70}


def _escape_xml(text: str) -> str:
    """Escape special XML characters."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _format_currency(cents: float) -> str:
    """Format cents as dollar string."""
    dollars = cents / 100
    if abs(dollars) >= 1:
        return f"${dollars:+.2f}"
    return f"{cents:+.0f}c"


@dataclass
class PnLCurve:
    """Cumulative P&L line chart with win/loss markers."""
    trades: list  # List of dicts with at least "pnl" key (in cents)
    title: str = "Cumulative P&L"
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    show_markers: bool = True
    show_zero_line: bool = True
    chart_type: str = "pnl_curve"


@dataclass
class WinRateChart:
    """Rolling win rate with optional confidence band."""
    results: list  # List of bools (True=win, False=loss)
    window: int = 20  # Rolling window size
    title: str = "Rolling Win Rate"
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    show_band: bool = True
    target_rate: Optional[float] = None  # e.g., 0.6 for 60% target
    chart_type: str = "win_rate"


@dataclass
class StrategyMatrix:
    """Multi-strategy comparison grid."""
    strategies: list  # List of dicts: {"name", "trades", "wins", "pnl", "avg_edge"}
    title: str = "Strategy Comparison"
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    chart_type: str = "strategy_matrix"


@dataclass
class DrawdownChart:
    """Drawdown visualization from equity curve."""
    trades: list  # List of dicts with "pnl" key
    title: str = "Drawdown Analysis"
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    chart_type: str = "drawdown"


@dataclass
class HeatmapChart:
    """Hour/day performance heatmap."""
    data: list  # List of dicts: {"hour": 0-23, "day": 0-6, "value": float}
    title: str = "Performance Heatmap"
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    value_label: str = "P&L (cents)"
    chart_type: str = "heatmap"


def _render_pnl_curve(chart: PnLCurve) -> str:
    """Render a cumulative P&L curve as SVG."""
    w, h = chart.width, chart.height
    plot_x = MARGIN["left"]
    plot_y = MARGIN["top"]
    plot_w = w - MARGIN["left"] - MARGIN["right"]
    plot_h = h - MARGIN["top"] - MARGIN["bottom"]

    # Calculate cumulative P&L
    cum_pnl = []
    running = 0
    for t in chart.trades:
        running += t.get("pnl", 0)
        cum_pnl.append(running)

    if not cum_pnl:
        cum_pnl = [0]

    min_pnl = min(0, min(cum_pnl))
    max_pnl = max(0, max(cum_pnl))
    pnl_range = max_pnl - min_pnl or 1

    # Scale functions
    def sx(i):
        if len(cum_pnl) <= 1:
            return plot_x + plot_w / 2
        return plot_x + (i / (len(cum_pnl) - 1)) * plot_w

    def sy(val):
        return plot_y + plot_h - ((val - min_pnl) / pnl_range) * plot_h

    # Build SVG
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="{CCA_COLORS["background"]}"/>',
        # Title
        f'<text x="{w/2}" y="30" text-anchor="middle" font-family="sans-serif" '
        f'font-size="16" font-weight="bold" fill="{CCA_COLORS["primary"]}">{_escape_xml(chart.title)}</text>',
        # Plot area
        f'<rect x="{plot_x}" y="{plot_y}" width="{plot_w}" height="{plot_h}" '
        f'fill="{CCA_COLORS["surface"]}" stroke="{CCA_COLORS["border"]}"/>',
    ]

    # Grid lines
    n_grid = 5
    for i in range(n_grid + 1):
        gy = plot_y + (i / n_grid) * plot_h
        val = max_pnl - (i / n_grid) * pnl_range
        parts.append(
            f'<line x1="{plot_x}" y1="{gy}" x2="{plot_x + plot_w}" y2="{gy}" '
            f'stroke="{TRADE_COLORS["grid"]}" stroke-width="0.5"/>'
        )
        parts.append(
            f'<text x="{plot_x - 5}" y="{gy + 4}" text-anchor="end" font-family="sans-serif" '
            f'font-size="10" fill="{CCA_COLORS["muted"]}">{_format_currency(val)}</text>'
        )

    # Zero line
    if chart.show_zero_line and min_pnl < 0 < max_pnl:
        zy = sy(0)
        parts.append(
            f'<line x1="{plot_x}" y1="{zy}" x2="{plot_x + plot_w}" y2="{zy}" '
            f'stroke="{TRADE_COLORS["zero_line"]}" stroke-width="1.5" stroke-dasharray="4,3"/>'
        )

    # P&L line
    points = " ".join(f"{sx(i)},{sy(v)}" for i, v in enumerate(cum_pnl))
    # Gradient fill under the line
    final_color = TRADE_COLORS["profit"] if cum_pnl[-1] >= 0 else TRADE_COLORS["loss"]
    parts.append(
        f'<defs><linearGradient id="pnl_fill" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{final_color}" stop-opacity="0.3"/>'
        f'<stop offset="100%" stop-color="{final_color}" stop-opacity="0.05"/>'
        f'</linearGradient></defs>'
    )

    # Fill area
    fill_points = f"{sx(0)},{sy(0)} " + points + f" {sx(len(cum_pnl)-1)},{sy(0)}"
    parts.append(f'<polygon points="{fill_points}" fill="url(#pnl_fill)"/>')

    # Line
    parts.append(
        f'<polyline points="{points}" fill="none" stroke="{final_color}" stroke-width="2"/>'
    )

    # Win/loss markers
    if chart.show_markers and len(chart.trades) <= 50:
        for i, t in enumerate(chart.trades):
            pnl = t.get("pnl", 0)
            color = TRADE_COLORS["profit"] if pnl >= 0 else TRADE_COLORS["loss"]
            r = 4 if abs(pnl) > 50 else 3
            parts.append(
                f'<circle cx="{sx(i)}" cy="{sy(cum_pnl[i])}" r="{r}" '
                f'fill="{color}" stroke="{CCA_COLORS["background"]}" stroke-width="1"/>'
            )

    # X-axis labels
    n_labels = min(len(cum_pnl), 10)
    step = max(1, len(cum_pnl) // n_labels)
    for i in range(0, len(cum_pnl), step):
        parts.append(
            f'<text x="{sx(i)}" y="{plot_y + plot_h + 20}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="10" fill="{CCA_COLORS["muted"]}">#{i+1}</text>'
        )

    # Final P&L annotation
    final = cum_pnl[-1]
    parts.append(
        f'<text x="{sx(len(cum_pnl)-1) + 5}" y="{sy(final) - 8}" font-family="sans-serif" '
        f'font-size="12" font-weight="bold" fill="{final_color}">{_format_currency(final)}</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


def _render_win_rate(chart: WinRateChart) -> str:
    """Render a rolling win rate chart as SVG."""
    w, h = chart.width, chart.height
    plot_x = MARGIN["left"]
    plot_y = MARGIN["top"]
    plot_w = w - MARGIN["left"] - MARGIN["right"]
    plot_h = h - MARGIN["top"] - MARGIN["bottom"]

    if len(chart.results) < chart.window:
        # Not enough data — show message
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
            f'<text x="{w/2}" y="{h/2}" text-anchor="middle" font-family="sans-serif" '
            f'font-size="14" fill="{CCA_COLORS["muted"]}">Need {chart.window}+ trades for rolling win rate</text>'
            f'</svg>'
        )

    # Calculate rolling win rate
    rates = []
    for i in range(chart.window - 1, len(chart.results)):
        window_data = chart.results[i - chart.window + 1:i + 1]
        rate = sum(1 for r in window_data if r) / len(window_data)
        rates.append(rate)

    min_rate = 0.0
    max_rate = 1.0

    def sx(i):
        if len(rates) <= 1:
            return plot_x + plot_w / 2
        return plot_x + (i / (len(rates) - 1)) * plot_w

    def sy(val):
        return plot_y + plot_h - ((val - min_rate) / (max_rate - min_rate)) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="{CCA_COLORS["background"]}"/>',
        f'<text x="{w/2}" y="30" text-anchor="middle" font-family="sans-serif" '
        f'font-size="16" font-weight="bold" fill="{CCA_COLORS["primary"]}">{_escape_xml(chart.title)}</text>',
        f'<rect x="{plot_x}" y="{plot_y}" width="{plot_w}" height="{plot_h}" '
        f'fill="{CCA_COLORS["surface"]}" stroke="{CCA_COLORS["border"]}"/>',
    ]

    # Y-axis labels (0%, 25%, 50%, 75%, 100%)
    for pct in [0, 25, 50, 75, 100]:
        gy = sy(pct / 100)
        parts.append(
            f'<line x1="{plot_x}" y1="{gy}" x2="{plot_x + plot_w}" y2="{gy}" '
            f'stroke="{TRADE_COLORS["grid"]}" stroke-width="0.5"/>'
        )
        parts.append(
            f'<text x="{plot_x - 5}" y="{gy + 4}" text-anchor="end" font-family="sans-serif" '
            f'font-size="10" fill="{CCA_COLORS["muted"]}">{pct}%</text>'
        )

    # Confidence band (Wilson interval approximation)
    if chart.show_band:
        upper_points = []
        lower_points = []
        for i, rate in enumerate(rates):
            n = chart.window
            z = 1.96  # 95% CI
            denominator = 1 + z * z / n
            centre = (rate + z * z / (2 * n)) / denominator
            margin = z * math.sqrt((rate * (1 - rate) + z * z / (4 * n)) / n) / denominator
            upper_points.append(f"{sx(i)},{sy(min(1, centre + margin))}")
            lower_points.append(f"{sx(i)},{sy(max(0, centre - margin))}")

        band_polygon = " ".join(upper_points) + " " + " ".join(reversed(lower_points))
        parts.append(f'<polygon points="{band_polygon}" fill="{TRADE_COLORS["band_fill"]}" opacity="0.5"/>')

    # Target rate line
    if chart.target_rate is not None:
        ty = sy(chart.target_rate)
        parts.append(
            f'<line x1="{plot_x}" y1="{ty}" x2="{plot_x + plot_w}" y2="{ty}" '
            f'stroke="{CCA_COLORS["warning"]}" stroke-width="1.5" stroke-dasharray="6,3"/>'
        )
        parts.append(
            f'<text x="{plot_x + plot_w + 5}" y="{ty + 4}" font-family="sans-serif" '
            f'font-size="10" fill="{CCA_COLORS["warning"]}">target</text>'
        )

    # Win rate line
    points = " ".join(f"{sx(i)},{sy(r)}" for i, r in enumerate(rates))
    parts.append(
        f'<polyline points="{points}" fill="none" stroke="{CCA_COLORS["accent"]}" stroke-width="2"/>'
    )

    # 50% reference line
    parts.append(
        f'<line x1="{plot_x}" y1="{sy(0.5)}" x2="{plot_x + plot_w}" y2="{sy(0.5)}" '
        f'stroke="{TRADE_COLORS["zero_line"]}" stroke-width="1" stroke-dasharray="4,3"/>'
    )

    # Current rate annotation
    current = rates[-1]
    color = TRADE_COLORS["profit"] if current >= 0.5 else TRADE_COLORS["loss"]
    parts.append(
        f'<text x="{sx(len(rates)-1)}" y="{sy(current) - 10}" text-anchor="end" '
        f'font-family="sans-serif" font-size="12" font-weight="bold" fill="{color}">'
        f'{current:.0%}</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


def _render_strategy_matrix(chart: StrategyMatrix) -> str:
    """Render a strategy comparison table as SVG."""
    w, h = chart.width, chart.height
    strategies = chart.strategies

    if not strategies:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
            f'<text x="{w/2}" y="{h/2}" text-anchor="middle">No strategies</text></svg>'
        )

    row_h = min(40, (h - 100) / (len(strategies) + 1))
    header_y = 70
    col_widths = [200, 80, 80, 120, 120]  # name, trades, wins, win%, pnl
    col_x = [40]
    for cw in col_widths[:-1]:
        col_x.append(col_x[-1] + cw)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="{CCA_COLORS["background"]}"/>',
        f'<text x="{w/2}" y="30" text-anchor="middle" font-family="sans-serif" '
        f'font-size="16" font-weight="bold" fill="{CCA_COLORS["primary"]}">{_escape_xml(chart.title)}</text>',
    ]

    # Headers
    headers = ["Strategy", "Trades", "Wins", "Win Rate", "P&L"]
    for i, header in enumerate(headers):
        parts.append(
            f'<text x="{col_x[i]}" y="{header_y}" font-family="sans-serif" '
            f'font-size="11" font-weight="bold" fill="{CCA_COLORS["primary"]}">{header}</text>'
        )

    # Separator
    parts.append(
        f'<line x1="30" y1="{header_y + 8}" x2="{w - 30}" y2="{header_y + 8}" '
        f'stroke="{CCA_COLORS["border"]}" stroke-width="1"/>'
    )

    # Rows
    for j, s in enumerate(strategies):
        ry = header_y + (j + 1) * row_h + 5
        name = s.get("name", f"Strategy {j+1}")
        trades = s.get("trades", 0)
        wins = s.get("wins", 0)
        win_rate = wins / trades if trades > 0 else 0
        pnl = s.get("pnl", 0)

        # Alternating row background
        if j % 2 == 1:
            parts.append(
                f'<rect x="30" y="{ry - row_h + 10}" width="{w - 60}" height="{row_h}" '
                f'fill="{CCA_COLORS["surface"]}"/>'
            )

        wr_color = TRADE_COLORS["profit"] if win_rate >= 0.5 else TRADE_COLORS["loss"]
        pnl_color = TRADE_COLORS["profit"] if pnl >= 0 else TRADE_COLORS["loss"]

        parts.append(f'<text x="{col_x[0]}" y="{ry}" font-family="sans-serif" font-size="12" fill="{CCA_COLORS["primary"]}">{_escape_xml(name)}</text>')
        parts.append(f'<text x="{col_x[1]}" y="{ry}" font-family="sans-serif" font-size="12" fill="{CCA_COLORS["muted"]}">{trades}</text>')
        parts.append(f'<text x="{col_x[2]}" y="{ry}" font-family="sans-serif" font-size="12" fill="{CCA_COLORS["muted"]}">{wins}</text>')
        parts.append(f'<text x="{col_x[3]}" y="{ry}" font-family="sans-serif" font-size="12" font-weight="bold" fill="{wr_color}">{win_rate:.0%}</text>')
        parts.append(f'<text x="{col_x[4]}" y="{ry}" font-family="sans-serif" font-size="12" font-weight="bold" fill="{pnl_color}">{_format_currency(pnl)}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def _render_drawdown(chart: DrawdownChart) -> str:
    """Render a drawdown chart as SVG."""
    w, h = chart.width, chart.height
    plot_x = MARGIN["left"]
    plot_y = MARGIN["top"]
    plot_w = w - MARGIN["left"] - MARGIN["right"]
    plot_h = h - MARGIN["top"] - MARGIN["bottom"]

    # Calculate equity curve and drawdown
    cum_pnl = []
    running = 0
    for t in chart.trades:
        running += t.get("pnl", 0)
        cum_pnl.append(running)

    if not cum_pnl:
        cum_pnl = [0]

    # Drawdown = current - peak
    peak = cum_pnl[0]
    drawdowns = []
    for val in cum_pnl:
        peak = max(peak, val)
        drawdowns.append(val - peak)  # Always <= 0

    min_dd = min(drawdowns) if drawdowns else 0
    max_dd = 0
    dd_range = max_dd - min_dd or 1

    def sx(i):
        if len(drawdowns) <= 1:
            return plot_x + plot_w / 2
        return plot_x + (i / (len(drawdowns) - 1)) * plot_w

    def sy(val):
        return plot_y + ((max_dd - val) / dd_range) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="{CCA_COLORS["background"]}"/>',
        f'<text x="{w/2}" y="30" text-anchor="middle" font-family="sans-serif" '
        f'font-size="16" font-weight="bold" fill="{CCA_COLORS["primary"]}">{_escape_xml(chart.title)}</text>',
        f'<rect x="{plot_x}" y="{plot_y}" width="{plot_w}" height="{plot_h}" '
        f'fill="{CCA_COLORS["surface"]}" stroke="{CCA_COLORS["border"]}"/>',
    ]

    # Zero line at top
    parts.append(
        f'<line x1="{plot_x}" y1="{sy(0)}" x2="{plot_x + plot_w}" y2="{sy(0)}" '
        f'stroke="{TRADE_COLORS["zero_line"]}" stroke-width="1.5"/>'
    )

    # Drawdown fill area
    fill_points = f"{sx(0)},{sy(0)}"
    for i, dd in enumerate(drawdowns):
        fill_points += f" {sx(i)},{sy(dd)}"
    fill_points += f" {sx(len(drawdowns)-1)},{sy(0)}"
    parts.append(f'<polygon points="{fill_points}" fill="{TRADE_COLORS["drawdown"]}" opacity="0.3"/>')

    # Drawdown line
    line_points = " ".join(f"{sx(i)},{sy(dd)}" for i, dd in enumerate(drawdowns))
    parts.append(
        f'<polyline points="{line_points}" fill="none" stroke="{TRADE_COLORS["loss"]}" stroke-width="2"/>'
    )

    # Max drawdown annotation
    max_dd_idx = drawdowns.index(min_dd)
    parts.append(
        f'<circle cx="{sx(max_dd_idx)}" cy="{sy(min_dd)}" r="5" '
        f'fill="{TRADE_COLORS["loss"]}" stroke="{CCA_COLORS["background"]}" stroke-width="1.5"/>'
    )
    parts.append(
        f'<text x="{sx(max_dd_idx)}" y="{sy(min_dd) + 18}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="11" font-weight="bold" '
        f'fill="{TRADE_COLORS["loss"]}">Max DD: {_format_currency(min_dd)}</text>'
    )

    # Y-axis labels
    n_grid = 4
    for i in range(n_grid + 1):
        gy = plot_y + (i / n_grid) * plot_h
        val = max_dd - (i / n_grid) * dd_range
        parts.append(
            f'<text x="{plot_x - 5}" y="{gy + 4}" text-anchor="end" font-family="sans-serif" '
            f'font-size="10" fill="{CCA_COLORS["muted"]}">{_format_currency(val)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _render_heatmap(chart: HeatmapChart) -> str:
    """Render an hour/day performance heatmap as SVG."""
    w, h = chart.width, chart.height

    if not chart.data:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
            f'<text x="{w/2}" y="{h/2}" text-anchor="middle">No data</text></svg>'
        )

    # Build grid: 24 hours x 7 days
    grid = {}
    for d in chart.data:
        key = (d.get("hour", 0), d.get("day", 0))
        grid[key] = d.get("value", 0)

    values = list(grid.values()) or [0]
    min_val = min(values)
    max_val = max(values)
    val_range = max_val - min_val or 1

    cell_w = (w - 120) / 24
    cell_h = (h - 100) / 7
    offset_x = 80
    offset_y = 60

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="{CCA_COLORS["background"]}"/>',
        f'<text x="{w/2}" y="30" text-anchor="middle" font-family="sans-serif" '
        f'font-size="16" font-weight="bold" fill="{CCA_COLORS["primary"]}">{_escape_xml(chart.title)}</text>',
    ]

    # Day labels
    for day in range(7):
        cy = offset_y + day * cell_h + cell_h / 2
        parts.append(
            f'<text x="{offset_x - 8}" y="{cy + 4}" text-anchor="end" font-family="sans-serif" '
            f'font-size="10" fill="{CCA_COLORS["muted"]}">{day_names[day]}</text>'
        )

    # Hour labels
    for hour in range(24):
        cx = offset_x + hour * cell_w + cell_w / 2
        if hour % 3 == 0:
            parts.append(
                f'<text x="{cx}" y="{offset_y - 5}" text-anchor="middle" font-family="sans-serif" '
                f'font-size="9" fill="{CCA_COLORS["muted"]}">{hour:02d}</text>'
            )

    # Cells
    for hour in range(24):
        for day in range(7):
            val = grid.get((hour, day), 0)
            # Color interpolation: red (negative) -> white (zero) -> green (positive)
            if val >= 0:
                ratio = val / max_val if max_val > 0 else 0
                r = int(255 - ratio * (255 - 22))
                g = int(255 - ratio * (255 - 199))
                b = int(255 - ratio * (255 - 154))
            else:
                ratio = abs(val) / abs(min_val) if min_val < 0 else 0
                r = int(255 - ratio * (255 - 233))
                g = int(255 - ratio * (255 - 69))
                b = int(255 - ratio * (255 - 96))

            color = f"#{r:02x}{g:02x}{b:02x}"
            cx = offset_x + hour * cell_w
            cy = offset_y + day * cell_h

            parts.append(
                f'<rect x="{cx}" y="{cy}" width="{cell_w - 1}" height="{cell_h - 1}" '
                f'fill="{color}" rx="2"/>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def render_svg(chart) -> str:
    """Render any chart type to SVG string."""
    renderers = {
        "pnl_curve": _render_pnl_curve,
        "win_rate": _render_win_rate,
        "strategy_matrix": _render_strategy_matrix,
        "drawdown": _render_drawdown,
        "heatmap": _render_heatmap,
    }
    renderer = renderers.get(chart.chart_type)
    if not renderer:
        raise ValueError(f"Unknown chart type: {chart.chart_type}")
    return renderer(chart)


def save_svg(chart, path: str) -> str:
    """Render and save chart to SVG file. Returns path."""
    svg = render_svg(chart)
    with open(path, 'w') as f:
        f.write(svg)
    return path


if __name__ == "__main__":
    # Demo: generate sample charts
    import sys

    trades = [
        {"pnl": 35}, {"pnl": 35}, {"pnl": -65}, {"pnl": 35},
        {"pnl": 35}, {"pnl": -65}, {"pnl": 35}, {"pnl": 35},
        {"pnl": 35}, {"pnl": -65}, {"pnl": 35}, {"pnl": 35},
    ]

    pnl = PnLCurve(trades=trades, title="Expiry Sniper P&L")
    print(render_svg(pnl)[:200] + "...")
    print(f"PnL chart: {len(render_svg(pnl))} chars SVG")
