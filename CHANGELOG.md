# ClaudeCodeAdvancements — Changelog
# Append-only. Never truncate.

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
