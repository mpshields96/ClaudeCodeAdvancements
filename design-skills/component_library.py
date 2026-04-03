#!/usr/bin/env python3
"""CCA UI Component Library — MT-32 Phase 4.

Reusable HTML components backed by CCA design tokens. Every component returns
a self-contained HTML string using CSS classes defined in component_stylesheet().

Usage:
    from component_library import button, card, alert, component_stylesheet, page

    css = component_stylesheet()
    html = page("Dashboard", [
        card("Score", stat_card("Sessions", "182", delta="+12", delta_dir="up")),
        alert("Tests passing", variant="success"),
    ])

Components:
    button(label, variant, size, href, disabled) -> str
    badge(text, variant) -> str
    alert(message, variant, title, dismissible) -> str
    card(title, body, footer, variant) -> str
    progress_bar(value, max_value, label, variant) -> str
    data_table(headers, rows, caption, striped, compact) -> str
    tabs(items, active_index) -> str
    stat_card(label, value, delta, delta_dir, subtitle) -> str

Helpers:
    component_stylesheet() -> str   CSS for all components (includes design tokens)
    page(title, components, theme) -> str   Full HTML page wrapper
"""
from __future__ import annotations
import html as _html
from typing import Optional

from design_tokens import to_css_vars, CCA_PALETTE


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_VALID_BUTTON_VARIANTS = {"primary", "secondary", "danger", "ghost"}
_VALID_BADGE_VARIANTS = {"default", "success", "warning", "danger", "neutral"}
_VALID_ALERT_VARIANTS = {"info", "success", "warning", "danger"}
_VALID_CARD_VARIANTS = {"default", "elevated", "outlined"}
_VALID_PROGRESS_VARIANTS = {"default", "success", "warning", "danger"}


def _esc(text: str) -> str:
    """HTML-escape text content."""
    return _html.escape(str(text))


# ---------------------------------------------------------------------------
# button
# ---------------------------------------------------------------------------

def button(
    label: str,
    *,
    variant: str = "primary",
    size: str = "md",
    href: Optional[str] = None,
    disabled: bool = False,
    btn_type: str = "button",
) -> str:
    """Render a button or link button.

    Args:
        label:    Button text.
        variant:  "primary" | "secondary" | "danger" | "ghost"
        size:     "sm" | "md" | "lg"
        href:     When given, renders an <a> tag instead of <button>.
        disabled: Adds disabled attribute / aria-disabled.
        btn_type: HTML type attribute (button/submit/reset).

    Returns:
        HTML string.
    """
    if variant not in _VALID_BUTTON_VARIANTS:
        variant = "primary"

    size_class = f"cca-btn-{size}" if size in {"sm", "lg"} else "cca-btn-md"
    classes = f"cca-btn cca-btn-{variant} {size_class}"
    label_esc = _esc(label)

    if href:
        disabled_attr = ' aria-disabled="true" tabindex="-1"' if disabled else ""
        return (
            f'<a href="{_esc(href)}" class="{classes}"{disabled_attr}>'
            f"{label_esc}</a>"
        )

    disabled_attr = " disabled" if disabled else ""
    return (
        f'<button type="{btn_type}" class="{classes}"{disabled_attr}>'
        f"{label_esc}</button>"
    )


# ---------------------------------------------------------------------------
# badge
# ---------------------------------------------------------------------------

def badge(text: str, *, variant: str = "default") -> str:
    """Render an inline badge/tag.

    Args:
        text:    Badge label.
        variant: "default" | "success" | "warning" | "danger" | "neutral"

    Returns:
        HTML string.
    """
    if variant not in _VALID_BADGE_VARIANTS:
        variant = "default"
    variant_class = "" if variant == "default" else f" cca-badge-{variant}"
    return f'<span class="cca-badge{variant_class}">{_esc(text)}</span>'


# ---------------------------------------------------------------------------
# alert
# ---------------------------------------------------------------------------

def alert(
    message: str,
    *,
    variant: str = "info",
    title: Optional[str] = None,
    dismissible: bool = False,
) -> str:
    """Render an alert banner.

    Args:
        message:     Alert body text.
        variant:     "info" | "success" | "warning" | "danger"
        title:       Optional bold heading above the message.
        dismissible: Add a dismiss button (×).

    Returns:
        HTML string.
    """
    if variant not in _VALID_ALERT_VARIANTS:
        variant = "info"

    dismiss_btn = ""
    dismiss_class = ""
    if dismissible:
        dismiss_class = " cca-alert-dismiss"
        dismiss_btn = (
            '<button class="cca-alert-close" aria-label="Dismiss">'
            "&times;</button>"
        )

    title_html = f"<strong>{_esc(title)}</strong><br>" if title else ""
    return (
        f'<div class="cca-alert cca-alert-{variant}{dismiss_class}" role="alert">'
        f"{dismiss_btn}{title_html}{_esc(message)}</div>"
    )


# ---------------------------------------------------------------------------
# card
# ---------------------------------------------------------------------------

def card(
    title: str,
    body: str,
    *,
    footer: Optional[str] = None,
    variant: str = "default",
) -> str:
    """Render a content card.

    Args:
        title:   Card heading.
        body:    Card body — may contain raw HTML.
        footer:  Optional footer text (plain text, HTML-escaped).
        variant: "default" | "elevated" | "outlined"

    Returns:
        HTML string.
    """
    if variant not in _VALID_CARD_VARIANTS:
        variant = "default"
    variant_class = "" if variant == "default" else f" cca-card-{variant}"

    footer_html = ""
    if footer is not None:
        footer_html = (
            f'<div class="cca-card-footer">{_esc(footer)}</div>'
        )

    return (
        f'<div class="cca-card{variant_class}">'
        f'<div class="cca-card-header"><h3 class="cca-card-title">{_esc(title)}</h3></div>'
        f'<div class="cca-card-body">{body}</div>'
        f"{footer_html}"
        f"</div>"
    )


# ---------------------------------------------------------------------------
# progress_bar
# ---------------------------------------------------------------------------

def progress_bar(
    value: float,
    max_value: float,
    *,
    label: Optional[str] = None,
    variant: str = "default",
) -> str:
    """Render a horizontal progress bar.

    Args:
        value:     Current value.
        max_value: Maximum value (denominator).
        label:     Optional text label shown above the bar.
        variant:   "default" | "success" | "warning" | "danger"

    Returns:
        HTML string.
    """
    if variant not in _VALID_PROGRESS_VARIANTS:
        variant = "default"

    # Clamp to [0, max_value]
    safe_max = max(max_value, 1)
    clamped = max(0.0, min(float(value), float(safe_max)))
    pct = int(round(clamped / safe_max * 100))

    variant_class = "" if variant == "default" else f" cca-progress-{variant}"
    label_html = (
        f'<span class="cca-progress-label">{_esc(label)}</span>' if label else ""
    )

    return (
        f'<div class="cca-progress-wrap">'
        f"{label_html}"
        f'<div class="cca-progress">'
        f'<div class="cca-progress-bar{variant_class}" style="width:{pct}%" '
        f'role="progressbar" aria-valuenow="{pct}" aria-valuemin="0" aria-valuemax="100">'
        f"{pct}%</div></div></div>"
    )


# ---------------------------------------------------------------------------
# data_table
# ---------------------------------------------------------------------------

def data_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    caption: Optional[str] = None,
    striped: bool = False,
    compact: bool = False,
) -> str:
    """Render an HTML data table.

    Args:
        headers: Column header labels.
        rows:    List of rows; each row is a list of cell values (strings).
        caption: Optional <caption> element text.
        striped: Adds alternating row shading class.
        compact: Reduces cell padding.

    Returns:
        HTML string.
    """
    modifier_classes = ""
    if striped:
        modifier_classes += " cca-table-striped"
    if compact:
        modifier_classes += " cca-table-compact"

    caption_html = (
        f"<caption>{_esc(caption)}</caption>" if caption else ""
    )

    header_cells = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    thead = f"<thead><tr>{header_cells}</tr></thead>"

    if rows:
        tbody_rows = "".join(
            "<tr>" + "".join(f"<td>{_esc(str(cell))}</td>" for cell in row) + "</tr>"
            for row in rows
        )
        tbody = f"<tbody>{tbody_rows}</tbody>"
    else:
        colspan = max(len(headers), 1)
        tbody = (
            f'<tbody><tr><td colspan="{colspan}" class="cca-table-empty">'
            "No data</td></tr></tbody>"
        )

    return (
        f'<div class="cca-table-wrap">'
        f'<table class="cca-table{modifier_classes}">'
        f"{caption_html}{thead}{tbody}"
        f"</table></div>"
    )


# ---------------------------------------------------------------------------
# tabs
# ---------------------------------------------------------------------------

def tabs(items: list[tuple[str, str]], *, active_index: int = 0) -> str:
    """Render a tab navigation with panels.

    Args:
        items:        List of (label, content_html) tuples.
        active_index: Index of the initially active tab (0-based).

    Returns:
        HTML string.
    """
    if not items:
        return '<div class="cca-tabs"></div>'

    # Clamp active_index
    active = max(0, min(active_index, len(items) - 1))

    tab_buttons = []
    tab_panels = []
    for i, (label, content) in enumerate(items):
        panel_id = f"cca-panel-{i}"
        tab_id = f"cca-tab-{i}"
        is_active = i == active

        active_class = " cca-tab-active" if is_active else ""
        hidden_attr = "" if is_active else ' hidden'

        tab_buttons.append(
            f'<button class="cca-tab{active_class}" role="tab" '
            f'id="{tab_id}" aria-controls="{panel_id}" '
            f'aria-selected="{str(is_active).lower()}">'
            f"{_esc(label)}</button>"
        )
        tab_panels.append(
            f'<div class="cca-tab-panel" id="{panel_id}" role="tabpanel" '
            f'aria-labelledby="{tab_id}"{hidden_attr}>'
            f"{content}</div>"
        )

    nav = '<div class="cca-tab-nav" role="tablist">' + "".join(tab_buttons) + "</div>"
    panels = '<div class="cca-tab-panels">' + "".join(tab_panels) + "</div>"
    return f'<div class="cca-tabs">{nav}{panels}</div>'


# ---------------------------------------------------------------------------
# stat_card
# ---------------------------------------------------------------------------

def stat_card(
    label: str,
    value: str,
    *,
    delta: Optional[str] = None,
    delta_dir: Optional[str] = None,
    subtitle: Optional[str] = None,
) -> str:
    """Render a metric/KPI stat card.

    Args:
        label:     Metric name (e.g. "Revenue").
        value:     Display value (e.g. "$1,234").
        delta:     Change indicator text (e.g. "+5%").
        delta_dir: "up" | "down" | "neutral"
        subtitle:  Small descriptive text below value.

    Returns:
        HTML string.
    """
    delta_html = ""
    if delta is not None:
        dir_class = f" cca-delta-{delta_dir}" if delta_dir in {"up", "down", "neutral"} else ""
        delta_html = f'<span class="cca-delta{dir_class}">{_esc(delta)}</span>'

    subtitle_html = ""
    if subtitle is not None:
        subtitle_html = f'<div class="cca-stat-subtitle">{_esc(subtitle)}</div>'

    return (
        f'<div class="cca-stat-card">'
        f'<div class="cca-stat-label">{_esc(label)}</div>'
        f'<div class="cca-stat-value">{_esc(value)}{delta_html}</div>'
        f"{subtitle_html}"
        f"</div>"
    )


# ---------------------------------------------------------------------------
# component_stylesheet
# ---------------------------------------------------------------------------

def component_stylesheet() -> str:
    """Return CSS for all CCA components.

    Includes:
      - Design token custom properties (:root)
      - Base resets
      - All component class styles

    Returns:
        CSS string.
    """
    tokens_css = to_css_vars()

    return tokens_css + """

/* === CCA Component Library === */

*, *::before, *::after { box-sizing: border-box; }

body {
  font-family: "Source Sans 3", "Helvetica Neue", Arial, sans-serif;
  font-size: 11pt;
  color: var(--cca-primary);
  background: var(--cca-bg);
  line-height: 1.5;
}

/* --- Buttons --- */
.cca-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  font-family: inherit;
  font-size: 11pt;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  transition: opacity 0.15s ease;
}
.cca-btn:hover { opacity: 0.85; }
.cca-btn:disabled, .cca-btn[aria-disabled="true"] { opacity: 0.45; cursor: not-allowed; }

.cca-btn-primary { background: var(--cca-accent); color: #fff; }
.cca-btn-secondary { background: var(--cca-surface); color: var(--cca-accent); border: 1px solid var(--cca-border); }
.cca-btn-danger { background: var(--cca-highlight); color: #fff; }
.cca-btn-ghost { background: transparent; color: var(--cca-accent); border: 1px solid var(--cca-accent); }

.cca-btn-sm { padding: 4px 8px; font-size: 9pt; }
.cca-btn-md { padding: 8px 16px; font-size: 11pt; }
.cca-btn-lg { padding: 12px 24px; font-size: 13pt; }

/* --- Badges --- */
.cca-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 8pt;
  font-weight: 700;
  background: var(--cca-surface);
  color: var(--cca-muted);
  border: 1px solid var(--cca-border);
}
.cca-badge-success { background: #d1fae5; color: #065f46; border-color: var(--cca-success); }
.cca-badge-warning { background: #fef3c7; color: #92400e; border-color: var(--cca-warning); }
.cca-badge-danger  { background: #fee2e2; color: #991b1b; border-color: var(--cca-highlight); }
.cca-badge-neutral { background: #f3f4f6; color: var(--cca-muted); border-color: var(--cca-border); }

/* --- Alerts --- */
.cca-alert {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 16px;
  border-left: 4px solid var(--cca-muted);
  border-radius: 4px;
  background: var(--cca-surface);
  font-size: 11pt;
  position: relative;
}
.cca-alert-info    { border-left-color: var(--cca-accent); background: #eff6ff; }
.cca-alert-success { border-left-color: var(--cca-success); background: #ecfdf5; }
.cca-alert-warning { border-left-color: var(--cca-warning); background: #fffbeb; }
.cca-alert-danger  { border-left-color: var(--cca-highlight); background: #fff1f2; }

.cca-alert-close {
  position: absolute; top: 8px; right: 8px;
  background: none; border: none; cursor: pointer;
  font-size: 14pt; color: var(--cca-muted);
}

/* --- Cards --- */
.cca-card {
  background: var(--cca-bg);
  border: 1px solid var(--cca-border);
  border-radius: 6px;
  overflow: hidden;
}
.cca-card-elevated { box-shadow: 0 4px 12px rgba(0,0,0,0.1); border: none; }
.cca-card-outlined { border: 2px solid var(--cca-accent); }

.cca-card-header { padding: 12px 16px; border-bottom: 1px solid var(--cca-border); }
.cca-card-title { margin: 0; font-size: 14pt; color: var(--cca-primary); font-weight: 700; }
.cca-card-body { padding: 16px; }
.cca-card-footer {
  padding: 8px 16px;
  background: var(--cca-surface);
  border-top: 1px solid var(--cca-border);
  font-size: 9pt;
  color: var(--cca-muted);
}

/* --- Progress bar --- */
.cca-progress-wrap { margin: 8px 0; }
.cca-progress-label { display: block; font-size: 9pt; color: var(--cca-muted); margin-bottom: 4px; }
.cca-progress {
  background: var(--cca-surface);
  border: 1px solid var(--cca-border);
  border-radius: 4px;
  overflow: hidden;
  height: 20px;
}
.cca-progress-bar {
  height: 100%;
  background: var(--cca-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 8pt;
  color: #fff;
  font-weight: 700;
  transition: width 0.3s ease;
  min-width: 28px;
}
.cca-progress-success { background: var(--cca-success); }
.cca-progress-warning { background: var(--cca-warning); color: #1a1a2e; }
.cca-progress-danger  { background: var(--cca-highlight); }

/* --- Data table --- */
.cca-table-wrap { overflow-x: auto; }
.cca-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11pt;
}
.cca-table caption {
  caption-side: top;
  text-align: left;
  font-size: 13pt;
  font-weight: 700;
  color: var(--cca-primary);
  padding: 8px 0;
}
.cca-table th {
  background: var(--cca-surface);
  color: var(--cca-primary);
  font-weight: 700;
  padding: 10px 12px;
  border-bottom: 2px solid var(--cca-border);
  text-align: left;
}
.cca-table td { padding: 8px 12px; border-bottom: 1px solid var(--cca-border); }
.cca-table-striped tr:nth-child(even) td { background: var(--cca-surface); }
.cca-table-compact th, .cca-table-compact td { padding: 4px 8px; font-size: 9pt; }
.cca-table-empty { color: var(--cca-muted); font-style: italic; text-align: center; }

/* --- Tabs --- */
.cca-tabs { border: 1px solid var(--cca-border); border-radius: 6px; overflow: hidden; }
.cca-tab-nav {
  display: flex;
  background: var(--cca-surface);
  border-bottom: 1px solid var(--cca-border);
}
.cca-tab {
  padding: 10px 20px;
  border: none;
  background: none;
  font-size: 11pt;
  font-family: inherit;
  font-weight: 600;
  color: var(--cca-muted);
  cursor: pointer;
  border-bottom: 3px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}
.cca-tab:hover { color: var(--cca-accent); }
.cca-tab-active { color: var(--cca-accent); border-bottom-color: var(--cca-accent); }
.cca-tab-panels { background: var(--cca-bg); }
.cca-tab-panel { padding: 16px; }
.cca-tab-panel[hidden] { display: none; }

/* --- Stat card --- */
.cca-stat-card {
  padding: 16px 20px;
  background: var(--cca-bg);
  border: 1px solid var(--cca-border);
  border-radius: 6px;
}
.cca-stat-label {
  font-size: 9pt;
  color: var(--cca-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 6px;
}
.cca-stat-value {
  font-size: 22pt;
  font-weight: 700;
  color: var(--cca-primary);
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.cca-delta { font-size: 10pt; font-weight: 600; }
.cca-delta-up   { color: var(--cca-success); }
.cca-delta-down { color: var(--cca-highlight); }
.cca-delta-neutral { color: var(--cca-muted); }
.cca-stat-subtitle { font-size: 9pt; color: var(--cca-muted); margin-top: 4px; }

/* --- Dark theme --- */
.cca-theme-dark {
  --cca-bg: var(--cca-dark-bg);
  --cca-surface: var(--cca-dark-surface);
  --cca-border: var(--cca-dark-border);
  --cca-primary: var(--cca-dark-text);
  color: var(--cca-dark-text);
  background: var(--cca-dark-bg);
}
"""


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------

def page(
    title: str,
    components: list[str],
    *,
    theme: str = "light",
) -> str:
    """Wrap components in a full standalone HTML page.

    Args:
        title:      Page <title> and visible <h1>.
        components: List of HTML strings to render in order.
        theme:      "light" | "dark"

    Returns:
        Complete <!DOCTYPE html> document.
    """
    theme_class = " cca-theme-dark" if theme == "dark" else ""
    body_content = "\n".join(components)
    css = component_stylesheet()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(title)}</title>
  <style>
{css}
  </style>
</head>
<body class="cca-page{theme_class}">
  <main class="cca-main">
{body_content}
  </main>
</body>
</html>"""
