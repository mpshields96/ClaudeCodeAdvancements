#!/bin/bash
# start_autoloop.sh — One-command CCA auto-loop launcher
#
# Usage:
#   ./start_autoloop.sh              # Start in tmux (default)
#   ./start_autoloop.sh --foreground # Start in current terminal
#   ./start_autoloop.sh --dry-run    # Simulate without spawning claude
#   ./start_autoloop.sh --status     # Show current loop status
#
# What this does:
#   1. Creates/attaches to tmux session "cca-workspace"
#   2. Launches cca_autoloop.py which reads SESSION_RESUME.md
#   3. Each iteration: spawns claude with resume prompt -> /cca-init -> /cca-auto
#   4. When session ends, reads new SESSION_RESUME.md, spawns next session
#   5. Stops after 50 iterations, 3 consecutive crashes, or manual Ctrl-C
#
# Safety: Max 50 iterations, 15s cooldown between sessions, crash detection.
# To stop: Ctrl-C in the tmux window, or `python3 cca_autoloop.py stop`

set -e

PROJECT_DIR="/Users/matthewshields/Projects/ClaudeCodeAdvancements"
AUTOLOOP="$PROJECT_DIR/cca_autoloop.py"

# Ensure we don't use API key (Max subscription auth)
unset ANTHROPIC_API_KEY

cd "$PROJECT_DIR"

# Parse arguments
MODE="tmux"
EXTRA_ARGS=""
for arg in "$@"; do
    case "$arg" in
        --foreground) MODE="foreground" ;;
        --dry-run)    EXTRA_ARGS="$EXTRA_ARGS --dry-run" ;;
        --status)     python3 "$AUTOLOOP" status; exit 0 ;;
        --help|-h)
            echo "Usage: ./start_autoloop.sh [--foreground] [--dry-run] [--status]"
            echo ""
            echo "  --foreground  Run in current terminal (default: tmux)"
            echo "  --dry-run     Simulate without spawning claude"
            echo "  --status      Show current loop status"
            exit 0
            ;;
    esac
done

if [ "$MODE" = "foreground" ]; then
    echo "Starting CCA auto-loop in foreground..."
    python3 "$AUTOLOOP" start $EXTRA_ARGS
else
    # Launch in tmux
    SESSION="cca-workspace"
    WINDOW="cca-autoloop"

    # Create tmux session if it doesn't exist
    if ! tmux has-session -t "$SESSION" 2>/dev/null; then
        tmux new-session -d -s "$SESSION" -n daemon
        echo "Created tmux session: $SESSION"
    fi

    # Check if window already exists
    if tmux list-windows -t "$SESSION" -F '#{window_name}' 2>/dev/null | grep -q "^${WINDOW}$"; then
        echo "Auto-loop window already exists. Attach with: tmux attach -t $SESSION:$WINDOW"
        exit 1
    fi

    # Create new window with the auto-loop
    tmux new-window -t "$SESSION" -n "$WINDOW" \
        "unset ANTHROPIC_API_KEY && cd '$PROJECT_DIR' && python3 '$AUTOLOOP' start $EXTRA_ARGS; echo 'Auto-loop exited. Press Enter to close.'; read"

    echo "CCA auto-loop started in tmux."
    echo "  Attach: tmux attach -t $SESSION:$WINDOW"
    echo "  Status: ./start_autoloop.sh --status"
    echo "  Stop:   Ctrl-C in the tmux window"
fi
