"""
correction_detector.py — Detects error->correction sequences in tool usage.

Adapted from Prism MCP's mistake-learning pattern. When a tool fails and then
succeeds on the same resource (file, command), the correction is auto-captured
and logged to the self-learning journal. Over time, these corrections surface
as proactive warnings in future sessions.

Design:
- Maintains a short buffer of recent tool results (success/failure)
- Detects: tool T fails on resource R, then tool T (or related) succeeds on R
- Captures: what failed, what succeeded, the resource involved
- Persists state between hook invocations via JSON state file

v1: Heuristic error detection from tool output strings.
No embeddings, no external dependencies. Stdlib only.
"""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_STATE_FILE = Path.home() / ".claude-correction-detector.json"
DEFAULT_BUFFER_SIZE = 12  # Recent tool results to keep
DEFAULT_MAX_AGE_SECONDS = 300  # 5 minutes — corrections older than this are stale

# Max output to store per entry (enough for error messages, not full file contents)
MAX_OUTPUT_LENGTH = 1500


# ---------------------------------------------------------------------------
# Error detection heuristics
# ---------------------------------------------------------------------------

# Patterns that strongly indicate tool failure
ERROR_PATTERNS = [
    # Python tracebacks
    re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE),
    re.compile(r"^\s*(?:File|Module)Error:", re.MULTILINE),
    # Common tool errors
    re.compile(r"Error:\s+", re.IGNORECASE),
    re.compile(r"command not found", re.IGNORECASE),
    re.compile(r"No such file or directory", re.IGNORECASE),
    re.compile(r"Permission denied", re.IGNORECASE),
    re.compile(r"failed with exit code \d+", re.IGNORECASE),
    # Edit tool failures
    re.compile(r"old_string.*not found", re.IGNORECASE),
    re.compile(r"old_string.*not unique", re.IGNORECASE),
    re.compile(r"is not unique in the file", re.IGNORECASE),
    # Read tool failures
    re.compile(r"File does not exist", re.IGNORECASE),
    re.compile(r"File content.*exceeds maximum", re.IGNORECASE),
    # Build/test failures
    re.compile(r"FAILED", re.IGNORECASE),
    re.compile(r"AssertionError", re.IGNORECASE),
    re.compile(r"SyntaxError:", re.IGNORECASE),
    re.compile(r"ImportError:", re.IGNORECASE),
    re.compile(r"ModuleNotFoundError:", re.IGNORECASE),
    re.compile(r"TypeError:", re.IGNORECASE),
    re.compile(r"ValueError:", re.IGNORECASE),
    re.compile(r"KeyError:", re.IGNORECASE),
    re.compile(r"AttributeError:", re.IGNORECASE),
    re.compile(r"NameError:", re.IGNORECASE),
    # Bash exit codes
    re.compile(r"exit code [1-9]\d*", re.IGNORECASE),
    re.compile(r"exited with \d+", re.IGNORECASE),
]

# Patterns that indicate success (used to confirm correction)
SUCCESS_INDICATORS = [
    re.compile(r"^\d+ passed", re.MULTILINE),
    re.compile(r"tests? passed", re.IGNORECASE),
    re.compile(r"Build succeeded", re.IGNORECASE),
    re.compile(r"Successfully", re.IGNORECASE),
    re.compile(r"OK$", re.MULTILINE),
]


def detect_error(output: str) -> Optional[str]:
    """Check if tool output indicates an error. Returns matched pattern or None."""
    for pattern in ERROR_PATTERNS:
        match = pattern.search(output)
        if match:
            return match.group(0).strip()
    return None


def extract_resource(tool_name: str, tool_input: dict) -> str:
    """Extract the primary resource (file path, command) from tool input."""
    if tool_name in ("Read", "Write", "Edit"):
        return tool_input.get("file_path", "")
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        # Extract primary file/path from command if present
        return cmd[:200]  # Truncate long commands
    elif tool_name in ("Glob", "Grep"):
        return tool_input.get("pattern", "")
    return tool_name


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """A single tool invocation result."""
    tool_name: str
    resource: str          # File path, command, or pattern
    output_preview: str    # Truncated output
    is_error: bool
    error_pattern: str     # What matched as an error (empty if success)
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "resource": self.resource,
            "output_preview": self.output_preview,
            "is_error": self.is_error,
            "error_pattern": self.error_pattern,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ToolResult":
        return cls(
            tool_name=d["tool_name"],
            resource=d["resource"],
            output_preview=d["output_preview"],
            is_error=d["is_error"],
            error_pattern=d.get("error_pattern", ""),
            timestamp=d["timestamp"],
        )


@dataclass
class CorrectionEvent:
    """A detected error->correction sequence."""
    error_tool: str        # Tool that failed
    error_resource: str    # What it failed on
    error_output: str      # What the error looked like
    error_pattern: str     # Which error pattern matched
    fix_tool: str          # Tool that succeeded
    fix_resource: str      # What it succeeded on
    fix_output: str        # What success looked like
    time_to_fix: float     # Seconds between error and fix
    timestamp: float       # When the correction was detected

    def to_dict(self) -> dict:
        return {
            "error_tool": self.error_tool,
            "error_resource": self.error_resource,
            "error_output": self.error_output[:500],
            "error_pattern": self.error_pattern,
            "fix_tool": self.fix_tool,
            "fix_resource": self.fix_resource,
            "fix_output": self.fix_output[:500],
            "time_to_fix": round(self.time_to_fix, 1),
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Core detector
# ---------------------------------------------------------------------------

class CorrectionDetector:
    """
    Detects error->correction sequences across tool invocations.

    After each tool result, checks whether it corrects a recent error on
    the same resource. If so, returns a CorrectionEvent for logging.

    Two matching modes:
    1. Same-resource: Edit fails on file X, then Edit succeeds on file X
    2. Same-tool-type: Bash command fails, then similar Bash command succeeds
    """

    def __init__(
        self,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        max_age: float = DEFAULT_MAX_AGE_SECONDS,
        state_file: Optional[Path] = None,
    ):
        self.buffer_size = buffer_size
        self.max_age = max_age
        self.state_file = state_file or DEFAULT_STATE_FILE
        self.buffer: list[ToolResult] = []
        self._corrections_detected = 0
        self._total_processed = 0

    def add(
        self,
        tool_name: str,
        tool_output: str,
        tool_input: Optional[dict] = None,
    ) -> Optional[CorrectionEvent]:
        """
        Add a tool result and check if it corrects a recent error.

        Returns CorrectionEvent if a correction was detected, None otherwise.
        """
        self._total_processed += 1
        now = time.time()

        # Determine error status
        error_match = detect_error(tool_output)
        is_error = error_match is not None

        # Extract resource identifier
        resource = extract_resource(tool_name, tool_input or {})

        entry = ToolResult(
            tool_name=tool_name,
            resource=resource,
            output_preview=tool_output[:MAX_OUTPUT_LENGTH],
            is_error=is_error,
            error_pattern=error_match or "",
            timestamp=now,
        )

        # Check for correction BEFORE adding new entry
        correction = None
        if not is_error:
            correction = self._find_correction(entry)

        # Add to buffer and trim
        self.buffer.append(entry)
        if len(self.buffer) > self.buffer_size:
            self.buffer = self.buffer[-self.buffer_size:]

        # Prune stale entries
        cutoff = now - self.max_age
        self.buffer = [e for e in self.buffer if e.timestamp >= cutoff]

        if correction:
            self._corrections_detected += 1

        return correction

    def _find_correction(self, success_entry: ToolResult) -> Optional[CorrectionEvent]:
        """
        Check if this successful result corrects a recent error.

        Looks backward through the buffer for a matching error:
        1. Same file path (for Read/Write/Edit)
        2. Same tool type + similar resource (for Bash/Grep/Glob)
        """
        now = success_entry.timestamp

        # Search backward for the most recent matching error
        for i in range(len(self.buffer) - 1, -1, -1):
            prev = self.buffer[i]
            if not prev.is_error:
                continue

            # Skip stale errors
            age = now - prev.timestamp
            if age > self.max_age:
                continue

            # Match: same resource (file path or command pattern)
            if self._resources_match(prev, success_entry):
                return CorrectionEvent(
                    error_tool=prev.tool_name,
                    error_resource=prev.resource,
                    error_output=prev.output_preview,
                    error_pattern=prev.error_pattern,
                    fix_tool=success_entry.tool_name,
                    fix_resource=success_entry.resource,
                    fix_output=success_entry.output_preview,
                    time_to_fix=age,
                    timestamp=now,
                )

        return None

    def _resources_match(self, error: ToolResult, success: ToolResult) -> bool:
        """Check if two tool results operate on the same resource."""
        # File-based tools: exact path match
        if error.tool_name in ("Read", "Write", "Edit") and \
           success.tool_name in ("Read", "Write", "Edit"):
            return (
                error.resource == success.resource
                and error.resource != ""
            )

        # Bash: same command prefix (first 80 chars)
        if error.tool_name == "Bash" and success.tool_name == "Bash":
            e_cmd = error.resource[:80]
            s_cmd = success.resource[:80]
            if not e_cmd or not s_cmd:
                return False
            # Same command base (e.g., "python3 test_foo.py" both times)
            e_base = e_cmd.split()[0] if e_cmd.split() else ""
            s_base = s_cmd.split()[0] if s_cmd.split() else ""
            return e_base == s_base and e_base != ""

        # Search tools: same pattern
        if error.tool_name in ("Glob", "Grep") and \
           success.tool_name in ("Glob", "Grep"):
            return error.resource == success.resource and error.resource != ""

        # Cross-tool: Edit fails, then Write to same file (rewrote instead of edited)
        if error.tool_name == "Edit" and success.tool_name == "Write":
            return error.resource == success.resource and error.resource != ""

        # Cross-tool: Read fails, then Glob for same pattern (file moved)
        # This is too loose — skip for v1

        return False

    def save_state(self) -> None:
        """Persist detector state to disk."""
        state = {
            "buffer": [e.to_dict() for e in self.buffer],
            "corrections_detected": self._corrections_detected,
            "total_processed": self._total_processed,
        }
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2))
        tmp.rename(self.state_file)

    def load_state(self) -> bool:
        """Load detector state from disk. Returns True if loaded."""
        if not self.state_file.exists():
            return False
        try:
            state = json.loads(self.state_file.read_text())
            self.buffer = [
                ToolResult.from_dict(d) for d in state.get("buffer", [])
            ]
            self._corrections_detected = state.get("corrections_detected", 0)
            self._total_processed = state.get("total_processed", 0)
            return True
        except (json.JSONDecodeError, KeyError, TypeError):
            return False

    def reset(self) -> None:
        """Clear buffer and state file."""
        self.buffer.clear()
        self._corrections_detected = 0
        self._total_processed = 0
        if self.state_file.exists():
            self.state_file.unlink()

    @property
    def stats(self) -> dict:
        return {
            "buffer_size": len(self.buffer),
            "buffer_capacity": self.buffer_size,
            "corrections_detected": self._corrections_detected,
            "total_processed": self._total_processed,
            "recent_errors": sum(1 for e in self.buffer if e.is_error),
        }
