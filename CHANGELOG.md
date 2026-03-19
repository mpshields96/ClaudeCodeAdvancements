# ClaudeCodeAdvancements — Changelog
# Append-only. Never truncate.

---

## Session 59 — 2026-03-19

**What changed:**
- `self-learning/trade_reflector.py` — NEW: MT-10 Phase 3A Kalshi trade pattern analysis (read-only SQLite, 5 detectors, structured proposals)
- `self-learning/tests/test_trade_reflector.py` — NEW: 47 tests (init, win rate drift, time-of-day, streaks, edge trend, sizing, proposals, edge cases)
- `FINDINGS_LOG.md` — 10 new entries: 5 Reddit r/ClaudeCode (context management 114pts, Zero-to-Fleet, markdownmaxxing, Okan, Superpowers), 5 GitHub MT-11 (engram, ClawMem, claude-mem, claude-context, awesome-toolkit)
- `SESSION_STATE.md` — Updated for S59
- `PROJECT_INDEX.md` — Added trade_reflector.py, updated test count to 2021/50 suites

**Why:**
- trade_reflector.py was the #1 priority from S58 — design doc was ready, pure code execution
- Hotspot available for first time this session — knocked out network-dependent Reddit + GitHub scans
- 10 findings provide ecosystem awareness for Frontier 1 (memory) and validate CCA's architectural approach

**Tests:** 2021/2021 passing (50 suites)

**Lessons:**
- S51 NEEDLE URLs not persisted — fresh scan was more productive than hunting lost references
- trade_reflector needs validation against real kalshi_bot.db schema before declaring production-ready

---

## Session 57 — 2026-03-19

**What changed:**
- `self-learning/research_outcomes.py` — NEW: Research ROI tracker (Delivery class, OutcomeTracker, FINDINGS_LOG parser, CLI)
- `self-learning/tests/test_research_outcomes.py` — NEW: 31 tests (Delivery, OutcomeTracker, ROI metrics, bulk import, FINDINGS_LOG parser)
- `self-learning/research_outcomes.jsonl` — NEW: 46 Kalshi research deliveries seeded (S50-S56)
- `self-learning/reflect.py` — Added `auto_reflect_if_due(every_n, session_id)` autonomous mid-session trigger
- `self-learning/tests/test_self_learning.py` — 6 new tests for auto_reflect_if_due (TestAutoReflect class)
- `design-skills/report_generator.py` — collect_self_learning() now reads research outcomes ROI data
- `CROSS_CHAT_INBOX.md` — S57 consolidated pickup checklist, research outcomes CLI docs
- `KALSHI_INTEL.md` — Updated self-learning infrastructure table with research_outcomes.py + micro_reflect
- `CCA_TO_POLYBOT.md` — Added research outcomes tracking instructions
- `cca-report-s57.pdf` — NEW: Professional CCA status report (261KB, Typst)

**Why:**
- Critical gap identified: no closed loop between CCA research recommendations and Kalshi profit outcomes
- micro_reflect() was built in S56 but not wired to fire autonomously — now triggers every N journal entries
- MT-17 (report PDF) was on the queue since S54
- VA wifi blocked all URL-dependent work — focused entirely on local code deliverables

**Tests:** 1946/1946 passing (48 suites)

**Lessons:**
- VA wifi is unreliable for Reddit/SSRN/GitHub — plan local-only tasks when on hospital network
- research_outcomes tracker should be seeded at delivery time, not retroactively (future: auto-seed in /cca-auto)

---

## Session 56 — 2026-03-19

**What changed:**
- `self-learning/reflect.py` — Added `micro_reflect(last_n=10)` for mid-session lightweight pattern detection
- `self-learning/tests/test_self_learning.py` — 10 new tests for micro_reflect (TestMicroReflect class, 101 total)
- `KALSHI_INTEL.md` — 18 verified academic papers + 4 GitHub repo evaluations + r/algotrading deep intelligence
- `CCA_TO_POLYBOT.md` — Massive S56 delivery: 6 actionable patterns, 3 top papers, Reddit intel, updated overnight recommendation
- `CROSS_CHAT_INBOX.md` — S56 notification to both Kalshi chats
- `FINDINGS_LOG.md` — 10 new entries across trading + Claude Code domains
- `MASTER_TASKS.md` — Priority queue refresh for S56

**Why:**
- Matthew directive: investigate how Kalshi chats track overnight profitability data — concern analysis is not optimal
- Tsang & Yang (2026) paper VALIDATES overnight liquidity thinning hypothesis (participation peaks 09-20 UTC)
- Self-learning only triggered at wrap time — micro_reflect() enables mid-session pattern detection
- VA hospital wifi blocked some URLs; pivoted to accessible sources for maximum research output

**Tests:** 1909/1909 passing (47 suites)

**Lessons:**
- r/Kalshi is mostly scam posts — pivot faster to higher-signal subreddits (r/algotrading, r/ClaudeCode)
- micro_reflect() fills the gap between wrap-only reflection and continuous monitoring
- No existing trading bot repo implements time-of-day filtering — CCA is ahead of ecosystem on this

---

## Session 52 — 2026-03-18

**What changed:**
- `KALSHI_INTEL.md` — 12 NEW verified academic papers with Python implementations (Papers 6-13: multinomial Kelly, E-values, DSR, profit vs info, fractional Kelly, wash trading, CPCV, BOCPD)
- `CROSS_CHAT_INBOX.md` — Updated notification for 12-paper delivery
- `LEARNINGS.md` — CCA dual mission (50% Kalshi + 50% self-improvement) codified as severity-3
- `FINDINGS_LOG.md` — OMEGA memory deep-dive (BUILD), trigger-table pattern, KG token optimization, CC March 2026 changelog
- `SESSION_STATE.md` — Full session progress + next priorities

**Why:**
- S51 resume prompt requested nuclear academic paper scan — delivered 12 papers covering Kelly, sequential testing, overfitting, changepoint detection
- CCA self-improvement side: Frontier 1 reconnaissance found OMEGA (95.4% LongMemEval) with 5 adaptable patterns
- PostCompact hook identified as immediate build opportunity from CC March 2026 changelog

**Tests:** 1768/1768 passing (44 suites)

**Lessons:**
- Reddit NEEDLE deep-reads via web search fail — posts are unfindable. Use reddit_reader.py or skip.
- CCA dual mission must be balanced: this session was ~70% Kalshi / 30% CCA. Next session should flip.

---

## Session 51 — 2026-03-19

**What changed:**
- `CROSS_CHAT_INBOX.md` — All 3 Kalshi Research S108 requests marked COMPLETE
- `~/.claude/cross-chat/CCA_TO_POLYBOT.md` — OctagonAI eval, Le (2026) calibration formula, FLB alert, Prime Directive reinforcement

**Why:**
- Matthew directive: ROI = make money. CCA research must generate profit for Kalshi bot.
- Le (2026) calibration formula is directly programmable: true_prob = p^b / (p^b + (1-p)^b)
- Political markets b=1.83 vs crypto b=1.03 → Pillar 3 expansion candidate (5-13x more mispriced)
- OctagonAI repo: 73/100 code, 25/100 strategy (LLM-as-edge is anti-pattern, don't adopt)

**Tests:** 1768/1768 passing (44 suites)

**Lessons:**
- PDF extraction needs poppler/PyPDF2 — neither installed. Use WebFetch HTML or browser for papers.
- Paper scanner domain keywords too broad for "prediction market" — returns soil chemistry papers.
- Reddit reader designed for single posts, not listing pages — use autonomous scanner for bulk.
- When Matthew says ROI, he means financial. Don't build iOS dashboards before profit research.

---

## Session 50 — 2026-03-19

- Cross-chat Kalshi bet sizing review (all 5 strategies)
- Academic research: CUSUM h=5.0, Kelly for pred markets, FLB short-horizon (14 verified citations)
- Meta labeling 23 features recommendation
- Parameter changes queue to CCA_TO_POLYBOT.md
- Added cross-chat inbox check to /cca-init

---

## Session 49 — 2026-03-18
- Committed S48 wrap files
- MT-13 Phase 2 COMPLETE: iOS project generator + Xcode build helper
  - `ios_project_gen.py`: generates complete Xcode projects from CLI (40 tests)
  - `xcode_build.py`: Python xcodebuild wrapper with error parsing (17 tests)
  - E2E validated: KalshiDashboard project builds + tests pass on iOS Simulator
  - Xcode 26.3 confirmed installed (Build 17C529)
- MT-17 Phase 4 COMPLETE: SVG chart generator + dashboard integration
  - `chart_generator.py`: 5 chart types (bar, h-bar, line, sparkline, donut), 42 tests
  - Integrated inline SVG charts into dashboard_generator.py
- Tests: 1768/1768 (44 suites)

---

## Session 48 — 2026-03-18

**What changed:**
- Built `session_pacer.py` — objective pacing for 2-3h autonomous /cca-auto runs (35 tests)
- Integrated session pacer into `/cca-auto` command (replaces hardcoded % thresholds)
- Wired pacer reset into `/cca-init` startup ritual
- MT-17 Phase 3 COMPLETE: `dashboard_generator.py` — self-contained HTML dashboard (33 tests)
- Created `/cca-dashboard` slash command for one-command dashboard generation
- Enhanced dashboard with live project data parsing (MASTER_TASKS, SESSION_STATE, PROJECT_INDEX)
- Updated PROJECT_INDEX (test counts, new files), MASTER_TASKS (MT-17 score)

**Why:**
- Matthew requested extended autonomous sessions; pacer gives Claude objective stop signals
- MT-17 Phase 3 delivers web-viewable project status — no Typst/PDF dependency needed
- Live data parsing means `/cca-dashboard` shows real project state, not demo data

**Tests:** 1686/1686 passing (42 suites) — +68 tests (+2 suites)
**Commits:** 8

**Lessons:**
- Session pacer + auto_wrap.py = objective pacing stack; no more guessing "am I at 60%?"
- HTML dashboards are trivially self-contained — inline CSS beats external deps for portability

---

## Session 47 — 2026-03-18

**What changed:**
- Created `/cca-slides` slash command (`.claude/commands/cca-slides.md`) — one-command slide generation
- Updated MASTER_TASKS.md priority scores: MT-14 (13.0->6.0), MT-17 (7.0->6.0)

**Why:**
- /cca-slides mirrors /cca-report pattern for quick presentation generation
- Priority queue was stale — MT-14 and MT-17 both completed work in S46 but scores weren't updated

**Tests:** 1618/1618 passing (40 suites)
**Commits:** 1

**Lessons:**
- Short housekeeping sessions are fine — keeps scores accurate and reduces debt for next session

---

## Session 46 — 2026-03-18

**What changed:**
- Wired resurfacer into /cca-init (Step 3: surfaces past findings at startup)
- MT-14 COMPLETE: All 15 subreddits scanned (7 new: r/webdev, r/iOSProgramming, r/MachineLearning, r/Bogleheads, r/stocks, r/SecurityAnalysis, r/ValueInvesting)
- MT-17 Phase 2 COMPLETE: Slide template + generator (25 tests, 5 slide types)
- CHANGELOG + LEARNINGS updated for Session 45 (deferred from S45 context limit)
- Checked cross-chat bridge — no Kalshi reply yet
- Committed Session 45 journal.jsonl

**Why:**
- Resurfacer integration prevents knowledge loss during session startup
- MT-14 completion means all subreddits have baseline scans for delta detection
- MT-17 slide generator enables professional presentation output

**Tests:** 1618/1618 passing (40 suites, +25 from slide generator)
**Commits:** 6

**Lessons:**
- Investing/general subs (r/stocks, r/Bogleheads) are noise for CCA — 98% NEEDLE rate means classifier is too broad
- Context limits hit at S45 end deferred wrap work — always budget 10% for wrap

---

## Session 45 — 2026-03-18

**What changed:**
- MT-10 Phase 3B COMPLETE: `self-learning/resurfacer.py` — findings re-surfacing module (41 tests)
- Cross-chat communication system: `CROSS_CHAT_INBOX.md` shared inbox + `bridge-sync.sh`
- `CCA_TO_POLYBOT.md` — Universal bet analytics framework (5 verified academic tools: SPRT, Wilson CI, Brier, CUSUM, FLB)
- `KALSHI_PRIME_DIRECTIVE.md` — permanent three-pillar cross-chat directive
- `CLAUDE.md` updated: read-only access to polymarket-bot for cross-chat bridge
- MT-14: Added r/AutoGPT + r/LangChain profiles, first scans (3 findings logged)
- Fixed 3 failing mobile_approver tests (Bash moved to ALWAYS_ALLOW_TOOLS)

**Why:**
- Cross-chat bridge enables CCA to serve Kalshi research (Matthew directive: 1/3 sessions on Kalshi)
- Resurfacer prevents knowledge loss — past reviews resurface when working on matching frontiers
- KALSHI_PRIME_DIRECTIVE documents the three pillars: perfect engine, deep research, expand beyond

**Tests:** 1593/1593 passing (39 suites, +41 new from resurfacer)
**Commits:** 8

**Lessons:**
- Cross-chat communication needs a protocol — unstructured bridge files get ignored
- Academic citation verification is non-negotiable (caught unverified references in first draft)
- r/AutoGPT and r/LangChain are moderate-yield for CCA frontiers (agent patterns relevant)

---

## Session 44 — 2026-03-18

**What changed:**
- MT-10 Phase 2 COMPLETE — 5/5 validation sessions across 36 transcripts (avg 70.8, improving trend)
- MT-10 Phase 3 scope expanded: findings re-surfacing (Matthew directive, Session 44)
- MT-13 research COMPLETE — `research/MT-13_ios_dev_research.md` (NEW) — full iOS/macOS dev landscape
- MT-8 scope closed — native Remote Control covers use case, remaining config outside CCA scope
- MT-14 first-time scans: r/MachineLearning (15 posts), r/webdev (25 posts), r/iOSProgramming (14 posts)
- 14 findings logged to FINDINGS_LOG.md (iOS ecosystem, r/ClaudeCode intel, r/MachineLearning)
- `MASTER_TASKS.md` — MT-10 Phase 2 marked complete, MT-13 research complete, MT-8 closed

**Why:**
- MT-10 Phase 2 validation reaching natural conclusion (5-session protocol)
- MT-13 hit decay cap (8.0, never touched) — research revealed Xcode 26.3 + Claude Agent SDK
- Matthew expanded MT-13 scope to include macOS apps for CCA tooling

**Tests:** 1552/1552 passing (38 suites, no changes)
**Commits:** 9

**Lessons:**
- Xcode 26.3 solves most of what MT-13 was created for — CCA's role shifts from "build capability" to "configure and template"
- r/webdev and r/MachineLearning are low-yield for CCA frontiers (mostly meta-discussion and pure research)
- Answering Matthew's strategic questions inline during /cca-auto is productive — captures directives that would otherwise be lost

---

## Session 43 — 2026-03-18

**What changed:**
- MT-10 Phase 2: Session 3/5 validation (4 transcripts, avg 71.25)
- MT-9 Phase 4: Deep-read 4 r/ClaudeAI posts (2 REFERENCE, 2 SKIP)
- 3 CCA reviews: design skills ADAPT, harness thread REF, TraderAlice REF-PERSONAL
- Design guide: quality gates + rules added to design-guide.md
- 4 new skillbook strategies (S10-S13) — CLAUDE.md routing, retrospectives, Read before Edit, bloat tracking
- r/ClaudeAI classifier cap fixed (needle_ratio_cap=0.4)
- LEARNINGS.md: PROJECT_INDEX.md retry hotspot (severity 2)

**Tests:** 1552/1552 passing (38 suites)
**Commits:** 6

---

## Session 42 — 2026-03-18

**What changed:**
- `MASTER_TASKS.md` — NEW priority decay scoring system (base_value + chats_untouched * aging_rate)
- MT-10 Phase 2: YoYo self-learning validation sessions 1-2/5 (4 transcripts analyzed, 13 proposals, scores 65-95)
- MT-9 Phase 3: Supervised autonomous scan trial on r/ClaudeAI (25 posts, 16 NEEDLEs)
- MT-11 Phase 2: Live GitHub API validated (30+ repos evaluated, 97 total in log)
- MT-12 Phase 2: Paper scanner across agents + prediction domains (40 papers, 21 logged)
- MT-8: Research complete — native Remote Control solves 90% of requirements
- `research/MT-8_remote_control_research.md` (NEW) — Remote Control setup guide

- Self-resolution scan: MT-1 (visual grid) and MT-5 (Pro bridge) mostly solved by community tools
- Scoring rule 6 added: self-resolution scan every 5 sessions

**6 MTs advanced in one session (first time). Decay system working: priorities shifted correctly after each sub-session.**

**Why:**
- Matthew requested working strictly from MT list by priority, with decay-based aging
- Force-multiplier criterion: work on what makes Claude smarter/faster first

**Tests:** 1552/1552 passing (38 suites, no changes)
**Commits:** 5

**Lessons:**
- Self-resolution scan should run at session START, not end — it changes the priority queue
- 3-session sub-session model works well for one chat (A/B/C structure)

---

## Session 41 — 2026-03-18

**What changed:**
- `design-skills/` (NEW MODULE) — Professional visual output via Typst
- `design-skills/report_generator.py` (NEW) — CCADataCollector + ReportRenderer + CLI, 21 tests
- `design-skills/templates/cca-report.typ` (NEW) — Status report Typst template (metric cards, module table, master tasks, priorities)
- `design-skills/design-guide.md` (NEW) — CCA visual language (8 colors, 7 typography levels, layout rules)
- `design-skills/CLAUDE.md` (NEW) — Module rules and architecture decisions
- `.claude/commands/cca-report.md` (NEW) — One-command PDF generation
- `MASTER_TASKS.md` — MT-17 scope expanded to PDFs + presentations + graphics + websites
- `PROJECT_INDEX.md` — Added design-skills module, updated test count
- `SESSION_STATE.md` — Updated with Session 41 work

**Why:**
- Matthew's CCA status report PDF was "atrocious" — needed professional-quality output
- MT-17 research (Session 40) selected Typst as the tool — this session built the implementation
- Matthew directive: design capabilities should cover all visual formats, not just PDFs

**Tests:** 1546/1546 passing (38 suites — +21 new tests, +1 new suite)

**Lessons:**
- Typst resolves `sys.inputs` paths relative to the template file — use `--root /` with absolute paths
- Typst compiles in <100ms — fast enough for interactive report generation
- TDD worked cleanly: 21 tests red -> green in one pass (only 1 integration fix needed)

---

## Session 40 — 2026-03-18

**What changed:**
- `self-learning/research/MT17_DESIGN_RESEARCH.md` (NEW) — Full PDF library comparison: Typst recommended over WeasyPrint/ReportLab for professional report generation
- `FINDINGS_LOG.md` — 3 new entries: Playwright CLI (407pts), Reddit MCP (62pts), Naksha v4 (25pts)
- `generate_report_pdf.py` — Committed from previous session (the "atrocious" PDF generator)
- `CCA_STATUS_REPORT_2026-03-17.txt` — Committed text report from previous session
- `SESSION_STATE.md` — Updated with Session 40 summary and next priorities

**Why:**
- MT-17 research phase needed: Matthew's PDF report was poor quality, Typst solves this with professional typography
- Paper deep-reads fulfill Session 39's priority #1 (top-scored papers from scanner)
- r/ClaudeCode weekly scan keeps intelligence current

**Papers deep-read:**
- Deep Research Agents (80pts, 117 citations) — agent taxonomy, MCP integration patterns
- HALO (75pts, 11 citations) — MCTS workflow optimization, 14.4% SOTA improvement
- AutoP2C (75pts, 14 citations) — paper-to-code generation pipeline

**Tests:** 1525/1525 passing (37 suites, no changes)

**Lessons:**
- Search for arXiv IDs before guessing — Semantic Scholar paper IDs != arXiv IDs
- Typst is the right tool for CCA: JSON-native, single binary, millisecond compile

---

## Session 39 — 2026-03-18

**What changed:**
- `FINDINGS_LOG.md` — 7 new reviews: YoYo v2 (REFERENCE), Design Studio (ADAPT->MT-17), Traul (REFERENCE), ClaudePrism (BUILD->MT-18), Autoresearch (ADAPT), Unsloth Studio (REFERENCE-PERSONAL->MT-19), reddit-mcp-buddy (REFERENCE)
- `MASTER_TASKS.md` — Created MT-17 (UI/Design Excellence + Report Generation), MT-18 (Academic Writing Workspace), MT-19 (Local LLM Fine-Tuning). Updated MT-12 status to Phase 1 COMPLETE. Updated priority order.
- `self-learning/paper_scanner.py` — Delay increased from 1.5s to 3s (429 rate limit fix)
- `self-learning/research/papers.jsonl` — 20 papers logged from 4-domain scan (agents, prediction, statistics, interaction)

**Why:**
- Matthew reviewed 7 Reddit posts and wanted findings documented as future tasks
- Paper_scanner needed rate limit fix (hit 429 at 1.5s in Session 38)
- 4-domain scan was next priority from Session 38 queue

**Tests:** 1525/1525 passing (no change)

**Lessons:**
- Design Studio top comment (130pts audit) shows community values honest evaluation — our /cca-review verdicts should be equally rigorous
- Paper_scanner at 3s delay successfully completed all 4 domains without 429 errors

---

## Session 38 — 2026-03-17

**What changed:**
- `agent-guard/path_validator.py` — Wired into live PreToolUse hooks (settings.local.json). Blocks system dir writes, destructive commands, path traversal. Fixed SyntaxWarning.
- `PROJECT_INDEX.md` — Trimmed 72% (441->122 lines, 28KB->5.5KB). Addresses 74% retry rate from trace analysis.
- `REFERENCE.md` — NEW: detailed API docs, test summary, architecture decisions, session history (moved from PROJECT_INDEX)
- `self-learning/paper_scanner.py` — NEW: MT-12 academic paper discovery. Semantic Scholar + arXiv APIs, 4 CCA domains, evaluation scoring, JSONL logging, CLI. 54 tests.
- `self-learning/research/papers.jsonl` — NEW: first paper logged (Agent0, 69/100 IMPLEMENT)
- `.claude/commands/cca-status.md` — NEW: /cca-status nuclear-level project overview command
- `.claude/commands/cca-auto.md` — Marathon mode for 2-hour autonomous sessions
- `CLAUDE.md` — Updated test commands section (was listing 8 suites/283 tests, now 37 suites/1525)

**Why:**
- path_validator was built in S37 but not wired — now live
- PROJECT_INDEX was the #1 retry hotspot (74% of sessions) — dramatic trim needed
- MT-12 academic paper integration was next on the roadmap
- Matthew requested nuclear overview command and 2-hour autonomous capability

**Tests:** 1525/1525 passing (was 1471, +54)

**Lessons:**
- Semantic Scholar shared rate limit is aggressive — 429 after rapid queries even with 0.5s delay. Need 1.5-3s between queries.
- macOS grep doesn't support -P flag — use awk/sed instead for Perl regex patterns

---

## Session 37 — 2026-03-17

**What changed:**
- `self-learning/batch_report.py` — NEW: Aggregate trace health across sessions (score dist, retry hotspots). 13 tests.
- `agent-guard/path_validator.py` — NEW: Dangerous path + command detection (traversal, rm -rf, dd, curl|bash). 30 tests.
- Sentinel dialed to 5-10%, scan limit enforced
- 31-session trace analysis: identified PROJECT_INDEX.md 74% retry rate

**Tests:** 1471/1471 passing (was 1428, +43)

---

## Session 29 — 2026-03-17

**What changed:**
- `context-monitor/hooks/meter.py` — CLAUDE_AUTOCOMPACT_PCT_OVERRIDE awareness: get_autocompact_pct(), compute_autocompact_proximity(), state file now includes autocompact_pct + autocompact_proximity. 10 new tests (62 total).
- `context-monitor/hooks/alert.py` — Autocompact proximity warnings: yellow zone alerts when approaching auto-compact (<10 points), red/critical messages include proximity. should_warn_autocompact() + updated should_alert/build_message signatures. 16 new tests (40 total).
- `context-monitor/statusline.py` — AC:Xpts display when approaching compaction. AC:NOW at threshold. _get_autocompact_pct(), _autocompact_proximity(), _format_autocompact_part(). Import os added.
- `context-monitor/tests/test_statusline.py` — NEW: First test suite for statusline.py. 24 tests covering thresholds, zones, bar, window format, autocompact proximity.
- `context-monitor/hooks/compact_anchor.py` — Autocompact proximity line in anchor output. IMMINENT at 0 points, "X points away" otherwise. 3 new tests (25 total).
- `self-learning/improver.py` — QualityGate class: geometric mean anti-gaming (Nash 1950 / sentrux pattern). 20 new tests (64 total).
- `spec-system/commands/design.md` — Performance Specifications section (call frequency, latency budget, resource constraints)
- `spec-system/commands/implement.md` — TDD red-green ordering enforced
- `spec-system/commands/tasks.md` — Demo field (observable outcome per task)
- `FINDINGS_LOG.md` — 19 new entries (18 r/ClaudeCode + 1 cerebellum repo)
- `MASTER_TASKS.md` — MT-7 marked COMPLETE, MT-10 updated with QualityGate + E2E validation

**Why:**
- CLAUDE_AUTOCOMPACT_PCT_OVERRIDE is a new Claude Code env var that changes when auto-compaction fires. Users with 1M context windows need awareness of approaching compaction to /compact proactively (prevents losing CLAUDE.md rules to the compaction bug).
- QualityGate prevents Goodhart's Law gaming in self-improvement loops — any zero metric tanks the composite score.
- Spec system enhancements from ADAPT findings: CAS demo statements, performance awareness, TDD ordering.

**Tests:** 1093/1093 passing (26 suites)

**Lessons:**
- Context-monitor module is now very well-covered (5 test suites, 178 tests). Next session should build outside this module.
- User feedback: focus on building, not re-scanning same subreddits. Consider diminishing returns.

---

## Session 28 — 2026-03-17

**What changed:**
- `self-learning/improver.py` — NEW: MT-10 YoYo improvement loop core. ImprovementProposal lifecycle (proposed -> approved -> building -> validated -> committed/rejected), ImprovementStore (JSONL persistence), ProposalGenerator (from_trace_report + from_reflect_patterns), risk classification (LOW/MEDIUM/HIGH), cross-session dedup, safety guards (protected files, max proposals per session, trading always HIGH)
- `self-learning/tests/test_improver.py` — NEW: 44 tests covering proposals, store, generator, risk classification, safety guards
- `self-learning/reflect.py` — Wired improver: analyze_current_session() auto-generates proposals, --propose flag, --session flag for tracking
- `agent-guard/hooks/network_guard.py` — NEW: AG-5 PreToolUse hook blocking port/firewall exposure. 20 threat patterns: adb tcpip, ufw disable/allow, iptables, docker -p, ngrok/cloudflared, nc/socat, python http.server, ssh -R 0.0.0.0, /etc/hosts, sshd_config
- `agent-guard/tests/test_network_guard.py` — NEW: 53 tests (port exposure, firewall mods, network config, safe commands, hook responses)
- `SESSION_STATE.md` — Updated to Session 28
- `PROJECT_INDEX.md` — Updated with new files, test counts
- `reddit-intelligence/profiles.py` — Added 5 investing/stocks subreddit profiles (r/investing, r/stocks, r/SecurityAnalysis, r/ValueInvesting, r/Bogleheads) per Matthew's directive
- `MASTER_TASKS.md` — MT-9 approved domains expanded with investing subs
- `FINDINGS_LOG.md` — 4 new entries from autonomous scanning (1M context, retry loops, Qwen browser, r/LocalLLaMA triage)

**Why:**
- MT-10 priority 1: YoYo self-learning loop closes the Observe -> Detect -> Hypothesize -> Build -> Validate -> Commit cycle. improver.py is the Hypothesize step.
- AG-5 from "We got hacked" BUILD verdict (458pts, r/ClaudeCode): Claude exposed ADB port 5555 on Hetzner VM, crypto miner exploited within hours. Community consensus: firewall-first, localhost-bind.
- Investing/stocks expansion: Matthew plans to use Claude for low-cost stock investing research long-term.

**Tests:** 1040/1040 passing (25 suites)

**Lessons:**
- Background agents lost to context compaction — process results within 5 minutes of spawn
- r/webdev and r/LocalLLaMA confirmed as low-signal for CCA (reinforces existing learning)

---

## Session 27 — 2026-03-17

**What changed:**
- `agent-guard/content_scanner.py` — NEW: AG-4 hazmat suit for autonomous scanning. 9 threat categories (executable_install, credential_harvest, data_exfiltration, financial_threat, system_damage, prompt_injection, scam_signals, low_quality_repo, malicious_url). 25+ regex patterns, phishing domain detection with whitelist, repo metadata scanning
- `agent-guard/tests/test_content_scanner.py` — NEW: 50 adversarial tests, zero false positives on 138 real posts
- `self-learning/reflect.py` — Added `analyze_current_session()` function + `--trace` CLI flag for trace analyzer integration
- `self-learning/journal.py` — Added `trace_analysis` event type
- `reddit-intelligence/findings/POLYBOT_DISHES.md` — NEW: 2 trading food dishes for Kalshi bot (Polymarket ghost fill exploit, mean reversion improvements)
- `FINDINGS_LOG.md` — 15 new entries: 2 BUILD, 3 ADAPT, 6 REFERENCE, 2 REFERENCE-PERSONAL, 1 SKIP, 1 inaccessible
- `MASTER_TASKS.md` — MT-15 added (detachable chat tabs)
- `PROJECT_INDEX.md` — Updated with content_scanner.py, test_content_scanner.py entries

**Why:**
- Matthew's directive: "hazmat suit before nuclear wasteland" — safety-first autonomous scanning
- Self-learning conquest: autonomously scan high-quality subreddits, filter rat poison, serve trading finds as food dishes to Kalshi bot
- Pipeline validation: prove profiles -> fetcher -> scanner -> deep-read -> findings works end-to-end before scaling to GitHub/papers

**Tests:** 943/943 passing (+50 from content_scanner)

**Lessons:**
- Validate post URLs before spawning deep-read agents — failed Reddit reads waste ~45k tokens per agent
- r/ClaudeAI post IDs from nuclear_fetcher month-view can differ from search results — verify URL before deep-read
- Phishing regex must use whitelist approach (check legit_domains first) to avoid false positives on anthropic.com
- Anthropic's memory feature is marketing-first (prompt export) — our local-first structured memory is architecturally ahead
- YoYo proves self-evolution loops work at $12/4 days — 4-gate safety model is the pattern for MT-10

---

## Session 25 — 2026-03-16

**What changed:**
- `ROADMAP.md` — complete overhaul: was stale since Session 1 (all frontiers showing "Research phase"), now reflects all 5 COMPLETE + 15 MTs with priorities
- `self-learning/research/TRACE_ANALYSIS_RESEARCH.md` — NEW: MT-7 research output. Full JSONL schema from 5 real transcripts, 6 pattern detector definitions with real-data thresholds
- `MASTER_TASKS.md` — 6 new master tasks (MT-9 through MT-14): autonomous subreddit intelligence (9 safety protections), YoYo self-learning loop, GitHub repo intelligence, academic paper integration, iOS app development, re-scanning previously scanned subs
- `CLAUDE.md` — NEW SECTION: 7 Cardinal Safety Rules (non-negotiable, override all other instructions, apply to all modes including overnight autonomy)
- `SESSION_STATE.md` — session 25 log, overnight 3-chat architecture, next priorities
- Memory: `feedback_cardinal_safety.md`, `project_overnight_3chat.md`

**Why:**
- Matthew's vision (Session 25): autonomous self-learning and self-building system that grows CCA and Kalshi bot without human intervention — with ironclad safety
- Anti-Frankenstein principle: every autonomous discovery must be objectively useful, clean, modular, tested, logged
- Cardinal safety rules established before overnight autonomy: never break anything, never expose credentials, never install malware, never risk financial loss
- Overnight architecture: exactly 3 chats (Kalshi main + Kalshi research + ONE CCA)

**Tests:** 800/800 passing (no new tests — research/planning session)

**Lessons:**
- ROADMAP.md going 24 sessions without update is a documentation debt anti-pattern — update docs same session as the work they describe
- Trace analysis research is code-ready: 6 pattern detectors with exact JSON field paths, real thresholds from 5 transcripts, recommended class architecture — next session should go straight to TDD
- Planning-only sessions (no code shipped) should be avoided when research is complete and implementation is ready

---

## Session 19 — 2026-03-16

**What changed:**
- `MASTER_TASKS.md` — new file: 6 master-level aspirational tasks (MT-0 through MT-5)
- `.claude/commands/cca-nuclear.md` — subreddit flexibility: accepts any subreddit as argument, file namespacing by slug
- `reddit-intelligence/nuclear_fetcher.py` — added `subreddit_slug()` function for filesystem-safe slug conversion
- `reddit-intelligence/tests/test_nuclear_fetcher.py` — 8 new slug tests (44 total)
- `scripts/kalshi-launch.sh` — new Terminal.app dual-window Kalshi launcher (replaces tmux approach)
- `FINDINGS_LOG.md` — frontend-design plugin entry upgraded from REFERENCE to ADAPT with full analysis
- `SESSION_STATE.md` — session 19 log, master-level tasks, updated priorities
- `PROJECT_INDEX.md` — added scripts/ directory, updated test counts
- Memory: `project_kalshi_self_learning.md`, `project_claude_pro_bridge.md`, `feedback_thoroughness.md`

**Why:**
- MT-0 (Kalshi self-learning integration) is the highest-stakes application of CCA's architecture — user identified research quality as the bottleneck
- Honest CCA vs YoYo analysis revealed 5 gaps: no autonomous loop, no codebase-as-memory, no pain/win tracking, no self-awareness, no pruning
- Nuclear subreddit flexibility enables scanning any subreddit with same pipeline (not just r/ClaudeCode)
- Terminal.app launcher is simpler and more reliable than tmux for dual-chat startup

**Tests:** 742/742 passing (20 suites, 8 new)

**Lessons:**
- Self-learning plateau is real (u/inbetweenthebleeps): optimizes mechanics not architectural judgment — design around this limitation
- "Evolution is in the artifact, not the weights" (liyuanhao) — the codebase IS the memory, not just the journal file

---

## Session 18 — 2026-03-16

**What changed:**
- `.claude/settings.local.json` — wired cost_alert.py as PreToolUse hook (fires on all tool calls, self-filters cheap tools)
- `~/.local/bin/dev-start` — rewrote as tmux split-pane launcher for Kalshi dual-chat automation (outside CCA scope, with user permission)
- `KALSHI_CHEATSHEET.md` — daily operations quick reference for Kalshi bot

**Why:**
- USAGE-3 cost alert hook needed to be live to warn/block on expensive sessions
- User needed one-command launch for two autonomous Kalshi bot chats with full instruction delivery
- Iterated through AppleScript (failed: accessibility/targeting), Claude Squad (failed: worktrees break shared filesystem), landed on tmux send-keys

**Tests:** 734/734 passing (20 suites)

**Lessons:**
- tmux `send-keys` with exact pane targeting is the reliable approach for scripted CLI input — AppleScript keystroke simulation is fragile and window-dependent
- `tmux kill-server` can corrupt the socket at `/private/tmp/tmux-501/default` — always clean the socket file if tmux refuses to start
- Claude Code sessions can't visually attach tmux — user must run the script from their own Terminal

---

## Session 16 — 2026-03-15

**What changed:**
- `usage-dashboard/usage_counter.py` — CLI token/cost counter reading transcript JSONL (sonnet/opus/haiku pricing, per-session/daily/weekly views)
- `usage-dashboard/arewedone.py` — structural completeness checker for all 7 modules (CLAUDE.md, source, tests, stubs, syntax)
- `.claude/commands/arewedone.md` — /arewedone slash command
- `.claude/commands/cca-wrap.md` — added Review & Apply self-learning phase
- `reddit-intelligence/CLAUDE.md` — module rules (was missing)
- `self-learning/CLAUDE.md` — module rules (was missing)
- Committed sessions 10-15 backlog (28 files, 5604 insertions)
- Installed claude-devtools v0.4.8, Claude Usage Bar v0.0.6, Claude Island v1.2

**Why:**
- USAGE-1 was the highest community demand from nuclear scan (9+ posts, 807pts OTel + 879pts devtools)
- /arewedone catches structural gaps that silently accumulate (found 2 missing CLAUDE.md files)
- Self-learning integration in /cca-wrap enables pattern detection at session boundaries
- 8-session commit backlog was a critical risk to work preservation

**Tests:** 568/568 passing (17 suites, 94 new)

**Lessons:**
- Test fixtures containing TODO/FIXME must be excluded from stub scanning
- Claude Island auto-installs hooks — don't launch while other CC sessions are active

---

## Session 14 — 2026-03-15

**What changed:**
- `self-learning/journal.py` — structured event journal (JSONL), CLI interface, nuclear metrics aggregation
- `self-learning/reflect.py` — pattern detection engine, strategy auto-adjustment, recommendation generator
- `self-learning/strategy.json` — tunable parameters for nuclear scan, session workflow, review strategy
- `self-learning/tests/test_self_learning.py` — 34 tests covering journal, stats, reflection, strategy apply
- `.claude/commands/cca-nuclear-wrap.md` — nuclear wrap command with 13-step self-learning integration
- `reddit-intelligence/findings/NUCLEAR_REPORT.md` — interim report with self-learning section added
- `reddit-intelligence/findings/nuclear_progress.json` — 45 post IDs reviewed
- `FINDINGS_LOG.md` — 22 new entries (nuclear scan batch 1)
- `SESSION_STATE.md` — session 14 log, nuclear progress, self-learning status
- `PROJECT_INDEX.md` — self-learning module added

**Why:**
- Nuclear scan systematically mines r/ClaudeCode for actionable patterns across all 5 frontiers
- Self-learning system adapted from YoYo pattern — tracks session outcomes, detects recurring patterns, suggests strategy tuning
- User requested self-learning deployed for CCA/CLI, not just Polybot

**Nuclear scan results (batch 1):**
- 45/110 posts reviewed | 2 BUILD | 8 ADAPT | 22.2% signal rate
- Top BUILD: OTel metrics for USAGE-1, claude-devtools for context observability
- 7 specific learnings captured to journal

**Tests:** 517/517 passing (15 suites)

**Lessons:**
- Self-learning journal must have SPECIFIC learnings, not vague summaries — "OTel better than transcript parsing" not "reviewed some posts"
- Posts >500pts have ~3x higher BUILD/ADAPT rate than posts 30-200pts

---

## Session 12 — 2026-03-15

**What changed:**
- `SESSION_STATE.md` — added MASTER PLAN section (unified workspace + self-learning architecture), session 12 work log, updated open items
- `FINDINGS_LOG.md` — 5 new entries (Claude Squad, Agent Deck, Codeman, NTM, 15-tool comparison), 27 total entries
- `CHANGELOG.md` — this entry
- `~/.local/bin/dev-start` — upgraded to auto-launch Claude in all 3 windows, idempotent re-attach
- `~/.local/bin/cs-start` — new Claude Squad launcher (backup)

**Why:**
- User wants all Claude Code sessions (CCA + 2 Kalshi) in one tmux window with zero manual setup
- Self-learning architecture designed for Polybot to adopt (journal + strategy feedback loop)
- Maestro (preferred UI) crashed on macOS 15.6 beta — fell back to tmux + dev-start

**Reddit reviews (6 new posts):**
- YoYo self-evolving agent (ADAPT, 941pts) — journal pattern for self-learning
- Crucix intelligence center (SKIP) — data dashboard, not agent management
- Maestro orchestrator (BUILD, 476pts) — built from source, crashed on SDK issue
- Maestro teaser (REFERENCE, 424pts) — confirms demand
- Agent Teams walkthrough (ADAPT, 461pts) — sendMessage pattern, Cozempic pruner
- Personal Claude setup / Adderall (same as Maestro)

**Infrastructure:**
- Maestro v0.2.4 built (crashed — macOS 15.6 beta _NSUserActivityTypeBrowsingWeb)
- Claude Squad v1.0.17 installed via brew
- tmux workspace: 3 windows, Claude auto-launched, 20/20 integration tests passing
- CShip statusline verified rendering in tmux

**Tests:** 483/483 passing

**Lessons:**
- Tauri apps built from source may crash on beta macOS due to SDK symbol changes — always have a CLI fallback
- tmux is more reliable than native desktop apps for multi-session management (no SDK dependencies)
- Self-learning agent architecture = shared journal + reflection step + minimum sample sizes — adapted from YoYo pattern

---

## Session 11 — 2026-03-15

**What changed:**
- `FINDINGS_LOG.md` — 9 new entries (4 batch 1 + 5 batch 2), introduced REFERENCE-PERSONAL verdict
- `LEARNINGS.md` — new Severity 2: file-writing hooks trigger system-reminder context burn (160k tokens/3 rounds)
- `SESSION_STATE.md` — 7 new open items (UserPromptSubmit hook, linked repos, compact anchor investigation, Recon install, ClaudePrism, trading refs, agtx)
- `.claude/commands/cca-review.md` — added REFERENCE-PERSONAL verdict option + synced to global
- Memory: user_profile.md (psychiatry resident, Kalshi/trading, academic writing), feedback_personal_tools.md

**Reddit reviews (9 posts):**
- Algotrading strategy list (REFERENCE-PERSONAL, 534pts)
- VEI volatility signal (REFERENCE-PERSONAL, 436pts)
- "claude on a crusade" meme (REFERENCE — Holy Order + superpowers links)
- Beast post 6-month tips (ADAPT — skill auto-activation, build checker, context burn warning)
- ClaudePrism academic workspace (REFERENCE-PERSONAL)
- code-commentary sports narrator (SKIP)
- Recon tmux dashboard (BUILD — 530pts, multi-agent visibility)
- Membase memory layer (REFERENCE — conflict resolution pattern)
- agtx terminal kanban (REFERENCE — worktree isolation, GSD plugin)

**Infrastructure installed:**
- tmux 3.6a, Rust 1.94.0, Recon v0.1.0 (tmux-native CC agent dashboard)
- ~/.tmux.conf with Recon keybindings
- ~/.local/bin/dev-start (3-window tmux: CCA + 2 Kalshi sessions)

**Key findings:**
- UserPromptSubmit hook for skill auto-activation is a new pattern CCA doesn't have
- File-writing hooks (Prettier, compact_anchor) silently burn context via system-reminder diffs
- Recon solves the multi-chat management problem using tmux + CC's own session JSON files

**Tests:** 483/483 passing (no changes to code)

**Lessons:**
- Don't dismiss tools outside CCA frontiers — use REFERENCE-PERSONAL for personally useful tools (trading, academic writing)
- Commit backlog has grown across 3 sessions — must commit first thing next session

---

## Session 10 — 2026-03-15

**What changed:**
- `.claude/commands/cca-wrap.md` — new session end ritual (self-grade, learnings, resume prompt)
- `.claude/commands/cca-scout.md` — autonomous subreddit scanner for high-signal posts
- `CLAUDE.md` — added "URL Review — Auto-Trigger" section + "Session Commands" table
- `FINDINGS_LOG.md` — 8 new entries from Reddit reviews
- All 5 /cca-* commands copied to `~/.claude/commands/` for global availability
- Verified: CShip v1.0.80, RTK v0.29.0, mobile approver hook, claude-code-transcripts

**Why:**
- User needed effortless Reddit review pipeline — paste URL, get verdict, auto-log
- Session management commands bring CCA to parity with polybot framework patterns
- Global commands mean /cca-review and /cca-scout work from any project folder

**Tests:** 483/483 passing (13 suites — no new test files, count increase from existing suites)

**Lessons:**
- Project-scoped commands (`.claude/commands/`) only work when Claude Code is launched from that folder. Copy to `~/.claude/commands/` for global availability.
- Reddit JSON API `top` without `t=month` param only returns ~24hr top. Need to add time range support to reddit_reader.py.
- CCA scope boundary prevents installing tools outside the project folder — batch installs into one non-CCA terminal session.

---

## Session 9 — 2026-03-15

**What changed:**
- SESSION_STATE.md updated to reflect 404/404 tests and session 9 wrap
- CHANGELOG.md created (this file)
- LEARNINGS.md created

**Why:**
- Wrap-only session. No new code. Confirmed all 13 suites pass (404 tests total).
- Identified critical gap: sessions 7+8 work (AG-2, AG-3, CTX-1–5, MEM-5, reddit-intel) was
  never committed despite being complete and tested.

**Tests:** 404/404 passing

**Lessons:**
- Sessions must commit before closing. Having 83+ untracked files across multiple sessions
  is a recovery liability. Commit discipline: ship each task, commit before the next.

---

## Session 8 — 2026-03-08

**What changed:**
- `context-monitor/hooks/auto_handoff.py` — CTX-4: Stop hook blocks exit at critical context
- `context-monitor/hooks/compact_anchor.py` — CTX-5: writes anchor file every N tool calls
- `context-monitor/tests/test_auto_handoff.py` — 27 tests
- `context-monitor/tests/test_compact_anchor.py` — 22 tests
- `memory-system/cli.py` — MEM-5: CLI viewer (list/search/delete/purge/stats)
- `memory-system/tests/test_cli.py` — 28 tests
- `agent-guard/ownership.py` — AG-2: ownership manifest CLI
- `agent-guard/tests/test_ownership.py` — 27 tests
- `.claude/commands/ag-ownership.md` — slash command
- CTX-1 bug fix: transcript format corrected (entry["message"]["usage"] for assistant entries)
- `context-monitor/tests/test_meter.py` — grew from 33 to 36 tests

**Why:**
- Context Monitor frontier completion (CTX-4/5 were the last two hooks)
- Memory system CLI gives users introspection into stored memories
- Ownership manifest helps multi-agent sessions detect file contention

**Tests:** 321/321 passing (sessions 7+8 combined, before credential_guard + reddit_reader)

**Lessons:**
- Stop hook block format: `{"decision": "block", "reason": "..."}` — different from PreToolUse
  which uses `hookSpecificOutput.permissionDecision`
- argparse subparsers don't inherit parent options — add `--project` to each subcommand

---

## Session 7 — 2026-03-01 (approx)

**What changed:**
- `reddit-intelligence/` — full plugin: reddit_reader.py, 43 tests, ri-scan/ri-read/ri-loop commands
- `reddit-intelligence/tests/test_reddit_reader.py` — 43 tests
- `.claude/commands/reddit-intel/` — symlinks to plugin commands
- `agent-guard/hooks/credential_guard.py` — AG-3: credential-extraction guard
- `agent-guard/tests/test_credential_guard.py` — 40 tests
- `context-monitor/hooks/meter.py` — CTX-1: token counter PostToolUse hook
- `context-monitor/hooks/alert.py` — CTX-3: PreToolUse alert for expensive tools
- `context-monitor/statusline.py` — CTX-2: ANSI statusline
- `context-monitor/tests/test_meter.py` — 33 tests
- `context-monitor/tests/test_alert.py` — 24 tests

**Why:**
- Context Monitor and Agent Guard frontiers largely completed in this session block
- reddit-intel provides ongoing community signal research for frontier validation

**Tests:** Suites passing; exact count captured in session 8

**Lessons:**
- Transcript path: `project_hash = os.getcwd().replace('/', '-')` → `~/.claude/projects/<hash>/<session>.jsonl`
- Real Claude Code transcripts: usage at `entry["message"]["usage"]`, not `entry["usage"]`

---

## Sessions 1–6 — 2026-02-19 to 2026-03-01

**What changed (cumulative):**
- Frontier 1 (memory-system): MEM-1 schema, MEM-2 capture hook, MEM-3 MCP server, MEM-4 /handoff, MEM-5 CLI
- Frontier 2 (spec-system): SPEC-1–6 slash commands + guard hook
- Frontier 4 (agent-guard): AG-1 mobile approver (iPhone push via ntfy.sh)
- Foundation: CLAUDE.md, PROJECT_INDEX.md, SESSION_STATE.md, ROADMAP.md, MASTER_ROADMAP.md
- Research: reddit_scout.py, EVIDENCE.md, browse-url global skill

**Why:**
- Initial project build-out — all five frontiers scoped and first three completed

**Tests:** 157/157 passing (as of session 6)

**Lessons:**
- PreToolUse deny: `hookSpecificOutput.permissionDecision: "deny"` — top-level `decision: "block"` silently fails
- Anthropic key regex must include hyphens: `sk-[A-Za-z0-9\-]{20,}` not `sk-[A-Za-z0-9]{20,}`
- Memory ID suffix: 8 hex chars minimum (3-char caused collisions at 100 rapid-fire creates)

---

## Session 21 — 2026-03-16

**What changed:**
- `self-learning/journal.py` — 6 trading event types (bet_placed, bet_outcome, market_research, edge_discovered, edge_rejected, strategy_shift), trading domain, get_trading_metrics(), trading-stats CLI
- `self-learning/reflect.py` — 4 trading pattern detectors (losing_strategy, research_dead_end, negative_pnl, strong_edge_discovery), trading metrics in report output
- `self-learning/strategy.json` — trading section (min_sample_bets, min_liquidity, win_rate_alert_below, etc.) + 4 bounded params
- `self-learning/tests/test_self_learning.py` — 24 new tests (51 -> 75)
- `spec-system/commands/design-review.md` — NEW: multi-persona design review (4 expert personas)
- `.claude/commands/spec-design-review.md` — NEW: thin wrapper for /spec:design-review
- `spec-system/commands/design.md` — Section 1b "Design References" for UI/visual features
- `MASTER_TASKS.md` — MT-0/MT-2/MT-3/MT-4 status updated to COMPLETE

**Why:**
- MT-0: Kalshi self-learning integration — build the trading domain schema in CCA as R&D before deploying to polymarket-bot
- MT-3: Multi-persona design review catches blind spots that single-perspective reviews miss
- MT-4: Design vocabulary ensures professional-quality UI from the spec phase

**Tests:** 783/783 passing (24 new)

**Lessons:**
- Edit tool refuses after system-reminder clears file context — read immediately before editing files in spec-system/ or other dirs that trigger CLAUDE.md injection

---

## Session 23 — 2026-03-16

**What changed:**
- `reddit-intelligence/findings/nuclear_queue_anthropic.json` — 75 posts fetched and classified
- `reddit-intelligence/findings/nuclear_progress_anthropic.json` — scan complete
- `reddit-intelligence/findings/NUCLEAR_REPORT_anthropic.md` — full report: 0 BUILD, 6 REF, 65 FAST-SKIP
- `reddit-intelligence/findings/nuclear_queue_algotrading.json` — 98 posts fetched and classified
- `reddit-intelligence/findings/nuclear_progress_algotrading.json` — scan complete
- `reddit-intelligence/findings/NUCLEAR_REPORT_algotrading.md` — full report: 0 BUILD, 4 REF, 3 REF-PERSONAL
- `FINDINGS_LOG.md` — 35 new entries (r/Anthropic + r/algotrading)
- `SESSION_STATE.md` — session 23 log

**Why:**
- Session 22 resume prompt specified nuclear scans for r/Anthropic and r/algotrading as top priorities
- r/Anthropic: validate whether general Anthropic sub has CCA-relevant signal (answer: no, ~85% politics noise)
- r/algotrading: find prediction-market infrastructure for Polybot (found PMXT: free orderbook data)

**Tests:** 783/783 passing (no code changes)

**Lessons:**
- r/Anthropic is ~85% politics/corporate noise — not worth nuclear scanning for CCA
- r/algotrading is domain-specific — only prediction-market posts have Polybot relevance
- r/ClaudeCode remains the ONLY high-signal sub for CCA frontiers
- Title-based triage (learned Session 22) saved massive tokens — applied successfully to both subs
- All 4 nuclear scans now COMPLETE: 411 total posts scanned across 4 subreddits

---

## Session 24b (Continuation) — 2026-03-16

**What changed:**
- FINDINGS_LOG.md — 3 new entries (151 total): mass-building post, ACE trace analysis, traul comms search
- MASTER_TASKS.md — 3 new master tasks (MT-6, MT-7, MT-8) with full lifecycle requirements
- LEARNINGS.md — New Severity 3 entry: "Building without testing/validation is wasted work"
- SESSION_STATE.md — Updated with Session 24b work + revised next priorities

**Why:**
- Matthew requested reviews of 3 Reddit posts (one flagged as "potentially huge")
- Matthew directed: expand nuclear scanner, add iPhone remote control task, and ensure all work has full lifecycle (research/plan/build/test/validate/backtest/iterate)
- Matthew's key directive: "building doesn't mean shit without legitimate framework, testing, and proven ideas and success"

**Tests:** 800/800 passing

**Lessons:**
- ACE framework's RLM Reflector pattern (programmatic trace querying) is the highest-signal self-learning upgrade found in 411+ posts scanned
- Every MT now requires explicit lifecycle documentation — not just "build X" but the full validation chain
- ROADMAP.md still stale (Session 1) — must be updated next session (5-minute fix deferred 23 sessions)

---
## Session 26 — 2026-03-17

**What changed:**
- `self-learning/trace_analyzer.py` — NEW: MT-7 implementation. 7 classes: TranscriptEntry, TranscriptSession, RetryDetector, WasteDetector, EfficiencyCalculator, VelocityCalculator, TraceAnalyzer. CLI entry point with --json flag.
- `self-learning/tests/test_trace_analyzer.py` — NEW: 50 tests covering all 7 classes (TDD green-field)
- `SESSION_STATE.md` — updated to Session 26, next priority queue
- `PROJECT_INDEX.md` — updated test count to 850/850, new file entries, session history row

**Why:**
- MT-7 trace analysis research was 100% complete (TRACE_ANALYSIS_RESEARCH.md had full schema + 6 pattern defs). Implementation was the logical next step. Tool validates against real data immediately — 3 transcripts analyzed, scores 15/85/40.

**Tests:** 850/850 passing (21 suites)

**Lessons:**
- SESSION_STATE.md is the #1 retry-loop offender in real transcript analysis (5-8 consecutive Edits detected). This is expected for doc-update patterns; orientation files should probably be exempted from RetryDetector the same way WasteDetector exempts them.
- trace_analyzer validates immediately against real data with no schema changes needed — TRACE_ANALYSIS_RESEARCH.md was thorough enough to go straight to code.

---


## Session 36 — 2026-03-17

**What changed:**
- `.claude/commands/cca-wrap.md` — exit loop fix + validate_strategies (6h) + Sentinel evolve (6g.5)
- `.claude/commands/cca-auto.md` — exit loop fix
- `.claude/commands/cca-nuclear-wrap.md` — exit loop fix
- `self-learning/improver.py` — SentinelMutator class (mutate_from_failure, cross_pollinate, scan_weaknesses), Improver.evolve(), MUTATION_STRATEGIES dict
- `self-learning/tests/test_sentinel.py` — 26 tests for Sentinel
- `self-learning/improvements.jsonl` — 6 proposals from 3 real transcript traces
- `FINDINGS_LOG.md` — 5 new reviews (usage tracker, devtools, receipts, 25 tips, Anthropic harness)
- `reddit-intelligence/github_evaluations.jsonl` — 30 repos from 4 GitHub queries

**Why:**
- Exit loop: Claude kept saying "Done."/"Exit." after session wrap — no terminal stop instruction
- Sentinel: Matthew's directive for X-Men Sentinel-style adaptive self-learning
- MT-10: Generate real data for 5-session validation run
- MT-11: First live GitHub scan to find frontier-relevant repos

**Tests:** 1428/1428 passing (+26 sentinel)

**Lessons:**
- Exit loop is an LLM behavior pattern — completion signals ("done") trigger self-response loops. Fix with explicit "STOP RESPONDING" in command templates.
- Don't stop between /cca-init and /cca-auto to explain things — just keep working.

---

## Session 37 — 2026-03-17

**What changed:**
- `self-learning/improver.py` — Sentinel mutation dialed to 5-10% (MAX_MUTATIONS_PER_CYCLE: 5->2, MAX_MUTATION_DEPTH: 3->2)
- `self-learning/strategy.json` — scan limit params (max_consecutive_scan_sessions: 3, scan_cooldown_build_sessions: 2)
- `.claude/commands/cca-auto.md` — scan limit enforcement + context budget for wrap (stop at 60%, not 75%)
- `self-learning/batch_report.py` — NEW: aggregate trace health CLI (score distribution, retry hotspots, waste stats)
- `self-learning/tests/test_batch_report.py` — 13 tests
- `agent-guard/path_validator.py` — NEW: AG-7 dangerous path + command detection (system dirs, traversal, rm -rf, dd, curl|bash)
- `agent-guard/tests/test_path_validator.py` — 30 tests
- `FINDINGS_LOG.md` — 3 new GitHub repo evaluations (engram 1.5K, hooks-mastery 3.3K, multi-agent-coordination)
- MT-10: 31-session aggregate trace analysis (avg score 70, PROJECT_INDEX.md 74% retry rate)

**Why:**
- Sentinel 20% was arbitrary and risky — Matthew requested conservative 5-10% ceiling
- Scan limit: too many consecutive scan sessions without building — need to ship code
- Context budget: wrap self-learning ritual needs 15-20% context, was being squeezed out
- batch_report validates trace_analyzer on real data and provides ongoing health monitoring
- path_validator addresses BUILD findings from r/vibecoding (GPT wiped F: drive, Codex deleted S3)

**Tests:** 1471/1471 passing (+43: 13 batch_report, 30 path_validator)

**Lessons:**
- TraceAnalyzer API: constructor takes path string, not session object. Analyze() returns flat dict (waste/retries/efficiency/velocity), not nested detectors dict.
- PROJECT_INDEX.md retried in 74% of sessions — biggest single efficiency win. Next session should restructure or cache.

---

## Session 43 — 2026-03-18

**What changed:**
- `self-learning/journal.jsonl` — MT-10 validation 3/5 event logged (4 transcripts, avg 71.25)
- `FINDINGS_LOG.md` — 7 new findings: Recon Tamagotchi, 14yr journals, vibe coding, interactive, design skills, harness setups, TraderAlice
- `design-skills/design-guide.md` — Added Rules Do/Don't, Quality Gates, external design references (typeui.sh)
- `self-learning/SKILLBOOK.md` — 4 new strategies (S10-S13), APF updated to 31.4%, growth metrics through S43
- `reddit-intelligence/profiles.py` — r/ClaudeAI needle_ratio_cap=0.4, tightened keywords
- `LEARNINGS.md` — PROJECT_INDEX.md retry hotspot (severity 2), r/ClaudeAI classifier (severity 1)
- `SESSION_STATE.md` — Full 5-sub-session documentation

**Why:**
- MT-10 Phase 2 validation (session 3/5) — measuring self-learning system effectiveness across 37 real sessions
- MT-9 Phase 4 — deep-reading r/ClaudeAI NEEDLE posts for frontier intelligence
- Matthew-requested reviews (3 URLs) — design skills, harness setups, trading bot
- Self-learning expansion — encoding cross-project learnings as actionable strategies

**Tests:** 1552/1552 passing (38 suites, no changes)

**Lessons:**
- Always Read source files before calling functions — wasted cycles guessing class/method names on improver.py, journal.py
- r/ClaudeAI classifier at 76% NEEDLE is too loose — fixed with needle_ratio_cap=0.4
- Cross-project strategies (S10-S13) strengthen the self-learning system beyond CCA-specific patterns

---

## Session 50 — 2026-03-19

**What changed:**
- `.claude/commands/cca-init.md` — Added Step 2.5: cross-chat inbox check (POLYBOT_TO_CCA.md)
- `CROSS_CHAT_INBOX.md` — Marked CUSUM threshold request as DELIVERED
- `~/.claude/cross-chat/CCA_TO_POLYBOT.md` — First-ever responses: CUSUM h=5.0 analysis, Kelly/FLB/Bayesian research, bet sizing review, meta labeling features

**Why:**
- 3 URGENT cross-chat requests from Kalshi S105-S108 had been unanswered for 24h
- Cross-chat communication gap: /cca-init never checked the inbox
- Matthew requested objective review of live bet sizing and values

**Tests:** 1768/1768 passing (44 suites)

**Lessons:**
- Research agents timeout when given 4+ web search topics. Break into 1-topic-per-agent.
- Cross-chat outbox was empty for entire project lifetime — add inbox check to init sequences.

---
