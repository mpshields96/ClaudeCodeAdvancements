#!/usr/bin/env python3
"""Architectural Coherence Checker — MT-20 Phase 9: Cross-project pattern enforcement.

Answers the question a senior developer would ask: "Does this project follow
consistent patterns, and does this file fit those patterns?"

Checks:
1. Module structure — do all modules have tests/, CLAUDE.md?
2. Pattern consistency — are naming, docstrings, imports consistent across files?
3. Auto-discovers modules by looking for directories with CLAUDE.md files.

Usage:
    from coherence_checker import check_coherence
    result = check_coherence("/path/to/project")
    # result is a dict with: project_root, modules_checked, files_checked, issues, score
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional


# Expected files in a well-structured module directory
_EXPECTED_MODULE_FILES = {
    "tests": "directory",
    "CLAUDE.md": "file",
}

# Python file extensions to analyze
_PY_EXTENSIONS = {".py"}

# camelCase function/variable pattern (not class names which are CamelCase by convention)
_CAMEL_CASE_FUNC = re.compile(r"^def\s+([a-z][a-z0-9]*[A-Z][a-zA-Z0-9]*)\s*\(", re.MULTILINE)
_CAMEL_CASE_VAR = re.compile(r"^\s+([a-z][a-z0-9]*[A-Z][a-zA-Z0-9]*)\s*=", re.MULTILINE)

# Module docstring detection — first non-comment, non-blank line should be a docstring
_MODULE_DOCSTRING = re.compile(r'^(?:\s*#[^\n]*\n)*\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')')


@dataclass
class CoherenceReport:
    """Result of a coherence check across the project."""
    project_root: str
    modules_checked: int
    files_checked: int
    issues: list = field(default_factory=list)
    score: float = 100.0

    def to_dict(self) -> dict:
        return {
            "project_root": self.project_root,
            "modules_checked": self.modules_checked,
            "files_checked": self.files_checked,
            "issues": self.issues,
            "score": round(self.score, 1),
        }


class ModuleStructureCheck:
    """Checks that module directories follow consistent structure."""

    def check(self, project_root: str, modules: list) -> list:
        """Check each module directory for expected files.

        Args:
            project_root: Project root directory.
            modules: List of module directory names to check.

        Returns:
            List of issue strings.
        """
        issues = []
        for mod_name in modules:
            mod_path = os.path.join(project_root, mod_name)
            if not os.path.isdir(mod_path):
                issues.append(f"{mod_name}: module directory does not exist")
                continue

            for expected, kind in _EXPECTED_MODULE_FILES.items():
                full_path = os.path.join(mod_path, expected)
                if kind == "directory" and not os.path.isdir(full_path):
                    issues.append(f"{mod_name}: missing tests/ directory")
                elif kind == "file" and not os.path.isfile(full_path):
                    issues.append(f"{mod_name}: missing CLAUDE.md (module rules)")

        return issues


class PatternConsistencyCheck:
    """Checks cross-file pattern consistency (naming, docstrings, style)."""

    def check(self, file_paths: list) -> list:
        """Analyze multiple Python files for consistency issues.

        Args:
            file_paths: List of .py file paths to analyze.

        Returns:
            List of issue strings.
        """
        issues = []
        py_files = [f for f in file_paths if f.endswith(".py")]

        if len(py_files) < 2:
            return issues

        # Collect per-file analysis
        file_data = []
        for fp in py_files:
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except (OSError, IOError):
                continue

            basename = os.path.basename(fp)
            has_docstring = bool(_MODULE_DOCSTRING.match(content))
            camel_funcs = _CAMEL_CASE_FUNC.findall(content)
            camel_vars = _CAMEL_CASE_VAR.findall(content)

            file_data.append({
                "path": fp,
                "basename": basename,
                "has_docstring": has_docstring,
                "camel_funcs": camel_funcs,
                "camel_vars": camel_vars,
                "content": content,
            })

        if not file_data:
            return issues

        # Check 1: Module docstring consistency
        with_docstring = [d for d in file_data if d["has_docstring"]]
        without_docstring = [d for d in file_data if not d["has_docstring"]]

        # If at least half have docstrings but some don't, flag the inconsistency
        if len(with_docstring) >= len(without_docstring) and without_docstring:
            for fd in without_docstring:
                issues.append(
                    f"{fd['basename']}: missing module docstring "
                    f"({len(with_docstring)}/{len(file_data)} files have one)"
                )

        # Check 2: Naming convention consistency (camelCase in a snake_case project)
        files_with_camel = []
        for fd in file_data:
            if fd["camel_funcs"] or fd["camel_vars"]:
                examples = fd["camel_funcs"][:2] + fd["camel_vars"][:2]
                files_with_camel.append((fd["basename"], examples))

        files_without_camel = len(file_data) - len(files_with_camel)
        if files_with_camel and files_without_camel >= len(files_with_camel):
            for basename, examples in files_with_camel:
                example_str = ", ".join(examples[:3])
                issues.append(
                    f"{basename}: uses camelCase naming ({example_str}) "
                    f"while {files_without_camel}/{len(file_data)} files use snake_case"
                )

        return issues


class CoherenceChecker:
    """Orchestrates all coherence checks across a project."""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.getcwd()
        self._structure = ModuleStructureCheck()
        self._patterns = PatternConsistencyCheck()

    def check(self, modules: Optional[list] = None) -> CoherenceReport:
        """Run all coherence checks.

        Args:
            modules: Optional list of module directory names. If None, auto-discovers
                     modules by looking for directories containing CLAUDE.md.

        Returns:
            CoherenceReport with issues and score.
        """
        # Auto-discover modules if not specified
        if modules is None:
            modules = self._discover_modules()

        all_issues = []

        # 1. Module structure check
        structure_issues = self._structure.check(self.project_root, modules)
        all_issues.extend(structure_issues)

        # 2. Collect all Python files across modules
        py_files = []
        for mod_name in modules:
            mod_path = os.path.join(self.project_root, mod_name)
            if not os.path.isdir(mod_path):
                continue
            for fname in os.listdir(mod_path):
                if fname.endswith(".py") and not fname.startswith("__"):
                    py_files.append(os.path.join(mod_path, fname))

        # 3. Pattern consistency check
        pattern_issues = self._patterns.check(py_files)
        all_issues.extend(pattern_issues)

        # Calculate score: start at 100, deduct per issue
        # Structure issues are more severe (5 pts each), pattern issues 3 pts each
        deduction = (len(structure_issues) * 5) + (len(pattern_issues) * 3)
        score = max(0.0, min(100.0, 100.0 - deduction))

        return CoherenceReport(
            project_root=self.project_root,
            modules_checked=len(modules),
            files_checked=len(py_files),
            issues=all_issues,
            score=score,
        )

    def _discover_modules(self) -> list:
        """Auto-discover module directories by looking for CLAUDE.md files."""
        modules = []
        try:
            entries = os.listdir(self.project_root)
        except OSError:
            return modules

        for entry in sorted(entries):
            entry_path = os.path.join(self.project_root, entry)
            if os.path.isdir(entry_path):
                claude_md = os.path.join(entry_path, "CLAUDE.md")
                if os.path.isfile(claude_md):
                    modules.append(entry)

        return modules


def check_coherence(project_root: str, modules: Optional[list] = None) -> dict:
    """Convenience function: check project coherence and return dict.

    Args:
        project_root: Path to the project root.
        modules: Optional list of module names to check.

    Returns:
        Dict with keys: project_root, modules_checked, files_checked, issues, score.
    """
    checker = CoherenceChecker(project_root=project_root)
    report = checker.check(modules=modules)
    return report.to_dict()
