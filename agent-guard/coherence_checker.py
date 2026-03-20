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


# Common stdlib module names — not exhaustive, but covers the vast majority
_STDLIB_MODULES = {
    "abc", "argparse", "ast", "asyncio", "base64", "bisect", "builtins",
    "calendar", "cgi", "cmd", "codecs", "collections", "colorsys",
    "configparser", "contextlib", "copy", "csv", "ctypes", "curses",
    "dataclasses", "datetime", "decimal", "difflib", "dis", "email",
    "enum", "errno", "faulthandler", "fileinput", "fnmatch", "fractions",
    "ftplib", "functools", "gc", "getpass", "gettext", "glob", "gzip",
    "hashlib", "heapq", "hmac", "html", "http", "imaplib", "importlib",
    "inspect", "io", "ipaddress", "itertools", "json", "keyword",
    "linecache", "locale", "logging", "lzma", "math", "mimetypes",
    "multiprocessing", "operator", "os", "pathlib", "pdb", "pickle",
    "platform", "pprint", "profile", "pstats", "py_compile",
    "queue", "random", "re", "readline", "reprlib", "resource",
    "runpy", "sched", "secrets", "select", "shelve", "shlex", "shutil",
    "signal", "site", "smtplib", "socket", "sqlite3", "ssl", "stat",
    "statistics", "string", "struct", "subprocess", "sys", "sysconfig",
    "syslog", "tempfile", "test", "textwrap", "threading", "time",
    "timeit", "token", "tokenize", "trace", "traceback", "tracemalloc",
    "turtle", "types", "typing", "unicodedata", "unittest", "urllib",
    "uuid", "venv", "warnings", "weakref", "webbrowser", "xml",
    "xmlrpc", "zipfile", "zipimport", "zlib",
}

# Import patterns (allow leading whitespace for imports inside try/except/if blocks)
_IMPORT_PATTERN = re.compile(r"^\s*import\s+(\S+)", re.MULTILINE)
_FROM_IMPORT_PATTERN = re.compile(r"^\s*from\s+(\S+)\s+import", re.MULTILINE)


class ImportDependencyCheck:
    """Builds import dependency graph and computes blast radius."""

    def build_graph(self, file_paths: list) -> dict:
        """Build a dependency graph from Python files.

        Args:
            file_paths: List of .py file paths.

        Returns:
            Dict mapping basename -> {"path": str, "imports": [module_names]}.
            Only local (non-stdlib) imports are included.
        """
        # Collect known local module names from file basenames
        local_modules = set()
        for fp in file_paths:
            basename = os.path.basename(fp)
            if basename.endswith(".py"):
                local_modules.add(basename[:-3])  # strip .py

        graph = {}
        for fp in file_paths:
            basename = os.path.basename(fp)
            if not basename.endswith(".py"):
                continue

            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except (OSError, IOError):
                continue

            # Extract all imports
            imports = set()
            for match in _IMPORT_PATTERN.findall(content):
                mod_name = match.split(".")[0]
                if mod_name not in _STDLIB_MODULES and mod_name in local_modules:
                    imports.add(mod_name)

            for match in _FROM_IMPORT_PATTERN.findall(content):
                mod_name = match.split(".")[0]
                if mod_name not in _STDLIB_MODULES and mod_name in local_modules:
                    imports.add(mod_name)

            # Don't count self-imports
            self_name = basename[:-3]
            imports.discard(self_name)

            graph[basename] = {
                "path": fp,
                "imports": sorted(imports),
            }

        return graph

    def find_dependents(self, module_name: str, graph: dict) -> list:
        """Find all files that import a given module.

        Args:
            module_name: Module name (without .py extension).
            graph: Dependency graph from build_graph().

        Returns:
            List of file basenames that depend on this module.
        """
        dependents = []
        for basename, data in graph.items():
            if module_name in data.get("imports", []):
                dependents.append(basename)
        return sorted(dependents)

    def blast_radius(self, module_name: str, graph: dict) -> dict:
        """Compute blast radius for changing a module.

        Args:
            module_name: Module name (without .py).
            graph: Dependency graph.

        Returns:
            Dict with direct_dependents count and list of affected files.
        """
        dependents = self.find_dependents(module_name, graph)
        return {
            "module": module_name,
            "direct_dependents": len(dependents),
            "files": dependents,
        }


# Section headings that contain rules
_RULE_SECTION_PATTERNS = [
    re.compile(r"^##\s+.*(?:non-negotiable|rules|constraints|architecture)\s*(?:rules)?", re.IGNORECASE),
]

# Patterns for stdlib-only rules
_STDLIB_RULE_PATTERN = re.compile(
    r"(?:zero\s+dependenc|no\s+external|stdlib.only|standard\s+library\s+only|no\s+(?:third.party|3rd.party))",
    re.IGNORECASE,
)

# Patterns for "never/no" forbidden action rules
_FORBIDDEN_PATTERN = re.compile(
    r"(?:^|\*\*)\s*(?:never|no\s+blocking|do\s+not|must\s+not)\b",
    re.IGNORECASE,
)

# Extract allowed exceptions from stdlib rule text (e.g., "stdlib + anthropic + fnmatch")
_ALLOWED_EXCEPTION_PATTERN = re.compile(r"\+\s*(\w+)", re.IGNORECASE)


class RuleExtractor:
    """Extracts structured rules from CLAUDE.md content."""

    def extract(self, content: str) -> list:
        """Parse CLAUDE.md content and return list of rule dicts.

        Each rule dict has:
            - text: str — the raw rule text
            - type: str — "stdlib_only", "forbidden", or "general"
            - allowed: list[str] — for stdlib_only rules, explicitly allowed packages

        Args:
            content: Full text of a CLAUDE.md file.

        Returns:
            List of rule dicts.
        """
        if not content or not content.strip():
            return []

        rules = []
        lines = content.splitlines()
        in_rule_section = False

        for line in lines:
            stripped = line.strip()

            # Check if this line is a rule section heading
            if stripped.startswith("##"):
                in_rule_section = any(p.match(stripped) for p in _RULE_SECTION_PATTERNS)
                continue

            # Only extract from rule sections
            if not in_rule_section:
                continue

            # Skip empty lines and non-list items
            if not stripped or not stripped.startswith("-"):
                continue

            # Clean up the rule text (strip leading "- ", bold markers)
            rule_text = stripped.lstrip("- ").strip()
            rule_text = rule_text.replace("**", "")

            if not rule_text:
                continue

            # Classify rule type
            rule_type = "general"
            allowed = []

            if _STDLIB_RULE_PATTERN.search(rule_text):
                rule_type = "stdlib_only"
                # Extract allowed exceptions (e.g., "+ anthropic", "+ fnmatch")
                allowed = _ALLOWED_EXCEPTION_PATTERN.findall(rule_text)
                # Also check for "beyond Python stdlib + X" pattern
                allowed = [a.lower() for a in allowed if a.lower() not in ("python", "stdlib")]
            elif _FORBIDDEN_PATTERN.search(rule_text):
                rule_type = "forbidden"

            rule = {"text": rule_text, "type": rule_type}
            if allowed:
                rule["allowed"] = allowed
            rules.append(rule)

        return rules


class RuleComplianceCheck:
    """Checks code files against extracted CLAUDE.md rules."""

    def check(self, file_path: str, rules: list, local_modules: set = None) -> list:
        """Check a code file against a list of rules.

        Args:
            file_path: Path to the code file.
            rules: List of rule dicts from RuleExtractor.
            local_modules: Set of known local module names (excluded from import checks).

        Returns:
            List of issue strings.
        """
        if not rules:
            return []

        # Only check Python files for import rules
        if not file_path.endswith(".py"):
            return []

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, IOError):
            return []

        issues = []
        basename = os.path.basename(file_path)
        local_mods = local_modules or set()

        for rule in rules:
            if rule["type"] == "stdlib_only":
                rule_issues = self._check_stdlib_only(
                    basename, content, rule, local_mods
                )
                issues.extend(rule_issues)

        return issues

    def _check_stdlib_only(self, basename: str, content: str, rule: dict, local_modules: set) -> list:
        """Check that a file only imports stdlib + allowed + local modules."""
        issues = []
        allowed = set(rule.get("allowed", []))

        # Extract all imports
        for match in _IMPORT_PATTERN.findall(content):
            mod_name = match.split(".")[0]
            if self._is_external(mod_name, allowed, local_modules):
                issues.append(
                    f"{basename}: imports '{mod_name}' — violates rule: {rule['text']}"
                )

        for match in _FROM_IMPORT_PATTERN.findall(content):
            mod_name = match.split(".")[0]
            if self._is_external(mod_name, allowed, local_modules):
                issues.append(
                    f"{basename}: imports '{mod_name}' — violates rule: {rule['text']}"
                )

        return issues

    def _is_external(self, mod_name: str, allowed: set, local_modules: set) -> bool:
        """Return True if module is external (not stdlib, not allowed, not local)."""
        if not mod_name:
            return False
        if mod_name in _STDLIB_MODULES:
            return False
        if mod_name.lower() in allowed:
            return False
        if mod_name in local_modules:
            return False
        # Relative imports (starting with .)
        if mod_name.startswith("."):
            return False
        return True


class CoherenceChecker:
    """Orchestrates all coherence checks across a project."""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.getcwd()
        self._structure = ModuleStructureCheck()
        self._patterns = PatternConsistencyCheck()
        self._rule_extractor = RuleExtractor()
        self._rule_compliance = RuleComplianceCheck()

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

        # 4. CLAUDE.md rule compliance check
        rule_issues = []
        # Collect local module names for import exclusion
        local_modules = set()
        for fp in py_files:
            bn = os.path.basename(fp)
            if bn.endswith(".py"):
                local_modules.add(bn[:-3])

        for mod_name in modules:
            mod_path = os.path.join(self.project_root, mod_name)
            claude_md_path = os.path.join(mod_path, "CLAUDE.md")
            if not os.path.isfile(claude_md_path):
                continue
            try:
                with open(claude_md_path, "r", encoding="utf-8", errors="replace") as f:
                    claude_content = f.read()
            except (OSError, IOError):
                continue

            rules = self._rule_extractor.extract(claude_content)
            if not rules:
                continue

            # Check each .py file in this module against its rules
            for fp in py_files:
                if not fp.startswith(mod_path):
                    continue
                file_rule_issues = self._rule_compliance.check(
                    fp, rules, local_modules=local_modules
                )
                rule_issues.extend(file_rule_issues)

        all_issues.extend(rule_issues)

        # 5. Project-root CLAUDE.md rule compliance (applies to ALL files)
        root_rule_issues = []
        root_claude_md = os.path.join(self.project_root, "CLAUDE.md")
        if os.path.isfile(root_claude_md):
            try:
                with open(root_claude_md, "r", encoding="utf-8", errors="replace") as f:
                    root_content = f.read()
                root_rules = self._rule_extractor.extract(root_content)
                if root_rules:
                    for fp in py_files:
                        file_issues = self._rule_compliance.check(
                            fp, root_rules, local_modules=local_modules
                        )
                        root_rule_issues.extend(file_issues)
            except (OSError, IOError):
                pass

        all_issues.extend(root_rule_issues)

        # Calculate score: start at 100, deduct per issue
        # Structure issues are more severe (5 pts each), pattern issues 3 pts,
        # rule violations 4 pts (more severe than patterns, less than structure)
        deduction = (len(structure_issues) * 5) + (len(pattern_issues) * 3) + (len(rule_issues) * 4) + (len(root_rule_issues) * 4)
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
