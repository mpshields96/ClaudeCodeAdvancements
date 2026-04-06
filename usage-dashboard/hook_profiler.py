#!/usr/bin/env python3
"""
Hook Chain Profiler — Measures execution time of all configured hooks.

Problem: CCA has 14 hooks firing on tool calls. If any hook is slow,
it silently degrades every operation. This tool measures each hook's
latency with realistic payloads and reports results.

Usage:
    python3 usage-dashboard/hook_profiler.py              # Run all hooks once
    python3 usage-dashboard/hook_profiler.py --repeat 5   # Average over 5 runs
    python3 usage-dashboard/hook_profiler.py --slow 50    # Only show hooks >50ms

Stdlib only. No external dependencies.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Data Types ──────────────────────────────────────────────────────────────

@dataclass
class HookResult:
    path: str
    event: str
    times_ms: list[float] = field(default_factory=list)
    error: str | None = None

    @property
    def avg_ms(self) -> float:
        return sum(self.times_ms) / len(self.times_ms) if self.times_ms else 0.0

    @property
    def min_ms(self) -> float:
        return min(self.times_ms) if self.times_ms else 0.0

    @property
    def max_ms(self) -> float:
        return max(self.times_ms) if self.times_ms else 0.0


# ── Hook Discovery ─────────────────────────────────────────────────────────

def load_hooks_from_settings(settings_path: str | None = None) -> list[tuple[str, str, str]]:
    """
    Parse settings.local.json and return list of (event, matcher, command).
    """
    if settings_path is None:
        settings_path = str(
            Path(__file__).resolve().parent.parent / ".claude" / "settings.local.json"
        )

    try:
        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    hooks_config = settings.get("hooks", {})
    result = []

    for event_name, entries in hooks_config.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            matcher = entry.get("matcher", "")
            for hook in entry.get("hooks", []):
                if hook.get("type") == "command":
                    cmd = hook.get("command", "")
                    if cmd:
                        result.append((event_name, matcher, cmd))

    return result


# ── Payload Generation ─────────────────────────────────────────────────────

def _make_payload(event: str, matcher: str) -> str:
    """Generate a realistic hook payload for the given event type."""
    base = {
        "hook_event_name": event,
        "cwd": "/tmp/test-project",
        "session_id": "test-session-001",
    }

    if event == "PreToolUse":
        tool = matcher if matcher else "Read"
        base["tool_name"] = tool
        base["tool_input"] = {"file_path": "/tmp/test-project/main.py"}
    elif event == "PostToolUse":
        base["tool_name"] = "Read"
        base["tool_input"] = {"file_path": "/tmp/test-project/main.py"}
        base["tool_output"] = "# file contents here"
    elif event == "UserPromptSubmit":
        base["user_prompt"] = "Fix the bug in main.py"
    elif event == "Stop":
        base["stop_reason"] = "end_turn"
        base["last_assistant_message"] = "I fixed the bug in main.py by adding a null check."
    elif event == "PostCompact":
        base["compact_summary"] = "Context was compacted at 85% usage."

    return json.dumps(base)


# ── Profiling ──────────────────────────────────────────────────────────────

def profile_hook(command: str, payload: str, timeout: float = 5.0) -> tuple[float, str | None]:
    """
    Run a single hook with the given payload and return (elapsed_ms, error).
    """
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            command.split(),
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = (time.monotonic() - t0) * 1000
        if result.returncode != 0 and result.stderr:
            return elapsed, result.stderr.strip()[:200]
        return elapsed, None
    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - t0) * 1000
        return elapsed, "TIMEOUT"
    except Exception as e:
        elapsed = (time.monotonic() - t0) * 1000
        return elapsed, str(e)[:200]


def profile_all(
    settings_path: str | None = None,
    repeat: int = 1,
    slow_threshold_ms: float = 0.0,
) -> list[HookResult]:
    """
    Profile all hooks from settings and return results.
    """
    hooks = load_hooks_from_settings(settings_path)
    results = []

    for event, matcher, command in hooks:
        # Extract just the script path for display
        parts = command.split()
        script = parts[-1] if parts else command
        display_path = str(Path(script).relative_to(Path(script).parents[1])) if len(Path(script).parts) > 2 else script

        hr = HookResult(path=display_path, event=f"{event}({matcher or '*'})")
        payload = _make_payload(event, matcher)

        for _ in range(repeat):
            elapsed, error = profile_hook(command, payload)
            hr.times_ms.append(elapsed)
            if error:
                hr.error = error

        if slow_threshold_ms <= 0 or hr.avg_ms >= slow_threshold_ms:
            results.append(hr)

    return results


# ── Chain Analysis ─────────────────────────────────────────────────────────

def chain_overhead(results: list[HookResult]) -> dict[str, float]:
    """
    Calculate total overhead per event type (hooks run sequentially per event).
    """
    overhead = {}
    for r in results:
        event = r.event.split("(")[0]
        overhead[event] = overhead.get(event, 0.0) + r.avg_ms
    return overhead


# ── Display ────────────────────────────────────────────────────────────────

def format_report(results: list[HookResult], repeat: int = 1) -> str:
    """Format profiling results as a human-readable report."""
    lines = []
    lines.append("=" * 80)
    lines.append("HOOK CHAIN PROFILER REPORT")
    lines.append("=" * 80)
    lines.append("")

    if not results:
        lines.append("No hooks found or all below threshold.")
        return "\n".join(lines)

    # Per-hook table
    if repeat > 1:
        lines.append(f"{'Hook':<50} {'Event':<22} {'Avg':>7} {'Min':>7} {'Max':>7}")
    else:
        lines.append(f"{'Hook':<50} {'Event':<22} {'Time':>7}")
    lines.append("-" * 80)

    for r in results:
        status = " ERR" if r.error else ""
        if repeat > 1:
            lines.append(
                f"{r.path:<50} {r.event:<22} {r.avg_ms:>5.1f}ms {r.min_ms:>5.1f}ms {r.max_ms:>5.1f}ms{status}"
            )
        else:
            lines.append(f"{r.path:<50} {r.event:<22} {r.avg_ms:>5.1f}ms{status}")

    # Chain overhead summary
    overhead = chain_overhead(results)
    lines.append("")
    lines.append("Chain overhead (sequential per event):")
    for event, total in sorted(overhead.items()):
        lines.append(f"  {event}: {total:.1f}ms total")

    total_all = sum(overhead.values())
    lines.append(f"  ALL EVENTS: {total_all:.1f}ms worst-case")

    # Warnings
    lines.append("")
    slow = [r for r in results if r.avg_ms > 100]
    if slow:
        lines.append("WARNING: Hooks exceeding 100ms:")
        for r in slow:
            lines.append(f"  {r.path}: {r.avg_ms:.1f}ms avg")

    errors = [r for r in results if r.error]
    if errors:
        lines.append("ERRORS:")
        for r in errors:
            lines.append(f"  {r.path}: {r.error}")

    lines.append("")
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Profile CCA hook chain latency")
    parser.add_argument("--repeat", type=int, default=1, help="Number of runs per hook (default: 1)")
    parser.add_argument("--slow", type=float, default=0, help="Only show hooks above this ms threshold")
    parser.add_argument("--settings", type=str, default=None, help="Path to settings.local.json")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of table")
    args = parser.parse_args()

    results = profile_all(
        settings_path=args.settings,
        repeat=args.repeat,
        slow_threshold_ms=args.slow,
    )

    if args.json:
        output = []
        for r in results:
            output.append({
                "hook": r.path,
                "event": r.event,
                "avg_ms": round(r.avg_ms, 1),
                "min_ms": round(r.min_ms, 1),
                "max_ms": round(r.max_ms, 1),
                "error": r.error,
            })
        print(json.dumps(output, indent=2))
    else:
        print(format_report(results, repeat=args.repeat))


if __name__ == "__main__":
    main()
