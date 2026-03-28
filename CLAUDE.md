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

## MT-53 STEAL CODE — WORK SMARTER NOT HARDER (S218 — Matthew directive, PERMANENT)

**MT-53 Pokemon Bot: Port code from cloned reference repos and GPT Plays Pokemon livefeed. Don't rewrite from scratch.** The reference repos were cloned for a reason. Read them, extract what works, adapt to our Crystal build. Writing 1000 LOC from scratch when a working implementation is already cloned locally is objectively dumb.

Sources: pokemon-agent/references/ (cloned repos), https://gpt-plays-pokemon.clad3815.dev/firered/livefeed
Reference: MATTHEW_DIRECTIVES.md S218 for full verbatim directive.

## MT-53 EMULATOR RULES (S219 — Matthew directive, PERMANENT)

**PyBoy is BANNED.** Do not use, install, recommend, or reference PyBoy. Period.
Use **mGBA** (mgba-py bindings) as the emulator backend. mGBA supports GB/GBC/GBA — one backend for all ROM types.

**RUN FIRST, BUILD WHILE PLAYING (S219 — Matthew directive):**
Do NOT try to build the bot to 100% completion before running it. The bot learns by playing.
1. Get the emulator running with mGBA backend
2. Validate boot sequence + RAM reading with `--offline` mode (no API cost)
3. Connect LLM and let it play — fix what actually breaks
4. The action cache, stuck detection, and movement validator adapt in real-time
5. Build remaining features (gym routing, team building, etc.) WHILE the bot plays

The bot playing IS the development process, not a reward at the end of it.

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
- **PyBoy is BANNED:** Do not use PyBoy for MT-53 Pokemon bot. Use mGBA (mgba-py). Matthew explicit directive S219.
- **Claude Island auto-hooks:** Do NOT launch while other CC sessions are active — it auto-installs global hooks into `~/.claude/hooks/`.
- **PROJECT_INDEX.md Edit retries:** Always Read PROJECT_INDEX.md (and SESSION_STATE.md) before editing. These structured table files cause Edit failures in 68% of sessions (25/37) when the old_string doesn't exactly match. Read costs ~500 tokens, saves ~2000 in retry loops.
- **GitHub repo:** `https://github.com/mpshields96/ClaudeCodeAdvancements`
- **AUTOLOOP TRIGGER (Step 10):** /cca-wrap has 10 steps, NOT 9. Step 10 (`python3 autoloop_trigger.py`) is the FINAL action and MUST execute after the resume prompt. The session is NOT complete until the trigger fires. This has been skipped in 3+ consecutive sessions. NEVER skip Step 10.
