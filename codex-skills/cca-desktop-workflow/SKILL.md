---
name: cca-desktop-workflow
description: Use when working in /Users/matthewshields/Projects/ClaudeCodeAdvancements from the Codex macOS desktop app and you want CCA-style init, auto, wrap, or autoloop behavior. Mirrors /cca-init, /cca-auto-desktop, /cca-wrap-desktop, and autoloop in a Codex-native way using repo checks, focused work loops, queue comms, and optional app automations.
---

# CCA Desktop Workflow

Use this skill only for the CCA repo:
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements`

This skill is the Codex desktop-app analogue of CCA's Claude slash commands:
- `/cca-init`
- `/cca-auto-desktop`
- `/cca-wrap-desktop`
- autoloop

Codex does not have identical slash-command hooks, so this skill emulates the workflow through explicit mode selection.

## Mode Selection

Ask for one of these modes explicitly:
- `init`
- `auto`
- `wrap`
- `autoloop`

Good prompts:
- `Use $cca-desktop-workflow in init mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.`
- `Use $cca-desktop-workflow in auto mode on main for the next CCA task.`
- `Use $cca-desktop-workflow in wrap mode and close out this CCA session.`
- `Use $cca-desktop-workflow in autoloop mode for one bounded autonomous CCA cycle.`

Short in-chat prompts are also valid and should be interpreted the same way:
- `CCA init`
- `CCA auto`
- `CCA wrap`
- `CCA autoloop`

Optional short forms with scope:
- `CCA auto on MT-53`
- `CCA autoloop on Pokemon viewer testing`
- `CCA wrap this CCA session`

When these short prompts are used in Codex desktop chat, treat them as invoking
this skill for the CCA repo with the matching mode, even if the user does not
repeat the full repo path.

## Init Mode

When invoked in `init` mode:
1. Read `AGENTS.md`.
2. Read `SESSION_STATE.md`.
3. Read `TODAYS_TASKS.md` when present.
4. Read Codex-side docs if relevant:
   - `CODEX_OPERATING_MANUAL.md`
   - `CODEX_QUICKSTART.md`
   - `CLAUDE_TO_CODEX.md`
5. Check `git status --short` and recent `git log --oneline`.
6. Check `cca_comm.py inbox` or the internal queue when the task involves coordination.
7. Run a reasonable baseline validation for the assigned scope.

Init mode should end with a compact briefing:
- current branch
- dirty/runtime files worth ignoring
- top task
- suggested reasoning level
- immediate next step

## Auto Mode

When invoked in `auto` mode:
1. Prefer `TODAYS_TASKS.md` first.
2. Fall through to `SESSION_STATE.md`, repo priorities, and live queue requests only after today's tasks are clear or the user scoped you elsewhere.
3. Work in focused loops with narrow scope.
4. Test when practical before and after edits.
5. Commit after each meaningful deliverable.
6. Use CCA internal comms directly when coordination matters; do not turn Matthew into a relay.
7. Keep going until a natural wrap point instead of pausing after each small task.

Default target: 1-2 meaningful deliverables per Codex session unless the user says otherwise.

## Wrap Mode

When invoked in `wrap` mode:
1. Run the most relevant validation for the changed scope.
2. Summarize what changed, what passed, and any remaining risks.
3. Commit clearly if the work is ready.
4. Send a direct CCA queue note to desktop when the conclusion belongs inside the CCA comms system.
5. Update Codex-owned docs only:
   - `CODEX_LEARNINGS.md`
   - `CODEX_QUICKSTART.md`
   - `CODEX_OPERATING_MANUAL.md`

Do not mutate Claude-owned state files unless explicitly assigned.

To generate a ready-to-paste wrap command from live repo state, run:
- `python3 codex_wrap.py`
- `python3 codex_wrap.py --write CODEX_WRAP_PROMPT.md`

## Autoloop Mode

Codex desktop app autoloop should be adapted, not copied literally.

In Codex:
- Do not try to self-spawn fresh desktop sessions from inside the current chat.
- Treat `autoloop` as one bounded autonomous cycle:
  - init
  - execute 1-2 meaningful tasks
  - wrap
- For recurring unattended runs, prefer Codex app Automations instead of shell respawn loops.

When invoked in `autoloop` mode:
1. Run `init` behavior first.
2. Execute the next highest-value CCA task in `auto` behavior.
3. Continue until one of these is true:
   - 1-2 meaningful tasks are complete
   - context is getting muddy
   - validation reveals a blocker
   - the user-specified stop condition is met
4. Run `wrap` behavior before stopping.

If the user explicitly wants recurrence, propose or create a Codex automation that runs one autoloop cycle per trigger.

## Command Mapping

Use this translation table:

| Claude CCA command | Codex desktop equivalent |
|---|---|
| `/cca-init` | `Use $cca-desktop-workflow in init mode ...` |
| `/cca-auto-desktop` | `Use $cca-desktop-workflow in auto mode ...` |
| `/cca-wrap-desktop` | `Use $cca-desktop-workflow in wrap mode ...` |
| `cca_autoloop.py` / desktop autoloop | `Use $cca-desktop-workflow in autoloop mode ...` plus optional Codex Automation |

## References

For the full Claude-side source material, read only what is needed:
- `.claude/commands/cca-init.md`
- `.claude/commands/cca-auto-desktop.md`
- `.claude/commands/cca-wrap-desktop.md`
- `cca_autoloop.py`

For Codex-side grounding:
- `CODEX_OPERATING_MANUAL.md`
- `CODEX_QUICKSTART.md`
- `CODEX_BRIDGE_PROMPT.md`
- `codex_wrap.py`
