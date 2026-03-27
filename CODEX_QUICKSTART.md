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

## Codex session ritual

1. Init
   - Read `AGENTS.md`
   - Read the authoritative state file
   - In CCA, read `TODAYS_TASKS.md` when present
   - Check `git status` / `git log`
2. Auto
   - Work in focused loops
   - Use default reasoning unless I explicitly recommend high
   - Keep scope narrow, test when practical, commit clearly
3. Wrap
   - Summarize what changed
   - Report tests run and current branch
   - Call out open risks or blockers
   - Prepare a short relay message for Claude Code when useful

## Codex self-learning

- Read-only study of Claude-built tools, docs, and patterns is encouraged
- Distill stable lessons into `CODEX_LEARNINGS.md`
- Prefer cloning useful patterns into Codex-owned docs/workflows instead of mutating Claude-owned infrastructure
- Keep the learned rules lightweight, practical, and repo-local

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
