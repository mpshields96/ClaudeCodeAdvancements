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


# ── CLI ───────────────────────────────────────────────────────────────────────


def cli_main(args: list = None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args:
        print("Usage: python3 github_scanner.py [queries|evaluate <owner/repo>]")
        return

    cmd = args[0]

    if cmd == "queries":
        scanner = GitHubScanner()
        queries = scanner.build_search_queries()
        print("GitHub search queries for CCA frontiers:")
        for i, q in enumerate(queries, 1):
            print(f"  {i}. {q}")

    elif cmd == "evaluate":
        if len(args) < 2:
            print("Usage: python3 github_scanner.py evaluate <owner/repo>")
            return
        repo_name = args[1]
        print(f"To evaluate {repo_name}, fetch its metadata via GitHub API")
        print(f"  URL: https://api.github.com/repos/{repo_name}")
        print("  Then pass the JSON to RepoMetadata.from_api_dict()")

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python3 github_scanner.py [queries|evaluate <owner/repo>]")


if __name__ == "__main__":
    cli_main()
