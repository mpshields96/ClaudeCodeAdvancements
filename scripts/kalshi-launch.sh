#!/bin/zsh
# kalshi-launch — Open two Terminal.app windows for Kalshi bot chats
#
# Usage: kalshi-launch
#
# Opens two separate Terminal.app windows:
#   Window 1: Main chat (live monitoring + betting)
#   Window 2: Research chat (finding edges + bugs)
#
# Each window launches Claude Code with --dangerously-skip-permissions,
# runs /polybot-init, then the appropriate auto command with instructions.
#
# After launch, you take over. The script exits.
#
# Install:
#   cp scripts/kalshi-launch.sh ~/.local/bin/kalshi-launch
#   chmod +x ~/.local/bin/kalshi-launch

KALSHI_DIR="$HOME/Projects/polymarket-bot"
WAIT=14  # seconds for Claude to load before sending commands

# ---- Validate ----
if [[ ! -d "$KALSHI_DIR" ]]; then
    echo "ERROR: $KALSHI_DIR does not exist"
    exit 1
fi

echo "Launching Kalshi dual-chat in Terminal.app..."

# ---- Strategy: use unique window titles to reliably target each window ----
# AppleScript `do script` returns the tab it created. We use that reference
# for all subsequent commands, avoiding window-ordering issues.

osascript - "$KALSHI_DIR" "$WAIT" <<'APPLESCRIPT'
on run argv
    set kalshiDir to item 1 of argv
    set waitSec to (item 2 of argv) as integer

    tell application "Terminal"
        activate

        -- Create Window 1: Main Chat
        set mainTab to do script ("cd " & kalshiDir & " && claude --dangerously-skip-permissions")
        set custom title of (first window whose selected tab is mainTab) to "Kalshi Main"

        -- Create Window 2: Research Chat
        set researchTab to do script ("cd " & kalshiDir & " && claude --dangerously-skip-permissions")
        set custom title of (first window whose selected tab is researchTab) to "Kalshi Research"

        -- Wait for Claude to load in both windows
        delay waitSec

        -- Init Main Chat
        do script "/polybot-init" in mainTab
        delay 4
        do script "/polybot-auto" in mainTab
        delay 4
        do script "Your job is to maintain live bets and the live bot. Monitor for bugs, glitches, don't let guards fail. Win money - replicate the profitable March 14 night session sniper bets approach. Work autonomously for 2 hours. Don't expect a response from me. Don't break anything, don't break this computer, don't let my info or money get stolen. When a session finishes, keep working - start a new one." in mainTab

        -- Init Research Chat
        do script "/polybot-init" in researchTab
        delay 4
        do script "/polybot-autoresearch" in researchTab
        delay 4
        do script "Your job is research - find new bets, markets, and edges of similar or greater quality than the sniper bets. Ensure no bugs, glitches, or guard fails mess with the bot. You do NOT monitor live bets - that is the other chat's job. Work autonomously for 2 hours. Don't expect a response from me. Don't break anything, don't break this computer, don't let my info or money get stolen. When a session finishes, keep working." in researchTab

    end tell
end run
APPLESCRIPT

echo ""
echo "Both chats launched and initialized."
echo "  Kalshi Main    — live monitoring + betting"
echo "  Kalshi Research — finding edges + bugs"
echo ""
echo "You're in control now."
