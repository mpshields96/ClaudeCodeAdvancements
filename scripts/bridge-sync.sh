#!/bin/bash
# bridge-sync.sh — Cross-chat communication bridge
# Syncs communication files between CCA and polymarket-bot projects.
#
# Usage:
#   ./scripts/bridge-sync.sh           # Sync both directions
#   ./scripts/bridge-sync.sh --status  # Show what's pending
#
# What it syncs:
#   CCA → Polybot: CCA_TO_POLYBOT.md, KALSHI_PRIME_DIRECTIVE.md
#   Polybot → CCA: POLYBOT_TO_CCA.md (if it exists)
#   Shared: CROSS_CHAT_INBOX.md (both can read/write)

CCA_DIR="/Users/matthewshields/Projects/ClaudeCodeAdvancements"
POLYBOT_DIR="/Users/matthewshields/Projects/polymarket-bot"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ "$1" = "--status" ]; then
    echo "=== Cross-Chat Bridge Status ==="
    echo ""
    echo "CCA → Polybot:"
    [ -f "$CCA_DIR/CCA_TO_POLYBOT.md" ] && echo "  CCA_TO_POLYBOT.md: EXISTS ($(wc -l < "$CCA_DIR/CCA_TO_POLYBOT.md") lines)" || echo "  CCA_TO_POLYBOT.md: not found"
    [ -f "$CCA_DIR/KALSHI_PRIME_DIRECTIVE.md" ] && echo "  KALSHI_PRIME_DIRECTIVE.md: EXISTS" || echo "  KALSHI_PRIME_DIRECTIVE.md: not found"
    echo ""
    echo "Polybot → CCA:"
    [ -f "$POLYBOT_DIR/POLYBOT_TO_CCA.md" ] && echo "  POLYBOT_TO_CCA.md: EXISTS ($(wc -l < "$POLYBOT_DIR/POLYBOT_TO_CCA.md") lines)" || echo "  POLYBOT_TO_CCA.md: not found"
    echo ""
    echo "Shared inbox:"
    [ -f "$CCA_DIR/CROSS_CHAT_INBOX.md" ] && echo "  CROSS_CHAT_INBOX.md: EXISTS ($(wc -l < "$CCA_DIR/CROSS_CHAT_INBOX.md") lines)" || echo "  CROSS_CHAT_INBOX.md: not found"
    exit 0
fi

echo "=== Syncing Cross-Chat Bridge ==="

# CCA → Polybot
if [ -f "$CCA_DIR/CCA_TO_POLYBOT.md" ]; then
    cp "$CCA_DIR/CCA_TO_POLYBOT.md" "$POLYBOT_DIR/CCA_TO_POLYBOT.md"
    echo -e "${GREEN}[OK]${NC} CCA_TO_POLYBOT.md → polymarket-bot/"
fi

if [ -f "$CCA_DIR/KALSHI_PRIME_DIRECTIVE.md" ]; then
    cp "$CCA_DIR/KALSHI_PRIME_DIRECTIVE.md" "$POLYBOT_DIR/KALSHI_PRIME_DIRECTIVE.md"
    echo -e "${GREEN}[OK]${NC} KALSHI_PRIME_DIRECTIVE.md → polymarket-bot/"
fi

# Polybot → CCA
if [ -f "$POLYBOT_DIR/POLYBOT_TO_CCA.md" ]; then
    cp "$POLYBOT_DIR/POLYBOT_TO_CCA.md" "$CCA_DIR/POLYBOT_TO_CCA.md"
    echo -e "${GREEN}[OK]${NC} POLYBOT_TO_CCA.md → ClaudeCodeAdvancements/"
else
    echo -e "${YELLOW}[--]${NC} No POLYBOT_TO_CCA.md to sync"
fi

# Copy inbox to polybot so research chat can read/write it
if [ -f "$CCA_DIR/CROSS_CHAT_INBOX.md" ]; then
    cp "$CCA_DIR/CROSS_CHAT_INBOX.md" "$POLYBOT_DIR/CROSS_CHAT_INBOX.md"
    echo -e "${GREEN}[OK]${NC} CROSS_CHAT_INBOX.md → polymarket-bot/"
fi

echo ""
echo "Done. Both projects now have the latest communication files."
echo "Kalshi research chat: read CCA_TO_POLYBOT.md for the analytics framework."
