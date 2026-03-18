#!/usr/bin/env python3
"""
profiles.py — Subreddit profiles, scan registry, and quick-scan mode for MT-6.

Merges /cca-scout (quick discovery) with /cca-nuclear (deep batch review) into
a unified system with predefined settings per subreddit and scan history tracking.

Usage:
    python3 profiles.py list                    # List all builtin profiles
    python3 profiles.py info r/ClaudeCode       # Show profile details
    python3 profiles.py stale                   # Show subs due for re-scan
    python3 profiles.py history                 # Show scan history

Stdlib only. No Claude tokens consumed.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Import classify_post from nuclear_fetcher (same package)
_THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(_THIS_DIR))
from nuclear_fetcher import classify_post


# ── Subreddit Profile ────────────────────────────────────────────────────────


@dataclass
class SubredditProfile:
    """Configuration for scanning a specific subreddit."""
    subreddit: str              # Display name (e.g., "ClaudeCode")
    min_score: int = 30         # Minimum post score to include
    timeframe: str = "month"    # Reddit sort timeframe: hour/day/week/month/year/all
    limit: int = 100            # Max posts to fetch
    extra_needle_keywords: list = field(default_factory=list)  # Additional NEEDLE keywords
    domain: str = "unknown"     # Category: claude, trading, dev, research
    needle_ratio_cap: float = 0.6  # Max fraction of posts that can be NEEDLE (0.0-1.0, default 60%)


# ── Builtin Profiles ─────────────────────────────────────────────────────────

BUILTIN_PROFILES = {
    "claudecode": SubredditProfile(
        subreddit="ClaudeCode",
        min_score=30,
        timeframe="month",
        limit=150,
        extra_needle_keywords=["claude.md", "hook", "mcp", "slash command", "statusline"],
        domain="claude",
    ),
    "claudeai": SubredditProfile(
        subreddit="ClaudeAI",
        min_score=40,
        timeframe="month",
        limit=100,
        extra_needle_keywords=["claude code", "hook", "mcp", "slash command", "memory", "context window", "agent", "workflow", "automation"],
        domain="claude",
        needle_ratio_cap=0.4,  # r/ClaudeAI is ~60% noise (memes, praise, politics) — cap at 40%
    ),
    "vibecoding": SubredditProfile(
        subreddit="vibecoding",
        min_score=20,
        timeframe="month",
        limit=75,
        extra_needle_keywords=["workflow", "automation", "agent", "cursor", "windsurf"],
        domain="claude",
    ),
    "localllama": SubredditProfile(
        subreddit="LocalLLaMA",
        min_score=50,
        timeframe="month",
        limit=100,
        extra_needle_keywords=["agent", "tool use", "function calling", "coding", "benchmark"],
        domain="research",
        needle_ratio_cap=0.4,  # Broad keywords saturate — cap at 40%
    ),
    "machinelearning": SubredditProfile(
        subreddit="MachineLearning",
        min_score=50,
        timeframe="month",
        limit=75,
        extra_needle_keywords=["agent", "llm", "transformer", "benchmark", "paper"],
        domain="research",
    ),
    "algotrading": SubredditProfile(
        subreddit="algotrading",
        min_score=30,
        timeframe="month",
        limit=100,
        extra_needle_keywords=[
            "prediction market", "kalshi", "polymarket", "bot", "api",
            "backtesting", "strategy", "edge", "signal",
        ],
        domain="trading",
    ),
    "kalshi": SubredditProfile(
        subreddit="Kalshi",
        min_score=10,
        timeframe="month",
        limit=50,
        extra_needle_keywords=["api", "bot", "strategy", "arbitrage", "market maker"],
        domain="trading",
    ),
    "polymarket": SubredditProfile(
        subreddit="polymarket",
        min_score=15,
        timeframe="month",
        limit=50,
        extra_needle_keywords=["api", "bot", "strategy", "arbitrage", "edge"],
        domain="trading",
    ),
    "webdev": SubredditProfile(
        subreddit="webdev",
        min_score=50,
        timeframe="month",
        limit=75,
        extra_needle_keywords=["ai", "claude", "copilot", "automation", "workflow"],
        domain="dev",
    ),
    "iosprogramming": SubredditProfile(
        subreddit="iOSProgramming",
        min_score=20,
        timeframe="month",
        limit=50,
        extra_needle_keywords=["swiftui", "xcode", "claude", "ai", "automation"],
        domain="dev",
    ),
    # Investing/stocks — added per Matthew's directive (Session 28)
    "investing": SubredditProfile(
        subreddit="investing",
        min_score=40,
        timeframe="month",
        limit=75,
        extra_needle_keywords=[
            "strategy", "portfolio", "etf", "index", "dividend",
            "factor", "risk", "allocation", "rebalancing", "automation",
        ],
        domain="trading",
        needle_ratio_cap=0.35,  # Very broad keywords — cap tightly
    ),
    "stocks": SubredditProfile(
        subreddit="stocks",
        min_score=50,
        timeframe="month",
        limit=75,
        extra_needle_keywords=[
            "analysis", "screener", "automation", "api", "backtesting",
            "fundamental", "technical", "quantitative",
        ],
        domain="trading",
        needle_ratio_cap=0.35,
    ),
    "securityanalysis": SubredditProfile(
        subreddit="SecurityAnalysis",
        min_score=20,
        timeframe="month",
        limit=50,
        extra_needle_keywords=[
            "valuation", "dcf", "moat", "margin of safety", "earnings",
            "10-k", "annual report", "factor", "quant",
        ],
        domain="trading",
    ),
    "valueinvesting": SubredditProfile(
        subreddit="ValueInvesting",
        min_score=30,
        timeframe="month",
        limit=50,
        extra_needle_keywords=[
            "intrinsic value", "dcf", "margin of safety", "screener",
            "dividend", "moat", "buffett", "graham",
        ],
        domain="trading",
    ),
    "bogleheads": SubredditProfile(
        subreddit="Bogleheads",
        min_score=30,
        timeframe="month",
        limit=50,
        extra_needle_keywords=[
            "index fund", "three-fund", "allocation", "rebalancing",
            "tax-loss harvesting", "automation", "vanguard",
        ],
        domain="trading",
    ),
    # AI agent/framework subs — added per Matthew's directive (Session 45)
    "autogpt": SubredditProfile(
        subreddit="AutoGPT",
        min_score=20,
        timeframe="month",
        limit=75,
        extra_needle_keywords=[
            "agent", "autonomous", "workflow", "tool use", "memory",
            "planning", "self-improvement", "loop", "benchmark",
        ],
        domain="research",
        needle_ratio_cap=0.5,
    ),
    "langchain": SubredditProfile(
        subreddit="LangChain",
        min_score=20,
        timeframe="month",
        limit=75,
        extra_needle_keywords=[
            "agent", "tool", "chain", "rag", "memory", "graph",
            "langgraph", "workflow", "orchestration", "benchmark",
        ],
        domain="research",
        needle_ratio_cap=0.5,
    ),
}


def get_profile(subreddit_input: str) -> SubredditProfile:
    """
    Look up a profile by subreddit name, slug, or r/Name format.
    Returns a default profile for unknown subreddits.
    """
    # Normalize: strip r/ prefix, lowercase for lookup
    clean = re.sub(r"^/?r/", "", subreddit_input.strip())
    slug = re.sub(r"[^a-z0-9]", "", clean.lower())

    if slug in BUILTIN_PROFILES:
        return BUILTIN_PROFILES[slug]

    # Unknown sub — return conservative defaults
    return SubredditProfile(
        subreddit=clean,
        min_score=20,
        timeframe="month",
        limit=50,
        extra_needle_keywords=[],
        domain="unknown",
    )


# ── Scan Registry ────────────────────────────────────────────────────────────

_DEFAULT_REGISTRY_PATH = str(_THIS_DIR / "scan_registry.json")


class ScanRegistry:
    """Tracks last-scan timestamps and yield metrics per subreddit."""

    def __init__(self, path: str = _DEFAULT_REGISTRY_PATH):
        self._path = path
        self._data = {}
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self):
        tmp = self._path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self._path)

    def record_scan(self, slug: str, posts_scanned: int, builds: int, adapts: int):
        """Record that a subreddit was scanned with results."""
        self._data[slug] = {
            "last_scan": datetime.now(timezone.utc).isoformat(),
            "posts_scanned": posts_scanned,
            "builds": builds,
            "adapts": adapts,
        }
        self._save()

    def list_scans(self) -> dict:
        """Return all scan records."""
        return dict(self._data)

    def is_stale(self, slug: str, max_age_days: int = 14) -> bool:
        """True if the sub has never been scanned or was scanned > max_age_days ago."""
        if slug not in self._data:
            return True
        last = self._data[slug].get("last_scan", "")
        if not last:
            return True
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - last_dt) > timedelta(days=max_age_days)
        except (ValueError, TypeError):
            return True

    def stale_subs(self, max_age_days: int = 14) -> list:
        """Return list of slugs that are overdue for a scan."""
        return [slug for slug in self._data if self.is_stale(slug, max_age_days)]

    def yield_score(self, slug: str) -> float:
        """
        Yield score = (builds + adapts) per 100 posts scanned.
        Higher = more productive subreddit. 0 if never scanned.
        """
        if slug not in self._data:
            return 0.0
        entry = self._data[slug]
        scanned = entry.get("posts_scanned", 0)
        if scanned == 0:
            return 0.0
        builds = entry.get("builds", 0)
        adapts = entry.get("adapts", 0)
        return (builds + adapts) / scanned * 100


# ── Quick-Scan Triage ────────────────────────────────────────────────────────


def quick_scan_triage(posts: list, deep_read_count: int = 10,
                      needle_ratio_cap: float = 1.0) -> tuple:
    """
    Quick-scan mode: classify all posts, pick top N for deep reading.

    Returns (deep_read_posts, skipped_posts).
    NEEDLEs are always included (up to needle_ratio_cap). HAY is always excluded.
    Remaining slots filled by score descending from MAYBE posts.

    needle_ratio_cap: Max fraction of posts that can be NEEDLE (0.0-1.0).
        If the NEEDLE ratio exceeds this cap, the lowest-score NEEDLEs are
        demoted to MAYBE. This prevents broad keywords from saturating results.
    """
    if not posts:
        return [], []

    # Classify each post
    for p in posts:
        p["_triage"] = classify_post(p)

    needles = [p for p in posts if p["_triage"] == "NEEDLE"]
    maybes = [p for p in posts if p["_triage"] == "MAYBE"]
    hay = [p for p in posts if p["_triage"] == "HAY"]

    # Apply needle_ratio_cap: if too many NEEDLEs, demote weakest to MAYBE
    if 0 < needle_ratio_cap < 1.0 and len(posts) > 0:
        max_needles = max(1, int(len(posts) * needle_ratio_cap))
        if len(needles) > max_needles:
            # Sort by score descending — keep top max_needles, demote rest
            needles.sort(key=lambda p: p.get("score", 0), reverse=True)
            demoted = needles[max_needles:]
            needles = needles[:max_needles]
            for p in demoted:
                p["_triage"] = "MAYBE"
            maybes.extend(demoted)

    # NEEDLEs always go to deep-read
    deep = list(needles)

    # Fill remaining slots with highest-score MAYBEs
    remaining_slots = max(0, deep_read_count - len(deep))
    maybes_sorted = sorted(maybes, key=lambda p: p["score"], reverse=True)
    deep.extend(maybes_sorted[:remaining_slots])

    # Sort final deep list by score descending
    deep.sort(key=lambda p: p["score"], reverse=True)

    # Everything else is skipped
    deep_ids = {p["id"] for p in deep}
    skipped = [p for p in posts if p["id"] not in deep_ids]

    # Clean up internal key
    for p in posts:
        p.pop("_triage", None)

    return deep, skipped


# ── Merge Scout + Nuclear ────────────────────────────────────────────────────


def merge_scout_nuclear(subreddit: str, mode: str, profile: SubredditProfile) -> dict:
    """
    Generate scan parameters that merge scout (quick) and nuclear (full) capabilities.

    mode="quick": scout-like — 25-50 posts, title triage, deep-read top 5-10
    mode="full": nuclear-like — 100-150 posts, full batch review
    """
    if mode not in ("quick", "full"):
        raise ValueError(f"Invalid mode: {mode}. Must be 'quick' or 'full'.")

    if mode == "quick":
        return {
            "subreddit": subreddit,
            "mode": "quick",
            "profile_name": re.sub(r"[^a-z0-9]", "", subreddit.lower()),
            "fetch_limit": min(profile.limit, 50),
            "deep_read_count": 10,
            "min_score": profile.min_score,
            "timeframe": profile.timeframe,
            "classify": True,
            "dedup": True,
        }
    else:  # full
        return {
            "subreddit": subreddit,
            "mode": "full",
            "profile_name": re.sub(r"[^a-z0-9]", "", subreddit.lower()),
            "fetch_limit": profile.limit,
            "deep_read_count": profile.limit,  # all posts get read
            "min_score": profile.min_score,
            "timeframe": profile.timeframe,
            "classify": True,
            "dedup": True,
        }


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 profiles.py [list|info|stale|history]")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "list":
        print(f"{'Slug':<20} {'Subreddit':<20} {'Domain':<10} {'Min Score':<10} {'Limit':<6} {'Timeframe'}")
        print("-" * 85)
        for slug, p in sorted(BUILTIN_PROFILES.items()):
            print(f"{slug:<20} r/{p.subreddit:<18} {p.domain:<10} {p.min_score:<10} {p.limit:<6} {p.timeframe}")

    elif cmd == "info":
        if len(sys.argv) < 3:
            print("Usage: python3 profiles.py info <subreddit>")
            sys.exit(1)
        p = get_profile(sys.argv[2])
        print(f"Subreddit: r/{p.subreddit}")
        print(f"Domain: {p.domain}")
        print(f"Min score: {p.min_score}")
        print(f"Limit: {p.limit}")
        print(f"Timeframe: {p.timeframe}")
        if p.extra_needle_keywords:
            print(f"Extra needles: {', '.join(p.extra_needle_keywords)}")

    elif cmd == "stale":
        reg = ScanRegistry()
        stale = reg.stale_subs()
        if stale:
            print(f"Stale subs (>14 days since last scan):")
            for s in stale:
                print(f"  - {s}")
        else:
            print("No stale subs.")
        # Also show never-scanned builtin profiles
        scanned = set(reg.list_scans().keys())
        unscanned = set(BUILTIN_PROFILES.keys()) - scanned
        if unscanned:
            print(f"\nNever scanned:")
            for s in sorted(unscanned):
                print(f"  - {s} (r/{BUILTIN_PROFILES[s].subreddit})")

    elif cmd == "history":
        reg = ScanRegistry()
        scans = reg.list_scans()
        if not scans:
            print("No scan history.")
            return
        print(f"{'Slug':<20} {'Last Scan':<22} {'Posts':<7} {'BUILD':<7} {'ADAPT':<7} {'Yield'}")
        print("-" * 80)
        for slug, data in sorted(scans.items()):
            last = data.get("last_scan", "?")[:19]
            posts = data.get("posts_scanned", 0)
            builds = data.get("builds", 0)
            adapts = data.get("adapts", 0)
            yld = reg.yield_score(slug)
            print(f"{slug:<20} {last:<22} {posts:<7} {builds:<7} {adapts:<7} {yld:.1f}%")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
