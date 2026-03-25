// CCA Comprehensive Status Report — Apple-Inspired Design v3
// Visual upgrade: accent bars, improved data density, growth callouts
// Usage: typst compile --root / --input data=/path/to/report.json cca-report.typ output.pdf

// ─── Color Palette (synced with design-guide.md + chart_generator.py) ──────
#let black = rgb("#1a1a2e")
#let dark = rgb("#3a3a3c")
#let mid = rgb("#636366")
#let light = rgb("#6b7280")
#let faint = rgb("#e5e7eb")
#let wash = rgb("#f8f9fa")
#let white = rgb("#ffffff")
#let blue = rgb("#0f3460")
#let green = rgb("#16c79a")
#let orange = rgb("#f59e0b")
#let red = rgb("#e94560")
#let teal = rgb("#5ac8fa")
#let indigo = rgb("#0f3460")

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
    self_learning: (principles_total: 65, principles_avg_score: 0.50, sentinel_rate: "0%", journal_sessions: 105, journal_wins: 72, journal_pains: 53, papers_logged: 21, research_deliveries: 0, research_implemented: 0, research_profitable: 0, research_profit_cents: 0),
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

#let section-header(title, accent: blue, lbl: none) = {
  v(5mm)
  // Thin accent bar at top for visual rhythm
  box(width: 28pt, height: 2.5pt, fill: accent, radius: 1pt)
  v(2mm)
  text(size: 7.5pt, fill: light, weight: "semibold", tracking: 1.5pt)[#upper(title)]
  v(1mm)
  if lbl != none [
    #text(size: 17pt, weight: "bold", fill: black)[#title] #label(lbl)
  ] else {
    text(size: 17pt, weight: "bold", fill: black)[#title]
  }
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

// Top accent: thin black bar + blue accent stripe
#place(top + left, dx: -22mm, dy: -24mm)[
  #rect(width: 210mm + 1mm, height: 0.8mm, fill: black)
]
#place(top + left, dx: -22mm, dy: -24mm + 0.8mm)[
  #rect(width: 210mm + 1mm, height: 2.5pt, fill: blue)
]

#v(48mm)

#align(center)[
  // Overline label with accent dot
  #box(inset: (x: 8pt, y: 3pt))[
    #text(size: 8pt, fill: light, tracking: 2.5pt, weight: "semibold")[PROJECT STATUS REPORT]
  ]
  #v(6mm)
  #text(size: 32pt, weight: "bold", fill: black, tracking: -0.5pt)[ClaudeCode Advancements]
  #v(8mm)
  // Accent-colored divider instead of gray
  #line(length: 36mm, stroke: 1pt + blue)
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

// Bottom accent: matching blue stripe + black bar
#place(bottom + left, dx: -22mm, dy: 22mm)[
  #rect(width: 210mm + 1mm, height: 2.5pt, fill: blue)
]
#place(bottom + left, dx: -22mm, dy: 22mm + 2.5pt)[
  #rect(width: 210mm + 1mm, height: 0.8mm, fill: black)
]

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// PAGE 2: TABLE OF CONTENTS
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Contents", accent: black)

#{
  let toc-items = (
    ("Executive Summary", "Project overview, health dashboard, and key metrics", <sec-exec>),
    ("Five Frontiers", "Status of the five core research areas", <sec-frontiers>),
    ("Module Deep-Dives", "Detailed breakdown of each module's capabilities and progress", <sec-modules>),
    ("Master Tasks", "All aspirational goals — complete, active, pending, and blocked", <sec-tasks>),
    ("Priority Queue", "Decay-based priority scoring for active work", <sec-priority>),
    ("Live Infrastructure", "Hook architecture integrated into Claude Code", <sec-hooks>),
    ("Intelligence & Research", "Reddit findings, academic papers, and self-learning metrics", <sec-intel>),
    ("Architecture Decisions", "Key technical decisions and their rationale", <sec-arch>),
    ("Risks & Blockers", "Known issues, mitigations, and technical debt", <sec-risks>),
    ("Next Priorities", "Upcoming work items ranked by impact", <sec-next>),
    ("Honest Assessment", "Objective gaps, limitations, and areas falling short", <sec-honest>),
  )

  for (i, (title, desc, lbl)) in toc-items.enumerate() {
    box(width: 100%, inset: (y: 4pt))[
      #grid(
        columns: (auto, 1fr, auto),
        column-gutter: 8pt,
        text(size: 14pt, weight: "bold", fill: blue)[#str(i + 1)],
        [
          #link(lbl)[#text(size: 10pt, weight: "semibold", fill: black)[#title]]
          #linebreak()
          #text(size: 8pt, fill: light)[#desc]
        ],
        context {
          let loc = query(lbl)
          if loc.len() > 0 {
            let pg = counter(page).at(loc.first().location()).first()
            text(size: 9pt, fill: mid, weight: "semibold")[#str(pg)]
          }
        },
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

#section-header("Executive Summary", accent: green, lbl: "sec-exec")

#{
  set par(leading: 0.8em)
  text(size: 9.5pt, fill: dark)[#data.executive_summary]
}

// ── Since Last Report (cross-report diff) ──────────────────────────────────
#if data.keys().contains("report_diff") and data.report_diff != none {
  v(4mm)
  box(
    width: 100%,
    fill: rgb("#f0f7ff"),
    stroke: (left: 3pt + blue, rest: 0.5pt + faint),
    radius: (right: 6pt),
    inset: 12pt,
  )[
    #{
      text(size: 7.5pt, fill: blue, weight: "semibold", tracking: 1pt)[SINCE LAST REPORT]
      if data.report_diff.keys().contains("sessions") and data.report_diff.sessions != none {
        text(size: 7pt, fill: light)[ — Session ]
        text(size: 7pt, fill: light)[#str(data.report_diff.sessions.old)]
        text(size: 7pt, fill: light)[ → ]
        text(size: 7pt, fill: light)[#str(data.report_diff.sessions.new)]
      }
      v(3mm)
    }

    // Summary deltas row
    #{
      if data.report_diff.keys().contains("summary_changes") {
        let changes = data.report_diff.summary_changes
        let items = ()
        for (key, label) in (
          ("total_tests", "Tests"),
          ("total_loc", "LOC"),
          ("git_commits", "Commits"),
          ("completed_tasks", "Completed MTs"),
          ("total_findings", "Findings"),
          ("total_delivered", "Delivered"),
        ) {
          if changes.keys().contains(key) {
            let entry = changes.at(key)
            if entry.delta != 0 {
              let sign = if entry.delta > 0 { "+" } else { "" }
              let color = if entry.delta > 0 { green } else { red }
              items.push((label, sign + str(entry.delta), color))
            }
          }
        }

        if items.len() > 0 {
          grid(
            columns: items.map(_ => 1fr),
            column-gutter: 6pt,
            ..items.map(((label, delta, color)) => {
              align(center)[
                #text(size: 18pt, weight: "bold", fill: color)[#delta]
                #v(1mm)
                #text(size: 7pt, fill: light)[#label]
              ]
            })
          )
        }
      }

      // MT transitions
      if data.report_diff.keys().contains("mt_changes") {
        let mtc = data.report_diff.mt_changes
        if mtc.keys().contains("newly_completed") and mtc.newly_completed.len() > 0 {
          v(3mm)
          text(size: 7.5pt, fill: green, weight: "semibold")[Newly Completed:]
          for mt in mtc.newly_completed {
            text(size: 8pt, fill: dark)[ #mt.id — #mt.name]
            linebreak()
          }
        }
      }

      // Kalshi P&L change
      if data.report_diff.keys().contains("kalshi_changes") and data.report_diff.kalshi_changes != none {
        let kc = data.report_diff.kalshi_changes
        if kc.keys().contains("pnl_delta_usd") and kc.pnl_delta_usd != 0 {
          v(2mm)
          let sign = if kc.pnl_delta_usd > 0 { "+" } else { "" }
          let color = if kc.pnl_delta_usd > 0 { green } else { red }
          text(size: 8pt, fill: color, weight: "semibold")[Kalshi P&L: #sign\$#str(calc.round(kc.pnl_delta_usd, digits: 2))]
          if kc.keys().contains("trades_delta") and kc.trades_delta != 0 {
            text(size: 7.5pt, fill: light)[ (+#str(kc.trades_delta) trades)]
          }
        }
      }
    }
  ]
}

#v(5mm)

// Project Health Grid — 3x2
#text(size: 12pt, weight: "bold", fill: black)[Project Health]
#v(3mm)

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 12pt,
  row-gutter: 10pt,

  // Row 1 — colored top-accent cards for visual differentiation
  box(fill: wash, radius: 6pt, inset: 0pt, width: 100%, clip: true)[
    #rect(width: 100%, height: 2.5pt, fill: green)
    #pad(x: 10pt, y: 8pt)[
      #text(size: 7pt, fill: light, weight: "semibold")[TESTS]
      #v(1mm)
      #text(size: 20pt, weight: "bold", fill: green)[#fmt(data.summary.passing_tests)]
      #text(size: 8pt, fill: light)[ #sym.slash #fmt(data.summary.total_tests)]
      #v(2mm)
      #progress-bar(data.summary.passing_tests, data.summary.total_tests, bar-color: green)
      #v(1mm)
      #text(size: 7pt, fill: light)[#data.summary.test_suites suites — 100% pass rate]
    ]
  ],

  box(fill: wash, radius: 6pt, inset: 0pt, width: 100%, clip: true)[
    #rect(width: 100%, height: 2.5pt, fill: blue)
    #pad(x: 10pt, y: 8pt)[
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
    ]
  ],

  box(fill: wash, radius: 6pt, inset: 0pt, width: 100%, clip: true)[
    #rect(width: 100%, height: 2.5pt, fill: orange)
    #pad(x: 10pt, y: 8pt)[
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
    ]
  ],

  // Row 2
  box(fill: wash, radius: 6pt, inset: 0pt, width: 100%, clip: true)[
    #rect(width: 100%, height: 2.5pt, fill: teal)
    #pad(x: 10pt, y: 8pt)[
      #text(size: 7pt, fill: light, weight: "semibold")[MODULES]
      #v(1mm)
      #text(size: 20pt, weight: "bold", fill: black)[#data.summary.total_modules]
      #v(2mm)
      #text(size: 7pt, fill: light)[#data.summary.source_files source files #sym.dot.c #data.summary.test_files test files]
      #v(2mm)
      #text(size: 7pt, fill: green)[0 stubs #sym.dot.c 0 syntax errors]
    ]
  ],

  box(fill: wash, radius: 6pt, inset: 0pt, width: 100%, clip: true)[
    #rect(width: 100%, height: 2.5pt, fill: indigo)
    #pad(x: 10pt, y: 8pt)[
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
    ]
  ],

  box(fill: wash, radius: 6pt, inset: 0pt, width: 100%, clip: true)[
    #rect(width: 100%, height: 2.5pt, fill: red)
    #pad(x: 10pt, y: 8pt)[
      #text(size: 7pt, fill: light, weight: "semibold")[INTELLIGENCE]
      #v(1mm)
      #text(size: 20pt, weight: "bold", fill: black)[#data.summary.total_findings]
      #text(size: 8pt, fill: light)[ findings]
      #v(2mm)
      #text(size: 7pt, fill: light)[#data.summary.total_papers papers #sym.dot.c #data.summary.live_hooks live hooks]
      #v(2mm)
      #text(size: 7pt, fill: mid)[Zero external dependencies]
    ]
  ],
)

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// PAGE 4: FIVE FRONTIERS
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Five Frontiers", accent: blue, lbl: "sec-frontiers")

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

#pagebreak(weak: true)

// ═══════════════════════════════════════════════════════════════════════════
// MODULE DEEP-DIVES
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Module Deep-Dives", accent: teal, lbl: "sec-modules")

// Charts: Tests per module + Module size treemap
#if chart-dir != none {
  grid(
    columns: (1fr, 1fr),
    column-gutter: 12pt,
    embed-chart("module_tests", width: 100%),
    embed-chart("module_loc_treemap", width: 100%),
  )
  v(4mm)
  // Statistical charts: Test density scatter + Code composition
  grid(
    columns: (1fr, 1fr),
    column-gutter: 12pt,
    embed-chart("test_density_scatter", width: 100%),
    embed-chart("module_composition", width: 100%),
  )
  v(4mm)
  // Coverage ratio + test distribution
  grid(
    columns: (1fr, 1fr),
    column-gutter: 12pt,
    embed-chart("coverage_ratio", width: 100%),
    embed-chart("test_distribution", width: 100%),
  )
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

    // Why it matters — ELI5 blurb
    #if mod.keys().contains("why_it_matters") and mod.why_it_matters != "" {
      v(2mm)
      box(
        fill: rgb("#f8f7f4"),
        radius: 3pt, inset: (x: 6pt, y: 4pt), width: 100%,
        stroke: (left: 2pt + rgb("#d4c5a0"), rest: none),
      )[
        #text(size: 6.5pt, fill: rgb("#8b7e66"), weight: "semibold", tracking: 0.5pt)[WHY THIS MATTERS]
        #h(4pt)
        #text(size: 7.5pt, fill: rgb("#5c5344"))[#mod.why_it_matters]
      ]
    }
  ]
  v(3mm)
}

#for mod in data.modules {
  module-card(mod)
}

#pagebreak(weak: true)

// ═══════════════════════════════════════════════════════════════════════════
// MASTER TASKS
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Master Tasks", accent: indigo, lbl: "sec-tasks")

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

    // Why it matters — ELI5 blurb for quick understanding
    #if task.keys().contains("why_it_matters") and task.why_it_matters != "" {
      v(2mm)
      box(
        fill: rgb("#f8f7f4"),
        radius: 3pt, inset: (x: 6pt, y: 4pt), width: 100%,
        stroke: (left: 2pt + rgb("#d4c5a0"), rest: none),
      )[
        #text(size: 6.5pt, fill: rgb("#8b7e66"), weight: "semibold", tracking: 0.5pt)[WHY THIS MATTERS]
        #h(4pt)
        #text(size: 7.5pt, fill: rgb("#5c5344"))[#task.why_it_matters]
      ]
    }
  ]
  v(3mm)
}

// Group: Complete (condensed — one line per task to save space)
#if data.master_tasks_complete.len() > 0 {
  text(size: 12pt, weight: "bold", fill: black)[Completed]
  v(1mm)
  text(size: 8pt, fill: light)[#data.master_tasks_complete.len() tasks delivered]
  v(3mm)
  for task in data.master_tasks_complete {
    box(
      width: 100%,
      fill: wash,
      radius: 4pt,
      inset: (x: 10pt, y: 6pt),
    )[
      #grid(
        columns: (auto, 1fr, auto, auto),
        column-gutter: 8pt,
        align: (left, left, right, right),
        text(size: 8pt, font: "Menlo", fill: light)[#task.id],
        text(size: 9pt, weight: "semibold", fill: dark)[#task.name],
        if task.keys().contains("test_count") and task.test_count > 0 {
          text(size: 7.5pt, fill: green)[#sym.checkmark #task.test_count tests]
        },
        status-badge("Complete", green),
      )
    ]
    v(2pt)
  }
}

// Group: Active (condensed — compact rows with progress + status one-liner)
#if data.master_tasks_active.len() > 0 {
  v(3mm)
  text(size: 12pt, weight: "bold", fill: black)[Active]
  v(1mm)
  text(size: 8pt, fill: light)[#data.master_tasks_active.len() tasks in progress]
  v(3mm)
  for task in data.master_tasks_active {
    box(
      width: 100%,
      stroke: (left: 3pt + blue, rest: 0.5pt + faint),
      radius: (right: 4pt),
      inset: (x: 10pt, y: 7pt),
      fill: white,
    )[
      // Row 1: ID, name, badge, test count
      #grid(
        columns: (auto, 1fr, auto, auto),
        column-gutter: 6pt,
        align: (left, left, right, right),
        text(size: 8pt, font: "Menlo", fill: light)[#task.id],
        text(size: 9.5pt, weight: "bold", fill: black)[#task.name],
        if task.keys().contains("test_count") and task.test_count > 0 {
          text(size: 7.5pt, fill: green)[#sym.checkmark #task.test_count tests]
        },
        status-badge("In Progress", blue),
      )
      // Row 2: Phase progress (if has phases)
      #if task.keys().contains("total_phases") and task.total_phases > 0 {
        v(2mm)
        grid(
          columns: (auto, 1fr, auto),
          column-gutter: 6pt,
          align: (left, center, right),
          text(size: 7pt, fill: light)[Phase],
          progress-bar(task.phases_done, task.total_phases, bar-color: blue),
          text(size: 7pt, weight: "bold", fill: dark)[#task.phases_done#sym.slash#task.total_phases],
        )
      }
      // Row 3: Status one-liner + next action (if any)
      #v(1.5mm)
      #text(size: 8pt, fill: mid)[#task.status]
      #if task.keys().contains("needs") and task.needs != "" {
        h(6pt)
        text(size: 7.5pt, fill: blue, weight: "semibold")[Next: #task.needs]
      }
    ]
    v(2.5pt)
  }
}

// Group: Pending (condensed — one-line per task, similar to completed)
#if data.master_tasks_pending.len() > 0 {
  v(3mm)
  text(size: 12pt, weight: "bold", fill: black)[Pending & Blocked]
  v(1mm)
  text(size: 8pt, fill: light)[#data.master_tasks_pending.len() tasks awaiting start or unblocked]
  v(3mm)
  for task in data.master_tasks_pending {
    let (badge-label, badge-color) = if task.category == "blocked" {
      ("Blocked", red)
    } else {
      ("Not Started", light)
    }
    box(
      width: 100%,
      stroke: (left: 3pt + badge-color, rest: 0.5pt + faint),
      radius: (right: 4pt),
      inset: (x: 10pt, y: 6pt),
      fill: white,
    )[
      #grid(
        columns: (auto, 1fr, auto),
        column-gutter: 8pt,
        align: (left, left, right),
        text(size: 8pt, font: "Menlo", fill: light)[#task.id],
        text(size: 9pt, weight: "semibold", fill: dark)[#task.name],
        status-badge(badge-label, badge-color),
      )
      #if task.keys().contains("needs") and task.needs != "" {
        v(1mm)
        text(size: 7.5pt, fill: if task.category == "blocked" { red } else { mid })[
          #if task.category == "blocked" [Blocked: ] else [Needs: ]#task.needs
        ]
      }
    ]
    v(2pt)
  }
}

#pagebreak(weak: true)

// ═══════════════════════════════════════════════════════════════════════════
// PRIORITY QUEUE
// ═══════════════════════════════════════════════════════════════════════════

#if data.keys().contains("priority_queue") and data.priority_queue.len() > 0 {
  section-header("Priority Queue", accent: blue, lbl: "sec-priority")

  text(size: 9pt, fill: mid)[
    Active tasks ranked by decay-based priority scoring. Score = base value + aging penalty. Higher = work on this first.
  ]
  v(3mm)

  for (i, item) in data.priority_queue.enumerate() {
    let bar-pct = item.score / 12.0 // Max possible score ~12
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

#section-header("Live Infrastructure", accent: green, lbl: "sec-hooks")

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
#v(3mm)
// Hook distribution chart
#embed-chart("hook_coverage", width: 60%)

#v(5mm)

// ═══════════════════════════════════════════════════════════════════════════
// INTELLIGENCE & RESEARCH
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Intelligence & Research", accent: orange, lbl: "sec-intel")

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
        ("PERSONAL", data.intelligence.reference_personal, orange),
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

    // Dynamic fields with fallbacks for older JSON data
    #let sl = data.self_learning
    #if sl.keys().contains("principles_total") {
      kv-row("Principles", [#sl.principles_total active (avg score: #sl.principles_avg_score)])
      kv-row("Journal Sessions", [#sl.journal_sessions tracked])
      kv-row("Wins / Pains", [#sl.journal_wins / #sl.journal_pains])
    } else {
      // Legacy fields
      kv-row("Strategies", [#sl.strategies_total total (#sl.strategies_confirmed confirmed)])
      kv-row("Trace Sessions", [#sl.trace_sessions analyzed])
      kv-row("Avg Score", [#sl.avg_score / 100])
    }
    #kv-row("Papers Logged", str(sl.papers_logged), highlight: true)
    #kv-row("Sentinel Rate", sl.sentinel_rate)
    #if sl.keys().contains("research_deliveries") and sl.research_deliveries > 0 {
      kv-row("Research ROI", [#sl.research_deliveries deliveries, #sl.research_profitable profitable], highlight: true)
    }

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
// KALSHI FINANCIAL ANALYTICS (MT-33)
// ═══════════════════════════════════════════════════════════════════════════

#if "kalshi_analytics" in data.keys() and data.kalshi_analytics.available {
  pagebreak()
  section-header("Financial Analytics — Kalshi Bot", accent: green, lbl: "sec-kalshi")

  // Summary stats row
  let ka = data.kalshi_analytics.summary
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 8pt,
    metric("Live Trades", str(ka.total_live_trades), accent-color: blue),
    metric("Win Rate", if ka.win_rate_pct != none { str(ka.win_rate_pct) + "%" } else { "N/A" }, accent-color: green),
    metric("Total P&L", "$" + str(calc.round(ka.total_pnl_usd, digits: 2)), accent-color: if ka.total_pnl_usd >= 0 { green } else { red }),
    metric("Settled", str(ka.settled_trades), accent-color: mid),
  )

  v(4mm)

  // Charts — row 1: Cumulative P&L + Bankroll
  if chart-dir != none {
    grid(
      columns: (1fr, 1fr),
      column-gutter: 12pt,
      embed-chart("kalshi_cumulative_pnl", width: 100%),
      embed-chart("kalshi_bankroll", width: 100%),
    )

    v(4mm)

    // Charts — row 2: Strategy Win Rate + Trade Volume
    grid(
      columns: (1fr, 1fr),
      column-gutter: 12pt,
      embed-chart("kalshi_strategy_winrate", width: 100%),
      embed-chart("kalshi_trade_volume", width: 100%),
    )

    v(4mm)

    // Charts — row 3: Daily Distribution + Strategy Box Plot
    grid(
      columns: (1fr, 1fr),
      column-gutter: 12pt,
      embed-chart("kalshi_daily_pnl_histogram", width: 100%),
      embed-chart("kalshi_strategy_pnl_box", width: 100%),
    )

    v(4mm)

    // Chart — row 4: Win Rate vs Profit scatter
    embed-chart("kalshi_winrate_vs_profit", width: 60%)
  }

  v(4mm)

  // Strategy breakdown table
  if data.kalshi_analytics.strategies.len() > 0 {
    v(2mm)
    text(size: 10pt, weight: "bold", fill: dark)[Strategy Performance]
    v(2mm)
    table(
      columns: (2fr, 0.8fr, 0.8fr, 0.8fr, 1fr, 1fr),
      stroke: 0.3pt + faint,
      fill: (_, row) => if row == 0 { black } else if calc.odd(row) { wash } else { white },
      align: (left, center, center, center, center, right),
      inset: 6pt,
      text(fill: white, weight: "semibold", size: 7.5pt)[Strategy],
      text(fill: white, weight: "semibold", size: 7.5pt)[Trades],
      text(fill: white, weight: "semibold", size: 7.5pt)[Wins],
      text(fill: white, weight: "semibold", size: 7.5pt)[Win %],
      text(fill: white, weight: "semibold", size: 7.5pt)[Avg P&L],
      text(fill: white, weight: "semibold", size: 7.5pt)[Total P&L],
      ..for s in data.kalshi_analytics.strategies {
        let avg-color = if s.avg_pnl_usd >= 0 { green } else { red }
        let total-color = if s.total_pnl_usd >= 0 { green } else { red }
        (
          text(size: 8pt, weight: "semibold", fill: dark)[#s.strategy],
          text(size: 8pt, fill: mid)[#str(s.trade_count)],
          text(size: 8pt, fill: mid)[#str(s.wins)],
          text(size: 8pt, fill: mid)[#str(s.win_rate_pct)%],
          text(size: 8pt, fill: avg-color)[
            \$#str(calc.round(s.avg_pnl_usd, digits: 2))],
          text(size: 8pt, weight: "semibold", fill: total-color)[
            \$#str(calc.round(s.total_pnl_usd, digits: 2))],
        )
      }
    )
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// SELF-LEARNING INTELLIGENCE (MT-33 Phase 5)
// ═══════════════════════════════════════════════════════════════════════════

#if "learning_intelligence" in data.keys() and data.learning_intelligence.available {
  v(6mm)
  section-header("Self-Learning Intelligence", accent: indigo, lbl: "sec-selflearn")

  // Summary metrics
  let lj = data.learning_intelligence.journal
  let la = data.learning_intelligence.apf
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 8pt,
    metric("Journal Entries", str(lj.total_entries), accent-color: indigo),
    metric("Wins / Pains", str(lj.wins) + " / " + str(lj.pains), accent-color: if lj.wins >= lj.pains { green } else { orange }),
    metric("Current APF", str(la.current_apf) + "%", accent-color: blue),
    metric("Posts Reviewed", str(la.total_reviewed), accent-color: mid),
  )

  v(4mm)

  // Charts
  if chart-dir != none {
    grid(
      columns: (1fr, 1fr),
      column-gutter: 12pt,
      embed-chart("learning_event_types", width: 100%),
      embed-chart("learning_domain_distribution", width: 100%),
    )

    v(4mm)

    embed-chart("learning_apf_trend", width: 60%)
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// ARCHITECTURE DECISIONS
// ═══════════════════════════════════════════════════════════════════════════

#if data.architecture_decisions.len() > 0 {
  section-header("Architecture Decisions", accent: mid, lbl: "sec-arch")

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

#pagebreak(weak: true)

// ═══════════════════════════════════════════════════════════════════════════
// RISKS, BLOCKERS & NEXT PRIORITIES
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Risks & Blockers", accent: red, lbl: "sec-risks")

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

#section-header("Next Priorities", accent: blue, lbl: "sec-next")

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
  section-header("Honest Assessment", accent: orange, lbl: "sec-honest")

  text(size: 9pt, fill: mid)[
    Objective gaps, limitations, and areas where the project falls short of its stated goals. Included for accountability.
  ]
  v(3mm)

  for criticism in data.criticisms {
    let severity-color = if criticism.severity == "blocker" { red } else if criticism.severity == "gap" { orange } else if criticism.severity == "limitation" { mid } else if criticism.severity == "debt" { blue } else { mid }

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
}

// ═══════════════════════════════════════════════════════════════════════════
// CLOSING PAGE
// ═══════════════════════════════════════════════════════════════════════════

#pagebreak()

// Top accent bar (matching cover)
#place(top + left, dx: -22mm, dy: -24mm)[
  #rect(width: 210mm + 1mm, height: 0.8mm, fill: black)
]
#place(top + left, dx: -22mm, dy: -24mm + 0.8mm)[
  #rect(width: 210mm + 1mm, height: 2.5pt, fill: blue)
]

#v(1fr)

#align(center)[
  #text(size: 7.5pt, fill: light, tracking: 2.5pt, weight: "semibold")[STATUS]
  #v(4mm)
  #text(size: 24pt, weight: "bold", fill: black)[All Systems Operational]
  #v(6mm)
  #line(length: 36mm, stroke: 1pt + blue)
  #v(6mm)

  // Hero stat callout
  #grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 4pt,
    align(center)[
      #text(size: 22pt, weight: "bold", fill: black)[#fmt(data.summary.total_tests)]
      #v(1mm)
      #text(size: 7pt, fill: light, tracking: 0.5pt)[TESTS]
    ],
    align(center)[
      #text(size: 22pt, weight: "bold", fill: black)[#fmt(data.summary.total_loc)]
      #v(1mm)
      #text(size: 7pt, fill: light, tracking: 0.5pt)[LOC]
    ],
    align(center)[
      #text(size: 22pt, weight: "bold", fill: black)[#data.session]
      #v(1mm)
      #text(size: 7pt, fill: light, tracking: 0.5pt)[SESSIONS]
    ],
    align(center)[
      #text(size: 22pt, weight: "bold", fill: black)[#data.summary.git_commits]
      #v(1mm)
      #text(size: 7pt, fill: light, tracking: 0.5pt)[COMMITS]
    ],
  )
  #v(6mm)

  // Secondary stats
  #text(size: 8.5pt, fill: mid)[
    #data.summary.total_modules modules
    #h(5pt) #sym.dot.c #h(5pt)
    #data.summary.master_tasks master tasks
    #h(5pt) #sym.dot.c #h(5pt)
    #data.summary.test_suites test suites
    #h(5pt) #sym.dot.c #h(5pt)
    Zero external dependencies
  ]

  #v(8mm)

  // Completion stats row
  #box(fill: wash, radius: 6pt, inset: 12pt, width: 80%)[
    #grid(
      columns: (1fr, 1fr, 1fr),
      align(center)[
        #text(size: 14pt, weight: "bold", fill: green)[#data.summary.completed_tasks]
        #v(1mm)
        #text(size: 7pt, fill: light)[MTs Complete]
      ],
      align(center)[
        #text(size: 14pt, weight: "bold", fill: blue)[#data.summary.in_progress_tasks]
        #v(1mm)
        #text(size: 7pt, fill: light)[MTs Active]
      ],
      align(center)[
        #text(size: 14pt, weight: "bold", fill: black)[#data.summary.total_findings]
        #v(1mm)
        #text(size: 7pt, fill: light)[Findings]
      ],
    )
  ]
]

#v(1fr)

// Bottom accent
#place(bottom + left, dx: -22mm, dy: 22mm)[
  #rect(width: 210mm + 1mm, height: 2.5pt, fill: blue)
]
#place(bottom + left, dx: -22mm, dy: 22mm + 2.5pt)[
  #rect(width: 210mm + 1mm, height: 0.8mm, fill: black)
]

#align(center)[
  #text(size: 7pt, fill: faint)[
    Generated #data.date #sym.dot.c Session #data.session #sym.dot.c github.com/mpshields96/ClaudeCodeAdvancements
  ]
]
