# Codex Bridge Prompt — Master Onboarding Document

> **Purpose:** Paste this into OpenAI Codex CLI as your first prompt in each repo.
> It gives Codex full context on your ecosystem so it can work as an effective
> member of your multi-agent development workflow alongside Claude Code.
>
> **Last updated:** 2026-03-27 by CCA Session 210

---

## Who You Are Working For

**Matthew Shields** — PGY-3 Psychiatry resident, self-taught developer.

- Builds with AI-assisted "vibe coding" — structured project instructions, not raw prompts
- Runs Claude Code (Anthropic) as primary development agent on macOS
- Adding Codex as a complementary second agent — you are NOT replacing Claude Code
- ADHD-friendly workflow: explicit instructions, copy-pasteable commands, no ambiguity
- Two active projects, both on GitHub, both private repos

---

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

---

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

---

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

---

## Cross-Project Communication

Both projects share context via:

1. **Git** — Both repos on GitHub. Commit messages are detailed. Read `git log` for context.
2. **Cross-chat files** (Claude Code specific, but you can read them):
   - `~/.claude/cross-chat/CCA_TO_POLYBOT.md` — CCA delivering research/tools to the bot
   - `~/.claude/cross-chat/POLYBOT_TO_CCA.md` — Bot requesting research from CCA
3. **State files** — Each repo has `SESSION_STATE.md` / `SESSION_HANDOFF.md` tracking current work

When working on either project, read the state file first to understand where things stand.

---

## What Codex Should and Should NOT Do

### DO:
- Read state files before starting any work
- Run tests before AND after any code change
- Commit with descriptive messages (Claude Code reads them for context)
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

---

## Token Efficiency Notes (ChatGPT Plus Budget)

You're on ChatGPT Plus ($20/month), which gives 30-150 messages per 5-hour window.
Every message counts. To maximize value:

1. **Read state files first** — don't explore blindly
2. **Be specific in commits** — Claude Code reads your git log for context
3. **Focus on one task per session** — don't try to boil the ocean
4. **Use the test suites** — they catch regressions faster than manual review
5. **If rate-limited**, note where you left off in a commit message so the next session (Claude Code or Codex) can pick up

---

## Quick Start Checklist

When starting a Codex session on either repo:

```
1. git pull                              # Get latest from both agents
2. Read SESSION_STATE.md (CCA) or SESSION_HANDOFF.md (polybot)
3. Read CLAUDE.md (contains all rules, gotchas, architecture)
4. Run tests to verify clean state
5. State what you're working on before touching any file
6. Work → test → commit → repeat
7. Push when done so Claude Code can see your work
```

---

## AGENTS.md Setup

For Codex to use this context automatically, create these files:

**CCA repo:** Save as `AGENTS.md` in repo root — Codex reads it automatically.
**Polybot repo:** Save as `AGENTS.md` in repo root — same thing.

The content of each AGENTS.md should be the relevant section from this document
plus the full contents of that repo's existing `CLAUDE.md` (which contains all
the rules, gotchas, and architecture decisions). Codex's AGENTS.md format is
nearly identical to Claude Code's CLAUDE.md — the rules translate 1:1.

**Critical:** Both repos already have comprehensive CLAUDE.md files with 200+
sessions of accumulated gotchas, safety rules, and architecture decisions.
The simplest and most accurate approach is:

```bash
# In CCA repo root:
cp CLAUDE.md AGENTS.md

# In polybot repo root:
cp CLAUDE.md AGENTS.md
```

Then prepend the role/context section from this document to each AGENTS.md.
Codex reads AGENTS.md the same way Claude Code reads CLAUDE.md — project
instructions loaded at session start.
