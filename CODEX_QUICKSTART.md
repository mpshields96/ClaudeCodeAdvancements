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
