#!/usr/bin/env python3
"""
arewedone.py — Structural Completeness Checker for ClaudeCodeAdvancements

Scans the project and reports on module completeness, code stubs,
test coverage, doc freshness, uncommitted work, and syntax health.

Usage:
    python3 arewedone.py                    # Full report
    python3 arewedone.py --module memory-system  # Check one module
    python3 arewedone.py --quiet            # Exit code only (0=pass, 1=issues)
    python3 arewedone.py --fix              # Auto-create missing test stubs
    python3 arewedone.py --root /path/to/project  # Explicit project root
"""

import argparse
import ast
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

MODULES = [
    "memory-system",
    "spec-system",
    "context-monitor",
    "agent-guard",
    "usage-dashboard",
    "reddit-intelligence",
    "self-learning",
]

DOC_FILES = [
    "SESSION_STATE.md",
    "PROJECT_INDEX.md",
]

DOC_FRESHNESS_HOURS = 24


@dataclass
class ModuleReport:
    name: str
    has_claude_md: bool = False
    py_files: List[str] = field(default_factory=list)
    test_files: List[str] = field(default_factory=list)
    has_tests_dir: bool = False
    tests_pass: bool = False
    test_run_output: str = ""
    test_run_attempted: bool = False
    status: str = "FAIL"  # PASS, WARN, FAIL
    summary: str = ""


@dataclass
class StubInfo:
    file_path: str
    line_number: int
    kind: str  # One of: todo, fixme, not-implemented, pass-only
    line_text: str


@dataclass
class SyntaxError_:
    file_path: str
    error: str


@dataclass
class DocFreshness:
    file_path: str
    age_hours: float
    exists: bool
    status: str  # OK, STALE, MISSING


@dataclass
class FullReport:
    module_reports: List[ModuleReport] = field(default_factory=list)
    stubs: List[StubInfo] = field(default_factory=list)
    syntax_errors: List[SyntaxError_] = field(default_factory=list)
    uncommitted_lines: List[str] = field(default_factory=list)
    doc_freshness: List[DocFreshness] = field(default_factory=list)
    has_issues: bool = False


def find_project_root(explicit_root: Optional[str] = None) -> Path:
    """Find project root by locating directory containing CLAUDE.md.

    Distinguishes the real project root from module-level CLAUDE.md files
    by checking that at least two known module directories exist alongside it.
    """
    if explicit_root:
        root = Path(explicit_root)
        if root.is_dir():
            return root
        raise FileNotFoundError(f"Specified root does not exist: {explicit_root}")

    def _is_project_root(d: Path) -> bool:
        """True if this looks like the real project root, not a module dir."""
        if not (d / "CLAUDE.md").is_file():
            return False
        # At least 2 known module dirs must exist alongside CLAUDE.md
        module_hits = sum(1 for m in MODULES if (d / m).is_dir())
        return module_hits >= 2

    # Walk up from this file's location
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if _is_project_root(current):
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    raise FileNotFoundError("Could not find project root (directory with CLAUDE.md + module dirs)")


def find_py_files(module_dir: Path) -> List[str]:
    """Find all .py files in a module, excluding tests/ and __pycache__."""
    py_files = []
    if not module_dir.is_dir():
        return py_files

    for root, dirs, files in os.walk(module_dir):
        # Skip tests and cache directories
        dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__", ".git")]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))

    return sorted(py_files)


def find_test_files(module_dir: Path) -> List[str]:
    """Find all test files in a module's tests/ directory."""
    tests_dir = module_dir / "tests"
    if not tests_dir.is_dir():
        return []

    test_files = []
    for root, dirs, files in os.walk(tests_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.startswith("test_") and f.endswith(".py"):
                test_files.append(os.path.join(root, f))

    return sorted(test_files)


def check_module_completeness(module_name: str, project_root: Path,
                               run_tests: bool = True) -> ModuleReport:
    """Check a single module for structural completeness."""
    report = ModuleReport(name=module_name)
    module_dir = project_root / module_name

    if not module_dir.is_dir():
        report.status = "FAIL"
        report.summary = "module directory not found"
        return report

    # Check CLAUDE.md
    report.has_claude_md = (module_dir / "CLAUDE.md").is_file()

    # Find py files (excluding tests)
    report.py_files = find_py_files(module_dir)

    # Find test files
    report.has_tests_dir = (module_dir / "tests").is_dir()
    report.test_files = find_test_files(module_dir)

    # Run tests if requested and test files exist
    if run_tests and report.test_files:
        report.test_run_attempted = True
        report.tests_pass = run_test_files(report.test_files)
    elif not report.test_files:
        # No tests to run — not a pass
        report.tests_pass = False
        report.test_run_attempted = False

    # Determine status
    issues = []
    if not report.has_claude_md:
        issues.append("missing CLAUDE.md")
    if not report.has_tests_dir:
        issues.append("missing tests/ directory")
    if not report.test_files:
        issues.append("NEEDS TESTS")
    if report.test_run_attempted and not report.tests_pass:
        issues.append("tests failing")

    if not issues:
        report.status = "PASS"
        parts = []
        parts.append("CLAUDE.md" if report.has_claude_md else "no CLAUDE.md")
        parts.append(f"{len(report.py_files)} py file{'s' if len(report.py_files) != 1 else ''}")
        parts.append(f"{len(report.test_files)} test file{'s' if len(report.test_files) != 1 else ''}")
        if report.test_run_attempted:
            parts.append("all tests pass")
        report.summary = ", ".join(parts)
    elif report.has_claude_md and report.py_files:
        report.status = "WARN"
        parts = []
        parts.append("CLAUDE.md present")
        parts.append(f"{len(report.py_files)} py file{'s' if len(report.py_files) != 1 else ''}")
        parts.append(f"{len(report.test_files)} test file{'s' if len(report.test_files) != 1 else ''}")
        parts.append(" — " + ", ".join(issues))
        report.summary = ", ".join(parts[:3]) + parts[3]
    else:
        report.status = "FAIL"
        report.summary = ", ".join(issues)

    return report


def run_test_files(test_files: List[str]) -> bool:
    """Run test files and return True if all pass."""
    for test_file in test_files:
        try:
            result = subprocess.run(
                [sys.executable, test_file],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                return False
        except (subprocess.TimeoutExpired, OSError):
            return False
    return True


def detect_pass_only_function(source: str) -> List[Tuple[int, str]]:
    """Detect functions/methods whose body is only `pass` (no docstring, no other code)."""
    results = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return results

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            # Separate docstring from other statements
            has_docstring = (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(getattr(body[0], "value", None), ast.Constant)
                and isinstance(body[0].value.value, str)
            )
            # Filter out string constants (docstrings) to get real statements
            stmts = [s for s in body if not isinstance(s, ast.Expr)
                      or not isinstance(getattr(s, "value", None), ast.Constant)
                      or not isinstance(s.value.value, str)]
            if len(stmts) == 1 and isinstance(stmts[0], ast.Pass):
                # If there's a docstring, the pass is intentional (documented
                # suppression, e.g. overriding log_message to suppress output).
                # Only flag undocumented pass-only functions as stubs.
                if not has_docstring:
                    results.append((node.lineno, f"def {node.name}(...): pass"))

    return results


def find_code_stubs(py_files: List[str], skip_tests: bool = True) -> List[StubInfo]:
    """Scan .py files for TODO, FIXME, NotImplementedError, pass-only functions.

    Args:
        skip_tests: If True, skip files in tests/ directories (they contain
                    intentional TODO/FIXME strings as test fixture data).
    """
    stubs = []
    patterns = [
        (re.compile(r'#\s*TODO\b', re.IGNORECASE), "TODO"),
        (re.compile(r'#\s*FIXME\b', re.IGNORECASE), "FIXME"),
        (re.compile(r'raise\s+NotImplementedError'), "NotImplementedError"),
    ]

    for fpath in py_files:
        if skip_tests and ("/tests/" in fpath or "/test_" in os.path.basename(fpath)):
            continue
        try:
            content = Path(fpath).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = content.splitlines()

        # Pattern-based detection
        for i, line in enumerate(lines, 1):
            for pattern, kind in patterns:
                if pattern.search(line):
                    stubs.append(StubInfo(
                        file_path=fpath,
                        line_number=i,
                        kind=kind,
                        line_text=line.strip(),
                    ))

        # AST-based pass-only detection
        for lineno, desc in detect_pass_only_function(content):
            stubs.append(StubInfo(
                file_path=fpath,
                line_number=lineno,
                kind="pass-only",
                line_text=desc,
            ))

    return stubs


def check_syntax(py_files: List[str]) -> List[SyntaxError_]:
    """Check all .py files for syntax errors using ast.parse."""
    errors = []
    for fpath in py_files:
        try:
            content = Path(fpath).read_text(encoding="utf-8", errors="replace")
            ast.parse(content, filename=fpath)
        except SyntaxError as e:
            errors.append(SyntaxError_(
                file_path=fpath,
                error=f"line {e.lineno}: {e.msg}",
            ))
        except OSError as e:
            errors.append(SyntaxError_(
                file_path=fpath,
                error=str(e),
            ))
    return errors


def get_git_status(project_root: Path) -> List[str]:
    """Get uncommitted/untracked files from git status."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=10,
        )
        if result.returncode != 0:
            return [f"(git error: {result.stderr.strip()})"]
        lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
        return lines
    except (OSError, subprocess.TimeoutExpired):
        return ["(git not available)"]


def parse_git_status_lines(lines: List[str]) -> List[str]:
    """Parse git status --porcelain lines into display format."""
    return lines  # Already in porcelain format which is readable


def check_doc_freshness(project_root: Path,
                        doc_files: Optional[List[str]] = None,
                        now: Optional[float] = None) -> List[DocFreshness]:
    """Check if documentation files have been recently updated."""
    if doc_files is None:
        doc_files = DOC_FILES
    if now is None:
        now = time.time()

    results = []
    for doc_name in doc_files:
        doc_path = project_root / doc_name
        if not doc_path.is_file():
            results.append(DocFreshness(
                file_path=doc_name,
                age_hours=0,
                exists=False,
                status="MISSING",
            ))
            continue

        mtime = os.path.getmtime(str(doc_path))
        age_seconds = now - mtime
        age_hours = age_seconds / 3600

        status = "OK" if age_hours <= DOC_FRESHNESS_HOURS else "STALE"
        results.append(DocFreshness(
            file_path=doc_name,
            age_hours=age_hours,
            exists=True,
            status=status,
        ))

    return results


def format_age(hours: float) -> str:
    """Format age in hours to a human-readable string."""
    if hours < 1:
        minutes = int(hours * 60)
        return f"{minutes}m ago"
    elif hours < 48:
        return f"{int(hours)}h ago"
    else:
        days = int(hours / 24)
        return f"{days}d ago"


def collect_all_py_files(project_root: Path, modules: List[str]) -> List[str]:
    """Collect all .py files across specified modules (including tests)."""
    all_files = []
    for mod_name in modules:
        mod_dir = project_root / mod_name
        if not mod_dir.is_dir():
            continue
        for root, dirs, files in os.walk(mod_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if f.endswith(".py"):
                    all_files.append(os.path.join(root, f))
    return sorted(all_files)


def generate_test_stub(py_file: str, module_dir: Path) -> Optional[Tuple[str, str]]:
    """Generate a test stub file path and content for a .py file that lacks tests.

    Returns (test_file_path, test_content) or None if test already exists.
    """
    py_name = Path(py_file).stem
    tests_dir = module_dir / "tests"
    test_file = tests_dir / f"test_{py_name}.py"

    if test_file.exists():
        return None

    rel_path = os.path.relpath(py_file, module_dir)
    module_import = rel_path.replace(os.sep, ".").replace(".py", "")

    content = f'''#!/usr/bin/env python3
"""Tests for {py_name}."""

import unittest
import sys
import os

# Add module root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Test{py_name.title().replace("_", "")}(unittest.TestCase):
    """Tests for {module_import}."""

    def test_placeholder(self):
        """Placeholder test — replace with real tests."""
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
'''
    return str(test_file), content


def create_missing_test_stubs(project_root: Path, modules: List[str]) -> List[str]:
    """Create test stubs for .py files that lack corresponding tests.

    Returns list of created file paths.
    """
    created = []
    for mod_name in modules:
        mod_dir = project_root / mod_name
        if not mod_dir.is_dir():
            continue

        py_files = find_py_files(mod_dir)
        tests_dir = mod_dir / "tests"

        # Create tests dir if needed
        if py_files and not tests_dir.is_dir():
            tests_dir.mkdir(parents=True, exist_ok=True)

        for py_file in py_files:
            result = generate_test_stub(py_file, mod_dir)
            if result:
                test_path, test_content = result
                Path(test_path).write_text(test_content, encoding="utf-8")
                created.append(test_path)

    return created


def run_full_check(project_root: Path, modules: List[str],
                   run_tests: bool = True) -> FullReport:
    """Run all checks and return a full report."""
    report = FullReport()

    # Module completeness
    for mod_name in modules:
        mod_report = check_module_completeness(mod_name, project_root,
                                                run_tests=run_tests)
        report.module_reports.append(mod_report)

    # All py files across modules (including tests for stub/syntax checks)
    all_py = collect_all_py_files(project_root, modules)

    # Code stubs
    report.stubs = find_code_stubs(all_py)

    # Syntax errors
    report.syntax_errors = check_syntax(all_py)

    # Git status
    report.uncommitted_lines = get_git_status(project_root)

    # Doc freshness
    report.doc_freshness = check_doc_freshness(project_root)

    # Determine overall issues
    failing_modules = [m for m in report.module_reports if m.status != "PASS"]
    report.has_issues = bool(
        failing_modules or report.stubs or report.syntax_errors
    )

    return report


def format_report(report: FullReport) -> str:
    """Format a FullReport into the display string."""
    lines = []
    lines.append("=== Are We Done? Structural Completeness Report ===")
    lines.append("")

    # Module reports
    for m in report.module_reports:
        tag = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]"}[m.status]
        lines.append(f"{tag} {m.name}: {m.summary}")
    lines.append("")

    # Code stubs
    lines.append(f"Code Stubs Found: {len(report.stubs)}")
    if report.stubs:
        for s in report.stubs:
            lines.append(f"  {s.file_path}:{s.line_number} [{s.kind}] {s.line_text}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Syntax errors
    lines.append(f"Syntax Errors: {len(report.syntax_errors)}")
    if report.syntax_errors:
        for e in report.syntax_errors:
            lines.append(f"  {e.file_path}: {e.error}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Uncommitted files
    lines.append(f"Uncommitted Files: {len(report.uncommitted_lines)}")
    if report.uncommitted_lines:
        for line in report.uncommitted_lines:
            lines.append(f"  {line}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Doc freshness
    lines.append("Doc Freshness:")
    for d in report.doc_freshness:
        if not d.exists:
            lines.append(f"  {d.file_path}: [MISSING]")
        else:
            age_str = format_age(d.age_hours)
            lines.append(f"  {d.file_path}: updated {age_str} [{d.status}]")
    lines.append("")

    # Overall summary
    passing = sum(1 for m in report.module_reports if m.status == "PASS")
    total = len(report.module_reports)
    lines.append(
        f"Overall: {passing}/{total} modules complete | "
        f"{len(report.stubs)} stubs | "
        f"{len(report.syntax_errors)} syntax errors | "
        f"{len(report.uncommitted_lines)} uncommitted"
    )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Structural completeness checker for ClaudeCodeAdvancements"
    )
    parser.add_argument(
        "--root",
        help="Explicit project root (default: auto-detect from CLAUDE.md)",
    )
    parser.add_argument(
        "--module",
        help="Check only this module",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="CI mode: exit code only (0=pass, 1=issues)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-create missing test stubs",
    )
    parser.add_argument(
        "--no-test-run",
        action="store_true",
        help="Skip running tests (faster, just check structure)",
    )

    args = parser.parse_args()

    try:
        project_root = find_project_root(args.root)
    except FileNotFoundError as e:
        if args.quiet:
            sys.exit(1)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    modules = MODULES
    if args.module:
        if args.module not in MODULES:
            if args.quiet:
                sys.exit(1)
            print(f"Error: Unknown module '{args.module}'", file=sys.stderr)
            print(f"Known modules: {', '.join(MODULES)}", file=sys.stderr)
            sys.exit(1)
        modules = [args.module]

    # --fix mode
    if args.fix:
        created = create_missing_test_stubs(project_root, modules)
        if not args.quiet:
            if created:
                print(f"Created {len(created)} test stub(s):")
                for f in created:
                    print(f"  {f}")
            else:
                print("No missing test stubs to create.")
        # Continue to run the report after fixing

    # Run checks
    report = run_full_check(project_root, modules,
                             run_tests=not args.no_test_run)

    if args.quiet:
        sys.exit(1 if report.has_issues else 0)

    print(format_report(report))
    sys.exit(1 if report.has_issues else 0)


if __name__ == "__main__":
    main()
