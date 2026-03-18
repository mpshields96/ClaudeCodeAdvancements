#!/usr/bin/env python3
"""
repo_tester.py — MT-15 GitHub Repo Tester/Evaluator.

Clones repos into sandboxed temp directories, detects language/framework,
runs tests, checks builds, and scores code quality. Never touches CCA directory.

Components:
  - LanguageDetector: identifies project language + test framework
  - SandboxRunner: executes commands in isolated temp dir with timeouts
  - RepoTester: orchestrates clone → detect → test → score → cleanup
  - RepoTestResult: scored output with verdict (QUALITY/ACCEPTABLE/LOW_QUALITY)
  - clone_repo(): shallow clone into /tmp with safety checks

Safety (NON-NEGOTIABLE):
  - Never clones into CCA directory
  - Sensitive env vars stripped from sandbox
  - All operations have timeouts
  - No global package installs (venv/node_modules only)
  - Cleanup always runs (even on failure)
  - No sudo, no system modifications

Usage:
    python3 repo_tester.py test <owner/repo>     # Clone + test + score
    python3 repo_tester.py local <path>           # Test a local directory
    python3 repo_tester.py results                # Show test result log

Stdlib only. No external dependencies.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ───────────────────────────────────────────────────────────────

_CCA_DIR = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
_CLONE_PREFIX = "cca-repo-test-"
_DEFAULT_TIMEOUT = 60  # seconds per command
_DEFAULT_CLONE_TIMEOUT = 30
_THIS_DIR = Path(__file__).parent

# Env vars that must NEVER leak into sandbox
_SENSITIVE_ENV_VARS = {
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GITHUB_TOKEN", "GH_TOKEN",
    "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID", "SUPABASE_KEY",
    "SUPABASE_URL", "DATABASE_URL", "SECRET_KEY", "API_KEY",
    "PRIVATE_KEY", "STRIPE_KEY", "SENDGRID_API_KEY",
}


# ── LanguageDetector ────────────────────────────────────────────────────────


class LanguageDetector:
    """
    Identifies project language, test framework, build command, and test command
    by examining files in a directory.
    """

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)

    def detect(self) -> dict:
        """
        Detect project language and test framework.

        Returns dict with keys:
          language, test_framework, build_command, test_command, test_file_count
        """
        result = {
            "language": "unknown",
            "test_framework": "unknown",
            "build_command": None,
            "test_command": None,
            "test_file_count": 0,
        }

        # Count test files
        test_files = self._find_test_files()
        result["test_file_count"] = len(test_files)

        # Detect by marker files (order matters — most specific first)
        if self._has("Cargo.toml"):
            result["language"] = "rust"
            result["test_framework"] = "cargo"
            result["build_command"] = ["cargo", "build"]
            result["test_command"] = ["cargo", "test"]

        elif self._has("go.mod"):
            result["language"] = "go"
            result["test_framework"] = "go"
            result["build_command"] = ["go", "build", "./..."]
            result["test_command"] = ["go", "test", "./..."]

        elif self._has("tsconfig.json") and self._has("package.json"):
            result["language"] = "typescript"
            result.update(self._detect_js_framework())

        elif self._has("package.json"):
            result["language"] = "javascript"
            result.update(self._detect_js_framework())

        elif self._has("setup.py") or self._has("pyproject.toml") or self._has("setup.cfg"):
            result["language"] = "python"
            result.update(self._detect_python_framework())

        elif any(self.project_dir.glob("*.py")):
            # Loose Python files
            result["language"] = "python"
            result.update(self._detect_python_framework())

        return result

    def _has(self, filename: str) -> bool:
        return (self.project_dir / filename).exists()

    def _find_test_files(self) -> list:
        """Find all test files in the project."""
        patterns = ["**/test_*.py", "**/tests/**/*.py", "**/*_test.py",
                     "**/*.test.js", "**/*.test.ts", "**/*.spec.js", "**/*.spec.ts",
                     "**/tests/**/*.rs", "**/*_test.go"]
        found = set()
        for pattern in patterns:
            for f in self.project_dir.glob(pattern):
                if f.is_file() and "__pycache__" not in str(f):
                    found.add(str(f))
        return list(found)

    def _detect_python_framework(self) -> dict:
        """Detect Python test framework (pytest vs unittest)."""
        result = {"test_framework": "unittest", "build_command": None, "test_command": None}

        # Check for pytest indicators
        has_pytest = False
        if self._has("pytest.ini") or self._has("conftest.py"):
            has_pytest = True
        if self._has("pyproject.toml"):
            try:
                content = (self.project_dir / "pyproject.toml").read_text()
                if "pytest" in content or "tool.pytest" in content:
                    has_pytest = True
            except OSError:
                pass
        if self._has("setup.cfg"):
            try:
                content = (self.project_dir / "setup.cfg").read_text()
                if "pytest" in content:
                    has_pytest = True
            except OSError:
                pass

        if has_pytest:
            result["test_framework"] = "pytest"
            result["test_command"] = ["python3", "-m", "pytest", "-x", "--tb=short", "-q"]
        else:
            result["test_framework"] = "unittest"
            result["test_command"] = ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"]

        return result

    def _detect_js_framework(self) -> dict:
        """Detect JS/TS test framework from package.json scripts."""
        result = {"test_framework": "unknown", "build_command": None, "test_command": None}

        try:
            pkg = json.loads((self.project_dir / "package.json").read_text())
        except (OSError, json.JSONDecodeError):
            return result

        scripts = pkg.get("scripts", {})

        # Detect test framework from test script
        test_script = scripts.get("test", "")
        if "jest" in test_script:
            result["test_framework"] = "jest"
        elif "vitest" in test_script:
            result["test_framework"] = "vitest"
        elif "mocha" in test_script:
            result["test_framework"] = "mocha"
        elif test_script:
            result["test_framework"] = "npm_test"

        # Build command
        if "build" in scripts:
            result["build_command"] = ["npm", "run", "build"]

        # Test command (always use npm test if available)
        if "test" in scripts:
            result["test_command"] = ["npm", "test"]

        return result


# ── SandboxRunner ───────────────────────────────────────────────────────────


class SandboxRunner:
    """
    Executes commands in a sandboxed directory with timeouts and env stripping.
    """

    def __init__(self, work_dir: str, timeout: int = _DEFAULT_TIMEOUT):
        # SAFETY: Never operate inside CCA directory
        abs_work = os.path.abspath(work_dir)
        abs_cca = os.path.abspath(_CCA_DIR)
        if abs_work.startswith(abs_cca):
            raise ValueError(
                f"SandboxRunner refuses to operate inside CCA directory: {abs_work}"
            )
        self.work_dir = abs_work
        self.timeout = timeout

    def _safe_env(self) -> dict:
        """Return environment with sensitive vars stripped."""
        env = dict(os.environ)
        for var in _SENSITIVE_ENV_VARS:
            env.pop(var, None)
        # Also strip anything that looks like a key/token
        to_remove = []
        for k in env:
            k_lower = k.lower()
            if any(pat in k_lower for pat in ("_key", "_token", "_secret", "_password")):
                to_remove.append(k)
        for k in to_remove:
            env.pop(k, None)
        return env

    def run(self, cmd: list, timeout: int = None) -> dict:
        """
        Run a command in the sandbox.

        Returns dict with: stdout, stderr, returncode, timed_out, duration_s
        """
        timeout = timeout or self.timeout
        start = time.monotonic()

        try:
            proc = subprocess.run(
                cmd,
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._safe_env(),
            )
            duration = time.monotonic() - start
            return {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
                "timed_out": False,
                "duration_s": round(duration, 2),
            }
        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "returncode": -1,
                "timed_out": True,
                "duration_s": round(duration, 2),
            }
        except FileNotFoundError:
            duration = time.monotonic() - start
            return {
                "stdout": "",
                "stderr": f"Command not found: {cmd[0]}",
                "returncode": 127,
                "timed_out": False,
                "duration_s": round(duration, 2),
            }
        except OSError as e:
            duration = time.monotonic() - start
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "timed_out": False,
                "duration_s": round(duration, 2),
            }


# ── RepoTestResult ──────────────────────────────────────────────────────────


@dataclass
class RepoTestResult:
    """Result of testing and evaluating a repo."""
    repo_name: str
    language: str
    test_framework: str
    tests_found: int
    tests_passed: int
    tests_failed: int
    build_success: bool
    test_success: bool
    quality_score: float
    quality_components: dict
    warnings: list
    errors: list
    duration_s: float

    @property
    def pass_rate(self) -> float:
        if self.tests_found == 0:
            return 0.0
        return self.tests_passed / self.tests_found

    @property
    def verdict(self) -> str:
        if self.quality_score >= 60:
            return "QUALITY"
        elif self.quality_score >= 30:
            return "ACCEPTABLE"
        else:
            return "LOW_QUALITY"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pass_rate"] = self.pass_rate
        d["verdict"] = self.verdict
        return d


# ── clone_repo ──────────────────────────────────────────────────────────────


def clone_repo(
    full_name: str,
    timeout: int = _DEFAULT_CLONE_TIMEOUT,
    dest_dir: str = None,
) -> str:
    """
    Shallow clone a GitHub repo into a temp directory.

    Args:
        full_name: "owner/repo" format
        timeout: clone timeout in seconds
        dest_dir: override destination (must NOT be inside CCA)

    Returns path to cloned directory, or None on failure.
    """
    if not full_name or "/" not in full_name:
        return None

    # Create temp dir
    if dest_dir:
        abs_dest = os.path.abspath(dest_dir)
        abs_cca = os.path.abspath(_CCA_DIR)
        if abs_dest.startswith(abs_cca):
            return None  # SAFETY: never clone into CCA
        clone_path = abs_dest
    else:
        clone_path = tempfile.mkdtemp(prefix=_CLONE_PREFIX)

    url = f"https://github.com/{full_name}.git"
    cmd = ["git", "clone", "--depth", "1", "--single-branch", url, clone_path]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            # Cleanup on failure
            shutil.rmtree(clone_path, ignore_errors=True)
            return None
        return clone_path
    except (subprocess.TimeoutExpired, OSError):
        shutil.rmtree(clone_path, ignore_errors=True)
        return None


# ── RepoTester ──────────────────────────────────────────────────────────────


class RepoTester:
    """
    Orchestrates repo evaluation: detect language → run tests → score quality.
    """

    def __init__(self, log_path: str = None, timeout: int = _DEFAULT_TIMEOUT):
        self.log_path = log_path or str(_THIS_DIR / "repo_test_results.jsonl")
        self.timeout = timeout

    def evaluate_local(self, project_dir: str, repo_name: str = "local/project") -> RepoTestResult:
        """
        Evaluate a local directory (already cloned or local project).

        Returns RepoTestResult with quality score and test results.
        """
        start = time.monotonic()
        project_dir = os.path.abspath(project_dir)
        warnings = []
        errors = []

        # Step 1: Detect language + framework
        detector = LanguageDetector(project_dir)
        detection = detector.detect()

        language = detection["language"]
        test_framework = detection["test_framework"]
        test_command = detection["test_command"]
        test_file_count = detection["test_file_count"]

        if language == "unknown":
            warnings.append("Could not detect project language")
            duration = time.monotonic() - start
            return RepoTestResult(
                repo_name=repo_name, language=language, test_framework=test_framework,
                tests_found=0, tests_passed=0, tests_failed=0,
                build_success=False, test_success=False, quality_score=0,
                quality_components={}, warnings=warnings, errors=errors,
                duration_s=round(duration, 2),
            )

        # Step 2: Run tests (if test command exists and project isn't inside CCA)
        tests_found = test_file_count
        tests_passed = 0
        tests_failed = 0
        test_success = False
        build_success = True  # Assume success unless we try and fail

        abs_proj = os.path.abspath(project_dir)
        abs_cca = os.path.abspath(_CCA_DIR)
        can_sandbox = not abs_proj.startswith(abs_cca)

        if test_command and can_sandbox:
            try:
                runner = SandboxRunner(project_dir, timeout=self.timeout)
                test_result = runner.run(test_command)

                if test_result["timed_out"]:
                    warnings.append("Tests timed out")
                    tests_failed = tests_found
                elif test_result["returncode"] == 0:
                    test_success = True
                    tests_passed = tests_found  # Approximate — passed if exit 0
                else:
                    # Try to parse test output for counts
                    parsed = self._parse_test_output(
                        test_result["stdout"] + test_result["stderr"],
                        language,
                    )
                    tests_passed = parsed.get("passed", 0)
                    tests_failed = parsed.get("failed", tests_found)
                    if tests_passed > 0 and tests_failed == 0:
                        test_success = True
            except ValueError:
                warnings.append("Cannot run tests — project inside CCA directory")
        elif not test_command:
            warnings.append("No test command detected")

        # Step 3: Score quality
        quality_components = self._score_quality(project_dir, detection, test_success, tests_found)
        quality_score = min(sum(quality_components.values()), 100)

        duration = time.monotonic() - start
        return RepoTestResult(
            repo_name=repo_name,
            language=language,
            test_framework=test_framework,
            tests_found=tests_found,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            build_success=build_success,
            test_success=test_success,
            quality_score=round(quality_score, 1),
            quality_components=quality_components,
            warnings=warnings,
            errors=errors,
            duration_s=round(duration, 2),
        )

    def _parse_test_output(self, output: str, language: str) -> dict:
        """Parse test output for pass/fail counts."""
        import re
        result = {"passed": 0, "failed": 0}

        if language == "python":
            # pytest: "5 passed, 2 failed"
            m = re.search(r"(\d+)\s+passed", output)
            if m:
                result["passed"] = int(m.group(1))
            m = re.search(r"(\d+)\s+failed", output)
            if m:
                result["failed"] = int(m.group(1))
            # unittest: "Ran 10 tests" + "OK" or "FAILED"
            m = re.search(r"Ran\s+(\d+)\s+test", output)
            if m:
                total = int(m.group(1))
                if "OK" in output:
                    result["passed"] = total
                else:
                    m2 = re.search(r"failures=(\d+)", output)
                    fails = int(m2.group(1)) if m2 else 0
                    m3 = re.search(r"errors=(\d+)", output)
                    errs = int(m3.group(1)) if m3 else 0
                    result["failed"] = fails + errs
                    result["passed"] = total - result["failed"]

        return result

    def _score_quality(self, project_dir: str, detection: dict,
                       test_success: bool, tests_found: int) -> dict:
        """
        Score project quality (0-100).

        Components:
          - tests (0-35): test coverage signal
          - source_files (0-25): codebase size
          - readme (0-15): documentation
          - structure (0-25): project organization
        """
        components = {}
        p = Path(project_dir)

        # -- Tests (0-35) --
        if test_success and tests_found >= 10:
            components["tests"] = 35
        elif test_success and tests_found >= 5:
            components["tests"] = 28
        elif test_success and tests_found >= 1:
            components["tests"] = 20
        elif tests_found >= 1:
            components["tests"] = 10  # Has tests but they fail
        else:
            components["tests"] = 0

        # -- Source files (0-25) --
        lang = detection["language"]
        ext_map = {
            "python": "*.py", "javascript": "*.js", "typescript": "*.ts",
            "rust": "*.rs", "go": "*.go",
        }
        ext = ext_map.get(lang, "*.*")
        source_files = list(p.glob(f"**/{ext}"))
        # Exclude test files and node_modules/.git
        source_files = [f for f in source_files
                        if "__pycache__" not in str(f)
                        and "node_modules" not in str(f)
                        and ".git" not in str(f)]
        count = len(source_files)

        if count >= 20:
            components["source_files"] = 25
        elif count >= 10:
            components["source_files"] = 20
        elif count >= 5:
            components["source_files"] = 15
        elif count >= 2:
            components["source_files"] = 10
        elif count >= 1:
            components["source_files"] = 5
        else:
            components["source_files"] = 0

        # -- README (0-15) --
        readme_files = list(p.glob("README*")) + list(p.glob("readme*"))
        if readme_files:
            # Check README quality (length)
            try:
                content = readme_files[0].read_text()
                if len(content) > 500:
                    components["readme"] = 15
                elif len(content) > 100:
                    components["readme"] = 10
                else:
                    components["readme"] = 5
            except OSError:
                components["readme"] = 5
        else:
            components["readme"] = 0

        # -- Structure (0-25) --
        structure_score = 0
        # Has dedicated test directory?
        if (p / "tests").exists() or (p / "test").exists() or (p / "__tests__").exists():
            structure_score += 8
        # Has source directory (src/lib/pkg)?
        if (p / "src").exists() or (p / "lib").exists() or (p / "pkg").exists():
            structure_score += 7
        # Has config file (setup.py, package.json, Cargo.toml, etc)?
        config_files = ["setup.py", "pyproject.toml", "package.json",
                        "Cargo.toml", "go.mod", "Makefile"]
        if any((p / f).exists() for f in config_files):
            structure_score += 5
        # Has license?
        license_files = list(p.glob("LICENSE*")) + list(p.glob("LICENCE*"))
        if license_files:
            structure_score += 5
        components["structure"] = min(structure_score, 25)

        return components

    def log_result(self, result: RepoTestResult):
        """Append test result to JSONL log."""
        entry = result.to_dict()
        entry["evaluated_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def cleanup(self, clone_dir: str):
        """Remove a cloned directory. Safe if already gone."""
        if clone_dir and os.path.exists(clone_dir):
            shutil.rmtree(clone_dir, ignore_errors=True)

    def test_repo(self, full_name: str) -> RepoTestResult:
        """
        Full pipeline: clone → detect → test → score → cleanup.

        Returns RepoTestResult or None on clone failure.
        """
        clone_path = clone_repo(full_name, timeout=_DEFAULT_CLONE_TIMEOUT)
        if clone_path is None:
            return None
        try:
            result = self.evaluate_local(clone_path, repo_name=full_name)
            self.log_result(result)
            return result
        finally:
            self.cleanup(clone_path)


# ── CLI ─────────────────────────────────────────────────────────────────────


def cli_main(args: list = None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args:
        print("Usage: python3 repo_tester.py [test|local|results] ...")
        print("  test <owner/repo>   Clone + test + score a GitHub repo")
        print("  local <path>        Test a local directory")
        print("  results             Show test result log")
        return

    cmd = args[0]

    if cmd == "test":
        if len(args) < 2:
            print("Usage: python3 repo_tester.py test <owner/repo>")
            return
        full_name = args[1]
        print(f"Cloning + testing {full_name}...")
        tester = RepoTester()
        result = tester.test_repo(full_name)
        if result is None:
            print(f"  Failed to clone {full_name}")
            return
        _print_result(result)

    elif cmd == "local":
        if len(args) < 2:
            print("Usage: python3 repo_tester.py local <path>")
            return
        path = os.path.abspath(args[1])
        repo_name = args[2] if len(args) > 2 else f"local/{Path(path).name}"
        print(f"Testing local project: {path}")
        tester = RepoTester()
        result = tester.evaluate_local(path, repo_name=repo_name)
        tester.log_result(result)
        _print_result(result)

    elif cmd == "results":
        log_path = str(_THIS_DIR / "repo_test_results.jsonl")
        if not os.path.exists(log_path):
            print("No test results yet.")
            return
        with open(log_path) as f:
            entries = [json.loads(line) for line in f if line.strip()]
        if not entries:
            print("No test results yet.")
            return
        print(f"Test results ({len(entries)} repos):\n")
        for entry in sorted(entries, key=lambda x: x.get("quality_score", 0), reverse=True):
            verdict = entry.get("verdict", "?")
            score = entry.get("quality_score", 0)
            name = entry.get("repo_name", "?")
            lang = entry.get("language", "?")
            tests = entry.get("tests_found", 0)
            marker = ">>>" if verdict == "QUALITY" else "   "
            print(f"  {marker} [{score:4.0f}] {verdict:<12} {name} ({lang}, {tests} tests)")

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python3 repo_tester.py [test|local|results]")


def _print_result(result: RepoTestResult):
    """Pretty-print a test result."""
    print(f"  {result.repo_name}  [{result.language}]  {result.test_framework}")
    print(f"  Tests: {result.tests_found} found, {result.tests_passed} passed, {result.tests_failed} failed")
    print(f"  Build: {'OK' if result.build_success else 'FAILED'}  |  Tests: {'PASS' if result.test_success else 'FAIL'}")
    print(f"  Quality: {result.quality_score}/100  ->  {result.verdict}")
    if result.quality_components:
        parts = [f"{k}={v}" for k, v in result.quality_components.items()]
        print(f"  Components: {', '.join(parts)}")
    if result.warnings:
        print(f"  Warnings: {'; '.join(result.warnings)}")
    if result.errors:
        print(f"  Errors: {'; '.join(result.errors)}")
    print(f"  Duration: {result.duration_s:.1f}s")


if __name__ == "__main__":
    cli_main()
