# CCA Auto-Loop Setup Guide

One-time setup to run `./start_autoloop.sh --desktop` hands-free.

---

## Step 1: Grant Accessibility Permissions

The autoloop uses AppleScript (System Events) to close Terminal windows and
handle "terminate running processes?" dialogs. macOS requires explicit
Accessibility permission for this.

**What gets modified:** ONLY the Accessibility permission list in System Settings.
No files, no system configs, no code, no settings.local.json. Fully reversible
(uncheck the box to revoke).

### Instructions (macOS 15 Sequoia)

1. Open **System Settings** (Apple menu > System Settings)
2. Click **Privacy & Security** in the left sidebar
3. Scroll down and click **Accessibility**
4. Click the **+** button (you may need to authenticate with Touch ID / password)
5. Navigate to: **Applications > Utilities > Terminal.app**
6. Click **Open**
7. Verify Terminal.app appears in the list with its toggle **ON**

If you use iTerm2 instead, add iTerm.app the same way.

### Verify it worked

Open Terminal.app and run:

```bash
osascript -e 'tell application "System Events" to get name of first process'
```

Expected output: `loginwindow` (or any process name).
If you see "not allowed assistive access": permission wasn't granted yet.

---

## Step 2: Run Pre-Flight Check

```bash
cd ~/Projects/ClaudeCodeAdvancements
python3 cca_autoloop.py preflight --desktop
```

This checks everything: claude binary, no duplicate sessions, SESSION_RESUME.md,
start_autoloop.sh executable, Terminal.app running, Accessibility permissions,
orphaned temp files. Fix any FAIL items before launching.

---

## Step 3: Run the Auto-Loop

```bash
# Close ALL CCA Claude Code desktop chats first
cd ~/Projects/ClaudeCodeAdvancements
./start_autoloop.sh --desktop
```

### What happens

1. Pre-flight checks run (claude binary, no duplicate sessions, temp cleanup)
2. Terminal.app window opens: "CCA-AutoLoop-Iter-1"
3. Claude runs /cca-init + /cca-auto autonomously
4. Session works, wraps, exits
5. Controller closes the window automatically
6. 15s cooldown
7. Next window opens: "CCA-AutoLoop-Iter-2"
8. Repeat until Ctrl-C or 50 iterations

### Model strategy options

```bash
./start_autoloop.sh --desktop                                # round-robin Sonnet/Opus
MODEL_STRATEGY=opus-primary ./start_autoloop.sh --desktop     # Opus only
MODEL_STRATEGY=sonnet-primary ./start_autoloop.sh --desktop   # Sonnet only (cheaper)
```

### Check status

```bash
python3 cca_autoloop.py status          # rich status with audit history
./start_autoloop.sh --status            # quick state dump
```

---

## What if Accessibility is NOT granted?

The autoloop still works but with degraded window management:
- Windows may not close automatically (you close them manually)
- "Terminate?" dialogs won't be auto-dismissed
- The loop itself continues — sessions still spawn and run

The pre-flight check warns but does not block.

---

## Removing Accessibility permissions later

System Settings > Privacy & Security > Accessibility > uncheck Terminal.app.
That's it. Nothing else changes.
