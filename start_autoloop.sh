#!/bin/bash
# start_autoloop.sh — CCA Auto-Loop: runs claude sessions back-to-back
#
# Usage:
#   ./start_autoloop.sh              # Run directly (recommended: in tmux)
#   ./start_autoloop.sh --tmux       # Launch inside a new tmux window
#   ./start_autoloop.sh --status     # Show current loop status
#
# What this does:
#   1. Reads SESSION_RESUME.md (written by /cca-wrap)
#   2. Launches `claude` with the resume prompt + /cca-init + /cca-auto
#   3. claude runs interactively, works autonomously, wraps, exits
#   4. Script reads the NEW SESSION_RESUME.md, loops back to step 2
#   5. Stops after MAX_ITERATIONS, consecutive crashes, or Ctrl-C
#
# IMPORTANT: claude needs a real TTY for interactive mode. This script
# runs claude in the foreground so it inherits the terminal's TTY.
# That's why we use bash (not Python subprocess) for the actual spawning.
#
# Safety: Max 50 iterations, 15s cooldown, crash detection, audit logging.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_DIR="/Users/matthewshields/Projects/ClaudeCodeAdvancements"
RESUME_FILE="$PROJECT_DIR/SESSION_RESUME.md"
LOG_FILE="$HOME/.cca-autoloop.log"
STATE_FILE="$HOME/.cca-autoloop-state.json"

MAX_ITERATIONS=${CCA_AUTOLOOP_MAX:-50}
COOLDOWN=${CCA_AUTOLOOP_COOLDOWN:-15}
MIN_SESSION_SECS=30
MAX_CONSECUTIVE_CRASHES=3
MAX_CONSECUTIVE_SHORT=3

# Model alternation: round-robin | opus-primary | sonnet-primary
MODEL_STRATEGY=${MODEL_STRATEGY:-round-robin}

# State tracking
iteration=0
total_sessions=0
total_crashes=0
consecutive_crashes=0
consecutive_short=0

# Ensure Max subscription auth (not API key credits)
unset ANTHROPIC_API_KEY

cd "$PROJECT_DIR"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log_event() {
    local event="$1"
    local data="${2:-{}}"
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "{\"ts\":\"$ts\",\"event\":\"$event\",\"data\":$data}" >> "$LOG_FILE" 2>/dev/null || true
}

save_state() {
    cat > "$STATE_FILE" <<STATEJSON
{
  "iteration": $iteration,
  "total_sessions": $total_sessions,
  "total_crashes": $total_crashes,
  "consecutive_crashes": $consecutive_crashes,
  "consecutive_short": $consecutive_short,
  "last_updated": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
STATEJSON
}

read_resume() {
    if [ -f "$RESUME_FILE" ]; then
        local content
        content=$(cat "$RESUME_FILE")
        # Check for empty/whitespace-only
        if [ -z "$(echo "$content" | tr -d '[:space:]')" ]; then
            echo "Run /cca-init then /cca-auto. No resume prompt was found."
        else
            echo "$content"
        fi
    else
        echo "Run /cca-init then /cca-auto. No resume prompt was found."
    fi
}

select_model() {
    local iter="$1"
    case "$MODEL_STRATEGY" in
        opus-primary)
            echo "opus"
            ;;
        sonnet-primary)
            echo "sonnet"
            ;;
        *)
            # round-robin: odd=sonnet, even=opus
            if [ $((iter % 2)) -eq 1 ]; then
                echo "sonnet"
            else
                echo "opus"
            fi
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

if [ "${1:-}" = "--status" ]; then
    if [ -f "$STATE_FILE" ]; then
        echo "CCA Auto-Loop Status:"
        cat "$STATE_FILE"
    else
        echo "No state file found. Auto-loop may not have run yet."
    fi
    exit 0
fi

if [ "${1:-}" = "--tmux" ]; then
    SESSION="cca-workspace"
    WINDOW="cca-autoloop"

    if ! tmux has-session -t "$SESSION" 2>/dev/null; then
        tmux new-session -d -s "$SESSION" -n daemon
        echo "Created tmux session: $SESSION"
    fi

    if tmux list-windows -t "$SESSION" -F '#{window_name}' 2>/dev/null | grep -q "^${WINDOW}$"; then
        echo "Auto-loop window already exists. Attach with: tmux attach -t $SESSION:$WINDOW"
        exit 1
    fi

    tmux new-window -t "$SESSION" -n "$WINDOW" \
        "cd '$PROJECT_DIR' && unset ANTHROPIC_API_KEY && '$PROJECT_DIR/start_autoloop.sh'; echo 'Auto-loop exited. Press Enter.'; read"

    echo "CCA auto-loop started in tmux."
    echo "  Attach: tmux attach -t $SESSION:$WINDOW"
    echo "  Status: ./start_autoloop.sh --status"
    echo "  Stop:   Ctrl-C in the tmux window"
    exit 0
fi

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    echo "Usage: ./start_autoloop.sh [--tmux | --desktop | --status | --help]"
    echo ""
    echo "  (no args)   Run the auto-loop in the current terminal"
    echo "  --tmux      Launch in a new tmux window"
    echo "  --desktop   Open each session in a visible Terminal.app window (interactive)"
    echo "  --status    Show current loop state"
    echo ""
    echo "Environment:"
    echo "  CCA_AUTOLOOP_MAX=N       Max iterations (default: 50)"
    echo "  CCA_AUTOLOOP_COOLDOWN=N  Seconds between sessions (default: 15)"
    echo "  MODEL_STRATEGY=STR       Model alternation: round-robin|opus-primary|sonnet-primary (default: round-robin)"
    exit 0
fi

# ---------------------------------------------------------------------------
# Desktop Mode Flag
# ---------------------------------------------------------------------------
DESKTOP_MODE=false
if [ "${1:-}" = "--desktop" ]; then
    DESKTOP_MODE=true
fi

# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

echo "========================================"
echo "  CCA Auto-Loop Starting"
echo "  Max iterations: $MAX_ITERATIONS"
echo "  Cooldown: ${COOLDOWN}s"
echo "  Model strategy: $MODEL_STRATEGY"
echo "  Desktop mode: $DESKTOP_MODE"
echo "  Project: $PROJECT_DIR"
echo "========================================"
echo ""

log_event "loop_started" "{\"max_iterations\":$MAX_ITERATIONS,\"cooldown\":$COOLDOWN,\"model_strategy\":\"$MODEL_STRATEGY\",\"desktop_mode\":$DESKTOP_MODE}"

cleanup_and_exit() {
    echo ""
    echo "Auto-loop interrupted."
    save_state
    log_event "loop_interrupted" "{}"

    # If in desktop mode, try to clean up any orphaned temp files
    if [ "$DESKTOP_MODE" = true ]; then
        echo "Cleaning up temp files..."
        rm -f /tmp/cca-autoloop-sentinel-$$-* 2>/dev/null
        rm -f /tmp/cca-autoloop-wrapper-$$-* 2>/dev/null
        rm -f /tmp/cca-autoloop-prompt-$$-* 2>/dev/null
    fi

    exit 0
}

trap cleanup_and_exit INT TERM

# Pre-flight: check no other CCA CLI sessions running
CCA_CLI_COUNT=$(ps ax -o command 2>/dev/null | grep "claude.*dangerously-skip" | grep -i "cca\|ClaudeCodeAdvancements" | grep -v grep | wc -l | tr -d ' ')
if [ "$CCA_CLI_COUNT" -gt 0 ]; then
    echo "BLOCKED: $CCA_CLI_COUNT CCA CLI session(s) already running."
    echo "Only one CCA session at a time to avoid rate limit burn."
    echo "Close other CCA sessions first, then retry."
    log_event "blocked_duplicate_session" "{\"count\":$CCA_CLI_COUNT}"
    exit 1
fi

while [ $iteration -lt $MAX_ITERATIONS ]; do
    iteration=$((iteration + 1))
    echo "--- Iteration $iteration / $MAX_ITERATIONS ---"

    # Read resume prompt
    RESUME_PROMPT=$(read_resume)
    resume_len=${#RESUME_PROMPT}
    echo "Resume prompt: ${resume_len} chars"

    # Build the full prompt (same format Matthew uses manually)
    FULL_PROMPT="/cca-init then review prompt below then /cca-auto

$RESUME_PROMPT"

    # Select model for this iteration
    MODEL=$(select_model $iteration)
    echo "Model: $MODEL ($MODEL_STRATEGY)"

    log_event "iteration_start" "{\"iteration\":$iteration,\"resume_length\":$resume_len,\"model\":\"$MODEL\",\"model_strategy\":\"$MODEL_STRATEGY\"}"

    # Record start time
    start_ts=$(date +%s)

    if [ "$DESKTOP_MODE" = true ]; then
        # Desktop mode: open a visible, INTERACTIVE Terminal.app window
        # Matthew can watch claude and type messages/instructions to it
        # Controller polls sentinel file for session completion
        WINDOW_TITLE="CCA-AutoLoop-Iter-$iteration"
        SENTINEL="/tmp/cca-autoloop-sentinel-$$-$iteration"
        rm -f "$SENTINEL"

        # Save the prompt to a temp file (avoids quoting issues in osascript)
        PROMPT_FILE="/tmp/cca-autoloop-prompt-$$-$iteration.txt"
        printf '%s' "$FULL_PROMPT" > "$PROMPT_FILE"

        # Write a self-contained wrapper script
        WRAPPER="/tmp/cca-autoloop-wrapper-$$-$iteration.sh"
        cat > "$WRAPPER" <<WRAPEOF
#!/bin/bash
# Set window title for identification
printf '\e]0;$WINDOW_TITLE\a'

cd "$PROJECT_DIR"
unset ANTHROPIC_API_KEY

echo "========================================"
echo "  CCA Auto-Loop — Iteration $iteration"
echo "  Model: $MODEL ($MODEL_STRATEGY)"
echo "  Window: $WINDOW_TITLE"
echo "========================================"
echo ""

PROMPT=\$(cat "$PROMPT_FILE")
claude --dangerously-skip-permissions --model "$MODEL" "\$PROMPT"
CLAUDE_EXIT=\$?

echo \$CLAUDE_EXIT > "$SENTINEL"

echo ""
echo "Session complete (exit=\$CLAUDE_EXIT). Window closing in 3 seconds..."
sleep 3

# Auto-close this Terminal.app window by title
osascript -e 'tell application "Terminal"
    set targetTitle to "$WINDOW_TITLE"
    repeat with w in windows
        repeat with t in tabs of w
            if name of t contains targetTitle then
                close w
                return
            end if
        end repeat
    end repeat
end tell' &>/dev/null &
exit
WRAPEOF
        chmod +x "$WRAPPER"

        echo "Opening Terminal.app window: $WINDOW_TITLE (--model $MODEL)..."
        osascript -e "tell application \"Terminal\" to do script \"'$WRAPPER'\"" >/dev/null 2>&1

        # Poll for the sentinel file (claude session has exited)
        while [ ! -f "$SENTINEL" ]; do
            sleep 2
        done
        exit_code=$(cat "$SENTINEL")

        # Fallback: close the window if auto-close didn't work
        osascript -e "tell application \"Terminal\"
            set targetTitle to \"$WINDOW_TITLE\"
            repeat with w in windows
                repeat with t in tabs of w
                    if name of t contains targetTitle then
                        close w
                        return
                    end if
                end repeat
            end repeat
        end tell" &>/dev/null 2>&1 || true

        # Cleanup temp files
        rm -f "$SENTINEL" "$WRAPPER" "$PROMPT_FILE"
    else
        # Foreground mode: claude inherits TTY directly
        echo "Spawning claude session (--model $MODEL)..."
        set +e
        claude --dangerously-skip-permissions --model "$MODEL" "$FULL_PROMPT"
        exit_code=$?
        set -e
    fi

    # Record end time
    end_ts=$(date +%s)
    duration=$((end_ts - start_ts))
    total_sessions=$((total_sessions + 1))

    echo ""
    echo "Session exited: code=$exit_code  duration=${duration}s  model=$MODEL"

    log_event "iteration_complete" "{\"iteration\":$iteration,\"exit_code\":$exit_code,\"duration\":$duration,\"model\":\"$MODEL\"}"

    # Track crashes
    if [ $exit_code -ne 0 ]; then
        total_crashes=$((total_crashes + 1))
        consecutive_crashes=$((consecutive_crashes + 1))
        echo "WARNING: Session crashed (consecutive: $consecutive_crashes)"
    else
        consecutive_crashes=0
    fi

    # Track short sessions
    if [ $duration -lt $MIN_SESSION_SECS ]; then
        consecutive_short=$((consecutive_short + 1))
        echo "WARNING: Short session ${duration}s (consecutive: $consecutive_short)"
    else
        consecutive_short=0
    fi

    # Save state after every iteration
    save_state

    # Check stop conditions
    if [ $consecutive_crashes -ge $MAX_CONSECUTIVE_CRASHES ]; then
        echo "STOPPING: $MAX_CONSECUTIVE_CRASHES consecutive crashes"
        log_event "loop_stopped" "{\"reason\":\"consecutive_crashes\"}"
        break
    fi

    if [ $consecutive_short -ge $MAX_CONSECUTIVE_SHORT ]; then
        echo "STOPPING: $MAX_CONSECUTIVE_SHORT consecutive short sessions"
        log_event "loop_stopped" "{\"reason\":\"consecutive_short_sessions\"}"
        break
    fi

    # Cooldown before next iteration
    if [ $iteration -lt $MAX_ITERATIONS ]; then
        echo "Cooldown: ${COOLDOWN}s before next session..."
        sleep $COOLDOWN
    fi

    echo ""
done

echo ""
echo "========================================"
echo "  CCA Auto-Loop Complete"
echo "  Iterations: $iteration"
echo "  Sessions: $total_sessions"
echo "  Crashes: $total_crashes"
echo "========================================"

save_state
log_event "loop_finished" "{\"iterations\":$iteration,\"sessions\":$total_sessions,\"crashes\":$total_crashes}"
