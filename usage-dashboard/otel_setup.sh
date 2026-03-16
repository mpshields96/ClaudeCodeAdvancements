#!/bin/bash
# USAGE-2: OTel Setup for Claude Code
#
# Configures environment variables for Claude Code OpenTelemetry metrics
# to flow to the local OTLP receiver (otel_receiver.py).
#
# Usage:
#   source usage-dashboard/otel_setup.sh          # Enable OTel (default port 4318)
#   source usage-dashboard/otel_setup.sh 4319     # Custom port
#   source usage-dashboard/otel_setup.sh off      # Disable OTel
#
# After sourcing, restart Claude Code for changes to take effect.

OTEL_PORT="${1:-4318}"

if [ "$OTEL_PORT" = "off" ] || [ "$OTEL_PORT" = "disable" ]; then
    unset CLAUDE_CODE_ENABLE_TELEMETRY
    unset OTEL_METRICS_EXPORTER
    unset OTEL_LOGS_EXPORTER
    unset OTEL_EXPORTER_OTLP_PROTOCOL
    unset OTEL_EXPORTER_OTLP_ENDPOINT
    echo "OTel disabled. Restart Claude Code for changes to take effect."
    return 0 2>/dev/null || exit 0
fi

export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:${OTEL_PORT}"

echo "OTel configured for Claude Code:"
echo "  CLAUDE_CODE_ENABLE_TELEMETRY=1"
echo "  OTEL_METRICS_EXPORTER=otlp"
echo "  OTEL_LOGS_EXPORTER=otlp"
echo "  OTEL_EXPORTER_OTLP_PROTOCOL=http/json"
echo "  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:${OTEL_PORT}"
echo ""
echo "Next steps:"
echo "  1. Start receiver:  python3 $(dirname "$0")/otel_receiver.py start --port ${OTEL_PORT}"
echo "  2. Restart Claude Code (new terminal or 'claude' command)"
echo "  3. View metrics:    python3 $(dirname "$0")/otel_receiver.py summary"
