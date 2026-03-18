// CCA Slide Template — 16:9 Presentation
// Usage: typst compile --root / --input data=/path/to/slides.json cca-slides.typ output.pdf

// --- Color Palette (from design-guide.md) ---
#let primary = rgb("#1a1a2e")
#let accent = rgb("#0f3460")
#let highlight = rgb("#e94560")
#let success = rgb("#16c79a")
#let muted = rgb("#6b7280")
#let surface = rgb("#f8f9fa")
#let border = rgb("#e5e7eb")
#let warning = rgb("#f59e0b")

// --- Data Loading ---
#let data = if sys.inputs.keys().contains("data") {
  json(sys.inputs.data)
} else {
  (
    title: "ClaudeCodeAdvancements",
    subtitle: "Project Update",
    author: "",
    date: "2026-03-18",
    session: 46,
    slides: (
      (type: "section", title: "Session 46 Overview"),
      (type: "summary", metrics: (
        total_tests: 1593,
        passing_tests: 1593,
        test_suites: 39,
        total_modules: 9,
        total_findings: 283,
      )),
      (type: "metrics", title: "Key Metrics", metrics: (
        (label: "Tests", value: "1593", sublabel: "39 suites"),
        (label: "Modules", value: "9", sublabel: "5 frontiers"),
        (label: "Findings", value: "283", sublabel: "32% APF"),
      )),
      (type: "bullets", title: "Five Frontiers", bullets: (
        "Memory System — persistent cross-session memory",
        "Spec System — requirements-first development",
        "Context Monitor — health tracking + auto-handoff",
        "Agent Guard — multi-agent safety",
        "Usage Dashboard — token/cost transparency",
      )),
      (type: "modules", modules: (
        (name: "Memory System", status: "COMPLETE", tests: 94),
        (name: "Spec System", status: "COMPLETE", tests: 90),
        (name: "Context Monitor", status: "COMPLETE", tests: 197),
        (name: "Agent Guard", status: "COMPLETE", tests: 264),
        (name: "Usage Dashboard", status: "COMPLETE", tests: 196),
      )),
    ),
  )
}

// --- Page Setup: 16:9 landscape ---
#set page(
  width: 254mm,
  height: 142.9mm,
  margin: (x: 20mm, y: 15mm),
  fill: white,
)

#set text(font: "Helvetica Neue", size: 14pt, fill: primary)

// --- Helper Functions ---

#let slide-header(body) = {
  text(size: 24pt, weight: "bold", fill: accent, body)
  v(2mm)
  line(length: 100%, stroke: 0.5pt + accent)
  v(6mm)
}

#let slide-footer() = {
  place(bottom + left, dy: 8mm,
    text(size: 8pt, fill: muted, data.title + " | " + data.date)
  )
  place(bottom + right, dy: 8mm,
    context text(size: 8pt, fill: muted,
      counter(page).display("1 / 1", both: true)
    )
  )
}

#let metric-card(label, value, sublabel) = {
  box(
    width: 100%,
    inset: 12pt,
    radius: 4pt,
    fill: surface,
    stroke: 0.5pt + border,
    [
      #text(size: 10pt, fill: muted, weight: "regular", label)
      #v(2mm)
      #text(size: 28pt, weight: "bold", fill: accent, value)
      #v(1mm)
      #text(size: 9pt, fill: muted, sublabel)
    ]
  )
}

#let status-dot(status) = {
  let color = if status == "COMPLETE" { success }
    else if status == "IN PROGRESS" { accent }
    else if status == "FAILING" { highlight }
    else { muted }
  box(circle(radius: 3pt, fill: color))
}

// --- Title Slide ---
#page[
  #v(1fr)
  #align(center)[
    #text(size: 36pt, weight: "bold", fill: primary, data.title)
    #v(4mm)
    #text(size: 18pt, fill: accent, data.subtitle)
    #v(8mm)
    #if data.author != "" {
      text(size: 12pt, fill: muted, data.author)
      v(2mm)
    }
    #text(size: 12pt, fill: muted, data.date)
    #if data.session != none {
      text(size: 12pt, fill: muted, "  |  Session " + str(data.session))
    }
  ]
  #v(1fr)
  #align(center)[
    #line(length: 40%, stroke: 1pt + accent)
  ]
  #v(8mm)
]

// --- Content Slides ---
#for slide in data.slides {

  // Section divider slide
  if slide.type == "section" {
    page[
      #v(1fr)
      #align(center)[
        #text(size: 32pt, weight: "bold", fill: accent, slide.title)
        #v(4mm)
        #line(length: 30%, stroke: 1pt + accent)
      ]
      #v(1fr)
    ]
  }

  // Summary slide (project overview numbers)
  else if slide.type == "summary" {
    page[
      #slide-header("Project Summary")
      #grid(
        columns: (1fr, 1fr, 1fr),
        column-gutter: 12pt,
        metric-card(
          "Tests",
          str(slide.metrics.passing_tests) + "/" + str(slide.metrics.total_tests),
          str(slide.metrics.test_suites) + " suites"
        ),
        metric-card(
          "Modules",
          str(slide.metrics.total_modules),
          "active modules"
        ),
        metric-card(
          "Findings",
          str(slide.metrics.total_findings),
          "from community research"
        ),
      )
      #slide-footer()
    ]
  }

  // Metric cards slide (custom large numbers)
  else if slide.type == "metrics" {
    page[
      #slide-header(slide.title)
      #let cols = slide.metrics.len()
      #let col-sizes = range(cols).map(_ => 1fr)
      #grid(
        columns: col-sizes,
        column-gutter: 12pt,
        ..slide.metrics.map(m => metric-card(m.label, m.value, m.sublabel))
      )
      #slide-footer()
    ]
  }

  // Bullet point slide
  else if slide.type == "bullets" {
    page[
      #slide-header(slide.title)
      #for bullet in slide.bullets {
        text(size: 14pt, fill: primary)[
          #h(4mm) #text(fill: accent, weight: "bold", "- ") #bullet
        ]
        v(6mm)
      }
      #slide-footer()
    ]
  }

  // Module status table slide
  else if slide.type == "modules" {
    page[
      #slide-header("Module Status")
      #table(
        columns: (auto, 1fr, auto, auto),
        inset: 8pt,
        stroke: 0.5pt + border,
        fill: (_, y) => if y == 0 { accent.lighten(90%) } else if calc.odd(y) { surface } else { white },
        table.header(
          text(weight: "bold", fill: accent, ""),
          text(weight: "bold", fill: accent, "Module"),
          text(weight: "bold", fill: accent, "Status"),
          text(weight: "bold", fill: accent, "Tests"),
        ),
        ..slide.modules.map(m => (
          status-dot(m.status),
          text(m.name),
          text(size: 11pt, fill: if m.status == "COMPLETE" { success } else { muted }, m.status),
          text(size: 11pt, str(m.tests)),
        )).flatten()
      )
      #slide-footer()
    ]
  }
}
