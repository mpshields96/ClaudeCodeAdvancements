# CCA Design Guide — Visual Language

All CCA visual output (reports, dashboards, presentations) follows this guide.

---

## Color Palette

All CCA visual output uses ONE palette. Typst templates, SVG charts, HTML dashboards,
and the website all share these exact values. See chart_generator.py CCA_COLORS.

| Role | Hex | Usage |
|------|-----|-------|
| Primary | #1a1a2e | Headers, titles, body text |
| Accent | #0f3460 | Section headers, borders, interactive elements |
| Highlight | #e94560 | Warnings, critical items, key metrics |
| Success | #16c79a | Passing tests, completed items |
| Muted | #6b7280 | Secondary text, captions, metadata |
| Warning | #f59e0b | Caution, medium-priority items |
| Background | #ffffff | Page background |
| Surface | #f8f9fa | Card/section backgrounds |
| Border | #e5e7eb | Table borders, dividers |
| Dark | #3a3a3c | Body text (Typst template default text fill) |
| Mid | #636366 | Descriptions, secondary body text |
| Teal | #5ac8fa | Module section accents (e.g. Module Deep-Dives header) |

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

## Design Tokens (MT-32 — Anti-AI-Slop System)

These tokens are the antidote to "AI slop UI" — the purple/indigo, generic card, verbose copy
pattern that makes AI-generated output immediately identifiable. Every CCA visual output MUST
use these tokens, never browser/LLM defaults.

### Color Tokens

| Token | Value | When to use | NEVER |
|-------|-------|-------------|-------|
| `--cca-primary` | #1a1a2e | Text, headers, emphasis | Never purple/indigo |
| `--cca-accent` | #0f3460 | Interactive elements, links, section borders | Never generic blue (#0000ff) |
| `--cca-highlight` | #e94560 | Warnings, critical data, call-to-action | Never red (#ff0000) |
| `--cca-success` | #16c79a | Passing, complete, positive metrics | Never lime green |
| `--cca-warning` | #f59e0b | Caution, medium-priority items | Never orange-red blends |
| `--cca-muted` | #6b7280 | Secondary text, metadata, captions | Never light gray (#ccc) |
| `--cca-bg` | #ffffff | Page/card backgrounds | Never off-white with tint |
| `--cca-surface` | #f8f9fa | Elevated surfaces, cards | Never darker than bg |
| `--cca-border` | #e5e7eb | Dividers, table borders | Never visible on white bg |

### Spacing Scale (8px base grid)

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | 4px / 1mm | Inline gaps, tight packing |
| `--space-sm` | 8px / 2mm | Within-component spacing |
| `--space-md` | 16px / 4mm | Between components |
| `--space-lg` | 24px / 6mm | Section separation |
| `--space-xl` | 32px / 8mm | Major section breaks |
| `--space-2xl` | 48px / 12mm | Page-level spacing |

### Typography Scale

| Token | Size | Weight | Line-height | Usage |
|-------|------|--------|-------------|-------|
| `--type-display` | 36pt | Bold | 1.1 | Cover page title only |
| `--type-h1` | 24pt | Bold | 1.2 | Report title |
| `--type-h2` | 17pt | Bold | 1.3 | Section headers |
| `--type-h3` | 14pt | Bold | 1.3 | Subsection headers |
| `--type-body` | 9.5-11pt | Regular | 1.5 | Body text |
| `--type-caption` | 7.5-8pt | Regular/Semibold | 1.4 | Labels, annotations |
| `--type-metric` | 22pt | Bold | 1.1 | Large numeric displays |
| `--type-code` | 10pt | Regular | 1.4 | Code, data values |

### Anti-AI-Slop Rules

1. **NO DEFAULT PURPLE** — if any output uses purple/indigo as a primary color, it's wrong
2. **NO GENERIC CARDS** — every card must serve a specific data purpose, not be decorative
3. **NO VERBOSE COPY** — data density over explanation. Show, don't tell.
4. **NO TAILWIND DEFAULTS** — explicit token values, never `text-gray-500` or `bg-indigo-600`
5. **NO ROUNDED-EVERYTHING** — use 3-5px radius for cards, 0 for data tables, never `rounded-full` on containers

### Chart Series Palette (not purple)

| Position | Hex | Name |
|----------|-----|------|
| Series 1 | #0f3460 | Deep blue (accent) |
| Series 2 | #e94560 | Rose (highlight) |
| Series 3 | #16c79a | Teal (success) |
| Series 4 | #f59e0b | Amber (warning) |
| Series 5 | #6b7280 | Slate (muted) |
| Series 6 | #8b5cf6 | Violet (sparingly — NOT as primary) |
| Series 7 | #06b6d4 | Cyan |
| Series 8 | #84cc16 | Lime |

## Chart/Visualization Rules

- Bar charts over pie charts (easier to compare)
- Horizontal bars for categories, vertical for time series
- Always label axes
- Use accent color for primary series, muted for secondary
- No 3D effects, no gradients, no decorative elements
- 14 chart types available: Bar, HorizontalBar, Line, Sparkline, Donut, Heatmap, StackedBar, Area, StackedArea, Waterfall, Radar, Gauge, Bubble, Treemap
- For Typst reports: charts auto-generated as SVG and embedded via report_charts.py

## Rules: Do

- Prefer semantic color tokens (e.g., "Success", "Highlight") over raw hex values
- Preserve visual hierarchy: title > section header > body > caption
- Keep interaction-free: reports are static PDF, no hover states needed
- Use concrete token values in all rules — no "large" or "subtle"
- Pair every spacing decision with a specific pt/mm value

## Rules: Don't

- Avoid low contrast text (minimum 4.5:1 ratio against background)
- Avoid inconsistent spacing rhythm — stick to the 4/8/12/16/24/32 scale
- Avoid decorative elements: no gradients, shadows, 3D, or ornamental borders
- Avoid more than 3 font weights per report (Regular, Semibold, Bold)
- Avoid color as the sole indicator — always pair with symbol or text

## Quality Gates

- Every color must map to a named token — no orphan hex values
- Typography hierarchy must be testable: title > subtitle > header > body in both size and weight
- Tables must have alternating rows and visible borders for print readability
- Accessibility: all text meets WCAG 2.2 AA contrast requirements
- Consistency: same metric should look identical across all report types

## Report Types

1. **CCA Status Report** — Full project overview: modules, tests, master tasks, findings
2. **Session Summary** — What was done, commits, learnings
3. **Scan Report** — NEEDLE/BUILD/ADAPT analysis from subreddit scans
4. **Paper Report** — Academic paper discovery results from MT-12

## External Design References

For expanding CCA's visual range beyond the default professional style:
- **typeui.sh** — 57 pre-built design system skill files (github.com/bergside/awesome-design-skills)
- Key styles to study: `minimal` (clean/functional), `enterprise` (corporate/data-dense), `editorial` (publication-quality)
- Pattern: each style defines color tokens, typography scale, component families, accessibility requirements, and quality gates in a single markdown file
- Adaptation: CCA could offer multiple report "themes" by swapping color tokens and typography while keeping the same layout structure
