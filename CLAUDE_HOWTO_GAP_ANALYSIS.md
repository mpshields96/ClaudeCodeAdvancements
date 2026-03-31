# Claude-Howto Gap Analysis
# Source: shanraisshan/claude-code-best-practice (26.2K stars, 13 modules)
# Purpose: Map what CCA already does vs what's new — prioritize Matthew's 11-13hr study
# Written: S241 (2026-03-30)

---

## TL;DR Priority Guide

| Priority | Module | Why |
|----------|--------|-----|
| HIGH | Module 2: Subagents | 16 frontmatter fields — we use ~5. Skills preloading, isolation, color, effort are new. |
| HIGH | Module 8: Hooks Deep Dive | 22 hook events — we use ~4. Several untapped events. |
| HIGH | Module 9: Orchestration Workflow | Command->Agent->Skill pattern — cleaner than our current approach. |
| HIGH | Boris Tips (Mar 30) | `/batch`, `--bare`, `/btw`, `/branch`, `/loop` — several unused features. |
| MEDIUM | Module 4: Skills | Agent skills vs direct skills distinction. `${CLAUDE_PLUGIN_DATA}` for persistence. |
| MEDIUM | Module 10: Agent Teams | Experimental but directly relevant to MT-21 hivemind. |
| MEDIUM | Module 6: Settings | 37+ keys, 8 permission modes — we use a subset. |
| LOW | Module 1: Memory (CLAUDE.md) | We already do this well. Ancestor/descendant loading is good to confirm. |
| LOW | Module 3: Commands | Reference material. 64 built-in commands cataloged. |
| LOW | Module 7: CLI Flags | Reference. `--bare`, `--teleport`, `--agent` are the notable ones. |
| SKIM | Module 5: MCP Servers | We already use several. Context7/DeepWiki worth noting. |
| SKIM | Module 11: Dev Workflows | RPI workflow is similar to our spec-system. Cross-model (Codex) interesting but low priority. |

---

## Module-by-Module Analysis

### Module 1: CLAUDE.md Layering — SKIM (we do this well)

**What they teach:**
- Ancestor loading (UP): walks CWD to root, loads every CLAUDE.md found
- Descendant loading (DOWN): lazy — only when Claude reads/edits files in subdirectory
- Siblings never load (working in frontend/ won't load backend/CLAUDE.md)
- CLAUDE.local.md for personal prefs (.gitignore it)
- Boris tip: after each correction, instruct Claude to update CLAUDE.md

**What CCA already does:**
- Root CLAUDE.md with full project rules
- Module-level CLAUDE.md files (memory-system/, agent-guard/, etc.)
- Global ~/.claude/CLAUDE.md with cross-project rules
- ~/.claude/rules/ for topic-specific rule files

**Gap:** None significant. We're ahead of the guide on layering complexity. The "update CLAUDE.md after corrections" tip is interesting but we capture corrections in memory files instead — arguably better (structured, searchable, typed).

---

### Module 2: Subagents — DEEP DIVE (major gaps)

**What they teach — 16 frontmatter fields:**

| Field | We Use? | Notes |
|-------|---------|-------|
| `name` | Yes | Standard |
| `description` | Yes | But we don't use `"PROACTIVELY"` keyword for auto-invocation |
| `tools` | Yes | Including `Agent(agent_type)` syntax for nested agents |
| `disallowedTools` | No | Could scope down workers for safety |
| `model` | Yes | haiku/sonnet/opus/inherit |
| `permissionMode` | Partially | 8 modes available — we mostly use default |
| `maxTurns` | No | Could prevent runaway agents |
| `skills` | **No** | **KEY GAP: preloading skills as domain knowledge into agents** |
| `mcpServers` | No | Scoping MCP servers per agent |
| `hooks` | No | Agent-scoped hooks (different from global hooks) |
| `memory` | No | `user`, `project`, or `local` memory scopes |
| `background` | No | Background task execution |
| `effort` | No | low/medium/high/max per agent |
| `isolation` | Partially | We know worktree but don't use it systematically |
| `initialPrompt` | No | Auto-submitted first turn — could eliminate manual prompts |
| `color` | No | Visual distinction in CLI output |

**6 built-in agent types:** general-purpose, Explore, Plan, Bash, statusline-setup, claude-code-guide

**Key gap: `skills:` field.** We can preload domain knowledge into agents via skills — this is cleaner than stuffing everything into the agent prompt. Our hivemind workers could each get role-specific skills preloaded.

**Key gap: `maxTurns`.** We have no runaway protection on spawned agents beyond token cost awareness.

**Key gap: `initialPrompt`.** Could auto-start agents without manual trigger — relevant for autoloop.

---

### Module 3: Commands — REFERENCE (low priority)

**What they teach:**
- 13 frontmatter fields for commands
- 64 built-in commands cataloged
- `context: fork` for isolated subagent execution
- `shell` field for system commands
- `paths` field for glob-pattern file scoping

**What CCA already does:**
- Extensive custom commands (cca-init, cca-auto, cca-wrap, etc.)
- We use most frontmatter fields already

**Gap:** `context: fork` is interesting — runs command in isolated subagent context. Could be useful for commands that shouldn't pollute main context. `paths` field for scoping commands to specific file patterns is also underused.

---

### Module 4: Skills — STUDY (moderate gaps)

**What they teach:**
- Two distinct patterns: Agent Skills (preloaded via `skills:`) vs Skills (direct invocation)
- `${CLAUDE_PLUGIN_DATA}` env var for skill-specific persistent storage
- Thariq's 9 types: library reference, product verification, data fetching, business automation, code scaffolding, code review, CI/CD, runbooks, infrastructure ops
- Thariq's 9 tips for skill design

**Key tips we're not using:**
1. Description fields are **trigger mechanisms**, not summaries — write them to maximize auto-invocation
2. Use `${CLAUDE_PLUGIN_DATA}` for skill-specific persistent storage (files, JSON, SQLite)
3. On-demand hooks (like `/careful`, `/freeze`) that activate safety modes only when called
4. Store configs in `config.json`, prompt users via AskUserQuestion

**Gap:** We have many skills but don't use the Agent Skills (preloaded) pattern. Our skill descriptions may not be optimized as trigger mechanisms. `${CLAUDE_PLUGIN_DATA}` could replace some of our ad-hoc state file paths.

---

### Module 5: MCP Servers — SKIM (mostly covered)

**What they teach:**
- Top 5 recommended: Context7, Playwright, Claude in Chrome, DeepWiki, Excalidraw
- stdio (local) vs http (remote) server types
- Three scopes: Project (.mcp.json), User (~/.claude.json), Subagent (frontmatter)
- Permission rules using `mcp__<server>__<tool>` naming

**What CCA already does:**
- We have Claude in Chrome, Gemini, PDF tools, Supabase, scheduled tasks
- We use both project and user scoping

**Gap:** Context7 (up-to-date library docs, prevents hallucinated APIs) and DeepWiki (wiki for any GitHub repo) are worth adding. Subagent-scoped MCP servers could scope down tool access per agent role.

---

### Module 6: Settings — STUDY (some gaps)

**What they teach:**
- 37+ settings keys with full reference
- 5-level hierarchy: Managed > CLI args > settings.local.json > settings.json > global
- 8 permission modes (we mainly use default + bypassPermissions)
- Pattern syntax: `Edit(*)`, `Bash(npm run *)`, `WebFetch(domain:*)`, `Read(.env)` deny
- `autoMode`, `worktree.symlinkDirectories`, `worktree.sparsePaths`
- 84+ environment variables

**Gaps:**
- `autoMode` settings — background safety classifier replacing manual permission prompts
- Granular permission patterns (we mostly use broad allow/deny, not path-specific)
- `worktree.symlinkDirectories` / `worktree.sparsePaths` for optimized worktree setup
- `outputStyle` options ("Explanatory", "Learning", custom)

---

### Module 7: CLI Startup Flags — REFERENCE (low priority)

**Notable flags we may not use:**
- `--bare`: Up to **10x faster** SDK startup (skips CLAUDE.md/settings/MCP). Relevant for headless/automated usage.
- `--teleport`: Resume a web session in local terminal
- `--fork-session`: Create new session ID when resuming (don't pollute original)
- `--agent <NAME>`: Specify custom agent for entire session
- `--add-dir <PATH>`: Multi-repo access in single session
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`: Enable agent teams

**Gap:** `--bare` is directly relevant to any CCA tooling that shells out to `claude -p`. 10x startup speedup is significant.

---

### Module 8: Hooks Deep Dive — DEEP DIVE (major gaps)

**22 hook events available:**

| Event | We Use? | Notes |
|-------|---------|-------|
| PreToolUse | Yes | Agent guard, loop detection |
| PostToolUse | Yes | Loop guard |
| Stop | Partially | Context monitor |
| UserPromptSubmit | Yes | Skill suggestions |
| PermissionRequest | No | Could auto-allow/deny based on context |
| PostToolUseFailure | No | Could capture error patterns for mistake-learning (Chat 7) |
| PreCompact | No | Could save critical state before compaction |
| PostCompact | No | Could restore/verify state after compaction |
| SessionStart | No | Could replace manual /cca-init checks |
| SessionEnd | No | Could auto-trigger wrap steps |
| Notification | No | Could route notifications to mobile/Telegram |
| SubagentStart | No | Could log/control agent spawns |
| SubagentStop | No | Could capture agent results |
| Setup | No | One-time initialization |
| TeammateIdle | No | Relevant to agent teams |
| TaskCompleted | No | Could auto-trigger next task |
| ConfigChange | No | Could detect setting modifications |
| WorktreeCreate | No | Could set up worktree-specific configs |
| WorktreeRemove | No | Cleanup |
| InstructionsLoaded | No | Could verify CLAUDE.md loaded correctly |
| Elicitation | No | MCP elicitation events |
| ElicitationResult | No | MCP elicitation results |

**4 hook types:** Command (shell), Prompt, Agent, HTTP handler

**Key gaps:**
- **PostToolUseFailure**: Perfect for Chat 7's mistake-learning pattern (Prism). Auto-capture when tools fail.
- **PreCompact/PostCompact**: Could preserve critical state through compaction (context monitor use case).
- **SessionStart/SessionEnd**: Could automate init/wrap steps we currently do manually.
- **SubagentStart/SubagentStop**: Could enforce agent spawn budgets (peak/off-peak).
- **Hook type: Agent**: Hooks can spawn agents — not just run shell commands. Powerful for complex reactions.

---

### Module 9: Orchestration Workflow — DEEP DIVE (new pattern)

**The Command -> Agent -> Skill pattern:**
1. **Command** (user-facing, lightweight): handles interaction, coordinates
2. **Agent** (background, heavier): fetches data, uses preloaded skills as domain knowledge
3. **Skill** (independent, reusable): produces output, receives data from context

**How this differs from CCA's current approach:**
- We conflate commands and skills — our slash commands do everything inline
- We don't use the Agent Skills (preloaded domain knowledge) pattern
- We don't separate "coordination" from "execution" cleanly

**Example:** Instead of `/cca-wrap` being a 244-line command that does everything, it could be:
- `/cca-wrap` command: coordinates the wrap sequence, asks questions
- `wrap-executor` agent: runs the analysis steps with preloaded `self-learning-analyzer` skill
- `session-reporter` skill: generates the resume prompt independently

**This is worth studying closely** — it could make our commands cleaner and more composable.

---

### Module 10: Agent Teams — STUDY (MT-21 relevant)

**What they teach:**
- Multiple independent Claude sessions coordinating via shared task list
- Each teammate gets full context window with own CLAUDE.md, MCP, skills
- Requires iTerm2 + tmux + `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- Data contract pattern: teammates agree on interfaces, work in parallel

**Relevance to MT-21 (Hivemind):**
- This is basically what we built with cca_comm.py but native
- Agent teams use a shared task list instead of our JSONL queue
- Each teammate is a full Claude session, not a spawned subagent
- Could potentially replace our custom hivemind infrastructure

**Gap:** We should evaluate whether native agent teams supersede our custom hivemind. If Anthropic is building this natively, our custom approach may be redundant — or complementary.

---

### Module 11: Development Workflows — SKIM (similar to spec-system)

**RPI (Research -> Plan -> Implement):**
- Very similar to our spec-system (requirements -> design -> tasks -> implement)
- They use dedicated agent personas (requirement-parser, product-manager, senior-engineer, CTO, UX designer, code-reviewer)
- Validation gates between phases

**Cross-Model (Claude + Codex):**
- 4-step: Plan (Opus) -> QA Review (GPT-5.4) -> Implement (Opus) -> Verify (GPT-5.4)
- Interesting but low priority — we already use Codex selectively

**Gap:** Minimal. Our spec-system covers this ground. The dedicated agent personas are interesting but align with what we already do in /spec:design-review.

---

### Boris Cherny Tips — STUDY (several actionable items)

**Tips we already follow:**
- Run multiple Claudes in parallel (dual-chat, hivemind)
- Use Opus with thinking
- Share CLAUDE.md with team (committed to git)
- Use slash commands for workflows
- Use subagents
- Pre-allow permissions
- Give Claude a way to verify its work (TDD, verification-before-completion)

**Tips we DON'T follow (gaps):**
1. **`/batch` for massive parallel changesets across worktrees** — unused
2. **`/btw` for side queries** without interrupting work — unused
3. **`/branch` for session forking** — unused
4. **Git worktrees (`claude -w`)** — known but not systematic
5. **PostToolUse hook to auto-format code** — we don't auto-format
6. **`--bare` for 10x faster SDK startup** — unused in tooling
7. **Start in Plan mode** (shift+tab twice) — we don't default to this
8. **claude.ai/code for extra parallelism** — unused (we moved to CLI)
9. **Tag @claude on PRs** to update CLAUDE.md — we don't do this

**Boris's core insight (Mar 10):** "Multiple uncorrelated context windows is the key insight." This validates our multi-chat architecture — separate contexts for separate concerns produce better results than one stuffed context.

**Boris's Mar 30 hidden features worth investigating:**
- `/loop` and `/schedule` for automated recurring tasks
- Cowork Dispatch for Desktop app remote control
- `/voice` for voice input (hold spacebar)

---

## Top 5 Action Items (for Matthew's study plan)

1. **Module 2 + 4 (Subagents + Skills):** Learn the `skills:` preloading pattern, `maxTurns`, `initialPrompt`, `effort` per agent. This directly improves every CCA agent we spawn.

2. **Module 8 (Hooks):** Learn PostToolUseFailure, PreCompact/PostCompact, SessionStart/SessionEnd, SubagentStart/SubagentStop. These unlock automation we currently do manually.

3. **Module 9 (Orchestration):** Study the Command->Agent->Skill separation pattern. Could clean up our command architecture significantly.

4. **Boris Tips (Mar 30):** Try `/batch`, `/btw`, `/branch`, `--bare`, `/voice`. Quick wins.

5. **Module 10 (Agent Teams):** Evaluate native agent teams vs our hivemind. If Anthropic's version is mature enough, we could simplify MT-21 significantly.

---

## What to Skip/Skim

- Module 1 (CLAUDE.md): We're already advanced here
- Module 3 (Commands): Reference only, we know the pattern
- Module 5 (MCP): We have our setup, just note Context7/DeepWiki
- Module 7 (CLI flags): Reference, just note `--bare` and `--teleport`
- Module 11 (Workflows): Similar to our spec-system, nothing new

---

## Second Study Resource: luongnv89/claude-howto (3K+ stars)

**Cloned to:** `references/claude-howto/` (gitignored — reference only)
**Source:** https://github.com/luongnv89/claude-howto (via r/vibecodeapp, 272pts)
**Different from** shanraisshan/claude-code-best-practice (this gap analysis source).

### Structure (10 numbered modules)

| Folder | Topic | CCA Gap Priority | Study Time |
|--------|-------|------------------|-----------|
| 01-slash-commands/ | 8 example commands + README | LOW — we know this | 15 min skim |
| 02-memory/ | CLAUDE.md layering (project, personal, directory) | LOW — we're ahead | 15 min skim |
| 03-skills/ | 6 example skills (blog-draft, brand-voice, code-review, etc.) | MEDIUM — skill design patterns | 30 min |
| 04-subagents/ | 7 example agents + 23-section deep reference | **HIGH** — covers maxTurns, effort, teams | 60 min |
| 05-mcp/ | MCP server setup guide | LOW — we have our setup | 15 min skim |
| 06-hooks/ | Hook events + 4 hook types (command, prompt, HTTP, agent) | **HIGH** — 25 events documented | 45 min |
| 07-plugins/ | 3 full plugin examples (devops, documentation, pr-review) | MEDIUM — plugin architecture | 30 min |
| 08-checkpoints/ | Checkpoint examples | LOW — basic feature | 10 min |
| 09-advanced-features/ | Planning mode, Auto Mode, Channels, Voice | MEDIUM — several unused features | 30 min |
| 10-cli/ | CLI flags and modes | LOW — reference | 15 min |

**Total study time: ~4-5 hours** (prioritizing HIGH modules)

### Built-in Interactive Features

The repo includes two Claude Code skills (auto-detected on clone):
- `/lesson-quiz <topic>` — Quiz yourself on any module (8-10 questions per topic)
- `/self-assessment` — Comprehensive proficiency quiz across all 10 areas

### Recommended Study Order (mapped to CCA gaps)

1. **04-subagents/** (HIGH) — This is the deepest gap. Read the full README (23 sections).
   Focus on: maxTurns, effort, agent teams, worktree isolation, persistent memory.
   Cross-reference with gap analysis Module 2 above.

2. **06-hooks/** (HIGH) — Read the full README for all 25 hook events.
   Focus on: PostToolUseFailure, PreCompact/PostCompact, SessionStart/SessionEnd.
   Cross-reference with gap analysis Module 8 above.

3. **03-skills/** (MEDIUM) — Study the 6 example skills for design patterns.
   Focus on: how SKILL.md files are structured, trigger descriptions.

4. **09-advanced-features/** (MEDIUM) — Planning mode, Auto Mode, Channels.
   Focus on: features we haven't tried yet.

5. **07-plugins/** (MEDIUM) — Full plugin architecture with commands + agents + hooks.
   This is the Command->Agent->Skill pattern from gap analysis Module 9.

6. Everything else: skim at your pace.
