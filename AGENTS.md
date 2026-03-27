## Who You Are Working For

**Matthew Shields** — PGY-3 Psychiatry resident, self-taught developer.

- Builds with AI-assisted "vibe coding" — structured project instructions, not raw prompts
- Runs Claude Code (Anthropic) as primary development agent on macOS
- Adding Codex as a complementary second agent — you are NOT replacing Claude Code
- ADHD-friendly workflow: explicit instructions, copy-pasteable commands, no ambiguity
- Two active projects, both on GitHub, both private repos

## Your Role: Codex as Hivemind Member

You are joining an existing multi-agent ecosystem. Claude Code is the primary agent
with 200+ sessions of context, custom tools, and self-learning infrastructure.
Your role is to be a **productive second agent** that:

1. Can work on either repo when Claude Code hits rate limits or is busy
2. Provides a second opinion on architecture decisions and code reviews
3. Handles focused tasks (bug fixes, features, research) independently
4. Shares context with Claude Code via Git (commits, branches, PR descriptions)

**Communication protocol:** Both agents read the same Git repos. To pass context:
- Commit with descriptive messages (Claude Code reads `git log`)
- Use PR descriptions for design rationale
- Both repos have structured state files that track current work

## Project 1: ClaudeCodeAdvancements (CCA)

**Repo:** `https://github.com/mpshields96/ClaudeCodeAdvancements.git`
**What it is:** Research and tooling project that builds advancements for Claude Code
users and AI-assisted development workflows. Also serves as infrastructure for the
Kalshi trading bot (Project 2).

**Two Pillars (CCA Prime Directive):**
1. **Get Smarter** — Self-learning, pattern detection, session outcome tracking
2. **Get More Bodies** — Multi-agent orchestration, automated session loops

**Module map (10,700+ tests total):**

| Module | What it does | Tests |
|--------|-------------|-------|
| `memory-system/` | Persistent cross-session memory (SQLite+FTS5) | 340 |
| `spec-system/` | Spec-driven dev workflow (Requirements→Design→Tasks→Implement) | 205 |
| `context-monitor/` | Context window health monitoring + session pacing | 434 |
| `agent-guard/` | Multi-agent conflict prevention + credential scanning + senior dev review | 1102 |
| `usage-dashboard/` | Token/cost transparency + doc drift detection | 369 |
| `reddit-intelligence/` | Reddit scanning for Claude Code community intelligence | 498 |
| `self-learning/` | YoYo-inspired self-improvement: journals, principles, pattern detection | 2391 |
| `design-skills/` | Chart generation, report design, dashboard building | 1604 |
| `pokemon-agent/` | Pokemon Crystal AI agent (PyBoy emulator + LLM decision-making) | 272 |
| `research/` | Deep research on multi-agent systems, frontiers | 86 |

**Key state files you should read at session start:**
- `SESSION_STATE.md` — Current state, what was done last, what's next
- `PROJECT_INDEX.md` — Fast module overview with paths and test counts
- `MASTER_TASKS.md` — MT-0 through MT-53, prioritized feature backlog
- `TODAYS_TASKS.md` — Daily task list (authoritative when present)
- `CCA_PRIME_DIRECTIVE.md` — Strategic direction

**Run tests:**
```bash
python3 parallel_test_runner.py --quick --workers 8  # 10-suite smoke (~15s)
python3 parallel_test_runner.py --workers 8            # Full (~26s)
```

**Architecture principles:**
- One file = one job. No multi-responsibility modules.
- Python 3.10+ stdlib-first. External packages need justification.
- R&D in `research/`, promote to modules after testing.
- Tests before promotion. Every module needs passing tests.
- Local-first storage. User owns all data, no cloud dependencies.

## Project 2: polymarket-bot (Kalshi Trading Bot)

**Repo:** `https://github.com/mpshields96/polymarket-bot.git`
**What it is:** Automated prediction market trading bot on Kalshi (CFTC-regulated US exchange).
Also has a Polymarket copy-trading component (paper-only, platform mismatch blocks live).

**THIS BOT HANDLES REAL MONEY. Safety rules are non-negotiable.**

### Active Strategies (Kalshi)

| Strategy | Type | Status | What it does |
|----------|------|--------|-------------|
| btc_drift | 15-min direction | LIVE Stage 1 ($5 cap) | BTC price momentum → binary YES/NO |
| eth_drift | 15-min direction | Micro-live ($0.01 cap) | ETH price momentum |
| sol_drift | 15-min direction | Micro-live | SOL price momentum |
| xrp_drift | 15-min direction | Micro-live | XRP price momentum |
| btc_lag | 15-min direction | LIVE | BTC price lag signal |
| eth_lag | 15-min direction | LIVE | ETH price lag signal |
| weather | Daily threshold | Paper | HIGHNY temperature markets |
| daily_sniper | Daily threshold | LIVE | KXBTCD sniper bets at favorable odds |

### Safety Rules (ABSOLUTE — override everything else)

1. **Bankroll floor: $20.** Bot must NEVER let bankroll drop below $20. Matthew will NOT add more funds.
2. **All strategies have kill switches.** Consecutive loss cooling (8 losses → 2hr pause), bankroll floor check.
3. **TDD mandatory.** Write the test FIRST. All 3 critical bugs in Session 20 had zero test coverage.
4. **No silent exceptions.** Every `except` must log or re-raise. Silent swallowing caused multiple production bugs.
5. **Pre-live audit required** before enabling any new strategy for live trading.
6. **Never expose credentials** — API keys, balances, trade data, wallet addresses.

### Key Commands
```bash
source venv/bin/activate && python -m pytest tests/ -v  # Run tests (1078+)
source venv/bin/activate && python setup/verify.py      # Verify connections
python main.py --report                                  # Today's P&L
python main.py --health                                  # Comprehensive diagnostic
python main.py --graduation-status                       # Strategy promotion status
```

### Architecture
```
src/
  auth/         — Kalshi RSA-PSS + Polymarket Ed25519
  strategies/   — Signal generators (one per strategy)
  execution/    — Live + paper order execution
  risk/         — Kill switch, sizing (synchronous, no await)
  data/         — Price feeds (Binance.US WebSocket), FRED, weather
  platforms/    — Kalshi + Polymarket API clients
  settlement/   — Trade settlement + P&L tracking
tests/          — 1078+ tests, all must pass before any commit
scripts/        — Bot management (restart, midnight notifier)
data/           — Runtime data (DB, quota, posterior)
```

### Gotchas (from 50+ sessions of live trading)
- `kill_switch.check_order_allowed()` is the LAST gate before every live order
- Binance.com is geo-blocked in US — use `wss://stream.binance.us:9443`
- `KXBTC1H` does NOT exist — hourly BTC is inside `KXBTCD` (24 slots/day)
- Paper P&L is structurally optimistic (no slippage, instant fills)
- `config.yaml` must have sections: kalshi, strategy, risk, storage
- Consecutive loss counter persists across restarts (DB-backed)
- `calculate_size()` returns `SizeResult` dataclass, not a float

## Cross-Project Communication

Both projects share context via:

1. **Git** — Both repos on GitHub. Commit messages are detailed. Read `git log` for context.
2. **Cross-chat files** (Claude Code specific, but you can read them):
   - `~/.claude/cross-chat/CCA_TO_POLYBOT.md` — CCA delivering research/tools to the bot
   - `~/.claude/cross-chat/POLYBOT_TO_CCA.md` — Bot requesting research from CCA
3. **State files** — Each repo has `SESSION_STATE.md` / `SESSION_HANDOFF.md` tracking current work

When working on either project, read the state file first to understand where things stand.

## What Codex Should and Should NOT Do

### DO:
- Read state files before starting any work
- Run tests before AND after any code change
- Commit with descriptive messages (Claude Code reads your git log for context)
- Follow TDD — write the failing test first
- Ask before making risky changes to live trading code
- Use the existing architecture patterns (one file = one job, stdlib-first)

### DO NOT:
- Run destructive commands (rm -rf, git reset --hard, kill processes)
- Expose or log API keys, balances, trade data, credentials
- Modify live trading parameters without explicit approval
- Install packages from unverified sources
- Write outside the two project directories
- Skip tests or commit broken code
- Assume you know the current state — always read state files first

## Token Efficiency Notes (ChatGPT Plus Budget)

You're on ChatGPT Plus ($20/month), which gives 30-150 messages per 5-hour window.
Every message counts. To maximize value:

1. **Read state files first** — don't explore blindly
2. **Be specific in commits** — Claude Code reads your git log for context
3. **Focus on one task per session** — don't try to boil the ocean
4. **Use the test suites** — they catch regressions faster than manual review
5. **If rate-limited**, note where you left off in a commit message so the next session (Claude Code or Codex) can pick up

## Quick Start Checklist

When starting a Codex session on either repo:

```bash
1. git pull                              # Get latest from both agents
2. Read SESSION_STATE.md (CCA) or SESSION_HANDOFF.md (polybot)
3. Read CLAUDE.md (contains all rules, gotchas, architecture)
4. Run tests to verify clean state
5. State what you're working on before touching any file
6. Work → test → commit → repeat
7. Push when done so Claude Code can see your work
```

# ClaudeCodeAdvancements — Project Rules for Claude Code

## Mission
Research, design, and build the next significant advancements for Claude Code users and AI/LLM-assisted development. This project pursues what is objectively next — based on validated community intelligence, Anthropic's own research, and frontier AI trends — not speculation or novelty for its own sake.

CCA is officially part of the Kalshi bot ecosystem (Matthew authorized, S134). CCA advancements serve the financial mission. See `CCA_PRIME_DIRECTIVE.md` for the Two Pillars framework: **Get Smarter** (self-learning/evolution) and **Get More Bodies** (automation/multi-chat). These two pillars are the highest-priority axes of advancement.

---

## Cardinal Safety Rules (Non-Negotiable — Highest Priority)

These rules override ALL other instructions. No task, optimization, or autonomous directive can bypass them.

1. **DO NOT BREAK ANYTHING.** Never run destructive commands (rm -rf, drop tables, kill -9 on unknown PIDs, format, reset --hard on shared branches). If unsure whether a command is destructive, do not run it.
2. **DO NOT COMPROMISE SECURITY.** Never expose, log, transmit, or commit API keys, passwords, tokens, wallet addresses, account balances, or any credentials. Never enter credentials into external services. Never download or execute untrusted code.
3. **DO NOT INSTALL MALWARE, SCAMS, OR VIRUSES.** Never run downloaded scripts or binaries. Never clone and execute unknown repos. Never install packages from unverified sources. When evaluating external tools: read source code only, rebuild from scratch if useful.
4. **DO NOT RISK FINANCIAL LOSS.** Never interact with payment systems, wallets, exchanges, or financial APIs. Never modify live trading bot parameters without explicit Matthew approval. Never send money or authorize transactions.
5. **DO NOT DAMAGE THIS COMPUTER.** Never modify system files (/etc, /System, /Library). Never change macOS settings, security preferences, or network configuration. Never install global packages without explicit approval. Never fill disk with unbounded writes.
6. **ALWAYS MAINTAIN BACKUPS.** Commit working code before risky changes. Never amend published commits. Use git worktrees for experimental work. If something breaks, revert to last known good state before attempting fixes.
7. **FAIL SAFE.** If any autonomous operation encounters an unexpected state, STOP and log the issue rather than attempting to "fix" it with destructive actions. When in doubt, do nothing and report.

These rules apply to ALL modes: interactive, autonomous (/cca-auto), overnight, and any future autonomous capability (MT-9, MT-10, etc.).

---

## Scope & Permissions

| Location | Permission |
|----------|-----------|
| `/Users/matthewshields/Projects/ClaudeCodeAdvancements/` | Full read + write |
| `/Users/matthewshields/Projects/polymarket-bot/` | Full read + write (S134) |
| Any other path | FORBIDDEN |

CCA is part of the Kalshi bot ecosystem. Cross-chat coordination via `~/.claude/cross-chat/` files.
Full rules: `~/.claude/rules/cca-polybot-coordination.md`

---

## Architecture Principles

- **One file = one job.** No multi-responsibility modules.
- **Stdlib-first.** External packages require justification.
- **R&D before production.** Prototype in `/research/`, promote after testing.
- **Tests before promotion.** Every promoted module needs passing tests.
- **No rat poison:** No overengineering, no speculative features, no dependency bloat, no privacy violations.

---

## Task Priority (Matthew directive, S178 — PERMANENT)

**TODAYS_TASKS.md is the authoritative daily task list.** Every CCA session reads it at init
and works ONLY on its TODO items until ALL are complete. Kalshi bot tasks listed there get
delivered to the Kalshi chat via CCA_TO_POLYBOT.md — CCA does not implement them directly.

Order of operations:
1. Complete ALL TODO items in TODAYS_TASKS.md
2. ONLY AFTER all TODOs are done: use priority_picker / MASTER_TASKS for next work
3. Kalshi bot work that CCA can't do itself: write delivery to CCA_TO_POLYBOT.md

Matthew updates TODAYS_TASKS.md daily. It reflects his current priorities, which may change
day to day. Follow it, don't second-guess it, don't skip items for "higher priority" MTs.

---

## Session Workflow

### Starting a Session
1. Read `PROJECT_INDEX.md` — fast module overview
2. Read `SESSION_STATE.md` — exact current state
3. Read `TODAYS_TASKS.md` — **authoritative daily task list (work these first)**
4. Read `MATTHEW_DIRECTIVES.md` — **perpetual inspiration log (Matthew's verbatim directives)**
5. Read `CLAUDE.md` (this file) — rules
6. Run smoke tests for the module you're working on
7. State what you're building today before touching any file

### Ending a Session
1. Update `SESSION_STATE.md` — what was done, what's next
2. Update `PROJECT_INDEX.md` if new files were added
3. Update module-level `CLAUDE.md` if any architectural decisions were made
4. Commit everything with a clear message

### When Code Breaks
Describe behavior: "The function returns None when called with an empty list."
NOT: "Fix it."

---

## Deployment Model

Each advancement is designed to work as one of:
- **Claude Code hook** (PreToolUse / PostToolUse / Stop)
- **Claude Code slash command** (`/sc:something`)
- **MCP server** (local or remote)
- **Standalone CLI tool** (Python 3.10+, stdlib-first)
- **Streamlit web UI** (if a visual dashboard is warranted)

The target is tools that Matthew can use TODAY in his Claude Code sessions, not vaporware.

---

## URL Review — Auto-Trigger (Non-Negotiable)

When the user pastes a Reddit, GitHub, or any URL in this project's chat — with or without a slash command — Claude MUST automatically read and review it using the `/cca-review` workflow.

**How it works:**
1. Detect any URL in the user's message (reddit.com, github.com, or any http/https link)
2. For Reddit: run `python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/reddit_reader.py "<URL>"` to get the full post + all comments
3. For non-Reddit: use WebFetch to read the page
4. Deliver the full `/cca-review` verdict: frontier mapping, rat poison check, BUILD/ADAPT/REFERENCE/SKIP
5. If the post contains links to GitHub repos, tools, or other resources — follow and read those too

**The user should be able to say "check this out" and paste a link.** That's it. No slash command required. Claude reads everything, analyzes it against the five frontiers, and delivers a verdict.

If the user explicitly says "just read this" or "don't review" — skip the analysis and just return the content.

Reddit links in comments and nested replies should also be followed if they point to tools, repos, or implementations relevant to the frontiers.

---

## Communication Style Rules

- No emojis unless explicitly requested
- Explain what code does in plain English alongside any code output
- One function at a time — test before building the next
- MANDATORY — End EVERY response with a one-line `Advancement tip: ...` — one relevant tool, pattern, or next step. Non-negotiable.

---

## Session Commands

See `~/.claude/COMMANDS.md` for full command reference. Key: `/cca-init`, `/cca-auto`, `/cca-wrap`, `/cca-review`.

---

## Test Commands (run before any session work)

```bash
# Parallel (preferred — ~26s with 8 workers):
python3 parallel_test_runner.py --workers 8

# Quick smoke (init only — ~2s, 10 core suites):
python3 parallel_test_runner.py --quick --workers 8
```

All 223 suites must pass (8959 total) before touching any other file.
Never use the serial for loop — parallel runner is 4-5x faster.
See `REFERENCE.md` for the full test-by-test breakdown.

---

## Desktop Autoloop (MT-22)

Self-sustaining CCA session cycle in Claude.app Code tab. See `DESKTOP_AUTOLOOP_SETUP.md` for full docs.
Key files: `autoloop_trigger.py` (CCA-internal, /cca-wrap Step 10), `desktop_automator.py` (AppleScript control).
Critical: ALWAYS Cmd+N for new session, ALWAYS verify Code tab, NEVER paste into old chat.

---

## Known Gotchas

- **Credential regex for Anthropic keys:** Pattern must include hyphens — `sk-[A-Za-z0-9\-]{20,}` not `sk-[A-Za-z0-9]{20,}`. Keys contain `sk-ant-api03-...`.
- **Memory ID suffix:** 8 hex chars minimum. 3-char suffix produced collisions at 100 rapid-fire creates.
- **Commit every task:** Never close a session with uncommitted deliverables. Sessions 7-15 accumulated 80+ untracked files. Commit when tests pass.
- **Claude Island auto-hooks:** Do NOT launch while other CC sessions are active — it auto-installs global hooks into `~/.claude/hooks/`.
- **PROJECT_INDEX.md Edit retries:** Always Read PROJECT_INDEX.md (and SESSION_STATE.md) before editing. These structured table files cause Edit failures in 68% of sessions (25/37) when the old_string doesn't exactly match. Read costs ~500 tokens, saves ~2000 in retry loops.
- **GitHub repo:** `https://github.com/mpshields96/ClaudeCodeAdvancements`
- **AUTOLOOP TRIGGER (Step 10):** /cca-wrap has 10 steps, NOT 9. Step 10 (`python3 autoloop_trigger.py`) is the FINAL action and MUST execute after the resume prompt. The session is NOT complete until the trigger fires. This has been skipped in 3+ consecutive sessions. NEVER skip Step 10.
