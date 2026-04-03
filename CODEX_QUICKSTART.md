# Codex Quickstart

## Open in repo root (not whole computer)

Always open Codex pointed at one of these:
- `/Users/matthewshields/Projects/ClaudeCodeAdvancements/`
- `/Users/matthewshields/Projects/polymarket-bot/`

## Task template (copy-paste this)

```text
Repo: ClaudeCodeAdvancements
Task: <what to do>
Scope: <files or directories>
Branch: codex/<task-name>
Push: yes/no
```

## Start a new chat when

- We finish a branch or 1-2 substantive tasks
- I start re-reading the same files or need old context re-pasted
- The thread accumulates lots of logs, handoffs, or mixed topics
- You want a clean repo/task handoff with minimal token waste
- The working context feels muddy; start fresh with repo + task + branch + latest commit
- Roughly every 60-90 minutes of focused work if the chat is still active

## Wrap now when

- A commit-ready deliverable is done
- We are about to change repos, branches, or tasks
- The current chat has solved the thing it was opened for
- The thread is getting mixed-topic and expensive
- We need a clean handoff point for Claude Code or the next Codex chat

## Codex session ritual

1. Init
   - Read `AGENTS.md`
   - In CCA, read `PROJECT_INDEX.md`, `SESSION_STATE.md`, `TODAYS_TASKS.md`, `MATTHEW_DIRECTIVES.md`, `CODEX_PRIME_DIRECTIVE.md`, `SESSION_RESUME.md`, and `CLAUDE_TO_CODEX.md`
   - Surface CCA learning context: `wrap_tracker.py trend`, `tip_tracker.py pending`, `session_outcome_tracker.py init-briefing`, `self-learning/resurfacer.py corrections --days 7`
   - Surface CCA optimization context: `priority_picker.py init-briefing`, `priority_picker.py recommend`, `mt_originator.py --briefing`, `session_timeline.py recent 5`, `hivemind_session_validator.format_for_init()`
   - Treat `SESSION_RESUME.md` as the full next-chat handoff written by `/cca-wrap`
   - Check `git status` / `git log`
2. Auto
   - Work in focused loops
   - Respect CCA task order: `TODAYS_TASKS.md` first, then `SESSION_RESUME.md`, then `SESSION_STATE.md`
   - Re-check the surfaced self-learning signals before repeating scope or old mistakes
   - Re-check the surfaced optimization signals before choosing fallback work
   - Use default reasoning unless I explicitly recommend high
   - Keep scope narrow, test when practical, commit clearly
3. Wrap
   - Update `SESSION_STATE.md`, `PROJECT_INDEX.md`, `CHANGELOG.md`, and `SESSION_RESUME.md` when this Codex session materially changed CCA state
   - Feed CCA learning tools when useful (`wrap_tracker.py`, `tip_tracker.py`, `session_outcome_tracker.py`, correction/journal tooling)
   - Summarize what changed
   - Report tests run and current branch
   - Call out open risks or blockers
   - Prepare a short relay message for Claude Code when useful

## Terminal First

Current default is Terminal.app, not the Codex desktop app.

Direct launch options after sourcing `codex_shell_helpers.sh` from `~/.zshrc`:
- `cx` — prepare the current terminal for the Codex workflow and show next commands
- `cxa` — jump to `~/Projects/ClaudeCodeAdvancements` and run `cx`
- `cxbot` — jump to `~/Projects/polymarket-bot` and run `cx`
- `codex init` — launch a fresh init chat for the current repo and refresh `CODEX_INIT_PROMPT.md`
- `codex auto` — the canonical fresh continuation/work chat for the current repo; refreshes `CODEX_AUTO_PROMPT.md`
- `codex next` — legacy alias for `codex auto`
- `codex wrap` — launch a fresh wrap chat for the current repo and refresh `CODEX_WRAP_PROMPT.md`
- `codex chat "<prompt>"` — launch an ad-hoc direct Codex chat
- `bash launch_codex.sh` — open a fresh Terminal.app window for CCA and start Codex with `CCA init`
- `bash launch_codex.sh kalshi` — open a fresh Terminal.app window for Kalshi and start Codex with `Kalshi init`

Prompt examples:
- `cxa`
- `codex init`
- `codex auto`
- `cxbot`
- `codex init`
- `bash launch_codex.sh cca "CCA init"`
- `bash launch_codex.sh kalshi "Kalshi init"`

Terminal workflow reference:
- `CODEX_TERMINAL_WORKFLOW.md`

## Desktop Skill

Codex desktop app equivalent of CCA slash commands:
- Skill: `$cca-desktop-workflow`
- Canonical source: `codex-skills/cca-desktop-workflow/`

Quick invocations:
- `Use $cca-desktop-workflow in init mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.`
- `Use $cca-desktop-workflow in auto mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.`
- `Use $cca-desktop-workflow in wrap mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.`
- `Use $cca-desktop-workflow in autoloop mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.`

Short in-chat equivalents:
- `CCA init`
- `CCA auto`
- `CCA wrap`
- `CCA autoloop`

Wrap command:
- `python3 codex_wrap.py`
- `python3 codex_wrap.py --write CODEX_WRAP_PROMPT.md`

Bridge files:
- `CLAUDE_TO_CODEX.md` — Claude Code -> Codex notes
- `CODEX_TO_CLAUDE.md` — Codex -> Claude Code durable handoff notes

Fresh-chat handoff artifact:
- `CODEX_AUTO_PROMPT.md` — refreshed by `codex auto`; `codex next` still points here as a legacy alias

Repo-local Codex command helpers:
- `python3 codex_init.py`
- `python3 codex_auto.py`
- `python3 codex_autoloop.py`
- `python3 codex_autoloop.py --max-deliverables 2`
- `bash launch_codex.sh`
- `bash launch_codex.sh kalshi`

## Codex self-learning

- Read-only study of Claude-built tools, docs, and patterns is encouraged
- Distill stable lessons into `CODEX_LEARNINGS.md`
- Prefer cloning useful patterns into Codex-owned docs/workflows instead of mutating Claude-owned infrastructure
- Keep the learned rules lightweight, practical, and repo-local

## Codex Prime Directive

- `CODEX_PRIME_DIRECTIVE.md` is the standing rule for Codex CCA chats
- Default move: steal and adapt CCA's proven briefing, self-learning, and workflow tools
- Do not build a parallel Codex-only system when a thin adapter around an existing CCA system will do

## Safe commands (always okay)

```
git status
git diff
git log
git checkout <branch>
git add <specific file>
git commit -m "message"
git push
python3 -m pytest
python3 parallel_test_runner.py --quick --workers 8
```

## Never approve (block these)

- Arbitrary `python3 <unknown script>`
- Arbitrary `bash` commands
- `pip install` / package installs
- `git reset --hard` / `git push --force` / `git branch -D`
- `rm -rf` or any destructive filesystem commands
- Anything touching `.env`, API keys, credentials, or secrets
- Anything touching live trading parameters or exchange APIs
- `--dangerously-skip-permissions` or equivalent overrides
