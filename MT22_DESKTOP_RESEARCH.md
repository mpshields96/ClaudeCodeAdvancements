# MT-22 Desktop Electron App Automation — Research (S131)

## Key Findings

**App**: `/Applications/Claude.app` — Electron-based (confirmed via Info.plist: `NSPrincipalClass=AtomicApplication`)
**Bundle ID**: `com.anthropic.claudefordesktop`
**URL Scheme**: `claude://` registered but undocumented
**Architecture**: Universal binary (x86_64 + arm64)

## Viable Automation Approaches (ranked)

### Tier 1: AppleScript Keystroke Emulation (RECOMMENDED for MVP)

```bash
# Activate Claude
osascript -e 'tell application "Claude" to activate'

# Send keystroke
osascript -e 'tell application "System Events" to keystroke "prompt text"'
osascript -e 'tell application "System Events" to keystroke return using command down'
```

**Pros**: Works immediately, Matthew can watch + interact, same pattern as Terminal.app autoloop
**Cons**: Cannot detect response state (timing-based workaround), cannot read response text

### Tier 2: URL Scheme (`claude://`) — EXPERIMENTAL

Unknown parameters. Registered in Info.plist but no documentation found. Could be cleaner than keystrokes if supported.

### Tier 3: PyObjC Accessibility API — ADVANCED

Direct API for UI control. More reliable than keystrokes but requires pyobjc installation. Not recommended for MVP.

### NOT VIABLE

- CLI pipe / stdin: Desktop app doesn't accept stdin
- IPC / socket: No evidence of external communication
- Electron DevTools: Requires special launch flags

## What Can't Be Done

1. **No state detection**: Can't tell when Claude finished responding — use conservative timeouts
2. **No response reading**: Can't extract Claude's actual response — Matthew monitors visually
3. **No session isolation**: Keystrokes go to active window — must activate + verify before sending

## Implementation Plan (5 phases)

| Phase | Sessions | What |
|-------|----------|------|
| 1. Research validation | 1 | Test AppleScript with live Claude app, confirm timing, explore URL scheme |
| 2. Prototype | 1-2 | Adapt start_autoloop.sh for Claude.app, implement activate + send + close |
| 3. Validation | 1-2 | Run prototype on real task, collect timing data |
| 4. Hardening | 1 | Edge cases, logging, tests |
| 5. Supervised trial | 3 runs | 3/3 clean 1-hour runs to approve for unsupervised use |

## New Functions Needed

```python
def activate_claude() -> bool           # Bring Claude app to foreground
def send_prompt_to_claude(prompt, timeout=60) -> bool  # Keystroke inject
def detect_response_ready(timeout=60) -> bool          # Heuristic polling
def close_claude_window() -> bool       # Close active window
```

## Existing Infrastructure to Reuse

- `start_autoloop.sh`: Terminal.app window management via AppleScript (template)
- `AUTOLOOP_SETUP.md`: Accessibility permission grant process
- `session_notifier.py`: ntfy.sh push notifications
- `crash_recovery.py`: Hung process detection + restart
- `cca_autoloop.py`: Session loop logic, audit trail, safety limits

## Safety Requirements

- Check process name before sending keystrokes (avoid non-Claude windows)
- Verify window title contains "Claude" before injection
- Max 1 Claude desktop window per automation loop
- Log every action with timestamp
- Visual/audio warning before first keystroke (Matthew awareness)

## Key Decision: Keystroke vs URL Scheme

If `claude://` scheme supports prompt injection (unlikely but worth checking):
- Use scheme for clean, atomic prompt delivery
- Skip keystroke timing issues entirely

If not (most likely):
- AppleScript keystroke with 0.5s activate delay + Cmd+Return to send
- Conservative response timeout (120s default, configurable)
