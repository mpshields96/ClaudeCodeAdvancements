"""worker_verifier.py — Automated worker output verification (MT-21 hivemind).

Based on MAST failure taxonomy (arXiv:2503.13657): insufficient task
verification is the #3 failure category in multi-agent LLM systems.
Workers report 'done' but coordinators must validate before accepting.

Three checks:
1. Tests pass — runs the project test suite
2. No regressions — test count didn't decrease
3. Committed — no uncommitted changes left behind

Usage:
    from worker_verifier import verify_worker_output

    verdict = verify_worker_output(
        test_command="python3 parallel_test_runner.py --quick --workers 8",
        before_count=10198,
        after_count=10230,
    )
    # verdict["verdict"] in ("ACCEPT", "REVIEW", "REJECT")

CLI:
    python3 worker_verifier.py --test-cmd "python3 -m pytest" --before 100 --after 105
    python3 worker_verifier.py --json
"""
import argparse
import json
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class VerificationResult:
    """Result of a single verification check."""

    passed: bool
    check_name: str
    message: str

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "check_name": self.check_name,
            "message": self.message,
        }


def check_tests_pass(
    test_command: str = "python3 parallel_test_runner.py --quick --workers 8",
    timeout: int = 120,
) -> VerificationResult:
    """Run test suite and check for pass/fail."""
    try:
        result = subprocess.run(
            test_command.split(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return VerificationResult(
                passed=True,
                check_name="tests_pass",
                message=f"Tests passed: {result.stdout.strip()[-80:]}",
            )
        return VerificationResult(
            passed=False,
            check_name="tests_pass",
            message=f"Tests failed (exit {result.returncode}): {result.stdout.strip()[-80:]}",
        )
    except subprocess.TimeoutExpired:
        return VerificationResult(
            passed=False,
            check_name="tests_pass",
            message=f"Timeout after {timeout}s running tests",
        )
    except FileNotFoundError:
        return VerificationResult(
            passed=False,
            check_name="tests_pass",
            message=f"Test command not found: {test_command.split()[0]}",
        )


def check_no_regressions(
    before_count: int, after_count: int
) -> VerificationResult:
    """Check that test count didn't decrease."""
    if before_count == 0:
        return VerificationResult(
            passed=True,
            check_name="no_regressions",
            message=f"First run, {after_count} tests",
        )
    if after_count >= before_count:
        return VerificationResult(
            passed=True,
            check_name="no_regressions",
            message=f"{after_count} >= {before_count} (no regression)",
        )
    return VerificationResult(
        passed=False,
        check_name="no_regressions",
        message=f"Regression: {after_count} < {before_count} ({before_count - after_count} tests lost)",
    )


def check_committed() -> VerificationResult:
    """Check git status for uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        changes = [
            line for line in result.stdout.strip().split("\n")
            if line.strip() and not line.startswith("??")
        ]
        if not changes:
            return VerificationResult(
                passed=True,
                check_name="committed",
                message="Working tree clean (no uncommitted changes)",
            )
        return VerificationResult(
            passed=False,
            check_name="committed",
            message=f"{len(changes)} uncommitted change(s): {', '.join(c.strip()[:30] for c in changes[:3])}",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return VerificationResult(
            passed=False,
            check_name="committed",
            message="Could not check git status",
        )


class WorkerVerifier:
    """Orchestrates verification checks and produces a verdict."""

    def judge(self, results: list[VerificationResult]) -> dict:
        """Produce verdict from check results.

        Verdicts:
            ACCEPT  — all checks pass, safe to merge
            REVIEW  — 1-2 checks failed, coordinator should review
            REJECT  — all checks failed, worker output is broken
        """
        if not results:
            return {
                "verdict": "ACCEPT",
                "all_passed": True,
                "failures": [],
                "results": [],
            }

        failures = [r for r in results if not r.passed]
        all_passed = len(failures) == 0

        if all_passed:
            verdict = "ACCEPT"
        elif len(failures) == len(results):
            verdict = "REJECT"
        else:
            verdict = "REVIEW"

        return {
            "verdict": verdict,
            "all_passed": all_passed,
            "failures": [f.check_name for f in failures],
            "results": [r.to_dict() for r in results],
        }


def verify_worker_output(
    test_command: str = "python3 parallel_test_runner.py --quick --workers 8",
    before_count: int | None = None,
    after_count: int | None = None,
    timeout: int = 120,
) -> dict:
    """Run all verification checks and return verdict.

    Args:
        test_command: Shell command to run tests
        before_count: Test count before worker's changes (None = skip regression check)
        after_count: Test count after worker's changes
        timeout: Test command timeout in seconds
    """
    results = []

    # Check 1: Tests pass
    results.append(check_tests_pass(test_command, timeout))

    # Check 2: No regressions (if counts provided)
    if before_count is not None and after_count is not None:
        results.append(check_no_regressions(before_count, after_count))

    # Check 3: Committed
    results.append(check_committed())

    verifier = WorkerVerifier()
    verdict = verifier.judge(results)
    verdict["results"] = [r.to_dict() for r in results]
    return verdict


def main():
    parser = argparse.ArgumentParser(description="Verify worker output")
    parser.add_argument("--test-cmd", default="python3 parallel_test_runner.py --quick --workers 8")
    parser.add_argument("--before", type=int, default=None, help="Test count before changes")
    parser.add_argument("--after", type=int, default=None, help="Test count after changes")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    verdict = verify_worker_output(
        test_command=args.test_cmd,
        before_count=args.before,
        after_count=args.after,
        timeout=args.timeout,
    )

    if args.json:
        print(json.dumps(verdict, indent=2))
    else:
        print(f"Verdict: {verdict['verdict']}")
        for r in verdict["results"]:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {r['check_name']}: {r['message']}")
        if verdict["failures"]:
            print(f"\nFailed checks: {', '.join(verdict['failures'])}")


if __name__ == "__main__":
    main()
