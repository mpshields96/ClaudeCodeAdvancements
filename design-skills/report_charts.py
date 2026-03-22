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
    BarChart,
    CCA_COLORS,
    DonutChart,
    HorizontalBarChart,
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
        chart = HorizontalBarChart(items, title="Frontier Test Coverage")
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

    # ── Batch operations ────────────────────────────────────────────────

    def generate_all(self, data):
        """Generate all charts, return dict of name -> SVG string."""
        return {
            "module_tests": self.module_tests_chart(data),
            "intelligence": self.intelligence_chart(data),
            "mt_status": self.mt_status_chart(data),
            "loc_distribution": self.loc_chart(data),
            "mt_progress": self.mt_progress_chart(data),
            "frontier_status": self.frontier_chart(data),
            "module_loc_treemap": self.module_loc_treemap(data),
        }

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
