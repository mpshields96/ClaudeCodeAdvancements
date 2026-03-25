#!/usr/bin/env python3
"""
dashboard_generator.py — Self-contained HTML dashboard for CCA project data.

Generates a single HTML file with inline CSS (no external deps) that displays:
- Metric cards (tests, modules, sessions, etc.)
- Module status grid with completion indicators
- Master task priority table with score bars
- Generation timestamp and project info

Follows design-guide.md: color palette, typography, layout rules.
All output is XSS-safe (HTML entities escaped).

Usage:
    python3 dashboard_generator.py generate --output dashboard.html
    python3 dashboard_generator.py generate --output dashboard.html --demo

Stdlib only. No external dependencies.
"""

import html
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

# Import chart generator (same module)
try:
    from chart_generator import (
        HorizontalBarChart, DonutChart, render_svg, CCA_COLORS as CHART_COLORS,
    )
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

# Import figure generator for multi-panel figures
try:
    from figure_generator import Figure, FigurePanel, render_figure
    FIGURES_AVAILABLE = True
except ImportError:
    FIGURES_AVAILABLE = False

# Import canonical design tokens
try:
    from design_linter import CCA_PALETTE, DARK_PALETTE
except ImportError:
    CCA_PALETTE = {}
    DARK_PALETTE = {}


# ── Design tokens from design_linter.py (canonical source) ───────────────────

COLORS = {
    "primary": CCA_PALETTE.get("primary", "#1a1a2e"),
    "accent": CCA_PALETTE.get("accent", "#0f3460"),
    "highlight": CCA_PALETTE.get("highlight", "#e94560"),
    "success": CCA_PALETTE.get("success", "#16c79a"),
    "muted": CCA_PALETTE.get("muted", "#6b7280"),
    "background": CCA_PALETTE.get("bg", "#ffffff"),
    "surface": CCA_PALETTE.get("surface", "#f8f9fa"),
    "border": CCA_PALETTE.get("border", "#e5e7eb"),
    "warning": CCA_PALETTE.get("warning", "#f59e0b"),
}


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class ModuleCard:
    """A module in the project."""
    name: str
    path: str
    status: str  # COMPLETE, ACTIVE, FAILING
    tests: int
    items: str  # e.g., "MEM-1-5 COMPLETE"

    def status_color(self) -> str:
        if self.status == "COMPLETE":
            return COLORS["success"]
        elif self.status == "FAILING":
            return COLORS["highlight"]
        return COLORS["accent"]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MasterTaskRow:
    """A master task entry."""
    id: str
    name: str
    score: float
    status: str

    def score_bar_width(self) -> float:
        """Score as percentage of max (20)."""
        return min(100.0, (self.score / 20.0) * 100.0)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["score_bar_width"] = self.score_bar_width()
        return d


@dataclass
class MetricCard:
    """A top-level metric."""
    label: str
    value: str
    status: str = "info"  # success, warning, critical, info

    def status_color(self) -> str:
        return {
            "success": COLORS["success"],
            "warning": COLORS["warning"],
            "critical": COLORS["highlight"],
        }.get(self.status, COLORS["accent"])

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DashboardData:
    """All data needed to render the dashboard."""
    title: str = "CCA Project Dashboard"
    generated_date: str = field(default_factory=lambda: date.today().isoformat())
    modules: List[ModuleCard] = field(default_factory=list)
    master_tasks: List[MasterTaskRow] = field(default_factory=list)
    metrics: List[MetricCard] = field(default_factory=list)
    session_number: int = 0
    daily_diff: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "generated_date": self.generated_date,
            "session_number": self.session_number,
            "modules": [m.to_dict() for m in self.modules],
            "master_tasks": [t.to_dict() for t in self.master_tasks],
            "metrics": [m.to_dict() for m in self.metrics],
            "daily_diff": self.daily_diff,
        }


# ── HTML Renderer ────────────────────────────────────────────────────────────


def _e(text: str) -> str:
    """HTML-escape text to prevent XSS."""
    return html.escape(str(text))


class DashboardRenderer:
    """Renders DashboardData as self-contained HTML."""

    def render(self, data: DashboardData, theme: str = "light", refresh_seconds: int = 0) -> str:
        """Generate complete HTML string. theme: 'light' or 'dark'. refresh_seconds: auto-refresh interval (0=off)."""
        metrics_html = self._render_metrics(data.metrics)
        daily_diff_html = self._render_daily_diff(data.daily_diff)
        charts_html = self._render_charts(data)
        modules_html = self._render_modules(data.modules)
        tasks_html = self._render_master_tasks(data.master_tasks)
        initial_theme = "dark" if theme == "dark" else "light"

        # Auto-refresh meta tag
        refresh_meta = ""
        refresh_notice = ""
        if refresh_seconds and refresh_seconds > 0:
            refresh_meta = f'\n<meta http-equiv="refresh" content="{refresh_seconds}">'
            refresh_notice = f'<span class="auto-refresh-notice"> — auto-refresh every {refresh_seconds}s</span>'

        # Embedded JSON data for programmatic access
        # Filter zero-delta modules from daily_diff to match visual output
        export_dict = data.to_dict()
        if export_dict.get("daily_diff") and export_dict["daily_diff"].get("module_deltas"):
            export_dict["daily_diff"]["module_deltas"] = [
                m for m in export_dict["daily_diff"]["module_deltas"]
                if m.get("tests_delta", 0) != 0 or m.get("loc_delta", 0) != 0
            ]
        # Escape < and > to prevent XSS inside script tags
        data_json = json.dumps(export_dict, indent=None, default=str)
        data_json = data_json.replace("<", "\\u003c").replace(">", "\\u003e")

        return f"""<!DOCTYPE html>
<html lang="en" data-theme="{initial_theme}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{refresh_meta}
<title>{_e(data.title)}</title>
<style>
{self._css()}
</style>
</head>
<body>
<div class="container" role="main">
  <header>
    <div class="header-flex">
      <div>
        <h1>{_e(data.title)}</h1>
        <p class="subtitle">Generated {_e(data.generated_date)}{f' — Session {data.session_number}' if data.session_number else ''}{refresh_notice}</p>
      </div>
      <button id="theme-toggle" onclick="toggleTheme()" aria-label="Toggle dark/light mode" title="Toggle dark/light mode" style="background:var(--surface);border:1px solid var(--border);border-radius:4px;padding:6px 12px;cursor:pointer;font-size:14px;color:var(--text-primary)">&#9789;</button>
    </div>
  </header>

  {metrics_html}
  {daily_diff_html}
  {charts_html}
  {modules_html}
  {tasks_html}

  <footer>
    <p>Generated by CCA Dashboard Generator — {_e(datetime.now().strftime('%Y-%m-%d %H:%M'))}</p>
  </footer>
</div>
<script id="dashboard-data" type="application/json">{data_json}</script>
<script>
{self._js()}
</script>
</body>
</html>"""

    def render_to_file(self, data: DashboardData, path: str, theme: str = "light", refresh_seconds: int = 0):
        """Render and write to file."""
        content = self.render(data, theme=theme, refresh_seconds=refresh_seconds)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            f.write(content)
        os.replace(tmp, path)

    def _css(self) -> str:
        return f"""
/* ── Theme custom properties ── */
:root, [data-theme="light"] {{
  --bg-primary: {COLORS['background']};
  --text-primary: {COLORS['primary']};
  --surface: {COLORS['surface']};
  --border: {COLORS['border']};
  --muted: {COLORS['muted']};
  --accent: {COLORS['accent']};
  --highlight: {COLORS['highlight']};
  --success: {COLORS['success']};
  --warning: {COLORS['warning']};
}}
[data-theme="dark"] {{
  --bg-primary: {DARK_PALETTE.get('dark_bg', '#0d1117')};
  --text-primary: {DARK_PALETTE.get('dark_text', '#e6edf3')};
  --surface: {DARK_PALETTE.get('dark_surface', '#161b22')};
  --border: {DARK_PALETTE.get('dark_border', '#30363d')};
  --muted: {DARK_PALETTE.get('dark_muted', '#8b949e')};
  --accent: {DARK_PALETTE.get('dark_accent', '#388bfd')};
  --highlight: {DARK_PALETTE.get('dark_highlight', '#f85149')};
  --success: {DARK_PALETTE.get('dark_success', '#3fb950')};
  --warning: {DARK_PALETTE.get('dark_warning', '#d29922')};
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: 'Source Sans 3', 'Helvetica Neue', Arial, sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.5;
  transition: background 0.2s, color 0.2s;
}}
.container {{
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 20px;
}}
header {{
  border-bottom: 2px solid var(--accent);
  padding-bottom: 12px;
  margin-bottom: 24px;
}}
header h1 {{
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}}
.subtitle {{
  font-size: 14px;
  color: var(--muted);
  margin-top: 4px;
}}

/* Metrics row */
.metrics {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}}
.metric-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 16px;
  text-align: center;
}}
.metric-value {{
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}}
.metric-label {{
  font-size: 12px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 4px;
}}

/* Section headers — collapsible */
.section-header {{
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  user-select: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
}}
.section-header .chevron {{
  font-size: 12px;
  transition: transform 0.2s;
  color: var(--muted);
}}
.section-header.collapsed .chevron {{
  transform: rotate(-90deg);
}}
.collapsible-content {{
  overflow: hidden;
  transition: max-height 0.3s ease;
}}
.collapsible-content.collapsed {{
  max-height: 0 !important;
  margin-bottom: 0;
}}

/* Module search */
.module-search-wrapper {{
  margin-bottom: 12px;
}}
.module-search-wrapper input {{
  width: 100%;
  max-width: 320px;
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 13px;
  background: var(--surface);
  color: var(--text-primary);
  outline: none;
}}
.module-search-wrapper input:focus {{
  border-color: var(--accent);
}}

/* Module grid */
.modules {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
  margin-bottom: 32px;
}}
.module-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 12px 16px;
  border-left: 4px solid var(--muted);
  transition: opacity 0.2s;
}}
.module-name {{
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}}
.module-path {{
  font-size: 11px;
  font-family: 'Source Code Pro', 'Courier New', monospace;
  color: var(--muted);
}}
.module-meta {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  font-size: 12px;
}}
.module-tests {{
  color: var(--muted);
}}
.module-status {{
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 12px;
  color: white;
}}

/* Master tasks table — sortable */
.tasks-table {{
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 32px;
  font-size: 13px;
}}
.tasks-table th {{
  background: var(--accent);
  color: white;
  padding: 8px 12px;
  text-align: left;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  cursor: pointer;
  user-select: none;
}}
.tasks-table th .sort-indicator {{
  margin-left: 4px;
  font-size: 10px;
  opacity: 0.6;
}}
.tasks-table td {{
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
}}
.tasks-table tr:nth-child(even) {{
  background: var(--surface);
}}
.score-bar {{
  background: var(--border);
  border-radius: 4px;
  height: 8px;
  width: 100%;
  max-width: 120px;
}}
.score-bar-fill {{
  height: 100%;
  border-radius: 4px;
  background: var(--accent);
}}

/* Footer */
footer {{
  margin-top: 32px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  text-align: center;
  font-size: 11px;
  color: var(--muted);
}}

/* Charts row */
.charts {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}}
.chart-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 12px;
  text-align: center;
}}
.chart-card svg {{
  max-width: 100%;
  height: auto;
}}

/* Daily diff */
.daily-diff {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 16px;
  margin-bottom: 32px;
}}
.diff-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}}
.diff-title {{
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}}
.diff-range {{
  font-size: 11px;
  color: var(--muted);
}}
.diff-totals {{
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
}}
.diff-stat {{
  text-align: center;
}}
.diff-delta {{
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}}
.diff-delta.positive {{ color: var(--success); }}
.diff-delta.negative {{ color: var(--highlight); }}
.diff-delta.zero {{ color: var(--muted); }}
.diff-label {{
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
.diff-modules {{
  font-size: 12px;
  color: var(--text-primary);
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}}
.diff-modules span {{
  color: var(--muted);
}}

/* Header flex */
.header-flex {{
  display: flex;
  justify-content: space-between;
  align-items: center;
}}

/* Auto-refresh notice */
.auto-refresh-notice {{
  font-size: 11px;
  color: var(--muted);
  font-style: italic;
}}

/* Responsive — tablet */
@media (max-width: 768px) {{
  .metrics {{ grid-template-columns: repeat(2, 1fr); }}
  .modules {{ grid-template-columns: 1fr; }}
  .charts {{ grid-template-columns: 1fr; }}
  .header-flex {{ flex-direction: column; align-items: flex-start; gap: 8px; }}
  .tasks-table {{ font-size: 12px; }}
  .tasks-table th, .tasks-table td {{ padding: 6px 8px; }}
}}

/* Responsive — mobile */
@media (max-width: 600px) {{
  .metrics {{ grid-template-columns: repeat(2, 1fr); }}
  .modules {{ grid-template-columns: 1fr; }}
  .charts {{ grid-template-columns: 1fr; }}
  .metric-value {{ font-size: 22px; }}
  .header-flex {{ flex-direction: column; align-items: flex-start; gap: 8px; }}
}}

/* Print styles */
@media print {{
  #theme-toggle, .module-search-wrapper, .auto-refresh-notice {{ display:none; }}
  body {{ background: white; color: black; }}
  .container {{ max-width: 100%; padding: 0; }}
  .module-card, .metric-card, .chart-card {{ break-inside: avoid; }}
}}
"""

    def _js(self) -> str:
        """JavaScript for v2 interactive features."""
        return """
/* Theme toggle */
function toggleTheme() {
  var el = document.documentElement;
  var current = el.getAttribute('data-theme') || 'light';
  var next = current === 'dark' ? 'light' : 'dark';
  el.setAttribute('data-theme', next);
  try { localStorage.setItem('cca-dashboard-theme', next); } catch(e) {}
  var btn = document.getElementById('theme-toggle');
  if (btn) btn.textContent = next === 'dark' ? '\\u2600' : '\\u263D';
}
/* Restore saved theme */
(function() {
  try {
    var saved = localStorage.getItem('cca-dashboard-theme');
    if (saved) {
      document.documentElement.setAttribute('data-theme', saved);
      var btn = document.getElementById('theme-toggle');
      if (btn) btn.textContent = saved === 'dark' ? '\\u2600' : '\\u263D';
    }
  } catch(e) {}
})();

/* Module search/filter */
function filterModules() {
  var query = (document.getElementById('module-search').value || '').toLowerCase();
  var cards = document.querySelectorAll('.module-card[data-name]');
  for (var i = 0; i < cards.length; i++) {
    var name = (cards[i].getAttribute('data-name') || '').toLowerCase();
    cards[i].style.display = (!query || name.indexOf(query) !== -1) ? '' : 'none';
  }
}

/* Sortable table */
var sortState = {};
function sortTable(colIdx) {
  var table = document.querySelector('.tasks-table.sortable');
  if (!table) return;
  var tbody = table.querySelector('tbody');
  if (!tbody) return;
  var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
  var dir = (sortState[colIdx] === 'asc') ? 'desc' : 'asc';
  sortState[colIdx] = dir;
  rows.sort(function(a, b) {
    var ca = a.cells[colIdx], cb = b.cells[colIdx];
    if (!ca || !cb) return 0;
    var va = ca.textContent.trim(), vb = cb.textContent.trim();
    var na = parseFloat(va), nb = parseFloat(vb);
    if (!isNaN(na) && !isNaN(nb)) {
      return dir === 'asc' ? na - nb : nb - na;
    }
    return dir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
  });
  for (var i = 0; i < rows.length; i++) tbody.appendChild(rows[i]);
  /* Update sort indicators */
  var ths = table.querySelectorAll('th');
  for (var j = 0; j < ths.length; j++) {
    var ind = ths[j].querySelector('.sort-indicator');
    if (ind) ind.textContent = (j === colIdx) ? (dir === 'asc' ? '\\u25B2' : '\\u25BC') : '\\u25BD';
  }
}

/* Collapsible sections */
function toggleSection(headerId, contentId) {
  var header = document.getElementById(headerId);
  var content = document.getElementById(contentId);
  if (!header || !content) return;
  var isCollapsed = content.classList.contains('collapsed');
  if (isCollapsed) {
    content.classList.remove('collapsed');
    header.classList.remove('collapsed');
  } else {
    content.classList.add('collapsed');
    header.classList.add('collapsed');
  }
}

/* Keyboard shortcuts */
document.addEventListener('keydown', function(e) {
  var search = document.getElementById('module-search');
  /* Escape clears and blurs search */
  if (e.key === 'Escape' && search) {
    search.value = '';
    filterModules();
    search.blur();
  }
  /* / focuses search (when not already in an input) */
  if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
    e.preventDefault();
    if (search) search.focus();
  }
});
"""

    def _render_charts(self, data: DashboardData) -> str:
        """Render inline SVG charts from module and task data."""
        if not CHARTS_AVAILABLE or not data.modules:
            return ""

        charts = []

        # Tests by module (horizontal bar)
        module_data = sorted(
            [(m.name, m.tests) for m in data.modules],
            key=lambda x: x[1], reverse=True,
        )
        if module_data:
            bar_height = max(200, len(module_data) * 32 + 60)
            bar_chart = HorizontalBarChart(
                module_data, title="Tests by Module",
                width=480, height=bar_height,
                show_values=True,
            )
            charts.append(f'<div class="chart-card">{render_svg(bar_chart)}</div>')

        # Task status donut
        if data.master_tasks:
            complete = sum(1 for t in data.master_tasks if "COMPLETE" in t.status.upper())
            in_progress = sum(1 for t in data.master_tasks
                              if "PROGRESS" in t.status.upper() or "ACTIVE" in t.status.upper())
            other = len(data.master_tasks) - complete - in_progress
            donut_data = []
            if complete:
                donut_data.append(("Complete", complete, CHART_COLORS["success"]))
            if in_progress:
                donut_data.append(("In Progress", in_progress, CHART_COLORS["accent"]))
            if other:
                donut_data.append(("Other", other, CHART_COLORS["muted"]))
            if donut_data:
                total = len(data.master_tasks)
                pct = int((complete / total) * 100) if total else 0
                donut = DonutChart(
                    donut_data, title="Master Task Status",
                    width=300, height=280,
                    center_text=f"{pct}%",
                )
                charts.append(f'<div class="chart-card">{render_svg(donut)}</div>')

        # Summary figure (multi-panel, MT-32 Phase 7)
        summary_fig_svg = self._render_summary_figure(data.modules)
        if summary_fig_svg:
            charts.append(f'<div class="chart-card">{summary_fig_svg}</div>')

        if not charts:
            return ""

        return f"""<h2 class="section-header">Charts</h2>
<div class="charts">
{chr(10).join(charts)}
</div>"""

    def _render_summary_figure(self, modules: list) -> str:
        """Render a multi-panel summary figure from module data.

        Uses figure_generator to create a 2-panel figure:
          (a) Tests by module (horizontal bar)
          (b) Module status breakdown (donut)

        Returns SVG string, or empty string if no data or figures unavailable.
        """
        if not modules or not FIGURES_AVAILABLE or not CHARTS_AVAILABLE:
            return ""

        panels = []

        # Panel (a): Tests by module
        sorted_mods = sorted(modules, key=lambda m: m.tests, reverse=True)
        items = [(m.name, m.tests) for m in sorted_mods[:8]]
        if items:
            bar_height = max(200, len(items) * 32 + 60)
            chart_a = HorizontalBarChart(
                items, title="Tests by Module",
                width=400, height=bar_height, show_values=True,
            )
            panels.append(FigurePanel(chart=chart_a, label="a"))

        # Panel (b): Status breakdown donut
        complete = sum(1 for m in modules if m.status == "COMPLETE")
        active = len(modules) - complete
        if complete or active:
            donut_data = []
            if complete:
                donut_data.append(("Complete", complete, CHART_COLORS["success"]))
            if active:
                donut_data.append(("Active", active, CHART_COLORS["accent"]))
            chart_b = DonutChart(
                donut_data, title="Module Status",
                width=300, height=280,
                center_text=f"{complete}/{len(modules)}",
            )
            panels.append(FigurePanel(chart=chart_b, label="b"))

        if not panels:
            return ""

        fig = Figure(panels=panels, cols=len(panels), title="Project Summary")
        return render_figure(fig)

    def _render_daily_diff(self, diff: Optional[dict]) -> str:
        """Render daily snapshot diff as a compact summary card."""
        if not diff:
            return ""

        dr = diff.get("date_range", {})
        td = diff.get("totals_delta", {})

        # Build delta items
        delta_items = []
        for key, label in [("tests", "Tests"), ("suites", "Suites"), ("loc", "LOC"), ("py_files", "Files")]:
            d = td.get(key, {})
            delta = d.get("delta", 0)
            if delta != 0:
                sign = "+" if delta > 0 else ""
                css_class = "positive" if delta > 0 else "negative"
                delta_items.append(
                    f'<div class="diff-stat">'
                    f'<div class="diff-delta {css_class}">{sign}{delta}</div>'
                    f'<div class="diff-label">{_e(label)}</div></div>'
                )

        if not delta_items:
            delta_items.append(
                '<div class="diff-stat">'
                '<div class="diff-delta zero">0</div>'
                '<div class="diff-label">No changes</div></div>'
            )

        totals_html = "\n".join(delta_items)

        # Module-level changes
        module_lines = []
        for md in diff.get("module_deltas", []):
            parts = []
            if md.get("tests_delta", 0) != 0:
                sign = "+" if md["tests_delta"] > 0 else ""
                parts.append(f"{sign}{md['tests_delta']} tests")
            if md.get("loc_delta", 0) != 0:
                sign = "+" if md["loc_delta"] > 0 else ""
                parts.append(f"{sign}{md['loc_delta']} LOC")
            if parts:
                module_lines.append(f"<strong>{_e(md['name'])}</strong>: <span>{_e(', '.join(parts))}</span>")

        modules_html = ""
        if module_lines:
            modules_html = f'<div class="diff-modules">{" &middot; ".join(module_lines)}</div>'

        return f"""<div class="daily-diff">
  <div class="diff-header">
    <span class="diff-title">Daily Changes</span>
    <span class="diff-range">{_e(dr.get('from', '?'))} &rarr; {_e(dr.get('to', '?'))}</span>
  </div>
  <div class="diff-totals">{totals_html}</div>
  {modules_html}
</div>"""

    def _render_metrics(self, metrics: List[MetricCard]) -> str:
        if not metrics:
            return ""
        cards = []
        for m in metrics:
            cards.append(f"""  <div class="metric-card">
    <div class="metric-value" style="color: {m.status_color()}">{_e(m.value)}</div>
    <div class="metric-label">{_e(m.label)}</div>
  </div>""")
        return f"""<div class="metrics">
{chr(10).join(cards)}
</div>"""

    def _render_modules(self, modules: List[ModuleCard]) -> str:
        if not modules:
            return ""
        cards = []
        for m in modules:
            cards.append(f"""  <div class="module-card" data-name="{_e(m.name)}" style="border-left-color: {m.status_color()}">
    <div class="module-name">{_e(m.name)}</div>
    <div class="module-path">{_e(m.path)}</div>
    <div class="module-meta">
      <span class="module-tests">{m.tests} tests</span>
      <span class="module-status" style="background: {m.status_color()}">{_e(m.status)}</span>
    </div>
  </div>""")
        return f"""<h2 class="section-header collapsible" id="modules-header" onclick="toggleSection('modules-header','modules-content')">Modules <span class="chevron">&#9660;</span></h2>
<div id="modules-content" class="collapsible-content">
<div class="module-search-wrapper">
  <input type="text" id="module-search" placeholder="Filter modules..." oninput="filterModules()" aria-label="Filter modules by name">
</div>
<div class="modules">
{chr(10).join(cards)}
</div>
</div>"""

    def _render_master_tasks(self, tasks: List[MasterTaskRow]) -> str:
        if not tasks:
            return ""
        rows = []
        for t in tasks:
            width = t.score_bar_width()
            rows.append(f"""  <tr>
    <td><strong>{_e(t.id)}</strong></td>
    <td>{_e(t.name)}</td>
    <td>
      <div style="display:flex;align-items:center;gap:8px">
        <span>{t.score:.1f}</span>
        <div class="score-bar"><div class="score-bar-fill" style="width:{width:.1f}%"></div></div>
      </div>
    </td>
    <td>{_e(t.status)}</td>
  </tr>""")
        return f"""<h2 class="section-header collapsible" id="tasks-header" onclick="toggleSection('tasks-header','tasks-content')">Master Tasks <span class="chevron">&#9660;</span></h2>
<div id="tasks-content" class="collapsible-content">
<table class="tasks-table sortable">
<thead><tr><th scope="col" onclick="sortTable(0)" style="cursor:pointer">ID <span class="sort-indicator">&#9661;</span></th><th scope="col" onclick="sortTable(1)" style="cursor:pointer">Name <span class="sort-indicator">&#9661;</span></th><th scope="col" onclick="sortTable(2)" style="cursor:pointer">Priority <span class="sort-indicator">&#9661;</span></th><th scope="col" onclick="sortTable(3)" style="cursor:pointer">Status <span class="sort-indicator">&#9661;</span></th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</div>"""


# ── Demo data ────────────────────────────────────────────────────────────────


def _demo_data() -> DashboardData:
    """Generate demo data for testing."""
    data = DashboardData(title="CCA Project Dashboard", session_number=48)
    data.metrics = [
        MetricCard(label="Total Tests", value="1653", status="success"),
        MetricCard(label="Modules", value="9", status="info"),
        MetricCard(label="Test Suites", value="41", status="info"),
        MetricCard(label="Master Tasks", value="18", status="info"),
    ]
    data.modules = [
        ModuleCard(name="Memory System", path="memory-system/", status="COMPLETE", tests=94, items="MEM-1-5"),
        ModuleCard(name="Spec System", path="spec-system/", status="COMPLETE", tests=90, items="SPEC-1-6"),
        ModuleCard(name="Context Monitor", path="context-monitor/", status="COMPLETE", tests=232, items="CTX-1-6 + Pacer"),
        ModuleCard(name="Agent Guard", path="agent-guard/", status="COMPLETE", tests=264, items="AG-1-7"),
        ModuleCard(name="Usage Dashboard", path="usage-dashboard/", status="COMPLETE", tests=196, items="USAGE-1-3"),
        ModuleCard(name="Reddit Intelligence", path="reddit-intelligence/", status="ACTIVE", tests=263, items="MT-6,9,11,14,15"),
        ModuleCard(name="Self-Learning", path="self-learning/", status="ACTIVE", tests=355, items="MT-7,10,12"),
        ModuleCard(name="Design Skills", path="design-skills/", status="ACTIVE", tests=71, items="MT-17"),
        ModuleCard(name="Research", path="research/", status="ACTIVE", tests=29, items="MT-8/13"),
    ]
    data.master_tasks = [
        MasterTaskRow(id="MT-10", name="YoYo Self-Learning", score=9.0, status="Phase 2 COMPLETE"),
        MasterTaskRow(id="MT-9", name="Autonomous Scanning", score=8.0, status="Phase 2 COMPLETE"),
        MasterTaskRow(id="MT-11", name="GitHub Intelligence", score=7.0, status="Phase 2 VALIDATED"),
        MasterTaskRow(id="MT-7", name="Trace Analyzer", score=7.0, status="Phase 2 COMPLETE"),
        MasterTaskRow(id="MT-17", name="Design/Reports", score=6.0, status="Phase 3 IN PROGRESS"),
        MasterTaskRow(id="MT-14", name="Re-scanning", score=6.0, status="Phase 1 COMPLETE"),
    ]
    return data


# ── CLI ──────────────────────────────────────────────────────────────────────


def cli_main(args: list = None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args:
        print(
            "Usage: python3 dashboard_generator.py generate --output FILE [--demo]\n"
            "\n"
            "Options:\n"
            "  --output FILE  Output HTML file path\n"
            "  --demo         Use demo data instead of reading project files"
        )
        return

    cmd = args[0]

    if cmd == "generate":
        output = None
        demo = False
        theme = "light"
        refresh = 0
        i = 1
        while i < len(args):
            if args[i] == "--output" and i + 1 < len(args):
                output = args[i + 1]
                i += 2
            elif args[i] == "--demo":
                demo = True
                i += 1
            elif args[i] == "--theme" and i + 1 < len(args):
                theme = args[i + 1]
                i += 2
            elif args[i] == "--refresh" and i + 1 < len(args):
                try:
                    refresh = int(args[i + 1])
                except ValueError:
                    refresh = 0
                i += 2
            else:
                i += 1

        if not output:
            print("Error: --output is required")
            return

        if demo:
            data = _demo_data()
        else:
            data = _collect_project_data()

        renderer = DashboardRenderer()
        renderer.render_to_file(data, output, theme=theme, refresh_seconds=refresh)
        print(f"Dashboard written to {output}")

    else:
        print(f"Unknown command: {cmd}")


def _collect_project_data() -> DashboardData:
    """Collect real CCA project data from PROJECT_INDEX, MASTER_TASKS, SESSION_STATE."""
    import re as _re
    project_root = str(Path(__file__).parent.parent)
    data = DashboardData()

    # ── Parse PROJECT_INDEX.md for modules ──
    index_path = os.path.join(project_root, "PROJECT_INDEX.md")
    if os.path.exists(index_path):
        with open(index_path) as f:
            content = f.read()
        in_module_table = False
        for line in content.split("\n"):
            line = line.strip()
            if "| Module " in line or "| Module|" in line:
                in_module_table = True
                continue
            if in_module_table and line.startswith("|---"):
                continue
            if in_module_table and line.startswith("|"):
                parts = [p.strip() for p in line.split("|")]
                parts = [p for p in parts if p]
                if len(parts) >= 4:
                    name = parts[0]
                    path = parts[1].strip("`")
                    items = parts[2]
                    try:
                        tests = int(parts[3])
                    except ValueError:
                        continue
                    status = "COMPLETE" if "COMPLETE" in items.upper() else "ACTIVE"
                    data.modules.append(ModuleCard(
                        name=name, path=path, status=status,
                        tests=tests, items=items,
                    ))
            elif in_module_table and not line.startswith("|"):
                in_module_table = False

        # Extract total test count from "Total: NNNN tests" line
        total_match = _re.search(r"\*\*Total:\s*~?([\d,]+)\s*tests\s*\(~?(\d+)\s*suites\)", content)
        if total_match:
            total_tests = int(total_match.group(1).replace(",", ""))
            total_suites = int(total_match.group(2))
        else:
            total_tests = sum(m.tests for m in data.modules)
            total_suites = len(data.modules)
    else:
        total_tests = sum(m.tests for m in data.modules)
        total_suites = len(data.modules)

    # ── Parse MASTER_TASKS.md priority table ──
    mt_path = os.path.join(project_root, "MASTER_TASKS.md")
    if os.path.exists(mt_path):
        with open(mt_path) as f:
            mt_content = f.read()
        # Look for priority table rows: | rank | MT-N | name | base | ... | **score** | status |
        for line in mt_content.split("\n"):
            mt_match = _re.match(
                r"\|\s*\d+\s*\|\s*(MT-\d+)\s*\|\s*([^|]+)\|\s*[\d.]+\s*\|.*\*\*([\d.]+)\*\*\s*\|\s*([^|]+)\|",
                line,
            )
            if mt_match:
                data.master_tasks.append(MasterTaskRow(
                    id=mt_match.group(1).strip(),
                    name=mt_match.group(2).strip(),
                    score=float(mt_match.group(3)),
                    status=mt_match.group(4).strip(),
                ))

    # ── Parse SESSION_STATE.md for session number ──
    state_path = os.path.join(project_root, "SESSION_STATE.md")
    if os.path.exists(state_path):
        with open(state_path) as f:
            state_content = f.read()
        session_match = _re.search(r"Session\s+(\d+)", state_content)
        if session_match:
            data.session_number = int(session_match.group(1))

    # ── Daily diff ──
    try:
        sys.path.insert(0, os.path.join(project_root, "design-skills"))
        import daily_snapshot as ds
        snapshots = ds.list_snapshots(ds.SNAPSHOT_DIR)
        if len(snapshots) >= 2:
            new_snap = ds.load_snapshot(snapshots[0], ds.SNAPSHOT_DIR)
            old_snap = ds.load_snapshot(snapshots[1], ds.SNAPSHOT_DIR)
            if new_snap and old_snap:
                data.daily_diff = ds.diff_snapshots(old_snap, new_snap)
    except Exception:
        pass

    # ── Build metrics ──
    complete_count = sum(1 for m in data.modules if m.status == "COMPLETE")
    data.metrics = [
        MetricCard(label="Total Tests", value=f"{total_tests:,}", status="success"),
        MetricCard(label="Test Suites", value=str(total_suites), status="info"),
        MetricCard(label="Modules", value=str(len(data.modules)), status="info"),
        MetricCard(
            label="Complete",
            value=f"{complete_count}/{len(data.modules)}",
            status="success" if complete_count == len(data.modules) else "info",
        ),
    ]

    return data


if __name__ == "__main__":
    cli_main()
