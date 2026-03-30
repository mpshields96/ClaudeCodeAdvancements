"""
Loop Detector — Catches autonomous agents stuck in repetitive cycles.

Maintains a ring buffer of recent tool outputs and uses difflib SequenceMatcher
to detect when consecutive outputs are suspiciously similar — a sign the agent
is stuck in a loop (retrying the same failing command, re-reading the same file,
making the same edit repeatedly, etc).

This is v1: string similarity only, no embeddings. Embedding-based similarity
is a v2 enhancement if this proves the concept.

Design inspired by Octopoda's loop detection pattern (FINDINGS_LOG entry #38),
adapted to work as a lightweight PostToolUse hook with zero dependencies beyond
stdlib.

Usage:
    detector = LoopDetector(window=5, threshold=0.80, min_consecutive=3)
    detector.add("tool output text here")
    result = detector.check()
    if result.is_loop:
        print(f"Loop detected: {result.description}")
"""

import hashlib
import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_WINDOW = 8          # Number of recent outputs to keep
DEFAULT_THRESHOLD = 0.80    # Similarity ratio to consider "same" (0.0-1.0)
DEFAULT_MIN_CONSECUTIVE = 3 # How many consecutive similar outputs = loop
DEFAULT_STATE_FILE = Path.home() / ".claude-loop-detector.json"

# Maximum output size to compare (truncate longer outputs to save CPU)
MAX_COMPARE_LENGTH = 4000

# Tool names that are expected to produce similar output (don't flag these)
EXEMPT_TOOLS = frozenset({
    "TodoWrite",      # Task list updates are naturally repetitive
    "AskUserQuestion", # Prompts may repeat while waiting
})


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LoopEntry:
    """A single tool output stored in the ring buffer."""
    tool_name: str
    output_hash: str       # SHA-256 of full output (for exact-match fast path)
    output_preview: str    # First MAX_COMPARE_LENGTH chars for similarity
    timestamp: float
    similarity_to_prev: float = 0.0  # Similarity to the previous entry


@dataclass
class LoopCheckResult:
    """Result of checking for a loop."""
    is_loop: bool
    consecutive_similar: int  # How many recent outputs are similar
    avg_similarity: float     # Average similarity across the similar run
    description: str          # Human-readable description
    tool_name: str = ""       # Which tool is looping
    recommendation: str = ""  # What to do about it


# ---------------------------------------------------------------------------
# Core detector
# ---------------------------------------------------------------------------

class LoopDetector:
    """
    Detects repetitive tool output patterns in autonomous sessions.

    Maintains a ring buffer of recent tool outputs. After each new output,
    checks whether the last N outputs are suspiciously similar using
    difflib.SequenceMatcher.

    Two detection modes:
    1. Exact match: SHA-256 hash comparison (instant, catches identical repeats)
    2. Fuzzy match: SequenceMatcher ratio (catches near-identical repeats like
       the same error with slightly different timestamps)
    """

    def __init__(
        self,
        window: int = DEFAULT_WINDOW,
        threshold: float = DEFAULT_THRESHOLD,
        min_consecutive: int = DEFAULT_MIN_CONSECUTIVE,
        state_file: Optional[Path] = None,
        exempt_tools: Optional[frozenset] = None,
    ):
        self.window = window
        self.threshold = threshold
        self.min_consecutive = min_consecutive
        self.state_file = state_file or DEFAULT_STATE_FILE
        self.exempt_tools = exempt_tools if exempt_tools is not None else EXEMPT_TOOLS
        self.buffer: deque[LoopEntry] = deque(maxlen=window)
        self._total_checks = 0
        self._loops_detected = 0

    def add(self, output: str, tool_name: str = "") -> None:
        """Add a new tool output to the ring buffer."""
        output_hash = hashlib.sha256(output.encode("utf-8", errors="replace")).hexdigest()
        preview = output[:MAX_COMPARE_LENGTH]

        # Calculate similarity to previous entry
        sim = 0.0
        if self.buffer:
            prev = self.buffer[-1]
            if output_hash == prev.output_hash:
                sim = 1.0  # Exact match — skip expensive SequenceMatcher
            else:
                sim = SequenceMatcher(
                    None, prev.output_preview, preview
                ).ratio()

        entry = LoopEntry(
            tool_name=tool_name,
            output_hash=output_hash,
            output_preview=preview,
            timestamp=time.time(),
            similarity_to_prev=sim,
        )
        self.buffer.append(entry)

    def check(self) -> LoopCheckResult:
        """
        Check whether recent outputs indicate a loop.

        Returns a LoopCheckResult with is_loop=True if the last
        min_consecutive outputs are all above the similarity threshold.
        """
        self._total_checks += 1

        if len(self.buffer) < self.min_consecutive:
            return LoopCheckResult(
                is_loop=False,
                consecutive_similar=0,
                avg_similarity=0.0,
                description="Not enough data yet",
            )

        # Check if the latest tool is exempt
        latest = self.buffer[-1]
        if latest.tool_name in self.exempt_tools:
            return LoopCheckResult(
                is_loop=False,
                consecutive_similar=0,
                avg_similarity=0.0,
                description=f"Tool '{latest.tool_name}' is exempt from loop detection",
            )

        # Count consecutive similar outputs from the end
        consecutive = 0
        total_sim = 0.0
        entries = list(self.buffer)

        for i in range(len(entries) - 1, 0, -1):
            sim = entries[i].similarity_to_prev
            if sim >= self.threshold:
                consecutive += 1
                total_sim += sim
            else:
                break

        avg_sim = total_sim / consecutive if consecutive > 0 else 0.0
        is_loop = consecutive >= self.min_consecutive

        if is_loop:
            self._loops_detected += 1
            tool = latest.tool_name or "unknown"
            desc = (
                f"Loop detected: {consecutive} consecutive outputs "
                f"with {avg_sim:.0%} average similarity (tool: {tool})"
            )
            recommendation = (
                "The agent appears stuck in a repetitive cycle. "
                "Consider: (1) trying a different approach, "
                "(2) reading error messages more carefully, "
                "(3) asking the user for guidance."
            )
        else:
            desc = f"{consecutive} similar outputs (need {self.min_consecutive} to trigger)"
            recommendation = ""

        return LoopCheckResult(
            is_loop=is_loop,
            consecutive_similar=consecutive,
            avg_similarity=avg_sim,
            description=desc,
            tool_name=latest.tool_name,
            recommendation=recommendation,
        )

    def save_state(self) -> None:
        """Persist detector state to disk for cross-invocation continuity."""
        state = {
            "buffer": [
                {
                    "tool_name": e.tool_name,
                    "output_hash": e.output_hash,
                    "output_preview": e.output_preview,
                    "timestamp": e.timestamp,
                    "similarity_to_prev": e.similarity_to_prev,
                }
                for e in self.buffer
            ],
            "total_checks": self._total_checks,
            "loops_detected": self._loops_detected,
            "config": {
                "window": self.window,
                "threshold": self.threshold,
                "min_consecutive": self.min_consecutive,
            },
        }
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2))
        tmp.rename(self.state_file)

    def load_state(self) -> bool:
        """Load detector state from disk. Returns True if state was loaded."""
        if not self.state_file.exists():
            return False
        try:
            state = json.loads(self.state_file.read_text())
            self.buffer.clear()
            for entry_data in state.get("buffer", []):
                self.buffer.append(LoopEntry(
                    tool_name=entry_data["tool_name"],
                    output_hash=entry_data["output_hash"],
                    output_preview=entry_data["output_preview"],
                    timestamp=entry_data["timestamp"],
                    similarity_to_prev=entry_data.get("similarity_to_prev", 0.0),
                ))
            self._total_checks = state.get("total_checks", 0)
            self._loops_detected = state.get("loops_detected", 0)
            return True
        except (json.JSONDecodeError, KeyError, TypeError):
            return False

    def reset(self) -> None:
        """Clear the buffer and state file."""
        self.buffer.clear()
        self._total_checks = 0
        self._loops_detected = 0
        if self.state_file.exists():
            self.state_file.unlink()

    @property
    def stats(self) -> dict:
        """Return detector statistics."""
        return {
            "buffer_size": len(self.buffer),
            "buffer_capacity": self.window,
            "total_checks": self._total_checks,
            "loops_detected": self._loops_detected,
            "threshold": self.threshold,
            "min_consecutive": self.min_consecutive,
        }
