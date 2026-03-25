#!/bin/bash
# autoloop_toggle.sh — MT-35 Phase 4: One-key autoloop pause/resume toggle.
#
# Toggles the CCA autoloop pause state and shows a macOS notification.
# Bind to Ctrl+Shift+P via macOS System Settings > Keyboard > Shortcuts:
#   1. Open Automator → New → Quick Action
#   2. Set "Workflow receives" to "no input"
#   3. Add "Run Shell Script" action with: /path/to/autoloop_toggle.sh
#   4. Save as "Toggle CCA Autoloop"
#   5. System Settings → Keyboard → Shortcuts → Services → assign Ctrl+Shift+P
#
# Or use Hammerspoon/skhd for direct binding without Automator.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PAUSE_FILE="$HOME/.cca-autoloop-paused"

# Toggle
output=$(python3 "$SCRIPT_DIR/autoloop_pause.py" toggle 2>&1)
status=$?

if [ $status -ne 0 ]; then
    osascript -e "display notification \"Toggle failed: $output\" with title \"CCA Autoloop\" sound name \"Basso\""
    exit 1
fi

# Show notification
if [ -f "$PAUSE_FILE" ]; then
    osascript -e 'display notification "Autoloop PAUSED — no new sessions will spawn" with title "CCA Autoloop ⏸" sound name "Purr"'
else
    osascript -e 'display notification "Autoloop RESUMED — sessions will spawn normally" with title "CCA Autoloop ▶" sound name "Purr"'
fi
