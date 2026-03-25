#!/usr/bin/env python3
"""scan_scheduler.py — MT-40 Phase 1: Automated Nuclear Scanning Loop.

Determines which subreddits need scanning based on staleness policies.
Reads scan_registry.json to check last-scan timestamps, compares against
per-subreddit freshness policies, and recommends what to scan next.

Usage:
    python3 scan_scheduler.py                    # Show scan recommendation
    python3 scan_scheduler.py --json             # JSON output
    python3 scan_scheduler.py --registry PATH    # Custom registry path

Stdlib only. No external dependencies. One file = one job.
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REGISTRY = os.path.join(SCRIPT_DIR, "reddit-intelligence", "scan_registry.json")

# Per-subreddit scan policies: max_age_days = how stale before triggering rescan,
# priority = weight for urgency ranking (higher = scan sooner when stale).
SCAN_POLICIES: dict[str, dict] = {
    "claudecode": {"max_age_days": 3, "priority": 10},
    "claudeai": {"max_age_days": 5, "priority": 8},
    "vibecoding": {"max_age_days": 5, "priority": 6},
}

NEVER_SCANNED_DAYS = 999


@dataclass
class SubStaleness:
    """Tracks how stale a subreddit's last scan is."""
    slug: str
    days_since_scan: int
    max_age_days: int
    priority: int

    @property
    def is_stale(self) -> bool:
        return self.days_since_scan > self.max_age_days

    @property
    def days_overdue(self) -> int:
        return max(0, self.days_since_scan - self.max_age_days)

    @property
    def urgency(self) -> float:
        if not self.is_stale:
            return 0.0
        return self.priority * (self.days_overdue / self.max_age_days)


@dataclass
class ScanRecommendation:
    """Result of scan scheduling — what to scan and why."""
    action: str  # "SCAN_NOW" or "OK"
    stale_subs: list[SubStaleness]

    @property
    def top_target(self) -> Optional[str]:
        if self.stale_subs:
            return self.stale_subs[0].slug
        return None

    def format_brief(self) -> str:
        if self.action == "OK":
            return "OK — All subreddits are fresh. No scan needed."
        lines = [f"SCAN_NOW — {len(self.stale_subs)} subreddit(s) need scanning:"]
        for s in self.stale_subs:
            lines.append(
                f"  {s.slug}: {s.days_overdue}d overdue "
                f"(last scan {s.days_since_scan}d ago, max {s.max_age_days}d)"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "top_target": self.top_target,
            "stale_count": len(self.stale_subs),
            "stale_subs": [
                {"slug": s.slug, "days_overdue": s.days_overdue, "urgency": round(s.urgency, 2)}
                for s in self.stale_subs
            ],
        }


class ScanScheduler:
    """Determines which subreddits need scanning based on staleness policies."""

    def __init__(self, registry_data: Optional[dict] = None):
        self.registry_data = registry_data or {}

    @classmethod
    def from_registry_file(cls, path: str = DEFAULT_REGISTRY) -> "ScanScheduler":
        if not os.path.exists(path):
            return cls(registry_data={})
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(registry_data=data)
        except (json.JSONDecodeError, OSError):
            return cls(registry_data={})

    def _compute_staleness(self, slug: str, policy: dict) -> SubStaleness:
        now = datetime.now(timezone.utc)
        entry = self.registry_data.get(slug)
        if entry and "last_scan" in entry:
            try:
                last_scan = datetime.fromisoformat(entry["last_scan"])
                days_since = (now - last_scan).days
            except (ValueError, TypeError):
                days_since = NEVER_SCANNED_DAYS
        else:
            days_since = NEVER_SCANNED_DAYS

        return SubStaleness(
            slug=slug,
            days_since_scan=days_since,
            max_age_days=policy["max_age_days"],
            priority=policy["priority"],
        )

    def should_auto_scan(self) -> dict:
        """Check if an auto-scan should be triggered. Returns dict for easy consumption.

        Returns:
            {"should_scan": bool, "top_target": str|None, "stale_count": int, "all_targets": list[str]}
        """
        rec = self.recommend()
        return {
            "should_scan": rec.action == "SCAN_NOW",
            "top_target": rec.top_target,
            "stale_count": len(rec.stale_subs),
            "all_targets": [s.slug for s in rec.stale_subs],
        }

    def scan_command(self, slug: str, limit: int = 25, period: str = "week") -> str:
        """Generate the shell command to scan a subreddit.

        Returns the full command string ready for subprocess or os.system().
        """
        fetcher = os.path.join(SCRIPT_DIR, "reddit-intelligence", "nuclear_fetcher.py")
        findings = os.path.join(SCRIPT_DIR, "FINDINGS_LOG.md")
        return (
            f"python3 {fetcher} {slug} {limit} {period} "
            f"--classify --hot --rising --dedup {findings}"
        )

    def recommend(self) -> ScanRecommendation:
        staleness_list = []
        for slug, policy in SCAN_POLICIES.items():
            s = self._compute_staleness(slug, policy)
            if s.is_stale:
                staleness_list.append(s)

        # Sort by urgency descending
        staleness_list.sort(key=lambda s: s.urgency, reverse=True)

        action = "SCAN_NOW" if staleness_list else "OK"
        return ScanRecommendation(action=action, stale_subs=staleness_list)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MT-40: Scan Scheduler")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="Path to scan_registry.json")
    args = parser.parse_args()

    sched = ScanScheduler.from_registry_file(args.registry)
    rec = sched.recommend()

    if args.json:
        print(json.dumps(rec.to_dict(), indent=2))
    else:
        print(rec.format_brief())


if __name__ == "__main__":
    main()
