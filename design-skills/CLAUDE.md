# Design Skills Module — Rules

## Purpose
Professional-quality visual output (PDF reports, HTML dashboards) from CCA data.
Replaces ad-hoc PDF generation with consistent, typographically sound design.

## Architecture
- `design-guide.md` — CCA visual language (colors, fonts, spacing, layout)
- `templates/` — Typst templates for different report types
- `report_generator.py` — Python CLI that collects CCA data and calls Typst
- `tests/` — Test suite for report_generator.py

## Key Decisions
- **Typst over WeasyPrint/ReportLab** — single binary, millisecond compile, JSON-native, professional typography
- **Pipeline:** Python collects data as JSON -> Typst template renders PDF
- **No external Python deps** — Typst is a system binary called via subprocess
- **One template per report type** — CCA status, session summary, scan report, paper report

## Design Principles
- Clean, minimal, professional — no decorative elements
- Consistent color palette across all reports
- Readable typography (11-12pt body, clear hierarchy)
- Data-dense but not cluttered
- Accessible (high contrast, semantic structure)
