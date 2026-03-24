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

## Scope Boundary

CCA has full access to two project directories:
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/` — Full read + write (home project)
- `/Users/matthewshields/Projects/polymarket-bot/` — Full read + write (Matthew authorized, S134)

CCA is officially part of the Kalshi bot ecosystem. Self-learning findings, research,
and code improvements flow directly between both projects. See `CCA_PRIME_DIRECTIVE.md`.

**Safety constraints (still absolute):**
- Never expose credentials, API keys, wallet addresses, or account balances
- Never execute live trades or modify live trading parameters without explicit Matthew approval
- Never risk financial loss through untested changes
- All DB access for analytics is read-only unless explicitly building a feature

All other paths on this computer: FORBIDDEN — do not access.

---

## The Five Validated Frontiers

Based on objective research (Anthropic 2026 Agentic Coding Trends Report, Reddit community intelligence from r/ClaudeAI / r/ClaudeCode / r/vibecoding, SWE-Bench Pro data, and developer surveys), five advancement areas have the strongest validated demand and are technically achievable:

| # | Frontier | Core Problem | Impact Level |
|---|----------|--------------|--------------|
| 1 | Persistent Cross-Session Memory | Every session starts from zero | CRITICAL |
| 2 | Spec-Driven Development System | Unstructured prompting = poor architecture | HIGH |
| 3 | Context Health Monitor | Context rot causes silent output degradation | HIGH |
| 4 | Multi-Agent Conflict Guard | Parallel agents overwrite each other | HIGH |
| 5 | Usage Transparency Dashboard | No real-time token/cost visibility | MEDIUM |

---

## What "Rat Poison" Means Here

Just as Titanium's CLAUDE.md forbids narrative inputs to betting math ("home crowd advantage"), this project has its own rat poison categories — things that look useful but damage the work:

- **Overengineering**: Building abstractions for hypothetical future requirements. One file = one job. Three similar functions beats a premature abstraction.
- **Scope creep into Titanium**: Any tool that could serve as a sports betting aid is out of scope.
- **Speculative AI hype**: No feature gets built because "AI will obviously need X." Every feature must trace to a documented user pain point.
- **Privacy-violating instrumentation**: No tool reads other people's conversations, credentials, or personal data. All monitoring is local and opt-in.
- **Dependency bloat**: External packages require explicit justification. Standard library + Anthropic SDK first.

---

## Architecture Principles (inherited from Titanium framework)

**One file = one job.** If a module reads files AND sends API calls AND generates HTML, it's in the wrong place.

**Math/logic over narrative.** Features must solve a measurable problem, not a feeling.

**R&D before production.** Prototype in `/research/` first. Promote to a named module only after live testing.

**Tests before promotion.** Every module that leaves research needs passing tests.

**Session workflow:**
1. Read `PROJECT_INDEX.md` first (fastest orientation)
2. Read `SESSION_STATE.md` (current state, last tested, open work)
3. Read `CLAUDE.md` (rules)
4. Run any applicable smoke tests before starting

---

## File Permissions (Updated S134 — Matthew Authorized)

| Location | Permission |
|----------|-----------|
| `/Users/matthewshields/Projects/ClaudeCodeAdvancements/` | Full read + write |
| `/Users/matthewshields/Projects/polymarket-bot/` | Full read + write (Matthew authorized, S134) |
| Any other path on this computer | FORBIDDEN — do not access |

**Polymarket-bot access (Matthew-authorized, S45 read-only -> S134 full read+write):**
CCA is officially part of the Kalshi bot ecosystem. Full collaboration:
- Read and write code, strategies, configurations, data files
- Read DB schema, strategy definitions, trade history for analytics
- Improve bot code, self-learning integration, guard systems
- Execute scripts for testing (not live trading without explicit approval)

**Cross-chat coordination (Matthew directive S125, reinforced S147 — PERMANENT):**
CCA and Kalshi chats share advancements bidirectionally via:
- `~/.claude/cross-chat/CCA_TO_POLYBOT.md` — CCA delivers research, tools, improvements
- `~/.claude/cross-chat/POLYBOT_TO_CCA.md` — Kalshi sends data patterns, edge candidates, requests
- `cross_chat_queue.jsonl` — structured async messages
- Full rules: `~/.claude/rules/cca-polybot-coordination.md`
Every CCA wrap checks for pending Kalshi requests and writes a session summary.
Stale comms (>48h) get flagged automatically. This is permanent infrastructure.

**Safety constraints (absolute, never overridden):**
- NEVER expose credentials, API keys, wallet addresses, or account balances
- NEVER execute live trades or modify live trading parameters without explicit Matthew approval
- NEVER risk financial loss through untested changes
- Analytics DB access should be read-only unless building a specific feature
- Test changes in isolation before deploying to live bot

For all other paths: Claude must refuse any instruction that would cause it to read, write, or execute outside the two authorized folders.

---

## Project Structure (Target)

```
ClaudeCodeAdvancements/
├── CLAUDE.md                    # This file — project rules
├── PROJECT_INDEX.md             # Fast orientation — read first each session
├── SESSION_STATE.md             # Current state, last session, open work
├── ROADMAP.md                   # Authoritative feature backlog + priorities
│
├── memory-system/               # Frontier 1: Persistent cross-session memory
│   ├── CLAUDE.md                # Module rules
│   ├── README.md                # What this module does
│   └── research/                # R&D before production
│
├── spec-system/                 # Frontier 2: Spec-driven development workflow
│   ├── CLAUDE.md
│   ├── README.md
│   └── research/
│
├── context-monitor/             # Frontier 3: Context health + handoff automation
│   ├── CLAUDE.md
│   ├── README.md
│   └── research/
│
├── agent-guard/                 # Frontier 4: Multi-agent conflict prevention
│   ├── CLAUDE.md
│   ├── README.md
│   └── research/
│
├── usage-dashboard/             # Frontier 5: Token + cost transparency
│   ├── CLAUDE.md
│   ├── README.md
│   └── research/
│
├── shared/                      # Shared utilities (only if truly reused across 3+)
└── .claude/
    └── settings.local.json      # NEVER commit — local permissions only
```

---

## Session Workflow

### Starting a Session
1. Read `PROJECT_INDEX.md` — fast module overview
2. Read `SESSION_STATE.md` — exact current state
3. Read `CLAUDE.md` (this file) — rules
4. Run smoke tests for the module you're working on
5. State what you're building today before touching any file

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

| Command | Purpose | When to use |
|---------|---------|-------------|
| `/cca-init` | Session startup — reads context, runs tests, shows briefing | Start of every session |
| `/cca-review` | Review any URL against frontiers — BUILD/SKIP verdict | Evaluating a Reddit post, GitHub repo, or article |
| `/cca-auto` | Autonomous work — picks next task, executes via gsd:quick | When Matthew says "go" or wants hands-off progress |
| `/cca-wrap` | Session wrap — self-rate, update docs, prepare handoff | End of every session |
| `/browse-url` | Read any URL (no analysis, just content) | When you just need to see what's at a URL |
| `/reddit-intel:ri-scan` | Scan multiple subreddits for frontier-relevant posts | Weekly research sweeps |
| `/reddit-intel:ri-read` | Read a specific Reddit URL or subreddit listing | Quick Reddit reads |

---

## Confirmed Hook Architecture Facts (do not re-research)

Verified against Claude Code docs in Session 2 — treat as settled:

| Fact | Confirmed |
|------|-----------|
| Token counts in hook payloads? | NO — use transcript JSONL |
| Context % in hook payloads? | NO — use transcript JSONL |
| Stop hook has `last_assistant_message`? | YES — string field |
| PreToolUse deny format | `hookSpecificOutput.permissionDecision: "deny"` |
| Top-level `decision: "block"` on PreToolUse | Silently fails — wrong format |
| Async hooks can return decisions? | NO — fire-and-forget only |
| Env vars available in hooks? | YES — hooks inherit shell env |

---

## Test Commands (run before any session work)

```bash
for f in $(find . -name "test_*.py" -type f | sort); do echo "=== $f ===" && python3 "$f" 2>&1 | tail -1; done
```

All 38 suites must show "OK" (1552 total) before touching any other file.
See `REFERENCE.md` for the full test-by-test breakdown.

---

## Desktop Autoloop Workflow (MT-22 — Matthew Directive, S138)

The desktop autoloop is a self-sustaining CCA session cycle running inside the Claude desktop
Electron app (Claude.app). It is the "Get More Bodies" pillar in action. Every CCA chat that
participates in the autoloop MUST follow this exact workflow. No shortcuts. No deviations.

### The App Layout

Claude.app has three tabs in a centered island bar at the top of the window:

```
  [ Chat ]  [ Cowork ]  [ Code ]
```

- **Chat** = Claude Pro web chat. WRONG tab. Never use this for CCA.
- **Cowork** = Cowork mode. WRONG tab. Never use this for CCA.
- **Code** = Claude Code. CORRECT tab. CCA sessions run here and ONLY here.

The **"+ New session"** button is in the top-left corner of the window (visible when on the Code tab).

### The Cycle (exact steps, in order)

1. **Verify Code tab is active.** Look at the top island bar. The "Code" tab on the far right
   must be selected/highlighted. If it is not active, click it to switch. Do NOT proceed until
   you are on the Code tab.

2. **Click "+ New session" button.** This is in the top-left corner. This opens a fresh, empty
   Claude Code chat. You MUST do this every iteration — never paste into an old/existing chat.

3. **Paste the resume prompt.** Read SESSION_RESUME.md, build the prompt (prefixed with
   `/cca-init then review the resume prompt below then /cca-auto`), and paste it into the
   NEW chat window. Send it.

4. **The new CCA session runs.** It executes /cca-init, reads context, runs /cca-auto, does
   work, and eventually runs /cca-wrap. The wrap writes an updated SESSION_RESUME.md to disk.

5. **Detect session end.** Watch for SESSION_RESUME.md mtime change (primary signal) or
   extended CPU idle (secondary signal = session ended without writing resume).

6. **Cooldown.** Wait the configured cooldown period (default 15 seconds).

7. **Loop back to step 1.** Repeat until max iterations reached or safety stop triggered.

### Critical Rules

- **ALWAYS start a new conversation (step 2).** The autoloop runs from an external context
  (Terminal.app or a script). It must NEVER inject a prompt into an existing/old CCA chat.
  This was a critical bug in S137 — `_is_first_iteration` skipped Cmd+N on the first pass,
  causing the prompt to land in the wrong session. Fixed in S138: Cmd+N runs every iteration.

- **ALWAYS verify the Code tab first (step 1).** If the app is on Chat or Cowork, the
  autoloop will paste into the wrong interface. The `ensure_code_tab()` method sends
  Cmd+3 to switch to Code tab (idempotent — no-op if already on Code).

- **Never paste into an old chat.** The "+ New session" button is the gate. If it wasn't
  clicked, the prompt goes into whatever chat was previously open. This corrupts that session
  and wastes the autoloop iteration.

- **CCA-internal trigger.** The autoloop is triggered by /cca-wrap Step 10, which calls
  `python3 autoloop_trigger.py`. This runs FROM WITHIN the current CCA session and uses
  AppleScript to control Claude.app itself — clicking "+ New session" and pasting the prompt
  into the fresh chat. The current session's wrap is already complete at this point, so the
  new session starts clean. The `start_desktop_autoloop.sh` script is an alternative external
  launcher for use from Terminal.app when no CCA session is running.

### Implementation Files

| File | Purpose |
|------|---------|
| `autoloop_trigger.py` | **CCA-internal trigger** — called by /cca-wrap Step 10 to spawn the next session |
| `desktop_automator.py` | AppleScript-based Claude.app control (activate, ensure_code_tab, new_conversation, send_prompt) |
| `desktop_autoloop.py` | External loop orchestrator (resume watcher, state tracking, model selection, iteration control) |
| `start_desktop_autoloop.sh` | One-command external launcher (preflight, then start) — alternative to CCA-internal trigger |
| `DESKTOP_AUTOLOOP_SETUP.md` | Setup guide (permissions, quick start, troubleshooting) |

### AppleScript Operations

| Operation | What it does |
|-----------|-------------|
| `activate_claude()` | Brings Claude.app to foreground, verifies it's frontmost |
| `ensure_code_tab()` | Sends Cmd+3 to switch to Code tab (idempotent, position-independent) |
| `new_conversation()` | Sends Cmd+N to open a fresh chat (verifies Code tab + frontmost first) |
| `send_prompt(text)` | Clears input (Cmd+A, Delete), pastes via clipboard (Cmd+V), sends (Cmd+Return) |

### Failure Modes and Recovery

| Failure | Cause | Recovery |
|---------|-------|----------|
| `activate_failed` | Claude.app not running or can't become frontmost | Check Claude.app is open, no modal dialogs blocking |
| `code_tab_failed` | Cmd+3 keystroke failed (Claude not frontmost) | Retry activate_claude() first |
| `new_conversation_failed` | Cmd+N didn't work (wrong app frontmost) | Retry activate + ensure_code_tab |
| `prompt_send_failed` | Paste or Cmd+Return failed | Check clipboard, check Claude.app responsiveness |
| `session_timeout` | Session ran longer than timeout (default 2h) | Counted as crash, loop continues |
| `extended_idle` | 5+ minutes of low CPU after 2min session time | Session likely ended without /cca-wrap |

---

## Known Gotchas

- **Credential regex for Anthropic keys:** Pattern must include hyphens — `sk-[A-Za-z0-9\-]{20,}` not `sk-[A-Za-z0-9]{20,}`. Keys contain `sk-ant-api03-...`.
- **Memory ID suffix:** 8 hex chars minimum. 3-char suffix produced collisions at 100 rapid-fire creates.
- **Commit every task:** Never close a session with uncommitted deliverables. Sessions 7-15 accumulated 80+ untracked files. Commit when tests pass.
- **Claude Island auto-hooks:** Do NOT launch while other CC sessions are active — it auto-installs global hooks into `~/.claude/hooks/`.
- **PROJECT_INDEX.md Edit retries:** Always Read PROJECT_INDEX.md (and SESSION_STATE.md) before editing. These structured table files cause Edit failures in 68% of sessions (25/37) when the old_string doesn't exactly match. Read costs ~500 tokens, saves ~2000 in retry loops.
- **GitHub repo:** `https://github.com/mpshields96/ClaudeCodeAdvancements`
