#!/usr/bin/env python3
"""
github_scanner.py — MT-11 GitHub Repository Intelligence Scanner.

Evaluates GitHub repos by metadata (stars, tests, license, activity) and
description content. No cloning — all analysis via API/web metadata.

Components:
  - RepoMetadata: structured repo info from GitHub API responses
  - RepoEvaluator: scores repos against quality + relevance rubric
  - EvaluationResult: scored output with verdict (EVALUATE/SKIP/BLOCKED)
  - GitHubScanner: orchestrates evaluation + logging + dedup

Safety (inherits MT-9 + MT-11 protections):
  - No git clone into CCA directory
  - No dependency installation
  - License check (GPL flagged, no-license penalized)
  - Recency check (inactive repos penalized)
  - Scam detection via content_scanner integration
  - Evaluation log for audit trail

Usage:
    python3 github_scanner.py queries               # Show search queries
    python3 github_scanner.py evaluate <owner/repo>  # Evaluate a repo (needs API)

Stdlib only. No external dependencies.
"""

import json
import os
import re
import sys
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent dirs for imports
_THIS_DIR = Path(__file__).parent
_PROJECT_DIR = _THIS_DIR.parent
sys.path.insert(0, str(_PROJECT_DIR / "agent-guard"))

from content_scanner import scan_text, scan_repo_metadata, ThreatLevel


# ── Frontier Relevance Keywords ──────────────────────────────────────────────

FRONTIER_KEYWORDS = {
    "memory": [
        "persistent memory", "cross-session", "long-term memory",
        "memory system", "conversation history", "session state",
    ],
    "spec": [
        "spec driven", "specification", "requirements", "design doc",
        "architecture", "task breakdown", "implementation plan",
    ],
    "context": [
        "context window", "context management", "token counting",
        "compaction", "context health", "context rot", "handoff",
    ],
    "agent": [
        "multi-agent", "agent coordination", "file locking",
        "conflict detection", "parallel agent", "agent guard",
    ],
    "usage": [
        "token usage", "cost tracking", "usage dashboard",
        "billing", "api cost", "token counter",
    ],
    "mcp": [
        "mcp server", "mcp tool", "model context protocol",
        "tool use", "function calling",
    ],
    "hook": [
        "claude hook", "pre tool use", "post tool use",
        "stop hook", "event hook", "lifecycle hook",
    ],
    "trading": [
        "trading bot", "prediction market", "kalshi", "polymarket",
        "backtesting", "strategy", "algorithm trading", "market maker",
    ],
    "dev_tools": [
        "developer tool", "cli tool", "code generation",
        "linter", "formatter", "code review", "testing framework",
    ],
}


# ── RepoMetadata ─────────────────────────────────────────────────────────────


@dataclass
class RepoMetadata:
    """Structured GitHub repo metadata."""
    full_name: str
    description: str
    stars: int
    forks: int
    open_issues: int
    language: str
    license_id: str  # None if no license
    age_days: float
    days_since_push: float
    topics: list
    url: str
    default_branch: str

    @classmethod
    def from_api_dict(cls, data: dict) -> "RepoMetadata":
        """Create from a GitHub API response dict."""
        now = datetime.now(timezone.utc)

        # Parse dates
        created_str = data.get("created_at", "")
        pushed_str = data.get("pushed_at", "")

        try:
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            age_days = (now - created).total_seconds() / 86400
        except (ValueError, TypeError):
            age_days = 0

        try:
            pushed = datetime.fromisoformat(pushed_str.replace("Z", "+00:00"))
            days_since_push = (now - pushed).total_seconds() / 86400
        except (ValueError, TypeError):
            days_since_push = float("inf")

        # License
        lic = data.get("license")
        license_id = lic.get("spdx_id") if isinstance(lic, dict) else None

        return cls(
            full_name=data.get("full_name", ""),
            description=data.get("description") or "",
            stars=data.get("stargazers_count", 0),
            forks=data.get("forks_count", 0),
            open_issues=data.get("open_issues_count", 0),
            language=data.get("language") or "",
            license_id=license_id,
            age_days=round(age_days, 1),
            days_since_push=round(days_since_push, 1),
            topics=data.get("topics") or [],
            url=data.get("html_url", ""),
            default_branch=data.get("default_branch", "main"),
        )


# ── EvaluationResult ─────────────────────────────────────────────────────────


@dataclass
class EvaluationResult:
    """Result of evaluating a repo."""
    total: float
    components: dict
    warnings: list
    blocked: bool
    block_reason: str
    verdict: str  # EVALUATE, SKIP, BLOCKED

    def to_dict(self) -> dict:
        return asdict(self)


# ── RepoEvaluator ────────────────────────────────────────────────────────────


_SCAM_KEYWORDS = [
    "free unlimited", "bypass rate limit", "bypass api", "100x your",
    "unlimited api", "free api calls", "hack", "crack", "keygen",
    "free credits", "unlimited credits", "jailbreak",
]

_RESTRICTIVE_LICENSES = {"GPL-2.0", "GPL-3.0", "AGPL-3.0"}


class RepoEvaluator:
    """
    Scores repos against a quality + relevance rubric.

    Scoring (0-100):
      - Stars: 0-25 (log scale)
      - Activity: 0-25 (recent push = more points)
      - License: 0-15 (MIT/Apache = full, GPL = partial, none = 0)
      - Relevance: 0-25 (topic/description match to CCA frontiers)
      - Age: 0-10 (mature but not abandoned)
    """

    def evaluate(self, meta: RepoMetadata) -> EvaluationResult:
        components = {}
        warnings = []
        blocked = False
        block_reason = ""

        # -- Scam check (blocks evaluation) --
        desc_lower = meta.description.lower()
        for kw in _SCAM_KEYWORDS:
            if kw in desc_lower:
                return EvaluationResult(
                    total=0, components={}, warnings=[],
                    blocked=True, block_reason=f"Scam keyword: '{kw}'",
                    verdict="BLOCKED",
                )

        # Content scanner check on description
        text_scan = scan_text(meta.description)
        if text_scan.threat_level.value >= ThreatLevel.DANGEROUS.value:
            return EvaluationResult(
                total=0, components={}, warnings=[],
                blocked=True, block_reason=f"Dangerous content in description: {text_scan.threat_types}",
                verdict="BLOCKED",
            )

        # -- Stars (0-25, log scale) --
        if meta.stars >= 1000:
            star_score = 25
        elif meta.stars >= 500:
            star_score = 22
        elif meta.stars >= 100:
            star_score = 18
        elif meta.stars >= 50:
            star_score = 14
        elif meta.stars >= 10:
            star_score = 8
        else:
            star_score = 3
            warnings.append(f"Very few stars ({meta.stars})")
        components["stars"] = star_score

        # -- Activity (0-25) --
        if meta.days_since_push <= 7:
            activity_score = 25
        elif meta.days_since_push <= 30:
            activity_score = 20
        elif meta.days_since_push <= 90:
            activity_score = 15
        elif meta.days_since_push <= 180:
            activity_score = 8
        else:
            activity_score = 3
            warnings.append(f"Inactive ({meta.days_since_push:.0f} days since last push)")
        components["activity"] = activity_score

        # -- License (0-15) --
        if meta.license_id is None:
            license_score = 0
            warnings.append("No license")
        elif meta.license_id in _RESTRICTIVE_LICENSES:
            license_score = 8
            warnings.append(f"Restrictive license ({meta.license_id}) — cannot relicense")
        elif meta.license_id in ("MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"):
            license_score = 15
        else:
            license_score = 10
        components["license"] = license_score

        # -- Relevance (0-25) --
        relevance_score = self._score_relevance(meta)
        components["relevance"] = relevance_score

        # -- Age (0-10) --
        if meta.age_days < 7:
            age_score = 2
            warnings.append(f"Brand new repo ({meta.age_days:.0f} days old)")
        elif meta.age_days < 30:
            age_score = 5
        elif meta.age_days < 365:
            age_score = 10
        else:
            age_score = 8  # Very old repos slightly less — may be abandoned
        components["age"] = age_score

        total = sum(components.values())

        # Determine verdict
        if total >= 50:
            verdict = "EVALUATE"
        else:
            verdict = "SKIP"

        return EvaluationResult(
            total=round(total, 1),
            components=components,
            warnings=warnings,
            blocked=blocked,
            block_reason=block_reason,
            verdict=verdict,
        )

    def _score_relevance(self, meta: RepoMetadata) -> int:
        """Score relevance to CCA frontiers based on topics + description."""
        text = (meta.description + " " + " ".join(meta.topics)).lower()
        matched_frontiers = set()

        for frontier, keywords in FRONTIER_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    matched_frontiers.add(frontier)
                    break

        if len(matched_frontiers) >= 3:
            return 25
        elif len(matched_frontiers) >= 2:
            return 20
        elif len(matched_frontiers) >= 1:
            return 15
        else:
            return 5


# ── GitHubScanner ────────────────────────────────────────────────────────────


class GitHubScanner:
    """
    Orchestrates GitHub repo evaluation + logging.
    """

    def __init__(self, eval_log_path: str = None):
        self.evaluator = RepoEvaluator()
        self.eval_log_path = eval_log_path or str(_THIS_DIR / "github_evaluations.jsonl")
        self._evaluated_cache = None

    def build_search_queries(self) -> list:
        """Generate GitHub search queries targeting CCA-relevant repos."""
        queries = [
            "claude code mcp server",
            "claude hooks agent",
            "context window management llm",
            "persistent memory ai agent",
            "multi-agent coordination",
            "prediction market bot api",
            "trading bot python backtesting",
            "developer tools cli ai",
            "spec driven development",
            "token usage tracking llm",
        ]
        return queries

    def evaluate(self, meta: RepoMetadata) -> EvaluationResult:
        """Evaluate a repo's metadata."""
        return self.evaluator.evaluate(meta)

    def log_evaluation(self, meta: RepoMetadata, result: EvaluationResult):
        """Append evaluation to JSONL log."""
        entry = {
            "repo": meta.full_name,
            "url": meta.url,
            "stars": meta.stars,
            "language": meta.language,
            "score": result.total,
            "verdict": result.verdict,
            "components": result.components,
            "warnings": result.warnings,
            "blocked": result.blocked,
            "block_reason": result.block_reason,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.eval_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        # Invalidate cache
        self._evaluated_cache = None

    def already_evaluated(self, full_name: str) -> bool:
        """Check if a repo has already been evaluated."""
        if self._evaluated_cache is None:
            self._evaluated_cache = set()
            if os.path.exists(self.eval_log_path):
                with open(self.eval_log_path) as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            self._evaluated_cache.add(entry.get("repo", ""))
                        except json.JSONDecodeError:
                            pass
        return full_name in self._evaluated_cache

    def scan_query(self, query: str, limit: int = 10, sort: str = "stars") -> list:
        """
        Search + evaluate + log pipeline.

        Searches GitHub, evaluates each repo, logs results, skips duplicates.
        Returns list of (RepoMetadata, EvaluationResult) tuples.
        """
        repos = search_repos(query, limit=limit, sort=sort)
        results = []
        for meta in repos:
            if self.already_evaluated(meta.full_name):
                continue
            result = self.evaluate(meta)
            self.log_evaluation(meta, result)
            results.append((meta, result))
        return results

    def deep_evaluate(self, meta: RepoMetadata) -> dict:
        """
        Deep evaluation: clone repo into sandbox, run tests, score quality.

        Only call this for repos that passed metadata evaluation (verdict=EVALUATE).
        Returns dict with test results or None on failure.
        """
        from repo_tester import RepoTester, clone_repo
        tester = RepoTester()
        clone_path = clone_repo(meta.full_name, timeout=30)
        if clone_path is None:
            return None
        try:
            result = tester.evaluate_local(clone_path, repo_name=meta.full_name)
            tester.log_result(result)
            return result.to_dict()
        finally:
            tester.cleanup(clone_path)

    def scan_all_queries(self, limit_per_query: int = 5) -> list:
        """
        Run all built-in search queries and collect results.
        Returns list of (RepoMetadata, EvaluationResult) tuples.
        """
        all_results = []
        for query in self.build_search_queries():
            results = self.scan_query(query, limit=limit_per_query)
            all_results.extend(results)
        return all_results


# ── GitHub API Integration (Phase 2) ─────────────────────────────────────────

_GITHUB_API = "https://api.github.com"
_USER_AGENT = "CCA-GitHub-Scanner/1.0 (github.com/mpshields96/ClaudeCodeAdvancements)"


def _github_request(url: str, timeout: int = 10) -> dict:
    """Make a GET request to GitHub API. Returns parsed JSON or None."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": _USER_AGENT,
    }
    # Use GITHUB_TOKEN if available (avoids 60 req/hr unauthenticated limit)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
            OSError, TimeoutError):
        return None


def fetch_repo(full_name: str, timeout: int = 10) -> "RepoMetadata":
    """
    Fetch repo metadata from GitHub API.

    Args:
        full_name: "owner/repo" format
        timeout: request timeout in seconds

    Returns RepoMetadata or None on failure.
    """
    if not full_name or "/" not in full_name:
        return None
    url = f"{_GITHUB_API}/repos/{urllib.parse.quote(full_name, safe='/')}"
    data = _github_request(url, timeout=timeout)
    if data is None or "full_name" not in data:
        return None
    return RepoMetadata.from_api_dict(data)


def search_repos(
    query: str,
    limit: int = 10,
    sort: str = "stars",
    timeout: int = 15,
) -> list:
    """
    Search GitHub repos by query string.

    Args:
        query: search terms
        limit: max results (capped at 30 per API page)
        sort: "stars", "updated", "forks", or "best-match"
        timeout: request timeout

    Returns list of RepoMetadata (may be empty).
    """
    if not query or not query.strip():
        return []

    params = {
        "q": query.strip(),
        "sort": sort if sort != "best-match" else "",
        "order": "desc",
        "per_page": min(limit, 30),
    }
    # Remove empty params
    params = {k: v for k, v in params.items() if v}
    url = f"{_GITHUB_API}/search/repositories?{urllib.parse.urlencode(params)}"
    data = _github_request(url, timeout=timeout)
    if data is None or "items" not in data:
        return []

    results = []
    for item in data["items"][:limit]:
        try:
            meta = RepoMetadata.from_api_dict(item)
            results.append(meta)
        except (KeyError, TypeError, ValueError):
            continue
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────


def cli_main(args: list = None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args:
        print("Usage: python3 github_scanner.py [queries|fetch|evaluate|scan] ...")
        print("  queries               Show built-in search queries")
        print("  fetch <owner/repo>    Fetch + evaluate a specific repo (live API)")
        print("  evaluate <owner/repo> Same as fetch")
        print("  scan [query]          Search + evaluate repos (live API)")
        print("  scan --all            Run all built-in queries")
        return

    cmd = args[0]

    if cmd == "queries":
        scanner = GitHubScanner()
        queries = scanner.build_search_queries()
        print("GitHub search queries for CCA frontiers:")
        for i, q in enumerate(queries, 1):
            print(f"  {i}. {q}")

    elif cmd in ("fetch", "evaluate"):
        if len(args) < 2:
            print("Usage: python3 github_scanner.py fetch <owner/repo> [--deep]")
            return
        repo_name = args[1]
        deep_mode = "--deep" in args
        print(f"Fetching {repo_name} from GitHub API...")
        meta = fetch_repo(repo_name)
        if meta is None:
            print(f"  Failed — repo not found or API unavailable.")
            return
        scanner = GitHubScanner()
        result = scanner.evaluate(meta)
        scanner.log_evaluation(meta, result)
        print(f"  {meta.full_name}  [{meta.language}]  {meta.stars} stars")
        print(f"  License: {meta.license_id or 'none'}  |  Last push: {meta.days_since_push:.0f}d ago  |  Age: {meta.age_days:.0f}d")
        print(f"  Topics: {', '.join(meta.topics[:8]) if meta.topics else 'none'}")
        print(f"  Score: {result.total}/100  →  {result.verdict}")
        if result.components:
            parts = [f"{k}={v}" for k, v in result.components.items()]
            print(f"  Components: {', '.join(parts)}")
        if result.warnings:
            print(f"  Warnings: {'; '.join(result.warnings)}")
        if result.blocked:
            print(f"  BLOCKED: {result.block_reason}")

        # Deep evaluation: clone, test, score
        if deep_mode and result.verdict == "EVALUATE":
            print(f"\n  Deep evaluation (clone + test + score)...")
            deep_result = scanner.deep_evaluate(meta)
            if deep_result:
                print(f"  Language: {deep_result.get('language', '?')}  |  Framework: {deep_result.get('test_framework', '?')}")
                print(f"  Tests: {deep_result.get('tests_found', 0)} found, {deep_result.get('tests_passed', 0)} passed")
                print(f"  Quality: {deep_result.get('quality_score', 0)}/100  →  {deep_result.get('verdict', '?')}")
            else:
                print(f"  Deep evaluation failed (clone or test error)")

    elif cmd == "scan":
        rest = args[1:]
        # Parse flags
        run_all = "--all" in rest
        limit = 5
        json_output = "--json" in rest
        query_parts = [a for a in rest if not a.startswith("--")]

        if "--help" in rest:
            print("Usage: python3 github_scanner.py scan [query] [--all] [--json]")
            print("  scan 'claude mcp'   Search + evaluate repos matching query")
            print("  scan --all          Run all built-in queries")
            print("  scan --json         Output as JSON")
            return

        scanner = GitHubScanner()

        if run_all:
            print("Running all built-in queries against GitHub API...")
            results = scanner.scan_all_queries(limit_per_query=limit)
        elif query_parts:
            query = " ".join(query_parts)
            print(f"Searching GitHub for: {query}")
            results = scanner.scan_query(query, limit=limit * 2)
        else:
            print("Usage: python3 github_scanner.py scan [query] or scan --all")
            return

        if json_output:
            output = []
            for meta, result in results:
                output.append({
                    "repo": meta.full_name,
                    "stars": meta.stars,
                    "language": meta.language,
                    "score": result.total,
                    "verdict": result.verdict,
                    "url": meta.url,
                })
            print(json.dumps(output, indent=2))
        else:
            if not results:
                print("No new repos found (all may be already evaluated).")
                return
            evaluate_count = sum(1 for _, r in results if r.verdict == "EVALUATE")
            skip_count = sum(1 for _, r in results if r.verdict == "SKIP")
            blocked_count = sum(1 for _, r in results if r.verdict == "BLOCKED")
            print(f"\nFound {len(results)} new repos: {evaluate_count} EVALUATE, {skip_count} SKIP, {blocked_count} BLOCKED\n")
            for meta, result in sorted(results, key=lambda x: x[1].total, reverse=True):
                marker = ">>>" if result.verdict == "EVALUATE" else "   "
                print(f"  {marker} [{result.total:4.0f}] {result.verdict:<8} {meta.full_name} ({meta.stars} stars, {meta.language})")
            print(f"\nLogged to: {scanner.eval_log_path}")

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python3 github_scanner.py [queries|fetch|evaluate|scan] ...")


if __name__ == "__main__":
    cli_main()
