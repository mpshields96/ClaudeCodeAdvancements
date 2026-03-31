#!/usr/bin/env python3
"""
Failure Capture — PostToolUseFailure hook that logs definitive tool failures.

Complementary to correction_capture.py (PostToolUse). While correction_capture
uses heuristics to detect errors in successful tool output, this hook fires
only when a tool actually fails — no false positives.

Together they give:
  - Definitive error signal (this hook, PostToolUseFailure)
  - Correction detection (correction_capture.py, PostToolUse)

Wire as PostToolUseFailure hook in settings.local.json:
{
  "hooks": {
    "PostToolUseFailure": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/self-learning/hooks/failure_capture.py"
          }
        ]
      }
    ]
  }
}

Environment variables:
  CLAUDE_FAILURE_CAPTURE_DISABLED  - Set to "1" to disable
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
    if os.environ.get("CLAUDE_FAILURE_CAPTURE_DISABLED") == "1":
        return

    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    # Extract tool info from hook payload
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # For PostToolUseFailure, the output IS the error — use it directly
    tool_output = hook_input.get("tool_output", "")
    if isinstance(tool_output, dict):
        tool_output = (
            tool_output.get("error", "")
            or tool_output.get("stderr", "")
            or tool_output.get("message", "")
            or tool_output.get("stdout", "")
            or json.dumps(tool_output)
        )

    if not tool_output or not isinstance(tool_output, str):
        # Even without output, the failure itself is worth recording
        tool_output = f"Tool {tool_name} failed (no error details)"

    # Feed to the correction detector — this registers the error in the buffer
    # so that correction_capture.py can detect the fix on the next PostToolUse
    detector = CorrectionDetector()
    detector.load_state()

    # Force-mark as error since PostToolUseFailure is definitive
    # We call add() which will detect the error via patterns,
    # but even if patterns don't match, the output from a failure hook
    # should be treated as an error. We prepend "Error: " to ensure detection.
    if not tool_output.startswith("Error"):
        error_output = f"Error: {tool_output}"
    else:
        error_output = tool_output

    detector.add(
        tool_name=tool_name,
        tool_output=error_output,
        tool_input=tool_input if isinstance(tool_input, dict) else {},
    )

    detector.save_state()

    # Also log the failure directly to journal for tracking
    _log_failure(tool_name, tool_output, tool_input)


def _log_failure(tool_name: str, error_output: str, tool_input: dict) -> None:
    """Log a tool failure to the self-learning journal."""
    from journal import log_event

    # Extract resource for context
    from correction_detector import extract_resource
    resource = extract_resource(tool_name, tool_input if isinstance(tool_input, dict) else {})

    log_event(
        event_type="error",
        domain="self_learning",
        metrics={
            "tool_name": tool_name,
            "resource": resource[:200],
        },
        notes=f"Tool failure: {tool_name} on {resource[:100]}. {error_output[:300]}",
    )


if __name__ == "__main__":
    main()
