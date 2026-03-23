#!/bin/bash
# start_desktop_autoloop.sh — Desktop Auto-Loop for Claude.app
#
# Usage:
#   ./start_desktop_autoloop.sh              # Run the desktop auto-loop
#   ./start_desktop_autoloop.sh --dry-run    # Simulate without keystrokes
#   ./start_desktop_autoloop.sh --preflight  # Check readiness
#   ./start_desktop_autoloop.sh --status     # Show current state
#   ./start_desktop_autoloop.sh --help       # Show help
#
# What this does:
#   1. Reads SESSION_RESUME.md (written by /cca-wrap)
#   2. Activates Claude.app and starts a new conversation
#   3. Pastes the resume prompt and sends with Cmd+Return
#   4. Monitors SESSION_RESUME.md for changes (= session wrapped)
#   5. Loops back to step 1 with cooldown
#
# Matthew watches and interacts freely while it runs.
# Like OpenClaw's Mac Mini pattern but for CCA in Claude desktop app.
#
# Requirements:
#   - Claude.app installed and running
#   - Accessibility permissions for Terminal.app (System Events)
#   - SESSION_RESUME.md exists (written by previous /cca-wrap)
#
# Safety: Max 50 iterations, 15s cooldown, crash detection, audit logging.

set -euo pipefail

PROJECT_DIR="/Users/matthewshields/Projects/ClaudeCodeAdvancements"
cd "$PROJECT_DIR"

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

case "${1:-start}" in
    --preflight|preflight)
        echo "Running pre-flight checks..."
        python3 desktop_autoloop.py preflight
        ;;
    --status|status)
        python3 desktop_autoloop.py status
        ;;
    --dry-run|dry-run)
        echo "Starting desktop auto-loop (DRY RUN)..."
        echo ""
        shift
        python3 desktop_autoloop.py start --dry-run "$@"
        ;;
    --help|help|-h)
        echo "Desktop Auto-Loop for Claude.app (MT-22)"
        echo ""
        echo "Usage:"
        echo "  ./start_desktop_autoloop.sh              # Start the loop"
        echo "  ./start_desktop_autoloop.sh --dry-run    # Simulate"
        echo "  ./start_desktop_autoloop.sh --preflight  # Check readiness"
        echo "  ./start_desktop_autoloop.sh --status     # Show state"
        echo ""
        echo "Options (pass after command):"
        echo "  --max-iterations N   Limit iterations (default 50)"
        echo "  --model opus|sonnet  Force a specific model"
        echo "  --cooldown N         Seconds between sessions (default 15)"
        echo ""
        echo "How it works:"
        echo "  1. Reads SESSION_RESUME.md"
        echo "  2. Activates Claude.app, starts new conversation"
        echo "  3. Pastes resume prompt, sends with Cmd+Return"
        echo "  4. Watches for SESSION_RESUME.md change (= session done)"
        echo "  5. Repeats until max iterations or safety stop"
        echo ""
        echo "You can interact with Claude.app freely while it runs."
        echo "Ctrl+C to stop the loop."
        ;;
    start|*)
        # Preflight first
        echo "Running pre-flight checks..."
        if ! python3 desktop_autoloop.py preflight; then
            echo ""
            echo "Pre-flight FAILED. Fix issues above before starting."
            exit 1
        fi
        echo ""

        # Warn about Accessibility permissions
        echo "NOTE: Terminal.app needs Accessibility access to send keystrokes."
        echo "Grant in: System Settings > Privacy & Security > Accessibility"
        echo ""

        # Start the loop
        shift 2>/dev/null || true
        python3 desktop_autoloop.py start "$@"
        ;;
esac
