# ClaudeCodeAdvancements — Project Rules for Claude Code

## Mission
Research, design, and build the next significant advancements for Claude Code users and AI/LLM-assisted development. This project pursues what is objectively next — based on validated community intelligence, Anthropic's own research, and frontier AI trends — not speculation or novelty for its own sake.

This is NOT a betting project. There is NO domain overlap with Titanium.

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

## Scope Boundary (Non-Negotiable)

Claude MUST NOT read, edit, or interact with any files outside of:
`/Users/matthewshields/Projects/ClaudeCodeAdvancements/`

This is absolute. No exceptions. No cross-project file access of any kind.

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

## File Permissions (Strict)

| Location | Permission |
|----------|-----------|
| `/Users/matthewshields/Projects/ClaudeCodeAdvancements/` | Full read + write |
| `/Users/matthewshields/Projects/polymarket-bot/` | READ-ONLY — for cross-chat bridge communication |
| Any other path on this computer | FORBIDDEN — do not access |

**Cross-project bridge (Matthew-authorized, Session 45):**
CCA may READ files in the polymarket-bot project for the purpose of cross-chat communication:
- Read handoff files, communication files, session state
- Read DB schema and strategy definitions (to build tools/research for the bot)
- NEVER write to polymarket-bot files — write CCA's responses to ClaudeCodeAdvancements/
- NEVER execute scripts, install packages, or modify code in polymarket-bot
- NEVER read or log credentials, API keys, wallet addresses, or financial account data

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

## Known Gotchas

- **Credential regex for Anthropic keys:** Pattern must include hyphens — `sk-[A-Za-z0-9\-]{20,}` not `sk-[A-Za-z0-9]{20,}`. Keys contain `sk-ant-api03-...`.
- **Memory ID suffix:** 8 hex chars minimum. 3-char suffix produced collisions at 100 rapid-fire creates.
- **Commit every task:** Never close a session with uncommitted deliverables. Sessions 7-15 accumulated 80+ untracked files. Commit when tests pass.
- **Claude Island auto-hooks:** Do NOT launch while other CC sessions are active — it auto-installs global hooks into `~/.claude/hooks/`.
- **PROJECT_INDEX.md Edit retries:** Always Read PROJECT_INDEX.md (and SESSION_STATE.md) before editing. These structured table files cause Edit failures in 68% of sessions (25/37) when the old_string doesn't exactly match. Read costs ~500 tokens, saves ~2000 in retry loops.
- **GitHub repo:** `https://github.com/mpshields96/ClaudeCodeAdvancements`
