# Fix: Claude Code Using API Billing Instead of Max Subscription

## Problem
~/.zshrc has `export ANTHROPIC_API_KEY="sk-ant-..."` which forces Claude Code
to use API billing ($) instead of your Max 5x subscription (OAuth, free with plan).

## Fix (copy-paste these two lines)

```bash
sed -i '' 's/^export ANTHROPIC_API_KEY/# export ANTHROPIC_API_KEY/' ~/.zshrc
unset ANTHROPIC_API_KEY
```

Line 1: Comments out the export in .zshrc (permanent fix for new terminals)
Line 2: Removes it from your current terminal session (immediate fix)

## Verify

After running the fix, start claude in any terminal:
```bash
cd ~/Projects/polymarket-bot && cc
```

You should see "Max" in the status line, NOT "API Usage Billing".

## If Python scripts need the API key

If polymarket-bot Python code uses `anthropic.Anthropic()` and needs the key:
- Add a `.env` file in polymarket-bot with `ANTHROPIC_API_KEY=sk-ant-...`
- Or set it only in the Python script's environment, not globally

## Launch scripts already handle this

Both launch_worker.sh and launch_kalshi.sh already have `unset ANTHROPIC_API_KEY`
baked in, so if you launch through those scripts, this isn't needed. But the
permanent .zshrc fix prevents the issue everywhere.
