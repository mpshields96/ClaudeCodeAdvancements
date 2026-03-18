#!/usr/bin/env python3
"""
Tests for repo_tester.py — MT-15 GitHub Repo Tester/Evaluator.

TDD: Tests written first, then implementation.
Evaluates repos by cloning into sandboxed temp dirs, running tests,
checking builds, and scoring code quality. Never touches CCA directory.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

_THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(_THIS_DIR.parent))


# ── Import Tests ────────────────────────────────────────────────────────────


class TestImports(unittest.TestCase):
    """All public classes and functions must be importable."""

    def test_import_language_detector(self):
        from repo_tester import LanguageDetector
        self.assertTrue(callable(LanguageDetector))

    def test_import_sandbox_runner(self):
        from repo_tester import SandboxRunner
        self.assertTrue(callable(SandboxRunner))

    def test_import_repo_tester(self):
        from repo_tester import RepoTester
        self.assertTrue(callable(RepoTester))

    def test_import_repo_test_result(self):
        from repo_tester import RepoTestResult
        self.assertTrue(callable(RepoTestResult))

    def test_import_clone_repo(self):
        from repo_tester import clone_repo
        self.assertTrue(callable(clone_repo))


# ── LanguageDetector Tests ──────────────────────────────────────────────────


class TestLanguageDetector(unittest.TestCase):
    """Tests for LanguageDetector — identifies project language and test framework."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_detect_python_pytest(self):
        """Should detect Python + pytest from setup.py/pyproject.toml and test files."""
        from repo_tester import LanguageDetector
        # Create minimal Python project
        Path(self.tmpdir, "setup.py").write_text("from setuptools import setup\nsetup()")
        Path(self.tmpdir, "tests").mkdir()
        Path(self.tmpdir, "tests", "test_main.py").write_text("def test_foo(): pass")
        Path(self.tmpdir, "pyproject.toml").write_text('[tool.pytest]\n')

        det = LanguageDetector(self.tmpdir)
        result = det.detect()
        self.assertEqual(result["language"], "python")
        self.assertIn(result["test_framework"], ("pytest", "unittest"))

    def test_detect_python_unittest(self):
        """Should detect Python + unittest when no pytest config."""
        from repo_tester import LanguageDetector
        Path(self.tmpdir, "setup.py").write_text("from setuptools import setup\nsetup()")
        Path(self.tmpdir, "tests").mkdir()
        Path(self.tmpdir, "tests", "test_main.py").write_text("import unittest")

        det = LanguageDetector(self.tmpdir)
        result = det.detect()
        self.assertEqual(result["language"], "python")

    def test_detect_javascript_npm(self):
        """Should detect JavaScript/TypeScript from package.json."""
        from repo_tester import LanguageDetector
        pkg = {"name": "test", "scripts": {"test": "jest"}}
        Path(self.tmpdir, "package.json").write_text(json.dumps(pkg))

        det = LanguageDetector(self.tmpdir)
        result = det.detect()
        self.assertIn(result["language"], ("javascript", "typescript"))

    def test_detect_rust(self):
        """Should detect Rust from Cargo.toml."""
        from repo_tester import LanguageDetector
        Path(self.tmpdir, "Cargo.toml").write_text('[package]\nname = "test"')

        det = LanguageDetector(self.tmpdir)
        result = det.detect()
        self.assertEqual(result["language"], "rust")

    def test_detect_go(self):
        """Should detect Go from go.mod."""
        from repo_tester import LanguageDetector
        Path(self.tmpdir, "go.mod").write_text('module example.com/test')

        det = LanguageDetector(self.tmpdir)
        result = det.detect()
        self.assertEqual(result["language"], "go")

    def test_detect_unknown(self):
        """Empty directory should return 'unknown'."""
        from repo_tester import LanguageDetector
        det = LanguageDetector(self.tmpdir)
        result = det.detect()
        self.assertEqual(result["language"], "unknown")

    def test_detect_returns_dict_with_keys(self):
        """Detection result must have language, test_framework, build_command, test_command."""
        from repo_tester import LanguageDetector
        det = LanguageDetector(self.tmpdir)
        result = det.detect()
        self.assertIn("language", result)
        self.assertIn("test_framework", result)
        self.assertIn("build_command", result)
        self.assertIn("test_command", result)

    def test_detect_test_file_count(self):
        """Should count test files found."""
        from repo_tester import LanguageDetector
        Path(self.tmpdir, "tests").mkdir()
        Path(self.tmpdir, "tests", "test_a.py").write_text("")
        Path(self.tmpdir, "tests", "test_b.py").write_text("")
        Path(self.tmpdir, "setup.py").write_text("")

        det = LanguageDetector(self.tmpdir)
        result = det.detect()
        self.assertIn("test_file_count", result)
        self.assertGreaterEqual(result["test_file_count"], 2)

    def test_detect_typescript_from_tsconfig(self):
        """Should detect TypeScript from tsconfig.json."""
        from repo_tester import LanguageDetector
        Path(self.tmpdir, "tsconfig.json").write_text('{}')
        pkg = {"name": "test", "scripts": {"test": "vitest"}}
        Path(self.tmpdir, "package.json").write_text(json.dumps(pkg))

        det = LanguageDetector(self.tmpdir)
        result = det.detect()
        self.assertEqual(result["language"], "typescript")


# ── SandboxRunner Tests ─────────────────────────────────────────────────────


class TestSandboxRunner(unittest.TestCase):
    """Tests for SandboxRunner — executes commands in sandboxed temp dir."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_run_simple_command(self):
        """Should run a simple command and return output."""
        from repo_tester import SandboxRunner
        runner = SandboxRunner(self.tmpdir)
        result = runner.run(["echo", "hello"])
        self.assertEqual(result["returncode"], 0)
        self.assertIn("hello", result["stdout"])

    def test_run_returns_stderr(self):
        """Should capture stderr."""
        from repo_tester import SandboxRunner
        runner = SandboxRunner(self.tmpdir)
        result = runner.run(["python3", "-c", "import sys; sys.stderr.write('err')"])
        self.assertIn("err", result["stderr"])

    def test_run_timeout(self):
        """Should timeout long-running commands."""
        from repo_tester import SandboxRunner
        runner = SandboxRunner(self.tmpdir, timeout=2)
        result = runner.run(["sleep", "10"])
        self.assertTrue(result["timed_out"])
        self.assertNotEqual(result["returncode"], 0)

    def test_run_in_correct_directory(self):
        """Command should execute in the sandbox directory."""
        from repo_tester import SandboxRunner
        runner = SandboxRunner(self.tmpdir)
        result = runner.run(["pwd"])
        self.assertIn(self.tmpdir, result["stdout"])

    def test_run_strips_sensitive_env_vars(self):
        """Should strip API keys and tokens from environment."""
        from repo_tester import SandboxRunner
        runner = SandboxRunner(self.tmpdir)
        # The runner should strip these from the environment
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-123", "GITHUB_TOKEN": "ghp_test"}):
            result = runner.run(["env"])
            self.assertNotIn("sk-test-123", result["stdout"])
            self.assertNotIn("ghp_test", result["stdout"])

    def test_run_nonexistent_command(self):
        """Should handle nonexistent commands gracefully."""
        from repo_tester import SandboxRunner
        runner = SandboxRunner(self.tmpdir)
        result = runner.run(["nonexistent_command_zzz"])
        self.assertNotEqual(result["returncode"], 0)

    def test_run_result_has_duration(self):
        """Should track command duration in seconds."""
        from repo_tester import SandboxRunner
        runner = SandboxRunner(self.tmpdir)
        result = runner.run(["echo", "quick"])
        self.assertIn("duration_s", result)
        self.assertIsInstance(result["duration_s"], float)
        self.assertGreaterEqual(result["duration_s"], 0)

    def test_sandbox_never_in_cca_directory(self):
        """Sandbox must NEVER be inside the CCA project directory."""
        from repo_tester import SandboxRunner
        cca_dir = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
        # Attempting to create a sandbox inside CCA should be rejected
        with self.assertRaises(ValueError):
            SandboxRunner(os.path.join(cca_dir, "temp_test"))


# ── RepoTestResult Tests ───────────────────────────────────────────────────


class TestRepoTestResult(unittest.TestCase):
    """Tests for RepoTestResult dataclass."""

    def test_create(self):
        from repo_tester import RepoTestResult
        result = RepoTestResult(
            repo_name="user/repo",
            language="python",
            test_framework="pytest",
            tests_found=10,
            tests_passed=8,
            tests_failed=2,
            build_success=True,
            test_success=False,
            quality_score=65.0,
            quality_components={},
            warnings=[],
            errors=["2 tests failed"],
            duration_s=12.5,
        )
        self.assertEqual(result.repo_name, "user/repo")
        self.assertEqual(result.tests_found, 10)

    def test_to_dict(self):
        from repo_tester import RepoTestResult
        result = RepoTestResult(
            repo_name="user/repo", language="python", test_framework="pytest",
            tests_found=5, tests_passed=5, tests_failed=0,
            build_success=True, test_success=True, quality_score=80.0,
            quality_components={"tests": 30, "structure": 25},
            warnings=[], errors=[], duration_s=5.0,
        )
        d = result.to_dict()
        self.assertEqual(d["repo_name"], "user/repo")
        self.assertEqual(d["quality_score"], 80.0)
        json.dumps(d)  # Must be serializable

    def test_pass_rate(self):
        """Should compute pass rate correctly."""
        from repo_tester import RepoTestResult
        result = RepoTestResult(
            repo_name="user/repo", language="python", test_framework="pytest",
            tests_found=10, tests_passed=8, tests_failed=2,
            build_success=True, test_success=False, quality_score=60.0,
            quality_components={}, warnings=[], errors=[], duration_s=5.0,
        )
        self.assertAlmostEqual(result.pass_rate, 0.8, places=2)

    def test_pass_rate_zero_tests(self):
        """Should return 0.0 pass rate when no tests found."""
        from repo_tester import RepoTestResult
        result = RepoTestResult(
            repo_name="user/repo", language="python", test_framework="unknown",
            tests_found=0, tests_passed=0, tests_failed=0,
            build_success=True, test_success=False, quality_score=20.0,
            quality_components={}, warnings=["No tests found"], errors=[], duration_s=1.0,
        )
        self.assertEqual(result.pass_rate, 0.0)

    def test_verdict_property(self):
        """Should compute verdict from quality_score."""
        from repo_tester import RepoTestResult
        good = RepoTestResult(
            repo_name="a/b", language="python", test_framework="pytest",
            tests_found=20, tests_passed=20, tests_failed=0,
            build_success=True, test_success=True, quality_score=75.0,
            quality_components={}, warnings=[], errors=[], duration_s=5.0,
        )
        bad = RepoTestResult(
            repo_name="c/d", language="python", test_framework="pytest",
            tests_found=2, tests_passed=0, tests_failed=2,
            build_success=False, test_success=False, quality_score=15.0,
            quality_components={}, warnings=[], errors=[], duration_s=5.0,
        )
        self.assertEqual(good.verdict, "QUALITY")
        self.assertEqual(bad.verdict, "LOW_QUALITY")


# ── clone_repo Tests ────────────────────────────────────────────────────────


class TestCloneRepo(unittest.TestCase):
    """Tests for clone_repo — shallow clone into temp dir."""

    def test_clone_returns_path_or_none(self):
        """clone_repo should return a path string or None on failure."""
        from repo_tester import clone_repo
        # Test with a known tiny repo (or mock)
        # For unit tests, we mock subprocess
        with patch("repo_tester.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = clone_repo("user/tiny-repo", timeout=10)
            if result is not None:
                self.assertIsInstance(result, str)
                self.assertTrue(result.startswith("/tmp") or result.startswith(tempfile.gettempdir()))

    def test_clone_uses_shallow(self):
        """Should use --depth 1 for shallow clone."""
        from repo_tester import clone_repo
        with patch("repo_tester.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            clone_repo("user/repo", timeout=10)
            if mock_run.called:
                args = mock_run.call_args[0][0]
                self.assertIn("--depth", args)
                self.assertIn("1", args)

    def test_clone_never_into_cca(self):
        """Clone destination must NEVER be inside CCA directory."""
        from repo_tester import clone_repo
        with patch("repo_tester.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = clone_repo("user/repo", timeout=10)
            if result is not None:
                cca_dir = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
                self.assertFalse(result.startswith(cca_dir))

    def test_clone_invalid_repo_returns_none(self):
        """Invalid repo name should return None."""
        from repo_tester import clone_repo
        result = clone_repo("", timeout=5)
        self.assertIsNone(result)

    def test_clone_failure_returns_none(self):
        """Git clone failure should return None."""
        from repo_tester import clone_repo
        with patch("repo_tester.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128)
            result = clone_repo("nonexistent/repo-zzz", timeout=5)
            self.assertIsNone(result)


# ── RepoTester Tests ────────────────────────────────────────────────────────


class TestRepoTester(unittest.TestCase):
    """Tests for RepoTester — the main orchestrator."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "test_results.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init(self):
        from repo_tester import RepoTester
        tester = RepoTester(log_path=self.log_path)
        self.assertIsNotNone(tester)

    def test_evaluate_local_dir(self):
        """Should evaluate a local directory (already cloned)."""
        from repo_tester import RepoTester
        # Create a minimal Python project
        proj = os.path.join(self.tmpdir, "project")
        os.makedirs(os.path.join(proj, "tests"))
        Path(proj, "setup.py").write_text("from setuptools import setup\nsetup(name='test')")
        Path(proj, "main.py").write_text("def hello():\n    return 'hello'\n")
        Path(proj, "tests", "test_main.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n"
            "    def test_pass(self): self.assertTrue(True)\n"
            "if __name__ == '__main__': unittest.main()\n"
        )

        tester = RepoTester(log_path=self.log_path)
        result = tester.evaluate_local(proj, repo_name="test/project")
        self.assertIsNotNone(result)
        self.assertEqual(result.repo_name, "test/project")
        self.assertEqual(result.language, "python")

    def test_evaluate_local_runs_tests(self):
        """Should actually run tests and report results."""
        from repo_tester import RepoTester
        proj = os.path.join(self.tmpdir, "project")
        os.makedirs(os.path.join(proj, "tests"))
        Path(proj, "setup.py").write_text("")
        Path(proj, "tests", "test_simple.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n"
            "    def test_one(self): self.assertTrue(True)\n"
            "    def test_two(self): self.assertTrue(True)\n"
            "if __name__ == '__main__': unittest.main()\n"
        )

        tester = RepoTester(log_path=self.log_path)
        result = tester.evaluate_local(proj, repo_name="test/project")
        self.assertGreaterEqual(result.tests_found, 1)

    def test_evaluate_local_counts_source_files(self):
        """Should count source files for quality scoring."""
        from repo_tester import RepoTester
        proj = os.path.join(self.tmpdir, "project")
        os.makedirs(proj)
        Path(proj, "setup.py").write_text("")
        Path(proj, "a.py").write_text("x = 1")
        Path(proj, "b.py").write_text("y = 2")
        Path(proj, "c.py").write_text("z = 3")

        tester = RepoTester(log_path=self.log_path)
        result = tester.evaluate_local(proj, repo_name="test/project")
        self.assertIn("source_files", result.quality_components)

    def test_log_result(self):
        """Should log results to JSONL file."""
        from repo_tester import RepoTester, RepoTestResult
        tester = RepoTester(log_path=self.log_path)
        result = RepoTestResult(
            repo_name="user/repo", language="python", test_framework="pytest",
            tests_found=5, tests_passed=5, tests_failed=0,
            build_success=True, test_success=True, quality_score=80.0,
            quality_components={}, warnings=[], errors=[], duration_s=5.0,
        )
        tester.log_result(result)
        self.assertTrue(os.path.exists(self.log_path))
        with open(self.log_path) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["repo_name"], "user/repo")

    def test_quality_scoring_with_tests(self):
        """Repos with tests should score higher than those without."""
        from repo_tester import RepoTester
        # Project WITH tests
        proj_with = os.path.join(self.tmpdir, "with_tests")
        os.makedirs(os.path.join(proj_with, "tests"))
        Path(proj_with, "setup.py").write_text("")
        Path(proj_with, "main.py").write_text("x = 1")
        Path(proj_with, "tests", "test_main.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n"
            "    def test_one(self): self.assertTrue(True)\n"
            "if __name__ == '__main__': unittest.main()\n"
        )

        # Project WITHOUT tests
        proj_without = os.path.join(self.tmpdir, "no_tests")
        os.makedirs(proj_without)
        Path(proj_without, "setup.py").write_text("")
        Path(proj_without, "main.py").write_text("x = 1")

        tester = RepoTester(log_path=self.log_path)
        result_with = tester.evaluate_local(proj_with, repo_name="a/with")
        result_without = tester.evaluate_local(proj_without, repo_name="b/without")
        self.assertGreater(result_with.quality_score, result_without.quality_score)

    def test_quality_scoring_readme_bonus(self):
        """Repos with README should get quality bonus."""
        from repo_tester import RepoTester
        proj = os.path.join(self.tmpdir, "project")
        os.makedirs(proj)
        Path(proj, "setup.py").write_text("")
        Path(proj, "README.md").write_text("# My Project\nThis does stuff.")

        tester = RepoTester(log_path=self.log_path)
        result = tester.evaluate_local(proj, repo_name="test/project")
        self.assertIn("readme", result.quality_components)
        self.assertGreater(result.quality_components["readme"], 0)

    def test_cleanup_always_runs(self):
        """Temp directories should always be cleaned up."""
        from repo_tester import RepoTester
        tester = RepoTester(log_path=self.log_path)
        # Create a temp dir simulating clone
        clone_dir = tempfile.mkdtemp(prefix="cca-repo-test-")
        self.assertTrue(os.path.exists(clone_dir))
        tester.cleanup(clone_dir)
        self.assertFalse(os.path.exists(clone_dir))

    def test_cleanup_ignores_missing_dir(self):
        """Cleanup should not raise if dir already gone."""
        from repo_tester import RepoTester
        tester = RepoTester(log_path=self.log_path)
        tester.cleanup("/tmp/nonexistent-dir-zzz-12345")  # Should not raise


# ── Quality Score Component Tests ───────────────────────────────────────────


class TestQualityScoring(unittest.TestCase):
    """Detailed tests for quality score components."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "test_results.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_score_components_present(self):
        """Quality components should include: tests, source_files, readme, structure."""
        from repo_tester import RepoTester
        proj = os.path.join(self.tmpdir, "project")
        os.makedirs(os.path.join(proj, "tests"))
        Path(proj, "setup.py").write_text("")
        Path(proj, "README.md").write_text("# Test")
        Path(proj, "main.py").write_text("x = 1")
        Path(proj, "tests", "test_main.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n"
            "    def test_one(self): pass\n"
            "if __name__ == '__main__': unittest.main()\n"
        )

        tester = RepoTester(log_path=self.log_path)
        result = tester.evaluate_local(proj, repo_name="test/proj")
        for key in ("tests", "source_files", "readme", "structure"):
            self.assertIn(key, result.quality_components, f"Missing component: {key}")

    def test_total_score_is_sum(self):
        """Total quality score should be sum of components (capped at 100)."""
        from repo_tester import RepoTester
        proj = os.path.join(self.tmpdir, "project")
        os.makedirs(proj)
        Path(proj, "setup.py").write_text("")
        Path(proj, "main.py").write_text("x = 1")

        tester = RepoTester(log_path=self.log_path)
        result = tester.evaluate_local(proj, repo_name="test/proj")
        component_sum = sum(result.quality_components.values())
        self.assertAlmostEqual(result.quality_score, min(component_sum, 100), places=1)

    def test_max_score_100(self):
        """Quality score should never exceed 100."""
        from repo_tester import RepoTestResult
        result = RepoTestResult(
            repo_name="perfect/repo", language="python", test_framework="pytest",
            tests_found=100, tests_passed=100, tests_failed=0,
            build_success=True, test_success=True, quality_score=100.0,
            quality_components={"tests": 40, "source_files": 25, "readme": 15, "structure": 20},
            warnings=[], errors=[], duration_s=5.0,
        )
        self.assertLessEqual(result.quality_score, 100)


# ── Safety Tests ────────────────────────────────────────────────────────────


class TestSafety(unittest.TestCase):
    """Safety guardrails — these must NEVER fail."""

    def test_sandbox_rejects_cca_directory(self):
        """SandboxRunner must refuse to operate inside CCA directory."""
        from repo_tester import SandboxRunner
        cca_dir = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
        with self.assertRaises(ValueError):
            SandboxRunner(cca_dir)
        with self.assertRaises(ValueError):
            SandboxRunner(os.path.join(cca_dir, "subdir"))

    def test_clone_never_targets_cca(self):
        """clone_repo must never create dirs inside CCA."""
        from repo_tester import clone_repo
        with patch("repo_tester.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = clone_repo("user/repo", timeout=10)
            if result is not None:
                cca_dir = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
                self.assertFalse(result.startswith(cca_dir),
                                 f"Clone dir {result} is inside CCA!")

    def test_env_vars_stripped(self):
        """Sensitive environment variables must be stripped from sandbox."""
        from repo_tester import SandboxRunner
        tmpdir = tempfile.mkdtemp()
        try:
            runner = SandboxRunner(tmpdir)
            sensitive_vars = [
                "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GITHUB_TOKEN",
                "GH_TOKEN", "AWS_SECRET_ACCESS_KEY", "SUPABASE_KEY",
            ]
            env = runner._safe_env()
            for var in sensitive_vars:
                self.assertNotIn(var, env,
                                 f"Sensitive var {var} leaked to sandbox!")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_timeout_enforced(self):
        """Commands must respect timeout — no infinite hangs."""
        from repo_tester import SandboxRunner
        tmpdir = tempfile.mkdtemp()
        try:
            runner = SandboxRunner(tmpdir, timeout=3)
            result = runner.run(["sleep", "30"])
            self.assertTrue(result["timed_out"])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_no_global_installs(self):
        """Test command should never use sudo or global pip install."""
        from repo_tester import RepoTester
        tester = RepoTester(log_path=os.path.join(tempfile.mkdtemp(), "log.jsonl"))
        # The test commands generated should not contain sudo
        proj = tempfile.mkdtemp()
        try:
            Path(proj, "setup.py").write_text("")
            from repo_tester import LanguageDetector
            det = LanguageDetector(proj)
            result = det.detect()
            if result["test_command"]:
                for cmd_part in result["test_command"]:
                    self.assertNotIn("sudo", cmd_part.lower() if isinstance(cmd_part, str) else "")
        finally:
            shutil.rmtree(proj, ignore_errors=True)


# ── Integration Tests (mock-based) ─────────────────────────────────────────


class TestIntegration(unittest.TestCase):
    """Integration tests using real filesystem but mocked git clone."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "results.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_full_pipeline_python_project(self):
        """Full pipeline: detect → test → score for a Python project."""
        from repo_tester import RepoTester

        # Create realistic Python project
        proj = os.path.join(self.tmpdir, "sample_project")
        os.makedirs(os.path.join(proj, "src"))
        os.makedirs(os.path.join(proj, "tests"))
        Path(proj, "setup.py").write_text(
            "from setuptools import setup\nsetup(name='sample', version='0.1')\n"
        )
        Path(proj, "README.md").write_text("# Sample Project\nA test project.\n")
        Path(proj, "src", "core.py").write_text(
            "def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n"
        )
        Path(proj, "tests", "__init__.py").write_text("")
        Path(proj, "tests", "test_core.py").write_text(
            "import unittest\nimport sys\nsys.path.insert(0, 'src')\n"
            "from core import add, multiply\n\n"
            "class TestCore(unittest.TestCase):\n"
            "    def test_add(self): self.assertEqual(add(1, 2), 3)\n"
            "    def test_multiply(self): self.assertEqual(multiply(2, 3), 6)\n"
            "    def test_add_negative(self): self.assertEqual(add(-1, 1), 0)\n\n"
            "if __name__ == '__main__': unittest.main()\n"
        )

        tester = RepoTester(log_path=self.log_path)
        result = tester.evaluate_local(proj, repo_name="sample/project")

        self.assertEqual(result.language, "python")
        self.assertGreaterEqual(result.tests_found, 1)
        self.assertGreater(result.quality_score, 0)
        self.assertFalse(result.errors)  # No errors for a valid project

    def test_full_pipeline_empty_project(self):
        """Empty project should get low quality score but not crash."""
        from repo_tester import RepoTester
        proj = os.path.join(self.tmpdir, "empty")
        os.makedirs(proj)

        tester = RepoTester(log_path=self.log_path)
        result = tester.evaluate_local(proj, repo_name="empty/project")
        self.assertEqual(result.language, "unknown")
        self.assertEqual(result.quality_score, 0)
        self.assertTrue(result.warnings)  # Should warn about empty project


if __name__ == "__main__":
    unittest.main()
