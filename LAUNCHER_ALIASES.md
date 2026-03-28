# Launcher Aliases

Three commands to launch Claude Code from any terminal. Already configured in `~/.zshrc`.

## Usage

| Command | What it does |
|---------|-------------|
| `cc` | Generic Claude Code in current directory (no model override) |
| `cca` | CCA project + Opus 4.6 |
| `ccbot` | Kalshi project + Sonnet 4.6 |

## After editing ~/.zshrc

If you just opened a new terminal, aliases are already loaded. If you changed them mid-session:

```bash
source ~/.zshrc
```

## What each alias expands to

```bash
cc     →  claude --dangerously-skip-permissions
cca    →  cd ~/Projects/ClaudeCodeAdvancements && claude --dangerously-skip-permissions --model opus
ccbot  →  cd ~/Projects/polymarket-bot && claude --dangerously-skip-permissions --model sonnet
```

## Notes

- `cca` and `ccbot` change your terminal's cwd to the project dir before launching
- Model split enforced at launch: CCA always Opus 4.6, Kalshi always Sonnet 4.6
- `cc` stays in whatever directory you're in and uses your account's default model
