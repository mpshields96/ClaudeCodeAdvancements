#!/bin/bash
# launch_phase3.sh — Launch 2 CLI workers for Phase 3 hivemind (3-chat)
#
# Usage (from Desktop coordinator):
#   bash launch_phase3.sh
#   bash launch_phase3.sh "cli1 task" "cli2 task"
#
# Launches cli1 and cli2 in separate Terminal tabs. Optionally assigns
# initial tasks to each. Workers will check inbox for additional tasks.
#
# Prerequisites:
#   - Desktop coordinator already running (this chat)
#   - Neither cli1 nor cli2 already running (checked by chat_detector)
#
# Safety: Aborts if either worker is already running.

set -euo pipefail

CCA_DIR="/Users/matthewshields/Projects/ClaudeCodeAdvancements"
CLI1_TASK="${1:-}"
CLI2_TASK="${2:-}"

echo "=== Phase 3 Launch: Desktop + cli1 + cli2 ==="
echo ""

# Pre-flight: check neither worker is running
for WID in cli1 cli2; do
    CHECK_RESULT=$(python3 "$CCA_DIR/chat_detector.py" check "$WID" 2>&1)
    if echo "$CHECK_RESULT" | grep -q "^BLOCKED"; then
        echo "ABORT: $WID already running."
        echo "$CHECK_RESULT"
        echo "Kill the existing $WID process first."
        exit 1
    fi
    echo "$CHECK_RESULT" | grep "WARNING" || true
done

# Launch cli1
echo "Launching cli1..."
CCA_WORKER_ID=cli1 bash "$CCA_DIR/launch_worker.sh" "$CLI1_TASK"
echo ""

# Brief delay to avoid Terminal tab race
sleep 1

# Launch cli2
echo "Launching cli2..."
CCA_WORKER_ID=cli2 bash "$CCA_DIR/launch_worker.sh" "$CLI2_TASK"
echo ""

echo "=== Phase 3 Active ==="
echo "  Desktop: this chat (coordinator)"
echo "  cli1: Terminal tab 1"
echo "  cli2: Terminal tab 2"
echo ""
echo "Assign tasks:  python3 cca_comm.py assign cli1 'task'"
echo "               python3 cca_comm.py assign cli2 'task'"
echo "Check status:  python3 cca_comm.py status"
echo "Check inbox:   python3 cca_comm.py inbox"
