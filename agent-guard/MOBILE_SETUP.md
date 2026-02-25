# Mobile Approver — iPhone Setup Guide
# Get Claude Code permission prompts on your iPhone lock screen.
# Tap Allow or Deny. Claude waits for your answer.

---

## What this does

When Claude Code wants to run a Bash command, write a file, or edit code,
this hook fires a push notification to your iPhone with two buttons:
- **Allow** — Claude proceeds
- **Deny** — Claude stops and tells you why it was blocked

Read-only operations (Read, Glob, Grep, WebSearch) are silently allowed — no noise.

---

## One-time setup (5 minutes)

### Step 1 — Install ntfy on iPhone
App Store: search "ntfy" or go to https://apps.apple.com/app/ntfy/id1625396347
It's free. No account required.

### Step 2 — Pick a unique topic name
This is your personal channel. Must be unique — something no one else would guess.
Example: `cc-mpshields96` or `claudecode-matt-2026`

Write it down. You'll use it in two places.

### Step 3 — Subscribe in the ntfy app
1. Open ntfy on iPhone
2. Tap the **+** button
3. Enter your topic name exactly as you chose it
4. Tap Subscribe

### Step 4 — Set the environment variable on your Mac
Add this to your `~/.zshrc` (or `~/.bash_profile`):

```bash
export MOBILE_APPROVER_TOPIC=your-topic-name-here
```

Then reload:
```bash
source ~/.zshrc
```

### Step 5 — Register the hook in Claude Code

Add to `~/.claude/settings.json` (the global Claude Code config, NOT settings.local.json):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/agent-guard/hooks/mobile_approver.py"
          }
        ]
      }
    ]
  }
}
```

If you already have other PreToolUse hooks (like spec-system/hooks/validate.py),
add this as an additional entry in the hooks array.

### Step 6 — Test it
```bash
echo '{"tool_name":"Bash","tool_input":{"command":"echo hello"}}' | \
  MOBILE_APPROVER_TOPIC=your-topic-name \
  python3 agent-guard/hooks/mobile_approver.py
```

Your iPhone should buzz within 2 seconds. Tap Allow or Deny. The terminal
should print the corresponding JSON decision.

---

## Configuration options

| Env var | Default | What it does |
|---------|---------|-------------|
| `MOBILE_APPROVER_TOPIC` | (none) | Your ntfy topic. Required. Without it, hook is a no-op. |
| `MOBILE_APPROVER_TIMEOUT` | `60` | Seconds to wait for your response before using default |
| `MOBILE_APPROVER_DEFAULT` | `allow` | What to do on timeout: `allow` or `deny` |
| `MOBILE_APPROVER_DISABLED` | `0` | Set to `1` to disable without removing the hook |

**Recommended timeout settings:**
- Normal use: `60` (you have 60 seconds to respond)
- Fully automated overnight runs: `0` with `MOBILE_APPROVER_DEFAULT=allow`
- High-security mode: `120` with `MOBILE_APPROVER_DEFAULT=deny`

For automated sessions where you don't want to be interrupted:
```bash
MOBILE_APPROVER_DISABLED=1 claude -p "$(cat .claude/prompts/auto-session.md)" --dangerously-skip-permissions
```

---

## What triggers a notification

| Tool | Triggers notification? |
|------|----------------------|
| Bash | YES |
| Write | YES |
| Edit | YES |
| Task (subagents) | YES |
| NotebookEdit | YES |
| Read | no |
| Glob | no |
| Grep | no |
| WebFetch / WebSearch | no |
| TodoWrite | no |

---

## Troubleshooting

**No notification received:**
- Check `MOBILE_APPROVER_TOPIC` is set: `echo $MOBILE_APPROVER_TOPIC`
- Check ntfy app is subscribed to exactly that topic name (case-sensitive)
- Test ntfy directly: `curl -d "test" ntfy.sh/your-topic-name`

**Hook times out and allows without waiting:**
- Increase `MOBILE_APPROVER_TIMEOUT`: `export MOBILE_APPROVER_TIMEOUT=120`

**Hook blocks all operations even when disabled:**
- Check `MOBILE_APPROVER_DISABLED=1` is exported in the shell running Claude Code

**Allow/Deny buttons don't appear:**
- Ensure ntfy app notifications are enabled in iOS Settings → Notifications → ntfy
- Buttons only appear in expanded notification view (long press the notification)
