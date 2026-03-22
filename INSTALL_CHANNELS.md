# Install Claude Code Channels (Telegram + Discord)
# MT-23 — Externally resolved by Anthropic (shipped 2026-03-20)
# Copy-paste these steps. No thinking required.

## Prerequisites

- Claude Code v2.1.80+ (check: `claude --version`)
- claude.ai login (not API key — Console/API auth not supported)
- Bun runtime (for official plugins): `brew install oven-sh/bun/bun`

---

## Option A: Telegram (Recommended for Matthew)

### Step 1: Create a Telegram Bot

1. Open Telegram on phone
2. Search for `@BotFather`
3. Send `/newbot`
4. Name it whatever (e.g. "Claude CCA Bot")
5. Copy the API token it gives you

### Step 2: Start Claude with Telegram Channel

```bash
claude --channels plugin:telegram@anthropic
```

### Step 3: Pair Your Phone

1. The bot will print a pairing URL in terminal
2. Open it on your phone
3. DM the bot from your Telegram account
4. Bot sends a pairing code
5. Approve in Claude Code terminal

### Step 4: Test

1. Send a message from Telegram: "what's the current git status?"
2. Claude should respond in your terminal AND reply in Telegram

---

## Option B: Discord

### Step 1: Create a Discord Bot

1. Go to https://discord.com/developers/applications
2. Create new application
3. Bot tab -> Add Bot -> Copy token
4. OAuth2 -> URL Generator -> Select `bot` scope + `Send Messages` permission
5. Use generated URL to add bot to your server

### Step 2: Start Claude with Discord Channel

```bash
claude --channels plugin:discord@anthropic
```

### Step 3: Pair (same flow as Telegram)

---

## For Session Daemon Integration (MT-30)

When the session daemon launches sessions, add `--channels` flag:

```json
{
  "id": "cca-desktop",
  "command": "claude --channels plugin:telegram@anthropic /cca-init",
  ...
}
```

This means every daemon-managed session is phone-accessible.

---

## Known Limitations (Research Preview)

- Requires claude.ai login (not API key auth)
- Team/Enterprise orgs must explicitly enable channels
- Custom channels need `--dangerously-load-development-channels` flag
- Context loss after long sessions reported (GitHub issue #28402)
- Signal not supported yet (community requested)

## Source

- Docs: https://code.claude.com/docs/en/channels-reference
- Plugins: https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins
