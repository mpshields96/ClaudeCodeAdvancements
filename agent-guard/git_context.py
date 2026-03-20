#!/usr/bin/env python3
"""Git Context — MT-20: Git history awareness for senior developer reviews.

Extracts git history, blame ownership, and churn metrics for a file to give
the senior review engine project context. Answers: who changed this, when,
why, and how often.

Uses subprocess to call git — stdlib only, no external dependencies.
Gracefully handles non-git repos and missing files.
"""

import os
import subprocess
from dataclasses import dataclass, field


@dataclass
class CommitInfo:
    """One commit that touched a file."""
    sha: str
    author: str
    date: str
    message: str

    @property
    def summary(self) -> str:
        """Truncated one-line summary of the commit message."""
        first_line = self.message.split("\n")[0]
        if len(first_line) > 80:
            return first_line[:77] + "..."
        return first_line


@dataclass
class FileHistory:
    """Git history for a single file."""
    file_path: str
    commits: list  # list of CommitInfo
    total_commits: int = 0


@dataclass
class BlameOwnership:
    """How much of a file one author owns."""
    author: str
    lines: int
    percentage: float


class GitContext:
    """Extract git history context for files.

    All methods are safe to call on non-git repos — they return empty results.
    """

    def __init__(self, repo_root: str):
        self.repo_root = repo_root
        self.is_git_repo = self._check_git_repo()

    def _check_git_repo(self) -> bool:
        """Check if repo_root is inside a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.repo_root,
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return False

    def _run_git(self, args: list) -> str:
        """Run a git command and return stdout. Returns '' on any error."""
        if not self.is_git_repo:
            return ""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_root,
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return ""
            return result.stdout
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return ""

    def file_history(self, file_path: str, max_commits: int = 10) -> FileHistory:
        """Get commit history for a file.

        Args:
            file_path: Path relative to repo root.
            max_commits: Maximum number of recent commits to return.

        Returns:
            FileHistory with recent commits and total count.
        """
        if not self.is_git_repo:
            return FileHistory(file_path=file_path, commits=[], total_commits=0)

        # Get total commit count
        count_output = self._run_git([
            "rev-list", "--count", "HEAD", "--", file_path
        ])
        total = int(count_output.strip()) if count_output.strip().isdigit() else 0

        # Get recent commits with structured format
        # Format: sha|author|date|message (use | as separator since it's rare in messages)
        log_output = self._run_git([
            "log", f"--max-count={max_commits}",
            "--format=%H|%an|%as|%s",
            "--", file_path,
        ])

        commits = []
        for line in log_output.strip().splitlines():
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commits.append(CommitInfo(
                    sha=parts[0][:8],
                    author=parts[1],
                    date=parts[2],
                    message=parts[3],
                ))

        return FileHistory(
            file_path=file_path,
            commits=commits,
            total_commits=total,
        )

    def blame_summary(self, file_path: str) -> list:
        """Get blame ownership breakdown for a file.

        Returns a list of BlameOwnership sorted by percentage (highest first).
        """
        if not self.is_git_repo:
            return []

        output = self._run_git(["blame", "--porcelain", file_path])
        if not output:
            return []

        # Count lines per author from porcelain blame
        author_lines = {}
        current_author = None
        for line in output.splitlines():
            if line.startswith("author "):
                current_author = line[7:]
            elif line.startswith("\t") and current_author:
                author_lines[current_author] = author_lines.get(current_author, 0) + 1

        total_lines = sum(author_lines.values())
        if total_lines == 0:
            return []

        owners = []
        for author, lines in author_lines.items():
            owners.append(BlameOwnership(
                author=author,
                lines=lines,
                percentage=round(lines / total_lines * 100, 1),
            ))

        return sorted(owners, key=lambda o: o.percentage, reverse=True)

    def commit_count(self, file_path: str) -> int:
        """Get total number of commits that touched a file."""
        if not self.is_git_repo:
            return 0
        output = self._run_git(["rev-list", "--count", "HEAD", "--", file_path])
        return int(output.strip()) if output.strip().isdigit() else 0

    def is_high_churn(self, file_path: str, threshold: int = 15) -> bool:
        """Check if a file has been changed frequently (high churn).

        Args:
            file_path: Path relative to repo root.
            threshold: Number of commits above which a file is "high churn".

        Returns:
            True if commit count exceeds threshold.
        """
        return self.commit_count(file_path) > threshold

    def format_for_review(self, file_path: str, max_commits: int = 5) -> str:
        """Format git context as natural language for inclusion in reviews.

        Args:
            file_path: Path relative to repo root.
            max_commits: How many recent commits to show.

        Returns:
            Formatted string suitable for review context.
        """
        if not self.is_git_repo:
            return "Not a git repository — no history available."

        history = self.file_history(file_path, max_commits=max_commits)
        if not history.commits:
            return f"No git history for {file_path}."

        lines = []
        lines.append(f"Git history ({history.total_commits} total commits):")

        for c in history.commits:
            lines.append(f"  {c.date} {c.author}: {c.summary}")

        # Ownership
        owners = self.blame_summary(file_path)
        if owners:
            top_owners = owners[:3]
            owner_parts = [f"{o.author} ({o.percentage}%)" for o in top_owners]
            lines.append(f"Ownership: {', '.join(owner_parts)}")

        # Churn
        if self.is_high_churn(file_path):
            lines.append("Note: This file changes frequently — review changes carefully.")

        return "\n".join(lines)
