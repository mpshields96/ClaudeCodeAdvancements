# MT-17 Research: PDF Generation Libraries for Professional Reports

**Date:** 2026-03-18 (Session 40)
**Goal:** Select the best library for generating professional-quality PDF reports from CCA data.

---

## Problem Statement

Claude Code produces visually poor PDF output. Matthew's CCA status report PDF was "atrocious." The r/ClaudeCode community widely identifies UI/design as Claude's weakest capability. MT-17 needs a programmatic PDF generation pipeline that produces professional results.

---

## Libraries Evaluated

### 1. Typst (RECOMMENDED)

**What:** Modern typesetting system — single binary, compiles .typ templates to PDF in milliseconds.
**Installation:** `brew install typst` (~40MB binary)
**Python integration:** Call via subprocess with `--input` flag for data passing. No native Python library needed.

**Strengths:**
- Millisecond compilation (vs seconds for LaTeX)
- Built-in parsers for JSON, CSV, XML — no external preprocessing needed
- Rich typography and layout out of the box
- Accessible PDFs by default (PDF/UA-1 optional)
- Single binary — no dependency hell
- Active development, growing package ecosystem (Typst Universe)
- Templates use a clean scripting language (not TeX macros)

**Weaknesses:**
- Newer ecosystem — fewer templates than LaTeX
- No direct Python library (subprocess only)
- Package ecosystem smaller than LaTeX

**Pipeline:**
1. Python script prepares data as JSON (project stats, test counts, module status)
2. Typst template (`cca-report.typ`) reads JSON and renders professional PDF
3. `typst compile --input data=report.json cca-report.typ output.pdf`

**CCA fit:** Perfect. Data is already JSON (papers.jsonl, journal.jsonl, scan reports). Typst reads JSON natively. One template → professional PDFs.

### 2. WeasyPrint

**What:** Python library that converts HTML + CSS to PDF.
**Installation:** `pip install weasyprint` (requires system deps: cairo, pango, gdk-pixbuf)

**Strengths:**
- Leverages HTML/CSS skills — write reports as web pages
- Good CSS Paged Media support (headers, footers, page numbers)
- Integrates with Jinja2 templates
- Mature, well-documented

**Weaknesses:**
- Heavy system dependencies (cairo, pango) — not stdlib-friendly
- Two-step workflow: HTML → PDF
- Limited paged media features compared to Typst
- Rendering quality varies with CSS complexity

**CCA fit:** Decent but heavier than needed. Good fallback if Typst doesn't work.

### 3. ReportLab

**What:** Python library for programmatic PDF construction.
**Installation:** `pip install reportlab`

**Strengths:**
- Pure Python (mostly)
- Full control over every PDF element
- Charts via ReportLab's built-in graphics
- Mature, production-proven

**Weaknesses:**
- Steep learning curve — imperative API, not declarative
- Verbose code for basic layouts
- Typography requires manual configuration
- No template system built-in

**CCA fit:** Too low-level for our needs. Good for complex charts but overkill for status reports.

### 4. fpdf2

**What:** Lightweight Python PDF library.
**Installation:** `pip install fpdf2`

**Strengths:**
- Pure Python, lightweight
- Unicode support
- Simple API

**Weaknesses:**
- Limited layout capabilities
- No template system
- Output quality lower than Typst/WeasyPrint

**CCA fit:** Too basic for professional reports.

---

## Recommendation: Typst

**Primary:** Typst for all CCA report generation.
- `brew install typst` (one-time)
- Create `design-skills/templates/cca-report.typ` (Typst template)
- Python script generates JSON data → Typst compiles to PDF
- Professional typography with zero Python dependencies

**Fallback:** WeasyPrint if Typst proves insufficient for specific layouts.

---

## Implementation Plan for MT-17

### Phase 1: Foundation
1. Install Typst (`brew install typst`)
2. Create `design-skills/` module directory
3. Create `design-skills/design-guide.md` — CCA visual language (colors, fonts, spacing)
4. Create first Typst template: `design-skills/templates/cca-report.typ`
5. Create `design-skills/report_generator.py` — Python script that collects CCA data and calls Typst

### Phase 2: Report Types
1. CCA Status Report (project overview, module status, test counts, master tasks)
2. Session Summary Report (what was done, commits, findings)
3. Scan Report (NEEDLE/BUILD/ADAPT analysis results)
4. Paper Scanner Report (top papers, domain breakdown)

### Phase 3: Design Excellence
1. Design vocabulary document (color palette, typography scale, layout patterns)
2. `/cca-report` slash command for one-command report generation
3. Multiple output formats (PDF, HTML)
4. Chart/visualization support

### Phase 4: Autonomous Report UI Scan
1. Add r/webdev, r/reactjs, r/frontend, r/UI_Design to autonomous scan targets
2. Track design-related findings separately for continuous improvement

---

## Paper Deep-Reads (Session 40)

### "Deep Research Agents: A Systematic Examination And Roadmap" (80/100)
- **arXiv:** 2506.18096 (June 2025, 117 citations)
- **Authors:** Yuxuan Huang et al. (Huawei Noah's Ark Lab, Oxford, UCL, Liverpool)
- **Key taxonomy:** Static vs dynamic workflows; single-agent vs multi-agent
- **MCP integration:** Paper explicitly discusses Model Context Protocol for extensibility
- **CCA relevance:** Validates our autonomous scanner architecture. Our MT-9 scanner uses dynamic workflows + tool composition (fetch → filter → classify → report). Paper confirms this is the right pattern.
- **Key gap identified:** Sequential execution inefficiencies — directly applicable to our scan pipeline. Could parallelize fetch + classify steps.
- **Action:** REFERENCE. Validates CCA architecture, no new patterns to implement.

### "HALO: Hierarchical Autonomous Logic-Oriented Orchestration" (75/100)
- **arXiv:** 2505.13516 (May 2025, 11 citations, has code)
- **Authors:** Zhipeng Hou, Junyi Tang, Yipeng Wang
- **Architecture:** 3-level hierarchy: planning → role-design → inference
- **Innovation:** MCTS (Monte Carlo Tree Search) for workflow optimization — treats agent interactions as searchable space
- **Results:** 14.4% average improvement over SOTA baselines
- **CCA relevance:** The hierarchy pattern maps to CCA's own architecture: /cca-auto (planning) → task selection (role-design) → gsd:quick (inference). The MCTS concept could optimize task ordering — instead of fixed queue, search for optimal execution order.
- **Action:** ADAPT (future). The MCTS workflow search concept is novel. Could be implemented as a task prioritizer that considers dependencies, context cost, and expected value. Not urgent — current priority queue works.

### "Agent0: Self-Evolving Agents from Zero Data" (69/100)
- Already logged Session 38. Self-evolving via tool-integrated reasoning. Directly validates SentinelMutator in MT-10.

---

## Sources
- [Generating PDF in Python (Rost Glukhov)](https://www.glukhov.org/post/2025/05/generating-pdf-in-python/)
- [Typst Automated PDF Generation Blog](https://typst.app/blog/2025/automated-generation/)
- [Deep Research Agents (arXiv 2506.18096)](https://arxiv.org/abs/2506.18096)
- [HALO (arXiv 2505.13516)](https://arxiv.org/abs/2505.13516)
