# CCA Design Guide — Visual Language

All CCA visual output (reports, dashboards, presentations) follows this guide.

---

## Color Palette

| Role | Hex | Usage |
|------|-----|-------|
| Primary | #1a1a2e | Headers, titles, body text |
| Accent | #0f3460 | Section headers, borders |
| Highlight | #e94560 | Warnings, critical items, key metrics |
| Success | #16c79a | Passing tests, completed items |
| Muted | #6b7280 | Secondary text, captions, metadata |
| Background | #ffffff | Page background |
| Surface | #f8f9fa | Card/section backgrounds |
| Border | #e5e7eb | Table borders, dividers |

## Typography

| Element | Font | Size | Weight |
|---------|------|------|--------|
| Title | Source Sans 3 | 24pt | Bold |
| Subtitle | Source Sans 3 | 16pt | Semibold |
| Section Header | Source Sans 3 | 14pt | Bold |
| Body | Source Sans 3 | 11pt | Regular |
| Code/Data | Source Code Pro | 10pt | Regular |
| Caption | Source Sans 3 | 9pt | Regular |
| Metric Value | Source Sans 3 | 20pt | Bold |

Fallback fonts: Helvetica Neue, Arial, sans-serif (for systems without Source Sans).

## Layout

- **Page:** A4 (210mm x 297mm), 20mm margins
- **Header:** Project name left, date right, thin accent line below
- **Footer:** Page number center, generation timestamp right
- **Sections:** 12pt spacing between sections, 8pt within
- **Cards:** Surface background, 1px border, 8px padding, 4px border-radius
- **Tables:** Alternating row colors (white / surface), header in accent
- **Columns:** 2-column layout for metric cards, full-width for tables

## Status Indicators

| Status | Color | Symbol |
|--------|-------|--------|
| Complete | Success (#16c79a) | filled circle |
| In Progress | Accent (#0f3460) | half circle |
| Not Started | Muted (#6b7280) | empty circle |
| Failing | Highlight (#e94560) | X mark |
| Warning | #f59e0b | triangle |

## Chart/Visualization Rules

- Bar charts over pie charts (easier to compare)
- Horizontal bars for categories, vertical for time series
- Always label axes
- Use accent color for primary series, muted for secondary
- No 3D effects, no gradients, no decorative elements

## Report Types

1. **CCA Status Report** — Full project overview: modules, tests, master tasks, findings
2. **Session Summary** — What was done, commits, learnings
3. **Scan Report** — NEEDLE/BUILD/ADAPT analysis from subreddit scans
4. **Paper Report** — Academic paper discovery results from MT-12
