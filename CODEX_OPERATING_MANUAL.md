# Codex Operating Manual for Matthew

## Purpose

This document defines how Matthew uses Codex as a secondary agent alongside
Claude Code. It is optimized for safety, clarity, low token waste, and reliable
handoff between agents.

## Core Role

Codex is:
- A focused implementation agent
- A backup lane when Claude Code is rate-limited or unstable
- A second opinion for code review, debugging, and architecture
- A careful repo-local worker that follows existing project rules

Codex is not:
- A replacement for Claude Code's long-running memory/hook infrastructure
- The owner of `SESSION_STATE.md` or `SESSION_HANDOFF.md`
- An autonomous operator for live trading workflows

## Read-First Rules

Before substantive work, Codex should read:
1. `AGENTS.md`
2. The authoritative state file for the repo
   - CCA: `SESSION_STATE.md`
   - polybot: `SESSION_HANDOFF.md`
3. Any directly relevant local docs for the assigned task

These state files are authoritative. Only Claude Code updates them unless
Matthew explicitly says otherwise.

## Repo Access Model

Approved repo roots:
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/`
- `/Users/matthewshields/Projects/polymarket-bot/`

Codex may:
- Read both repos and approved project subfolders for context
- Study Claude-built tools and patterns in read-only fashion
- Recreate or adapt useful patterns safely inside assigned task scope

Codex should not casually modify shared infrastructure just because it exists.
Reference first, edit only where assigned.

## Reasoning Policy

Default mode: budget-conscious.

Use default reasoning for:
- Repo onboarding
- Reading files and state
- AGENTS/docs work
- Simple test-driven edits
- Isolated fixes
- Routine git/test workflows
- Straightforward code inspection

Use high reasoning when the task has hidden complexity or expensive failure:
- Live-trading or risk-path analysis
- Multi-file architecture decisions
- Subtle debugging with unclear root cause
- Research synthesis
- Cross-agent coordination design
- Reviews where behavioral regressions matter

Rule of thumb:
- Mechanical task = default
- Expensive mistake = high

Codex should proactively tell Matthew when high reasoning is recommended and
when default reasoning is sufficient.

## Permission Model

### Always Okay
- Read files in approved repos
- Search code and inspect repo state
- Read approved subfolders for reference
- Edit directly relevant files in assigned scope
- Run safe local tests
- Run safe git reads like `status`, `diff`, `log`

### Ask First
- Anything touching live trading behavior
- Changing risk thresholds, sizing, kill switches, or strategy params
- Broad refactors beyond assigned scope
- Editing Claude-owned state/handoff files
- Network actions material to task execution
- Publishing actions or git operations that may surprise current repo state

### Never Without Explicit Approval
- Destructive commands
- Touching credentials, `.env`, or sensitive config
- System/global config changes
- Package installs unless truly necessary
- Running live trading or exchange-connected workflows

## Coordination Protocol

Phase 1 coordination artifact: git commit messages only.

Workflow:
1. Matthew assigns repo, task, constraints, and whether push is desired.
2. Codex reads repo rules and authoritative state first.
3. Codex states:
   - target repo
   - reasoning level (`default` or `high recommended`)
   - permission profile
   - intended file/edit scope
4. Codex performs focused work only in assigned scope.
5. Codex runs appropriate local tests when practical.
6. Codex uses descriptive commit titles.
7. If needed, Codex uses commit message body text as a handoff note to Claude Code.
8. Claude Code reads `git log` and treats commit messages as Codex handoff notes.
9. If no code change occurs but a conclusion matters, Matthew relays it manually.

Repo-local bridge files:
- `CLAUDE_TO_CODEX.md` for Claude Code -> Codex notes
- `CODEX_TO_CLAUDE.md` for Codex -> Claude Code durable notes

## Codex Init / Auto / Wrap Emulation

Codex should mirror the useful parts of CCA's workflow without pretending the
platform hooks are identical.

Preferred desktop-app entrypoint:
- Use `$cca-desktop-workflow`
- Canonical repo source: `codex-skills/cca-desktop-workflow/`
- See `CODEX_DESKTOP_WORKFLOW.md` for ready-to-paste prompts

Init:
- Read `AGENTS.md`
- Read the authoritative state file
- In CCA, read `TODAYS_TASKS.md` when present
- Treat `SESSION_RESUME.md` as the full next-chat handoff written by `/cca-wrap`
- Check `git status` and recent `git log`
- State repo, reasoning level, risk profile, and file scope before substantive work

Auto:
- Work in focused loops on one task at a time
- Prefer default reasoning unless the task justifies high
- Keep edits narrow, validate with local tests when practical, and use branch-first workflow
- Use commit messages as durable handoff notes to Claude Code

Wrap:
- Stop before context gets muddy
- Summarize outcome, tests, open issues, and next best step
- Prepare a short relay message for Matthew / Claude Code when needed
- Distill durable lessons into `CODEX_LEARNINGS.md` when they are likely to matter again

Autoloop:
- In Codex desktop, autoloop means one bounded init -> auto -> wrap cycle
- Do not emulate Claude's CLI respawn loop literally inside the app
- For recurrence, prefer Codex Automations that run one cycle per trigger

## Context Reset Guidance

Start a fresh Codex chat when:
- a branch or substantive task is complete
- the conversation has mixed multiple repos or goals
- large logs or long pasted context are crowding out the active task
- Codex starts needing old context re-pasted
- Matthew wants a clean handoff with repo + task + branch + latest commit

Default heuristic:
- stay in the current chat for one focused task or one branch
- start a new chat when the work meaningfully changes direction

## Self-Learning Emulation

Codex cannot replicate Claude Code's full hook/memory stack from inside a
session, but it can emulate the valuable parts locally:

- Study Claude-built repo tools and docs in read-only mode
- Reuse patterns that are objectively helpful
- Capture stable lessons in Codex-owned docs
- Favor small, durable heuristics over giant memory dumps

`CODEX_LEARNINGS.md` is the local reference for durable Codex-specific lessons,
workflow heuristics, and recurring gotchas worth reusing across sessions.

## Role Split

Claude Code owns:
- Session state management
- Self-learning infrastructure
- Cross-chat coordination
- Autonomous monitoring loops
- Live trading operations and operational safety ownership
- Authoritative state-file updates

Codex owns:
- Focused implementation
- Bug fixes
- Code review
- Research
- Architecture second opinions
- Overflow work when Claude Code is limited or busy
- Backup execution lane when Anthropic limits interfere with progress

Codex is also a good reviewer of Claude Code's work, especially for catching
blind spots that self-review can miss.

## Prompt Template

Matthew should prefer prompts like:

```text
Repo: <repo name>
Task: <exact task>
Scope: <files or directories allowed>
Constraints: <important safety limits>
Reasoning: default unless high is justified
Push: yes/no
```

## Codex Behavior Expectations

Codex should:
- Be concise by default
- Coach Matthew on when to use higher reasoning
- Remind him about scope and permissions when it matters
- Avoid turning every exchange into a long procedural lecture
- Optimize for useful execution, not prompt perfection

## Safe Approvals Reference

### Permanently Safe (auto-approve these)

| Command | Why safe |
|---------|----------|
| `git status` | Read-only |
| `git diff` | Read-only |
| `git log` | Read-only |
| `git checkout <branch>` | Local branch switch |
| `git add <specific file>` | Staging only |
| `git commit -m "..."` | Local commit |
| `git push` | Standard push (no force) |
| `python3 -m pytest` | Test runner |
| `python3 parallel_test_runner.py` | CCA test runner |

### Never Auto-Approve (always block or ask Matthew)

| Command pattern | Risk |
|-----------------|------|
| Arbitrary `python3 <script>` | Unknown execution |
| Arbitrary `bash` | Unknown execution |
| `pip install` / package installs | Dependency risk |
| `git reset --hard` | Destroys uncommitted work |
| `git push --force` | Destroys remote history |
| `git branch -D` | Destroys branches |
| `rm -rf` / mass delete | Destroys files |
| Anything with `.env`, keys, secrets | Credential exposure |
| Anything touching live trading | Financial risk |
| `--dangerously-skip-permissions` | Safety bypass |

### Grey Area (use judgment, prefer asking)

- `python3 <known project script>` with known arguments — okay if in scope
- `git stash` — safe but ask if unsure about stash state
- File creation in assigned scope — okay
- File creation outside scope — ask first

## Best Uses of Codex

High-value use cases:
- Focused coding tasks
- Debugging
- Code review of Claude Code commits
- Research summaries
- Architecture comparisons
- Overflow work during Claude rate limits

Lower-value use cases:
- Recreating Claude-specific hook ecosystems from scratch unless assigned
- Owning long-running project memory/state infrastructure
