#!/bin/bash
# launch_codex.sh — Start Codex in a new Terminal.app window
#
# Usage:
#   bash launch_codex.sh
#   bash launch_codex.sh cca
#   bash launch_codex.sh kalshi
#   bash launch_codex.sh "CCA init"
#   bash launch_codex.sh cca "CCA go: tighten codex terminal docs"
#   bash launch_codex.sh kalshi "Kalshi init"
#
# What it does:
#   1. Opens a new Terminal.app window
#   2. cd to the requested repo (CCA by default)
#   3. Starts Codex pinned to gpt-5.4 + high reasoning + danger-full-access
#   4. Sets CCA_CHAT_ID=codex for CCA sessions so cca_comm.py works
#
# Notes:
#   - This mirrors the existing CCA/Kalshi launcher pattern: open Terminal.app,
#     set context, then start the agent directly.
#   - Codex auth/config still comes from your local Codex install; the launch
#     flags make the intended model/access profile explicit.

set -euo pipefail

CCA_DIR="/Users/matthewshields/Projects/ClaudeCodeAdvancements"
KALSHI_DIR="/Users/matthewshields/Projects/polymarket-bot"
MODE="${1:-cca}"
PROMPT=""

if [[ "$MODE" != "cca" && "$MODE" != "kalshi" ]]; then
    PROMPT="$MODE"
    MODE="cca"
else
    PROMPT="${2:-}"
fi

if [ "$MODE" = "cca" ]; then
    WORKDIR="$CCA_DIR"
    DEFAULT_PROMPT="CCA init"
    CHAT_ID_EXPORT='export CCA_CHAT_ID=codex'
    LABEL="CCA"
else
    WORKDIR="$KALSHI_DIR"
    DEFAULT_PROMPT="Kalshi init"
    CHAT_ID_EXPORT=""
    LABEL="Kalshi"
fi

if [ ! -d "$WORKDIR" ]; then
    echo "ERROR: $WORKDIR does not exist"
    exit 1
fi

if [ -z "$PROMPT" ]; then
    PROMPT="$DEFAULT_PROMPT"
fi

TMPSCRIPT=$(mktemp /tmp/codex_launch_XXXXXX.sh)
PROMPT_ESCAPED=$(printf '%q' "$PROMPT")

cat > "$TMPSCRIPT" <<INNERSCRIPT
#!/bin/bash
unset ANTHROPIC_API_KEY
$CHAT_ID_EXPORT
cd "$WORKDIR"
PROMPT_CONTENT=$PROMPT_ESCAPED
echo "=== Codex ($LABEL) ==="
echo "Model: gpt-5.4"
echo "Reasoning: high"
echo "Access: danger-full-access + approval never"
echo "Directory: $WORKDIR"
if [ -n "\$PROMPT_CONTENT" ]; then
    echo "Startup prompt: \$PROMPT_CONTENT"
fi
echo ""
rm -f "$TMPSCRIPT"
exec codex -m gpt-5.4 -c 'model_reasoning_effort="high"' -s danger-full-access -a never "\$PROMPT_CONTENT"
INNERSCRIPT
chmod +x "$TMPSCRIPT"

open -a Terminal "$TMPSCRIPT"

echo ""
echo "Codex launched in new Terminal window."
echo "  Repo: $LABEL"
echo "  Directory: $WORKDIR"
echo "  Prompt: $PROMPT"
echo "  Model: gpt-5.4"
echo "  Reasoning: high"
echo "  Access: danger-full-access + approval never"
