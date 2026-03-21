#!/bin/bash
# launch_kalshi.sh — Start a Kalshi bot chat in a new Terminal window
#
# Usage:
#   bash launch_kalshi.sh [main|research]
#   bash launch_kalshi.sh both          # Launch main AND research in two windows
#
# What it does:
#   1. Opens a new Terminal.app window (reliable — no tab AppleScript fragility)
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

# Handle "both" mode — launch main and research in sequence
if [ "$MODE" = "both" ]; then
    echo "Launching both Kalshi chats..."
    bash "$0" main
    sleep 2
    bash "$0" research
    exit 0
fi

if [ "$MODE" = "main" ]; then
    COMMAND="/kalshi-main"
elif [ "$MODE" = "research" ]; then
    COMMAND="/kalshi-research"
else
    echo "Usage: bash launch_kalshi.sh [main|research|both]"
    echo "  main     — monitoring + autonomous trading (default)"
    echo "  research — research mode"
    echo "  both     — launch main AND research in separate windows"
    exit 1
fi

# Rate limit awareness — warn during peak hours
if python3 "/Users/matthewshields/Projects/ClaudeCodeAdvancements/peak_hours.py" --check 2>/dev/null; then
    : # off-peak, proceed normally
else
    echo "WARNING: Peak hours detected (8AM-2PM ET weekday). Standard rate limits apply."
    echo "Launching Kalshi chat anyway — but monitor for rate limit hits."
fi

# Verify the project exists
if [ ! -d "$KALSHI_DIR" ]; then
    echo "ERROR: $KALSHI_DIR does not exist"
    exit 1
fi

# Launch in a new Terminal window using 'open' + temp script
# This is more reliable than AppleScript keystroke-based tab creation,
# which fails with -1719 "Invalid index" when no window exists.
TMPSCRIPT=$(mktemp /tmp/kalshi_launch_XXXXXX.sh)
cat > "$TMPSCRIPT" <<INNERSCRIPT
#!/bin/bash
unset ANTHROPIC_API_KEY
cd "$KALSHI_DIR"
echo "=== Kalshi Bot ($MODE) ==="
echo "Auth: Max subscription (ANTHROPIC_API_KEY unset)"
echo ""
rm -f "$TMPSCRIPT"
exec claude $COMMAND
INNERSCRIPT
chmod +x "$TMPSCRIPT"

open -a Terminal "$TMPSCRIPT"

echo ""
echo "Kalshi chat launched in new Terminal window."
echo "  Mode: $MODE"
echo "  Directory: $KALSHI_DIR"
echo "  Command: claude $COMMAND"
echo ""
echo "Communication:"
echo "  CCA -> Kalshi: CCA_TO_POLYBOT.md (in CCA project)"
echo "  Kalshi -> CCA: POLYBOT_TO_CCA.md (in CCA project)"
