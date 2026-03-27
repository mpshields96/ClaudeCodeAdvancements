# Codex Desktop Workflow

This is the Codex macOS desktop-app version of CCA's command system.

Claude Code has slash commands like `/cca-init`, `/cca-auto-desktop`, and `/cca-wrap-desktop`.
Codex desktop does not expose the same command mechanism, so the Codex-native equivalent is:

- an installed skill: `$cca-desktop-workflow`
- short mode prompts for `init`, `auto`, `wrap`, and `autoloop`

## Install Location

Canonical source lives in this repo:
- `codex-skills/cca-desktop-workflow/`

Desktop-app install target:
- `~/.codex/skills/cca-desktop-workflow`

The recommended setup is a symlink from the home skill directory to the repo copy so changes stay versioned here.

## Command Equivalents

| CCA Claude command | Codex desktop equivalent |
|---|---|
| `/cca-init` | `Use $cca-desktop-workflow in init mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.` |
| `/cca-auto-desktop` | `Use $cca-desktop-workflow in auto mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.` |
| `/cca-wrap-desktop` | `Use $cca-desktop-workflow in wrap mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.` |
| autoloop | `Use $cca-desktop-workflow in autoloop mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.` |

## Ready-To-Paste Prompts

### Init

```text
Use $cca-desktop-workflow in init mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.
Goal: orient, verify branch/state, and prepare the next high-value task.
```

### Auto

```text
Use $cca-desktop-workflow in auto mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.
Stay in CCA only. Pick the next highest-value task, work autonomously, test when practical, and commit clearly.
Use CCA internal comms directly when coordination matters.
```

### Wrap

```text
Use $cca-desktop-workflow in wrap mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.
Run the relevant validation, summarize the outcome, commit if ready, and send any needed note directly through CCA comms.
```

Repo-local wrap command:

```bash
python3 codex_wrap.py
python3 codex_wrap.py --write CODEX_WRAP_PROMPT.md
```

### Autoloop

```text
Use $cca-desktop-workflow in autoloop mode for /Users/matthewshields/Projects/ClaudeCodeAdvancements.
Run one bounded autonomous cycle: init, execute up to 2 meaningful tasks, then wrap.
Do not use Matthew as the messenger if CCA comms can carry the handoff.
```

## Codex-Specific Difference

Codex autoloop should be adapted, not copied literally.

In Claude, autoloop respawns sessions from shell scripts and resume files.
In Codex desktop, the better equivalent is:
- one bounded `autoloop` cycle inside the current chat, or
- a Codex Automation that runs one such cycle on a schedule

If you want recurring unattended Codex sessions, ask Codex to turn the autoloop prompt into an Automation.
