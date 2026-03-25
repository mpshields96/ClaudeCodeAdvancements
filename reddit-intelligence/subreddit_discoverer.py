#!/usr/bin/env python3
"""subreddit_discoverer.py — Discover high-quality subreddits for CCA + Kalshi projects.

Searches Reddit for subreddits relevant to our project domains that we're NOT
already tracking in profiles.py. Scores candidates by subscriber count, activity,
and domain relevance. Outputs ranked proposals for new profiles.

Usage:
    python3 subreddit_discoverer.py                    # Discover across all domains
    python3 subreddit_discoverer.py --domain claude    # Single domain
    python3 subreddit_discoverer.py --domain trading   # Trading-focused
    python3 subreddit_discoverer.py --json             # JSON output
    python3 subreddit_discoverer.py --top 10           # Top N results
    python3 subreddit_discoverer.py --propose          # Generate SubredditProfile code

Stdlib only. Uses Reddit's public JSON API (no auth required).
"""

import json
import math
import os
import re
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(_THIS_DIR))

# Import existing profiles to know what we already track
from profiles import BUILTIN_PROFILES

# ── Project Domains ──────────────────────────────────────────────────────────

DOMAIN_QUERIES = {
    "claude": {
        "description": "Claude Code, AI coding assistants, LLM dev tools",
        "search_terms": [
            "claude code ai",
            "ai coding assistant",
            "llm developer tools",
            "ai pair programming",
            "copilot alternative",
            "ai code generation",
            "mcp model context protocol",
            "ai agent framework",
        ],
        "relevance_keywords": [
            "claude", "anthropic", "ai coding", "copilot", "cursor",
            "windsurf", "aider", "code generation", "llm", "mcp",
            "agent", "hook", "automation", "workflow", "prompt engineering",
        ],
    },
    "trading": {
        "description": "Prediction markets, algorithmic trading, quant finance",
        "search_terms": [
            "prediction market trading",
            "algorithmic trading bot",
            "quantitative finance",
            "sports betting analytics",
            "market making strategy",
            "kelly criterion betting",
            "bayesian trading",
            "event contract trading",
        ],
        "relevance_keywords": [
            "trading", "algorithm", "quant", "prediction", "market",
            "kalshi", "polymarket", "betting", "strategy", "backtesting",
            "kelly", "bayesian", "arbitrage", "signal", "edge",
            "portfolio", "risk management", "position sizing",
        ],
    },
    "research": {
        "description": "AI/ML research, agent architectures, self-learning systems",
        "search_terms": [
            "ai agent research",
            "reinforcement learning agent",
            "self-improving ai",
            "multi agent systems",
            "llm benchmark evaluation",
            "ai safety alignment",
            "machine learning operations",
            "autonomous coding agent",
        ],
        "relevance_keywords": [
            "agent", "research", "paper", "benchmark", "evaluation",
            "reinforcement", "self-improvement", "multi-agent", "autonomous",
            "transformer", "fine-tuning", "rag", "retrieval", "embedding",
        ],
    },
    "dev": {
        "description": "Developer tools, CLI, productivity, devops",
        "search_terms": [
            "developer productivity tools",
            "cli tools programming",
            "devops automation",
            "code review automation",
            "testing framework",
            "developer experience",
        ],
        "relevance_keywords": [
            "developer", "tool", "cli", "automation", "productivity",
            "testing", "devops", "ci/cd", "code review", "linter",
            "formatter", "ide", "terminal", "workflow",
        ],
    },
}

# ── User-Agent for Reddit API ────────────────────────────────────────────────

_USER_AGENT = "CCA-SubredditDiscoverer/1.0 (research-only; stdlib-only)"
_RATE_LIMIT_SEC = 2.0  # Be polite to Reddit API


# ── SubredditCandidate ───────────────────────────────────────────────────────


@dataclass
class SubredditCandidate:
    """A discovered subreddit candidate for potential tracking."""
    name: str
    display_name: str
    subscribers: int
    description: str
    public_description: str
    active_accounts: int  # May be 0 if not available
    created_utc: float
    url: str
    over18: bool
    domain: str  # Which project domain matched
    relevance_score: float  # 0-100
    already_tracked: bool

    def age_days(self) -> float:
        if self.created_utc <= 0:
            return 0
        return (datetime.now(timezone.utc).timestamp() - self.created_utc) / 86400

    def to_dict(self) -> dict:
        d = asdict(self)
        d["age_days"] = round(self.age_days(), 0)
        return d

    def profile_proposal(self) -> str:
        """Generate a SubredditProfile code snippet."""
        slug = re.sub(r"[^a-z0-9]", "", self.display_name.lower())
        # Pick reasonable defaults based on subscriber count
        min_score = 20 if self.subscribers < 50000 else 30 if self.subscribers < 200000 else 50
        limit = 50 if self.subscribers < 50000 else 75 if self.subscribers < 200000 else 100
        return (
            f'    "{slug}": SubredditProfile(\n'
            f'        subreddit="{self.display_name}",\n'
            f'        min_score={min_score},\n'
            f'        timeframe="month",\n'
            f'        limit={limit},\n'
            f'        extra_needle_keywords=[],  # TODO: add domain keywords\n'
            f'        domain="{self.domain}",\n'
            f"    ),"
        )


# ── Discovery Engine ─────────────────────────────────────────────────────────


def _already_tracked_slugs() -> set:
    """Get normalized slugs of all subreddits we already track."""
    tracked = set()
    for slug, profile in BUILTIN_PROFILES.items():
        tracked.add(slug)
        tracked.add(re.sub(r"[^a-z0-9]", "", profile.subreddit.lower()))
    return tracked


def _fetch_json(url: str) -> Optional[dict]:
    """Fetch JSON from Reddit's public API with rate limiting."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        return None


def _search_subreddits(query: str, limit: int = 10) -> list:
    """Search Reddit for subreddits matching a query."""
    encoded = urllib.parse.quote(query)
    url = f"https://www.reddit.com/subreddits/search.json?q={encoded}&limit={limit}&sort=relevance"
    data = _fetch_json(url)
    if not data or "data" not in data:
        return []
    return data["data"].get("children", [])


def _score_relevance(sub_data: dict, domain_keywords: list) -> float:
    """Score a subreddit's relevance to a domain (0-100)."""
    desc = (sub_data.get("public_description") or "") + " " + (sub_data.get("description") or "")
    title = sub_data.get("display_name", "") + " " + (sub_data.get("title") or "")
    text = (desc + " " + title).lower()

    # Keyword matches (0-50)
    matches = sum(1 for kw in domain_keywords if kw.lower() in text)
    keyword_score = min(50, matches * 10)

    # Subscriber score (0-25, log scale)
    subs = sub_data.get("subscribers", 0) or 0
    if subs > 0:
        sub_score = min(25, math.log10(max(1, subs)) * 5)
    else:
        sub_score = 0

    # Activity score (0-15, based on active users)
    active = sub_data.get("accounts_active", 0) or 0
    if active > 0:
        activity_score = min(15, math.log10(max(1, active)) * 5)
    else:
        activity_score = 0

    # Age penalty — very new subs (<90 days) get penalized (0-10)
    created = sub_data.get("created_utc", 0) or 0
    if created > 0:
        age_days = (datetime.now(timezone.utc).timestamp() - created) / 86400
        age_score = min(10, age_days / 36.5)  # Full score at ~1 year
    else:
        age_score = 5  # Unknown age, neutral

    return round(keyword_score + sub_score + activity_score + age_score, 1)


def discover_subreddits(
    domains: Optional[list] = None,
    top_n: int = 20,
    min_subscribers: int = 1000,
) -> list:
    """
    Discover subreddits across specified domains (or all domains).

    Returns sorted list of SubredditCandidate objects, highest relevance first.
    Deduplicates and filters out already-tracked subreddits.
    """
    if domains is None:
        domains = list(DOMAIN_QUERIES.keys())

    tracked = _already_tracked_slugs()
    seen = set()
    candidates = []

    for domain in domains:
        if domain not in DOMAIN_QUERIES:
            continue

        config = DOMAIN_QUERIES[domain]
        for query in config["search_terms"]:
            results = _search_subreddits(query, limit=10)
            time.sleep(_RATE_LIMIT_SEC)  # Rate limit

            for item in results:
                sub = item.get("data", {})
                name = sub.get("display_name", "")
                slug = re.sub(r"[^a-z0-9]", "", name.lower())

                if not name or slug in seen:
                    continue
                seen.add(slug)

                # Skip NSFW
                if sub.get("over18", False):
                    continue

                # Skip tiny subreddits
                subscribers = sub.get("subscribers", 0) or 0
                if subscribers < min_subscribers:
                    continue

                is_tracked = slug in tracked
                relevance = _score_relevance(sub, config["relevance_keywords"])

                candidates.append(SubredditCandidate(
                    name=slug,
                    display_name=name,
                    subscribers=subscribers,
                    description=(sub.get("description") or "")[:200],
                    public_description=(sub.get("public_description") or "")[:200],
                    active_accounts=sub.get("accounts_active", 0) or 0,
                    created_utc=sub.get("created_utc", 0) or 0,
                    url=f"https://www.reddit.com/r/{name}/",
                    over18=False,
                    domain=domain,
                    relevance_score=relevance,
                    already_tracked=is_tracked,
                ))

    # Sort by relevance, highest first
    candidates.sort(key=lambda c: c.relevance_score, reverse=True)
    return candidates[:top_n]


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Discover high-quality subreddits for CCA + Kalshi")
    parser.add_argument("--domain", choices=list(DOMAIN_QUERIES.keys()), help="Single domain to search")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--top", type=int, default=20, help="Number of top results")
    parser.add_argument("--min-subs", type=int, default=1000, help="Minimum subscriber count")
    parser.add_argument("--propose", action="store_true", help="Generate SubredditProfile code")
    parser.add_argument("--include-tracked", action="store_true", help="Include already-tracked subs")
    args = parser.parse_args()

    domains = [args.domain] if args.domain else None

    print(f"Searching Reddit for subreddits across {args.domain or 'all'} domains...")
    print(f"(This takes ~{len(DOMAIN_QUERIES.get(args.domain, DOMAIN_QUERIES).get('search_terms', [])) if args.domain else sum(len(v['search_terms']) for v in DOMAIN_QUERIES.values())} queries, ~2s each)\n")

    candidates = discover_subreddits(
        domains=domains,
        top_n=args.top,
        min_subscribers=args.min_subs,
    )

    if not args.include_tracked:
        candidates = [c for c in candidates if not c.already_tracked]

    if args.json:
        print(json.dumps([c.to_dict() for c in candidates], indent=2))
        return

    if not candidates:
        print("No new subreddit candidates found.")
        return

    # Pretty print
    print(f"DISCOVERED SUBREDDITS ({len(candidates)} new candidates):\n")
    for i, c in enumerate(candidates, 1):
        tracked_tag = " [ALREADY TRACKED]" if c.already_tracked else ""
        print(f"  {i:2d}. r/{c.display_name}{tracked_tag}")
        print(f"      Score: {c.relevance_score:.0f}/100 | Subs: {c.subscribers:,} | "
              f"Active: {c.active_accounts:,} | Domain: {c.domain}")
        desc = c.public_description or c.description
        if desc:
            print(f"      {desc[:100]}...")
        print()

    if args.propose:
        print("\n--- PROPOSED PROFILES (paste into profiles.py BUILTIN_PROFILES) ---\n")
        for c in candidates:
            if not c.already_tracked:
                print(c.profile_proposal())
                print()


if __name__ == "__main__":
    main()
