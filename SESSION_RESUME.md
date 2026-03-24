Run /cca-init. Last session was S139 on 2026-03-23.

CRITICAL BUG STILL OPEN: Autoloop trigger lands on CHAT tab, not Code tab.

What S139 did:
- Confirmed Electron accessibility tree is completely empty (just anonymous groups + window buttons)
- Discovered Cmd+1/2/3 keyboard shortcuts switch tabs (Matthew confirmed Cmd+3 goes to Code)
- Replaced broken accessibility tree approach with Cmd+3 keystroke in ensure_code_tab()
- Added switch_to_tab() method with Cmd+1/2/3 mapping
- 3 commits, all tests pass (211 suites, 8544 total)

What FAILED in live testing:
- Test 1: Cmd+3 before Cmd+N — still landed on Chat tab
- Test 2: Double Cmd+3 (before AND after Cmd+N) + 500ms settling delay — STILL Chat tab
- Cmd+3 works when Matthew manually presses it, but NOT when sent via AppleScript automation

ROOT CAUSE HYPOTHESIS: AppleScript keystroke "3" using command down may be intercepted
differently when sent programmatically vs typed physically. Possible issues:
1. The keystroke is going to the WRONG window/process (this Claude Code session, not the app UI)
2. Electron ignores programmatic keystrokes for tab switching (security feature?)
3. The Cmd+3 shortcut only works in certain focus contexts (e.g., when the input field isn't focused)

NEXT SESSION MUST TRY:
1. Use AppleScript menu click: View menu or Window menu might have tab items (checked S139 — none found)
2. Use `open "claude://code"` URL scheme (claude:// scheme exists, try code/chat/cowork paths)
3. Try clicking at coordinates using CoreGraphics CGEventCreateMouseEvent (code already written at /tmp/test_click_code_tab.py pattern — calculate from window bounds)
4. Try sending keystroke to the APPLICATION not System Events: `tell application "Claude" to ...`
5. Check if Cmd+3 works via `osascript -e 'tell application "System Events" to keystroke "3" using command down'` from Terminal when Claude.app is focused manually

Files: desktop_automator.py (switch_to_tab, ensure_code_tab, new_conversation all updated),
tests/test_desktop_automator.py (20 tests rewritten), CLAUDE.md (docs updated).
Tests: 211/211 suites, 8544 total. Git: all committed on main.
