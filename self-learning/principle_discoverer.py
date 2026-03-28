#!/usr/bin/env python3
"""principle_discoverer.py — MT-49 Phase 3: Automated principle discovery.

Discovers principles from:
1. Git commit patterns (file coupling, hotspots, large commits)
2. Session journal patterns (recurring pains/wins)
3. Registers discovered patterns as principles in principle_registry

Usage:
    python3 self-learning/principle_discoverer.py discover [--dry-run]
    python3 self-learning/principle_discoverer.py status

Stdlib only. No external dependencies.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from principle_registry import add_principle, _load_principles

DEFAULT_PRINCIPLES_PATH = os.path.join(SCRIPT_DIR, "principles.jsonl")
DEFAULT_JOURNAL_PATH = os.path.join(SCRIPT_DIR, "journal.jsonl")


@dataclass
class CommitPattern:
    """A pattern discovered from git or journal analysis."""
    pattern_type: str  # coupling, hotspot, large_commit, recurring_pain, recurring_win
    description: str
    evidence_count: int
    confidence: float
    source_commits: list = field(default_factory=list)

    @property
    def clamped_confidence(self) -> float:
        return max(0.0, min(1.0, self.confidence))

    def to_principle_text(self) -> str:
        return self.description


class GitPatternDiscoverer:
    """Discovers principles from git commit history."""

    GIT_LOG_FORMAT = (
        'git log --pretty=format:"COMMIT_START %h %ai%n%s" '
        '--name-only -n {limit}'
    )

    def __init__(self, project_root=None, min_coupling_count=3,
                 hotspot_threshold=5, commit_limit=200):
        self.project_root = project_root or PROJECT_ROOT
        self.min_coupling_count = min_coupling_count
        self.hotspot_threshold = hotspot_threshold
        self.commit_limit = commit_limit

    def discover(self) -> list:
        """Run all git pattern detectors. Returns list of CommitPattern."""
        commits = self._get_commits()
        if not commits:
            return []

        patterns = []
        patterns.extend(self._detect_coupling(commits))
        patterns.extend(self._detect_hotspots(commits))
        patterns.extend(self._detect_session_size(commits))
        return patterns

    def _get_commits(self) -> list:
        """Get parsed commits from git log."""
        try:
            cmd = (
                f'git log --pretty=format:"COMMIT_START %h %ai%n%s" '
                f'--name-only -n {self.commit_limit}'
            )
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True, text=True,
                cwd=self.project_root,
            )
            if result.returncode != 0:
                return []
            return self._parse_git_log(result.stdout)
        except Exception:
            return []

    def _parse_git_log(self, log_text: str) -> list:
        """Parse git log output into structured commit dicts."""
        commits = []
        current = None
        in_files = False

        for line in log_text.split("\n"):
            line = line.strip('"').strip()
            if line.startswith("COMMIT_START "):
                if current:
                    commits.append(current)
                parts = line.split(" ", 2)
                hash_val = parts[1] if len(parts) > 1 else ""
                date_str = parts[2] if len(parts) > 2 else ""
                current = {"hash": hash_val, "message": "", "files": [], "date": date_str}
                in_files = False
            elif line == "FILES_START":
                in_files = True
            elif line == "FILES_END":
                in_files = False
            elif in_files and line:
                if current:
                    current["files"].append(line)
            elif current and not current["message"] and line and not line.startswith("COMMIT_START"):
                current["message"] = line
                # After message, remaining non-empty lines before next COMMIT_START are files
                in_files = True
            elif in_files and current and line:
                current["files"].append(line)

        if current:
            commits.append(current)

        return commits

    @staticmethod
    def _is_test_source_pair(a: str, b: str) -> bool:
        """True if a and b are a test file and its source file (expected TDD coupling)."""
        a_base = os.path.basename(a)
        b_base = os.path.basename(b)
        if a_base.startswith("test_") and a_base[5:] == b_base:
            return True
        if b_base.startswith("test_") and b_base[5:] == a_base:
            return True
        return False

    def _detect_coupling(self, commits: list) -> list:
        """Find files that frequently change together (excludes test+source pairs)."""
        pair_counts = Counter()
        pair_commits = {}

        for commit in commits:
            py_files = sorted(set(
                f for f in commit["files"]
                if f.endswith(".py") and not f.startswith(".")
                and not os.path.basename(f).startswith("test_")
            ))
            if len(py_files) < 2 or len(py_files) > 10:
                continue
            for a, b in combinations(py_files, 2):
                if self._is_test_source_pair(a, b):
                    continue
                pair = (a, b)
                pair_counts[pair] += 1
                if pair not in pair_commits:
                    pair_commits[pair] = []
                pair_commits[pair].append(commit["hash"])

        patterns = []
        for (a, b), count in pair_counts.most_common(10):
            if count >= self.min_coupling_count:
                total_a = sum(1 for c in commits if a in c["files"])
                total_b = sum(1 for c in commits if b in c["files"])
                # Jaccard similarity: co-occurrences / union
                union = total_a + total_b - count
                confidence = count / max(union, 1)

                a_short = os.path.basename(a)
                b_short = os.path.basename(b)
                patterns.append(CommitPattern(
                    pattern_type="coupling",
                    description=(
                        f"{a_short} and {b_short} are tightly coupled — "
                        f"changed together in {count}/{union} commits (Jaccard={confidence:.0%}). "
                        f"When modifying {a}, check if {b} also needs updates."
                    ),
                    evidence_count=count,
                    confidence=min(confidence, 1.0),
                    source_commits=pair_commits[(a, b)][:5],
                ))
        return patterns

    def _detect_hotspots(self, commits: list) -> list:
        """Find source files that change very frequently (churn hotspots)."""
        file_counts = Counter()
        for commit in commits:
            for f in commit["files"]:
                if (f.endswith(".py") and not f.startswith(".")
                        and not os.path.basename(f).startswith("test_")):
                    file_counts[f] += 1

        if not file_counts:
            return []

        patterns = []
        total_commits = len(commits)
        for filepath, count in file_counts.most_common(5):
            if count >= self.hotspot_threshold:
                ratio = count / total_commits
                short = os.path.basename(filepath)
                patterns.append(CommitPattern(
                    pattern_type="hotspot",
                    description=(
                        f"{short} is a churn hotspot — changed in {count}/{total_commits} "
                        f"commits ({ratio:.0%}). Consider if this file has too many "
                        f"responsibilities or needs decomposition."
                    ),
                    evidence_count=count,
                    confidence=min(ratio * 2, 1.0),  # Scale up for significance
                    source_commits=[],
                ))
        return patterns

    # Wrap commits are expected to be large — filter them from large_commit detection
    WRAP_PATTERN = re.compile(r"S\d+:?\s*(Session\s+)?[Ww]rap\b")

    def _detect_session_size(self, commits: list) -> list:
        """Detect sessions with unusually large commits (excluding wrap commits)."""
        patterns = []
        for commit in commits:
            file_count = len(commit["files"])
            if file_count >= 12 and not self.WRAP_PATTERN.search(commit.get("message", "")):
                patterns.append(CommitPattern(
                    pattern_type="large_commit",
                    description=(
                        f"Large commit ({file_count} files) in {commit['hash']}: "
                        f"'{commit['message'][:60]}'. Large commits are harder to review "
                        f"and more likely to introduce subtle bugs. Prefer smaller, "
                        f"focused commits."
                    ),
                    evidence_count=1,
                    confidence=0.6,
                    source_commits=[commit["hash"]],
                ))
        return patterns


class SessionPatternDiscoverer:
    """Discovers principles from session journal patterns."""

    def __init__(self, journal_path=None, min_occurrences=3):
        self.journal_path = journal_path or DEFAULT_JOURNAL_PATH
        self.min_occurrences = min_occurrences

    def discover(self) -> list:
        """Analyze journal for recurring patterns."""
        entries = self._load_journal()
        if not entries:
            return []

        patterns = []
        patterns.extend(self._detect_recurring_events(entries, "pain"))
        patterns.extend(self._detect_recurring_events(entries, "win"))
        return patterns

    def _load_journal(self) -> list:
        """Load journal entries."""
        if not os.path.exists(self.journal_path):
            return []
        entries = []
        try:
            with open(self.journal_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []
        return entries

    def _detect_recurring_events(self, entries: list, event_type: str) -> list:
        """Find events of given type that recur across sessions."""
        # Group by tag
        tag_counts = Counter()
        tag_details = {}
        tag_sessions = {}

        for entry in entries:
            if entry.get("type") != event_type:
                continue
            tags = entry.get("tags", [])
            detail = entry.get("detail", "")
            session = entry.get("session", 0)

            for tag in tags:
                tag_counts[tag] += 1
                if tag not in tag_details:
                    tag_details[tag] = detail
                if tag not in tag_sessions:
                    tag_sessions[tag] = set()
                tag_sessions[tag].add(session)

            # Also count by detail text (first 50 chars as key)
            if not tags and detail:
                key = detail[:50]
                tag_counts[key] += 1
                tag_details[key] = detail
                if key not in tag_sessions:
                    tag_sessions[key] = set()
                tag_sessions[key].add(session)

        patterns = []
        for tag, count in tag_counts.most_common(10):
            if count < self.min_occurrences:
                continue

            detail = tag_details.get(tag, tag)
            sessions = tag_sessions.get(tag, set())
            session_count = len(sessions)

            if event_type == "pain":
                description = (
                    f"Recurring pain: '{detail}' — occurred {count} times across "
                    f"{session_count} sessions. This is a systemic issue worth solving."
                )
                ptype = "recurring_pain"
            else:
                description = (
                    f"Proven practice: '{detail}' — success {count} times across "
                    f"{session_count} sessions. Continue applying this pattern."
                )
                ptype = "recurring_win"

            patterns.append(CommitPattern(
                pattern_type=ptype,
                description=description,
                evidence_count=count,
                confidence=min(count / 10.0, 1.0),
                source_commits=[],
            ))

        return patterns


class PrincipleDiscoverer:
    """Top-level orchestrator — runs all discoverers and registers results."""

    # Map pattern types to principle domains
    DOMAIN_MAP = {
        "coupling": "code_quality",
        "hotspot": "code_quality",
        "large_commit": "session_management",
        "recurring_pain": "cca_operations",
        "recurring_win": "cca_operations",
    }

    def __init__(self, project_root=None, principles_path=None,
                 journal_path=None, min_confidence=0.4):
        self.project_root = project_root or PROJECT_ROOT
        self.principles_path = principles_path or DEFAULT_PRINCIPLES_PATH
        self.journal_path = journal_path or DEFAULT_JOURNAL_PATH
        self.min_confidence = min_confidence
        self._registered = 0
        self._skipped = 0

    def discover_all(self) -> list:
        """Run all discoverers and return combined patterns."""
        git_disc = GitPatternDiscoverer(project_root=self.project_root)
        session_disc = SessionPatternDiscoverer(journal_path=self.journal_path)

        all_patterns = []
        all_patterns.extend(git_disc.discover())
        all_patterns.extend(session_disc.discover())
        return all_patterns

    def discover_and_register(self, dry_run=False) -> dict:
        """Discover patterns and register as principles.

        Returns:
            Dict with counts: discovered, registered, skipped.
        """
        patterns = self.discover_all()
        if dry_run:
            return {
                "discovered": len(patterns),
                "registered": 0,
                "skipped": 0,
                "patterns": [
                    {"type": p.pattern_type, "desc": p.description[:80],
                     "confidence": round(p.clamped_confidence, 2),
                     "eff_confidence": round(self._effective_confidence(p), 2),
                     "evidence": p.evidence_count,
                     "would_register": self._effective_confidence(p) >= self.min_confidence}
                    for p in patterns
                ],
            }

        registered = self._register_patterns(patterns)
        return {
            "discovered": len(patterns),
            "registered": registered,
            "skipped": len(patterns) - registered,
        }

    @staticmethod
    def _effective_confidence(pattern) -> float:
        """Compute effective confidence with evidence boost.

        High-evidence patterns get a boost even if raw confidence is low.
        E.g., a hotspot appearing in 18/200 commits has raw conf=0.18 but
        18 appearances is strong evidence — boost to cross the threshold.
        """
        base = pattern.clamped_confidence
        n = pattern.evidence_count
        # Logarithmic evidence boost: +0.12 per doubling above n=4
        if n >= 4:
            import math
            boost = 0.12 * math.log2(n / 4)
            return min(base + boost, 1.0)
        return base

    def _register_patterns(self, patterns: list) -> int:
        """Register patterns as principles. Returns count of newly registered."""
        existing = _load_principles(self.principles_path)
        existing_texts = {p.text.lower().strip() for p in existing.values()}

        count = 0
        for pattern in patterns:
            if self._effective_confidence(pattern) < self.min_confidence:
                continue

            text = pattern.to_principle_text()
            if text.lower().strip() in existing_texts:
                continue

            domain = self.DOMAIN_MAP.get(pattern.pattern_type, "general")
            add_principle(
                text=text,
                source_domain=domain,
                applicable_domains=[domain],
                source_context=f"auto-discovered ({pattern.pattern_type}, "
                               f"evidence={pattern.evidence_count})",
                path=self.principles_path,
            )
            existing_texts.add(text.lower().strip())
            count += 1

        self._registered += count
        return count

    def summary(self) -> str:
        """Return summary of registered principles."""
        principles = _load_principles(self.principles_path)
        auto_discovered = [
            p for p in principles.values()
            if "auto-discovered" in p.source_context
        ]
        return (
            f"Principle registry: {len(principles)} total, "
            f"{len(auto_discovered)} auto-discovered. "
            f"Session registered: {self._registered}."
        )


def parse_args():
    parser = argparse.ArgumentParser(description="Automated principle discovery")
    sub = parser.add_subparsers(dest="command")

    disc = sub.add_parser("discover", help="Discover and register principles")
    disc.add_argument("--dry-run", action="store_true", help="Show what would be discovered")
    disc.add_argument("--project-root", default=None)
    disc.add_argument("--principles-path", default=None)
    disc.add_argument("--journal-path", default=None)
    disc.add_argument("--min-confidence", type=float, default=0.4)

    status = sub.add_parser("status", help="Show discovery status")
    status.add_argument("--principles-path", default=None)

    return parser.parse_args()


def main():
    args = parse_args()

    if args.command == "discover":
        d = PrincipleDiscoverer(
            project_root=args.project_root,
            principles_path=args.principles_path,
            journal_path=args.journal_path,
            min_confidence=args.min_confidence,
        )
        result = d.discover_and_register(dry_run=args.dry_run)
        print(f"Discovered: {result['discovered']} patterns")
        print(f"Registered: {result['registered']} new principles")
        print(f"Skipped: {result['skipped']} (duplicate or low confidence)")
        if args.dry_run and result.get("patterns"):
            print("\nCandidate patterns:")
            for p in result["patterns"]:
                reg = " [REGISTER]" if p.get("would_register") else ""
                print(f"  [{p['type']}] {p['desc']} (conf={p['confidence']}, eff={p.get('eff_confidence', p['confidence'])}, n={p['evidence']}){reg}")

    elif args.command == "status":
        principles_path = args.principles_path or DEFAULT_PRINCIPLES_PATH
        principles = _load_principles(principles_path)
        auto = [p for p in principles.values() if "auto-discovered" in p.source_context]
        print(f"Total principles: {len(principles)}")
        print(f"Auto-discovered: {len(auto)}")
        if auto:
            by_type = Counter()
            for p in auto:
                ctx = p.source_context
                matched = False
                for ptype in ["coupling", "hotspot", "large_commit", "recurring_pain", "recurring_win"]:
                    if ptype in ctx:
                        by_type[ptype] += 1
                        matched = True
                        break
                if not matched:
                    by_type["other"] += 1
            for t, c in by_type.most_common():
                print(f"  {t}: {c}")
    else:
        print("Usage: principle_discoverer.py {discover|status}")
        print("  discover [--dry-run]  — Find and register new principles")
        print("  status                — Show auto-discovery stats")


if __name__ == "__main__":
    main()
