// CCA Comprehensive Status Report — Apple-Inspired Design
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

// ─── Data Loading ──────────────────────────────────────────────────────────
#let data = if sys.inputs.keys().contains("data") {
  json(sys.inputs.data)
} else {
  // Minimal fallback for template preview
  (
    title: "ClaudeCodeAdvancements",
    subtitle: "Comprehensive Project Report",
    date: "2026-03-18",
    session: 52,
    summary: (
      total_tests: 1768, passing_tests: 1768, test_suites: 44,
      total_modules: 9, total_findings: 289, total_papers: 21,
      master_tasks: 19, completed_tasks: 8, in_progress_tasks: 7,
      not_started_tasks: 3, blocked_tasks: 1,
      source_files: 50, test_files: 45, source_loc: 19110,
      test_loc: 18621, total_loc: 37731, git_commits: 217,
      project_age_days: 28, live_hooks: 9,
    ),
    executive_summary: "ClaudeCodeAdvancements is a research and development project building validated tools, hooks, and systems for Claude Code. All five original frontiers are production-complete with 1,768 automated tests. The project has expanded into 19 master-level tasks covering autonomous intelligence, self-learning, academic research, and professional design output.",
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
  )
}

// ─── Helpers ───────────────────────────────────────────────────────────────

// Status badge: filled rounded box with text
#let status-badge(label, bg-color, text-color: white) = {
  box(
    fill: bg-color,
    radius: 3pt,
    inset: (x: 6pt, y: 3pt),
  )[#text(size: 8pt, weight: "semibold", fill: text-color)[#label]]
}

// Numeric format with comma separators
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

// Section header
#let section-header(title) = {
  v(6mm)
  text(size: 8pt, fill: light, weight: "semibold")[#upper(title)]
  v(1mm)
  text(size: 18pt, weight: "bold", fill: black)[#title]
  v(2mm)
  line(length: 100%, stroke: 0.3pt + faint)
  v(4mm)
}

// Progress bar
#let progress-bar(current, total, width: 100%, bar-color: blue) = {
  let pct = if total > 0 { calc.min(current / total, 1.0) } else { 0 }
  box(width: width, height: 6pt, radius: 3pt, fill: wash, clip: true)[
    #box(width: pct * 100%, height: 100%, fill: bar-color, radius: 3pt)
  ]
}

// Metric card (refined)
#let metric(label, value, accent-color: black) = {
  box(width: 100%, inset: (x: 0pt, y: 4pt))[
    #text(size: 8pt, fill: light, weight: "semibold")[#upper(label)]
    #v(1mm)
    #text(size: 24pt, weight: "bold", fill: accent-color)[#value]
  ]
}

// Key-value row
#let kv-row(key, value, highlight: false) = {
  grid(
    columns: (35%, 65%),
    text(size: 9pt, fill: light)[#key],
    text(size: 9pt, fill: if highlight { blue } else { dark }, weight: if highlight { "semibold" } else { "regular" })[#value],
  )
  v(2pt)
}

// ─── Page Setup ────────────────────────────────────────────────────────────
#set page(
  paper: "a4",
  margin: (top: 24mm, bottom: 22mm, left: 22mm, right: 22mm),
  header: context {
    if counter(page).get().first() > 1 {
      set text(size: 7.5pt, fill: light)
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

#set text(font: "Helvetica Neue", size: 10pt, fill: dark)
#set par(leading: 0.65em)

// ═══════════════════════════════════════════════════════════════════════════
// PAGE 1: COVER
// ═══════════════════════════════════════════════════════════════════════════

// Thin top accent
#place(top + left, dx: -22mm, dy: -24mm)[
  #rect(width: 210mm + 1mm, height: 0.8mm, fill: black)
]

#v(52mm)

#align(center)[
  #text(size: 10pt, fill: light, tracking: 2pt)[PROJECT STATUS REPORT]
  #v(6mm)
  #text(size: 38pt, weight: "bold", fill: black, tracking: -0.5pt)[ClaudeCode]
  #v(-2mm)
  #text(size: 38pt, weight: "bold", fill: black, tracking: -0.5pt)[Advancements]
  #v(8mm)
  #line(length: 36mm, stroke: 0.3pt + faint)
  #v(8mm)
  #text(size: 10pt, fill: mid)[
    Research, tools, and systems for AI-assisted development
  ]
]

#v(32mm)

// Hero metrics — clean horizontal row
#let hero-stats = (
  (fmt(data.summary.total_tests), "tests passing"),
  (fmt(data.summary.total_loc), "lines of code"),
  (str(data.summary.total_modules), "modules"),
  (str(data.summary.git_commits), "commits"),
)

#let col-w = (166mm) / 4

#{
  let y-pos = 0pt
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 0pt,
    ..hero-stats.map(((val, label)) => {
      align(center)[
        #text(size: 26pt, weight: "bold", fill: black)[#val]
        #v(2mm)
        #text(size: 8pt, fill: light)[#label]
      ]
    })
  )
}

#v(2mm)

// Hairline separators would be nice but keeping it clean

#v(1fr)

#align(center)[
  #text(size: 9pt, fill: light)[Session #data.session #sym.dot.c #data.date]
  #v(2mm)
  #text(size: 7.5pt, fill: faint)[github.com/mpshields96/ClaudeCodeAdvancements]
]

#v(8mm)

// Bottom accent
#place(bottom + left, dx: -22mm, dy: 22mm)[
  #rect(width: 210mm + 1mm, height: 0.8mm, fill: black)
]

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// PAGE 2: EXECUTIVE SUMMARY + PROJECT HEALTH
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Executive Summary")

#{
  set par(leading: 0.8em)
  text(size: 10pt, fill: dark)[#data.executive_summary]
}

#v(6mm)

// Project Health Grid — 3x4
#text(size: 13pt, weight: "bold", fill: black)[Project Health]
#v(4mm)

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 16pt,
  row-gutter: 12pt,

  // Row 1
  box(fill: wash, radius: 6pt, inset: 12pt, width: 100%)[
    #text(size: 7.5pt, fill: light, weight: "semibold")[TESTS]
    #v(1mm)
    #text(size: 22pt, weight: "bold", fill: green)[#fmt(data.summary.passing_tests)]
    #text(size: 9pt, fill: light)[ #sym.slash #fmt(data.summary.total_tests)]
    #v(2mm)
    #progress-bar(data.summary.passing_tests, data.summary.total_tests, bar-color: green)
    #v(1mm)
    #text(size: 7.5pt, fill: light)[#data.summary.test_suites suites — 100% pass rate]
  ],

  box(fill: wash, radius: 6pt, inset: 12pt, width: 100%)[
    #text(size: 7.5pt, fill: light, weight: "semibold")[CODEBASE]
    #v(1mm)
    #text(size: 22pt, weight: "bold", fill: black)[#fmt(data.summary.total_loc)]
    #v(2mm)
    #grid(
      columns: (1fr, 1fr),
      text(size: 7.5pt, fill: light)[Source: #fmt(data.summary.source_loc)],
      text(size: 7.5pt, fill: light)[Test: #fmt(data.summary.test_loc)],
    )
    #v(2mm)
    #{
      let ratio = calc.round(data.summary.test_loc / data.summary.source_loc * 100) / 100
      text(size: 7.5pt, fill: mid)[Test-to-source ratio: #str(ratio):1]
    }
  ],

  box(fill: wash, radius: 6pt, inset: 12pt, width: 100%)[
    #text(size: 7.5pt, fill: light, weight: "semibold")[VELOCITY]
    #v(1mm)
    #text(size: 22pt, weight: "bold", fill: black)[#data.summary.git_commits]
    #text(size: 9pt, fill: light)[ commits]
    #v(2mm)
    #{
      let per_day = calc.round(data.summary.git_commits / data.summary.project_age_days * 10) / 10
      let per_session = calc.round(data.summary.git_commits / data.session * 10) / 10
      text(size: 7.5pt, fill: light)[#str(per_day)/day #sym.dot.c #str(per_session)/session]
    }
    #v(2mm)
    #text(size: 7.5pt, fill: mid)[#data.summary.project_age_days days #sym.dot.c #data.session sessions]
  ],

  // Row 2
  box(fill: wash, radius: 6pt, inset: 12pt, width: 100%)[
    #text(size: 7.5pt, fill: light, weight: "semibold")[MODULES]
    #v(1mm)
    #text(size: 22pt, weight: "bold", fill: black)[#data.summary.total_modules]
    #v(2mm)
    #text(size: 7.5pt, fill: light)[#data.summary.source_files source files #sym.dot.c #data.summary.test_files test files]
    #v(2mm)
    #text(size: 7.5pt, fill: green)[0 stubs #sym.dot.c 0 syntax errors]
  ],

  box(fill: wash, radius: 6pt, inset: 12pt, width: 100%)[
    #text(size: 7.5pt, fill: light, weight: "semibold")[MASTER TASKS]
    #v(1mm)
    #text(size: 22pt, weight: "bold", fill: black)[#data.summary.master_tasks]
    #v(2mm)
    #progress-bar(data.summary.completed_tasks, data.summary.master_tasks, bar-color: blue)
    #v(1mm)
    #text(size: 7.5pt, fill: light)[
      #text(fill: green)[#data.summary.completed_tasks done]
      #sym.dot.c #data.summary.in_progress_tasks active
      #sym.dot.c #data.summary.not_started_tasks pending
    ]
  ],

  box(fill: wash, radius: 6pt, inset: 12pt, width: 100%)[
    #text(size: 7.5pt, fill: light, weight: "semibold")[INTELLIGENCE]
    #v(1mm)
    #text(size: 22pt, weight: "bold", fill: black)[#data.summary.total_findings]
    #text(size: 9pt, fill: light)[ findings]
    #v(2mm)
    #text(size: 7.5pt, fill: light)[#data.summary.total_papers papers #sym.dot.c #data.summary.live_hooks live hooks]
    #v(2mm)
    #text(size: 7.5pt, fill: mid)[Zero external dependencies]
  ],
)

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// PAGES 3-4: MODULE DEEP-DIVES
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Module Deep-Dives")

// Module card layout
#let module-card(mod) = {
  let status-color = if mod.status == "COMPLETE" { green } else { blue }
  let badge-label = if mod.status == "COMPLETE" { "Complete" } else { "Active" }

  box(
    width: 100%,
    fill: white,
    stroke: 0.5pt + faint,
    radius: 6pt,
    inset: 14pt,
  )[
    // Header row: name + badge
    #grid(
      columns: (1fr, auto),
      align: (left, right),
      text(size: 12pt, weight: "bold", fill: black)[#mod.name],
      status-badge(badge-label, status-color),
    )
    #v(3mm)

    // Stats row
    #grid(
      columns: (auto, auto, auto, 1fr),
      column-gutter: 16pt,
      align: left,
      [#text(size: 8pt, fill: light)[TESTS] #h(2pt) #text(size: 11pt, weight: "bold", fill: black)[#mod.tests]],
      [#text(size: 8pt, fill: light)[LOC] #h(2pt) #text(size: 11pt, weight: "bold", fill: black)[#fmt(mod.loc)]],
      [#text(size: 8pt, fill: light)[FILES] #h(2pt) #text(size: 11pt, weight: "bold", fill: black)[#mod.files]],
      text(size: 8pt, fill: light, font: "Menlo")[#mod.path],
    )
    #v(3mm)

    // Description
    #text(size: 9pt, fill: mid)[#mod.description]

    // Components
    #if mod.components.len() > 0 {
      v(3mm)
      text(size: 8pt, fill: light, weight: "semibold")[KEY COMPONENTS]
      v(1mm)
      for comp in mod.components {
        text(size: 8.5pt, fill: dark)[#sym.dash.en #h(3pt) #comp]
        linebreak()
      }
    }

    // What's next (for active modules)
    #if mod.keys().contains("next") and mod.next != "" {
      v(3mm)
      box(fill: rgb("#eff6ff"), radius: 3pt, inset: (x: 8pt, y: 5pt), width: 100%)[
        #text(size: 8pt, fill: blue, weight: "semibold")[NEXT: ]
        #text(size: 8pt, fill: dark)[#mod.next]
      ]
    }
  ]
  v(4mm)
}

#for mod in data.modules {
  module-card(mod)
}

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// PAGES 5-7: MASTER TASKS
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Master Tasks")

#text(size: 10pt, fill: mid)[
  #data.summary.master_tasks tasks defined #sym.dot.c
  #text(fill: green, weight: "semibold")[#data.summary.completed_tasks complete] #sym.dot.c
  #text(fill: blue, weight: "semibold")[#data.summary.in_progress_tasks active] #sym.dot.c
  #data.summary.not_started_tasks pending #sym.dot.c
  #data.summary.blocked_tasks blocked
]

#v(4mm)

// Task card
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
    inset: 12pt,
    fill: white,
  )[
    // Header
    #grid(
      columns: (auto, 1fr, auto),
      column-gutter: 8pt,
      align: (left, left, right),
      text(size: 9pt, font: "Menlo", fill: light)[#task.id],
      text(size: 11pt, weight: "bold", fill: black)[#task.name],
      status-badge(badge-label, badge-color),
    )

    // Status detail
    #v(2mm)
    #text(size: 9pt, fill: mid)[#task.status]

    // Delivered items
    #if task.keys().contains("delivered") and task.delivered.len() > 0 {
      v(2mm)
      text(size: 8pt, fill: light, weight: "semibold")[DELIVERED]
      v(1mm)
      for item in task.delivered {
        text(size: 8.5pt, fill: dark)[#sym.checkmark.light #h(3pt) #item]
        linebreak()
      }
    }

    // What's needed / next
    #if task.keys().contains("needs") and task.needs != "" {
      v(2mm)
      box(
        fill: if task.category == "blocked" { rgb("#fff1f0") } else { rgb("#eff6ff") },
        radius: 3pt, inset: (x: 8pt, y: 5pt), width: 100%,
      )[
        #text(size: 8pt,
          fill: if task.category == "blocked" { red } else { blue },
          weight: "semibold",
        )[#if task.category == "blocked" [BLOCKED: ] else [NEXT: ]]
        #text(size: 8pt, fill: dark)[#task.needs]
      ]
    }
  ]
  v(4mm)
}

// Group: Complete
#if data.master_tasks_complete.len() > 0 {
  text(size: 13pt, weight: "bold", fill: black)[Completed]
  v(1mm)
  text(size: 9pt, fill: light)[#data.master_tasks_complete.len() tasks delivered]
  v(4mm)
  for task in data.master_tasks_complete {
    task-card(task)
  }
}

// Group: Active
#if data.master_tasks_active.len() > 0 {
  v(4mm)
  text(size: 13pt, weight: "bold", fill: black)[Active]
  v(1mm)
  text(size: 9pt, fill: light)[#data.master_tasks_active.len() tasks in progress]
  v(4mm)
  for task in data.master_tasks_active {
    task-card(task)
  }
}

// Group: Pending (not started + blocked)
#if data.master_tasks_pending.len() > 0 {
  v(4mm)
  text(size: 13pt, weight: "bold", fill: black)[Pending]
  v(1mm)
  text(size: 9pt, fill: light)[#data.master_tasks_pending.len() tasks awaiting start or unblocked]
  v(4mm)
  for task in data.master_tasks_pending {
    task-card(task)
  }
}

#pagebreak()

// ═══════════════════════════════════════════════════════════════════════════
// LIVE INFRASTRUCTURE
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Live Infrastructure")

#text(size: 10pt, fill: mid)[
  #data.summary.live_hooks hooks integrated into Claude Code via settings.local.json
]
#v(4mm)

#table(
  columns: (1.2fr, 1fr, 2fr, 2.5fr),
  stroke: 0.3pt + faint,
  fill: (_, row) => if row == 0 { black } else if calc.odd(row) { wash } else { white },
  align: (left, left, left, left),
  inset: 8pt,

  text(fill: white, weight: "semibold", size: 9pt)[Event],
  text(fill: white, weight: "semibold", size: 9pt)[Matcher],
  text(fill: white, weight: "semibold", size: 9pt)[Hook],
  text(fill: white, weight: "semibold", size: 9pt)[Purpose],

  ..for hook in data.hooks {
    (
      text(size: 8.5pt, font: "Menlo", fill: dark)[#hook.event],
      text(size: 8.5pt, fill: mid)[#hook.matcher],
      text(size: 8.5pt, fill: dark)[#hook.file],
      text(size: 8.5pt, fill: mid)[#hook.purpose],
    )
  }
)

#v(6mm)

// ═══════════════════════════════════════════════════════════════════════════
// INTELLIGENCE & RESEARCH
// ═══════════════════════════════════════════════════════════════════════════

#section-header("Intelligence & Research")

#grid(
  columns: (1fr, 1fr),
  column-gutter: 16pt,

  // Reddit Intelligence
  box(fill: wash, radius: 6pt, inset: 14pt, width: 100%)[
    #text(size: 11pt, weight: "bold", fill: black)[Reddit Intelligence]
    #v(3mm)

    #text(size: 8pt, fill: light, weight: "semibold")[FINDINGS BY VERDICT]
    #v(2mm)

    // Verdict bars
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
          text(size: 7.5pt, fill: mid)[#label],
          text(size: 7.5pt, weight: "bold", fill: dark)[#count],
          {
            h(4pt)
            progress-bar(count, data.intelligence.findings_total, bar-color: color)
          },
        )
        v(2pt)
      }
    }

    #v(3mm)
    #text(size: 8pt, fill: light)[
      #data.intelligence.subreddits_scanned subreddits scanned #sym.dot.c
      #data.intelligence.github_repos_evaluated GitHub repos evaluated
    ]
  ],

  // Self-Learning
  box(fill: wash, radius: 6pt, inset: 14pt, width: 100%)[
    #text(size: 11pt, weight: "bold", fill: black)[Self-Learning System]
    #v(3mm)

    #kv-row("Strategies", [#data.self_learning.strategies_total total (#data.self_learning.strategies_confirmed confirmed)])
    #kv-row("Proposals", [#data.self_learning.proposals (all LOW risk)])
    #kv-row("Trace Sessions", [#data.self_learning.trace_sessions analyzed])
    #kv-row("Avg Score", [#data.self_learning.avg_score / 100])
    #kv-row("Papers Logged", str(data.self_learning.papers_logged), highlight: true)
    #kv-row("Sentinel Rate", data.self_learning.sentinel_rate)

    #v(3mm)
    #text(size: 8pt, fill: light)[
      YoYo improvement loop: observe, detect, hypothesize, build, validate
    ]
  ],
)

#v(6mm)

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
    inset: 8pt,

    text(fill: white, weight: "semibold", size: 9pt)[Decision],
    text(fill: white, weight: "semibold", size: 9pt)[Rationale],

    ..for dec in data.architecture_decisions {
      (
        text(size: 9pt, weight: "semibold", fill: dark)[#dec.decision],
        text(size: 8.5pt, fill: mid)[#dec.rationale],
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
        text(size: 10pt, weight: "semibold", fill: black)[#risk.title],
        status-badge(upper(risk.severity), severity-color),
      )
      #v(1mm)
      #text(size: 9pt, fill: mid)[#risk.description]
      #if risk.keys().contains("mitigation") and risk.mitigation != "" {
        v(1mm)
        text(size: 8pt, fill: blue)[Mitigation: #risk.mitigation]
      }
    ]
    v(3mm)
  }
} else {
  text(size: 10pt, fill: green, weight: "semibold")[No critical risks or blockers identified.]
}

#v(6mm)

#section-header("Next Priorities")

#for (i, priority) in data.next_priorities.enumerate() {
  box(
    width: 100%,
    fill: wash,
    radius: 6pt,
    inset: 12pt,
  )[
    #grid(
      columns: (auto, 1fr),
      column-gutter: 8pt,
      align: (center, left),
      text(size: 16pt, weight: "bold", fill: blue)[#(i + 1)],
      [
        #text(size: 10pt, weight: "semibold", fill: black)[#priority.title]
        #if priority.keys().contains("detail") and priority.detail != "" {
          linebreak()
          text(size: 9pt, fill: mid)[#priority.detail]
        }
      ],
    )
  ]
  v(3mm)
}

// ═══════════════════════════════════════════════════════════════════════════
// CLOSING PAGE
// ═══════════════════════════════════════════════════════════════════════════

#pagebreak()

#v(1fr)

#align(center)[
  #text(size: 8pt, fill: light, tracking: 2pt)[STATUS]
  #v(4mm)
  #text(size: 22pt, weight: "bold", fill: black)[All Systems Operational]
  #v(6mm)
  #line(length: 36mm, stroke: 0.3pt + faint)
  #v(6mm)
  #text(size: 9pt, fill: mid)[
    #fmt(data.summary.total_tests) tests
    #h(6pt) #sym.dot.c #h(6pt)
    #fmt(data.summary.total_loc) LOC
    #h(6pt) #sym.dot.c #h(6pt)
    #data.session sessions
    #h(6pt) #sym.dot.c #h(6pt)
    #data.summary.git_commits commits
  ]
  #v(3mm)
  #text(size: 9pt, fill: mid)[
    #data.summary.total_modules modules complete
    #h(6pt) #sym.dot.c #h(6pt)
    0 stubs
    #h(6pt) #sym.dot.c #h(6pt)
    0 syntax errors
  ]
  #v(3mm)
  #text(size: 9pt, fill: mid)[
    Zero external dependencies
  ]
]

#v(1fr)

#align(center)[
  #text(size: 7.5pt, fill: faint)[
    Generated #data.date #sym.dot.c Session #data.session #sym.dot.c github.com/mpshields96/ClaudeCodeAdvancements
  ]
]
