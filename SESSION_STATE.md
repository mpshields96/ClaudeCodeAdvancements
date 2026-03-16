# ClaudeCodeAdvancements — Session State
# Update at end of every session before closing.

---

## Current State (as of Session 16 — 2026-03-15)

**Phase:** Implementation session COMPLETE. Committed sessions 10-15 backlog + session 16 work. Built USAGE-1 token counter (44 tests), /arewedone structural checker (50 tests), upgraded /cca-wrap with self-learning Review & Apply phase. Installed claude-devtools, Claude Usage Bar, Claude Island. All 568 tests passing across 17 suites. 7/7 modules pass structural check.
**Next session starts at:** Run /cca-init. Priority: (1) Launch Claude Island when Kalshi chats idle — test hook safety. (2) Complete Claude Usage Bar OAuth setup. (3) Maestro retry (check for version > v0.2.4). (4) Implement next BUILD: OTel metrics integration for USAGE-1. (5) Push to remote.

---

## What Was Done in Session 16 (2026-03-15)

### Implementation — Top BUILD Candidates from Nuclear Scan

**Commit backlog cleared:**
- Committed all sessions 10-15 work in single clean commit (0581d17)
- 28 files, 5604 insertions — revertable with `git revert 0581d17`

**USAGE-1: Token Counter CLI (NEW — usage-dashboard/usage_counter.py)**
- Reads Claude Code transcript JSONL for per-session token/cost breakdown
- Supports sonnet/opus/haiku pricing models
- Commands: sessions, session <id>, today, week, project [path]
- Revealed: $516.94 total across 11 CCA sessions
- 44 tests, all passing

**/arewedone: Structural Completeness Checker (NEW — usage-dashboard/arewedone.py)**
- Scans all 7 modules for: CLAUDE.md, source files, tests, test pass/fail
- Detects code stubs (TODO/FIXME/NotImplementedError) excluding test fixtures
- Reports uncommitted files, doc freshness, syntax errors
- --quiet mode for CI-style exit code (0=pass, 1=issues)
- 50 tests, all passing
- Found and fixed: missing CLAUDE.md in reddit-intelligence/ and self-learning/

**cca-wrap upgraded:**
- Added "Review & Apply" self-learning phase
- Runs reflect.py at session end, logs patterns, suggests rule updates

**External tools installed:**
- claude-devtools v0.4.8 — `brew install --cask` (read-only session log viewer)
- Claude Usage Bar v0.0.6 — /Applications (needs OAuth setup)
- Claude Island v1.2 — /Applications (NOT launched — auto-installs hooks, could affect Kalshi chats)

**Tests:** 568/568 passing (17 suites — 94 new tests)

---

## CRITICAL: Uncommitted Work From Sessions 7+8

All files below exist on disk and tests pass, but have never been committed. Commit first:

```bash
git add agent-guard/hooks/credential_guard.py
git add agent-guard/ownership.py
git add agent-guard/tests/test_credential_guard.py
git add agent-guard/tests/test_ownership.py
git add context-monitor/hooks/
git add context-monitor/statusline.py
git add context-monitor/tests/
git add memory-system/cli.py
git add memory-system/tests/test_cli.py
git add reddit-intelligence/
git add .claude/commands/ag-ownership.md
git add .claude/commands/cca-auto.md
git add .claude/commands/cca-init.md
git add .claude/commands/cca-review.md
git add .claude/commands/cca-wrap.md
git add .claude/commands/reddit-intel/
git add .claude/commands/reddit-research.md
git add FINDINGS_LOG.md
git add .claude/settings.local.json
git add CLAUDE.md
git add SESSION_STATE.md
```

Then commit with a message covering sessions 7+8 deliverables.

---

## What Was Done in Session 15 (2026-03-15)

### Nuclear Scan Session 2 — COMPLETED
- Reviewed remaining 65 posts (33 fast-skip + 32 deep-read)
- Nuclear scan now COMPLETE: all 138 posts processed, 110 unique reviews
- Final stats: 5 BUILD, 23 ADAPT, 20 REFERENCE, 6 SKIP, 57 FAST-SKIP
- Special flags: 1 polybot-relevant, 3 maestro-relevant, 9 usage-dashboard
- NUCLEAR_REPORT.md finalized with ranked BUILD candidates and grouped ADAPT patterns
- FINDINGS_LOG.md expanded from 54 to 82 entries
- Top BUILD candidates: (1) claude-devtools 879pts, (2) OTel Metrics 807pts, (3) Self-Improvement Loop 269pts, (4) Claude Island 309pts, (5) Usage Menu Bar 282pts

### Notes
- Maestro retry POSTPONED to 2026-03-16 (Kalshi bot running in terminal tonight)
- Uncommitted work from sessions 7-15 still needs committing (CRITICAL)

**Tests:** 517+ passing (15 suites)

---

## What Was Done in Session 14 (2026-03-15)

### Nuclear Scan Batch 1
- Reviewed 45/110 posts from r/ClaudeCode (Top > Year)
- 2 BUILD, 8 ADAPT, 9 REFERENCE, 5 SKIP, 21 FAST-SKIP
- Signal rate: 22.2% (BUILD+ADAPT / reviewed)
- Top BUILD: OTel metrics integration, claude-devtools desktop app
- Progress saved to `reddit-intelligence/findings/nuclear_progress.json`
- Interim report at `reddit-intelligence/findings/NUCLEAR_REPORT.md`
- 22 new entries in FINDINGS_LOG.md (54 total)

### Self-Learning System (NEW)
- `self-learning/journal.py` — structured append-only event log (JSONL)
- `self-learning/reflect.py` — pattern detection + strategy recommendations
- `self-learning/strategy.json` — tunable parameters (v1)
- `self-learning/tests/test_self_learning.py` — 34 tests, all passing
- `.claude/commands/cca-nuclear-wrap.md` — nuclear wrap command with self-learning integration
- 5 journal entries logged (1 batch, 2 BUILD verdicts, 1 pattern, 1 session outcome)
- 10 learnings captured

### Key Learnings
- CC natively emits OTel metrics — USAGE-1 should use this
- MCP tools consume 70k+ tokens even when unused (#1 context killer)
- ENABLE_LSP_TOOL hidden flag (50ms vs 30-60s navigation)
- evolve-yourself pattern: frequency-based skill auto-create at 3x/day

**Tests:** 517/517 passing (15 suites — includes 34 new self-learning tests)

---

## What Was Done in Session 12 (2026-03-15)

### Master Window Project + Research Deep Dive

**Reddit reviews (14 posts this session, 22 total in FINDINGS_LOG):**
- YoYo self-evolving agent (ADAPT — self-learning journal loop, 941pts)
- Crucix intelligence center (SKIP — data dashboard, not agent management)
- Maestro multi-session orchestrator (BUILD — 476pts, grid UI, macOS native)
- Maestro teaser post (REFERENCE — 424pts, confirms community demand)
- Agent Teams full walkthrough (ADAPT — sendMessage pattern, Cozempic pruner)
- Personal Claude setup / Adderall post (same as Maestro — already logged)

**Multi-agent tool research (15 tools evaluated):**
- Claude Squad, Recon, Agent Deck, Codeman, NTM, claude-tmux, Claude Dashboard,
  IttyBitty, CCManager, Amux, claude-code-monitor, claude-code-dashboard, TmuxCC,
  tmux-claude-code, Maestro

**Infrastructure built:**
- Maestro v0.2.4 built from source (Tauri + Rust, 2m55s compile)
  - CRASHED: macOS 15.6 beta SDK incompatibility (_NSUserActivityTypeBrowsingWeb symbol)
  - .dmg saved at /tmp/maestro-build/target/release/bundle/dmg/
- Claude Squad v1.0.17 installed (brew install claude-squad)
- tmux 3-session workspace configured and tested (20/20 tests passing):
  - Window 0: cca (ClaudeCodeAdvancements, normal perms)
  - Window 1: kalshi-1 (polymarket-bot, --dangerously-skip-permissions)
  - Window 2: kalshi-2 (polymarket-bot, --dangerously-skip-permissions)
- `~/.local/bin/dev-start` updated with auto-launch + idempotent re-attach
- `~/.local/bin/cs-start` created (Claude Squad launcher, backup option)

**Architecture designed:**
- Self-learning Polybot journal + strategy feedback loop (YoYo pattern adapted for trading)
- Cross-chat coordination via shared journal file
- Master plan documented in SESSION_STATE.md for future session persistence

**Tests:** 483/483 passing (no code changes to CCA modules)

---

## What Was Done in Session 11 (2026-03-15)

### Research + Tooling — Reddit Reviews + tmux/Recon Install

**Reddit reviews (9 posts — 2 batches):**
- Batch 1: algotrading strategy list (REF-PERSONAL), VEI signal (REF-PERSONAL), "crusade" meme (REF), Beast 6-month tips (ADAPT)
- Batch 2: ClaudePrism academic workspace (REF-PERSONAL), code-commentary (SKIP), Recon tmux dashboard (BUILD), Membase (REF), agtx kanban (REF)

**Key findings captured:**
- LEARNINGS: file-writing hooks trigger system-reminder context burn (Severity 2)
- UserPromptSubmit skill auto-activation hook — new buildable pattern from Beast post
- 3 linked repos to review: github/spec-kit, facetlayer/candle, dimitritholen/raggy

**Infrastructure installed:**
- tmux 3.6a (brew install tmux)
- Rust 1.94.0 (brew install rust)
- Recon v0.1.0 (cargo install, tmux-native CC agent dashboard)
- ~/.tmux.conf with Recon keybindings (prefix+g dashboard, prefix+i next input)
- ~/.local/bin/dev-start script (3-window tmux: CCA + 2 Kalshi bot sessions)

**Framework upgrades:**
- cca-review command: added REFERENCE-PERSONAL verdict (synced to global)
- Memory: user_profile.md, feedback_personal_tools.md
- CHANGELOG, FINDINGS_LOG, SESSION_STATE all updated

**Tests:** 483/483 passing (no code changes)

---

## What Was Done in Session 10 (2026-03-15)

### Framework Upgrade — Session Management + Reddit Pipeline

**New commands:**
- `/cca-wrap` — session end ritual with self-grading, learnings capture, resume prompts
- `/cca-scout` — autonomous subreddit scanner (filters by score, dedupes vs FINDINGS_LOG)

**CLAUDE.md upgrades:**
- Added "URL Review — Auto-Trigger" section (any URL pasted auto-triggers /cca-review)
- Added "Session Commands" reference table (all 7 CCA commands documented)

**Reddit reviews (8 posts):**
- Defuddle URL reading (ADAPT) — incorporated url_reader.py approach
- claude-code-best-practice 15k-star repo (REFERENCE) — confirmed CCA already follows most patterns
- OpenClaw/Public.com autonomous trading (REFERENCE) — flagged for polybot research chat
- CShip statusline (BUILD) — installed, wired into settings.json
- Autoresearch + Ouro Loop (ADAPT) — IRON LAWS prompt generated for polybot
- Session transcript tools (ADAPT) — installed claude-code-transcripts
- RTK token compression (BUILD) — confirmed already installed and working
- iOS shipping best practices (REFERENCE) — CLAUDE.md-as-contract pattern validated

**Infrastructure verified:**
- CShip v1.0.80 — running, statusline configured
- RTK v0.29.0 — running, hook wired
- All 5 /cca-* commands copied to ~/.claude/commands/ (global)
- Mobile approver hook — running
- claude-code-transcripts — installed via Homebrew

**Tests:** 483/483 passing (13 suites) — up from 404 (test count increase is from existing tests, no new test files)

---

## What Was Done in Session 9

Wrap-only session. No new code. Confirmed 404/404 tests passing across 13 suites.

---

## What Was Done in Session 8 (2026-03-08)

### CTX-4: Auto-Handoff Stop Hook (complete — 27 tests)

**File:** `context-monitor/hooks/auto_handoff.py`

**What it does:**
- Runs at session end (Stop hook)
- If context zone is `critical` → blocks exit, asks Claude to run `/handoff`
- If context zone is `red` → warns to stderr (non-blocking by default)
- If `HANDOFF.md` was written in the last 5 minutes → always allows exit (anti-loop)
- Silent pass-through for green/yellow/unknown

**Anti-loop mechanism:** `handoff_is_fresh(path, max_age_minutes)` checks mtime.

**Output format (Stop hook):**
- Allow: `{}`
- Block: `{"decision": "block", "reason": "..."}`

**Environment variables:**
- `CLAUDE_CONTEXT_STATE_FILE` — state file (default: `~/.claude-context-health.json`)
- `CLAUDE_CONTEXT_HANDOFF_PATH` — HANDOFF.md path (default: `./HANDOFF.md`)
- `CLAUDE_CONTEXT_HANDOFF_AGE` — max age minutes before re-triggering (default: 5)
- `CLAUDE_CONTEXT_HANDOFF_RED` — set "1" to also block on red zone
- `CLAUDE_CONTEXT_HANDOFF_DISABLED` — set "1" to disable

**Wired:** `Stop` hook in `.claude/settings.local.json`

---

### CTX-5: Compaction Anchor Hook (complete — 22 tests)

**File:** `context-monitor/hooks/compact_anchor.py`

**What it does:**
- Runs as PostToolUse hook (alongside meter.py)
- Every N tool calls (default: 10), writes `.claude-compact-anchor.md` to project root
- File contains: context zone/%, session ID prefix, last tool called, instructions to re-read SESSION_STATE.md after compaction
- Stores `turn_count` as a machine-parseable comment for round-trip integrity
- Atomic write via temp file

**Key functions:**
- `should_write(turn_count, write_every)` — True at turn 0 and every N turns
- `build_anchor_content(state, tool_name, turn_count, session_id)` — builds markdown
- `load_anchor_turn_count(path)` — reads back `<!-- turn_count: N -->` from anchor

**Environment variables:**
- `CLAUDE_CONTEXT_STATE_FILE` — state file path
- `CLAUDE_CONTEXT_ANCHOR_PATH` — anchor file path (default: `./.claude-compact-anchor.md`)
- `CLAUDE_CONTEXT_ANCHOR_EVERY` — write interval in turns (default: 10)
- `CLAUDE_CONTEXT_ANCHOR_DISABLED` — set "1" to disable

**Wired:** second hook in `PostToolUse` array in `.claude/settings.local.json`

---

### MEM-5: CLI Memory Viewer (complete — 28 tests)

**File:** `memory-system/cli.py`

**Usage:**
```bash
python3 memory-system/cli.py list                           # Current project memories
python3 memory-system/cli.py list --project myapp          # Specific project
python3 memory-system/cli.py list --global                 # Global memories
python3 memory-system/cli.py list --all                    # All projects
python3 memory-system/cli.py list --confidence HIGH        # Filter by confidence
python3 memory-system/cli.py list --type decision          # Filter by type
python3 memory-system/cli.py search "SQLite"               # Keyword/tag search
python3 memory-system/cli.py delete mem_20260219_143022_abc  # Delete by ID
python3 memory-system/cli.py purge                         # Remove expired memories
python3 memory-system/cli.py stats                         # Summary counts
```

**TTL by confidence:** HIGH=365 days, MEDIUM=180 days, LOW=90 days

---

### AG-2: Ownership Manifest (complete — 27 tests)

**Files:** `agent-guard/ownership.py`, `agent-guard/tests/test_ownership.py`, `.claude/commands/ag-ownership.md`

**What it does:**
- CLI tool: `python3 agent-guard/ownership.py`
- Reads last N git commits (default: 20), maps which files were changed by which session
- Detects "conflict risk" files — those appearing in 2+ commits in the window
- Shows uncommitted changes (files in-flight this session)
- Outputs Markdown report with columns: File | Last Session | Date | Commit
- Session label extraction: recognizes "AG-1:", "CTX-3:", "Session 6:" prefixes in commit subjects
- Available as `/ag-ownership` slash command

**Options:** `--commits N`, `--hours N`, `--conflicts-only`, `--output PATH`

---

### CTX-3: Alert Hook (complete — 24 tests)

**File:** `context-monitor/hooks/alert.py`

PreToolUse hook. Silent for cheap tools (Read/Glob/Grep/TodoWrite). Warns before expensive tools (Agent/WebSearch/WebFetch/Bash/Write/Edit) in red/critical zones. Opt-in blocking via `CLAUDE_CONTEXT_ALERT_BLOCK=1`.

---

### CTX-2: Statusline (complete)

**File:** `context-monitor/statusline.py`

Reads native `context_window.used_percentage` from stdin JSON (Claude Code provides this natively). ANSI-colored bar: `CTX [======    ] 45% ok   | $0.02 | Sonnet`. Wired in `~/.claude/settings.json` globally.

---

### CTX-1: Context Meter Hook (complete — 36 tests)

**Files:**
- `context-monitor/hooks/meter.py` — PostToolUse hook
- `context-monitor/tests/test_meter.py` — 36 tests

**What it does:**
1. Reads session transcript JSONL after every tool call
2. Extracts total prompt tokens from `entry["message"]["usage"]` (assistant entries)
3. Computes % of configured window (default 200k)
4. Classifies: green (<50%) / yellow (50–70%) / red (70–85%) / critical (≥85%)
5. Writes state atomically to `~/.claude-context-health.json`

**Transcript path derivation:**
```python
project_hash = os.getcwd().replace('/', '-')  # e.g. '-Users-matthewshields-...'
path = ~/.claude/projects/<project_hash>/<session_id>.jsonl
```

---

### AG-3: Credential-Extraction Guard (complete — 40 tests)

**File:** `agent-guard/hooks/credential_guard.py`

PreToolUse hook. Flags Bash commands that could extract env vars, read .env files, or exfiltrate credentials.

---

### reddit-intel plugin (complete — 43 tests)

**Files:** `reddit-intelligence/` — full plugin including reddit_reader.py, test suite, commands.

---

## What Was Done in Session 7

### reddit-intel Claude Code Plugin (complete)

`.claude/commands/reddit-intel/` contains symlinks to `reddit-intelligence/commands/ri-*.md`.
Available in this project as `/reddit-intel:ri-scan`, `/reddit-intel:ri-read`, `/reddit-intel:ri-loop`.

---

## What Was Done in Session 6

### AG-1: Mobile Approver iPhone Hook (complete — 36 tests)
- `agent-guard/hooks/mobile_approver.py` — PreToolUse hook using ntfy.sh
- Sends push notification to iPhone with Allow/Deny action buttons on lock screen
- Claude waits up to 60s for response; fails open if no network or no topic configured

### Reddit Scout + browse-url global skill (complete)

---

## Frontier Status

| Frontier | Module | Status | Tests | Next Action |
|----------|--------|--------|-------|-------------|
| 1: Persistent Memory | memory-system/ | MEM-1 ✅ MEM-2 ✅ MEM-3 ✅ MEM-4 ✅ MEM-5 ✅ | 94/94 | Frontier complete |
| 2: Spec System | spec-system/ | SPEC-1–6 ✅ | 26/26 | Frontier complete |
| 3: Context Monitor | context-monitor/ | CTX-1 ✅ CTX-2 ✅ CTX-3 ✅ CTX-4 ✅ CTX-5 ✅ | 109/109 | Frontier complete |
| 4: Agent Guard | agent-guard/ | AG-1 ✅ AG-2 ✅ AG-3 ✅ | 103/103 | Frontier nearly complete |
| 5: Usage Dashboard | usage-dashboard/ | USAGE-1 ✅ /arewedone ✅ | 94/94 | OTel integration, alert hook |

---

## Total Test Count

| Module | Tests | Status |
|--------|-------|--------|
| memory-system (capture) | 37 | 37/37 passing |
| memory-system (mcp_server) | 29 | 29/29 passing |
| memory-system (cli) | 28 | 28/28 passing |
| spec-system | 26 | 26/26 passing |
| research (reddit_scout) | 29 | 29/29 passing |
| agent-guard (mobile_approver) | 36 | 36/36 passing |
| agent-guard (ownership) | 27 | 27/27 passing |
| agent-guard (credential_guard) | 40 | 40/40 passing |
| context-monitor (meter) | 36 | 36/36 passing |
| context-monitor (alert) | 24 | 24/24 passing |
| context-monitor (auto_handoff) | 27 | 27/27 passing |
| context-monitor (compact_anchor) | 22 | 22/22 passing |
| reddit-intelligence (reader) | 43 | 43/43 passing |
| reddit-intelligence (nuclear_fetcher) | 29 | 29/29 passing |
| self-learning | 34 | 34/34 passing |
| usage-dashboard (usage_counter) | 44 | 44/44 passing |
| usage-dashboard (arewedone) | 50 | 50/50 passing |
| **Total** | **568** | **568/568 passing** |

---

## Key Architecture Decisions (cumulative)

| Decision | Rationale |
|----------|-----------|-
| Memory capture via Stop hook | Stop has `last_assistant_message` — better context than PostToolUse alone |
| Transcript JSONL for explicit memory | `transcript_path` in Stop payload; explicit user "remember/always/never" → HIGH confidence |
| 8-char UUID suffix for memory IDs | 3-char caused collisions at 100 rapid-fire creates. 8-char is collision-resistant. |
| SPEC_GUARD_MODE env var | Default warn-only — never surprises user. Opt-in blocking. |
| `hookSpecificOutput.permissionDecision` | PreToolUse ONLY event using hookSpecificOutput. Top-level `block` silently fails. |
| Stop hook block format | `{"decision": "block", "reason": "..."}` — NOT hookSpecificOutput (different from PreToolUse) |
| Spec system is slash commands | Zero-infrastructure, user-invoked. Only the guard is a hook. |
| Local-first storage (`~/.claude-memory/`) | User owns data. No external dependency. Privacy by default. |
| Transcript format | `entry["message"]["usage"]` for assistant entries. `input + cache_read + cache_create = total`. |
| `--project` per subparser | argparse subparsers don't inherit parent parser options — must add to each subcommand |

---

## Open Items

### USAGE-1: Token counter dashboard
- macOS menu bar app UX (or Streamlit)
- Thinking token visibility (Opus blindsides Pro users)
- Per-session cost tracking

### ADAPT: UserPromptSubmit skill auto-activation hook
- Pattern from "Beast" post (r/ClaudeCode/comments/1oivs81)
- Hook analyzes user prompt for keywords/intent → injects skill activation reminder before Claude processes it
- Uses skill-rules.json with keywords, intent regex, file path triggers, content triggers
- Could auto-activate /spec:requirements when new feature work detected
- Delivery: UserPromptSubmit hook (Python)

### REVIEW: Linked repos from Beast post comments
- `github/spec-kit` — GitHub's own spec-driven dev framework
- `facetlayer/candle` — MCP-based process manager
- `dimitritholen/raggy` — lightweight per-project RAG for dev docs

### INVESTIGATE: compact_anchor.py system-reminder context burn
- CTX-5 writes .claude-compact-anchor.md every 10 turns — may trigger system-reminder token drain
- See LEARNINGS.md entry for details
- Test: check if anchor writes produce system-reminder diffs in transcript JSONL

### INSTALL: ClaudePrism — scientific writing workspace
- Repo: github.com/delibae/claude-prism
- For: academic papers, research writing (psychiatry)
- Local-first, wraps CC as subprocess, LaTeX + PDF preview

### REFERENCE-PERSONAL: Trading/Kalshi resources
- r/algotrading strategy list (534pts) — 40+ basic algo strategies
- VEI volatility expansion signal with Python source (436pts) — fast/slow ATR ratio
- Both bookmarked in FINDINGS_LOG.md

### INVESTIGATE: Cozempic context pruner
- Repo: github.com/Ruya-AI/cozempic (pip install cozempic)
- Prunes duplicate system-reminders and oversized tool outputs that eat context
- Auto-checkpoints team state before compaction
- Directly relevant to CTX-5 compact_anchor investigation
- Found in Agent Teams post comments (r/ClaudeCode/comments/1qz8tyy)

---

## MASTER PLAN: Unified Workspace + Self-Learning Architecture

**Status:** IN PROGRESS — tmux setup complete, self-learning design ready for Polybot adoption

### Part 1: Master Window (COMPLETE)

**Goal:** All Claude Code sessions in one window. Open Terminal, type `dev-start`, everything launches.

**What was built:**
- tmux 3-session workspace via `~/.local/bin/dev-start`
- Window 0: `cca` — ClaudeCodeAdvancements (normal permissions)
- Window 1: `kalshi-1` — Polymarket/Kalshi main chat (--dangerously-skip-permissions)
- Window 2: `kalshi-2` — Polymarket/Kalshi research chat (--dangerously-skip-permissions)
- All sessions auto-launch Claude Code in correct project directories
- Idempotent: re-running `dev-start` attaches to existing session (no duplicates)
- CShip statusline renders correctly in tmux
- Sessions survive Terminal closure (tmux background)

**Keyboard shortcuts:**
- `Ctrl+b, 0/1/2` — jump to CCA / Kalshi Main / Kalshi Research
- `Ctrl+b, w` — visual window picker
- `Ctrl+b, d` — detach (sessions keep running)
- `Ctrl+b, c` — add a new window
- `Ctrl+b, &` — kill current window

**Tools evaluated (15 total):**
- Claude Squad v1.0.17 — INSTALLED (Go TUI, brew install, backup option)
- Maestro v0.2.4 — BUILT but crashes on macOS 15.6 beta (SDK symbol _NSUserActivityTypeBrowsingWeb missing from CoreServices). Retry when off beta or Maestro updates Tauri config.
- Recon — previously installed (tmux popup dashboard)
- Agent Deck, Codeman, NTM, claude-tmux, Claude Dashboard, IttyBitty, CCManager, Amux, claude-code-monitor, claude-code-dashboard, TmuxCC, tmux-claude-code — all evaluated, details in FINDINGS_LOG.md

**Adding/removing sessions:**
- Add: `Ctrl+b, c` then `cd /path/to/project && claude`
- Remove: `Ctrl+b, &` to kill current window
- Or edit `~/.local/bin/dev-start` to change the default template

### Part 2: Self-Learning Polybot Architecture (DESIGNED — needs Polybot adoption)

**Goal:** Kalshi main chat (monitors/bets) and research chat (coding/bugs) learn from outcomes and improve strategy autonomously.

**Architecture (adapted from YoYo self-evolving agent pattern):**

```
┌─────────────────────┐     writes outcomes     ┌──────────────────────┐
│   Kalshi Main Chat   │ ──────────────────────> │                      │
│   (live monitoring)  │                         │   Shared Journal     │
│   /polybot-auto      │ <────────────────────── │   (structured JSON)  │
│                      │     reads strategy      │                      │
└─────────────────────┘                         │   Location: TBD      │
                                                 │   ~/polybot-journal/ │
┌─────────────────────┐     reads outcomes       │   or project-local   │
│  Kalshi Research     │ ──────────────────────> │                      │
│  (coding/infra/bugs) │                         └──────────────────────┘
│  /polybot-autoresearch│
│                      │ ──> updates strategy config based on patterns
└─────────────────────┘
```

**Journal schema (proposed):**
```json
{
  "timestamp": "2026-03-15T21:00:00Z",
  "event_type": "bet_outcome | strategy_update | pattern_detected | error",
  "market_type": "crypto_15m | weather | sports | custom",
  "ticker": "KXBTC15M",
  "side": "yes | no",
  "price_cents": 95,
  "result": "win | loss | void",
  "pnl_cents": 500,
  "confidence": 0.85,
  "conditions": "low_liquidity, post_8pm, high_volatility",
  "strategy_version": "expiry_sniper_v1",
  "notes": "Lost on low-liquidity market — need min liquidity threshold"
}
```

**Self-learning loop (per session start):**
1. Research chat reads journal at `/polybot-auto` or `/polybot-init`
2. Aggregates: win rate by market type, time, conditions, strategy version
3. Detects patterns: "we lose on X conditions" or "strategy Y outperforms Z"
4. Updates strategy config (thresholds, filters, confidence adjustments)
5. Main chat reads updated config at next session start

**Key safeguards:**
- Minimum sample size (N=20) before any strategy change
- Strategy changes are logged with reason (no silent drift)
- Backtesting: replay past outcomes through new strategy before deploying
- Never expose API keys, account balances, or trade history in logs/commits

**What Polybot needs to implement:**
1. Journal writer in main chat (log every bet outcome)
2. Journal reader + pattern detector in research chat
3. Strategy config file that both chats read
4. Reflection step at session start (read journal, summarize learnings)

**Handoff to Polybot:** Tell either Kalshi chat:
> "Read SESSION_STATE.md in /Users/matthewshields/Projects/ClaudeCodeAdvancements — section 'MASTER PLAN Part 2: Self-Learning'. Adopt this architecture for the journal + strategy feedback loop."

### Part 3: Cross-Chat Coordination (FUTURE)

**Problem:** CCA and Polybot can't write to each other's folders (scope boundaries).
**Solution options:**
1. Shared file at `~/.claude-workspace-state.json` (neutral location)
2. Agent Teams sendMessage pattern (file-based inbox per agent)
3. Polybot reads CCA's SESSION_STATE.md (read-only cross-reference)

**Not urgent.** The tmux window switching (Ctrl+b, 0/1/2) makes manual coordination fast enough for now.

### Debugging Issues to Watch

| Issue | Risk | Mitigation |
|-------|------|------------|
| Maestro crash on macOS 15.6 beta | Known | Use tmux + dev-start instead. Retry Maestro after macOS stable or SDK update |
| CShip in tmux | Low (tested, works) | If ANSI breaks, set `TERM=xterm-256color` in tmux.conf |
| Hooks in tmux sessions | Low (tested, works) | Global hooks fire in all sessions. Project hooks fire per CWD |
| Duplicate sessions on re-run | None (fixed) | dev-start checks `tmux has-session` before creating |
| Old Terminal tab sessions | Clean up needed | Close old tabs after wrap commands finish |
| Context burn from 3 concurrent sessions | Medium | Only actively chat with 1-2 at a time. Idle sessions cost zero tokens |
| Credential exposure in logs/commits | CRITICAL | AG-3 credential guard active. Never log keys, balances, or trade data to git |
| Strategy drift in self-learning | Medium | Minimum sample size N=20 before changes. All changes logged with reason |

---

## Session 17 Start Protocol

1. Run /cca-init
2. Run all 17 test suites — confirm 568+ passing
3. Launch Claude Island (only when Kalshi chats are NOT active — it auto-installs hooks)
4. Complete Claude Usage Bar OAuth setup (open app, sign in, paste auth code)
5. Retry Maestro install (check for version > v0.2.4)
6. Implement next BUILD: OTel metrics integration for usage-dashboard
7. Push all commits to remote (2 new commits from Session 16)
8. State what you're building before touching any file
