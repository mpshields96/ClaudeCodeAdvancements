# Install Discord Channels for Claude Code (SECONDARY — Notification Fallback)
# Primary mobile path: Remote Control (zero-setup, see MT23_MOBILE_RESEARCH.md)
# Discord is for push notifications when RC is unavailable.
# Copy-paste each step. One at a time.

## Prerequisites (one-time)

### Step 1: Check Claude Code version
```bash
claude --version
```
Need v2.1.80 or later. If older, update Claude Code first.

### Step 2: Install Bun (if not installed)
```bash
bun --version
```
If "command not found":
```bash
curl -fsSL https://bun.sh/install | bash
```

### Step 3: Create Discord Bot
1. Go to https://discord.com/developers/applications
2. Click "New Application" — name it "CCA Claude Bridge"
3. Go to Bot section — click "Reset Token" — COPY THE TOKEN
4. Enable "Message Content Intent" (under Privileged Gateway Intents)
5. Go to OAuth2 — URL Generator:
   - Scopes: bot
   - Bot Permissions: View Channels, Send Messages, Read Message History, Attach Files, Add Reactions
6. Copy the generated URL — open it — add bot to your personal Discord server

## Setup (in Claude Code)

### Step 4: Install plugin
```
/plugin marketplace add anthropics/claude-plugins-official
/plugin install discord@claude-plugins-official
```

### Step 5: Configure token
```
/discord:configure PASTE_YOUR_BOT_TOKEN_HERE
```

### Step 6: Restart Claude Code with channels
```bash
claude --channels plugin:discord@claude-plugins-official
```

### Step 7: Pair your account
1. Open Discord on iPhone (or desktop)
2. DM your bot — send any message
3. Bot replies with a pairing code
4. In Claude Code, run:
```
/discord:access pair PASTE_CODE_HERE
```

### Step 8: Lock down (security)
```
/discord:access policy allowlist
```

## Done! Test it.
Send a DM to your bot from Discord. Claude should respond.

## To use daily:
```bash
claude --channels plugin:discord@claude-plugins-official
```
Add this flag to your launch scripts alongside `--remote-control`.

## Combined launch (Remote Control + Discord notifications):
```bash
claude --remote-control "CCA Desktop" --channels plugin:discord@claude-plugins-official
```
