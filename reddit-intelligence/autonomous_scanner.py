#!/usr/bin/env python3
"""
autonomous_scanner.py — MT-9 Autonomous Cross-Subreddit Intelligence Pipeline.

Orchestrates profiles.py + nuclear_fetcher.py + content_scanner.py into a
self-directed scanning pipeline that picks which subreddit to scan, enforces
safety protections, and produces structured reports.

Components:
  - ScanPrioritizer: picks which sub to scan (staleness + yield + diversity)
  - SafetyGate: enforces kill switch, rate limits, content scanning
  - AutonomousScanner: orchestrates the full pipeline
  - ScanReport: structured output

Safety (MT-9 non-negotiable):
  1. No executable downloads
  2. No credential exposure
  3. No system modifications
  4. No financial actions
  5. No outbound data
  6. Sandboxed evaluation (read-only analysis)
  7. Scam detection
  8. Rate limiting (max 50 posts/scan, min 30s between scans)
  9. Audit trail (all findings logged)

Kill switch: create ~/.cca-autonomous-pause to instantly pause all scanning.

Usage:
    python3 autonomous_scanner.py rank                # Show prioritized sub list
    python3 autonomous_scanner.py status              # Show safety gate status
    python3 autonomous_scanner.py pick                # Pick next target
    python3 autonomous_scanner.py pick --domain claude # Pick from specific domain

Stdlib only. No external dependencies.
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent dirs to path for imports
_THIS_DIR = Path(__file__).parent
_PROJECT_DIR = _THIS_DIR.parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_PROJECT_DIR / "agent-guard"))

from profiles import BUILTIN_PROFILES, get_profile, ScanRegistry, merge_scout_nuclear
from nuclear_fetcher import classify_post, load_findings_urls, fetch_top_posts, fetch_hot_posts, fetch_rising_posts
from content_scanner import is_safe_for_deep_read
from github_scanner import TrendingScanner


# ── Approved Domains (MT-9 spec) ─────────────────────────────────────────────

APPROVED_DOMAINS = {"claude", "trading", "dev", "research"}


# ── ScanReport ────────────────────────────────────────────────────────────────


@dataclass
class ScanReport:
    """Structured output from an autonomous scan."""
    subreddit: str
    slug: str
    domain: str
    posts_fetched: int
    posts_safe: int
    posts_blocked: int
    needles: int
    maybes: int
    hay: int
    blocked_reasons: list = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        lines = [
            f"r/{self.subreddit} ({self.domain}) — Autonomous Scan Report",
            f"  Posts fetched: {self.posts_fetched}",
            f"  Safe for review: {self.posts_safe}",
            f"  Blocked (safety): {self.posts_blocked}",
            f"  Classification: {self.needles} NEEDLE, {self.maybes} MAYBE, {self.hay} HAY",
        ]
        if self.blocked_reasons:
            unique = list(set(self.blocked_reasons))[:5]
            lines.append(f"  Block reasons: {', '.join(unique)}")
        return "\n".join(lines)


# ── ScanResult ───────────────────────────────────────────────────────────────


@dataclass
class ScanResult:
    """Complete result from execute_scan — report + classified post lists."""
    report: ScanReport
    needles: list = field(default_factory=list)
    maybes: list = field(default_factory=list)
    hay: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "report": self.report.to_dict(),
            "needles": self.needles,
            "maybes": self.maybes,
            "hay": self.hay,
        }

    def save_json(self, path: str):
        """Write result to JSON file (atomic)."""
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        os.replace(tmp, path)


# ── GitHubTrendingReport ──────────────────────────────────────────────────────


@dataclass
class GitHubTrendingReport:
    """Structured output from a GitHub trending scan."""
    repos_found: int
    evaluate_count: int
    languages_scanned: list
    results: list  # list of (RepoMetadata, EvaluationResult) serialized dicts
    days: int = 7
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "repos_found": self.repos_found,
            "evaluate_count": self.evaluate_count,
            "languages_scanned": self.languages_scanned,
            "results": self.results,
            "days": self.days,
            "timestamp": self.timestamp,
        }

    def summary(self) -> str:
        lines = [
            f"GitHub Trending Scan — {self.days}d window",
            f"  Repos found: {self.repos_found}",
            f"  EVALUATE verdicts: {self.evaluate_count}",
            f"  Languages: {', '.join(self.languages_scanned)}",
        ]
        return "\n".join(lines)


# ── ScanPrioritizer ──────────────────────────────────────────────────────────


class ScanPrioritizer:
    """
    Picks which subreddit to scan next based on:
    1. Staleness (days since last scan) — higher = more priority
    2. Historical yield (BUILD+ADAPT rate) — higher = more priority
    3. Never-scanned bonus — subs never scanned get max staleness score
    4. Domain diversity — represented in output for caller filtering
    """

    # Weights for priority scoring
    STALENESS_WEIGHT = 2.0    # Staleness is most important
    YIELD_WEIGHT = 1.0        # Past performance matters
    NEVER_SCANNED_BONUS = 100  # Never-scanned subs get a big boost

    def __init__(self, registry_path: str = None):
        if registry_path is None:
            registry_path = str(_THIS_DIR / "scan_registry.json")
        self._registry = ScanRegistry(registry_path)

    def rank_all(self) -> list:
        """
        Rank all builtin profiles by priority score.
        Returns list of dicts sorted by priority_score descending.
        """
        now = datetime.now(timezone.utc)
        scans = self._registry.list_scans()
        ranked = []

        for slug, profile in BUILTIN_PROFILES.items():
            # Skip domains we're not approved for
            if profile.domain not in APPROVED_DOMAINS and profile.domain != "unknown":
                continue

            entry = {
                "slug": slug,
                "subreddit": profile.subreddit,
                "domain": profile.domain,
                "never_scanned": False,
                "staleness_days": float("inf"),
                "yield_score": 0.0,
                "priority_score": 0.0,
            }

            if slug not in scans:
                # Never scanned — highest priority
                entry["never_scanned"] = True
                entry["staleness_days"] = float("inf")
                entry["priority_score"] = self.NEVER_SCANNED_BONUS
            else:
                scan_data = scans[slug]
                last_scan_str = scan_data.get("last_scan", "")

                # Compute staleness
                try:
                    last_dt = datetime.fromisoformat(last_scan_str)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    staleness = (now - last_dt).total_seconds() / 86400
                except (ValueError, TypeError):
                    staleness = float("inf")

                entry["staleness_days"] = round(staleness, 1)

                # Compute yield
                yield_score = self._registry.yield_score(slug)
                entry["yield_score"] = round(yield_score, 2)

                # Combined priority
                entry["priority_score"] = round(
                    staleness * self.STALENESS_WEIGHT + yield_score * self.YIELD_WEIGHT,
                    2,
                )

            ranked.append(entry)

        # Sort by priority_score descending
        ranked.sort(key=lambda r: r["priority_score"], reverse=True)
        return ranked

    def pick_next(self, exclude: list = None, domain: str = None) -> dict:
        """
        Pick the highest-priority sub to scan next.

        Args:
            exclude: list of slugs to skip
            domain: if set, only return subs from this domain
        """
        exclude = set(exclude or [])
        ranked = self.rank_all()

        for entry in ranked:
            if entry["slug"] in exclude:
                continue
            if domain and entry["domain"] != domain:
                continue
            return entry

        # Fallback: return the top entry ignoring filters
        return ranked[0] if ranked else {}


# ── SafetyGate ────────────────────────────────────────────────────────────────


class SafetyGate:
    """
    Enforces MT-9 safety protections:
    - Kill switch file check
    - Rate limiting (max posts per scan, max scans per session)
    - Content safety delegation to content_scanner.py
    - State persistence
    """

    def __init__(
        self,
        kill_switch_path: str = None,
        state_path: str = None,
        max_posts_per_scan: int = 50,
        max_scans_per_session: int = 10,
        min_delay_seconds: int = 30,
    ):
        self.kill_switch_path = kill_switch_path or os.path.expanduser("~/.cca-autonomous-pause")
        self.state_path = state_path or str(_THIS_DIR / "autonomous_state.json")
        self.max_posts_per_scan = max_posts_per_scan
        self.max_scans_per_session = max_scans_per_session
        self.min_delay_seconds = min_delay_seconds

        # Session state
        self.scans_this_session = 0
        self.subs_scanned = []
        self.last_scan_time = None
        self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path) as f:
                    state = json.load(f)
                self.scans_this_session = state.get("scans_this_session", 0)
                self.subs_scanned = state.get("subs_scanned", [])
                last = state.get("last_scan_time")
                if last:
                    self.last_scan_time = datetime.fromisoformat(last)
            except (json.JSONDecodeError, OSError, ValueError):
                pass

    def save_state(self):
        state = {
            "scans_this_session": self.scans_this_session,
            "subs_scanned": self.subs_scanned,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, self.state_path)

    def can_scan(self) -> tuple:
        """
        Check if scanning is currently allowed.
        Returns (allowed: bool, reason: str).
        """
        # Kill switch
        if os.path.exists(self.kill_switch_path):
            return False, "Kill switch active — ~/.cca-autonomous-pause exists. Remove to resume."

        # Session scan limit
        if self.scans_this_session >= self.max_scans_per_session:
            return False, f"Session scan limit reached ({self.max_scans_per_session}). Start a new session."

        # Rate limiting (delay between scans)
        if self.last_scan_time and self.min_delay_seconds > 0:
            elapsed = (datetime.now(timezone.utc) - self.last_scan_time).total_seconds()
            if elapsed < self.min_delay_seconds:
                remaining = int(self.min_delay_seconds - elapsed)
                return False, f"Rate limit — wait {remaining}s before next scan."

        return True, "Scanning allowed."

    def record_scan(self, slug: str):
        """Record that a scan was performed."""
        self.scans_this_session += 1
        if slug not in self.subs_scanned:
            self.subs_scanned.append(slug)
        self.last_scan_time = datetime.now(timezone.utc)
        self.save_state()

    def check_post_safety(self, post: dict) -> tuple:
        """
        Check if a post is safe for deep reading.
        Delegates to content_scanner.is_safe_for_deep_read.
        Returns (is_safe: bool, reason: str).
        """
        return is_safe_for_deep_read(post)


# ── AutonomousScanner ─────────────────────────────────────────────────────────


class AutonomousScanner:
    """
    Orchestrates the autonomous scanning pipeline:
    1. Pick target sub (via ScanPrioritizer)
    2. Check safety (via SafetyGate)
    3. Fetch posts (via nuclear_fetcher infrastructure)
    4. Filter unsafe posts
    5. Classify (NEEDLE/MAYBE/HAY)
    6. Dedup against FINDINGS_LOG.md
    7. Produce ScanReport
    """

    def __init__(
        self,
        registry_path: str = None,
        kill_switch_path: str = None,
        state_path: str = None,
        findings_path: str = None,
    ):
        self.prioritizer = ScanPrioritizer(registry_path=registry_path)
        self.safety_gate = SafetyGate(
            kill_switch_path=kill_switch_path,
            state_path=state_path,
        )
        self.findings_path = findings_path or str(_PROJECT_DIR / "FINDINGS_LOG.md")

    def pick_target(self, exclude: list = None, domain: str = None) -> dict:
        """
        Pick the next sub to scan. Returns None if blocked by safety gate.
        """
        allowed, reason = self.safety_gate.can_scan()
        if not allowed:
            return None
        return self.prioritizer.pick_next(exclude=exclude, domain=domain)

    def filter_posts(self, posts: list) -> tuple:
        """
        Filter posts through safety gate.
        Returns (safe_posts, blocked_posts_with_reasons).
        """
        safe = []
        blocked = []
        for post in posts:
            is_safe, reason = self.safety_gate.check_post_safety(post)
            if is_safe:
                safe.append(post)
            else:
                blocked.append({"post": post, "reason": reason})

        # Enforce max posts per scan
        if len(safe) > self.safety_gate.max_posts_per_scan:
            safe = safe[:self.safety_gate.max_posts_per_scan]

        return safe, blocked

    def dedup_posts(self, posts: list) -> list:
        """Remove posts already in FINDINGS_LOG.md."""
        known_ids = load_findings_urls(self.findings_path)
        return [p for p in posts if p["id"] not in known_ids]

    def classify_posts(self, posts: list) -> list:
        """Add triage classification to each post."""
        for p in posts:
            p["triage"] = classify_post(p)
        return posts

    def execute_scan(
        self,
        subreddit: str,
        slug: str,
        domain: str,
        fetch_limit: int = None,
        timeframe: str = None,
    ) -> ScanResult:
        """
        Execute a full autonomous scan on a subreddit.

        1. Check safety gate
        2. Resolve fetch params from profile (or use custom)
        3. Fetch posts via nuclear_fetcher
        4. Filter unsafe
        5. Dedup against FINDINGS_LOG
        6. Classify (NEEDLE/MAYBE/HAY)
        7. Record scan in safety gate + registry
        8. Build and return ScanResult

        Returns None if blocked by safety gate.
        """
        # Safety check
        allowed, reason = self.safety_gate.can_scan()
        if not allowed:
            return None

        # Resolve fetch parameters from profile if not custom
        if fetch_limit is None or timeframe is None:
            try:
                profile = get_profile(subreddit)
                params = merge_scout_nuclear(subreddit, "full", profile)
                fetch_limit = fetch_limit or params.get("fetch_limit", 100)
                timeframe = timeframe or params.get("timeframe", "year")
            except Exception:
                fetch_limit = fetch_limit or 100
                timeframe = timeframe or "year"

        # Fetch posts (zero Claude tokens — pure Reddit API)
        posts = fetch_top_posts(subreddit, fetch_limit, timeframe)

        # Filter unsafe
        safe, blocked = self.filter_posts(posts)

        # Dedup against FINDINGS_LOG
        safe = self.dedup_posts(safe)

        # Classify
        safe = self.classify_posts(safe)

        # Split by triage
        needles = [p for p in safe if p.get("triage") == "NEEDLE"]
        maybes = [p for p in safe if p.get("triage") == "MAYBE"]
        hay = [p for p in safe if p.get("triage") == "HAY"]

        # Build report
        report = self.build_report(subreddit, slug, domain, posts, safe, blocked)

        # Record scan
        self.safety_gate.record_scan(slug)

        # Update scan registry
        registry = ScanRegistry(self.prioritizer._registry._path)
        registry.record_scan(
            slug,
            posts_scanned=len(posts),
            builds=0,  # Will be updated after review
            adapts=0,
        )

        return ScanResult(
            report=report,
            needles=needles,
            maybes=maybes,
            hay=hay,
        )

    def execute_daily_scan(
        self,
        subs: list = None,
        hot_limit: int = 25,
        rising_limit: int = 10,
        include_rescan: bool = False,
    ) -> list:
        """
        Execute a daily hot+rising scan across multiple subreddits.

        Designed for daily use — lightweight, fast, feeds self-learning.
        Fetches hot + rising posts, dedupes, classifies, returns ScanResults.

        Args:
            subs: list of subreddit names to scan. Defaults to high-signal subs.
            hot_limit: max hot posts per sub (default 25)
            rising_limit: max rising posts per sub (default 10)

        Returns list of ScanResult (one per sub scanned).
        """
        if subs is None:
            # Default to highest-signal subs for daily scanning
            subs = ["ClaudeCode", "ClaudeAI", "vibecoding"]

        results = []

        for sub in subs:
            # Safety check each sub
            allowed, reason = self.safety_gate.can_scan()
            if not allowed:
                break

            # Resolve slug and domain
            slug = sub.lower().replace("/", "").replace("r", "", 1) if sub.startswith("r/") else sub.lower()
            try:
                profile = get_profile(sub)
                scan_domain = profile.domain if hasattr(profile, "domain") else "unknown"
                slug_clean = slug.replace(" ", "")
            except Exception:
                scan_domain = "unknown"
                slug_clean = slug

            # Fetch hot + rising (zero Claude tokens)
            hot_posts = fetch_hot_posts(sub, hot_limit)
            rising_posts = fetch_rising_posts(sub, rising_limit)

            # Merge and deduplicate by post ID
            seen_ids = set()
            all_posts = []
            for p in hot_posts + rising_posts:
                if p["id"] not in seen_ids:
                    seen_ids.add(p["id"])
                    all_posts.append(p)

            # Filter unsafe
            safe, blocked = self.filter_posts(all_posts)

            # Dedup against FINDINGS_LOG
            safe = self.dedup_posts(safe)

            # Classify
            safe = self.classify_posts(safe)

            # Split by triage
            needles = [p for p in safe if p.get("triage") == "NEEDLE"]
            maybes = [p for p in safe if p.get("triage") == "MAYBE"]
            hay = [p for p in safe if p.get("triage") == "HAY"]

            # Build report
            report = self.build_report(sub, slug_clean, scan_domain, all_posts, safe, blocked)

            # Record scan
            self.safety_gate.record_scan(slug_clean)

            results.append(ScanResult(
                report=report,
                needles=needles,
                maybes=maybes,
                hay=hay,
            ))

            # Brief pause between subs
            time.sleep(1.0)

        # MT-14 Phase 3: optionally rescan stale subs as part of daily scan
        if include_rescan:
            rescan_results = self.execute_rescan_stale()
            results.extend(rescan_results)

        return results

    def rescan_sub(
        self,
        subreddit: str,
        max_age_days: int = 14,
    ) -> ScanResult:
        """
        MT-14: Delta-rescan a previously scanned subreddit.

        Only returns posts newer than the last scan timestamp.
        Useful for keeping intelligence current without re-reviewing old posts.

        Args:
            subreddit: subreddit name
            max_age_days: only rescan if last scan was > max_age_days ago

        Returns ScanResult with only new posts, or None if not stale or blocked.
        """
        # Resolve profile
        profile = get_profile(subreddit)
        slug = subreddit.lower().replace("/", "").replace("r", "", 1) if subreddit.startswith("r/") else subreddit.lower()
        slug = slug.replace(" ", "")

        # Check if this sub is actually stale
        registry = ScanRegistry(self.prioritizer._registry._path)
        if not registry.is_stale(slug, max_age_days):
            return None  # Not stale — skip

        # Safety check
        allowed, reason = self.safety_gate.can_scan()
        if not allowed:
            return None

        # Get last scan timestamp
        scans = registry.list_scans()
        last_scan_ts = None
        if slug in scans:
            last_scan_str = scans[slug].get("last_scan", "")
            if last_scan_str:
                try:
                    last_scan_ts = datetime.fromisoformat(last_scan_str)
                    if last_scan_ts.tzinfo is None:
                        last_scan_ts = last_scan_ts.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    last_scan_ts = None

        # Fetch recent posts (use "week" timeframe for delta scanning)
        fetch_limit = min(profile.limit, 75)
        posts = fetch_top_posts(subreddit, fetch_limit, "week")

        # Delta filter: only keep posts created after last scan
        if last_scan_ts:
            delta_posts = []
            for p in posts:
                # Reddit post created_utc is a Unix timestamp
                created_utc = p.get("created_utc", 0)
                if created_utc:
                    try:
                        post_time = datetime.fromtimestamp(float(created_utc), tz=timezone.utc)
                        if post_time > last_scan_ts:
                            delta_posts.append(p)
                    except (ValueError, TypeError, OSError):
                        delta_posts.append(p)  # Include if we can't parse
                else:
                    delta_posts.append(p)  # Include if no timestamp
            posts = delta_posts

        if not posts:
            # No new posts since last scan
            self.safety_gate.record_scan(slug)
            return ScanResult(
                report=ScanReport(
                    subreddit=subreddit, slug=slug,
                    domain=profile.domain if hasattr(profile, "domain") else "unknown",
                    posts_fetched=0, posts_safe=0, posts_blocked=0,
                    needles=0, maybes=0, hay=0, blocked_reasons=[],
                ),
                needles=[], maybes=[], hay=[],
            )

        # Standard pipeline: filter -> dedup -> classify
        safe, blocked = self.filter_posts(posts)
        safe = self.dedup_posts(safe)
        safe = self.classify_posts(safe)

        needles = [p for p in safe if p.get("triage") == "NEEDLE"]
        maybes = [p for p in safe if p.get("triage") == "MAYBE"]
        hay = [p for p in safe if p.get("triage") == "HAY"]

        domain = profile.domain if hasattr(profile, "domain") else "unknown"
        report = self.build_report(subreddit, slug, domain, posts, safe, blocked)

        # Record
        self.safety_gate.record_scan(slug)
        registry.record_scan(slug, posts_scanned=len(posts), builds=0, adapts=0)

        return ScanResult(
            report=report,
            needles=needles,
            maybes=maybes,
            hay=hay,
        )

    def get_stale_subs(self, max_age_days: int = 14) -> list:
        """Return list of stale sub slugs that need rescanning."""
        registry = ScanRegistry(self.prioritizer._registry._path)
        return registry.stale_subs(max_age_days)

    def execute_rescan_stale(
        self,
        max_age_days: int = 14,
    ) -> list:
        """
        MT-14 Phase 3: Auto-rescan all stale subreddits.

        Iterates all subs in the registry that haven't been scanned in
        max_age_days, runs rescan_sub() on each, and returns a list of
        ScanResults.

        Respects safety gate (kill switch, session limits, rate limits).

        Args:
            max_age_days: threshold for staleness (default 14 days)

        Returns list of ScanResult (one per stale sub rescanned).
        """
        stale_slugs = self.get_stale_subs(max_age_days=max_age_days)
        results = []

        for slug in stale_slugs:
            # Safety gate check before each rescan
            allowed, reason = self.safety_gate.can_scan()
            if not allowed:
                break

            # Resolve subreddit name from profile
            try:
                profile = get_profile(slug)
                sub_name = profile.subreddit
            except Exception:
                sub_name = slug

            result = self.rescan_sub(sub_name, max_age_days=max_age_days)
            if result is not None:
                results.append(result)

            # Brief pause between rescans
            time.sleep(0.5)

        return results

    def execute_github_trending(
        self,
        language: str = None,
        days: int = 7,
        limit_per_lang: int = 5,
        eval_log_path: str = None,
        trending_log_path: str = None,
    ) -> "GitHubTrendingReport":
        """
        MT-11 Phase 3: Execute GitHub trending scan through autonomous pipeline.

        Wraps TrendingScanner with safety gate checks and scan recording.
        If language is specified, scans only that language. Otherwise scans all
        CCA-relevant languages.

        Returns GitHubTrendingReport, or None if blocked by safety gate.
        """
        # Safety check
        allowed, reason = self.safety_gate.can_scan()
        if not allowed:
            return None

        ts = TrendingScanner(
            eval_log_path=eval_log_path,
            trending_log_path=trending_log_path,
        )

        if language:
            # Single language scan
            results = ts.scan_trending(language=language, days=days, limit=limit_per_lang)
            languages_scanned = [language]
        else:
            # All CCA languages
            results = ts.scan_all_trending(days=days, limit_per_lang=limit_per_lang)
            languages_scanned = ts.get_cca_languages()

        repos_found = len(results)
        evaluate_count = sum(1 for _, ev in results if ev.verdict == "EVALUATE")

        # Serialize results for report
        serialized = []
        for meta, ev in results:
            serialized.append({
                "repo": meta.full_name,
                "stars": meta.stars,
                "language": meta.language,
                "verdict": ev.verdict,
                "score": ev.total,
            })

        # Record scan in safety gate
        self.safety_gate.record_scan("github-trending")

        return GitHubTrendingReport(
            repos_found=repos_found,
            evaluate_count=evaluate_count,
            languages_scanned=languages_scanned,
            results=serialized,
            days=days,
        )

    def build_report(self, subreddit: str, slug: str, domain: str,
                     fetched: list, safe: list, blocked: list) -> ScanReport:
        """Build a ScanReport from scan results."""
        needles = sum(1 for p in safe if p.get("triage") == "NEEDLE")
        maybes = sum(1 for p in safe if p.get("triage") == "MAYBE")
        hay = sum(1 for p in safe if p.get("triage") == "HAY")
        blocked_reasons = [b["reason"] for b in blocked]

        return ScanReport(
            subreddit=subreddit,
            slug=slug,
            domain=domain,
            posts_fetched=len(fetched),
            posts_safe=len(safe),
            posts_blocked=len(blocked),
            needles=needles,
            maybes=maybes,
            hay=hay,
            blocked_reasons=blocked_reasons,
        )


# ── CLI ───────────────────────────────────────────────────────────────────────


def cli_main(args: list = None):
    """CLI entry point for autonomous scanner."""
    if args is None:
        args = sys.argv[1:]

    if not args:
        print("Usage: python3 autonomous_scanner.py [rank|status|pick|scan|daily|rescan|rescan-all|stale|github-trending]")
        print("  rank                    Show prioritized sub list")
        print("  status                  Show safety gate status")
        print("  pick [--domain <d>]     Pick next target sub")
        print("  scan [--target <sub>]   Execute full scan on auto-picked or specified sub")
        print("       [--json]           Output JSON instead of summary")
        print("       [--limit <N>]      Override fetch limit")
        print("       [--timeframe <t>]  Override timeframe (hour/day/week/month/year)")
        print("  daily [--subs s1,s2]    Daily hot+rising scan across key subs")
        print("        [--hot-limit N]   Max hot posts per sub (default 25)")
        print("        [--rising-limit N] Max rising posts per sub (default 10)")
        print("  rescan [--target <sub>] MT-14: Delta-rescan stale sub (only new posts)")
        print("  rescan-all              MT-14 Phase 3: Auto-rescan ALL stale subs")
        print("        [--max-age <N>]   Staleness threshold in days (default 14)")
        print("        [--json]          Output JSON")
        print("  stale                   Show subs due for rescanning")
        print("  github-trending         MT-11: Scan GitHub for trending repos")
        print("        [--language <l>]  Scan single language (default: all CCA languages)")
        print("        [--days <N>]      Lookback window (default 7)")
        print("        [--json]          Output JSON")
        return

    cmd = args[0]

    # Parse optional flags
    registry_path = None
    state_path = None
    kill_switch_path = None
    findings_path = None
    domain = None
    target = None
    output_json = False
    fetch_limit = None
    timeframe = None
    daily_subs = None
    hot_limit = 25
    rising_limit = 10
    language = None
    days = 7
    max_age = 14
    i = 1
    while i < len(args):
        if args[i] == "--max-age" and i + 1 < len(args):
            max_age = int(args[i + 1])
            i += 2
        elif args[i] == "--language" and i + 1 < len(args):
            language = args[i + 1]
            i += 2
        elif args[i] == "--days" and i + 1 < len(args):
            days = int(args[i + 1])
            i += 2
        elif args[i] == "--registry" and i + 1 < len(args):
            registry_path = args[i + 1]
            i += 2
        elif args[i] == "--state" and i + 1 < len(args):
            state_path = args[i + 1]
            i += 2
        elif args[i] == "--kill-switch" and i + 1 < len(args):
            kill_switch_path = args[i + 1]
            i += 2
        elif args[i] == "--findings" and i + 1 < len(args):
            findings_path = args[i + 1]
            i += 2
        elif args[i] == "--domain" and i + 1 < len(args):
            domain = args[i + 1]
            i += 2
        elif args[i] == "--target" and i + 1 < len(args):
            target = args[i + 1]
            i += 2
        elif args[i] == "--json":
            output_json = True
            i += 1
        elif args[i] == "--limit" and i + 1 < len(args):
            fetch_limit = int(args[i + 1])
            i += 2
        elif args[i] == "--timeframe" and i + 1 < len(args):
            timeframe = args[i + 1]
            i += 2
        elif args[i] == "--subs" and i + 1 < len(args):
            daily_subs = [s.strip() for s in args[i + 1].split(",")]
            i += 2
        elif args[i] == "--hot-limit" and i + 1 < len(args):
            hot_limit = int(args[i + 1])
            i += 2
        elif args[i] == "--rising-limit" and i + 1 < len(args):
            rising_limit = int(args[i + 1])
            i += 2
        else:
            i += 1

    if cmd == "rank":
        p = ScanPrioritizer(registry_path=registry_path)
        ranked = p.rank_all()
        print(f"{'Slug':<20} {'Subreddit':<20} {'Domain':<10} {'Stale(d)':<10} {'Yield':<8} {'Score'}")
        print("-" * 85)
        for r in ranked:
            stale = "never" if r["never_scanned"] else f"{r['staleness_days']:.0f}"
            yld = f"{r['yield_score']:.1f}%" if r['yield_score'] > 0 else "-"
            print(f"{r['slug']:<20} r/{r['subreddit']:<18} {r['domain']:<10} {stale:<10} {yld:<8} {r['priority_score']:.1f}")

    elif cmd == "status":
        gate = SafetyGate(kill_switch_path=kill_switch_path, state_path=state_path)
        allowed, reason = gate.can_scan()
        print(f"Autonomous scan status: {'ALLOWED' if allowed else 'BLOCKED'}")
        print(f"  Reason: {reason}")
        print(f"  Scans this session: {gate.scans_this_session}/{gate.max_scans_per_session}")
        print(f"  Subs scanned: {', '.join(gate.subs_scanned) if gate.subs_scanned else 'none'}")
        kill = "ACTIVE" if os.path.exists(gate.kill_switch_path) else "inactive"
        print(f"  Kill switch: {kill}")

    elif cmd == "pick":
        scanner = AutonomousScanner(
            registry_path=registry_path,
            kill_switch_path=kill_switch_path,
            state_path=state_path,
        )
        picked = scanner.pick_target(domain=domain)
        if picked is None:
            print("Scanning blocked — check status for details.")
        else:
            print(f"Next target: r/{picked['subreddit']} ({picked['domain']})")
            print(f"  Slug: {picked['slug']}")
            stale = "never scanned" if picked["never_scanned"] else f"{picked['staleness_days']:.0f} days"
            print(f"  Staleness: {stale}")
            print(f"  Priority score: {picked['priority_score']:.1f}")

    elif cmd == "scan":
        import re as _re
        scanner = AutonomousScanner(
            registry_path=registry_path,
            kill_switch_path=kill_switch_path,
            state_path=state_path,
            findings_path=findings_path,
        )

        # Determine target: explicit --target or auto-pick
        if target:
            sub = _re.sub(r"^/?r/", "", target.strip())
            # Resolve slug and domain from profiles
            try:
                profile = get_profile(sub)
                slug = profile.slug if hasattr(profile, "slug") else sub.lower()
                scan_domain = profile.domain if hasattr(profile, "domain") else "unknown"
            except Exception:
                slug = _re.sub(r"[^a-z0-9]", "", sub.lower())
                scan_domain = "unknown"
        else:
            picked = scanner.pick_target(domain=domain)
            if picked is None:
                print("Scanning blocked — check status for details.")
                return
            sub = picked["subreddit"]
            slug = picked["slug"]
            scan_domain = picked["domain"]
            stale = "never scanned" if picked["never_scanned"] else f"{picked['staleness_days']:.0f} days stale"
            if not output_json:
                print(f"Auto-picked: r/{sub} ({scan_domain}) — {stale}")

        # Execute scan
        result = scanner.execute_scan(
            sub, slug, scan_domain,
            fetch_limit=fetch_limit,
            timeframe=timeframe,
        )

        if result is None:
            print("Scan blocked by safety gate.")
            return

        if output_json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.report.summary())
            print(f"\nReady for review: {len(result.needles)} NEEDLE, "
                  f"{len(result.maybes)} MAYBE, {len(result.hay)} HAY")

    elif cmd == "daily":
        scanner = AutonomousScanner(
            registry_path=registry_path,
            kill_switch_path=kill_switch_path,
            state_path=state_path,
            findings_path=findings_path,
        )

        results = scanner.execute_daily_scan(
            subs=daily_subs,
            hot_limit=hot_limit,
            rising_limit=rising_limit,
        )

        if output_json:
            print(json.dumps([r.to_dict() for r in results], indent=2))
        else:
            total_needles = 0
            total_new = 0
            for r in results:
                print(r.report.summary())
                total_needles += len(r.needles)
                total_new += r.report.posts_safe
                print()

            print(f"DAILY SCAN COMPLETE — {len(results)} subs scanned")
            print(f"  Total new posts: {total_new}")
            print(f"  NEEDLEs for review: {total_needles}")

            if total_needles > 0:
                print(f"\nTop NEEDLEs to review:")
                all_needles = []
                for r in results:
                    all_needles.extend(r.needles)
                all_needles.sort(key=lambda p: p["score"], reverse=True)
                for i, p in enumerate(all_needles[:15], 1):
                    print(f"  {i:2d}. [{p['score']:4d}pts] r/{p['subreddit']} — {p['title'][:80]}")
                    print(f"      {p['permalink']}")

    elif cmd == "rescan":
        scanner = AutonomousScanner(
            registry_path=registry_path,
            kill_switch_path=kill_switch_path,
            state_path=state_path,
            findings_path=findings_path,
        )

        if target:
            sub = target
        else:
            # Auto-pick stalest sub
            stale = scanner.get_stale_subs()
            if not stale:
                print("No stale subs to rescan.")
                return
            sub = stale[0]
            # Try to get the display name from profile
            try:
                profile = get_profile(sub)
                sub = profile.subreddit
            except Exception:
                pass

        print(f"Rescanning r/{sub} (delta mode — only new posts since last scan)...")
        result = scanner.rescan_sub(sub)
        if result is None:
            print("  Rescan blocked (not stale or safety gate triggered)")
        elif output_json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            if result.report.posts_fetched == 0:
                print(f"  No new posts since last scan.")
            else:
                print(result.report.summary())
                if result.needles:
                    print(f"\n  NEEDLEs for review:")
                    for i, p in enumerate(result.needles[:10], 1):
                        print(f"    {i}. [{p['score']:4d}pts] {p['title'][:80]}")

    elif cmd == "rescan-all":
        scanner = AutonomousScanner(
            registry_path=registry_path,
            kill_switch_path=kill_switch_path,
            state_path=state_path,
            findings_path=findings_path,
        )
        results = scanner.execute_rescan_stale(max_age_days=max_age)
        if output_json:
            print(json.dumps([r.to_dict() for r in results], indent=2))
        elif not results:
            print(f"No stale subs to rescan (threshold: {max_age} days).")
        else:
            total_new = 0
            total_needles = 0
            for r in results:
                print(r.report.summary())
                total_new += r.report.posts_safe
                total_needles += len(r.needles)
                print()
            print(f"RESCAN-ALL COMPLETE — {len(results)} stale subs rescanned")
            print(f"  Total new posts: {total_new}")
            print(f"  NEEDLEs for review: {total_needles}")

    elif cmd == "stale":
        scanner = AutonomousScanner(
            registry_path=registry_path,
            kill_switch_path=kill_switch_path,
            state_path=state_path,
            findings_path=findings_path,
        )
        stale = scanner.get_stale_subs()
        if stale:
            print(f"Stale subs (>14 days since last scan):")
            for s in stale:
                print(f"  - {s}")
        else:
            print("No stale subs.")

    elif cmd == "github-trending":
        scanner = AutonomousScanner(
            registry_path=registry_path,
            kill_switch_path=kill_switch_path,
            state_path=state_path,
            findings_path=findings_path,
        )

        report = scanner.execute_github_trending(
            language=language,
            days=days,
            limit_per_lang=fetch_limit or 5,
        )

        if report is None:
            print("GitHub trending scan blocked by safety gate.")
        elif output_json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(report.summary())
            if report.results:
                evaluate_repos = [r for r in report.results if r["verdict"] == "EVALUATE"]
                if evaluate_repos:
                    print(f"\n  EVALUATE repos:")
                    for r in evaluate_repos:
                        print(f"    - {r['repo']} ({r['language']}, {r['stars']} stars, score {r['score']})")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    cli_main()
