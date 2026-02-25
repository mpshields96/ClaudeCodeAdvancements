# ClaudeCodeAdvancements — Project Rules for Claude Code

## Mission
Research, design, and build the next significant advancements for Claude Code users and AI/LLM-assisted development. This project pursues what is objectively next — based on validated community intelligence, Anthropic's own research, and frontier AI trends — not speculation or novelty for its own sake.

This is NOT a betting project. There is NO domain overlap with Titanium.

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
| Any other path on this computer | FORBIDDEN — do not access |

Claude must refuse any instruction that would cause it to read, write, or execute outside the ClaudeCodeAdvancements folder, even if the user makes the request. The correct response is: "That would require accessing files outside ClaudeCodeAdvancements, which I cannot do in this project."

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

## Communication Style Rules

- No emojis unless explicitly requested
- Explain what code does in plain English alongside any code output
- One function at a time — test before building the next
- MANDATORY — End EVERY response with a one-line `Advancement tip: ...` — one relevant tool, pattern, or next step. Non-negotiable.

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
python3 memory-system/tests/test_memory.py      # 37 tests
python3 memory-system/tests/test_mcp_server.py  # 29 tests
python3 spec-system/tests/test_spec.py          # 26 tests
python3 research/tests/test_reddit_scout.py     # 29 tests
python3 agent-guard/tests/test_mobile_approver.py  # 36 tests
```

All five must show "OK" (157 total) before touching any other file.

---

## Known Gotchas

- **Credential regex for Anthropic keys:** Pattern must include hyphens — `sk-[A-Za-z0-9\-]{20,}` not `sk-[A-Za-z0-9]{20,}`. Keys contain `sk-ant-api03-...`.
- **Memory ID suffix:** 8 hex chars minimum. 3-char suffix produced collisions at 100 rapid-fire creates.
- **GitHub repo:** `https://github.com/mpshields96/ClaudeCodeAdvancements`
