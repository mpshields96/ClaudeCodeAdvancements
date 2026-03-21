#!/usr/bin/env python3
"""Tests for trading_chart.py — MT-24 Phase 1."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trading_chart import (
    PnLCurve, WinRateChart, StrategyMatrix, DrawdownChart, HeatmapChart,
    render_svg, save_svg, _format_currency, _escape_xml,
)


SAMPLE_TRADES = [
    {"pnl": 35}, {"pnl": 35}, {"pnl": -65}, {"pnl": 35},
    {"pnl": 35}, {"pnl": -65}, {"pnl": 35}, {"pnl": 35},
]


class TestPnLCurve(unittest.TestCase):
    """Test P&L curve chart generation."""

    def test_basic_render(self):
        chart = PnLCurve(trades=SAMPLE_TRADES)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertIn("Cumulative P&amp;L", svg)

    def test_single_trade(self):
        chart = PnLCurve(trades=[{"pnl": 100}])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_empty_trades(self):
        chart = PnLCurve(trades=[])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_all_losses(self):
        chart = PnLCurve(trades=[{"pnl": -50}, {"pnl": -30}])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        # Should use loss color
        self.assertIn("#e94560", svg)

    def test_all_wins(self):
        chart = PnLCurve(trades=[{"pnl": 50}, {"pnl": 30}])
        svg = render_svg(chart)
        self.assertIn("#16c79a", svg)  # profit color

    def test_custom_title(self):
        chart = PnLCurve(trades=SAMPLE_TRADES, title="My Strategy")
        svg = render_svg(chart)
        self.assertIn("My Strategy", svg)

    def test_no_markers_when_disabled(self):
        chart = PnLCurve(trades=SAMPLE_TRADES, show_markers=False)
        svg = render_svg(chart)
        # Should not have individual trade circles
        self.assertNotIn("<circle", svg)

    def test_markers_shown_by_default(self):
        chart = PnLCurve(trades=SAMPLE_TRADES[:5])
        svg = render_svg(chart)
        self.assertIn("<circle", svg)

    def test_zero_line_shown(self):
        chart = PnLCurve(trades=[{"pnl": 50}, {"pnl": -100}])
        svg = render_svg(chart)
        self.assertIn("stroke-dasharray", svg)

    def test_large_dataset_no_markers(self):
        trades = [{"pnl": 10}] * 100
        chart = PnLCurve(trades=trades, show_markers=True)
        svg = render_svg(chart)
        # >50 trades should skip markers
        self.assertNotIn("<circle", svg)

    def test_custom_dimensions(self):
        chart = PnLCurve(trades=SAMPLE_TRADES, width=400, height=200)
        svg = render_svg(chart)
        self.assertIn('width="400"', svg)
        self.assertIn('height="200"', svg)


class TestWinRateChart(unittest.TestCase):
    """Test win rate chart generation."""

    def test_basic_render(self):
        results = [True, False, True, True, False] * 10  # 50 results
        chart = WinRateChart(results=results, window=10)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("Rolling Win Rate", svg)

    def test_insufficient_data(self):
        results = [True, False, True]
        chart = WinRateChart(results=results, window=20)
        svg = render_svg(chart)
        self.assertIn("Need 20+ trades", svg)

    def test_with_target_rate(self):
        results = [True, False, True, True] * 10
        chart = WinRateChart(results=results, window=5, target_rate=0.6)
        svg = render_svg(chart)
        self.assertIn("target", svg)
        self.assertIn("stroke-dasharray", svg)

    def test_all_wins(self):
        results = [True] * 30
        chart = WinRateChart(results=results, window=10)
        svg = render_svg(chart)
        self.assertIn("100%", svg)

    def test_all_losses(self):
        results = [False] * 30
        chart = WinRateChart(results=results, window=10)
        svg = render_svg(chart)
        self.assertIn("0%", svg)

    def test_confidence_band(self):
        results = [True, False] * 25
        chart = WinRateChart(results=results, window=10, show_band=True)
        svg = render_svg(chart)
        self.assertIn("polygon", svg)  # Band is a polygon

    def test_no_confidence_band(self):
        results = [True, False] * 25
        chart = WinRateChart(results=results, window=10, show_band=False)
        svg = render_svg(chart)
        # Should still have polyline but no polygon for band
        self.assertIn("polyline", svg)


class TestStrategyMatrix(unittest.TestCase):
    """Test strategy comparison matrix."""

    def test_basic_render(self):
        strategies = [
            {"name": "Expiry Sniper", "trades": 100, "wins": 65, "pnl": 1200},
            {"name": "Momentum", "trades": 50, "wins": 30, "pnl": -200},
        ]
        chart = StrategyMatrix(strategies=strategies)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("Expiry Sniper", svg)
        self.assertIn("Momentum", svg)

    def test_empty_strategies(self):
        chart = StrategyMatrix(strategies=[])
        svg = render_svg(chart)
        self.assertIn("No strategies", svg)

    def test_win_rate_coloring(self):
        strategies = [
            {"name": "Good", "trades": 100, "wins": 70, "pnl": 500},
            {"name": "Bad", "trades": 100, "wins": 30, "pnl": -500},
        ]
        chart = StrategyMatrix(strategies=strategies)
        svg = render_svg(chart)
        # Should have both green and red colors
        self.assertIn("#16c79a", svg)  # profit
        self.assertIn("#e94560", svg)  # loss

    def test_zero_trades(self):
        strategies = [{"name": "Empty", "trades": 0, "wins": 0, "pnl": 0}]
        chart = StrategyMatrix(strategies=strategies)
        svg = render_svg(chart)
        self.assertIn("0%", svg)

    def test_headers_present(self):
        strategies = [{"name": "Test", "trades": 10, "wins": 5, "pnl": 100}]
        chart = StrategyMatrix(strategies=strategies)
        svg = render_svg(chart)
        self.assertIn("Strategy", svg)
        self.assertIn("Trades", svg)
        self.assertIn("Win Rate", svg)


class TestDrawdownChart(unittest.TestCase):
    """Test drawdown visualization."""

    def test_basic_render(self):
        chart = DrawdownChart(trades=SAMPLE_TRADES)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("Drawdown", svg)

    def test_no_drawdown(self):
        chart = DrawdownChart(trades=[{"pnl": 10}, {"pnl": 10}])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_deep_drawdown(self):
        trades = [{"pnl": 100}, {"pnl": -200}, {"pnl": -100}]
        chart = DrawdownChart(trades=trades)
        svg = render_svg(chart)
        self.assertIn("Max DD", svg)

    def test_empty_trades(self):
        chart = DrawdownChart(trades=[])
        svg = render_svg(chart)
        self.assertIn("<svg", svg)

    def test_max_drawdown_marker(self):
        trades = [{"pnl": 50}, {"pnl": -100}, {"pnl": 50}]
        chart = DrawdownChart(trades=trades)
        svg = render_svg(chart)
        self.assertIn("<circle", svg)  # Max DD point marker


class TestHeatmapChart(unittest.TestCase):
    """Test heatmap chart generation."""

    def test_basic_render(self):
        data = [
            {"hour": 10, "day": 1, "value": 50},
            {"hour": 14, "day": 3, "value": -30},
            {"hour": 20, "day": 5, "value": 100},
        ]
        chart = HeatmapChart(data=data)
        svg = render_svg(chart)
        self.assertIn("<svg", svg)
        self.assertIn("Heatmap", svg)

    def test_empty_data(self):
        chart = HeatmapChart(data=[])
        svg = render_svg(chart)
        self.assertIn("No data", svg)

    def test_all_positive(self):
        data = [{"hour": h, "day": 0, "value": h * 10} for h in range(24)]
        chart = HeatmapChart(data=data)
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_all_negative(self):
        data = [{"hour": h, "day": 0, "value": -h * 10} for h in range(24)]
        chart = HeatmapChart(data=data)
        svg = render_svg(chart)
        self.assertIn("<rect", svg)

    def test_day_labels(self):
        data = [{"hour": 0, "day": d, "value": 10} for d in range(7)]
        chart = HeatmapChart(data=data)
        svg = render_svg(chart)
        self.assertIn("Mon", svg)
        self.assertIn("Sun", svg)


class TestUtilities(unittest.TestCase):
    """Test utility functions."""

    def test_format_currency_positive_dollars(self):
        self.assertEqual(_format_currency(150), "$+1.50")

    def test_format_currency_negative_dollars(self):
        self.assertEqual(_format_currency(-250), "$-2.50")

    def test_format_currency_cents(self):
        self.assertEqual(_format_currency(50), "+50c")

    def test_format_currency_zero(self):
        self.assertEqual(_format_currency(0), "+0c")

    def test_escape_xml(self):
        self.assertEqual(_escape_xml("A & B"), "A &amp; B")
        self.assertEqual(_escape_xml("x < y"), "x &lt; y")
        self.assertEqual(_escape_xml('say "hi"'), "say &quot;hi&quot;")


class TestSaveSVG(unittest.TestCase):
    """Test file saving."""

    def test_save_to_file(self):
        chart = PnLCurve(trades=SAMPLE_TRADES)
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            result = save_svg(chart, path)
            self.assertEqual(result, path)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("<svg", content)
        finally:
            os.unlink(path)


class TestRenderDispatch(unittest.TestCase):
    """Test render_svg dispatch."""

    def test_unknown_chart_type_raises(self):
        class FakeChart:
            chart_type = "nonexistent"
        with self.assertRaises(ValueError):
            render_svg(FakeChart())

    def test_all_chart_types(self):
        charts = [
            PnLCurve(trades=SAMPLE_TRADES),
            WinRateChart(results=[True, False] * 15, window=5),
            StrategyMatrix(strategies=[{"name": "X", "trades": 10, "wins": 5, "pnl": 100}]),
            DrawdownChart(trades=SAMPLE_TRADES),
            HeatmapChart(data=[{"hour": 10, "day": 1, "value": 50}]),
        ]
        for chart in charts:
            svg = render_svg(chart)
            self.assertIn("<svg", svg, f"Failed for {chart.chart_type}")
            self.assertIn("</svg>", svg, f"Failed for {chart.chart_type}")


if __name__ == "__main__":
    unittest.main()
