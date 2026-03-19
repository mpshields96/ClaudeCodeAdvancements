"""Tests for Xcode build helper (MT-13 Phase 2).

Verifies xcode_build.py wraps xcodebuild commands correctly
and provides useful abstractions for Claude Code CLI workflows.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ios_project_gen import ProjectConfig, generate_project
from xcode_build import (
    XcodeBuild,
    BuildResult,
    find_project,
    list_schemes,
    list_simulators,
    parse_build_errors,
)


class TestBuildResult(unittest.TestCase):
    """Test BuildResult dataclass."""

    def test_success(self):
        r = BuildResult(success=True, output="BUILD SUCCEEDED", errors=[])
        self.assertTrue(r.success)
        self.assertEqual(r.errors, [])

    def test_failure_with_errors(self):
        r = BuildResult(success=False, output="", errors=["error: foo.swift:5: blah"])
        self.assertFalse(r.success)
        self.assertEqual(len(r.errors), 1)

    def test_str_representation(self):
        r = BuildResult(success=True, output="ok", errors=[])
        self.assertIn("success", str(r).lower())


class TestParseBuildErrors(unittest.TestCase):
    """Test error extraction from xcodebuild output."""

    def test_extracts_swift_error(self):
        output = "foo.swift:10:5: error: cannot find 'bar' in scope\nBUILD FAILED"
        errors = parse_build_errors(output)
        self.assertEqual(len(errors), 1)
        self.assertIn("cannot find", errors[0])

    def test_extracts_multiple_errors(self):
        output = "a.swift:1:1: error: x\nb.swift:2:2: error: y\nBUILD FAILED"
        errors = parse_build_errors(output)
        self.assertEqual(len(errors), 2)

    def test_ignores_warnings(self):
        output = "a.swift:1:1: warning: unused var\nBUILD SUCCEEDED"
        errors = parse_build_errors(output)
        self.assertEqual(len(errors), 0)

    def test_extracts_linker_error(self):
        output = "ld: error: undefined symbol: _main\nBUILD FAILED"
        errors = parse_build_errors(output)
        self.assertTrue(len(errors) >= 1)

    def test_empty_output(self):
        errors = parse_build_errors("")
        self.assertEqual(errors, [])


class TestFindProject(unittest.TestCase):
    """Test project discovery."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_finds_xcodeproj(self):
        cfg = ProjectConfig(name="FindMe")
        generate_project(cfg, self.tmpdir)
        proj = find_project(os.path.join(self.tmpdir, "FindMe"))
        self.assertIsNotNone(proj)
        self.assertTrue(proj.endswith(".xcodeproj"))

    def test_returns_none_if_no_project(self):
        proj = find_project(self.tmpdir)
        self.assertIsNone(proj)


class TestListSimulators(unittest.TestCase):
    """Test simulator listing."""

    @classmethod
    def setUpClass(cls):
        try:
            result = subprocess.run(
                ["xcrun", "simctl", "list", "devices", "available"],
                capture_output=True, text=True, timeout=10,
            )
            cls.simctl_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            cls.simctl_available = False

    def test_returns_list(self):
        if not self.simctl_available:
            self.skipTest("simctl not available")
        sims = list_simulators()
        self.assertIsInstance(sims, list)
        self.assertTrue(len(sims) > 0)

    def test_simulator_has_name_and_id(self):
        if not self.simctl_available:
            self.skipTest("simctl not available")
        sims = list_simulators()
        for sim in sims[:3]:
            self.assertIn("name", sim)
            self.assertIn("udid", sim)


class TestXcodeBuild(unittest.TestCase):
    """Test XcodeBuild wrapper with real generated project."""

    @classmethod
    def setUpClass(cls):
        try:
            result = subprocess.run(
                ["xcodebuild", "-version"],
                capture_output=True, text=True, timeout=10,
            )
            cls.xcode_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            cls.xcode_available = False

    def setUp(self):
        if not self.xcode_available:
            self.skipTest("xcodebuild not available")
        self.tmpdir = tempfile.mkdtemp()
        self.cfg = ProjectConfig(name="XBTestApp")
        self.project_path = generate_project(self.cfg, self.tmpdir)
        self.xb = XcodeBuild(
            project=os.path.join(self.project_path, "XBTestApp.xcodeproj"),
            scheme="XBTestApp",
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_build_succeeds(self):
        result = self.xb.build(destination="generic/platform=iOS Simulator")
        self.assertTrue(result.success, f"Build failed: {result.errors}")

    def test_clean_succeeds(self):
        result = self.xb.clean()
        self.assertTrue(result.success)

    def test_build_result_has_output(self):
        result = self.xb.build(destination="generic/platform=iOS Simulator")
        self.assertIsInstance(result.output, str)

    def test_invalid_scheme_fails(self):
        xb = XcodeBuild(
            project=os.path.join(self.project_path, "XBTestApp.xcodeproj"),
            scheme="NonExistentScheme",
        )
        result = xb.build(destination="generic/platform=iOS Simulator")
        self.assertFalse(result.success)


class TestListSchemes(unittest.TestCase):
    """Test scheme listing from a project."""

    @classmethod
    def setUpClass(cls):
        try:
            result = subprocess.run(
                ["xcodebuild", "-version"],
                capture_output=True, text=True, timeout=10,
            )
            cls.xcode_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            cls.xcode_available = False

    def setUp(self):
        if not self.xcode_available:
            self.skipTest("xcodebuild not available")
        self.tmpdir = tempfile.mkdtemp()
        cfg = ProjectConfig(name="SchemeApp")
        self.project_path = generate_project(cfg, self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_finds_app_scheme(self):
        proj = os.path.join(self.project_path, "SchemeApp.xcodeproj")
        schemes = list_schemes(proj)
        self.assertIn("SchemeApp", schemes)


if __name__ == "__main__":
    unittest.main()
