"""
Correction Capture — PostToolUse hook that detects error->correction sequences.

Adapted from Prism MCP's mistake-learning pattern. When a tool fails and then
the agent corrects it (succeeds on the same resource), the correction is
auto-captured to the self-learning journal for future resurfacing.

Wire as PostToolUse hook in settings.local.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/self-learning/hooks/correction_capture.py"
          }
        ]
      }
    ]
  }
}

Environment variables:
  CLAUDE_CORRECTION_CAPTURE_DISABLED  - Set to "1" to disable
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from correction_detector import CorrectionDetector


def main() -> None:
    # Check if disabled
    if os.environ.get("CLAUDE_CORRECTION_CAPTURE_DISABLED") == "1":
        return

    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    # Extract tool info from hook payload
    tool_name = hook_input.get("tool_name", "")
    tool_output = hook_input.get("tool_output", "")
    tool_input = hook_input.get("tool_input", {})

    # Normalize tool_output to string
    if isinstance(tool_output, dict):
        tool_output = (
            tool_output.get("stdout", "")
            or tool_output.get("output", "")
            or tool_output.get("content", "")
            or json.dumps(tool_output)
        )

    if not tool_output or not isinstance(tool_output, str):
        return

    # Initialize detector and load persisted state
    detector = CorrectionDetector()
    detector.load_state()

    # Add result and check for correction
    correction = detector.add(
        tool_name=tool_name,
        tool_output=tool_output,
        tool_input=tool_input if isinstance(tool_input, dict) else {},
    )

    # Persist state
    detector.save_state()

    # If correction detected, log to journal
    if correction:
        _log_correction(correction)


def _log_correction(correction) -> None:
    """Log a detected correction to the self-learning journal."""
    # Import journal here to avoid circular imports at module level
    from journal import log_event

    log_event(
        event_type="correction_captured",
        domain="self_learning",
        metrics={
            "error_tool": correction.error_tool,
            "fix_tool": correction.fix_tool,
            "time_to_fix_seconds": correction.time_to_fix,
            "error_pattern": correction.error_pattern,
        },
        notes=(
            f"Error on {correction.error_resource}: {correction.error_pattern}. "
            f"Fixed with {correction.fix_tool} after {correction.time_to_fix:.0f}s."
        ),
    )


if __name__ == "__main__":
    main()
