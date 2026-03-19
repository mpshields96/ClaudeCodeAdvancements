"""Tests for iOS project generator (MT-13 Phase 2).

Verifies that ios_project_gen.py creates valid Xcode projects
with SwiftUI app targets, test targets, and CCA-convention files.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ios_project_gen import (
    ProjectConfig,
    generate_project,
    generate_pbxproj,
    generate_swiftui_app,
    generate_content_view,
    generate_tests,
    generate_claude_md,
    generate_info_plist,
)


class TestProjectConfig(unittest.TestCase):
    """Test project configuration dataclass."""

    def test_defaults(self):
        cfg = ProjectConfig(name="MyApp")
        self.assertEqual(cfg.name, "MyApp")
        self.assertEqual(cfg.bundle_id, "com.cca.MyApp")
        self.assertEqual(cfg.deployment_target, "18.0")
        self.assertEqual(cfg.swift_version, "6.0")
        self.assertTrue(cfg.include_tests)

    def test_custom_bundle_id(self):
        cfg = ProjectConfig(name="Foo", bundle_id="com.custom.foo")
        self.assertEqual(cfg.bundle_id, "com.custom.foo")

    def test_name_sanitization(self):
        """Names with spaces/special chars get sanitized for module name."""
        cfg = ProjectConfig(name="My Cool App")
        self.assertEqual(cfg.module_name, "MyCoolApp")

    def test_name_with_hyphens(self):
        cfg = ProjectConfig(name="kalshi-dashboard")
        self.assertEqual(cfg.module_name, "kalshidashboard")

    def test_empty_name_raises(self):
        with self.assertRaises(ValueError):
            ProjectConfig(name="")


class TestGenerateProject(unittest.TestCase):
    """Test full project generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cfg = ProjectConfig(name="TestApp")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_xcodeproj_dir(self):
        path = generate_project(self.cfg, self.tmpdir)
        self.assertTrue(os.path.isdir(os.path.join(path, "TestApp.xcodeproj")))

    def test_creates_pbxproj(self):
        path = generate_project(self.cfg, self.tmpdir)
        pbx = os.path.join(path, "TestApp.xcodeproj", "project.pbxproj")
        self.assertTrue(os.path.isfile(pbx))

    def test_creates_app_swift(self):
        path = generate_project(self.cfg, self.tmpdir)
        app = os.path.join(path, "TestApp", "TestAppApp.swift")
        self.assertTrue(os.path.isfile(app))

    def test_creates_content_view(self):
        path = generate_project(self.cfg, self.tmpdir)
        cv = os.path.join(path, "TestApp", "ContentView.swift")
        self.assertTrue(os.path.isfile(cv))

    def test_creates_assets(self):
        path = generate_project(self.cfg, self.tmpdir)
        assets = os.path.join(path, "TestApp", "Assets.xcassets")
        self.assertTrue(os.path.isdir(assets))

    def test_creates_test_target(self):
        path = generate_project(self.cfg, self.tmpdir)
        test_file = os.path.join(path, "TestAppTests", "TestAppTests.swift")
        self.assertTrue(os.path.isfile(test_file))

    def test_no_tests_when_disabled(self):
        cfg = ProjectConfig(name="TestApp", include_tests=False)
        path = generate_project(cfg, self.tmpdir)
        self.assertFalse(os.path.isdir(os.path.join(path, "TestAppTests")))

    def test_creates_claude_md(self):
        path = generate_project(self.cfg, self.tmpdir)
        claude = os.path.join(path, "CLAUDE.md")
        self.assertTrue(os.path.isfile(claude))

    def test_creates_gitignore(self):
        path = generate_project(self.cfg, self.tmpdir)
        gi = os.path.join(path, ".gitignore")
        self.assertTrue(os.path.isfile(gi))

    def test_returns_project_path(self):
        path = generate_project(self.cfg, self.tmpdir)
        self.assertEqual(path, os.path.join(self.tmpdir, "TestApp"))

    def test_raises_if_output_exists(self):
        os.makedirs(os.path.join(self.tmpdir, "TestApp"))
        with self.assertRaises(FileExistsError):
            generate_project(self.cfg, self.tmpdir)


class TestGeneratePbxproj(unittest.TestCase):
    """Test pbxproj file generation."""

    def test_returns_string(self):
        cfg = ProjectConfig(name="Foo")
        result = generate_pbxproj(cfg)
        self.assertIsInstance(result, str)

    def test_contains_project_name(self):
        cfg = ProjectConfig(name="MyApp")
        result = generate_pbxproj(cfg)
        self.assertIn("MyApp", result)

    def test_contains_bundle_id(self):
        cfg = ProjectConfig(name="MyApp", bundle_id="com.test.myapp")
        result = generate_pbxproj(cfg)
        self.assertIn("com.test.myapp", result)

    def test_contains_archive_version(self):
        result = generate_pbxproj(ProjectConfig(name="X"))
        self.assertIn("archiveVersion = 1", result)

    def test_contains_swift_version(self):
        cfg = ProjectConfig(name="X", swift_version="6.0")
        result = generate_pbxproj(cfg)
        self.assertIn("6.0", result)

    def test_contains_deployment_target(self):
        cfg = ProjectConfig(name="X", deployment_target="18.0")
        result = generate_pbxproj(cfg)
        self.assertIn("18.0", result)

    def test_contains_test_target_when_enabled(self):
        cfg = ProjectConfig(name="MyApp", include_tests=True)
        result = generate_pbxproj(cfg)
        self.assertIn("MyAppTests", result)

    def test_no_test_target_when_disabled(self):
        cfg = ProjectConfig(name="MyApp", include_tests=False)
        result = generate_pbxproj(cfg)
        self.assertNotIn("MyAppTests", result)


class TestSwiftFileGeneration(unittest.TestCase):
    """Test Swift source file generation."""

    def test_app_contains_app_protocol(self):
        result = generate_swiftui_app("TestApp")
        self.assertIn("@main", result)
        self.assertIn("struct TestAppApp: App", result)
        self.assertIn("import SwiftUI", result)

    def test_content_view_has_body(self):
        result = generate_content_view("TestApp")
        self.assertIn("struct ContentView: View", result)
        self.assertIn("var body: some View", result)

    def test_content_view_has_preview(self):
        result = generate_content_view("TestApp")
        self.assertIn("#Preview", result)

    def test_tests_import_testing(self):
        result = generate_tests("TestApp")
        self.assertIn("import Testing", result)

    def test_tests_have_test_macro(self):
        result = generate_tests("TestApp")
        self.assertIn("@Test", result)


class TestClaudeMd(unittest.TestCase):
    """Test CLAUDE.md generation for iOS projects."""

    def test_contains_project_name(self):
        result = generate_claude_md("MyApp")
        self.assertIn("MyApp", result)

    def test_contains_swiftui_rules(self):
        result = generate_claude_md("MyApp")
        self.assertIn("SwiftUI", result)

    def test_contains_architecture_section(self):
        result = generate_claude_md("MyApp")
        self.assertIn("Architecture", result)

    def test_contains_test_section(self):
        result = generate_claude_md("MyApp")
        self.assertIn("Test", result)

    def test_contains_one_file_one_job(self):
        result = generate_claude_md("MyApp")
        self.assertIn("one file", result.lower())


class TestInfoPlist(unittest.TestCase):
    """Test Info.plist generation."""

    def test_returns_valid_xml(self):
        result = generate_info_plist("MyApp")
        self.assertIn("<?xml", result)
        self.assertIn("</plist>", result)

    def test_contains_bundle_name(self):
        result = generate_info_plist("MyApp")
        self.assertIn("MyApp", result)


class TestXcodeBuildIntegration(unittest.TestCase):
    """Integration tests — verify generated project actually compiles.

    These tests are slower (invoke xcodebuild) but critical for validation.
    Skip if xcodebuild is not available.
    """

    @classmethod
    def setUpClass(cls):
        """Check xcodebuild is available."""
        try:
            result = subprocess.run(
                ["xcodebuild", "-version"],
                capture_output=True, text=True, timeout=10
            )
            cls.xcode_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            cls.xcode_available = False

    def setUp(self):
        if not self.xcode_available:
            self.skipTest("xcodebuild not available")
        self.tmpdir = tempfile.mkdtemp()
        self.cfg = ProjectConfig(name="BuildTestApp")
        self.project_path = generate_project(self.cfg, self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_project_builds_for_simulator(self):
        """The generated project must compile for iOS Simulator."""
        result = subprocess.run(
            [
                "xcodebuild", "build",
                "-project", os.path.join(self.project_path, "BuildTestApp.xcodeproj"),
                "-scheme", "BuildTestApp",
                "-destination", "generic/platform=iOS Simulator",
                "-quiet",
            ],
            capture_output=True, text=True, timeout=120,
            cwd=self.project_path,
        )
        self.assertEqual(
            result.returncode, 0,
            f"xcodebuild failed:\nstdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}"
        )

    def test_tests_compile(self):
        """The generated test target must compile."""
        result = subprocess.run(
            [
                "xcodebuild", "build-for-testing",
                "-project", os.path.join(self.project_path, "BuildTestApp.xcodeproj"),
                "-scheme", "BuildTestApp",
                "-destination", "generic/platform=iOS Simulator",
                "-quiet",
            ],
            capture_output=True, text=True, timeout=120,
            cwd=self.project_path,
        )
        self.assertEqual(
            result.returncode, 0,
            f"test build failed:\nstdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}"
        )


class TestCLI(unittest.TestCase):
    """Test CLI interface."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cli_creates_project(self):
        """CLI invocation creates a project directory."""
        script = os.path.join(os.path.dirname(__file__), "..", "ios_project_gen.py")
        result = subprocess.run(
            [sys.executable, script, "CLITestApp", "--output", self.tmpdir],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, f"CLI failed: {result.stderr}")
        self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "CLITestApp")))

    def test_cli_with_bundle_id(self):
        script = os.path.join(os.path.dirname(__file__), "..", "ios_project_gen.py")
        result = subprocess.run(
            [sys.executable, script, "CLITestApp",
             "--output", self.tmpdir, "--bundle-id", "org.test.cli"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        pbx = os.path.join(self.tmpdir, "CLITestApp", "CLITestApp.xcodeproj", "project.pbxproj")
        with open(pbx) as f:
            self.assertIn("org.test.cli", f.read())


if __name__ == "__main__":
    unittest.main()
