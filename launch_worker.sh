#!/bin/bash
# launch_worker.sh — Start a CCA worker in a new Terminal tab
#
# Usage (from Desktop coordinator chat):
#   bash launch_worker.sh "single clear task description"
#
# IMPORTANT: One task per message. Do NOT combine multiple tasks into the
# launch task string (e.g., "TASK 1: ... TASK 2: ..."). Workers tend to
# pick the easiest task and wrap early. Instead:
#   1. launch_worker.sh "primary task"     ← worker reads this first
#   2. python3 cca_comm.py task cli1 "second task"  ← queued separately
# The worker will check inbox after completing task 1 and find task 2.
#
# What it does:
#   1. Pre-launch duplicate check (abort if same worker already running)
#   2. Assigns a task to cli1 via cca_comm.py (if task_description provided)
#   3. Opens a new Terminal.app tab
#   4. Sets CCA_CHAT_ID=cli1 in that tab
#   5. Starts claude with /cca-worker in the CCA project directory
#
# Multi-task: Worker loops on inbox after each task. Front-load 2-3 tasks
# via cca_comm.py after launch for maximum worker utilization.
#
# The worker will:
#   - Run /cca-init (detects CCA_CHAT_ID=cli1, shows worker role)
#   - Run /cca-auto-worker (checks inbox, claims scope, executes, reports back)
#
# Safety: Only operates within ClaudeCodeAdvancements. No external access.

set -euo pipefail

CCA_DIR="/Users/matthewshields/Projects/ClaudeCodeAdvancements"
WORKER_ID="${CCA_WORKER_ID:-cli1}"
TASK_DESC="${1:-}"

# Step 0a: Rate limit awareness — warn during peak hours
if python3 "$CCA_DIR/peak_hours.py" --check 2>/dev/null; then
    : # off-peak, proceed normally
else
    echo "WARNING: Peak hours detected (8AM-2PM ET weekday). Standard rate limits apply."
    echo "Launching worker anyway — but consider pausing during heavy load."
fi

# Step 0b: Pre-launch duplicate check — abort if same worker already running
CHECK_RESULT=$(python3 "$CCA_DIR/chat_detector.py" check "$WORKER_ID" 2>&1)
if echo "$CHECK_RESULT" | grep -q "^BLOCKED"; then
    echo "ABORT: $CHECK_RESULT"
    echo "Kill the existing $WORKER_ID process first, or use a different worker ID."
    exit 1
fi
# Show warnings (e.g. stale processes) but continue
echo "$CHECK_RESULT" | grep "WARNING" || true

# Step 1: If a task description was provided, assign it via queue
if [ -n "$TASK_DESC" ]; then
    echo "Assigning task to $WORKER_ID: $TASK_DESC"
    CCA_CHAT_ID=desktop python3 "$CCA_DIR/cca_comm.py" task "$WORKER_ID" "$TASK_DESC"
fi

# Step 2: Open a new Terminal tab and start the worker
# Uses AppleScript to open a tab in Terminal.app with the right env
# CRITICAL: unset ANTHROPIC_API_KEY so claude uses Max subscription (OAuth),
# not API credits. S105 terminal chats burned $5 API credits because of this.
osascript <<APPLESCRIPT
tell application "Terminal"
    activate
    -- Open a new tab in the frontmost window
    tell application "System Events"
        keystroke "t" using command down
    end tell
    delay 0.5
    -- Run the worker setup command in the new tab
    do script "unset ANTHROPIC_API_KEY && export CCA_CHAT_ID=$WORKER_ID && cd $CCA_DIR && echo '=== CCA Worker ($WORKER_ID) ===' && claude /cca-worker" in front window
end tell
APPLESCRIPT

echo ""
echo "Worker launched in new Terminal tab."
echo "  Worker ID: $WORKER_ID"
echo "  Directory: $CCA_DIR"
if [ -n "$TASK_DESC" ]; then
    echo "  Task: $TASK_DESC"
fi
echo ""
echo "Monitor from desktop: python3 cca_comm.py status"
echo "Check worker output:  python3 cca_comm.py inbox"
