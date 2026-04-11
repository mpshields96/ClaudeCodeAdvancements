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
- A full CCA hivemind member when Matthew explicitly wants CCA-quality workflow inside Codex

Codex is not:
- A replacement for Claude Code's long-running memory/hook infrastructure
- An autonomous operator for live trading workflows

## Read-First Rules

Before substantive work, Codex should read:
1. `AGENTS.md`
2. The fast-orientation index / authoritative state stack for the repo
   - CCA: `SESSION_STATE.md`
   - polybot: `SESSION_HANDOFF.md`
   - In CCA, also read `PROJECT_INDEX.md`, `TODAYS_TASKS.md`, `MATTHEW_DIRECTIVES.md`, `CODEX_PRIME_DIRECTIVE.md`, `SESSION_RESUME.md`, and `CLAUDE_TO_CODEX.md`
3. Any directly relevant local docs for the assigned task

These state files remain authoritative. In CCA-equal mode, Codex is expected to
keep them current when it lands work, rather than treating them as read-only.

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
- `CCA_TO_POLYBOT.md` / `POLYBOT_TO_CCA.md` are mandatory bridge context when Kalshi coordination is relevant
- `python3 bridge_status.py` is the canonical tri-chat freshness / relay-gap check

Dual-notify rule for Kalshi-bot changes:
- If Codex changes `/Users/matthewshields/Projects/polymarket-bot/`, Codex must notify both CCA and Kalshi.
- Immediate visibility: send a CCA queue note to desktop and a Kalshi relay note (`km` and/or `kr`) via `cca_comm.py`.
- Durable visibility: append the outcome to `CODEX_TO_CLAUDE.md` so CCA can replay it on future init/wrap.
- Do this for code changes, bug fixes, parameter-safe hardening, and any other repo edits that materially affect Kalshi behavior or operator understanding.
- Do not assume CCA will relay later. Dual notification is the default, not a special case.

Advancement execution rule:
- When Codex identifies an actionable advancement tip, Codex should execute it or codify it during the same workstream whenever it is safe and in scope.
- Screen for no-brainer follow-through during init and wrap: if a tip can be implemented, logged, or turned into a durable operating rule in under ~15 minutes without expanding risk, do it now instead of carrying it as advice.
- Do not end the session with "Advancement tip: ..." as a suggestion-only footer if the underlying improvement can be implemented, logged, or turned into a durable operating rule right now.
- Treat these tips as required follow-through, not optional inspiration.
- Report what was done as `Advancement follow-through: ...`, not as a dangling suggestion. Only emit a remaining tip when blocked, out of scope, or risky.

Operational proof rule:
- Unit tests and static reasoning do not prove an operational helper works in the live repo.
- Any startup gate, wrap helper, bridge command, or operator-facing workflow should be live-probed at least once before Codex treats it as trustworthy.
- If the live probe disagrees with the tested design, log the runtime truth immediately and prioritize the runtime blocker over the cleaner paper design.

## Codex Init / Auto / Wrap Emulation

Codex should mirror the useful parts of CCA's workflow without pretending the
platform hooks are identical.

Preferred terminal entrypoint for now:
- `cx` in the current repo
- `cxa` for `/Users/matthewshields/Projects/ClaudeCodeAdvancements`
- `cxbot` for `/Users/matthewshields/Projects/polymarket-bot`
- `bash launch_codex.sh` / `bash launch_codex.sh kalshi` for fresh Terminal.app windows
- See `CODEX_TERMINAL_WORKFLOW.md` for the Terminal-first setup

Command simplification:
- Treat `codex auto` as the single continuation/work command
- `codex next` may still exist as a compatibility alias, but it should not carry separate workflow meaning

Prime directive:
- `CODEX_PRIME_DIRECTIVE.md` is mandatory reading for CCA Codex chats
- Default to stealing and adapting proven CCA machinery before building Codex-only parallel systems

Preferred desktop-app entrypoint:
- Use `$cca-desktop-workflow`
- Canonical repo source: `codex-skills/cca-desktop-workflow/`
- See `CODEX_DESKTOP_WORKFLOW.md` for ready-to-paste prompts

Init:
- Verify the active repo root is the canonical CCA repo before substantive work
- Read `AGENTS.md`
- Read `PROJECT_INDEX.md`, the authoritative state file, `TODAYS_TASKS.md`, `MATTHEW_DIRECTIVES.md`, `CODEX_PRIME_DIRECTIVE.md`, `SESSION_RESUME.md`, and `CLAUDE_TO_CODEX.md`
- Surface CCA self-learning context when available: `wrap_tracker.py trend`, `tip_tracker.py pending`, `session_outcome_tracker.py init-briefing`, and `self-learning/resurfacer.py corrections --days 7`
- Surface CCA optimization context when available: `priority_picker.py init-briefing`, `priority_picker.py recommend`, `mt_originator.py --briefing`, `session_timeline.py recent 5`, and `hivemind_session_validator.format_for_init()`
- Treat `SESSION_RESUME.md` as the full next-chat handoff written by `/cca-wrap`
- Check `git status` and recent `git log`
- State repo, reasoning level, risk profile, and file scope before substantive work

Auto:
- Work in focused loops on one task at a time
- Respect CCA task order: `TODAYS_TASKS.md` first, then `SESSION_RESUME.md`, then `SESSION_STATE.md`
- Re-check the surfaced self-learning signals before drifting scope or repeating a recent mistake
- Re-check the surfaced optimization signals before falling back to stale task memory or ad hoc task picking
- If `tip_tracker.py pending` surfaces an actionable no-brainer improvement that fits the current workstream, implement or codify it before mentioning it to Matthew as advice.
- Run `python3 bridge_status.py` at the start of coordination rounds instead of freehand checking bridge files in random order
- Prefer default reasoning unless the task justifies high
- Keep edits narrow, validate with local tests when practical, and use branch-first workflow
- Use commit messages as durable handoff notes to Claude Code
- If work changes the Kalshi bot, notify both CCA and Kalshi before moving on

Wrap:
- Stop before context gets muddy
- If Codex landed meaningful CCA work, update `SESSION_STATE.md`, `PROJECT_INDEX.md`, `CHANGELOG.md`, and `SESSION_RESUME.md` as needed
- Feed CCA's learning loop when useful via `wrap_tracker.py`, `tip_tracker.py`, `session_outcome_tracker.py`, and journal/correction tooling
- Summarize outcome, tests, open issues, and next best step
- Include `Advancement follow-through:` in the wrap summary when a tip was executed or codified during the session.
- Prepare a short relay message for Matthew / Claude Code when needed
- Distill durable lessons into `CODEX_LEARNINGS.md` when they are likely to matter again
- For Kalshi-bot changes, confirm both CCA and Kalshi were notified, not just one lane

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

Codex owns:
- Focused implementation
- Bug fixes
- Code review
- Research
- Architecture second opinions
- Overflow work when Claude Code is limited or busy
- Backup execution lane when Anthropic limits interfere with progress

In explicit CCA-equal mode, Codex also updates the same shared CCA session docs
that Claude would normally update, provided the edits reflect real session work
and the repo stays internally consistent.

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
