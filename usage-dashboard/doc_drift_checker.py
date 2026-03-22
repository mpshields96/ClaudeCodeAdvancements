#!/usr/bin/env python3
"""
doc_drift_checker.py — Automated Documentation Accuracy Verification

Problem: PROJECT_INDEX.md and ROADMAP.md test counts, module lists, and file
paths drift from reality over time. The ROADMAP was 43 sessions stale before
S68 caught it manually. This tool catches drift automatically.

Checks:
1. Test counts per module: claimed vs actual (AST-counted test methods)
2. Total test count: claimed vs actual
3. Suite count: claimed vs actual
4. File paths: documented files that don't exist on disk
5. Roadmap vs PROJECT_INDEX consistency

Usage:
    python3 doc_drift_checker.py                # Full drift report
    python3 doc_drift_checker.py --json         # JSON output (for hooks/CI)
    python3 doc_drift_checker.py --quiet        # Exit code only (0=clean, 1=drift)
    python3 doc_drift_checker.py --root /path   # Explicit project root

Stdlib only. No external dependencies.
"""

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Default modules to check
DEFAULT_MODULES = [
    "memory-system",
    "spec-system",
    "context-monitor",
    "agent-guard",
    "usage-dashboard",
    "reddit-intelligence",
    "self-learning",
    "design-skills",
    "research",
]


@dataclass
class TestCountMismatch:
    source: str       # Which doc file (PROJECT_INDEX.md, ROADMAP.md)
    module: str       # Module name
    claimed: int      # What the doc says
    actual: int       # What actually exists


@dataclass
class DriftReport:
    test_mismatches: List[TestCountMismatch] = field(default_factory=list)
    missing_files: List[str] = field(default_factory=list)
    total_claimed: Optional[int] = None
    total_actual: Optional[int] = None
    suite_claimed: Optional[int] = None
    suite_actual: Optional[int] = None

    @property
    def has_drift(self) -> bool:
        return bool(self.test_mismatches) or bool(self.missing_files)

    def format(self) -> str:
        lines = ["=== Doc Drift Report ===", ""]

        if not self.has_drift:
            lines.append("No drift detected. Docs match codebase.")
            if self.total_actual is not None:
                lines.append(f"Total tests: {self.total_actual}")
            if self.suite_actual is not None:
                lines.append(f"Total suites: {self.suite_actual}")
            return "\n".join(lines)

        # Test count mismatches
        if self.test_mismatches:
            lines.append("TEST COUNT MISMATCHES:")
            for m in self.test_mismatches:
                delta = m.actual - m.claimed
                sign = "+" if delta > 0 else ""
                lines.append(
                    f"  [{m.source}] {m.module}: "
                    f"claimed={m.claimed}, actual={m.actual} ({sign}{delta})"
                )
            lines.append("")

        # Missing files
        if self.missing_files:
            lines.append("MISSING FILES (documented but not on disk):")
            for f in self.missing_files:
                lines.append(f"  {f}")
            lines.append("")

        # Totals
        if self.total_claimed is not None and self.total_actual is not None:
            match = "MATCH" if self.total_claimed == self.total_actual else "MISMATCH"
            lines.append(
                f"Total tests: claimed={self.total_claimed}, "
                f"actual={self.total_actual} [{match}]"
            )

        if self.suite_claimed is not None and self.suite_actual is not None:
            match = "MATCH" if self.suite_claimed == self.suite_actual else "MISMATCH"
            lines.append(
                f"Total suites: claimed={self.suite_claimed}, "
                f"actual={self.suite_actual} [{match}]"
            )

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "has_drift": self.has_drift,
            "test_mismatches": [
                {
                    "source": m.source,
                    "module": m.module,
                    "claimed": m.claimed,
                    "actual": m.actual,
                }
                for m in self.test_mismatches
            ],
            "missing_files": self.missing_files,
            "total_claimed": self.total_claimed,
            "total_actual": self.total_actual,
            "suite_claimed": self.suite_claimed,
            "suite_actual": self.suite_actual,
        }


# --- Parsing functions ---

def parse_module_test_counts(content: str) -> Dict[str, int]:
    """Parse module test counts from PROJECT_INDEX.md Module Map table.

    Expects rows like:
        | Memory System | `memory-system/` | COMPLETE | 228 |
    """
    counts = {}
    # Match table rows with backtick-wrapped module paths
    pattern = re.compile(
        r'\|\s*[^|]+\s*\|\s*`([^`/]+)/`\s*\|\s*[^|]+\s*\|\s*(\d+)\s*\|'
    )
    for match in pattern.finditer(content):
        module_name = match.group(1)
        test_count = int(match.group(2))
        counts[module_name] = test_count
    return counts


def parse_total_test_count(content: str) -> Optional[int]:
    """Parse the total test count from PROJECT_INDEX.md.

    Expects: **Total: 2279 tests (54 suites).**
    """
    pattern = re.compile(r'\*\*Total:\s*~?(\d+)\s*tests')
    match = pattern.search(content)
    if match:
        return int(match.group(1))
    return None


def parse_suite_count(content: str) -> Optional[int]:
    """Parse the suite count from PROJECT_INDEX.md.

    Expects: **Total: 2279 tests (54 suites).**
    """
    pattern = re.compile(r'\((\d+)\s*suites?\)')
    match = pattern.search(content)
    if match:
        return int(match.group(1))
    return None


def parse_roadmap_test_table(content: str) -> Dict[str, int]:
    """Parse test counts from ROADMAP.md Total Test Coverage table.

    Expects rows like:
        | memory-system | 229 |
    Skips the bold total row.
    """
    counts = {}
    pattern = re.compile(r'\|\s*([a-z][a-z0-9-]+)\s*\|\s*(\d+)\s*\|')
    for match in pattern.finditer(content):
        module_name = match.group(1)
        test_count = int(match.group(2))
        counts[module_name] = test_count
    return counts


def parse_roadmap_total(content: str) -> Optional[int]:
    """Parse total from ROADMAP.md bold total row.

    Expects: | **Total** | **2260** |
    """
    pattern = re.compile(r'\|\s*\*\*Total\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|')
    match = pattern.search(content)
    if match:
        return int(match.group(1))
    return None


# --- Actual test counting ---

def count_tests_in_file(filepath: str) -> int:
    """Count test methods (def test_*) in a Python file using AST."""
    try:
        content = Path(filepath).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=filepath)
    except (SyntaxError, OSError):
        return 0

    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                count += 1
    return count


def count_module_tests(module_dir: Path) -> int:
    """Count all test methods across all test_*.py files in a module."""
    tests_dir = module_dir / "tests"
    if not tests_dir.is_dir():
        return 0

    total = 0
    for root, dirs, files in os.walk(tests_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.startswith("test_") and f.endswith(".py"):
                total += count_tests_in_file(os.path.join(root, f))
    return total


def count_test_suites(project_root: Path, modules: List[str]) -> int:
    """Count total number of test_*.py files across all modules + top-level tests/."""
    count = 0
    for mod_name in modules:
        tests_dir = project_root / mod_name / "tests"
        if tests_dir.is_dir():
            for root, dirs, files in os.walk(tests_dir):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for f in files:
                    if f.startswith("test_") and f.endswith(".py"):
                        count += 1

    # Also check top-level tests/ directory
    top_tests = project_root / "tests"
    if top_tests.is_dir():
        for f in top_tests.iterdir():
            if f.name.startswith("test_") and f.name.endswith(".py"):
                count += 1

    return count


# --- File path checking ---

def extract_backtick_paths(content: str) -> List[str]:
    """Extract file paths from backtick-wrapped references in markdown.

    Only includes paths that look like real files (contain a dot for extension).
    Excludes directories (ending in /), slash commands (/foo:bar), and bare words.
    """
    pattern = re.compile(r'`([^`]+)`')
    paths = []
    for match in pattern.finditer(content):
        candidate = match.group(1)
        # Must contain a dot (file extension) but not start with /
        # and not end with /
        if (
            "." in candidate
            and not candidate.startswith("/")
            and not candidate.endswith("/")
            and not candidate.startswith("$")
            and "/" not in candidate or candidate.count("/") <= 3
        ):
            # Filter out things that are clearly not file paths
            if re.match(r'^[a-zA-Z0-9_./-]+\.\w+$', candidate):
                paths.append(candidate)
    return paths


def extract_module_files(content: str) -> Dict[str, List[str]]:
    """Extract per-module file paths from PROJECT_INDEX.md Key Files section.

    Expects blocks like:
        **memory-system/** — description
        - `hooks/capture_hook.py` — description
        - `memory_store.py` — description
    """
    modules = {}
    current_module = None

    for line in content.splitlines():
        # Check for module header: **module-name/** — description
        mod_match = re.match(r'\*\*([a-z][a-z0-9-]+)/\*\*', line)
        if mod_match:
            current_module = mod_match.group(1)
            modules[current_module] = []
            continue

        # Check for file entry under current module
        if current_module and line.strip().startswith("- `"):
            file_match = re.match(r'\s*-\s*`([^`]+\.py)`', line)
            if file_match:
                modules[current_module].append(file_match.group(1))

    return modules


def check_paths_exist(
    paths: List[str], base_dir: Path
) -> Tuple[List[str], List[str]]:
    """Check which paths exist relative to base_dir.

    Returns (existing, missing).
    """
    existing = []
    missing = []
    for p in paths:
        if (base_dir / p).exists():
            existing.append(p)
        else:
            missing.append(p)
    return existing, missing


# --- Main orchestration ---

def run_drift_check(
    project_root: Path,
    modules: Optional[List[str]] = None,
) -> DriftReport:
    """Run the full doc drift check."""
    if modules is None:
        modules = DEFAULT_MODULES

    report = DriftReport()

    # Read docs
    pi_path = project_root / "PROJECT_INDEX.md"
    rm_path = project_root / "ROADMAP.md"

    pi_content = ""
    rm_content = ""
    if pi_path.is_file():
        pi_content = pi_path.read_text(encoding="utf-8", errors="replace")
    if rm_path.is_file():
        rm_content = rm_path.read_text(encoding="utf-8", errors="replace")

    # Parse claimed counts
    pi_counts = parse_module_test_counts(pi_content)
    rm_counts = parse_roadmap_test_table(rm_content)
    pi_total = parse_total_test_count(pi_content)
    rm_total = parse_roadmap_total(rm_content)
    pi_suites = parse_suite_count(pi_content)

    # Count actual tests
    actual_counts = {}
    actual_total = 0
    for mod_name in modules:
        mod_dir = project_root / mod_name
        if mod_dir.is_dir():
            count = count_module_tests(mod_dir)
            actual_counts[mod_name] = count
            actual_total += count

    # Also count top-level tests/ directory
    top_tests = project_root / "tests"
    if top_tests.is_dir():
        for f in top_tests.iterdir():
            if f.name.startswith("test_") and f.name.endswith(".py"):
                actual_total += count_tests_in_file(str(f))

    # Also count test files at project root (not in any subdirectory)
    for f in project_root.iterdir():
        if f.is_file() and f.name.startswith("test_") and f.name.endswith(".py"):
            actual_total += count_tests_in_file(str(f))

    # Compare PROJECT_INDEX counts
    for mod_name, claimed in pi_counts.items():
        actual = actual_counts.get(mod_name, 0)
        if claimed != actual:
            report.test_mismatches.append(
                TestCountMismatch("PROJECT_INDEX.md", mod_name, claimed, actual)
            )

    # Compare ROADMAP counts
    for mod_name, claimed in rm_counts.items():
        actual = actual_counts.get(mod_name, 0)
        if claimed != actual:
            report.test_mismatches.append(
                TestCountMismatch("ROADMAP.md", mod_name, claimed, actual)
            )

    # Set totals
    report.total_claimed = pi_total
    report.total_actual = actual_total
    report.suite_claimed = pi_suites
    report.suite_actual = count_test_suites(project_root, modules)

    # Check if total mismatches
    if pi_total is not None and pi_total != actual_total:
        report.test_mismatches.append(
            TestCountMismatch("PROJECT_INDEX.md", "TOTAL", pi_total, actual_total)
        )
    if rm_total is not None and rm_total != actual_total:
        report.test_mismatches.append(
            TestCountMismatch("ROADMAP.md", "TOTAL", rm_total, actual_total)
        )

    # Check file paths from PROJECT_INDEX
    module_files = extract_module_files(pi_content)
    for mod_name, files in module_files.items():
        # "root" module means files live at project root, not in root/ subdir
        if mod_name == "root":
            mod_dir = project_root
        else:
            mod_dir = project_root / mod_name
        _, missing = check_paths_exist(files, mod_dir)
        for m in missing:
            report.missing_files.append(f"{mod_name}/{m}")

    return report


def find_project_root(explicit_root: Optional[str] = None) -> Path:
    """Find project root by locating directory with CLAUDE.md + module dirs."""
    if explicit_root:
        root = Path(explicit_root)
        if root.is_dir():
            return root
        raise FileNotFoundError(f"Specified root does not exist: {explicit_root}")

    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "CLAUDE.md").is_file():
            module_hits = sum(
                1 for m in DEFAULT_MODULES if (current / m).is_dir()
            )
            if module_hits >= 2:
                return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    raise FileNotFoundError("Could not find project root")


def main():
    parser = argparse.ArgumentParser(
        description="Check PROJECT_INDEX.md and ROADMAP.md accuracy"
    )
    parser.add_argument("--root", help="Explicit project root")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--quiet", action="store_true", help="Exit code only (0=clean, 1=drift)"
    )

    args = parser.parse_args()

    try:
        project_root = find_project_root(args.root)
    except FileNotFoundError as e:
        if args.quiet:
            sys.exit(1)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    report = run_drift_check(project_root)

    if args.quiet:
        sys.exit(1 if report.has_drift else 0)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.format())

    sys.exit(1 if report.has_drift else 0)


if __name__ == "__main__":
    main()
