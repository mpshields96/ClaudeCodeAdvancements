#!/usr/bin/env python3
"""parallel_test_runner.py — MT-36 Phase 3: Parallel test suite execution.

Runs all CCA test suites in parallel using multiprocessing.Pool.
Replaces the serial `for f in $(find...); do python3 "$f"; done` loop
in cca-wrap/cca-init that takes ~90-120s with a parallel version
targeting ~30-45s (4 workers).

Usage:
    python3 parallel_test_runner.py                  # Run all, 4 workers
    python3 parallel_test_runner.py --workers 8      # 8 workers
    python3 parallel_test_runner.py --json            # JSON output
    python3 parallel_test_runner.py --changed-only    # Only suites for changed files
    python3 parallel_test_runner.py --quick           # Smoke test (10 core suites)

Stdlib only. No external dependencies.
"""
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from multiprocessing import Pool
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Core smoke test suites — fast, high-coverage, catch most regressions
SMOKE_SUITES = [
    "tests/test_hook_chain_integration.py",
    "tests/test_priority_picker.py",
    "agent-guard/tests/test_path_validator.py",
    "context-monitor/tests/test_meter.py",
    "memory-system/tests/test_memory.py",
    "spec-system/tests/test_validate.py",
    "self-learning/tests/test_journal.py",
    "usage-dashboard/tests/test_arewedone.py",
    "design-skills/tests/test_chart_generator.py",
    "reddit-intelligence/tests/test_reddit_reader.py",
]


@dataclass
class SuiteResult:
    """Result of running one test suite."""
    path: str
    passed: bool
    tests_run: int
    duration_s: float
    output: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def discover_test_files(root: str) -> list[str]:
    """Find all test_*.py files under root."""
    test_files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        # Skip __pycache__, .git, node_modules
        if any(skip in dirpath for skip in ("__pycache__", ".git", "node_modules", ".planning", ".venv", "venv", "reference_repos")):
            continue
        for f in sorted(filenames):
            if f.startswith("test_") and f.endswith(".py"):
                test_files.append(os.path.join(dirpath, f))
    return sorted(test_files)


def run_single_suite(path: str) -> SuiteResult:
    """Run a single test suite and capture results."""
    start = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True,
            timeout=120,  # 2 min max per suite
            cwd=os.path.dirname(path) or ".",
        )
        elapsed = time.monotonic() - start
        output = result.stderr + result.stdout

        # Parse test count from output
        tests_run = 0
        ran_match = re.search(r"Ran (\d+) test", output)
        if ran_match:
            tests_run = int(ran_match.group(1))

        # Check for OK/FAILED
        passed = result.returncode == 0 and "FAILED" not in output.split("\n")[-5:]

        # Also accept "OK" anywhere in last 5 lines
        last_lines = output.strip().split("\n")[-5:]
        has_ok = any("OK" in line for line in last_lines)
        has_failed = any("FAILED" in line for line in last_lines)

        if has_failed:
            passed = False
        elif has_ok and result.returncode == 0:
            passed = True

        error = None
        if not passed:
            # Extract failure info
            fail_lines = [l for l in output.split("\n") if "FAIL" in l or "Error" in l]
            error = "; ".join(fail_lines[-3:]) if fail_lines else f"exit code {result.returncode}"

        return SuiteResult(
            path=path, passed=passed, tests_run=tests_run,
            duration_s=round(elapsed, 3), output=output[-500:],  # Last 500 chars
            error=error,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        return SuiteResult(
            path=path, passed=False, tests_run=0,
            duration_s=round(elapsed, 3), output="TIMEOUT after 120s",
            error="timeout",
        )
    except Exception as e:
        elapsed = time.monotonic() - start
        return SuiteResult(
            path=path, passed=False, tests_run=0,
            duration_s=round(elapsed, 3), output=str(e),
            error=str(e),
        )


def run_all_parallel(
    test_files: list[str],
    workers: int = 4,
) -> list[SuiteResult]:
    """Run all test suites in parallel."""
    if not test_files:
        return []
    # Cap workers at file count
    actual_workers = min(workers, len(test_files))
    if actual_workers <= 1:
        return [run_single_suite(f) for f in test_files]

    with Pool(processes=actual_workers) as pool:
        results = pool.map(run_single_suite, test_files)
    return results


def format_results(results: list[SuiteResult]) -> str:
    """Format results into human-readable summary."""
    if not results:
        return "No test suites found."

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    total_tests = sum(r.tests_run for r in results)
    total_time = sum(r.duration_s for r in results)

    lines = [f"{passed}/{total} suites passed, {total_tests} tests, {total_time:.1f}s total"]

    failed = [r for r in results if not r.passed]
    if failed:
        lines.append("")
        lines.append("FAILED:")
        for r in failed:
            lines.append(f"  {os.path.relpath(r.path, SCRIPT_DIR)}: {r.error or 'unknown'}")

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parallel test runner (MT-36)")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--quick", action="store_true", help="Smoke test only (10 core suites)")
    parser.add_argument("--root", default=SCRIPT_DIR, help="Project root")
    args = parser.parse_args()

    start = time.monotonic()

    if args.quick:
        test_files = [os.path.join(args.root, s) for s in SMOKE_SUITES
                     if os.path.exists(os.path.join(args.root, s))]
    else:
        test_files = discover_test_files(args.root)

    results = run_all_parallel(test_files, workers=args.workers)
    wall_time = time.monotonic() - start

    if args.json:
        output = {
            "suites": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "total_tests": sum(r.tests_run for r in results),
            "wall_time_s": round(wall_time, 2),
            "cpu_time_s": round(sum(r.duration_s for r in results), 2),
            "speedup": round(sum(r.duration_s for r in results) / wall_time, 1) if wall_time > 0 else 0,
            "workers": args.workers,
            "failures": [r.to_dict() for r in results if not r.passed],
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_results(results))
        print(f"\nWall time: {wall_time:.1f}s (speedup: {sum(r.duration_s for r in results) / wall_time:.1f}x)")

    sys.exit(0 if all(r.passed for r in results) else 1)


if __name__ == "__main__":
    main()
