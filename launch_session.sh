#!/bin/bash
# launch_session.sh — Unified multi-chat session launcher
#
# Usage:
#   bash launch_session.sh solo                  # Just CCA desktop (no terminals)
#   bash launch_session.sh 2chat "worker task"   # CCA desktop + CLI worker
#   bash launch_session.sh 3chat "worker task"   # CCA desktop + CLI worker + Kalshi main
#
# What it does:
#   1. Pre-flight safety checks (duplicate sessions, peak hours, auth)
#   2. Launches requested terminal chats in new Terminal windows
#   3. Reports status
#
# This script does NOT start the desktop coordinator — that's the chat
# you're already in. It only launches the HELPER terminals.
#
# Safety:
#   - Pre-launch duplicate detection (aborts if same worker already running)
#   - Peak hours warning
#   - Auth fix check (ANTHROPIC_API_KEY must not be exported)
#   - Delay between launches to avoid rate limit spikes

set -euo pipefail

CCA_DIR="/Users/matthewshields/Projects/ClaudeCodeAdvancements"
MODE="${1:-}"
WORKER_TASK="${2:-}"

if [ -z "$MODE" ] || [ "$MODE" = "help" ] || [ "$MODE" = "--help" ]; then
    echo "launch_session.sh — Unified multi-chat session launcher"
    echo ""
    echo "Usage:"
    echo "  bash launch_session.sh solo                    # No helper terminals"
    echo "  bash launch_session.sh 2chat \"worker task\"     # Launch CLI worker"
    echo "  bash launch_session.sh 3chat \"worker task\"     # Launch CLI worker + Kalshi main"
    echo ""
    echo "Notes:"
    echo "  - Run this FROM the CCA desktop coordinator chat"
    echo "  - This only launches helper terminals, not the desktop chat itself"
    echo "  - Worker task is optional (can queue via cca_comm.py after launch)"
    echo "  - Kalshi main runs independently — no CCA coordination needed"
    exit 0
fi

# ── Validate mode ──────────────────────────────────────────────────────
if [[ "$MODE" != "solo" && "$MODE" != "2chat" && "$MODE" != "3chat" ]]; then
    echo "ERROR: Invalid mode '$MODE'. Must be: solo, 2chat, or 3chat"
    exit 1
fi

# ── Solo mode — nothing to launch ─────────────────────────────────────
if [ "$MODE" = "solo" ]; then
    echo "Solo mode — no helper terminals to launch."
    echo "You're the only chat. Run /cca-auto to start working."
    exit 0
fi

# ── Pre-flight checks ─────────────────────────────────────────────────
echo "=== Pre-flight checks ==="

# 1. Peak hours warning
if python3 "$CCA_DIR/peak_hours.py" --check 2>/dev/null; then
    echo "[OK] Off-peak hours — full rate limits available"
else
    echo "[WARN] Peak hours (8AM-2PM ET weekday) — standard rate limits apply"
    echo "       Consider fewer parallel chats during peak."
fi

# 2. Auth check — ANTHROPIC_API_KEY should NOT be exported
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo "[WARN] ANTHROPIC_API_KEY is set in environment!"
    echo "       Terminal chats will use API credits instead of Max subscription."
    echo "       Fix: unset ANTHROPIC_API_KEY (or run the zshrc sed fix)"
fi

# 3. Duplicate worker check
CHECK_RESULT=$(python3 "$CCA_DIR/chat_detector.py" check cli1 2>&1 || true)
if echo "$CHECK_RESULT" | grep -q "^BLOCKED"; then
    echo "[BLOCKED] Worker cli1 is already running: $CHECK_RESULT"
    echo "Kill the existing worker first, or use a different worker ID."
    exit 1
fi
echo "$CHECK_RESULT" | grep "WARNING" && true || echo "[OK] No duplicate workers detected"

echo ""

# ── Launch worker ─────────────────────────────────────────────────────
echo "=== Launching CLI worker ==="
if [ -n "$WORKER_TASK" ]; then
    bash "$CCA_DIR/launch_worker.sh" "$WORKER_TASK"
else
    bash "$CCA_DIR/launch_worker.sh"
fi
echo "[DONE] Worker launched"

# ── Launch Kalshi (3chat only) ────────────────────────────────────────
if [ "$MODE" = "3chat" ]; then
    echo ""
    echo "=== Launching Kalshi main ==="
    # Small delay between launches to avoid rate limit spikes
    sleep 3
    bash "$CCA_DIR/launch_kalshi.sh" main
    echo "[DONE] Kalshi main launched"
fi

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo "=== Session launched ==="
echo "  Mode: $MODE"
echo "  Desktop: this chat (coordinator)"
echo "  Worker:  cli1 (new Terminal window)"
if [ "$MODE" = "3chat" ]; then
    echo "  Kalshi:  main (new Terminal window)"
fi
echo ""
echo "Next steps:"
echo "  1. Verify worker started: python3 cca_comm.py status"
if [ -z "$WORKER_TASK" ]; then
    echo "  2. Queue worker tasks:  python3 cca_comm.py task cli1 \"task description\""
fi
echo "  3. Start desktop work:  /cca-auto-desktop"
echo "  4. Check worker:        python3 cca_comm.py inbox"
