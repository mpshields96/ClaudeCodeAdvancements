# MT-32 Phase 2 Research: SVG Library Evaluation

**Author:** Worker cli1, Session 119
**Date:** 2026-03-21
**Task:** Evaluate svg.py and CeTZ-Plot as potential foundations for chart_generator.py

---

## Executive Summary

Neither svg.py nor CeTZ-Plot is a drop-in replacement for chart_generator.py, but each offers
targeted value for specific use cases:

- **svg.py**: Strong candidate for NEW chart types requiring complex SVG features (filters,
  animations, gradients). Not worth migrating existing 14 chart types — high cost, low benefit.
- **CeTZ-Plot**: Valuable for the /cca-report Typst pipeline specifically. Only 6 chart types
  vs our 14+, so cannot replace chart_generator.py wholesale. Could coexist as a "native Typst
  charts" path for simple charts while complex charts remain SVG-embedded.

**Recommendation: REFERENCE — do not migrate, monitor CeTZ-Plot for chart type expansion.**

---

## Part 1: svg.py Evaluation

### Project Details

| Field | Value |
|-------|-------|
| Repository | https://github.com/orsinium-labs/svg.py |
| Version | v1.10.0 (December 28, 2025) |
| Stars | 385 |
| Size | ~63.7 KB source, 9 modules |
| Dependencies | Zero — pure Python stdlib |
| License | MIT |
| Python | 3.8+ |

### API Design

svg.py uses an **object-oriented SVG element model** that mirrors the SVG specification:

```python
import svg

canvas = svg.SVG(
    width=500, height=300,
    elements=[
        svg.Rect(x=10, y=10, width=100, height=80, fill="#0f3460"),
        svg.Text("Session 119", x=60, y=55, fill="white", text_anchor="middle"),
    ],
)
print(canvas)  # → valid SVG string
```

**Exported classes (~90+):**
- Basic shapes: Circle, Ellipse, Rect, Polygon, Polyline, Path
- Text: Text, TextPath, TSpan
- Gradients: LinearGradient, RadialGradient
- Filters: 23+ filter primitives (GaussianBlur, DropShadow, Morphology, etc.)
- Transforms: Translate, Rotate, Scale, SkewX, SkewY, Matrix
- Animation: Animate, AnimateMotion, AnimateTransform
- Path data: 25+ path command classes (M, L, C, Q, A, H, V, Z, etc.)

### How chart_generator.py Does It Today

chart_generator.py uses **raw string concatenation** with helper functions:

```python
def _text(x, y, text, font_size=11, fill=None, anchor="middle", ...):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="..." ...>{_escape(text)}</text>\n'

def _rect(x, y, w, h, fill, rx=0):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" rx="{rx}"/>\n'
```

Each chart's `render_svg()` function concatenates these strings into a complete SVG document.

### Comparison: svg.py vs Current Approach

| Dimension | chart_generator.py (current) | svg.py-based |
|-----------|------------------------------|--------------|
| **Dependencies** | Zero (strings only) | Zero (also stdlib) |
| **Type safety** | None — runtime errors only | Full type hints, mypy-compatible |
| **SVG correctness** | Fragile — manual escaping, no validation | Correct by construction |
| **Gradient support** | Manual string templates | `LinearGradient`, `RadialGradient` classes |
| **Filter effects** | None | 23+ filter primitives |
| **Animation** | None | `Animate`, `AnimateMotion` classes |
| **Complex paths** | Manual `M L A Z` strings | 25+ typed path command classes |
| **Escaping** | Custom `_escape()` function | Built-in (library handles it) |
| **File size** | Single ~2200 LOC file | 9 modules, ~64 KB total |
| **Migration cost** | — | High: 14 chart types × ~100 lines each |

### Migration Cost Analysis

chart_generator.py currently has **14 chart types** across ~2200 LOC. A full migration to svg.py
would require rewriting every chart's `render_svg()` function. Estimated effort:

- ~100-150 lines per chart type × 14 charts = ~1,400-2,100 LOC rewritten
- Plus helper functions (_text, _rect, _line, _circle, _polyline, _lerp_color, _arc_path)
- All 900+ design-skills tests would need re-verification
- Risk: behavioral regressions in SVG output (pixel-level differences could break report_charts.py)

**Verdict: Migration cost is high; benefit is incremental (type safety only).**
The current approach works, is tested, and produces correct SVGs. svg.py is most valuable for
**new features** that would otherwise require complex string-building.

### Where svg.py Adds Clear Value (New Features)

These are cases where our current raw-string approach would be painful:

1. **Animated charts** — e.g., progress bars that animate on load in HTML dashboards
2. **Filter effects** — drop shadows on bar chart labels, blur overlays on alert states
3. **Complex gradient fills** — multi-stop gradients for heat zones in GaugeChart
4. **SVG definitions/symbols** — reusable chart component templates
5. **Accessibility attributes** — `<title>`, `<desc>` elements for screen readers

### Verdict for svg.py

**REFERENCE — Do not migrate existing chart types. Use svg.py as a reference/tool for new
chart types that require SVG features beyond our current helper functions.**

Specifically: if we build an AnimatedSparkline, SVGDefs-based icon library, or filter-enhanced
GaugeChart, svg.py is the right foundation. For BarChart, LineChart, etc. — stay with current approach.

---

## Part 2: CeTZ-Plot Evaluation

### Project Details

| Field | Value |
|-------|-------|
| Repository | https://github.com/cetz-package/cetz-plot |
| Version | v0.1.3 (September 2025) |
| Stars | 248 |
| Language | Typst (99.8%) |
| License | LGPL-3.0 |
| Requires | CeTZ ≥ 0.4.2 |
| Typst Universe | `@preview/cetz-plot:0.1.3` |

### Supported Chart Types

| Chart Type | CeTZ-Plot | chart_generator.py |
|------------|-----------|-------------------|
| Line/trend | ✓ (plot.line) | ✓ LineChart, AreaChart |
| Bar (clustered) | ✓ (chart.bar) | ✓ BarChart, GroupedBarChart |
| Pie/donut | ✓ (chart.piechart) | ✓ DonutChart |
| Pyramid | ✓ | ✗ Not implemented |
| Process/flow | ✓ | ✗ Not implemented |
| Cycle diagram | ✓ | ✗ Not implemented |
| Scatter/bubble | ✗ | ✓ BubbleChart |
| Heatmap | ✗ | ✓ HeatmapChart |
| Waterfall | ✗ | ✓ WaterfallChart |
| Radar/spider | ✗ | ✓ RadarChart |
| Gauge | ✗ | ✓ GaugeChart |
| Treemap | ✗ | ✓ TreemapChart |
| Stacked area | ✗ | ✓ StackedAreaChart |
| Stacked bar | ✗ | ✓ StackedBarChart |
| Sparkline | ✗ | ✓ Sparkline |
| Horizontal bar | ✗ | ✓ HorizontalBarChart |

**Coverage: CeTZ-Plot covers 3/14 of our chart types directly.**

### Integration Pattern

```typst
#import "@preview/cetz:0.4.2"
#import "@preview/cetz-plot:0.1.3": plot, chart

#cetz.canvas({
  plot.plot(size: (6, 4), {
    plot.add(((0,0), (1,1), (2,0.5), (3,2)))
  })
})
```

CeTZ-Plot integrates directly into `.typ` files — no Python intermediary, no SVG files, no
subprocess calls. Charts render as native Typst vector graphics.

### Current /cca-report Pipeline

```
Python (report_generator.py)
  → collect data as JSON
  → render_svg() for each chart
  → embed SVG via Typst image() calls
  → Typst compiles to PDF
```

### Proposed CeTZ-Plot Pipeline (Hybrid)

```
Python (report_generator.py)
  → collect data as JSON
  → write data into .typ file directly
  → Typst renders charts natively via CeTZ-Plot
  → Typst compiles to PDF (no SVG intermediary)
```

**Benefits:**
- Eliminates SVG files as build artifacts
- Charts match Typst's typography and color system exactly
- Simpler pipeline (fewer moving parts)
- Native vector output (no rasterization)

**Costs:**
- Requires CeTZ + CeTZ-Plot as Typst packages (network dependency at first run)
- Only covers 3/14 chart types — would need to maintain SVG pipeline anyway for the rest
- Typst package API may change between versions (LGPL project, less stable than Typst core)
- Debugging requires Typst expertise, not just Python

### Migration Feasibility

A **partial migration** could make sense:
- Simple charts in /cca-report (bar, line, pie) → CeTZ-Plot native
- Complex charts (radar, waterfall, treemap, gauge) → keep SVG embedded via image()
- Would require conditional logic in report_generator.py to choose rendering path

This hybrid adds complexity without eliminating the SVG pipeline entirely.

### Verdict for CeTZ-Plot

**REFERENCE — Track for future adoption when chart type coverage reaches 10+.**

At 3/14 chart type coverage, CeTZ-Plot cannot replace chart_generator.py. A partial migration
would add complexity (two rendering paths) without a clear win. Revisit when:
- CeTZ-Plot reaches v0.3+ with scatter, heatmap, stacked bar support
- We need to produce reports in environments without Python (pure Typst contexts)
- The Typst ecosystem matures enough to guarantee API stability

---

## Part 3: Comparison Matrix

| Dimension | chart_generator.py | svg.py-based | CeTZ-Plot |
|-----------|-------------------|--------------|-----------|
| **Dependencies** | Zero | Zero | CeTZ package |
| **Chart types** | 14 | 14 (if migrated) | 6 natively |
| **Type safety** | None | Full | N/A (Typst) |
| **HTML output** | Yes | Yes | No (PDF only) |
| **PDF output** | Via Typst | Via Typst | Native |
| **Animation** | No | Yes | Limited |
| **Filter effects** | No | Yes | No |
| **Migration cost** | — | High | Very high |
| **Stability** | Battle-tested (900+ tests) | Stable library | Young project |
| **Maintenance** | We own it | External maintainer | External maintainer |

---

## Part 4: Actionable Decisions

### What to Do Now (Session 119+)

1. **Keep chart_generator.py as-is** — 14 chart types, 900+ tests, fully working.
   Do NOT migrate to svg.py.

2. **Use svg.py as inspiration/reference** — when building new chart features that need
   filter effects, animations, or complex gradients, study svg.py's API rather than
   reinventing string helpers.

3. **Monitor CeTZ-Plot** — revisit at v0.3+ for potential native Typst charts in /cca-report.
   Flag if scatter, heatmap, or stacked bar support is added.

4. **If building AnimatedCharts or SVGIconLibrary** — use svg.py as the foundation.
   Install pattern: `pip install svg.py` (63KB, zero runtime deps).

### Open Questions for Desktop

- Is animation a priority for HTML dashboard charts? (If yes, svg.py is worth a prototype)
- Should /cca-report use native CeTZ-Plot for its 3 supported types today, or wait for fuller coverage?
- Should we add `svg.py` to our ROADMAP as a potential foundation for a v2 chart engine?

---

## Sources

- svg.py README: https://github.com/orsinium-labs/svg.py
- svg.py PyPI: https://pypi.org/project/svg.py/
- CeTZ-Plot GitHub: https://github.com/cetz-package/cetz-plot
- CeTZ-Plot Typst Universe: https://typst.app/universe/package/cetz-plot/
- Research conducted: 2026-03-21 (Worker cli1, S119)
