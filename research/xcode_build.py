#!/usr/bin/env python3
"""Xcode build helper for Claude Code CLI workflows (MT-13 Phase 2).

Wraps xcodebuild commands into a Python API for use from Claude Code.
Provides build, clean, test, scheme listing, simulator listing, and
structured error parsing.

Usage:
    python3 xcode_build.py build --project MyApp.xcodeproj --scheme MyApp
    python3 xcode_build.py clean --project MyApp.xcodeproj --scheme MyApp
    python3 xcode_build.py schemes --project MyApp.xcodeproj
    python3 xcode_build.py simulators
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class BuildResult:
    """Result of an xcodebuild invocation."""
    success: bool
    output: str
    errors: list = field(default_factory=list)

    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILURE"
        err_count = len(self.errors)
        return f"BuildResult({status}, {err_count} errors)"


# ---------------------------------------------------------------------------
# Error parsing
# ---------------------------------------------------------------------------

def parse_build_errors(output: str) -> list:
    """Extract error lines from xcodebuild output.

    Catches Swift compiler errors (file:line:col: error:) and
    linker errors (ld: error:).
    """
    if not output:
        return []

    errors = []
    for line in output.splitlines():
        # Swift compiler error: file.swift:10:5: error: message
        if re.search(r":\d+:\d+: error:", line):
            errors.append(line.strip())
        # Linker error: ld: error: message
        elif line.strip().startswith("ld: error:"):
            errors.append(line.strip())
        # Generic xcodebuild error (e.g., scheme not found)
        elif "error:" in line.lower() and "warning:" not in line.lower():
            # Avoid false positives from warnings
            if not line.strip().startswith("warning:"):
                errors.append(line.strip())

    return errors


# ---------------------------------------------------------------------------
# Project discovery
# ---------------------------------------------------------------------------

def find_project(directory: str) -> str | None:
    """Find the first .xcodeproj in a directory.

    Args:
        directory: Path to search in.

    Returns:
        Full path to .xcodeproj, or None if not found.
    """
    pattern = os.path.join(directory, "*.xcodeproj")
    matches = glob.glob(pattern)
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# Simulator listing
# ---------------------------------------------------------------------------

def list_simulators() -> list:
    """List available iOS simulators.

    Returns:
        List of dicts with 'name', 'udid', 'runtime' keys.
    """
    result = subprocess.run(
        ["xcrun", "simctl", "list", "devices", "available", "-j"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        return []

    data = json.loads(result.stdout)
    simulators = []
    for runtime, devices in data.get("devices", {}).items():
        for device in devices:
            if device.get("isAvailable", False):
                simulators.append({
                    "name": device["name"],
                    "udid": device["udid"],
                    "runtime": runtime,
                })
    return simulators


# ---------------------------------------------------------------------------
# Scheme listing
# ---------------------------------------------------------------------------

def list_schemes(project_path: str) -> list:
    """List available schemes in an Xcode project.

    Args:
        project_path: Path to .xcodeproj.

    Returns:
        List of scheme name strings.
    """
    result = subprocess.run(
        ["xcodebuild", "-list", "-project", project_path, "-json"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        return []

    data = json.loads(result.stdout)
    project_info = data.get("project", {})
    return project_info.get("schemes", [])


# ---------------------------------------------------------------------------
# XcodeBuild wrapper
# ---------------------------------------------------------------------------

class XcodeBuild:
    """Wrapper around xcodebuild for a specific project and scheme."""

    def __init__(self, project: str, scheme: str):
        self.project = project
        self.scheme = scheme

    def _run(self, action: str, extra_args: list = None,
             timeout: int = 120) -> BuildResult:
        """Run an xcodebuild action.

        Args:
            action: xcodebuild action (build, clean, test, build-for-testing).
            extra_args: Additional CLI arguments.
            timeout: Timeout in seconds.

        Returns:
            BuildResult with success status, output, and parsed errors.
        """
        cmd = [
            "xcodebuild", action,
            "-project", self.project,
            "-scheme", self.scheme,
        ]
        if extra_args:
            cmd.extend(extra_args)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
            output = result.stdout + "\n" + result.stderr
            errors = parse_build_errors(output)
            return BuildResult(
                success=result.returncode == 0,
                output=output,
                errors=errors,
            )
        except subprocess.TimeoutExpired:
            return BuildResult(
                success=False,
                output="",
                errors=[f"Build timed out after {timeout}s"],
            )

    def build(self, destination: str = "generic/platform=iOS Simulator",
              quiet: bool = True) -> BuildResult:
        """Build the project.

        Args:
            destination: Build destination string.
            quiet: If True, pass -quiet to reduce output.
        """
        args = ["-destination", destination]
        if quiet:
            args.append("-quiet")
        return self._run("build", args)

    def clean(self) -> BuildResult:
        """Clean the project."""
        return self._run("clean", ["-quiet"])

    def test(self, destination: str = None, quiet: bool = True) -> BuildResult:
        """Run tests.

        Args:
            destination: Test destination (e.g., specific simulator).
            quiet: If True, pass -quiet.
        """
        args = []
        if destination:
            args.extend(["-destination", destination])
        else:
            # Pick first available iPhone simulator
            sims = list_simulators()
            iphone_sims = [s for s in sims if "iPhone" in s["name"]]
            if iphone_sims:
                sim = iphone_sims[0]
                args.extend([
                    "-destination",
                    f"platform=iOS Simulator,id={sim['udid']}",
                ])
            else:
                args.extend(["-destination", "generic/platform=iOS Simulator"])
        if quiet:
            args.append("-quiet")
        return self._run("test", args, timeout=180)

    def build_for_testing(self, destination: str = "generic/platform=iOS Simulator",
                          quiet: bool = True) -> BuildResult:
        """Build for testing without running tests."""
        args = ["-destination", destination]
        if quiet:
            args.append("-quiet")
        return self._run("build-for-testing", args)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Xcode build helper for Claude Code.")
    sub = parser.add_subparsers(dest="command", required=True)

    # build
    build_p = sub.add_parser("build", help="Build the project")
    build_p.add_argument("--project", "-p", required=True)
    build_p.add_argument("--scheme", "-s", required=True)
    build_p.add_argument("--destination", "-d", default="generic/platform=iOS Simulator")

    # clean
    clean_p = sub.add_parser("clean", help="Clean the project")
    clean_p.add_argument("--project", "-p", required=True)
    clean_p.add_argument("--scheme", "-s", required=True)

    # test
    test_p = sub.add_parser("test", help="Run tests")
    test_p.add_argument("--project", "-p", required=True)
    test_p.add_argument("--scheme", "-s", required=True)
    test_p.add_argument("--destination", "-d")

    # schemes
    schemes_p = sub.add_parser("schemes", help="List schemes")
    schemes_p.add_argument("--project", "-p", required=True)

    # simulators
    sub.add_parser("simulators", help="List available simulators")

    args = parser.parse_args()

    if args.command == "simulators":
        sims = list_simulators()
        for s in sims:
            print(f"  {s['name']} ({s['udid'][:8]}...)")
        print(f"\n{len(sims)} simulators available")
        return

    if args.command == "schemes":
        schemes = list_schemes(args.project)
        for s in schemes:
            print(f"  {s}")
        return

    xb = XcodeBuild(project=args.project, scheme=args.scheme)

    if args.command == "build":
        result = xb.build(destination=args.destination)
    elif args.command == "clean":
        result = xb.clean()
    elif args.command == "test":
        result = xb.test(destination=args.destination)
    else:
        parser.error(f"Unknown command: {args.command}")
        return

    print(result)
    if result.errors:
        print("\nErrors:")
        for e in result.errors:
            print(f"  {e}")
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
