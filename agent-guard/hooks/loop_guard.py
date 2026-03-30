"""
Loop Guard — PostToolUse hook that detects autonomous agent loops.

Reads the tool output from stdin (Claude Code hook protocol), feeds it to
the LoopDetector, and outputs a warning if a loop is detected. The warning
is non-blocking — it alerts Claude but doesn't prevent tool execution.

Wire as PostToolUse hook in settings.local.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/agent-guard/hooks/loop_guard.py"
          }
        ]
      }
    ]
  }
}

Environment variables:
  CLAUDE_LOOP_GUARD_DISABLED  - Set to "1" to disable
  CLAUDE_LOOP_THRESHOLD       - Similarity threshold (default: 0.80)
  CLAUDE_LOOP_MIN_CONSECUTIVE - Consecutive similar outputs to trigger (default: 3)
  CLAUDE_LOOP_WINDOW          - Ring buffer size (default: 8)
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path so we can import loop_detector
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loop_detector import LoopDetector, DEFAULT_THRESHOLD, DEFAULT_MIN_CONSECUTIVE, DEFAULT_WINDOW


def main() -> None:
    # Check if disabled
    if os.environ.get("CLAUDE_LOOP_GUARD_DISABLED") == "1":
        return

    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    # Extract tool name and output from hook payload
    tool_name = hook_input.get("tool_name", "")
    tool_output = hook_input.get("tool_output", "")

    # For Bash tool, the output might be nested
    if isinstance(tool_output, dict):
        tool_output = tool_output.get("stdout", "") or tool_output.get("output", "") or json.dumps(tool_output)

    if not tool_output or not isinstance(tool_output, str):
        return

    # Configure detector from env vars
    threshold = float(os.environ.get("CLAUDE_LOOP_THRESHOLD", str(DEFAULT_THRESHOLD)))
    min_consecutive = int(os.environ.get("CLAUDE_LOOP_MIN_CONSECUTIVE", str(DEFAULT_MIN_CONSECUTIVE)))
    window = int(os.environ.get("CLAUDE_LOOP_WINDOW", str(DEFAULT_WINDOW)))

    # Initialize detector and load persisted state
    detector = LoopDetector(
        window=window,
        threshold=threshold,
        min_consecutive=min_consecutive,
    )
    detector.load_state()

    # Add the new output and check for loops
    detector.add(tool_output, tool_name=tool_name)
    result = detector.check()

    # Persist state for next invocation
    detector.save_state()

    # If loop detected, output a warning via hook protocol
    if result.is_loop:
        warning = {
            "hookSpecificOutput": {
                "message": (
                    f"LOOP DETECTED: {result.consecutive_similar} consecutive "
                    f"similar outputs ({result.avg_similarity:.0%} avg similarity). "
                    f"Tool: {result.tool_name}. "
                    f"{result.recommendation}"
                ),
            }
        }
        json.dump(warning, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
