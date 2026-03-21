#!/bin/bash
# launch_kalshi.sh — Start a Kalshi bot chat in a new Terminal tab
#
# Usage (from CCA Desktop coordinator):
#   bash launch_kalshi.sh [main|research]
#
# What it does:
#   1. Opens a new Terminal.app tab
#   2. cd to polymarket-bot project
#   3. Starts claude with /kalshi-main or /kalshi-research
#
# The Kalshi chat will:
#   - Read polymarket-bot/CLAUDE.md (its own rules)
#   - Run /polybot-init (session startup)
#   - Run /polybot-auto or /polybot-autoresearch
#
# Communication with CCA:
#   - CCA writes research/task briefs to CCA_TO_POLYBOT.md
#   - Kalshi chat reads CCA_TO_POLYBOT.md at startup
#   - Kalshi writes back to POLYBOT_TO_CCA.md (return channel)
#
# Safety: This script only opens a terminal. It does NOT write to
# or modify any files in the polymarket-bot project.

set -euo pipefail

KALSHI_DIR="/Users/matthewshields/Projects/polymarket-bot"
MODE="${1:-main}"

if [ "$MODE" = "main" ]; then
    COMMAND="/kalshi-main"
elif [ "$MODE" = "research" ]; then
    COMMAND="/kalshi-research"
else
    echo "Usage: bash launch_kalshi.sh [main|research]"
    echo "  main     — monitoring + autonomous trading (default)"
    echo "  research — research mode"
    exit 1
fi

# Verify the project exists
if [ ! -d "$KALSHI_DIR" ]; then
    echo "ERROR: $KALSHI_DIR does not exist"
    exit 1
fi

# Open a new Terminal tab and start the Kalshi chat
osascript <<APPLESCRIPT
tell application "Terminal"
    activate
    tell application "System Events"
        keystroke "t" using command down
    end tell
    delay 0.5
    do script "cd $KALSHI_DIR && echo '=== Kalshi Bot ($MODE) ===' && claude $COMMAND" in front window
end tell
APPLESCRIPT

echo ""
echo "Kalshi chat launched in new Terminal tab."
echo "  Mode: $MODE"
echo "  Directory: $KALSHI_DIR"
echo "  Command: claude $COMMAND"
echo ""
echo "Communication:"
echo "  CCA -> Kalshi: CCA_TO_POLYBOT.md (in CCA project)"
echo "  Kalshi -> CCA: POLYBOT_TO_CCA.md (in CCA project)"
