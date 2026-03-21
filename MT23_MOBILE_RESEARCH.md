# MT-23: Mobile Remote Control v2 — Research Summary
# Phase 1 Research — 2026-03-21 (S103)

---

## Official Claude Code Channels — What It Is

Claude Code Channels is an official Anthropic feature (research preview) that pushes events into a running Claude Code session via MCP servers. Telegram and Discord are the first two supported platforms.

**Key: This is NOT the same as Remote Control.** Remote Control lets you drive a session from claude.ai/mobile app. Channels let you push messages from Telegram/Discord into your session — bidirectional chat bridge.

---

## Requirements

- Claude Code v2.1.80 or later
- claude.ai login (Console/API key auth NOT supported)
- Bun installed (`bun --version` — plugins are Bun scripts, not Node/Deno)
- Pro/Max plan (Team/Enterprise need admin to enable)

---

## Telegram Setup (Step-by-Step)

1. Open BotFather in Telegram, `/newbot`, create bot, copy token
2. In Claude Code: `/plugin install telegram@claude-plugins-official`
   - If not found: `/plugin marketplace add anthropics/claude-plugins-official` first
3. `/telegram:configure <token>` — saves to `~/.claude/channels/telegram/.env`
4. Restart: `claude --channels plugin:telegram@claude-plugins-official`
5. Send message to bot in Telegram → bot replies with pairing code
6. In Claude Code: `/telegram:access pair <code>`
7. Lock down: `/telegram:access policy allowlist`

---

## Discord Setup (Step-by-Step)

1. Discord Developer Portal → New Application → create bot → copy token
2. Enable Message Content Intent in bot settings
3. OAuth2 → bot scope → permissions: View Channels, Send Messages, Read History, Attach Files, Add Reactions
4. In Claude Code: `/plugin install discord@claude-plugins-official`
5. `/discord:configure <token>` — saves to `~/.claude/channels/discord/.env`
6. Restart: `claude --channels plugin:discord@claude-plugins-official`
7. DM bot → pairing code → `/discord:access pair <code>`
8. `/discord:access policy allowlist`

---

## Security Model

- Sender allowlist: only paired IDs can push messages, everyone else silently dropped
- Pairing flow: bot sends code → user approves in Claude Code → added to allowlist
- `--channels` flag controls which servers are enabled per session
- Being in `.mcp.json` alone is NOT enough to receive messages

---

## Known Limitations (Research Preview)

1. **Context loss bug**: Reported by user — after long session, Claude reduces context and loses MCP tool definitions. Requires restart from computer.
2. **Permission pauses**: If Claude hits a permission prompt while away, session pauses until local approval. Use `--dangerously-skip-permissions` only in trusted environments.
3. **Plugin syntax may change**: Research preview, `--channels` flag and protocol contract may change.
4. **Allowlist-only plugins**: Only Anthropic-maintained plugins allowed during preview. Use `--dangerously-load-development-channels` for custom channels.
5. **No Signal support**: Community-requested but not available.
6. **Events only while session is open**: For always-on, run in persistent terminal or background process.

---

## Comparison: Channels vs Remote Control vs ntfy (Current)

| Feature | Channels (Telegram/Discord) | Remote Control | ntfy (Current CCA) |
|---------|---------------------------|----------------|-------------------|
| Direction | Bidirectional chat | You drive session | One-way push |
| Platform | Telegram, Discord | claude.ai, mobile app | Any ntfy client |
| Setup | Plugin install + pairing | Built-in | API topic config |
| Context | Shares running session | Shares running session | No session access |
| Reply | Claude replies in chat | You see in claude.ai | No reply path |
| Persistence | Session must be open | Session must be open | Fire-and-forget |
| Effort | Medium (bot setup) | Low (native) | Low (topic setup) |

---

## Recommendation for Matthew

**Telegram is the strongest candidate** for Matthew's use case:
- iPhone app experience: Telegram on iPhone is fast, native-feeling
- Hop on/hop off: Send message → Claude acts → reply appears in chat
- Memory: The session context persists (it's the same Claude Code session)
- Bidirectional: Ask questions, give commands, receive results
- Security: Allowlist ensures only Matthew can interact

**Migration path from ntfy:**
1. Install Telegram on iPhone (if not already)
2. Create bot via BotFather (5 min)
3. Install plugin + configure token (2 min)
4. Pair account (1 min)
5. Test: send message from phone → verify response
6. Once validated: update CCA launch scripts to include `--channels` flag
7. Gradually phase out ntfy mobile approver

**Risk mitigation:**
- Context loss bug: Test with long sessions before relying on it
- Permission pauses: Our hook-based safety approach prevents dangerous commands, so `--dangerously-skip-permissions` may not be needed for most mobile interactions
- Keep ntfy as fallback during transition period

---

## Next Steps (Phase 2)

1. Verify Claude Code version: `claude --version` (need v2.1.80+)
2. Verify Bun installed: `bun --version`
3. Write INSTALL_TELEGRAM_CHANNELS.md with copy-pasteable steps (ADHD-friendly)
4. Matthew manual step: create Telegram bot via BotFather
5. Test session with Telegram channel
6. Validate hop-on/hop-off UX (leave 30 min, return)
7. Update CCA launch scripts if validated

---

## Sources

- Official docs: https://code.claude.com/docs/en/channels
- Plugin source: https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/telegram
- Reddit discussion (364 upvotes): https://www.reddit.com/r/ClaudeAI/comments/1ryh3da/
