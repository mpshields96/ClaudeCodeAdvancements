#!/usr/bin/env python3
"""component_demo.py — Generate a browser-viewable HTML demo of the CCA component library.

Usage:
    cd design-skills/
    python3 component_demo.py                    # writes component_demo.html
    python3 component_demo.py --out /tmp/demo.html
    python3 component_demo.py --open             # open in default browser

Output: A self-contained HTML file showing all 8 components across both light and dark themes.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import component_library as cl


def build_demo() -> str:
    """Build the full demo page HTML."""

    # -- Buttons section --
    buttons = cl.card("Buttons", "\n".join([
        "<div style='display:flex;gap:8px;flex-wrap:wrap;align-items:center;'>",
        cl.button("Primary"),
        cl.button("Secondary", variant="secondary"),
        cl.button("Danger", variant="danger"),
        cl.button("Ghost", variant="ghost"),
        cl.button("Small", size="sm"),
        cl.button("Large", size="lg"),
        cl.button("Link", href="#demo"),
        cl.button("Disabled", disabled=True),
        "</div>",
    ]))

    # -- Badges section --
    badges = cl.card("Badges", " ".join([
        cl.badge("Default"),
        cl.badge("Success", variant="success"),
        cl.badge("Warning", variant="warning"),
        cl.badge("Danger", variant="danger"),
        cl.badge("Neutral", variant="neutral"),
    ]))

    # -- Alerts section --
    alerts = cl.card("Alerts", "\n".join([
        cl.alert("Informational alert — system is nominal.", variant="info", title="Info"),
        cl.alert("All 274 test suites passing.", variant="success", title="Tests OK"),
        cl.alert("Context at 52% — approaching yellow zone.", variant="warning", title="Warning"),
        cl.alert("Iron Law violated: credential exposure blocked.", variant="danger", title="Blocked"),
        cl.alert("This alert can be dismissed.", variant="info", dismissible=True),
    ]))

    # -- Progress bars section --
    progress = cl.card("Progress Bars", "\n".join([
        cl.progress_bar(100, 100, label="Tests passing", variant="success"),
        cl.progress_bar(52, 100, label="Context usage", variant="warning"),
        cl.progress_bar(18, 100, label="Danger zone", variant="danger"),
        cl.progress_bar(37, 100, label="Phase completion"),
    ]))

    # -- Stat cards section --
    stats_row = "<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;'>"
    stats_row += cl.stat_card("Sessions", "256", delta="+1", delta_dir="up", subtitle="today")
    stats_row += cl.stat_card("Tests", "618", delta="+75", delta_dir="up")
    stats_row += cl.stat_card("Principles", "203", subtitle="self-learning")
    stats_row += cl.stat_card("Context", "52%", delta="-15%", delta_dir="down", subtitle="from peak")
    stats_row += "</div>"
    stats = cl.card("Stat Cards", stats_row)

    # -- Data table section --
    table_html = cl.data_table(
        ["MT", "Name", "Phase", "Status"],
        [
            ["MT-32", "Visual Excellence", "4/7", cl.badge("Active", variant="success")],
            ["MT-49", "Self-Learning v6", "6/6", cl.badge("Complete", variant="neutral")],
            ["MT-53", "Pokemon Bot", "2/5", cl.badge("Active", variant="warning")],
            ["MT-21", "Hivemind", "1/3", cl.badge("Paused", variant="neutral")],
        ],
        caption="Master Tasks — Active",
        striped=True,
    )
    table = cl.card("Data Table", table_html)

    # -- Tabs section --
    tab_panel = cl.tabs([
        ("Overview", "<p>CCA is a research + build project for Claude Code advancements.</p>" +
                     cl.alert("5 frontiers: Memory, Spec, Context, Agent Guard, Dashboard.", variant="info")),
        ("Metrics", stats_row),
        ("Tests", cl.progress_bar(274, 274, label="All suites passing", variant="success")),
    ])
    tabs = cl.card("Tabs", tab_panel)

    # -- Empty table edge case --
    empty_table = cl.card("Empty Table (edge case)", cl.data_table(["Col A", "Col B"], []))

    # Build page with heading
    heading = "<h1 style='color:var(--cca-primary);margin-bottom:8px;'>CCA Component Library Demo</h1>"
    subheading = (
        "<p style='color:var(--cca-muted);margin-top:0;margin-bottom:24px;'>"
        "MT-32 Phase 4 — 8 components backed by CCA design tokens. "
        "All components return HTML strings; compose freely."
        "</p>"
    )
    grid_style = "display:grid;grid-template-columns:1fr 1fr;gap:16px;"

    layout = "\n".join([
        heading,
        subheading,
        f"<div style='{grid_style}'>",
        buttons,
        badges,
        alerts,
        progress,
        "</div>",
        "<div style='margin-top:16px;'>", stats, "</div>",
        "<div style='margin-top:16px;'>", table, "</div>",
        "<div style='margin-top:16px;'>", tabs, "</div>",
        "<div style='margin-top:16px;'>", empty_table, "</div>",
    ])

    return cl.page("CCA Component Library Demo", [layout])


def main():
    parser = argparse.ArgumentParser(description="Generate CCA component library demo")
    parser.add_argument("--out", default="component_demo.html", help="Output file path")
    parser.add_argument("--open", action="store_true", help="Open in default browser after writing")
    args = parser.parse_args()

    html = build_demo()
    out_path = os.path.abspath(args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Demo written: {out_path} ({len(html):,} bytes)")

    if args.open:
        import subprocess
        subprocess.run(["open", out_path], check=False)


if __name__ == "__main__":
    main()
