# Install Claude Control — Step by Step

Claude Control gives you a visual dashboard showing all your running Claude Code sessions.
You can see what each chat is doing, switch between them, and manage them from one window.

---

## Steps

### 1. Open this URL in your browser

```
https://github.com/sverrirsig/claude-control/releases
```

### 2. Download the DMG file

- Click the `.dmg` file under the latest release (should be something like `Claude-Control-0.8.3.dmg`)
- It will download to your Downloads folder
- You should see a `.dmg` file in `~/Downloads/`

### 3. Open the DMG

- Double-click the downloaded `.dmg` file in Finder
- A window will pop up showing the Claude Control app icon and an Applications folder

### 4. Drag to Applications

- Drag the Claude Control icon to the Applications folder in that window
- Wait for the copy to finish

### 5. Open Claude Control

- Open Finder, go to Applications
- Double-click "Claude Control"
- If macOS says "can't be opened because Apple cannot check it for malicious software":
  - Click "Cancel"
  - Go to System Settings > Privacy & Security
  - Scroll down and click "Open Anyway" next to the Claude Control message
  - Click "Open" in the popup

### 6. Verify it works

- You should see a window showing your running Claude Code sessions
- If Claude Code is running, it should auto-detect the processes
- You should see session status (Working/Idle/Waiting)

---

## What it does for you

- Shows all running Claude Code sessions in one dashboard
- Auto-detects Claude processes (no config needed)
- Shows git branch, file changes, PR status per session
- Keyboard shortcuts to switch between sessions fast
- Push notifications when sessions need attention

## If something goes wrong

- It's stateless — quitting it can't break anything
- If it doesn't detect sessions, make sure Claude Code is running in Terminal
- Works with Terminal.app, iTerm2, Ghostty, kitty, WezTerm, Alacritty
