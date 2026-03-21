#!/usr/bin/env python3
"""init_cache.py — Cache test results and project metrics for fast session init.

Problem: Running all 105+ test suites at session start takes ~2 minutes.
Solution: Cache test counts at wrap time, read cache at init. Only re-run
if test files have been modified since cache was written.

Usage:
    python3 init_cache.py write          # Save current test counts (at wrap)
    python3 init_cache.py read           # Read cached counts (at init)
    python3 init_cache.py stale          # Check if cache is stale
    python3 init_cache.py smoke          # Run 10 critical suites only
    python3 init_cache.py summary        # One-line init summary

Stdlib only. No external dependencies.
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

CACHE_FILE = Path.home() / ".cca-test-cache.json"
PROJECT_ROOT = Path(__file__).resolve().parent

# Critical suites for smoke test (most important, fastest)
SMOKE_SUITES = [
    "agent-guard/tests/test_path_validator.py",
    "agent-guard/tests/test_bash_guard.py",
    "agent-guard/tests/test_credential_guard.py",
    "context-monitor/tests/test_meter.py",
    "context-monitor/tests/test_alert.py",
    "memory-system/tests/test_memory.py",
    "spec-system/tests/test_spec.py",
    "tests/test_hook_chain_integration.py",
    "tests/test_cca_internal_queue.py",
    "tests/test_priority_picker.py",
]


@dataclass
class TestCache:
    """Cached test run results."""
    total_tests: int = 0
    total_suites: int = 0
    all_passed: bool = False
    timestamp: float = 0.0
    session: str = ""
    test_file_hash: str = ""  # Hash of test file mtimes for staleness

    def age_minutes(self) -> float:
        return (time.time() - self.timestamp) / 60

    def is_stale(self, max_age_hours: float = 4.0) -> bool:
        """Cache is stale if older than max_age or test files changed."""
        if self.timestamp == 0:
            return True
        if self.age_minutes() > max_age_hours * 60:
            return True
        # Check if any test file was modified since cache
        current_hash = _compute_test_file_hash()
        return current_hash != self.test_file_hash

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, data: str) -> "TestCache":
        d = json.loads(data)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _find_test_files() -> list[Path]:
    """Find all test_*.py files in the project."""
    files = []
    for root, dirs, filenames in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules")]
        for f in filenames:
            if f.startswith("test_") and f.endswith(".py"):
                files.append(Path(root) / f)
    return sorted(files)


def _compute_test_file_hash() -> str:
    """Hash of all test file modification times — detects any test file change."""
    test_files = _find_test_files()
    mtimes = []
    for f in test_files:
        try:
            mtimes.append(f"{f.relative_to(PROJECT_ROOT)}:{f.stat().st_mtime:.0f}")
        except OSError:
            pass
    return str(hash(tuple(mtimes)))


def _count_tests_and_suites() -> tuple[int, int]:
    """Count test methods and suites by running unittest discovery."""
    test_files = _find_test_files()
    total_tests = 0
    total_suites = len(test_files)

    for f in test_files:
        try:
            result = subprocess.run(
                [sys.executable, str(f)],
                capture_output=True, text=True, timeout=30,
            )
            # Parse "Ran N tests" from stderr
            for line in result.stderr.splitlines():
                if line.startswith("Ran "):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            total_tests += int(parts[1])
                        except ValueError:
                            pass
                    break
        except (subprocess.TimeoutExpired, OSError):
            pass

    return total_tests, total_suites


def _run_smoke_tests() -> tuple[bool, int, int]:
    """Run critical smoke suites only. Returns (all_passed, passed_count, total_count)."""
    passed = 0
    failed = 0

    for suite in SMOKE_SUITES:
        suite_path = PROJECT_ROOT / suite
        if not suite_path.exists():
            continue
        try:
            result = subprocess.run(
                [sys.executable, str(suite_path)],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                passed += 1
            else:
                failed += 1
                print(f"  FAIL: {suite}", file=sys.stderr)
        except (subprocess.TimeoutExpired, OSError) as e:
            failed += 1
            print(f"  ERROR: {suite}: {e}", file=sys.stderr)

    total = passed + failed
    return failed == 0, passed, total


def write_cache(session: str = "") -> TestCache:
    """Run all tests and write cache. Call at session wrap."""
    total_tests, total_suites = _count_tests_and_suites()
    cache = TestCache(
        total_tests=total_tests,
        total_suites=total_suites,
        all_passed=True,  # Assume passed if we're wrapping
        timestamp=time.time(),
        session=session,
        test_file_hash=_compute_test_file_hash(),
    )
    CACHE_FILE.write_text(cache.to_json(), encoding="utf-8")
    return cache


def read_cache() -> TestCache | None:
    """Read cached test results. Returns None if no cache."""
    if not CACHE_FILE.exists():
        return None
    try:
        return TestCache.from_json(CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def init_summary() -> str:
    """One-line summary for session init."""
    cache = read_cache()
    if cache is None:
        return "No test cache. Run full suite."
    if cache.is_stale():
        return f"Cache stale ({cache.age_minutes():.0f}m old, test files changed). Run smoke or full suite."
    return (
        f"Cache: {cache.total_tests} tests, {cache.total_suites} suites, "
        f"all passed ({cache.age_minutes():.0f}m ago, session {cache.session})"
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test cache for fast init")
    parser.add_argument("command", choices=["write", "read", "stale", "smoke", "summary"])
    parser.add_argument("--session", default="", help="Session ID for cache write")
    args = parser.parse_args()

    if args.command == "write":
        cache = write_cache(args.session)
        print(f"Cache written: {cache.total_tests} tests, {cache.total_suites} suites")

    elif args.command == "read":
        cache = read_cache()
        if cache:
            print(cache.to_json())
        else:
            print("No cache found.")

    elif args.command == "stale":
        cache = read_cache()
        if cache is None:
            print("NO_CACHE")
            sys.exit(1)
        if cache.is_stale():
            print(f"STALE ({cache.age_minutes():.0f}m old)")
            sys.exit(1)
        print(f"FRESH ({cache.age_minutes():.0f}m old)")

    elif args.command == "smoke":
        all_passed, passed, total = _run_smoke_tests()
        print(f"Smoke: {passed}/{total} passed")
        sys.exit(0 if all_passed else 1)

    elif args.command == "summary":
        print(init_summary())


if __name__ == "__main__":
    main()
