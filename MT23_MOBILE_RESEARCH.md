# MT-23: Mobile Remote Control v2 — Research Summary
# Phase 2 Research — 2026-03-21 (S104)
# DIRECTION CHANGE (S103 Matthew explicit): Remote Control = PRIMARY, Discord = SECONDARY

---

## Strategy Summary

| Path | Role | Setup | Why |
|------|------|-------|-----|
| **Remote Control** | PRIMARY | Zero (built-in) | No bot, no token, no pairing. Matthew prefers zero-setup. |
| **Discord Channels** | SECONDARY / fallback | Medium (bot + plugin) | Push notifications when RC unavailable |
| ~~Telegram~~ | ~~Deprecated~~ | ~~Medium~~ | ~~Matthew chose Remote Control over Telegram (S103)~~ |
| ntfy | CURRENT (keep as bridge) | Low | One-way push, already wired into CCA |

---

## Remote Control — What It Is

Remote Control is an official Anthropic feature (released Feb 2026) that connects claude.ai/code or the Claude iOS/Android app to a Claude Code session running on your local machine. The session runs locally — the web/mobile interface is just a window into it.

**Zero setup**: no bot creation, no API token, no plugin installation, no pairing flow. Just run `claude --remote-control` and scan the QR code.

---

## Requirements

- Claude Code v2.1.51 or later (current: check `claude --version`)
- claude.ai login (API key auth NOT supported)
- Pro or Max plan (Team/Enterprise need admin toggle)
- Claude iOS app installed on iPhone

---

## How to Start Remote Control

### Option A: Server Mode (dedicated process, recommended for CCA)

```bash
claude remote-control --name "CCA Desktop"
```

Flags:
| Flag | Description |
|------|-------------|
| `--name "CCA Desktop"` | Custom session title visible in claude.ai/code session list |
| `--spawn worktree` | Each on-demand session gets its own git worktree (prevents file conflicts) |
| `--spawn same-dir` | All sessions share CWD (default) |
| `--capacity <N>` | Max concurrent sessions (default 32) |
| `--verbose` | Detailed connection logs |
| `--sandbox` / `--no-sandbox` | Filesystem/network isolation |

### Option B: Interactive + Remote Control (use existing session)

```bash
claude --remote-control "CCA Desktop"
# or shorthand:
claude --rc "CCA Desktop"
```

### Option C: Enable from Inside a Running Session

```
/remote-control CCA Desktop
# or shorthand:
/rc CCA Desktop
```

### Option D: Enable for ALL Sessions Automatically

Run `/config` inside Claude Code → set "Enable Remote Control for all sessions" to `true`.
Every `claude` launch then auto-registers a remote session.

---

## Connecting from iPhone

1. **QR Code**: Displayed in terminal. Scan with Claude iOS app.
2. **Session URL**: Copy from terminal, open in any browser → goes to claude.ai/code.
3. **Session List**: Open Claude app → find session by name (shows computer icon + green dot when online).
4. **Download app**: If not installed, run `/mobile` in Claude Code for download QR code.

---

## What Works Well (Strengths)

1. **Zero setup**: No bot, no token, no plugin, no pairing. Just `--rc` and scan.
2. **Full local environment**: Filesystem, MCP servers, tools, project config all available.
3. **Cross-device sync**: Terminal, browser, phone — messages sync in real-time.
4. **Auto-reconnect**: Laptop sleep or network drops → reconnects automatically when back.
5. **Server mode**: Run `claude remote-control` → multiple concurrent sessions via `--spawn`.
6. **Session naming**: Custom names for easy identification in session list.

---

## Known Gaps and Limitations (Critical for Hop-On/Hop-Off)

### GAP 1: Session Reconnection Broken (CRITICAL)
- **GitHub Issue**: #28402 (OPEN, 17+ confirmations, 8 duplicate issues filed)
- **Problem**: After navigating away from session (swiping, closing app, pressing back), the session disappears from session list. No way to reconnect.
- **Impact**: Defeats the entire hop-on/hop-off use case. You must keep the app open without navigation.
- **Related issues**: #28532 (frequent disconnections), #28571 (resync fails after drop), #29313 (sessions go stale), #29748 (sessions don't survive reboots), #30691 (sessions don't appear until URL opened manually), #31102 (add reconnect option)
- **No official fix or workaround from Anthropic yet.**
- **CCA Workaround**: Save session URL to clipboard/file. Bookmark it. Re-open URL directly rather than searching session list.

### GAP 2: Terminal Must Stay Open
- If you close the terminal or stop `claude`, the session ends permanently.
- **CCA Workaround**: Run in tmux/screen session so Terminal.app can close without killing the process. Our `dev-start` tmux workspace already does this.

### GAP 3: 10-Minute Network Timeout
- If machine is awake but can't reach network for ~10 min, session exits.
- **CCA Workaround**: Monitor network connectivity, auto-restart RC on timeout.

### GAP 4: Single-User Only
- Cannot share session with another person. No pair programming via RC.
- Not a blocker for Matthew's solo use case.

### GAP 5: Permission Prompts Pause Session
- If Claude hits a permission prompt while Matthew is on phone, session pauses.
- **CCA Workaround**: Our hook-based safety + allowlists prevent most dangerous operations. Consider scoped `--allowedTools` for phone sessions.

### GAP 6: No Push Notifications
- RC doesn't push notifications when Claude finishes a task or needs input.
- **CCA Workaround**: This is where Discord Channels becomes the SECONDARY path — push notifications for "task done" or "need approval" events.

---

## CCA Enhancement Opportunities (What We Can Build)

### Enhancement 1: Auto-RC in Launch Scripts
Update `launch_worker.sh` and session start to always include `--remote-control` flag.
```bash
# In launch scripts:
claude --remote-control "CCA Desktop" /cca-desktop
```

### Enhancement 2: RC Session URL Persistence
Save the session URL to a known file on start. If Matthew needs to reconnect from phone:
```bash
# Auto-save URL on RC start (hook or wrapper)
echo "$RC_URL" > ~/.claude-rc-session-url
# Phone can bookmark this location or use a Shortcut to open it
```

### Enhancement 3: tmux Integration (Keep Sessions Alive)
Ensure all CCA sessions run inside tmux so Terminal.app closure doesn't kill them.
Already partially solved by `dev-start` workspace.

### Enhancement 4: Discord as Notification Channel
Set up Discord Channels as a notification-only secondary:
- Push "task complete" notifications
- Push "permission needed" alerts
- Push "session disconnected" warnings
- Matthew can respond via Discord if RC is down

### Enhancement 5: Network Health Monitor
Detect network drops > 5 min, auto-restart RC before the 10-min timeout kills it.

### Enhancement 6: Session Naming Convention
Auto-name sessions with project + role:
- "CCA Desktop S104"
- "CCA Worker cli1"
- "Kalshi Main"

---

## Comparison: Remote Control vs Channels vs ntfy

| Feature | Remote Control (PRIMARY) | Discord Channels (SECONDARY) | ntfy (CURRENT) |
|---------|------------------------|---------------------------|----------------|
| Direction | Bidirectional — you drive session | Bidirectional — push + reply | One-way push |
| Platform | claude.ai/code + Claude iOS app | Discord app | Any ntfy client |
| Setup | Zero (built-in) | Medium (bot + plugin + pairing) | Low (topic config) |
| Context | Full session access | Shares running session | No session access |
| Persistence | Session must be open | Session must be open | Fire-and-forget |
| Notifications | None (GAP 6) | Push notifications | Push notifications |
| Reconnection | BROKEN (GAP 1) | Stable (Discord handles) | N/A |
| Effort | Low | Medium | Low |

**Optimal combo for Matthew**: Remote Control for active driving + Discord for notifications/fallback + ntfy kept as bridge during transition.

---

## Recommendation for Matthew

**Remote Control is the right PRIMARY choice** because:
1. Zero-setup aligns with Matthew's preference (no bot, no token, no pairing)
2. Full session access from iPhone (not just notifications)
3. Built-in to Claude Code — no external dependencies
4. Server mode supports multiple concurrent sessions

**But GAP 1 (reconnection) must be worked around** for reliable hop-on/hop-off:
- Save session URL to a persistent location (clipboard, file, bookmark)
- Use tmux to prevent terminal closure from killing sessions
- Set up Discord Channels as notification fallback

---

## Implementation Plan (Phase 3)

### Step 1: Verify Prerequisites
```bash
claude --version    # Need v2.1.51+
```

### Step 2: Test Basic RC Flow
```bash
claude --remote-control "CCA Test"
# Scan QR with iPhone
# Send a test message from phone
# Verify response appears
```

### Step 3: Test Hop-On/Hop-Off
1. Start RC session
2. Save session URL
3. Navigate away from Claude app
4. Wait 5 minutes
5. Re-open session URL directly (not via session list)
6. Verify session is still alive and responsive

### Step 4: Wire into CCA Launch Scripts
- Update `launch_worker.sh` to include `--rc`
- Update `/cca-desktop` to auto-enable RC
- Save session URLs to `~/.claude-rc-sessions/`

### Step 5: Set Up Discord as Secondary (Optional)
- Create Discord bot for CCA notifications
- Install Discord channel plugin
- Configure for notification-only use

### Step 6: Validate Full Workflow
- Start CCA session at desk with RC
- Walk away with iPhone
- Check status from phone
- Approve/deny operations
- Return to desk, continue in terminal

---

## Sources

- Official docs: https://code.claude.com/docs/en/remote-control
- GitHub issue #28402 (reconnection): https://github.com/anthropics/claude-code/issues/28402
- VentureBeat coverage: https://venturebeat.com/orchestration/anthropic-just-released-a-mobile-version-of-claude-code-called-remote
- Simon Willison analysis: https://simonwillison.net/2026/Feb/25/claude-code-remote-control/
- Claude Code Channels docs: https://code.claude.com/docs/en/channels
- Product Hunt: https://www.producthunt.com/products/claude-code-remote-access
