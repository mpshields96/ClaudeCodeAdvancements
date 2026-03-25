#!/usr/bin/env python3
"""efficiency_dashboard.py — MT-36 Phase 5: Session Efficiency Dashboard.

Self-contained HTML dashboard showing session overhead trends, category
breakdowns, top time sinks, and quality-speed correlation.

Reads from:
    - session_timings.jsonl (MT-36 Phase 1 timing data)
    - session_outcomes.jsonl (MT-10 session outcomes)

Usage:
    python3 efficiency_dashboard.py                        # Generate dashboard
    python3 efficiency_dashboard.py --output path.html     # Custom output path
    python3 efficiency_dashboard.py --last 10              # Last N sessions only

Stdlib only. No external dependencies. One file = one job.
"""

import html
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TIMING_PATH = os.path.join(SCRIPT_DIR, "session_timings.jsonl")
DEFAULT_OUTCOME_PATH = os.path.join(SCRIPT_DIR, "session_outcomes.jsonl")
DEFAULT_OUTPUT_PATH = os.path.join(SCRIPT_DIR, "efficiency_dashboard.html")

OVERHEAD_CATEGORIES = {"init", "wrap", "test", "doc"}
PRODUCTIVE_CATEGORIES = {"code"}

GRADE_MAP = {
    "A+": 4.3, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0, "D-": 0.7,
    "F": 0.0,
}

# Colors matching CCA design guide (dark mode)
COLORS = {
    "bg": "#1a1a2e",
    "card": "#16213e",
    "card_border": "#0f3460",
    "text": "#e0e0e0",
    "text_muted": "#8892b0",
    "accent": "#e94560",
    "green": "#4ecca3",
    "yellow": "#ffc947",
    "blue": "#3498db",
    "purple": "#9b59b6",
    "orange": "#e67e22",
    "init": "#3498db",
    "wrap": "#e94560",
    "test": "#ffc947",
    "code": "#4ecca3",
    "doc": "#9b59b6",
    "other": "#8892b0",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_jsonl(path: str) -> list[dict]:
    """Load entries from a JSONL file, skipping corrupt lines."""
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def load_session_data(
    timing_path: str = DEFAULT_TIMING_PATH,
    outcome_path: str = DEFAULT_OUTCOME_PATH,
) -> dict:
    """Load timing and outcome data from JSONL files."""
    return {
        "timings": _load_jsonl(timing_path),
        "outcomes": _load_jsonl(outcome_path),
    }


# ---------------------------------------------------------------------------
# Data merging
# ---------------------------------------------------------------------------

def grade_to_numeric(grade: Optional[str]) -> Optional[float]:
    """Convert letter grade to numeric GPA-style value."""
    if grade is None:
        return None
    return GRADE_MAP.get(grade)


def merge_timing_and_outcomes(
    timings: list[dict],
    outcomes: list[dict],
) -> list[dict]:
    """Merge timing data with session outcomes by session_id."""
    if not timings:
        return []

    outcome_map = {o["session_id"]: o for o in outcomes}

    merged = []
    for t in timings:
        sid = t.get("session_id", 0)
        steps = t.get("steps", [])

        overhead_s = sum(
            s["duration_s"] for s in steps
            if s.get("category") in OVERHEAD_CATEGORIES
        )
        productive_s = sum(
            s["duration_s"] for s in steps
            if s.get("category") in PRODUCTIVE_CATEGORIES
        )
        total_s = sum(s["duration_s"] for s in steps)
        overhead_ratio = overhead_s / total_s if total_s > 0 else 0.0

        by_cat = {}
        for s in steps:
            cat = s.get("category", "other")
            by_cat[cat] = by_cat.get(cat, 0.0) + s["duration_s"]

        outcome = outcome_map.get(sid, {})

        merged.append({
            "session_id": sid,
            "timestamp": t.get("timestamp", ""),
            "total_s": round(total_s, 2),
            "overhead_s": round(overhead_s, 2),
            "productive_s": round(productive_s, 2),
            "overhead_ratio": round(overhead_ratio, 4),
            "by_category": by_cat,
            "steps": steps,
            "grade": outcome.get("grade"),
            "commits": outcome.get("commits", 0),
            "tests_total": outcome.get("tests_total", 0),
        })

    return merged


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def compute_dashboard_stats(merged: list[dict]) -> dict:
    """Compute aggregate stats for the dashboard."""
    if not merged:
        return {
            "session_count": 0,
            "avg_overhead_ratio": 0.0,
            "avg_overhead_pct": "0.0%",
            "trend": "stable",
            "category_totals": {},
            "top_sinks": [],
            "per_session": [],
            "quality_speed": [],
        }

    n = len(merged)
    ratios = [m["overhead_ratio"] for m in merged]
    avg_ratio = sum(ratios) / n

    # Trend: compare first half to second half
    trend = "stable"
    if n >= 4:
        mid = n // 2
        first_avg = sum(ratios[:mid]) / mid
        second_avg = sum(ratios[mid:]) / (n - mid)
        diff = second_avg - first_avg
        if diff < -0.05:
            trend = "improving"
        elif diff > 0.05:
            trend = "worsening"

    # Category totals
    cat_totals: dict[str, float] = {}
    for m in merged:
        for cat, dur in m["by_category"].items():
            cat_totals[cat] = cat_totals.get(cat, 0.0) + dur

    # Top sinks (overhead steps, averaged across sessions)
    step_durations: dict[str, list[float]] = {}
    step_cats: dict[str, str] = {}
    for m in merged:
        for s in m["steps"]:
            if s.get("category") not in OVERHEAD_CATEGORIES:
                continue
            name = s["name"]
            step_durations.setdefault(name, []).append(s["duration_s"])
            step_cats[name] = s["category"]

    top_sinks = []
    for name, durs in step_durations.items():
        avg = sum(durs) / len(durs)
        top_sinks.append({
            "name": name,
            "avg_s": round(avg, 2),
            "category": step_cats[name],
            "count": len(durs),
        })
    top_sinks.sort(key=lambda x: x["avg_s"], reverse=True)
    top_sinks = top_sinks[:10]

    # Per-session data for charts
    per_session = []
    for m in merged:
        per_session.append({
            "session_id": m["session_id"],
            "overhead_ratio": round(m["overhead_ratio"], 4),
            "total_s": m["total_s"],
            "overhead_s": m["overhead_s"],
            "productive_s": m["productive_s"],
            "by_category": {k: round(v, 1) for k, v in m["by_category"].items()},
            "grade": m["grade"],
        })

    # Quality vs speed data points
    quality_speed = []
    for m in merged:
        gn = grade_to_numeric(m["grade"])
        quality_speed.append({
            "session_id": m["session_id"],
            "overhead_ratio": round(m["overhead_ratio"], 4),
            "grade": m["grade"],
            "grade_numeric": gn,
        })

    return {
        "session_count": n,
        "avg_overhead_ratio": round(avg_ratio, 4),
        "avg_overhead_pct": f"{avg_ratio * 100:.1f}%",
        "best_overhead_ratio": round(min(ratios), 4),
        "worst_overhead_ratio": round(max(ratios), 4),
        "trend": trend,
        "category_totals": {k: round(v, 1) for k, v in cat_totals.items()},
        "top_sinks": top_sinks,
        "per_session": per_session,
        "quality_speed": quality_speed,
    }


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _fmt_time(seconds: float) -> str:
    """Format seconds into human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def generate_html(stats: dict) -> str:
    """Generate self-contained HTML dashboard from stats."""
    if stats["session_count"] == 0:
        return _generate_empty_html()

    data_json = json.dumps(stats, indent=2)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CCA Session Efficiency Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    background: {COLORS['bg']};
    color: {COLORS['text']};
    padding: 24px;
    line-height: 1.5;
}}
h1 {{
    font-size: 1.6rem;
    margin-bottom: 8px;
    color: {COLORS['accent']};
}}
h2 {{
    font-size: 1.1rem;
    margin-bottom: 12px;
    color: {COLORS['text']};
    border-bottom: 1px solid {COLORS['card_border']};
    padding-bottom: 6px;
}}
.subtitle {{
    color: {COLORS['text_muted']};
    font-size: 0.85rem;
    margin-bottom: 24px;
}}
.grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}}
.card {{
    background: {COLORS['card']};
    border: 1px solid {COLORS['card_border']};
    border-radius: 8px;
    padding: 16px;
}}
.card.full {{ grid-column: 1 / -1; }}
.stat-row {{
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    border-bottom: 1px solid {COLORS['card_border']}33;
}}
.stat-label {{ color: {COLORS['text_muted']}; font-size: 0.85rem; }}
.stat-value {{ font-weight: 600; }}
.stat-value.good {{ color: {COLORS['green']}; }}
.stat-value.warn {{ color: {COLORS['yellow']}; }}
.stat-value.bad {{ color: {COLORS['accent']}; }}
.trend-improving {{ color: {COLORS['green']}; }}
.trend-stable {{ color: {COLORS['text_muted']}; }}
.trend-worsening {{ color: {COLORS['accent']}; }}
.bar-chart {{ margin: 8px 0; }}
.bar-row {{
    display: flex;
    align-items: center;
    margin: 6px 0;
}}
.bar-label {{
    width: 140px;
    font-size: 0.8rem;
    color: {COLORS['text_muted']};
    flex-shrink: 0;
}}
.bar-track {{
    flex: 1;
    height: 20px;
    background: {COLORS['bg']};
    border-radius: 4px;
    overflow: hidden;
    position: relative;
}}
.bar-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s ease;
}}
.bar-value {{
    width: 60px;
    text-align: right;
    font-size: 0.8rem;
    flex-shrink: 0;
    margin-left: 8px;
}}
canvas {{
    width: 100% !important;
    max-height: 250px;
}}
.stacked-bar {{
    display: flex;
    height: 28px;
    border-radius: 4px;
    overflow: hidden;
    margin: 4px 0;
}}
.stacked-segment {{
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    color: #fff;
    min-width: 2px;
}}
.legend {{
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin: 8px 0;
    font-size: 0.8rem;
}}
.legend-item {{
    display: flex;
    align-items: center;
    gap: 4px;
}}
.legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 2px;
}}
.session-label {{
    font-size: 0.75rem;
    color: {COLORS['text_muted']};
    margin-bottom: 2px;
}}
.sink-row {{
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid {COLORS['card_border']}22;
    font-size: 0.85rem;
}}
.sink-name {{ color: {COLORS['text']}; }}
.sink-cat {{
    font-size: 0.7rem;
    padding: 2px 6px;
    border-radius: 3px;
    margin-left: 8px;
}}
.footer {{
    text-align: center;
    color: {COLORS['text_muted']};
    font-size: 0.75rem;
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid {COLORS['card_border']};
}}
</style>
</head>
<body>

<h1>Session Efficiency Dashboard</h1>
<div class="subtitle">MT-36 Phase 5 — Quality-Preserving Speed Analysis</div>

<div class="grid">
    <!-- Summary stats -->
    <div class="card" id="summary-card"></div>
    <!-- Category breakdown -->
    <div class="card" id="category-card"></div>
</div>

<div class="grid">
    <!-- Overhead trend per session -->
    <div class="card full" id="trend-card"></div>
</div>

<div class="grid">
    <!-- Per-session stacked bars -->
    <div class="card full" id="session-card"></div>
</div>

<div class="grid">
    <!-- Top sinks -->
    <div class="card" id="sinks-card"></div>
    <!-- Quality vs speed -->
    <div class="card" id="quality-card"></div>
</div>

<div class="footer">
    Generated by CCA Session Efficiency Dashboard (MT-36 Phase 5)
</div>

<script>
const data = {data_json};
const COLORS = {json.dumps(COLORS)};

// --- Summary card ---
(function() {{
    const card = document.getElementById('summary-card');
    const ratio = data.avg_overhead_ratio;
    const cls = ratio < 0.25 ? 'good' : ratio < 0.40 ? 'warn' : 'bad';
    const trendCls = 'trend-' + data.trend;

    card.innerHTML = `
        <h2>Summary</h2>
        <div class="stat-row">
            <span class="stat-label">Sessions Analyzed</span>
            <span class="stat-value">${{data.session_count}}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Avg Overhead</span>
            <span class="stat-value ${{cls}}">${{data.avg_overhead_pct}}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Best Session</span>
            <span class="stat-value good">${{(data.best_overhead_ratio * 100).toFixed(1)}}%</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Worst Session</span>
            <span class="stat-value bad">${{(data.worst_overhead_ratio * 100).toFixed(1)}}%</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Trend</span>
            <span class="stat-value ${{trendCls}}">${{data.trend}}</span>
        </div>
    `;
}})();

// --- Category breakdown card ---
(function() {{
    const card = document.getElementById('category-card');
    const cats = data.category_totals;
    const total = Object.values(cats).reduce((a, b) => a + b, 0);
    const catOrder = ['init', 'wrap', 'test', 'doc', 'code', 'other'];

    let barsHtml = '';
    for (const cat of catOrder) {{
        if (!(cat in cats)) continue;
        const val = cats[cat];
        const pct = total > 0 ? (val / total * 100) : 0;
        const color = COLORS[cat] || COLORS.other;
        const timeStr = val < 60 ? val.toFixed(0) + 's' : (val / 60).toFixed(1) + 'm';
        barsHtml += `
            <div class="bar-row">
                <span class="bar-label">${{cat}}</span>
                <div class="bar-track">
                    <div class="bar-fill" style="width:${{pct}}%;background:${{color}}"></div>
                </div>
                <span class="bar-value">${{timeStr}} (${{pct.toFixed(0)}}%)</span>
            </div>
        `;
    }}

    card.innerHTML = `<h2>Time by Category (All Sessions)</h2><div class="bar-chart">${{barsHtml}}</div>`;
}})();

// --- Overhead trend card ---
(function() {{
    const card = document.getElementById('trend-card');
    const sessions = data.per_session;
    const maxRatio = Math.max(...sessions.map(s => s.overhead_ratio), 0.5);

    // Simple SVG line chart
    const w = 800, h = 200, pad = 40;
    const xStep = sessions.length > 1 ? (w - 2 * pad) / (sessions.length - 1) : 0;

    let points = sessions.map((s, i) => {{
        const x = pad + i * xStep;
        const y = h - pad - (s.overhead_ratio / maxRatio) * (h - 2 * pad);
        return {{ x, y, s }};
    }});

    let pathD = points.map((p, i) => `${{i === 0 ? 'M' : 'L'}} ${{p.x}} ${{p.y}}`).join(' ');

    // Y-axis labels
    let yLabels = '';
    for (let i = 0; i <= 4; i++) {{
        const val = (maxRatio * i / 4 * 100).toFixed(0);
        const y = h - pad - (i / 4) * (h - 2 * pad);
        yLabels += `<text x="${{pad - 5}}" y="${{y + 4}}" text-anchor="end" fill="${{COLORS.text_muted}}" font-size="11">${{val}}%</text>`;
        yLabels += `<line x1="${{pad}}" y1="${{y}}" x2="${{w - pad}}" y2="${{y}}" stroke="${{COLORS.card_border}}" stroke-dasharray="4"/>`;
    }}

    // X-axis labels
    let xLabels = '';
    const step = Math.max(1, Math.floor(sessions.length / 10));
    points.forEach((p, i) => {{
        if (i % step === 0 || i === points.length - 1) {{
            xLabels += `<text x="${{p.x}}" y="${{h - pad + 16}}" text-anchor="middle" fill="${{COLORS.text_muted}}" font-size="11">S${{p.s.session_id}}</text>`;
        }}
    }});

    // Dots
    let dots = points.map(p => {{
        const color = p.s.overhead_ratio < 0.25 ? COLORS.green : p.s.overhead_ratio < 0.40 ? COLORS.yellow : COLORS.accent;
        return `<circle cx="${{p.x}}" cy="${{p.y}}" r="4" fill="${{color}}" />`;
    }}).join('');

    card.innerHTML = `
        <h2>Overhead Ratio Trend</h2>
        <svg viewBox="0 0 ${{w}} ${{h}}" style="width:100%;max-height:250px">
            ${{yLabels}}
            ${{xLabels}}
            <path d="${{pathD}}" fill="none" stroke="${{COLORS.accent}}" stroke-width="2"/>
            ${{dots}}
        </svg>
    `;
}})();

// --- Per-session stacked bars ---
(function() {{
    const card = document.getElementById('session-card');
    const sessions = data.per_session;
    const catOrder = ['init', 'wrap', 'test', 'doc', 'code'];

    let legendHtml = catOrder.map(c =>
        `<div class="legend-item"><div class="legend-dot" style="background:${{COLORS[c]}}"></div>${{c}}</div>`
    ).join('');

    let barsHtml = '';
    for (const s of sessions) {{
        const total = s.total_s || 1;
        let segments = '';
        for (const cat of catOrder) {{
            const val = (s.by_category || {{}})[cat] || 0;
            const pct = (val / total * 100);
            if (pct < 1) continue;
            segments += `<div class="stacked-segment" style="width:${{pct}}%;background:${{COLORS[cat]}}" title="${{cat}}: ${{val.toFixed(0)}}s (${{pct.toFixed(0)}}%)">${{pct >= 8 ? pct.toFixed(0) + '%' : ''}}</div>`;
        }}
        const gradeStr = s.grade ? ` [${{s.grade}}]` : '';
        barsHtml += `
            <div class="session-label">S${{s.session_id}}${{gradeStr}} — ${{(total / 60).toFixed(1)}}m total, ${{(s.overhead_ratio * 100).toFixed(0)}}% overhead</div>
            <div class="stacked-bar">${{segments}}</div>
        `;
    }}

    card.innerHTML = `
        <h2>Per-Session Breakdown</h2>
        <div class="legend">${{legendHtml}}</div>
        ${{barsHtml}}
    `;
}})();

// --- Top sinks card ---
(function() {{
    const card = document.getElementById('sinks-card');
    const sinks = data.top_sinks;

    let sinksHtml = '';
    if (sinks.length === 0) {{
        sinksHtml = '<div style="color:' + COLORS.text_muted + '">No overhead sinks detected</div>';
    }} else {{
        for (const s of sinks.slice(0, 8)) {{
            const color = COLORS[s.category] || COLORS.other;
            const timeStr = s.avg_s < 60 ? s.avg_s.toFixed(0) + 's' : (s.avg_s / 60).toFixed(1) + 'm';
            sinksHtml += `
                <div class="sink-row">
                    <span class="sink-name">${{s.name}} <span class="sink-cat" style="background:${{color}}33;color:${{color}}">${{s.category}}</span></span>
                    <span>${{timeStr}} avg (${{s.count}}x)</span>
                </div>
            `;
        }}
    }}

    card.innerHTML = `<h2>Top Overhead Sinks</h2>${{sinksHtml}}`;
}})();

// --- Quality vs speed card ---
(function() {{
    const card = document.getElementById('quality-card');
    const qsData = data.quality_speed.filter(d => d.grade_numeric !== null);

    if (qsData.length === 0) {{
        card.innerHTML = '<h2>Quality vs Speed</h2><div style="color:' + COLORS.text_muted + '">No grade data available</div>';
        return;
    }}

    // Simple scatter plot via SVG
    const w = 350, h = 200, pad = 40;
    const maxRatio = Math.max(...qsData.map(d => d.overhead_ratio), 0.5);
    const maxGrade = 4.3;

    let dots = qsData.map(d => {{
        const x = pad + (d.overhead_ratio / maxRatio) * (w - 2 * pad);
        const y = h - pad - (d.grade_numeric / maxGrade) * (h - 2 * pad);
        return `<circle cx="${{x}}" cy="${{y}}" r="5" fill="${{COLORS.green}}" opacity="0.7">
            <title>S${{d.session_id}}: ${{d.grade}} @ ${{(d.overhead_ratio * 100).toFixed(0)}}% overhead</title>
        </circle>`;
    }}).join('');

    // Axis labels
    let yLabels = '';
    for (const g of ['F', 'D', 'C', 'B', 'A']) {{
        const gn = {{'F': 0, 'D': 1, 'C': 2, 'B': 3, 'A': 4}}[g];
        const y = h - pad - (gn / maxGrade) * (h - 2 * pad);
        yLabels += `<text x="${{pad - 5}}" y="${{y + 4}}" text-anchor="end" fill="${{COLORS.text_muted}}" font-size="10">${{g}}</text>`;
    }}

    card.innerHTML = `
        <h2>Quality vs Speed</h2>
        <svg viewBox="0 0 ${{w}} ${{h}}" style="width:100%;max-height:220px">
            ${{yLabels}}
            <text x="${{w / 2}}" y="${{h - 5}}" text-anchor="middle" fill="${{COLORS.text_muted}}" font-size="10">Overhead %</text>
            <text x="10" y="${{h / 2}}" transform="rotate(-90, 10, ${{h / 2}})" text-anchor="middle" fill="${{COLORS.text_muted}}" font-size="10">Grade</text>
            ${{dots}}
        </svg>
        <div style="font-size:0.8rem;color:${{COLORS.text_muted}}">
            ${{qsData.length}} sessions with grades. Lower overhead + higher grade = optimal.
        </div>
    `;
}})();

</script>
</body>
</html>"""


def _generate_empty_html() -> str:
    """Generate dashboard HTML when no data is available."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CCA Session Efficiency Dashboard</title>
<style>
body {{
    font-family: 'SF Mono', 'Consolas', monospace;
    background: {COLORS['bg']};
    color: {COLORS['text']};
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    text-align: center;
}}
h1 {{ color: {COLORS['accent']}; margin-bottom: 16px; }}
p {{ color: {COLORS['text_muted']}; }}
</style>
</head>
<body>
<div>
    <h1>Session Efficiency Dashboard</h1>
    <p>No data yet. Wire session_timer into /cca-init and /cca-wrap to start collecting.</p>
    <p style="margin-top:24px;font-size:0.85rem;">
        Use <code>SessionTimer(session_id=N)</code> in init/wrap/auto commands.<br>
        Data persists to <code>session_timings.jsonl</code>.
    </p>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main dashboard class
# ---------------------------------------------------------------------------

class EfficiencyDashboard:
    """Generate the session efficiency dashboard."""

    def __init__(
        self,
        timing_path: str = DEFAULT_TIMING_PATH,
        outcome_path: str = DEFAULT_OUTCOME_PATH,
    ):
        self.timing_path = timing_path
        self.outcome_path = outcome_path
        self.stats: Optional[dict] = None

    def generate(self, output_path: str = DEFAULT_OUTPUT_PATH) -> str:
        """Load data, compute stats, generate HTML, write to file."""
        data = load_session_data(self.timing_path, self.outcome_path)
        merged = merge_timing_and_outcomes(data["timings"], data["outcomes"])
        self.stats = compute_dashboard_stats(merged)
        html_content = generate_html(self.stats)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="CCA Session Efficiency Dashboard")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT_PATH, help="Output HTML path")
    parser.add_argument("--timing", default=DEFAULT_TIMING_PATH, help="Timing JSONL path")
    parser.add_argument("--outcomes", default=DEFAULT_OUTCOME_PATH, help="Outcomes JSONL path")
    parser.add_argument("--last", type=int, default=0, help="Only last N sessions")
    args = parser.parse_args()

    dash = EfficiencyDashboard(timing_path=args.timing, outcome_path=args.outcomes)
    path = dash.generate(output_path=args.output)

    if dash.stats and dash.stats["session_count"] > 0:
        s = dash.stats
        print(f"Dashboard generated: {path}")
        print(f"Sessions: {s['session_count']}, Avg overhead: {s['avg_overhead_pct']}, Trend: {s['trend']}")
    else:
        print(f"Dashboard generated (no data): {path}")


if __name__ == "__main__":
    main()
