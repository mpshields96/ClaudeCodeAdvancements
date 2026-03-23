"""Report chart generator — creates SVG charts from CCA report data for Typst embedding.

Bridges CCADataCollector output to chart_generator.py chart types.
Each method takes full report data dict and returns an SVG string.

Usage:
    from report_charts import ReportChartGenerator
    gen = ReportChartGenerator(output_dir="/tmp/charts")
    charts = gen.generate_all(report_data)  # dict of name -> SVG string
    paths = gen.save_all(report_data)        # dict of name -> file path
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from chart_generator import (
    AreaChart,
    BarChart,
    BoxPlot,
    CCA_COLORS,
    DonutChart,
    HistogramChart,
    HorizontalBarChart,
    LineChart,
    ScatterPlot,
    SERIES_PALETTE,
    StackedBarChart,
    TreemapChart,
    render_svg,
)


class ReportChartGenerator:
    """Generates SVG charts from CCA report data for PDF embedding."""

    def __init__(self, output_dir=None):
        self.output_dir = output_dir

    # ── Individual charts ───────────────────────────────────────────────

    def module_tests_chart(self, data):
        """Horizontal bar chart of test counts per module, sorted descending."""
        modules = data.get("modules", [])
        if not modules or all(m.get("tests", 0) == 0 for m in modules):
            return self._empty_chart("Tests per Module")

        # Sort by test count descending
        sorted_mods = sorted(modules, key=lambda m: m.get("tests", 0), reverse=True)
        items = [(m["name"], m["tests"]) for m in sorted_mods]

        chart = HorizontalBarChart(items, title="Tests per Module", show_values=True)
        return render_svg(chart)

    def intelligence_chart(self, data):
        """Donut chart of intelligence verdict distribution."""
        intel = data.get("intelligence", {})
        if intel.get("findings_total", 0) == 0:
            return self._empty_chart("Intelligence Verdicts")

        # DonutChart expects (label, value, color) tuples
        verdict_colors = {
            "BUILD": CCA_COLORS["success"],
            "ADAPT": CCA_COLORS["accent"],
            "REFERENCE": CCA_COLORS["warning"],
            "REF-PERSONAL": CCA_COLORS["muted"],
            "SKIP": CCA_COLORS["highlight"],
            "OTHER": CCA_COLORS["border"],
        }
        segments = []
        verdict_map = [
            ("BUILD", intel.get("build", 0)),
            ("ADAPT", intel.get("adapt", 0)),
            ("REFERENCE", intel.get("reference", 0)),
            ("REF-PERSONAL", intel.get("reference_personal", 0)),
            ("SKIP", intel.get("skip", 0)),
            ("OTHER", intel.get("other", 0)),
        ]
        for label, value in verdict_map:
            if value > 0:
                segments.append((label, value, verdict_colors.get(label, CCA_COLORS["muted"])))

        if not segments:
            return self._empty_chart("Intelligence Verdicts")

        chart = DonutChart(segments, title="Intelligence Verdicts")
        return render_svg(chart)

    def mt_status_chart(self, data):
        """Bar chart of MT status breakdown (complete/active/pending)."""
        complete = len(data.get("master_tasks_complete", []))
        active = len(data.get("master_tasks_active", []))
        pending = len(data.get("master_tasks_pending", []))

        if complete + active + pending == 0:
            return self._empty_chart("Master Task Status")

        items = [
            ("Complete", complete),
            ("Active", active),
            ("Pending", pending),
        ]
        chart = BarChart(items, title="Master Task Status")
        return render_svg(chart)

    def loc_chart(self, data):
        """Bar chart of source LOC vs test LOC."""
        summary = data.get("summary", {})
        source = summary.get("source_loc", 0)
        test = summary.get("test_loc", 0)

        if source + test == 0:
            return self._empty_chart("Lines of Code")

        items = [("Source", source), ("Test", test)]
        chart = BarChart(items, title="Lines of Code")
        return render_svg(chart)

    def mt_progress_chart(self, data):
        """Stacked bar chart showing phase progress for active MTs."""
        active = data.get("master_tasks_active", [])
        if not active:
            return self._empty_chart("MT Phase Progress")

        # StackedBarChart expects data=[(label, [vals...])], series_names=[...]
        chart_data = []
        for task in active:
            label = task.get("id", "?")
            phases_done = task.get("phases_done", 0)
            total = task.get("total_phases", 0)
            remaining = max(0, total - phases_done)
            chart_data.append((label, [phases_done, remaining]))

        chart = StackedBarChart(
            data=chart_data,
            series_names=["Done", "Remaining"],
            title="MT Phase Progress",
        )
        return render_svg(chart)

    def frontier_chart(self, data):
        """Horizontal bar chart of frontier test coverage."""
        frontiers = data.get("frontiers", [])
        if not frontiers:
            return self._empty_chart("Frontier Test Coverage")

        items = [(f["name"], f.get("tests", 0)) for f in frontiers]
        chart = HorizontalBarChart(items, title="Frontier Test Coverage", width=600)
        return render_svg(chart)

    def module_loc_treemap(self, data):
        """Treemap of source LOC per module — visual size comparison."""
        modules = data.get("modules", [])
        if not modules or all(m.get("loc", 0) == 0 for m in modules):
            return self._empty_chart("Module Size (LOC)")

        # Assign colors from series palette
        items = []
        for i, m in enumerate(sorted(modules, key=lambda x: x.get("loc", 0), reverse=True)):
            loc = m.get("loc", 0)
            if loc > 0:
                color = SERIES_PALETTE[i % len(SERIES_PALETTE)]
                items.append((m["name"], loc, color))

        if not items:
            return self._empty_chart("Module Size (LOC)")

        chart = TreemapChart(data=items, title="Module Size (LOC)")
        return render_svg(chart)

    # ── CCA statistical charts (MT-32) ─────────────────────────────────

    def test_density_scatter(self, data):
        """ScatterPlot: tests vs LOC per module — reveals test density."""
        modules = data.get("modules", [])
        points = [
            {"x": m.get("loc", 0), "y": m.get("tests", 0), "label": m["name"]}
            for m in modules
            if m.get("loc", 0) > 0
        ]
        if not points:
            return self._empty_chart("Test Density by Module")

        chart = ScatterPlot(
            series=[{"name": "Modules", "data": points}],
            title="Test Density by Module",
            x_label="Source LOC",
            y_label="Tests",
            width=600,
            height=400,
            show_trend=True,
        )
        return render_svg(chart)

    def module_composition(self, data):
        """StackedBarChart: source LOC vs test LOC — code composition."""
        summary = data.get("summary", {})
        source = summary.get("source_loc", 0) or 0
        test = summary.get("test_loc", 0) or 0
        if source + test == 0:
            return self._empty_chart("Code Composition")

        chart_data = [("Project", [source, test])]
        chart = StackedBarChart(
            data=chart_data,
            series_names=["Source", "Test"],
            title="Code Composition (LOC)",
        )
        return render_svg(chart)

    # ── Kalshi financial charts (MT-33) ─────────────────────────────────

    def kalshi_cumulative_pnl(self, data):
        """LineChart: cumulative P&L over time."""
        kalshi = data.get("kalshi_analytics", {})
        if not kalshi.get("available"):
            return self._empty_chart("Cumulative P&L")
        chart_data = kalshi.get("charts", {}).get("cumulative_pnl", {})
        labels = chart_data.get("labels", [])
        values = chart_data.get("values", [])
        if not labels:
            return self._empty_chart("Cumulative P&L")
        # Thin labels for readability
        thinned = self._thin_labels(labels, max_labels=12)
        items = list(zip(thinned, values))
        chart = LineChart(items, title="Cumulative P&L ($)", show_points=True,
                          color=CCA_COLORS["success"])
        return render_svg(chart)

    def kalshi_strategy_winrate(self, data):
        """HorizontalBarChart: win rate by strategy."""
        kalshi = data.get("kalshi_analytics", {})
        if not kalshi.get("available"):
            return self._empty_chart("Strategy Win Rate")
        chart_data = kalshi.get("charts", {}).get("strategy_winrate", {})
        labels = chart_data.get("labels", [])
        values = chart_data.get("values", [])
        if not labels:
            return self._empty_chart("Strategy Win Rate")
        # Top 10 strategies only
        items = list(zip(labels[:10], values[:10]))
        chart = HorizontalBarChart(items, title="Win Rate by Strategy (%)",
                                   show_values=True, color=CCA_COLORS["primary"])
        return render_svg(chart)

    def kalshi_daily_pnl_histogram(self, data):
        """HistogramChart: daily P&L distribution."""
        kalshi = data.get("kalshi_analytics", {})
        if not kalshi.get("available"):
            return self._empty_chart("Daily P&L Distribution")
        chart_data = kalshi.get("charts", {}).get("daily_pnl_histogram", {})
        values = chart_data.get("values", [])
        if not values or len(values) < 3:
            return self._empty_chart("Daily P&L Distribution")
        chart = HistogramChart(values, title="Daily P&L Distribution ($)",
                               color=CCA_COLORS["accent"])
        return render_svg(chart)

    def kalshi_strategy_pnl_box(self, data):
        """BoxPlot: P&L distribution per strategy."""
        kalshi = data.get("kalshi_analytics", {})
        if not kalshi.get("available"):
            return self._empty_chart("Strategy P&L Distribution")
        chart_data = kalshi.get("charts", {}).get("strategy_pnl_distribution", {})
        categories = chart_data.get("categories", [])
        data_series = chart_data.get("data_series", [])
        if not categories:
            return self._empty_chart("Strategy P&L Distribution")
        # Top 8 strategies with most data points
        paired = list(zip(categories, data_series))
        paired.sort(key=lambda x: len(x[1]), reverse=True)
        paired = paired[:8]
        box_data = [(p[0], p[1]) for p in paired]
        chart = BoxPlot(box_data, title="P&L Distribution by Strategy ($)")
        return render_svg(chart)

    def kalshi_winrate_vs_profit(self, data):
        """ScatterPlot: win rate vs avg profit per strategy."""
        kalshi = data.get("kalshi_analytics", {})
        if not kalshi.get("available"):
            return self._empty_chart("Win Rate vs Avg Profit")
        chart_data = kalshi.get("charts", {}).get("winrate_vs_profit", {})
        series_list = chart_data.get("series", [])
        if not series_list or not series_list[0].get("data"):
            return self._empty_chart("Win Rate vs Avg Profit")
        points = series_list[0]["data"]
        series = [{"name": "Strategies",
                    "data": [(p["x"], p["y"]) for p in points]}]
        chart = ScatterPlot(series, title="Win Rate vs Avg Profit",
                            x_label="Win Rate (%)", y_label="Avg P&L ($)")
        return render_svg(chart)

    def kalshi_trade_volume(self, data):
        """DonutChart: trade count by strategy."""
        kalshi = data.get("kalshi_analytics", {})
        if not kalshi.get("available"):
            return self._empty_chart("Trade Volume")
        chart_data = kalshi.get("charts", {}).get("trade_volume", {})
        labels = chart_data.get("labels", [])
        values = chart_data.get("values", [])
        if not labels:
            return self._empty_chart("Trade Volume")
        # Top 8, group rest as "Other"
        if len(labels) > 8:
            top_labels = labels[:8]
            top_values = values[:8]
            other_sum = sum(values[8:])
            top_labels.append("Other")
            top_values.append(other_sum)
            labels, values = top_labels, top_values
        palette = SERIES_PALETTE[:len(labels)]
        items = [(l, v, c) for l, v, c in zip(labels, values, palette)]
        chart = DonutChart(items, title="Trade Volume by Strategy")
        return render_svg(chart)

    def kalshi_bankroll(self, data):
        """AreaChart: bankroll balance over time."""
        kalshi = data.get("kalshi_analytics", {})
        if not kalshi.get("available"):
            return self._empty_chart("Bankroll History")
        chart_data = kalshi.get("charts", {}).get("bankroll_timeline", {})
        labels = chart_data.get("labels", [])
        values = chart_data.get("values", [])
        if not labels:
            return self._empty_chart("Bankroll History")
        thinned = self._thin_labels(labels, max_labels=12)
        items = list(zip(thinned, values))
        chart = AreaChart(items, title="Bankroll ($)", color=CCA_COLORS["primary"])
        return render_svg(chart)

    # ── Self-learning charts (MT-33 Phase 5) ────────────────────────────

    def learning_event_types(self, data):
        """BarChart: journal event type distribution."""
        learning = data.get("learning_intelligence", {})
        if not learning.get("available"):
            return self._empty_chart("Journal Events")
        chart_data = learning.get("charts", {}).get("event_types", {})
        labels = chart_data.get("labels", [])
        values = chart_data.get("values", [])
        if not labels:
            return self._empty_chart("Journal Events")
        items = list(zip(labels[:10], values[:10]))
        chart = BarChart(items, title="Journal Event Types", show_values=True,
                         color=CCA_COLORS["accent"])
        return render_svg(chart)

    def learning_apf_trend(self, data):
        """LineChart: APF score over sessions."""
        learning = data.get("learning_intelligence", {})
        if not learning.get("available"):
            return self._empty_chart("APF Trend")
        chart_data = learning.get("charts", {}).get("apf_trend", {})
        labels = chart_data.get("labels", [])
        values = chart_data.get("values", [])
        if not labels:
            return self._empty_chart("APF Trend")
        items = list(zip(labels, values))
        chart = LineChart(items, title="Actionable Post Fraction (%)",
                          show_points=True, color=CCA_COLORS["primary"])
        return render_svg(chart)

    def learning_domain_distribution(self, data):
        """DonutChart: journal entries by domain."""
        learning = data.get("learning_intelligence", {})
        if not learning.get("available"):
            return self._empty_chart("Domain Distribution")
        chart_data = learning.get("charts", {}).get("domain_distribution", {})
        labels = chart_data.get("labels", [])
        values = chart_data.get("values", [])
        if not labels:
            return self._empty_chart("Domain Distribution")
        palette = SERIES_PALETTE[:len(labels)]
        items = [(l, v, c) for l, v, c in zip(labels, values, palette)]
        chart = DonutChart(items, title="Events by Domain")
        return render_svg(chart)

    def _thin_labels(self, labels, max_labels=12):
        """Thin labels for chart readability — show every Nth."""
        if len(labels) <= max_labels:
            return labels
        step = max(1, len(labels) // max_labels)
        return [l if i % step == 0 else "" for i, l in enumerate(labels)]

    # ── Batch operations ────────────────────────────────────────────────

    def generate_all(self, data):
        """Generate all charts, return dict of name -> SVG string."""
        charts = {
            "module_tests": self.module_tests_chart(data),
            "intelligence": self.intelligence_chart(data),
            "mt_status": self.mt_status_chart(data),
            "loc_distribution": self.loc_chart(data),
            "mt_progress": self.mt_progress_chart(data),
            "frontier_status": self.frontier_chart(data),
            "module_loc_treemap": self.module_loc_treemap(data),
            "test_density_scatter": self.test_density_scatter(data),
            "module_composition": self.module_composition(data),
        }
        # Kalshi financial charts (MT-33) — only if data available
        if data.get("kalshi_analytics", {}).get("available"):
            charts.update({
                "kalshi_cumulative_pnl": self.kalshi_cumulative_pnl(data),
                "kalshi_strategy_winrate": self.kalshi_strategy_winrate(data),
                "kalshi_daily_pnl_histogram": self.kalshi_daily_pnl_histogram(data),
                "kalshi_strategy_pnl_box": self.kalshi_strategy_pnl_box(data),
                "kalshi_winrate_vs_profit": self.kalshi_winrate_vs_profit(data),
                "kalshi_trade_volume": self.kalshi_trade_volume(data),
                "kalshi_bankroll": self.kalshi_bankroll(data),
            })
        # Self-learning charts (MT-33 Phase 5) — only if data available
        if data.get("learning_intelligence", {}).get("available"):
            charts.update({
                "learning_event_types": self.learning_event_types(data),
                "learning_apf_trend": self.learning_apf_trend(data),
                "learning_domain_distribution": self.learning_domain_distribution(data),
            })
        return charts

    def save_all(self, data):
        """Generate all charts and save to output_dir. Returns dict of name -> path."""
        if not self.output_dir:
            raise ValueError("output_dir must be set to save charts")

        os.makedirs(self.output_dir, exist_ok=True)
        charts = self.generate_all(data)
        paths = {}

        for name, svg in charts.items():
            path = os.path.join(self.output_dir, f"{name}.svg")
            with open(path, "w") as f:
                f.write(svg)
            paths[name] = path

        return paths

    # ── Helpers ──────────────────────────────────────────────────────────

    def _empty_chart(self, title):
        """Return a minimal SVG with 'No data' message."""
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400">'
            f'<rect width="600" height="400" fill="#ffffff"/>'
            f'<text x="300" y="30" text-anchor="middle" font-size="16" '
            f'font-family="sans-serif" font-weight="bold">{title}</text>'
            f'<text x="300" y="210" text-anchor="middle" font-size="14" '
            f'font-family="sans-serif" fill="#6b7280">No data</text>'
            f'</svg>'
        )
