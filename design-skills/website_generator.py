#!/usr/bin/env python3
"""
website_generator.py — MT-17 Phase 5: Website and documentation page templates.

Generates self-contained HTML (inline CSS, no external dependencies) for:
1. LandingPage — project landing page with hero, features grid, metrics, footer
2. DocsPage — documentation page with sidebar navigation and content sections

All output follows design-guide.md (CCA visual language).
All user content is HTML-escaped (XSS-safe).

Usage:
    from website_generator import LandingPage, FeatureCard, MetricCard, NavLink
    from website_generator import render_landing_page, write_landing_page

    page = LandingPage(
        title="ClaudeCodeAdvancements",
        tagline="Next-level enhancements for Claude Code.",
        hero_cta_text="View on GitHub",
        hero_cta_url="https://github.com/mpshields96/ClaudeCodeAdvancements",
        features=[...],
        metrics=[...],
    )
    write_landing_page(page, "index.html")

Stdlib only. No external dependencies.
"""

import html as html_mod
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# ── Design tokens (from canonical design_tokens module) ──────────────────────

import design_tokens

COLORS = {
    **design_tokens.CCA_PALETTE,
    "background": design_tokens.CCA_PALETTE["bg"],
}

FONTS = {
    "body": "system-ui, -apple-system, 'Segoe UI', sans-serif",
    "mono": "'SF Mono', 'Fira Code', 'Consolas', monospace",
}


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class FeatureCard:
    """A feature highlight card for the landing page."""
    title: str
    description: str
    icon: Optional[str] = None
    link: Optional[str] = None


@dataclass
class MetricCard:
    """A numeric metric display for the landing page."""
    label: str
    value: str
    unit: Optional[str] = None


@dataclass
class NavLink:
    """A navigation bar link."""
    label: str
    url: str
    active: bool = False


@dataclass
class LandingPage:
    """Data for a project landing page."""
    title: str
    tagline: str
    hero_cta_text: str
    hero_cta_url: str
    features: List[FeatureCard] = field(default_factory=list)
    metrics: List[MetricCard] = field(default_factory=list)
    nav_links: List[NavLink] = field(default_factory=list)
    figures: List[dict] = field(default_factory=list)
    footer_text: Optional[str] = None


@dataclass
class DocSection:
    """A content section in a documentation page."""
    heading: str
    content: str
    level: int = 2
    code_block: Optional[str] = None
    code_lang: Optional[str] = None


@dataclass
class DocsPage:
    """Data for a documentation page with sidebar navigation."""
    title: str
    module: str
    description: str
    sections: List[DocSection] = field(default_factory=list)
    nav_links: List[NavLink] = field(default_factory=list)


# ── Shared CSS ────────────────────────────────────────────────────────────────

def _base_css() -> str:
    """Base CSS following design-guide.md."""
    p = COLORS["primary"]
    a = COLORS["accent"]
    h = COLORS["highlight"]
    s = COLORS["success"]
    m = COLORS["muted"]
    bg = COLORS["background"]
    sf = COLORS["surface"]
    bd = COLORS["border"]
    font = FONTS["body"]
    mono = FONTS["mono"]

    return f"""
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: {font};
    font-size: 16px;
    line-height: 1.6;
    color: {p};
    background: {bg};
}}
a {{ color: {a}; text-decoration: none; }}
a:hover {{ color: {h}; text-decoration: underline; }}
code, pre {{
    font-family: {mono};
    font-size: 0.9em;
}}
pre {{
    background: {p};
    color: #e6edf3;
    padding: 1.2rem;
    border-radius: 6px;
    overflow-x: auto;
    margin: 1rem 0;
}}
pre code {{ background: none; padding: 0; color: inherit; }}
code:not(pre code) {{
    background: {sf};
    border: 1px solid {bd};
    padding: 0.15em 0.4em;
    border-radius: 3px;
}}
.nav {{
    background: {p};
    padding: 0 2rem;
    display: flex;
    align-items: center;
    gap: 2rem;
    height: 56px;
    position: sticky;
    top: 0;
    z-index: 100;
}}
.nav-title {{
    font-size: 1.1rem;
    font-weight: 700;
    color: #ffffff;
    flex: 1;
}}
.nav-links {{ display: flex; gap: 1.5rem; }}
.nav-links a {{
    color: #e6edf3;
    font-size: 0.9rem;
    font-weight: 500;
}}
.nav-links a:hover, .nav-links a.active {{ color: #ffffff; text-decoration: none; }}
.badge {{
    display: inline-block;
    background: {a};
    color: #ffffff;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.15em 0.5em;
    border-radius: 999px;
    margin-left: 0.4rem;
    vertical-align: middle;
}}
"""


# ── Landing page rendering ────────────────────────────────────────────────────

def _landing_css() -> str:
    p = COLORS["primary"]
    a = COLORS["accent"]
    h = COLORS["highlight"]
    s = COLORS["success"]
    m = COLORS["muted"]
    bg = COLORS["background"]
    sf = COLORS["surface"]
    bd = COLORS["border"]

    return f"""
.hero {{
    background: linear-gradient(135deg, {p} 0%, {a} 100%);
    color: #ffffff;
    padding: 5rem 2rem 4rem;
    text-align: center;
}}
.hero h1 {{
    font-size: clamp(2rem, 5vw, 3.5rem);
    font-weight: 800;
    margin-bottom: 1rem;
    letter-spacing: -0.02em;
}}
.hero p {{
    font-size: 1.2rem;
    color: #e6edf3;
    max-width: 600px;
    margin: 0 auto 2rem;
}}
.cta-btn {{
    display: inline-block;
    background: {h};
    color: #ffffff;
    font-weight: 700;
    font-size: 1rem;
    padding: 0.8rem 2rem;
    border-radius: 6px;
    text-decoration: none;
    transition: opacity 0.15s;
}}
.cta-btn:hover {{ opacity: 0.88; color: #ffffff; text-decoration: none; }}
.metrics-strip {{
    display: flex;
    justify-content: center;
    gap: 3rem;
    padding: 2.5rem 2rem;
    background: {sf};
    border-bottom: 1px solid {bd};
    flex-wrap: wrap;
}}
.metric {{
    text-align: center;
}}
.metric-value {{
    font-size: 2.4rem;
    font-weight: 800;
    color: {a};
    line-height: 1;
}}
.metric-label {{
    font-size: 0.85rem;
    color: {m};
    margin-top: 0.25rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.features {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 4rem 2rem;
}}
.features-heading {{
    text-align: center;
    font-size: 1.8rem;
    font-weight: 700;
    margin-bottom: 2.5rem;
    color: {p};
}}
.features-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1.5rem;
}}
.feature-card {{
    background: {sf};
    border: 1px solid {bd};
    border-radius: 8px;
    padding: 1.5rem;
    transition: box-shadow 0.15s;
}}
.feature-card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
.feature-icon {{
    font-size: 1.8rem;
    margin-bottom: 0.75rem;
    display: block;
}}
.feature-title {{
    font-size: 1.05rem;
    font-weight: 700;
    color: {p};
    margin-bottom: 0.5rem;
}}
.feature-desc {{
    font-size: 0.9rem;
    color: {m};
    line-height: 1.5;
}}
footer {{
    text-align: center;
    padding: 2rem;
    font-size: 0.85rem;
    color: {m};
    border-top: 1px solid {bd};
    margin-top: 2rem;
}}
"""


def render_landing_page(page: LandingPage) -> str:
    """Render a LandingPage to a self-contained HTML string."""
    e = html_mod.escape  # shorthand for escaping

    # Build nav
    nav_links_html = ""
    for link in page.nav_links:
        active_class = ' class="active"' if link.active else ""
        nav_links_html += f'<a href="{e(link.url)}"{active_class}>{e(link.label)}</a>\n'

    nav_html = f"""
<nav class="nav">
  <span class="nav-title">{e(page.title)}</span>
  <div class="nav-links">
    {nav_links_html}
  </div>
</nav>
""" if page.nav_links else ""

    # Build metrics strip
    metrics_html = ""
    if page.metrics:
        items = ""
        for m in page.metrics:
            unit = f" {e(m.unit)}" if m.unit else ""
            items += f"""
<div class="metric">
  <div class="metric-value">{e(m.value)}{unit}</div>
  <div class="metric-label">{e(m.label)}</div>
</div>
"""
        metrics_html = f'<div class="metrics-strip">{items}</div>'

    # Build features grid
    features_html = ""
    if page.features:
        cards = ""
        for f in page.features:
            icon_html = f'<span class="feature-icon">{e(f.icon)}</span>' if f.icon else ""
            title_content = e(f.title)
            if f.link:
                title_content = f'<a href="{e(f.link)}">{e(f.title)}</a>'
            cards += f"""
<div class="feature-card">
  {icon_html}
  <div class="feature-title">{title_content}</div>
  <div class="feature-desc">{e(f.description)}</div>
</div>
"""
        features_html = f"""
<section class="features">
  <h2 class="features-heading">What's inside</h2>
  <div class="features-grid">
    {cards}
  </div>
</section>
"""

    # Figures section (MT-32 Phase 7)
    figures_html = ""
    if page.figures:
        fig_cards = ""
        for fig in page.figures:
            fig_title = e(fig.get("title", ""))
            fig_svg = fig.get("svg", "")
            fig_cards += f"""
<div class="figure-card">
  <h3 class="figure-title">{fig_title}</h3>
  <div class="figure-content">{fig_svg}</div>
</div>
"""
        figures_html = f"""
<section class="figure-section">
  <h2 class="features-heading">Visualizations</h2>
  <div class="figures-grid">
    {fig_cards}
  </div>
</section>
"""

    # Footer
    footer_text = page.footer_text or f"Built with Claude Code &amp; CCA &middot; {e(page.title)}"
    footer_html = f'<footer>{footer_text}</footer>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{e(page.title)}</title>
  <style>
    {_base_css()}
    {_landing_css()}
  </style>
</head>
<body>
{nav_html}
<section class="hero">
  <h1>{e(page.title)}</h1>
  <p>{e(page.tagline)}</p>
  <a href="{e(page.hero_cta_url)}" class="cta-btn">{e(page.hero_cta_text)}</a>
</section>
{metrics_html}
{features_html}
{figures_html}
{footer_html}
</body>
</html>"""


def write_landing_page(page: LandingPage, output_path: str) -> None:
    """Write a LandingPage to an HTML file."""
    Path(output_path).write_text(render_landing_page(page), encoding="utf-8")


# ── Docs page rendering ───────────────────────────────────────────────────────

def _docs_css() -> str:
    p = COLORS["primary"]
    a = COLORS["accent"]
    h = COLORS["highlight"]
    m = COLORS["muted"]
    bg = COLORS["background"]
    sf = COLORS["surface"]
    bd = COLORS["border"]

    return f"""
.docs-layout {{
    display: flex;
    min-height: calc(100vh - 56px);
}}
.docs-sidebar {{
    width: 240px;
    flex-shrink: 0;
    background: {sf};
    border-right: 1px solid {bd};
    padding: 2rem 1.25rem;
    position: sticky;
    top: 56px;
    height: calc(100vh - 56px);
    overflow-y: auto;
}}
.docs-sidebar h2 {{
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {m};
    margin-bottom: 0.75rem;
}}
.sidebar-links {{ list-style: none; }}
.sidebar-links li {{ margin-bottom: 0.4rem; }}
.sidebar-links a {{
    font-size: 0.875rem;
    color: {p};
    font-weight: 500;
    display: block;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
}}
.sidebar-links a:hover {{
    background: {bd};
    text-decoration: none;
}}
.docs-main {{
    flex: 1;
    padding: 3rem 4rem;
    max-width: 820px;
}}
.docs-header {{
    border-bottom: 2px solid {bd};
    padding-bottom: 1.5rem;
    margin-bottom: 2rem;
}}
.docs-header h1 {{
    font-size: 2rem;
    font-weight: 800;
    color: {p};
    margin-bottom: 0.5rem;
}}
.docs-description {{
    font-size: 1.05rem;
    color: {m};
}}
.docs-section {{
    margin-bottom: 2.5rem;
}}
.docs-section h2 {{
    font-size: 1.3rem;
    font-weight: 700;
    color: {a};
    margin-bottom: 0.75rem;
    padding-top: 0.5rem;
    border-top: 1px solid {bd};
}}
.docs-section h3 {{
    font-size: 1.1rem;
    font-weight: 600;
    color: {p};
    margin-bottom: 0.5rem;
}}
.docs-section p {{
    color: {p};
    margin-bottom: 0.75rem;
    line-height: 1.7;
}}
@media (max-width: 768px) {{
    .docs-layout {{ flex-direction: column; }}
    .docs-sidebar {{
        width: 100%;
        position: static;
        height: auto;
        border-right: none;
        border-bottom: 1px solid {bd};
    }}
    .docs-main {{ padding: 2rem 1rem; }}
}}
"""


def render_docs_page(page: DocsPage) -> str:
    """Render a DocsPage to a self-contained HTML string."""
    e = html_mod.escape

    # Build nav
    nav_links_html = ""
    for link in page.nav_links:
        active_class = ' class="active"' if link.active else ""
        nav_links_html += f'<a href="{e(link.url)}"{active_class}>{e(link.label)}</a>\n'
    nav_html = f"""
<nav class="nav">
  <span class="nav-title">{e(page.title)}</span>
  <div class="nav-links">
    {nav_links_html}
  </div>
</nav>
""" if page.nav_links else f"""
<nav class="nav">
  <span class="nav-title">{e(page.title)}</span>
</nav>
"""

    # Sidebar section links
    sidebar_items = ""
    for section in page.sections:
        anchor = section.heading.lower().replace(" ", "-").replace("/", "-")
        sidebar_items += f'<li><a href="#{e(anchor)}">{e(section.heading)}</a></li>\n'

    sidebar_html = f"""
<aside class="docs-sidebar">
  <h2>Contents</h2>
  <ul class="sidebar-links">
    {sidebar_items}
  </ul>
</aside>
"""

    # Main content sections
    sections_html = ""
    for section in page.sections:
        anchor = section.heading.lower().replace(" ", "-").replace("/", "-")
        level = max(2, min(3, section.level))
        tag = f"h{level}"
        content_html = f"<p>{e(section.content)}</p>"
        code_html = ""
        if section.code_block is not None:
            lang = e(section.code_lang or "")
            code_html = f'<pre><code class="language-{lang}">{e(section.code_block)}</code></pre>'
        sections_html += f"""
<section class="docs-section" id="{e(anchor)}">
  <{tag}>{e(section.heading)}</{tag}>
  {content_html}
  {code_html}
</section>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{e(page.title)} — Documentation</title>
  <style>
    {_base_css()}
    {_docs_css()}
  </style>
</head>
<body>
{nav_html}
<div class="docs-layout">
  {sidebar_html}
  <main class="docs-main">
    <div class="docs-header">
      <h1>{e(page.title)}</h1>
      <p class="docs-description">{e(page.description)}</p>
    </div>
    {sections_html}
  </main>
</div>
</body>
</html>"""


def write_docs_page(page: DocsPage, output_path: str) -> None:
    """Write a DocsPage to an HTML file."""
    Path(output_path).write_text(render_docs_page(page), encoding="utf-8")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _demo_landing_page() -> LandingPage:
    return LandingPage(
        title="ClaudeCodeAdvancements",
        tagline="Research, design, and build the next significant advancements for Claude Code users.",
        hero_cta_text="View on GitHub",
        hero_cta_url="https://github.com/mpshields96/ClaudeCodeAdvancements",
        features=[
            FeatureCard("Memory System", "Persistent cross-session memory with FTS5 search.", "🧠"),
            FeatureCard("Spec System", "Spec-driven development: requirements → design → tasks → code.", "📋"),
            FeatureCard("Context Monitor", "Real-time context health monitoring and auto-handoff.", "📊"),
            FeatureCard("Agent Guard", "Multi-agent conflict prevention and bash safety.", "🛡️"),
            FeatureCard("Usage Dashboard", "Token and cost transparency with doc drift detection.", "💡"),
            FeatureCard("Self-Learning", "Cross-session improvement via trace analysis and reflection.", "🔄"),
        ],
        metrics=[
            MetricCard("Tests", "2484"),
            MetricCard("Modules", "9"),
            MetricCard("Sessions", "69"),
        ],
        nav_links=[
            NavLink("Home", "/", active=True),
            NavLink("GitHub", "https://github.com/mpshields96/ClaudeCodeAdvancements"),
        ],
    )


def _collect_landing_page() -> LandingPage:
    """Build a LandingPage from real CCA project data."""
    import re
    project_root = str(Path(__file__).parent.parent)

    # Read PROJECT_INDEX.md for module data
    index_path = os.path.join(project_root, "PROJECT_INDEX.md")
    index_content = ""
    if os.path.exists(index_path):
        with open(index_path) as f:
            index_content = f.read()

    # Parse module table
    features = []
    module_icons = {
        "Memory System": "🧠", "Spec System": "📋", "Context Monitor": "📊",
        "Agent Guard": "🛡️", "Usage Dashboard": "💡", "Reddit Intelligence": "🔍",
        "Self-Learning": "🔄", "Design Skills": "🎨", "Research": "🔬",
    }
    module_descriptions = {
        "Memory System": "Persistent cross-session memory with FTS5 search and MCP server.",
        "Spec System": "Spec-driven development: requirements, design, tasks, implement.",
        "Context Monitor": "Real-time context health monitoring and auto-handoff.",
        "Agent Guard": "Multi-agent conflict prevention, credential guard, bash safety.",
        "Usage Dashboard": "Token and cost transparency with doc drift detection.",
        "Reddit Intelligence": "Community signal research from Reddit and GitHub.",
        "Self-Learning": "Cross-session improvement via trace analysis and reflection.",
        "Design Skills": "Professional PDF reports, HTML dashboards, SVG charts.",
        "Research": "R&D tools including iOS project generation.",
    }

    in_table = False
    for line in index_content.split("\n"):
        stripped = line.strip()
        if "| Module " in stripped or "| Module|" in stripped:
            in_table = True
            continue
        if in_table and stripped.startswith("|---"):
            continue
        if in_table and stripped.startswith("|"):
            parts = [p.strip() for p in stripped.split("|")]
            parts = [p for p in parts if p]
            if len(parts) >= 1:
                name = parts[0]
                desc = module_descriptions.get(name, "")
                icon = module_icons.get(name, "")
                if name and desc:
                    features.append(FeatureCard(name, desc, icon))
        elif in_table and not stripped.startswith("|"):
            in_table = False

    # Extract totals
    total_match = re.search(r"\*\*Total:\s*([\d,]+)\s*tests\s*\((\d+)\s*suites\)", index_content)
    total_tests = total_match.group(1).replace(",", "") if total_match else "0"
    total_suites = total_match.group(2) if total_match else "0"

    # Session number from SESSION_STATE.md
    state_path = os.path.join(project_root, "SESSION_STATE.md")
    session = "0"
    if os.path.exists(state_path):
        with open(state_path) as f:
            state_content = f.read()
        session_match = re.search(r"Session (\d+)", state_content)
        if session_match:
            session = session_match.group(1)

    return LandingPage(
        title="ClaudeCodeAdvancements",
        tagline="Research, design, and build the next significant advancements for Claude Code users.",
        hero_cta_text="View on GitHub",
        hero_cta_url="https://github.com/mpshields96/ClaudeCodeAdvancements",
        features=features or [FeatureCard("CCA", "Project data not found.")],
        metrics=[
            MetricCard("Tests", total_tests),
            MetricCard("Suites", total_suites),
            MetricCard("Modules", str(len(features))),
            MetricCard("Sessions", session),
        ],
        nav_links=[
            NavLink("Home", "/", active=True),
            NavLink("GitHub", "https://github.com/mpshields96/ClaudeCodeAdvancements"),
        ],
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate CCA website pages")
    parser.add_argument("--type", choices=["landing", "docs"], default="landing")
    parser.add_argument("--output", default="-", help="Output file (- for stdout)")
    parser.add_argument("--demo", action="store_true", help="Use hardcoded demo data")
    args = parser.parse_args()

    if args.type == "landing":
        page = _demo_landing_page() if args.demo else _collect_landing_page()
        html_out = render_landing_page(page)
    else:
        page = DocsPage(
            title="ClaudeCodeAdvancements",
            module="root",
            description="Documentation for the CCA project.",
            sections=[
                DocSection("Overview", "CCA builds validated advancements for Claude Code users."),
                DocSection("Installation", "Clone the repo and run the test suite.",
                           code_block="git clone https://github.com/mpshields96/ClaudeCodeAdvancements\npython3 -m pytest", code_lang="bash"),
            ],
            nav_links=[NavLink("Home", "/"), NavLink("GitHub", "https://github.com/mpshields96/ClaudeCodeAdvancements")],
        )
        html_out = render_docs_page(page)

    if args.output == "-":
        print(html_out)
    else:
        Path(args.output).write_text(html_out, encoding="utf-8")
        print(f"Written to {args.output}")


if __name__ == "__main__":
    main()
