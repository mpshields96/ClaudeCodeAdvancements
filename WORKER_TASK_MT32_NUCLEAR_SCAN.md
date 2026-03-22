# Worker Task: MT-32 Visual/Design Nuclear Intelligence Scan

**Assigned by:** Desktop coordinator (S118)
**Priority:** HIGH — Matthew explicit directive
**Estimated time:** 45-60 minutes
**Type:** Deep nuclear scan (subreddits + GitHub)

---

## What You're Looking For

MT-32 (Visual Excellence & Design Engineering) needs research intelligence across 8 pillars:

1. **Report generation** — Tools, libraries, techniques for AI-generated professional reports (PDF, HTML, Typst, LaTeX). What produces output that doesn't look like "AI slop"?
2. **UI development** — Frameworks, component libraries, design patterns for LLM-generated web UIs. What makes Claude Code web output look professional?
3. **Graphic design** — SVG generation, icon creation, infographic tools, visual asset pipelines. AI-assisted graphic design that works.
4. **Data visualization** — Interactive charts, D3.js alternatives, publication-quality statistical graphics. Beyond basic bar/line/donut.
5. **Figure/image generation** — Multi-panel figures, scientific visualization, diagram generation (beyond mermaid). Architecture diagrams, flow charts, ER diagrams.
6. **Dashboard design** — Interactive web dashboards, real-time data display, responsive layouts. What dashboards built by AI actually look good?
7. **Design systems** — Design tokens, color systems, typography scales, spacing. How to make AI output consistently branded.
8. **Presentation/slide design** — Slide generators, deck builders, visual storytelling. AI-generated presentations that aren't embarrassing.

---

## Subreddits to Scan (Prioritized)

**Tier 1 — Most likely to have high-signal posts:**
- r/ClaudeCode — search for: UI, design, visual, chart, dashboard, report, CSS, frontend, styling
- r/ChatGPTCoding — search for: UI generation, component, design system, visualization
- r/webdev — search for: AI-generated UI, Claude, LLM web design, AI dashboard
- r/reactjs — search for: AI component generation, Claude code, design system automation
- r/frontend — search for: AI design, LLM frontend, Claude styling

**Tier 2 — Specialized knowledge:**
- r/dataisbeautiful — search for: tool, library, Python visualization, SVG
- r/datavisualization — search for: D3, plotly, interactive chart, publication quality
- r/web_design — search for: AI design, Claude, automation, design system
- r/UI_Design — search for: AI, component library, design tokens
- r/graphic_design — search for: AI tools, SVG, automation, vector

**Tier 3 — Framework-specific:**
- r/tailwindcss — search for: AI, component, design system
- r/svelte — search for: AI generation, dashboard, visualization
- r/nextjs — search for: AI UI generation, dashboard template

---

## GitHub Scan Targets

Search GitHub trending for repos tagged with:
- `visualization`, `data-visualization`, `chart`, `svg-charts`
- `design-system`, `design-tokens`, `ui-library`
- `report-generator`, `pdf-generator`, `dashboard`
- `infographic`, `diagram`, `figure-generation`
- `ai-ui`, `llm-ui`, `claude-code`

Focus on repos with:
- 100+ stars (quality signal)
- Recent activity (last 3 months)
- Python or JavaScript/TypeScript (our stack)
- Clean documentation (usable, not vaporware)

---

## How to Execute

1. Use `python3 reddit-intelligence/reddit_reader.py "<url>"` for Reddit posts
2. Use `python3 reddit-intelligence/github_scanner.py` for GitHub scanning
3. For each finding, log to FINDINGS_LOG.md with verdict:
   - **BUILD**: We should build this into CCA
   - **ADAPT**: Core concept useful, needs CCA-specific adaptation
   - **REFERENCE**: Good to know, file for later
   - **SKIP**: Not useful / rat poison

---

## Rat Poison Filter (CRITICAL)

SKIP anything that:
- Is an 8000-line prompt library pretending to be a design system
- Requires Figma, Sketch, or proprietary design tool MCPs
- Uses "team of specialists" metaphor (one LLM with good instructions = same result)
- Is purely aesthetic with no functional improvement
- Adds heavy dependencies (prefer stdlib, SVG, vanilla CSS)
- Is a wrapper around GPT-4 Vision for screenshot-to-code (well-trodden, diminishing returns)

PRIORITIZE anything that:
- Shows concrete before/after visual improvement
- Has a working demo or real output samples
- Uses techniques applicable to Typst/HTML/SVG (our output formats)
- Addresses the specific weakness of LLM-generated UIs (layout, spacing, color, typography)
- Is buildable in Python with minimal deps
- Helps with report generation specifically (Matthew's emphasis)

---

## Deliverable

Write findings to: `MT32_VISUAL_DESIGN_SCAN.md` in project root.

Format per finding:
```
### [Title] — [Verdict: BUILD/ADAPT/REFERENCE/SKIP]
**Source:** [URL]
**Stars/Score:** [if applicable]
**Relevant MT-32 Pillar(s):** [1-8 from list above]
**What it does:** [2-3 sentences]
**Why it matters for CCA:** [1-2 sentences]
**Rat poison check:** [CLEAN / concern noted]
```

End with a summary: top 3 BUILD/ADAPT findings and how they map to MT-32 phases.

---

## After Scan

Run `python3 cca_comm.py done "MT-32 nuclear scan complete — [N] findings, [M] BUILD/ADAPT"` when finished.
