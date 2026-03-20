#!/usr/bin/env python3
"""
spec_freshness.py — Spec Rot / Staleness Detector (Frontier 2)

Detects when spec files (requirements.md, design.md, tasks.md) have become
stale relative to the code they describe. Prevents the "two conflicting
sources of truth" problem identified in community research.

Problem: After implementation begins, code evolves but specs don't get updated.
Over time, specs become misleading — worse than having no spec at all.

Solution: Compare modification times of spec files vs code files. Flag stale
specs. Support explicit RETIRED status for intent documents that have served
their purpose.

Usage:
    python3 spec-system/spec_freshness.py /path/to/project
    python3 spec-system/spec_freshness.py .              # current directory

Stdlib only. No external dependencies.
"""

import json
import os
import sys
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────

SPEC_FILES = {"requirements.md", "design.md", "tasks.md"}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".rb", ".java",
    ".c", ".cpp", ".h", ".cs", ".php", ".swift", ".kt", ".sh", ".bash",
}


# ── Spec File Detection ─────────────────────────────────────────────────────

def find_spec_files(directory: str) -> list[Path]:
    """Find spec files in a directory (non-recursive, exact names only)."""
    result = []
    for name in sorted(SPEC_FILES):
        path = Path(directory) / name
        if path.exists() and path.is_file():
            result.append(path)
    return result


def find_code_files(directory: str) -> list[Path]:
    """Find code files recursively, excluding test files."""
    result = []
    for root, _dirs, files in os.walk(directory):
        for name in files:
            path = Path(root) / name
            if path.suffix.lower() not in CODE_EXTENSIONS:
                continue
            if name.startswith("test_") or name.endswith("_test.py"):
                continue
            result.append(path)
    return sorted(result)


# ── Retired Detection ────────────────────────────────────────────────────────

def is_retired(spec_path: Path) -> bool:
    """Check if a spec file has been explicitly retired."""
    try:
        content = spec_path.read_text(encoding="utf-8")
        return "Status: RETIRED" in content
    except OSError:
        return False


# ── Freshness Check ──────────────────────────────────────────────────────────

def check_freshness(spec_path: Path, code_files: list[Path]) -> dict:
    """
    Check freshness of a single spec file relative to code files.

    Returns dict with:
        spec_file: str (filename)
        status: FRESH | STALE | RETIRED
        newer_code_files: int (count of code files modified after spec)
        spec_mtime: float
        newest_code_mtime: float | None
    """
    if is_retired(spec_path):
        return {
            "spec_file": spec_path.name,
            "status": "RETIRED",
            "newer_code_files": 0,
            "spec_mtime": spec_path.stat().st_mtime,
            "newest_code_mtime": None,
        }

    spec_mtime = spec_path.stat().st_mtime

    if not code_files:
        return {
            "spec_file": spec_path.name,
            "status": "FRESH",
            "newer_code_files": 0,
            "spec_mtime": spec_mtime,
            "newest_code_mtime": None,
        }

    newer_count = 0
    newest_code_mtime = 0.0

    for code_file in code_files:
        try:
            code_mtime = code_file.stat().st_mtime
        except OSError:
            continue
        if code_mtime > newest_code_mtime:
            newest_code_mtime = code_mtime
        if code_mtime > spec_mtime:
            newer_count += 1

    status = "STALE" if newer_count > 0 else "FRESH"

    return {
        "spec_file": spec_path.name,
        "status": status,
        "newer_code_files": newer_count,
        "spec_mtime": spec_mtime,
        "newest_code_mtime": newest_code_mtime if newest_code_mtime > 0 else None,
    }


# ── Project-Level Report ─────────────────────────────────────────────────────

def project_freshness(directory: str) -> dict:
    """
    Full freshness report for a project directory.

    Returns dict with:
        directory: str
        summary: FRESH | STALE | NO_SPECS
        specs: list[dict] (per-spec freshness results)
    """
    spec_files = find_spec_files(directory)
    code_files = find_code_files(directory)

    # Filter out retired specs for staleness assessment
    active_specs = [s for s in spec_files if not is_retired(s)]

    if not active_specs:
        return {
            "directory": directory,
            "summary": "NO_SPECS",
            "specs": [],
        }

    results = []
    any_stale = False

    for spec in active_specs:
        result = check_freshness(spec, code_files)
        results.append(result)
        if result["status"] == "STALE":
            any_stale = True

    return {
        "directory": directory,
        "summary": "STALE" if any_stale else "FRESH",
        "specs": results,
    }


# ── Human-Readable Report ────────────────────────────────────────────────────

def freshness_report(directory: str) -> str:
    """Generate a human-readable freshness report."""
    report = project_freshness(directory)
    lines = [f"Spec Freshness: {report['summary']}"]

    if report["summary"] == "NO_SPECS":
        lines.append("  No active spec files found.")
        return "\n".join(lines)

    for spec in report["specs"]:
        status_marker = "OK" if spec["status"] == "FRESH" else "STALE"
        line = f"  [{status_marker}] {spec['spec_file']}"
        if spec["newer_code_files"] > 0:
            line += f" — {spec['newer_code_files']} code file(s) modified since spec"
        lines.append(line)

    if report["summary"] == "STALE":
        lines.append("")
        lines.append("  Action: Update stale specs or mark as 'Status: RETIRED' if implementation is complete.")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    directory = os.path.abspath(directory)

    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    if "--json" in sys.argv:
        report = project_freshness(directory)
        print(json.dumps(report, indent=2))
    else:
        print(freshness_report(directory))


if __name__ == "__main__":
    main()
