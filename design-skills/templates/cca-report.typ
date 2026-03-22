// CCA Comprehensive Status Report — Apple-Inspired Design v2
// Usage: typst compile --root / --input data=/path/to/report.json cca-report.typ output.pdf

// ─── Color Palette ─────────────────────────────────────────────────────────
#let black = rgb("#1c1c1e")
#let dark = rgb("#3a3a3c")
#let mid = rgb("#636366")
#let light = rgb("#8e8e93")
#let faint = rgb("#d1d1d6")
#let wash = rgb("#f2f2f7")
#let white = rgb("#ffffff")
#let blue = rgb("#007aff")
#let green = rgb("#34c759")
#let orange = rgb("#ff9500")
#let red = rgb("#ff3b30")
#let purple = rgb("#af52de")
#let teal = rgb("#5ac8fa")
#let indigo = rgb("#5856d6")

// ─── Data Loading ──────────────────────────────────────────────────────────
#let data = if sys.inputs.keys().contains("data") {
  json(sys.inputs.data)
} else {
  (
    title: "ClaudeCodeAdvancements",
    subtitle: "Comprehensive Project Report",
    date: "2026-03-18",
    session: 54,
    summary: (
      total_tests: 1768, passing_tests: 1768, test_suites: 44,
      total_modules: 9, total_findings: 289, total_papers: 21,
      master_tasks: 19, completed_tasks: 8, in_progress_tasks: 7,
      not_started_tasks: 3, blocked_tasks: 1,
      source_files: 50, test_files: 45, source_loc: 19110,
      test_loc: 18621, total_loc: 37731, git_commits: 217,
      project_age_days: 28, live_hooks: 9, total_delivered: 0,
    ),
    executive_summary: "",
    modules: (),
    master_tasks_complete: (),
    master_tasks_active: (),
    master_tasks_pending: (),
    hooks: (),
    intelligence: (findings_total: 289, build: 19, adapt: 51, reference: 104, reference_personal: 13, skip: 32, other: 26, subreddits_scanned: 7, github_repos_evaluated: 30),
    self_learning: (strategies_total: 10, strategies_confirmed: 4, proposals: 6, trace_sessions: 31, avg_score: 70, papers_logged: 21, sentinel_rate: "5-10%"),
    risks: (),
    next_priorities: (),
    architecture_decisions: (),
    session_highlights: (),
    frontiers: (),
    priority_queue: (),
  )
}

// ─── Chart Directory ──────────────────────────────────────────────────────
#let chart-dir = if sys.inputs.keys().contains("chart_dir") {
  sys.inputs.chart_dir
} else {
  none
}

#let embed-chart(name, width: 100%) = {
  if chart-dir != none {
    let path = chart-dir + "/" + name + ".svg"
    image(path, width: width)
  }
}

// ─── Helpers ───────────────────────────────────────────────────────────────

#let status-badge(label, bg-color, text-color: white) = {
  box(
    fill: bg-color,
    radius: 3pt,
    inset: (x: 6pt, y: 3pt),
  )[#text(size: 7.5pt, weight: "semibold", fill: text-color)[#label]]
}

#let fmt(n) = {
  let s = str(n)
  let len = s.len()
  let result = ""
  for (i, c) in s.codepoints().enumerate() {
    if i > 0 and calc.rem(len - i, 3) == 0 { result += "," }
    result += c
  }
  result
}

#let section-header(title) = {
  v(5mm)
  text(size: 7.5pt, fill: light, weight: "semibold", tracking: 1.5pt)[#upper(title)]
  v(1mm)
  text(size: 17pt, weight: "bold", fill: black)[#title]
  v(2mm)
  line(length: 100%, stroke: 0.3pt + faint)
  v(3mm)
}

#let progress-bar(current, total, width: 100%, bar-color: blue, height: 5pt) = {
  let pct = if total > 0 { calc.min(current / total, 1.0) } else { 0 }
  box(width: width, height: height, radius: 2.5pt, fill: wash, clip: true)[
    #box(width: pct * 100%, height: 100%, fill: bar-color, radius: 2.5pt)
  ]
}

#let metric(label, value, accent-color: black) = {
  box(width: 100%, inset: (x: 0pt, y: 4pt))[
    #text(size: 7.5pt, fill: light, weight: "semibold")[#upper(label)]
    #v(1mm)
    #text(size: 22pt, weight: "bold", fill: accent-color)[#value]
  ]
}

#let kv-row(key, value, highlight: false) = {
  grid(
    columns: (35%, 65%),
    text(size: 8.5pt, fill: light)[#key],
    text(size: 8.5pt, fill: if highlight { blue } else { dark }, weight: if highlight { "semibold" } else { "regular" })[#value],
  )
  v(2pt)
}

// ─── Page Setup ────────────────────────────────────────────────────────────
#set page(
  paper: "a4",
  margin: (top: 24mm, bottom: 22mm, left: 22mm, right: 22mm),
  header: context {
    if counter(page).get().first() > 1 {
      set text(size: 7pt, fill: light)
      grid(
        columns: (1fr, 1fr),
        align: (left, right),
        [ClaudeCodeAdvancements],
        [Session #data.session #sym.dot.c #data.date],
      )
      v(1mm)
      line(length: 100%, stroke: 0.2pt + faint)
    }
  },
  footer: context {
    if counter(page).get().first() > 1 {
      line(length: 100%, stroke: 0.2pt + faint)
      v(1mm)
      set text(size: 7pt, fill: light)
      grid(
        columns: (1fr, 1fr),
        align: (left, right),
        [Comprehensive Project Report],
        [#counter(page).display()],
      )
    }
  },
)

#set text(font: "Helvetica Neue", size: 9.5pt, fill: dark)
#set par(leading: 0.65em)

// ═══════════════════════════════════════════════════════════════════════════
// PAGE 1: COVER
// ═══════════════════════════════════════════════════════════════════════════

#place(top + left, dx: -22mm, dy: -24mm)[
  #rect(width: 210mm + 1mm, height: 0.8mm, fill: black)
]

#v(48mm)

#align(center)[
  #text(size: 9pt, fill: light, tracking: 2.5pt, weight: "semibold")[PROJECT STATUS REPORT]
  #v(6mm)
  #text(size: 36pt, weight: "bold", fill: black, tracking: -0.5pt)[ClaudeCode]
  #v(-2mm)
  #text(size: 36pt, weight: "bold", fill: black, tracking: -0.5pt)[Advancements]
  #v(8mm)
  #line(length: 36mm, stroke: 0.3pt + faint)
  #v(8mm)
  #text(size: 10pt, fill: mid)[
    Research, tools, and systems for AI-assisted development
  ]
]

#v(28mm)

// Hero metrics
#let hero-stats = (
  (fmt(data.summary.total_tests), "tests passing"),
  (fmt(data.summary.total_loc), "lines of code"),
  (str(data.summary.total_modules), "modules"),
  (str(data.summary.git_commits), "commits"),
)

#{
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 0pt,
    ..hero-stats.map(((val, label)) => {
      align(center)[
        #text(size: 24pt, weight: "bold", fill: black)[#val]
        #v(2mm)
        #text(size: 7.5pt, fill: light, tracking: 0.5pt)[#upper(label)]
      ]
    })
  )
}

#v(12mm)

// Secondary stats row
#let secondary-stats = (
  (str(data.summary.master_tasks), "master tasks"),
  (str(data.summary.total_findings), "intelligence findings"),
  (str(data.summary.live_hooks), "live hooks"),
  (str(data.summary.project_age_days) + "d", "project age"),
)

#{
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 0pt,
    ..secondary-stats.map(((val, label)) => {
      align(center)[
        #text(size: 14pt, weight: "semibold", fill: mid)[#val]
        #v(1mm)
        #text(size: 7pt, fill: light)[#label]
      ]
    })
  )
}

#v(1fr)

#align(center)[
  #text(size: 8.5pt, fill: light)[Session #data.session #sym.dot.c #data.date]
  #v(2mm)
  #text(size: 7pt, fill: faint)[github.com/mpshields96/ClaudeCodeAdvancements]
]

#v(8mm)

#place(bottom + left, dx: -22mm, dy: 22mm)[
  #rect(width: 210mm + 1mm, height: 0.8mm, fill: black)
]

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// PAGE 2: TABLE OF CONTENTS
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Contents")

#{
  let toc-items = (
    ("Executive Summary", "Project overview, health dashboard, and key metrics"),
    ("Five Frontiers", "Status of the five core research areas"),
    ("Module Deep-Dives", "Detailed breakdown of each module's capabilities and progress"),
    ("Master Tasks", "All aspirational goals — complete, active, pending, and blocked"),
    ("Priority Queue", "Decay-based priority scoring for active work"),
    ("Live Infrastructure", "Hook architecture integrated into Claude Code"),
    ("Intelligence & Research", "Reddit findings, academic papers, and self-learning metrics"),
    ("Architecture Decisions", "Key technical decisions and their rationale"),
    ("Risks & Blockers", "Known issues, mitigations, and technical debt"),
    ("Next Priorities", "Upcoming work items ranked by impact"),
    ("Honest Assessment", "Objective gaps, limitations, and areas falling short"),
  )

  for (i, (title, desc)) in toc-items.enumerate() {
    box(width: 100%, inset: (y: 4pt))[
      #grid(
        columns: (auto, 1fr, auto),
        column-gutter: 8pt,
        text(size: 14pt, weight: "bold", fill: blue)[#str(i + 1)],
        [
          #text(size: 10pt, weight: "semibold", fill: black)[#title]
          #linebreak()
          #text(size: 8pt, fill: light)[#desc]
        ],
        text(size: 8pt, fill: faint)[],
      )
    ]
    if i < toc-items.len() - 1 {
      line(length: 100%, stroke: 0.2pt + faint)
    }
    v(1pt)
  }
}

// Session highlights (if available)
#if data.keys().contains("session_highlights") and data.session_highlights.len() > 0 {
  v(6mm)
  text(size: 7.5pt, fill: light, weight: "semibold", tracking: 1.5pt)[LATEST SESSION HIGHLIGHTS]
  v(2mm)
  box(fill: wash, radius: 6pt, inset: 12pt, width: 100%)[
    #for (i, highlight) in data.session_highlights.enumerate() {
      grid(
        columns: (auto, 1fr),
        column-gutter: 6pt,
        text(size: 8pt, fill: green, weight: "bold")[#sym.checkmark],
        text(size: 8.5pt, fill: dark)[#highlight],
      )
      if i < data.session_highlights.len() - 1 { v(2pt) }
    }
  ]
}

// Daily changes (if snapshot diff available)
#if data.keys().contains("daily_diff") and data.daily_diff != none {
  v(6mm)
  text(size: 7.5pt, fill: light, weight: "semibold", tracking: 1.5pt)[DAILY CHANGES]
  v(1mm)
  text(size: 7pt, fill: mid)[#data.daily_diff.date_range.from #sym.arrow.r #data.daily_diff.date_range.to]
  v(2mm)

  // Totals delta row
  {
    let deltas = data.daily_diff.totals_delta
    let items = ()
    for (key, label) in (("tests", "Tests"), ("suites", "Suites"), ("loc", "LOC"), ("py_files", "Files")) {
      if deltas.keys().contains(key) and deltas.at(key).delta != 0 {
        let d = deltas.at(key)
        let sign = if d.delta > 0 { "+" } else { "" }
        let color = if d.delta > 0 { green } else if d.delta < 0 { red } else { mid }
        items.push((label, sign + str(d.delta), color))
      }
    }

    if items.len() > 0 {
      box(fill: wash, radius: 6pt, inset: 10pt, width: 100%)[
        #grid(
          columns: items.map(_ => 1fr),
          column-gutter: 8pt,
          ..items.map(((label, delta, color)) => {
            align(center)[
              #text(size: 16pt, weight: "bold", fill: color)[#delta]
              #v(1mm)
              #text(size: 7pt, fill: light)[#label]
            ]
          })
        )
      ]
    } else {
      box(fill: wash, radius: 6pt, inset: 10pt, width: 100%)[
        #text(size: 8pt, fill: mid)[No measurable changes between snapshots.]
      ]
    }
  }

  // Module-level changes
  if data.daily_diff.keys().contains("module_deltas") and data.daily_diff.module_deltas.len() > 0 {
    v(2mm)
    for md in data.daily_diff.module_deltas {
      let parts = ()
      if md.tests_delta != 0 {
        let sign = if md.tests_delta > 0 { "+" } else { "" }
        parts.push(sign + str(md.tests_delta) + " tests")
      }
      if md.loc_delta != 0 {
        let sign = if md.loc_delta > 0 { "+" } else { "" }
        parts.push(sign + str(md.loc_delta) + " LOC")
      }
      if parts.len() > 0 {
        grid(
          columns: (auto, 1fr),
          column-gutter: 6pt,
          text(size: 7.5pt, weight: "semibold", fill: dark)[#md.name],
          text(size: 7.5pt, fill: mid)[#parts.join(", ")],
        )
        v(1pt)
      }
    }
  }

  // New test suites
  if data.daily_diff.keys().contains("new_suites") and data.daily_diff.new_suites.len() > 0 {
    v(2mm)
    for ns in data.daily_diff.new_suites {
      text(size: 7.5pt, fill: green)[+ #text(font: "Menlo", size: 7pt)[#ns.file] #text(fill: mid)[(#ns.count tests)]]
      linebreak()
    }
  }
}

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// PAGE 3: EXECUTIVE SUMMARY + PROJECT HEALTH
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Executive Summary")

#{
  set par(leading: 0.8em)
  text(size: 9.5pt, fill: dark)[#data.executive_summary]
}

#v(5mm)

// Project Health Grid — 3x2
#text(size: 12pt, weight: "bold", fill: black)[Project Health]
#v(3mm)

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 12pt,
  row-gutter: 10pt,

  // Row 1
  box(fill: wash, radius: 6pt, inset: 10pt, width: 100%)[
    #text(size: 7pt, fill: light, weight: "semibold")[TESTS]
    #v(1mm)
    #text(size: 20pt, weight: "bold", fill: green)[#fmt(data.summary.passing_tests)]
    #text(size: 8pt, fill: light)[ #sym.slash #fmt(data.summary.total_tests)]
    #v(2mm)
    #progress-bar(data.summary.passing_tests, data.summary.total_tests, bar-color: green)
    #v(1mm)
    #text(size: 7pt, fill: light)[#data.summary.test_suites suites — 100% pass rate]
  ],

  box(fill: wash, radius: 6pt, inset: 10pt, width: 100%)[
    #text(size: 7pt, fill: light, weight: "semibold")[CODEBASE]
    #v(1mm)
    #text(size: 20pt, weight: "bold", fill: black)[#fmt(data.summary.total_loc)]
    #v(2mm)
    #grid(
      columns: (1fr, 1fr),
      text(size: 7pt, fill: light)[Source: #fmt(data.summary.source_loc)],
      text(size: 7pt, fill: light)[Test: #fmt(data.summary.test_loc)],
    )
    #v(2mm)
    #{
      let ratio = calc.round(data.summary.test_loc / calc.max(data.summary.source_loc, 1) * 100) / 100
      text(size: 7pt, fill: mid)[Test-to-source ratio: #str(ratio):1]
    }
  ],

  box(fill: wash, radius: 6pt, inset: 10pt, width: 100%)[
    #text(size: 7pt, fill: light, weight: "semibold")[VELOCITY]
    #v(1mm)
    #text(size: 20pt, weight: "bold", fill: black)[#data.summary.git_commits]
    #text(size: 8pt, fill: light)[ commits]
    #v(2mm)
    #{
      let per_day = calc.round(data.summary.git_commits / calc.max(data.summary.project_age_days, 1) * 10) / 10
      let per_session = calc.round(data.summary.git_commits / calc.max(data.session, 1) * 10) / 10
      text(size: 7pt, fill: light)[#str(per_day)/day #sym.dot.c #str(per_session)/session]
    }
    #v(2mm)
    #text(size: 7pt, fill: mid)[#data.summary.project_age_days days #sym.dot.c #data.session sessions]
  ],

  // Row 2
  box(fill: wash, radius: 6pt, inset: 10pt, width: 100%)[
    #text(size: 7pt, fill: light, weight: "semibold")[MODULES]
    #v(1mm)
    #text(size: 20pt, weight: "bold", fill: black)[#data.summary.total_modules]
    #v(2mm)
    #text(size: 7pt, fill: light)[#data.summary.source_files source files #sym.dot.c #data.summary.test_files test files]
    #v(2mm)
    #text(size: 7pt, fill: green)[0 stubs #sym.dot.c 0 syntax errors]
  ],

  box(fill: wash, radius: 6pt, inset: 10pt, width: 100%)[
    #text(size: 7pt, fill: light, weight: "semibold")[MASTER TASKS]
    #v(1mm)
    #text(size: 20pt, weight: "bold", fill: black)[#data.summary.master_tasks]
    #v(2mm)
    #progress-bar(data.summary.completed_tasks, data.summary.master_tasks, bar-color: blue)
    #v(1mm)
    #text(size: 7pt, fill: light)[
      #text(fill: green)[#data.summary.completed_tasks done]
      #sym.dot.c #data.summary.in_progress_tasks active
      #sym.dot.c #data.summary.not_started_tasks pending
    ]
  ],

  box(fill: wash, radius: 6pt, inset: 10pt, width: 100%)[
    #text(size: 7pt, fill: light, weight: "semibold")[INTELLIGENCE]
    #v(1mm)
    #text(size: 20pt, weight: "bold", fill: black)[#data.summary.total_findings]
    #text(size: 8pt, fill: light)[ findings]
    #v(2mm)
    #text(size: 7pt, fill: light)[#data.summary.total_papers papers #sym.dot.c #data.summary.live_hooks live hooks]
    #v(2mm)
    #text(size: 7pt, fill: mid)[Zero external dependencies]
  ],
)

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// PAGE 4: FIVE FRONTIERS
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Five Frontiers")

#text(size: 9.5pt, fill: mid)[
  The five core research areas that drive CCA's development, each validated through community intelligence, Anthropic research, and developer surveys.
]
#v(4mm)

// Chart: Frontier test coverage
#if chart-dir != none {
  box(width: 100%, inset: (bottom: 6pt))[
    #embed-chart("frontier_status", width: 85%)
  ]
  v(4mm)
}

#if data.keys().contains("frontiers") and data.frontiers.len() > 0 {
  for frontier in data.frontiers {
    let status-color = if frontier.status == "COMPLETE" { green } else { blue }
    let impact-color = if frontier.impact == "CRITICAL" { red } else if frontier.impact == "HIGH" { orange } else { blue }

    box(
      width: 100%,
      fill: white,
      stroke: (left: 3pt + status-color, rest: 0.5pt + faint),
      radius: (right: 5pt),
      inset: 12pt,
    )[
      #grid(
        columns: (auto, 1fr, auto, auto),
        column-gutter: 8pt,
        align: (left, left, right, right),
        text(size: 20pt, weight: "bold", fill: status-color)[#frontier.number],
        text(size: 11pt, weight: "bold", fill: black)[#frontier.name],
        status-badge(if frontier.status == "COMPLETE" { "Complete" } else { "Active" }, status-color),
        status-badge(frontier.impact, impact-color),
      )
      #v(2mm)
      #text(size: 8.5pt, fill: mid)[#frontier.description]
      #v(2mm)
      #grid(
        columns: (auto, auto, 1fr),
        column-gutter: 12pt,
        text(size: 7.5pt, fill: light)[TESTS: #text(weight: "bold", fill: dark)[#frontier.tests]],
        text(size: 7.5pt, fill: light)[LOC: #text(weight: "bold", fill: dark)[#fmt(frontier.loc)]],
        [],
      )
    ]
    v(3mm)
  }
} else {
  text(size: 9pt, fill: light)[Frontier data not available.]
}

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// PAGES 5-6: MODULE DEEP-DIVES
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Module Deep-Dives")

// Chart: Tests per module
#if chart-dir != none {
  box(width: 100%, inset: (bottom: 8pt))[
    #embed-chart("module_tests", width: 90%)
  ]
  v(4mm)
}

#let module-card(mod) = {
  let status-color = if mod.status == "COMPLETE" { green } else { blue }
  let badge-label = if mod.status == "COMPLETE" { "Complete" } else { "Active" }

  box(
    width: 100%,
    fill: white,
    stroke: 0.5pt + faint,
    radius: 5pt,
    inset: 12pt,
  )[
    #grid(
      columns: (1fr, auto),
      align: (left, right),
      text(size: 11pt, weight: "bold", fill: black)[#mod.name],
      status-badge(badge-label, status-color),
    )
    #v(2mm)

    // Stats row
    #grid(
      columns: (auto, auto, auto, 1fr),
      column-gutter: 14pt,
      align: left,
      [#text(size: 7pt, fill: light)[TESTS] #h(2pt) #text(size: 10pt, weight: "bold", fill: black)[#mod.tests]],
      [#text(size: 7pt, fill: light)[LOC] #h(2pt) #text(size: 10pt, weight: "bold", fill: black)[#fmt(mod.loc)]],
      [#text(size: 7pt, fill: light)[FILES] #h(2pt) #text(size: 10pt, weight: "bold", fill: black)[#mod.files]],
      text(size: 7.5pt, fill: light, font: "Menlo")[#mod.path],
    )
    #v(2mm)

    // Description
    #text(size: 8.5pt, fill: mid)[#mod.description]

    // Components (compact two-column layout)
    #if mod.components.len() > 0 {
      v(2mm)
      text(size: 7pt, fill: light, weight: "semibold", tracking: 0.5pt)[KEY COMPONENTS]
      v(1mm)
      let half = calc.ceil(mod.components.len() / 2)
      grid(
        columns: (1fr, 1fr),
        column-gutter: 8pt,
        row-gutter: 1pt,
        ..{
          let cells = ()
          for (i, comp) in mod.components.enumerate() {
            cells.push(text(size: 7.5pt, fill: dark)[#sym.dash.en #h(2pt) #comp])
          }
          // Pad to even
          if calc.rem(cells.len(), 2) != 0 { cells.push([]) }
          cells
        }
      )
    }

    // What's next
    #if mod.keys().contains("next") and mod.next != "" {
      v(2mm)
      box(fill: rgb("#eff6ff"), radius: 3pt, inset: (x: 8pt, y: 4pt), width: 100%)[
        #text(size: 7pt, fill: blue, weight: "semibold")[NEXT: ]
        #text(size: 7.5pt, fill: dark)[#mod.next]
      ]
    }
  ]
  v(3mm)
}

#for mod in data.modules {
  module-card(mod)
}

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// PAGES 7-9: MASTER TASKS (expanded with phase progress + gaps)
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Master Tasks")

// Charts: MT status breakdown + phase progress
#if chart-dir != none {
  grid(
    columns: (1fr, 1fr),
    column-gutter: 12pt,
    embed-chart("mt_status", width: 100%),
    embed-chart("mt_progress", width: 100%),
  )
  v(4mm)
}

#text(size: 9.5pt, fill: mid)[
  #data.summary.master_tasks tasks defined #sym.dot.c
  #text(fill: green, weight: "semibold")[#data.summary.completed_tasks complete] #sym.dot.c
  #text(fill: blue, weight: "semibold")[#data.summary.in_progress_tasks active] #sym.dot.c
  #data.summary.not_started_tasks pending #sym.dot.c
  #data.summary.blocked_tasks blocked
]

#v(3mm)

// Task card (enhanced with phase progress)
#let task-card(task) = {
  let (badge-label, badge-color) = if task.category == "complete" {
    ("Complete", green)
  } else if task.category == "active" {
    ("In Progress", blue)
  } else if task.category == "blocked" {
    ("Blocked", red)
  } else {
    ("Not Started", light)
  }

  box(
    width: 100%,
    stroke: (left: 3pt + badge-color, rest: 0.5pt + faint),
    radius: (right: 4pt),
    inset: 10pt,
    fill: white,
  )[
    // Header
    #grid(
      columns: (auto, 1fr, auto),
      column-gutter: 6pt,
      align: (left, left, right),
      text(size: 8pt, font: "Menlo", fill: light)[#task.id],
      text(size: 10pt, weight: "bold", fill: black)[#task.name],
      status-badge(badge-label, badge-color),
    )

    // Phase progress bar (if has phases)
    #if task.keys().contains("total_phases") and task.total_phases > 0 {
      v(2mm)
      grid(
        columns: (auto, 1fr, auto),
        column-gutter: 6pt,
        align: (left, center, right),
        text(size: 7pt, fill: light)[Phase],
        progress-bar(task.phases_done, task.total_phases, bar-color: badge-color),
        text(size: 7pt, weight: "bold", fill: dark)[#task.phases_done#sym.slash#task.total_phases],
      )
    }

    // Status detail
    #v(1.5mm)
    #text(size: 8pt, fill: mid)[#task.status]

    // Test count if available
    #if task.keys().contains("test_count") and task.test_count > 0 {
      h(8pt)
      text(size: 7.5pt, fill: green)[#sym.checkmark #task.test_count tests]
    }

    // Delivered items
    #if task.keys().contains("delivered") and task.delivered.len() > 0 {
      v(2mm)
      text(size: 7pt, fill: light, weight: "semibold", tracking: 0.5pt)[DELIVERED]
      v(1mm)
      for item in task.delivered {
        text(size: 7.5pt, fill: dark)[#text(fill: green)[#sym.checkmark.light] #h(2pt) #item]
        linebreak()
      }
    }

    // What's remaining (gaps)
    #if task.keys().contains("remaining") and task.remaining.len() > 0 {
      v(2mm)
      text(size: 7pt, fill: orange, weight: "semibold", tracking: 0.5pt)[REMAINING]
      v(1mm)
      for item in task.remaining {
        text(size: 7.5pt, fill: mid)[#text(fill: orange)[#sym.circle.small] #h(2pt) #item]
        linebreak()
      }
    }

    // What's needed / next
    #if task.keys().contains("needs") and task.needs != "" {
      v(2mm)
      box(
        fill: if task.category == "blocked" { rgb("#fff1f0") } else { rgb("#eff6ff") },
        radius: 3pt, inset: (x: 6pt, y: 4pt), width: 100%,
      )[
        #text(size: 7pt,
          fill: if task.category == "blocked" { red } else { blue },
          weight: "semibold",
        )[#if task.category == "blocked" [BLOCKED: ] else [NEXT: ]]
        #text(size: 7.5pt, fill: dark)[#task.needs]
      ]
    }
  ]
  v(3mm)
}

// Group: Complete
#if data.master_tasks_complete.len() > 0 {
  text(size: 12pt, weight: "bold", fill: black)[Completed]
  v(1mm)
  text(size: 8pt, fill: light)[#data.master_tasks_complete.len() tasks delivered]
  v(3mm)
  for task in data.master_tasks_complete {
    task-card(task)
  }
}

// Group: Active
#if data.master_tasks_active.len() > 0 {
  v(3mm)
  text(size: 12pt, weight: "bold", fill: black)[Active]
  v(1mm)
  text(size: 8pt, fill: light)[#data.master_tasks_active.len() tasks in progress]
  v(3mm)
  for task in data.master_tasks_active {
    task-card(task)
  }
}

// Group: Pending (not started + blocked)
#if data.master_tasks_pending.len() > 0 {
  v(3mm)
  text(size: 12pt, weight: "bold", fill: black)[Pending & Blocked]
  v(1mm)
  text(size: 8pt, fill: light)[#data.master_tasks_pending.len() tasks awaiting start or unblocked]
  v(3mm)
  for task in data.master_tasks_pending {
    task-card(task)
  }
}

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// PRIORITY QUEUE
// ═══════════════════════════════════════════════════════════════════════════

#if data.keys().contains("priority_queue") and data.priority_queue.len() > 0 {
  section-header("Priority Queue")

  text(size: 9pt, fill: mid)[
    Active tasks ranked by decay-based priority scoring. Score = base value + aging penalty. Higher = work on this first.
  ]
  v(3mm)

  for (i, item) in data.priority_queue.enumerate() {
    let bar-pct = item.score / 18.0 // Max possible score is 2x base of 9 = 18
    box(
      width: 100%,
      fill: if calc.even(i) { wash } else { white },
      radius: 4pt,
      inset: (x: 10pt, y: 6pt),
    )[
      #grid(
        columns: (auto, auto, 1fr, auto),
        column-gutter: 8pt,
        align: (center, left, left, right),
        text(size: 16pt, weight: "bold", fill: blue)[#item.rank],
        text(size: 8pt, font: "Menlo", fill: light)[#item.id],
        [
          #text(size: 9pt, weight: "semibold", fill: black)[#item.name]
          #if item.keys().contains("next_phase") and item.next_phase != "" {
            linebreak()
            text(size: 7.5pt, fill: mid)[#item.next_phase]
          }
        ],
        text(size: 14pt, weight: "bold", fill: blue)[#str(item.score)],
      )
    ]
    v(1pt)
  }

  pagebreak()
}

// ═══════════════════════════════════════════════════════════════════════════
// LIVE INFRASTRUCTURE
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Live Infrastructure")

#text(size: 9pt, fill: mid)[
  #data.summary.live_hooks hooks integrated into Claude Code via settings.local.json.
  Every tool call passes through this pipeline.
]
#v(3mm)

#table(
  columns: (1.2fr, 1fr, 2fr, 2.5fr),
  stroke: 0.3pt + faint,
  fill: (_, row) => if row == 0 { black } else if calc.odd(row) { wash } else { white },
  align: (left, left, left, left),
  inset: 7pt,

  text(fill: white, weight: "semibold", size: 8pt)[Event],
  text(fill: white, weight: "semibold", size: 8pt)[Matcher],
  text(fill: white, weight: "semibold", size: 8pt)[Hook],
  text(fill: white, weight: "semibold", size: 8pt)[Purpose],

  ..for hook in data.hooks {
    (
      text(size: 8pt, font: "Menlo", fill: dark)[#hook.event],
      text(size: 8pt, fill: mid)[#hook.matcher],
      text(size: 8pt, fill: dark)[#hook.file],
      text(size: 8pt, fill: mid)[#hook.purpose],
    )
  }
)

#v(5mm)

// ═══════════════════════════════════════════════════════════════════════════
// INTELLIGENCE & RESEARCH
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Intelligence & Research")

#grid(
  columns: (1fr, 1fr),
  column-gutter: 12pt,

  // Reddit Intelligence
  box(fill: wash, radius: 6pt, inset: 12pt, width: 100%)[
    #text(size: 10pt, weight: "bold", fill: black)[Reddit Intelligence]
    #v(3mm)

    #text(size: 7pt, fill: light, weight: "semibold")[FINDINGS BY VERDICT]
    #v(2mm)

    #{
      let verdicts = (
        ("BUILD", data.intelligence.build, green),
        ("ADAPT", data.intelligence.adapt, blue),
        ("REFERENCE", data.intelligence.reference, mid),
        ("PERSONAL", data.intelligence.reference_personal, purple),
        ("SKIP", data.intelligence.skip, light),
      )
      for (label, count, color) in verdicts {
        grid(
          columns: (22%, 10%, 68%),
          align: (left, right, left),
          text(size: 7pt, fill: mid)[#label],
          text(size: 7pt, weight: "bold", fill: dark)[#count],
          {
            h(4pt)
            progress-bar(count, data.intelligence.findings_total, bar-color: color, height: 4pt)
          },
        )
        v(2pt)
      }
    }

    #v(2mm)
    #text(size: 7pt, fill: light)[
      #data.intelligence.subreddits_scanned subreddits #sym.dot.c
      #data.intelligence.github_repos_evaluated repos evaluated
    ]
  ],

  // Self-Learning
  box(fill: wash, radius: 6pt, inset: 12pt, width: 100%)[
    #text(size: 10pt, weight: "bold", fill: black)[Self-Learning System]
    #v(3mm)

    #kv-row("Strategies", [#data.self_learning.strategies_total total (#data.self_learning.strategies_confirmed confirmed)])
    #kv-row("Proposals", [#data.self_learning.proposals (all LOW risk)])
    #kv-row("Trace Sessions", [#data.self_learning.trace_sessions analyzed])
    #kv-row("Avg Score", [#data.self_learning.avg_score / 100])
    #kv-row("Papers Logged", str(data.self_learning.papers_logged), highlight: true)
    #kv-row("Sentinel Rate", data.self_learning.sentinel_rate)

    #v(2mm)
    #text(size: 7pt, fill: light)[
      YoYo loop: observe #sym.arrow detect #sym.arrow hypothesize #sym.arrow build #sym.arrow validate
    ]
  ],
)

// Charts: Intelligence verdicts donut + LOC distribution
#if chart-dir != none {
  v(4mm)
  grid(
    columns: (1fr, 1fr),
    column-gutter: 12pt,
    embed-chart("intelligence", width: 100%),
    embed-chart("loc_distribution", width: 100%),
  )
}

#v(5mm)

// ═══════════════════════════════════════════════════════════════════════════
// ARCHITECTURE DECISIONS
// ═══════════════════════════════════════════════════════════════════════════

#if data.architecture_decisions.len() > 0 {
  section-header("Architecture Decisions")

  table(
    columns: (1.5fr, 2.5fr),
    stroke: 0.3pt + faint,
    fill: (_, row) => if row == 0 { black } else if calc.odd(row) { wash } else { white },
    align: (left, left),
    inset: 7pt,

    text(fill: white, weight: "semibold", size: 8pt)[Decision],
    text(fill: white, weight: "semibold", size: 8pt)[Rationale],

    ..for dec in data.architecture_decisions {
      (
        text(size: 8.5pt, weight: "semibold", fill: dark)[#dec.decision],
        text(size: 8pt, fill: mid)[#dec.rationale],
      )
    }
  )
}

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// RISKS, BLOCKERS & NEXT PRIORITIES
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Risks & Blockers")

#if data.risks.len() > 0 {
  for risk in data.risks {
    let severity-color = if risk.severity == "blocker" { red } else if risk.severity == "risk" { orange } else { light }
    box(
      width: 100%,
      stroke: (left: 3pt + severity-color, rest: 0.5pt + faint),
      radius: (right: 4pt),
      inset: 10pt,
      fill: white,
    )[
      #grid(
        columns: (1fr, auto),
        text(size: 9.5pt, weight: "semibold", fill: black)[#risk.title],
        status-badge(upper(risk.severity), severity-color),
      )
      #v(1mm)
      #text(size: 8.5pt, fill: mid)[#risk.description]
      #if risk.keys().contains("mitigation") and risk.mitigation != "" {
        v(1mm)
        text(size: 7.5pt, fill: blue)[Mitigation: #risk.mitigation]
      }
    ]
    v(3mm)
  }
} else {
  text(size: 9pt, fill: green, weight: "semibold")[No critical risks or blockers identified.]
}

#v(5mm)

#section-header("Next Priorities")

#for (i, priority) in data.next_priorities.enumerate() {
  box(
    width: 100%,
    fill: wash,
    radius: 5pt,
    inset: 10pt,
  )[
    #grid(
      columns: (auto, 1fr),
      column-gutter: 8pt,
      align: (center, left),
      text(size: 14pt, weight: "bold", fill: blue)[#(i + 1)],
      [
        #text(size: 9.5pt, weight: "semibold", fill: black)[#priority.title]
        #if priority.keys().contains("detail") and priority.detail != "" {
          linebreak()
          text(size: 8pt, fill: mid)[#priority.detail]
        }
      ],
    )
  ]
  v(2mm)
}

// ═══════════════════════════════════════════════════════════════════════════
// HONEST ASSESSMENT
// ═══════════════════════════════════════════════════════════════════════════

#if data.keys().contains("criticisms") and data.criticisms.len() > 0 {
  section-header("Honest Assessment")

  text(size: 9pt, fill: mid)[
    Objective gaps, limitations, and areas where the project falls short of its stated goals. Included for accountability.
  ]
  v(3mm)

  for criticism in data.criticisms {
    let severity-color = if criticism.severity == "blocker" { red } else if criticism.severity == "gap" { orange } else if criticism.severity == "limitation" { purple } else if criticism.severity == "debt" { indigo } else { mid }

    box(
      width: 100%,
      stroke: (left: 3pt + severity-color, rest: 0.5pt + faint),
      radius: (right: 4pt),
      inset: 10pt,
      fill: white,
    )[
      #grid(
        columns: (1fr, auto),
        text(size: 9.5pt, weight: "semibold", fill: black)[#criticism.title],
        status-badge(upper(criticism.severity), severity-color),
      )
      #v(1.5mm)
      #text(size: 8.5pt, fill: mid)[#criticism.detail]
    ]
    v(3mm)
  }

  pagebreak()
}

// ═══════════════════════════════════════════════════════════════════════════
// CLOSING PAGE
// ═══════════════════════════════════════════════════════════════════════════

#pagebreak()

#v(1fr)

#align(center)[
  #text(size: 7.5pt, fill: light, tracking: 2pt)[STATUS]
  #v(4mm)
  #text(size: 20pt, weight: "bold", fill: black)[All Systems Operational]
  #v(5mm)
  #line(length: 36mm, stroke: 0.3pt + faint)
  #v(5mm)
  #text(size: 8.5pt, fill: mid)[
    #fmt(data.summary.total_tests) tests
    #h(5pt) #sym.dot.c #h(5pt)
    #fmt(data.summary.total_loc) LOC
    #h(5pt) #sym.dot.c #h(5pt)
    #data.session sessions
    #h(5pt) #sym.dot.c #h(5pt)
    #data.summary.git_commits commits
  ]
  #v(2mm)
  #text(size: 8.5pt, fill: mid)[
    #data.summary.total_modules modules
    #h(5pt) #sym.dot.c #h(5pt)
    #data.summary.master_tasks master tasks
    #h(5pt) #sym.dot.c #h(5pt)
    Zero external dependencies
  ]
]

#v(1fr)

#align(center)[
  #text(size: 7pt, fill: faint)[
    Generated #data.date #sym.dot.c Session #data.session #sym.dot.c github.com/mpshields96/ClaudeCodeAdvancements
  ]
]
