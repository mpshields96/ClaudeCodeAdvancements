#!/usr/bin/env python3
"""
auto_wrap.py — Automatic session wrap-up trigger for /cca-auto.

Reads context health state (from meter.py) and tracks compaction events
to determine when a session should wrap up to maintain output quality.

Wrap triggers (any one is sufficient):
1. Context zone is red or critical
2. Compaction count exceeds threshold (default: 2)
3. Token count exceeds quality ceiling (default: 400k)

This module is called between tasks by /cca-auto to objectively decide
when to trigger /cca-wrap instead of continuing work.

Usage as library:
    from auto_wrap import AutoWrapMonitor
    monitor = AutoWrapMonitor()
    decision = monitor.check()
    if decision.should_wrap:
        # trigger /cca-wrap

Usage as CLI:
    python3 auto_wrap.py check       # Check if wrap is needed
    python3 auto_wrap.py status      # Show current state
    python3 auto_wrap.py compact     # Record a compaction event

Stdlib only. No external dependencies.
"""

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path


# ── WrapDecision ──────────────────────────────────────────────────────────────


@dataclass
class WrapDecision:
    """Result of checking whether to wrap up the session."""
    should_wrap: bool = False
    reason: str = ""
    urgency: str = "none"  # none, normal, high, critical
    context_pct: float = 0.0
    zone: str = "unknown"
    tokens: int = 0
    compaction_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ── AutoWrapMonitor ───────────────────────────────────────────────────────────

# Default quality ceiling: 400k tokens.
# Community-validated: quality degrades significantly above this.
# Red zone ceiling from context-monitor research.
_DEFAULT_TOKEN_CEILING = 400_000

# Default max compactions before wrap.
# >1 compaction means context has been compressed twice — quality risk.
_DEFAULT_MAX_COMPACTIONS = 2


class AutoWrapMonitor:
    """
    Monitors session health and decides when to trigger wrap-up.

    Reads:
      - Context health state file (from meter.py PostToolUse hook)
      - Internal wrap state (compaction count, tracked separately)

    Triggers wrap when:
      1. Context zone is red or critical
      2. Compaction count >= max_compactions
      3. Token count >= token_quality_ceiling
    """

    def __init__(
        self,
        context_state_path: str = None,
        wrap_state_path: str = None,
        token_quality_ceiling: int = _DEFAULT_TOKEN_CEILING,
        max_compactions: int = _DEFAULT_MAX_COMPACTIONS,
    ):
        self.context_state_path = context_state_path or str(
            Path.home() / ".claude-context-health.json"
        )
        self.wrap_state_path = wrap_state_path or str(
            Path.home() / ".cca-wrap-state.json"
        )
        self.token_quality_ceiling = token_quality_ceiling
        self.max_compactions = max_compactions

        # Internal state
        self.compaction_count = 0
        self._load_wrap_state()

    def _load_wrap_state(self):
        if os.path.exists(self.wrap_state_path):
            try:
                with open(self.wrap_state_path) as f:
                    data = json.load(f)
                self.compaction_count = data.get("compaction_count", 0)
            except (json.JSONDecodeError, OSError):
                pass

    def save_state(self):
        state = {
            "compaction_count": self.compaction_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.wrap_state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, self.wrap_state_path)

    def _read_context_state(self) -> dict:
        """Read the context health state file written by meter.py."""
        if not os.path.exists(self.context_state_path):
            return {}
        try:
            with open(self.context_state_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def record_compaction(self):
        """Record that a context compaction event occurred."""
        self.compaction_count += 1
        self.save_state()

    def reset(self):
        """Reset wrap state (for new sessions)."""
        self.compaction_count = 0
        self.save_state()

    def check(self) -> WrapDecision:
        """
        Check all wrap triggers and return a decision.

        Triggers (any one = wrap):
        1. Zone is red or critical
        2. Compaction count >= max_compactions
        3. Tokens >= token_quality_ceiling
        """
        ctx = self._read_context_state()
        pct = ctx.get("pct", 0.0)
        zone = ctx.get("zone", "unknown")
        tokens = ctx.get("tokens", 0)

        decision = WrapDecision(
            context_pct=pct,
            zone=zone,
            tokens=tokens,
            compaction_count=self.compaction_count,
        )

        # Trigger 1: Critical zone — urgent wrap
        if zone == "critical":
            decision.should_wrap = True
            decision.reason = f"Context in critical zone ({pct:.0f}%). Wrap immediately to preserve quality."
            decision.urgency = "critical"
            return decision

        # Trigger 2: Red zone — high urgency wrap
        if zone == "red":
            decision.should_wrap = True
            decision.reason = f"Context in red zone ({pct:.0f}%). Quality is degrading — wrap and start fresh."
            decision.urgency = "high"
            return decision

        # Trigger 3: Compaction count exceeded
        if self.compaction_count >= self.max_compactions:
            decision.should_wrap = True
            decision.reason = (
                f"Context compacted {self.compaction_count} times. "
                f"Multiple compactions cause instruction amnesia — wrap and start fresh."
            )
            decision.urgency = "high"
            return decision

        # Trigger 4: Token count exceeds quality ceiling
        if tokens >= self.token_quality_ceiling:
            decision.should_wrap = True
            decision.reason = (
                f"Token count ({tokens:,}) exceeds quality ceiling ({self.token_quality_ceiling:,}). "
                f"Output quality degrades beyond this point — wrap and start fresh."
            )
            decision.urgency = "normal"
            return decision

        return decision


# ── CLI ───────────────────────────────────────────────────────────────────────


def cli_main(args: list = None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args:
        print("Usage: python3 auto_wrap.py [check|status|compact|reset]")
        return

    cmd = args[0]

    # Parse flags
    state_path = None
    wrap_state_path = None
    i = 1
    while i < len(args):
        if args[i] == "--state" and i + 1 < len(args):
            state_path = args[i + 1]
            i += 2
        elif args[i] == "--wrap-state" and i + 1 < len(args):
            wrap_state_path = args[i + 1]
            i += 2
        else:
            i += 1

    monitor = AutoWrapMonitor(
        context_state_path=state_path,
        wrap_state_path=wrap_state_path,
    )

    if cmd == "check":
        decision = monitor.check()
        if decision.should_wrap:
            print(f"WRAP NEEDED ({decision.urgency}): {decision.reason}")
        else:
            print(f"No wrap needed. Zone: {decision.zone}, "
                  f"Tokens: {decision.tokens:,}, "
                  f"Compactions: {decision.compaction_count}")

    elif cmd == "status":
        ctx = monitor._read_context_state()
        print(f"Context health: {ctx.get('zone', 'unknown')} ({ctx.get('pct', 0):.0f}%)")
        print(f"Tokens: {ctx.get('tokens', 0):,} / {ctx.get('window', 200000):,}")
        print(f"Compaction count: {monitor.compaction_count}")
        print(f"Max compactions before wrap: {monitor.max_compactions}")
        print(f"Token quality ceiling: {monitor.token_quality_ceiling:,}")

    elif cmd == "compact":
        monitor.record_compaction()
        print(f"Compaction recorded. Count: {monitor.compaction_count}")

    elif cmd == "reset":
        monitor.reset()
        print("Wrap state reset.")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    cli_main()
