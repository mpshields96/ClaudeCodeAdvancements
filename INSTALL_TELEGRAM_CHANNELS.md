# Install Telegram Channels for Claude Code
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

### Step 3: Create Telegram Bot
1. Open Telegram on your iPhone
2. Search for @BotFather
3. Send: /newbot
4. Give it a name (e.g., "CCA Claude Bridge")
5. Give it a username (e.g., "cca_claude_bot")
6. COPY THE TOKEN it gives you (looks like: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11)

## Setup (in Claude Code)

### Step 4: Install plugin
```
/plugin marketplace add anthropics/claude-plugins-official
/plugin install telegram@claude-plugins-official
```

### Step 5: Configure token
```
/telegram:configure PASTE_YOUR_TOKEN_HERE
```

### Step 6: Restart Claude Code with channels
```bash
claude --channels plugin:telegram@claude-plugins-official
```

### Step 7: Pair your account
1. Open Telegram on iPhone
2. Find your bot and send any message
3. Bot replies with a pairing code
4. In Claude Code, run:
```
/telegram:access pair PASTE_CODE_HERE
```

### Step 8: Lock down (security)
```
/telegram:access policy allowlist
```

## Done! Test it.
Send a message to your bot from iPhone. Claude should respond.

## To use daily:
```bash
claude --channels plugin:telegram@claude-plugins-official
```
Add this flag to your launch scripts.
