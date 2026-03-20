#!/usr/bin/env python3
"""Senior Review Engine — MT-20 Phase 7: On-demand senior developer code review.

Orchestrates existing submodules (SATD, quality scorer, effort scorer) into a
structured code review that reads like feedback from a senior developer colleague.

Usage:
    from senior_review import review_file
    result = review_file("/path/to/file.py")
    # result is a dict with: file_path, verdict, concerns, suggestions, metrics

Verdicts:
    - approve: Clean code, no blocking issues
    - conditional: Issues found but not blocking — fix before merging
    - rethink: Structural problems — needs redesign before proceeding
    - error: File not found or unreadable
"""

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
if _MODULE_DIR not in sys.path:
    sys.path.insert(0, _MODULE_DIR)

from satd_detector import SATDDetector, SATDLevel
from code_quality_scorer import CodeQualityScorer
from effort_scorer import EffortScorer
from coherence_checker import CoherenceChecker, ImportDependencyCheck
from fp_filter import FPFilter
from adr_reader import ADRReader
from git_context import GitContext

# Code file extensions we perform deep analysis on
_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp",
    ".h", ".hpp", ".rb", ".sh", ".bash", ".zsh",
}

# Thresholds
_LOC_LARGE_FILE = 400
_LOC_VERY_LARGE_FILE = 800
_HIGH_SATD_THRESHOLD = 3       # 3+ HIGH-severity SATD markers = concern
_TOTAL_SATD_THRESHOLD = 5     # 5+ total SATD markers = concern
_QUALITY_CONDITIONAL = 60      # Quality score below 60 = conditional
_QUALITY_RETHINK = 40          # Quality score below 40 = rethink
_EFFORT_HIGH = 4               # Effort score 4+ = concern


class ReviewVerdict(Enum):
    APPROVE = "approve"
    CONDITIONAL = "conditional"
    RETHINK = "rethink"


@dataclass
class ReviewResult:
    """Structured review output."""
    file_path: str
    verdict: str
    concerns: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "verdict": self.verdict,
            "concerns": self.concerns,
            "suggestions": self.suggestions,
            "metrics": self.metrics,
            "error": self.error,
        }


def _get_extension(file_path: str) -> str:
    """Return lowercase file extension including dot."""
    basename = os.path.basename(file_path)
    if "." not in basename:
        return ""
    return "." + basename.rsplit(".", 1)[-1].lower()


def _is_code_file(file_path: str) -> bool:
    """Check if file is a code file worth deep analysis."""
    return _get_extension(file_path) in _CODE_EXTENSIONS


class SeniorReview:
    """Orchestrates submodules into a structured senior developer review."""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root
        self._satd = SATDDetector()
        self._quality = CodeQualityScorer()
        self._effort = EffortScorer()
        self._fp_filter = FPFilter()
        self._adr_reader = ADRReader()

    def review(self, file_path: str, content: Optional[str] = None) -> ReviewResult:
        """Review a file and produce structured feedback.

        Args:
            file_path: Path to the file to review.
            content: Optional pre-read content. If None, reads from disk.

        Returns:
            ReviewResult with verdict, concerns, suggestions, and metrics.
        """
        # Read file if content not provided
        if content is None:
            if not os.path.isfile(file_path):
                return ReviewResult(
                    file_path=file_path,
                    verdict="error",
                    error=f"File not found: {file_path}",
                )
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except (OSError, IOError) as e:
                return ReviewResult(
                    file_path=file_path,
                    verdict="error",
                    error=f"Cannot read file: {e}",
                )

        # Empty files pass trivially
        if not content or not content.strip():
            return ReviewResult(
                file_path=file_path,
                verdict="approve",
                metrics={"loc": 0},
            )

        # Non-code files get minimal analysis
        if not _is_code_file(file_path):
            loc = len([l for l in content.splitlines() if l.strip()])
            return ReviewResult(
                file_path=file_path,
                verdict="approve",
                metrics={"loc": loc, "type": "non-code"},
            )

        # Run all analyzers
        concerns = []
        suggestions = []

        # 0. FP confidence — determines how much we trust findings from this file
        fp_confidence = self._fp_filter.confidence(file_path)

        # Vendored files get minimal review — skip deep analysis
        if self._fp_filter.should_skip(file_path):
            loc = len([l for l in content.splitlines() if l.strip()])
            return ReviewResult(
                file_path=file_path,
                verdict="approve",
                metrics={"loc": loc, "type": "vendored", "fp_confidence": 0.0,
                         "satd_total": 0, "satd_high": 0},
            )

        # 1. Quality score
        quality_report = self._quality.score(content, file_path=file_path)
        loc = quality_report.loc

        # 2. SATD markers (filtered by fp_filter)
        raw_satd_markers = self._satd.scan_file_content(content, file_path=file_path)
        # Convert to dicts for fp_filter, then back
        satd_dicts = [{"severity": m.level.name, "line": m.line, "text": m.text, "marker": m}
                      for m in raw_satd_markers]
        filtered_dicts = self._fp_filter.filter_findings(satd_dicts, file_path)
        satd_markers = [d["marker"] for d in filtered_dicts]
        high_satd = [m for m in satd_markers if m.level == SATDLevel.HIGH]

        # 3. Effort score
        effort_result = self._effort.score_content(content, file_path=file_path)

        # 4. Coherence check (if project_root is set)
        coherence_issues = []
        blast_radius = {}
        if self.project_root and os.path.isdir(self.project_root):
            try:
                coherence = CoherenceChecker(project_root=self.project_root)
                report = coherence.check()
                coherence_issues = report.issues
            except Exception:
                pass  # Coherence check is advisory, never blocks

            # 5. Blast radius — what depends on this file?
            try:
                dep_checker = ImportDependencyCheck()
                # Find sibling .py files in same directory
                file_dir = os.path.dirname(os.path.abspath(file_path))
                sibling_files = [
                    os.path.join(file_dir, f)
                    for f in os.listdir(file_dir)
                    if f.endswith(".py") and not f.startswith("__")
                ]
                if sibling_files:
                    graph = dep_checker.build_graph(sibling_files)
                    module_name = os.path.basename(file_path).replace(".py", "")
                    blast_radius = dep_checker.blast_radius(module_name, graph)
            except Exception:
                pass  # Blast radius is advisory

        # 6. ADR relevance — surface architectural decisions related to this file
        relevant_adrs = []
        if self.project_root and os.path.isdir(self.project_root):
            try:
                adrs = self._adr_reader.discover(self.project_root)
                if adrs:
                    relevant_adrs = self._adr_reader.find_relevant(
                        adrs, file_path, content
                    )
            except Exception:
                pass  # ADR check is advisory, never blocks

        # 7. Git history context
        git_history = None
        git_churn = False
        git_commit_count = 0
        if self.project_root and os.path.isdir(self.project_root):
            try:
                git = GitContext(self.project_root)
                if git.is_git_repo:
                    # Get relative path for git commands
                    abs_path = os.path.abspath(file_path)
                    abs_root = os.path.abspath(self.project_root)
                    if abs_path.startswith(abs_root):
                        rel_path = os.path.relpath(abs_path, abs_root)
                    else:
                        rel_path = file_path
                    git_history = git.file_history(rel_path, max_commits=5)
                    git_commit_count = git_history.total_commits
                    git_churn = git.is_high_churn(rel_path)
            except Exception:
                pass  # Git context is advisory, never blocks

        # Build metrics dict
        metrics = {
            "loc": loc,
            "quality_score": round(quality_report.overall_score, 1),
            "quality_grade": quality_report.grade,
            "effort_score": effort_result.score,
            "effort_label": effort_result.label,
            "satd_total": len(satd_markers),
            "satd_high": len(high_satd),
            "complexity": effort_result.complexity,
            "coherence_issues": len(coherence_issues),
            "blast_radius": blast_radius.get("direct_dependents", 0),
            "blast_files": blast_radius.get("files", []),
            "fp_confidence": fp_confidence,
            "relevant_adrs": len(relevant_adrs),
            "git_commits": git_commit_count,
            "git_high_churn": git_churn,
        }

        # Generate concerns from analysis
        # ADR concerns (architectural decisions)
        for adr in relevant_adrs:
            if adr.status == "deprecated":
                short = adr.summary[:80] + "..." if len(adr.summary) > 80 else adr.summary
                concerns.append(
                    f"Deprecated ADR: '{adr.title}' — {short}. "
                    f"This file may be using a deprecated pattern."
                )
            elif adr.status == "accepted":
                short = adr.summary[:80] + "..." if len(adr.summary) > 80 else adr.summary
                suggestions.append(
                    f"Related ADR: '{adr.title}' — {short}"
                )

        # Coherence concerns (project-level patterns)
        if coherence_issues:
            # Only surface issues relevant to the file being reviewed
            file_basename = os.path.basename(file_path)
            relevant = [i for i in coherence_issues if file_basename in i]
            for issue in relevant:
                concerns.append(f"Coherence: {issue}")

        # Blast radius concern
        br_count = blast_radius.get("direct_dependents", 0)
        if br_count >= 3:
            br_files = ", ".join(blast_radius.get("files", [])[:5])
            concerns.append(
                f"High blast radius: {br_count} files depend on this module ({br_files}). "
                f"Changes here ripple outward — test dependents after modifying."
            )

        # Size concerns
        if loc > _LOC_VERY_LARGE_FILE:
            concerns.append(
                f"Very large file ({loc} LOC). Files above {_LOC_VERY_LARGE_FILE} LOC "
                f"degrade review quality and increase merge conflict risk. "
                f"Consider splitting into focused modules."
            )
        elif loc > _LOC_LARGE_FILE:
            concerns.append(
                f"Large file ({loc} LOC). Atlassian research shows review effectiveness "
                f"drops sharply above {_LOC_LARGE_FILE} LOC."
            )

        # SATD concerns
        if len(high_satd) >= _HIGH_SATD_THRESHOLD:
            marker_lines = ", ".join(f"L{m.line}" for m in high_satd[:5])
            concerns.append(
                f"{len(high_satd)} HIGH-severity debt markers (HACK/FIXME/WORKAROUND) "
                f"at {marker_lines}. These indicate known broken or fragile code."
            )
        elif len(satd_markers) >= _TOTAL_SATD_THRESHOLD:
            concerns.append(
                f"{len(satd_markers)} technical debt markers found. "
                f"Consider addressing them before they accumulate further."
            )

        # Quality concerns
        if quality_report.overall_score < _QUALITY_RETHINK:
            concerns.append(
                f"Quality score {quality_report.overall_score:.0f}/100 (grade {quality_report.grade}). "
                f"Multiple quality dimensions are below acceptable thresholds."
            )
        elif quality_report.overall_score < _QUALITY_CONDITIONAL:
            concerns.append(
                f"Quality score {quality_report.overall_score:.0f}/100 (grade {quality_report.grade}). "
                f"Review the dimension breakdown for specific improvement areas."
            )

        # Effort/complexity concerns
        if effort_result.score >= _EFFORT_HIGH:
            concerns.append(
                f"Review effort: {effort_result.label} ({effort_result.score}/5). "
                f"{effort_result.complexity} complexity markers suggest high cognitive load."
            )

        # Git history concerns
        if git_churn:
            concerns.append(
                f"High churn file ({git_commit_count} commits). Frequently changed files "
                f"are higher risk — extra care with testing and review."
            )
        if git_history and git_history.commits:
            last_commit = git_history.commits[0]
            suggestions.append(
                f"Last changed {last_commit.date} by {last_commit.author}: "
                f"{last_commit.summary}"
            )

        # Generate suggestions based on dimension scores
        for dim in quality_report.dimensions:
            if dim.score < 60:
                suggestions.append(f"{dim.name}: {dim.detail}")

        # Determine verdict
        verdict = self._determine_verdict(
            quality_score=quality_report.overall_score,
            high_satd_count=len(high_satd),
            total_satd_count=len(satd_markers),
            loc=loc,
            effort_score=effort_result.score,
        )

        return ReviewResult(
            file_path=file_path,
            verdict=verdict,
            concerns=concerns,
            suggestions=suggestions,
            metrics=metrics,
        )

    def _determine_verdict(
        self,
        quality_score: float,
        high_satd_count: int,
        total_satd_count: int,
        loc: int,
        effort_score: int,
    ) -> str:
        """Determine review verdict based on aggregated signals.

        Verdict logic:
        - RETHINK if quality < 40 OR high SATD >= 5 OR LOC > 1000
        - CONDITIONAL if quality < 60 OR high SATD >= 3 OR effort >= 4
        - APPROVE otherwise
        """
        # Rethink triggers (structural problems)
        if quality_score < _QUALITY_RETHINK:
            return ReviewVerdict.RETHINK.value
        if high_satd_count >= 5:
            return ReviewVerdict.RETHINK.value
        if loc > 1000:
            return ReviewVerdict.RETHINK.value

        # Conditional triggers (fixable issues)
        if quality_score < _QUALITY_CONDITIONAL:
            return ReviewVerdict.CONDITIONAL.value
        if high_satd_count >= _HIGH_SATD_THRESHOLD:
            return ReviewVerdict.CONDITIONAL.value
        if total_satd_count >= _TOTAL_SATD_THRESHOLD:
            return ReviewVerdict.CONDITIONAL.value
        if effort_score >= _EFFORT_HIGH:
            return ReviewVerdict.CONDITIONAL.value

        return ReviewVerdict.APPROVE.value


def review_file(file_path: str, project_root: str = "") -> dict:
    """Convenience function: review a file and return dict result.

    Args:
        file_path: Path to the file to review.
        project_root: Optional project root for context.

    Returns:
        Dict with keys: file_path, verdict, concerns, suggestions, metrics, error.
    """
    reviewer = SeniorReview(project_root=project_root)
    result = reviewer.review(file_path)
    return result.to_dict()
