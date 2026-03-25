#!/usr/bin/env python3
"""scan_executor.py — MT-40 Phase 4: Automated Scan Pipeline.

Orchestrates the full nuclear scan cycle:
1. Check subreddit staleness via scan_scheduler
2. Generate scan commands for stale subs
3. Execute scans (or return commands for Claude to execute)
4. Update scan_registry.json with timestamps
5. Run mt_originator to detect uncovered BUILD findings

This is the "wiring" that connects scan_scheduler + nuclear_fetcher +
mt_originator into a single automated pipeline for /cca-auto.

Usage:
    python3 scan_executor.py check              # Check if scan needed
    python3 scan_executor.py commands            # Show commands to run
    python3 scan_executor.py update <slug> <N>   # Update registry after scan

Stdlib only. No external dependencies. One file = one job.

S162 — MT-40 Phase 4: Wire auto-trigger into /cca-auto.
"""

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REGISTRY = os.path.join(SCRIPT_DIR, "reddit-intelligence", "scan_registry.json")
DEFAULT_FINDINGS = os.path.join(SCRIPT_DIR, "FINDINGS_LOG.md")

# Import scan_scheduler for staleness checking
sys.path.insert(0, SCRIPT_DIR)
from scan_scheduler import ScanScheduler, SCAN_POLICIES


@dataclass
class ScanResult:
    """Result of scanning one subreddit."""
    slug: str
    posts_fetched: int = 0
    new_findings: int = 0
    mt_proposals: int = 0
    scan_command: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


class ScanExecutor:
    """Orchestrates the full nuclear scan pipeline."""

    def __init__(
        self,
        registry_path: str = DEFAULT_REGISTRY,
        findings_path: str = DEFAULT_FINDINGS,
        max_scans_per_run: int = 3,
    ):
        self.registry_path = registry_path
        self.findings_path = findings_path
        self.max_scans_per_run = max_scans_per_run
        self._scheduler = ScanScheduler.from_registry_file(registry_path)

    def check_staleness(self) -> dict:
        """Check if any subreddits need scanning. Returns scan_scheduler output."""
        return self._scheduler.should_auto_scan()

    def generate_scan_commands(self) -> list[dict]:
        """Generate shell commands for stale subreddits.

        Returns list of {"slug": str, "command": str} dicts, ordered by urgency.
        """
        staleness = self.check_staleness()
        if not staleness["should_scan"]:
            return []

        commands = []
        targets = staleness["all_targets"][:self.max_scans_per_run]
        for slug in targets:
            cmd = self._scheduler.scan_command(slug)
            commands.append({"slug": slug, "command": cmd})
        return commands

    def update_registry(self, slug: str, posts_fetched: int = 0) -> None:
        """Update scan_registry.json after a scan completes."""
        registry = {}
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r") as f:
                    registry = json.load(f)
            except (json.JSONDecodeError, OSError):
                registry = {}

        registry[slug] = {
            "last_scan": datetime.now(timezone.utc).isoformat(),
            "posts_fetched": posts_fetched,
        }

        with open(self.registry_path, "w") as f:
            json.dump(registry, f, indent=2)

    def format_brief(self, results: list[ScanResult]) -> str:
        """Format scan results into a brief summary."""
        if not results:
            return "No scans executed."

        lines = [f"Scan complete — {len(results)} subreddit(s):"]
        for r in results:
            if r.error:
                lines.append(f"  {r.slug}: ERROR — {r.error}")
            else:
                parts = [f"{r.posts_fetched} posts"]
                if r.new_findings:
                    parts.append(f"{r.new_findings} findings")
                if r.mt_proposals:
                    parts.append(f"{r.mt_proposals} MT proposals")
                lines.append(f"  {r.slug}: {', '.join(parts)}")
        return "\n".join(lines)


# ── Convenience Functions ─────────────────────────────────────────────────

def should_scan_now(registry_path: str = DEFAULT_REGISTRY) -> bool:
    """Quick check: does any subreddit need scanning?"""
    scheduler = ScanScheduler.from_registry_file(registry_path)
    result = scheduler.should_auto_scan()
    return result["should_scan"]


def run_auto_scan(
    registry_path: str = DEFAULT_REGISTRY,
    findings_path: str = DEFAULT_FINDINGS,
    max_scans: int = 3,
) -> list[dict]:
    """Get scan commands for stale subs. Returns list of {slug, command} dicts.

    Designed for /cca-auto to call and then execute the commands.
    """
    ex = ScanExecutor(
        registry_path=registry_path,
        findings_path=findings_path,
        max_scans_per_run=max_scans,
    )
    return ex.generate_scan_commands()


def main():
    if len(sys.argv) < 2:
        print("Usage: scan_executor.py [check|commands|update <slug> <posts>]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "check":
        ex = ScanExecutor()
        result = ex.check_staleness()
        if result["should_scan"]:
            print(f"SCAN NEEDED — {result['stale_count']} stale sub(s): {', '.join(result['all_targets'])}")
        else:
            print("All subreddits are fresh. No scan needed.")

    elif cmd == "commands":
        ex = ScanExecutor()
        commands = ex.generate_scan_commands()
        if not commands:
            print("No scans needed.")
        else:
            for c in commands:
                print(f"[{c['slug']}] {c['command']}")

    elif cmd == "update":
        if len(sys.argv) < 3:
            print("Usage: scan_executor.py update <slug> [posts_count]")
            sys.exit(1)
        slug = sys.argv[2]
        posts = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        ex = ScanExecutor()
        ex.update_registry(slug, posts)
        print(f"Updated registry: {slug} scanned ({posts} posts)")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
