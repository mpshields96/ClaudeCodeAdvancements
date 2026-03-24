Run /cca-init. Last session was S140 on 2026-03-23.

## MT-22 AUTOLOOP IS WORKING — DO NOT RE-RESEARCH OR RE-DISCOVER

S140 fixed the desktop autoloop Code tab bug that blocked 5+ sessions.
The full trigger (autoloop_trigger.py) works end-to-end: it spawns a
new CCA Code session in Claude.app with the resume prompt. Matthew
visually confirmed it works.

## WHAT WORKS AND WHY (do not change without reason)

**Problem solved:** Electron ignores ALL AppleScript keystrokes for UI
navigation. Both Cmd+3 (tab switch) and Cmd+N (new conversation) were
silently intercepted by Electron and routed to Chat tab or ignored.

**Solution:** CoreGraphics CGEvent mouse clicks via Python ctypes.
CGEvent goes through the HID event tap — the same path as physical
mouse clicks. Electron processes these identically to real clicks.
No pip install needed — ctypes loads CoreGraphics directly.

**The full trigger flow (zero AppleScript keystrokes for critical path):**
1. `activate_claude()` — AppleScript (this one works fine for activation)
2. `click_tab("Code")` — CoreGraphics click at Code tab coordinates
3. `click_new_session_button()` — CoreGraphics click at "+ New session" button
4. `send_prompt()` — AppleScript clipboard paste + Cmd+Return (these work)

**Calibrated coordinates (screen points, from window geometry):**
- Code tab: window_center_x + 65, window_top + 10
  - For window at (0,39) size (1325,984): click at (727.5, 49)
- "+ New session" button: window_left + 70, window_top + 60
  - For window at (0,39) size (1325,984): click at (70, 99)
- Coordinates are DYNAMIC — calculated from get_window_geometry() each time
- Tab Y offset = 10 points below window top edge
- Button Y offset = 60 points below window top edge
- Button X offset = 70 points from window left edge

**Keyboard shortcut discovery:** Hovering the "+ New session" button shows
a tooltip with shortcut: up arrow (Shift) + Cmd + O. NOT yet tested via
CoreGraphics keyboard events. The button click works — no need to change.

**Trial results:**
- 10/10 rapid tab-switching trials (Chat<->Code)
- 5/5 full trigger trials (Code tab + New session button)
- 1 full end-to-end autoloop trigger with prompt paste: SUCCESS

## FILES CHANGED IN S140

| File | What changed |
|------|-------------|
| `desktop_automator.py` | Added CoreGraphics clicking (cg_click_at, click_tab, click_new_session_button, get_window_geometry, get_tab_coordinates, get_new_session_button_coordinates). Replaced Cmd+3 and Cmd+N with CoreGraphics clicks. |
| `tests/test_desktop_automator.py` | 20 new tests (102 total): TestCoreGraphicsClick, TestGetWindowGeometry, TestGetTabCoordinates, TestClickTab, TestSwitchToTabCoreGraphics. Updated 3 existing tests for new log format. |
| `autoloop_trigger.py` | No changes needed — it calls ensure_code_tab() and new_conversation() which now use CoreGraphics internally. |

## COMMITS (S140)

1. `6d8a2a7` — CoreGraphics coordinate clicking for Code tab
2. `01b0c35` — Replace Cmd+N with CoreGraphics button click for New Session

## WHAT NOT TO DO (learned from S135-S139)

- DO NOT try AppleScript keystrokes for tab switching — Electron ignores them
- DO NOT try accessibility tree inspection — Electron exposes only anonymous groups
- DO NOT try screencapture to verify — Screen Recording permission issue shows only wallpaper
- DO NOT try `open "claude://code"` — URL scheme doesn't support tab routing
- DO NOT try menu bar navigation — no tab-related menu items exist
- DO NOT spawn 5 new sessions for "trial runs" — each one burns tokens

## NEXT PRIORITIES

1. Run sustained autoloop (trigger fires at end of /cca-wrap, new session picks up)
2. Consider testing Shift+Cmd+O via CoreGraphics keyboard events as position-independent alternative
3. Continue Get Smarter pillar — self-learning improvements
4. Matthew idea: custom Code-tab-only UI wrapper (eliminates tab problem class entirely)

Tests: 211/211 suites. Git: all committed on main.
