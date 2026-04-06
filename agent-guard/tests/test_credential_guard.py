"""
Tests for AG-3: credential-extraction guard.
"""
from __future__ import annotations
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import credential_guard


class TestCheckCommand(unittest.TestCase):

    # --- Docker patterns ---

    def test_flags_docker_compose_config(self):
        threats = credential_guard.check_command("docker compose config")
        self.assertTrue(len(threats) > 0)
        self.assertTrue(any("critical" == t["severity"] for t in threats))

    def test_flags_docker_compose_config_hyphen(self):
        threats = credential_guard.check_command("docker-compose config")
        self.assertTrue(len(threats) > 0)

    def test_flags_docker_inspect(self):
        threats = credential_guard.check_command("docker inspect mycontainer")
        self.assertTrue(len(threats) > 0)

    # --- Env var dump patterns ---

    def test_flags_printenv(self):
        threats = credential_guard.check_command("printenv")
        self.assertTrue(len(threats) > 0)

    def test_flags_env_piped(self):
        threats = credential_guard.check_command("env | grep API")
        self.assertTrue(len(threats) > 0)

    def test_flags_env_redirected(self):
        threats = credential_guard.check_command("env > /tmp/leaked.txt")
        self.assertTrue(len(threats) > 0)

    def test_env_without_pipe_not_flagged(self):
        # Just `env` alone without pipe is ambiguous — the rule requires a pipe/redirect
        threats = credential_guard.check_command("env")
        # Should not match env without pipe
        env_threats = [t for t in threats if "env" in t["description"].lower() and "piped" in t["description"]]
        self.assertEqual(len(env_threats), 0)

    def test_flags_set_piped(self):
        threats = credential_guard.check_command("set | grep SECRET")
        self.assertTrue(len(threats) > 0)

    # --- Credential file reads ---

    def test_flags_cat_dotenv(self):
        threats = credential_guard.check_command("cat .env")
        self.assertTrue(len(threats) > 0)
        self.assertTrue(any("critical" == t["severity"] for t in threats))

    def test_flags_cat_dotenv_quoted(self):
        threats = credential_guard.check_command('cat ".env"')
        self.assertTrue(len(threats) > 0)

    def test_flags_cat_aws_credentials(self):
        threats = credential_guard.check_command("cat ~/.aws/credentials")
        self.assertTrue(len(threats) > 0)

    def test_flags_cat_ssh_private_key(self):
        threats = credential_guard.check_command("cat ~/.ssh/id_rsa")
        self.assertTrue(len(threats) > 0)

    def test_cat_ssh_known_hosts_not_flagged(self):
        threats = credential_guard.check_command("cat ~/.ssh/known_hosts")
        ssh_threats = [t for t in threats if "private key" in t["description"]]
        self.assertEqual(len(ssh_threats), 0)

    def test_cat_ssh_config_not_flagged(self):
        threats = credential_guard.check_command("cat ~/.ssh/config")
        ssh_threats = [t for t in threats if "private key" in t["description"]]
        self.assertEqual(len(ssh_threats), 0)

    def test_flags_proc_self_environ(self):
        threats = credential_guard.check_command("cat /proc/self/environ")
        self.assertTrue(len(threats) > 0)
        self.assertTrue(any("critical" == t["severity"] for t in threats))

    # --- History exfil ---

    def test_flags_history_piped(self):
        threats = credential_guard.check_command("history | grep docker")
        self.assertTrue(len(threats) > 0)

    # --- Safe commands ---

    def test_safe_ls_not_flagged(self):
        threats = credential_guard.check_command("ls -la")
        self.assertEqual(threats, [])

    def test_safe_git_status_not_flagged(self):
        threats = credential_guard.check_command("git status")
        self.assertEqual(threats, [])

    def test_safe_python_test_not_flagged(self):
        threats = credential_guard.check_command("python3 -m pytest tests/")
        self.assertEqual(threats, [])

    def test_safe_docker_build_not_flagged(self):
        threats = credential_guard.check_command("docker build -t myapp .")
        self.assertEqual(threats, [])

    def test_safe_docker_run_not_flagged(self):
        threats = credential_guard.check_command("docker run --rm myapp")
        self.assertEqual(threats, [])

    def test_safe_cat_readme_not_flagged(self):
        threats = credential_guard.check_command("cat README.md")
        self.assertEqual(threats, [])

    def test_safe_grep_in_source_not_flagged(self):
        threats = credential_guard.check_command("grep -r 'def main' src/")
        self.assertEqual(threats, [])

    def test_empty_command_not_flagged(self):
        threats = credential_guard.check_command("")
        self.assertEqual(threats, [])


class TestHasCriticalThreat(unittest.TestCase):

    def test_returns_true_for_critical(self):
        threats = [{"severity": "critical", "description": "test", "pattern": "x"}]
        self.assertTrue(credential_guard.has_critical_threat(threats))

    def test_returns_false_for_high_only(self):
        threats = [{"severity": "high", "description": "test", "pattern": "x"}]
        self.assertFalse(credential_guard.has_critical_threat(threats))

    def test_returns_false_for_empty(self):
        self.assertFalse(credential_guard.has_critical_threat([]))


class TestBuildWarnMessage(unittest.TestCase):

    def test_contains_command(self):
        threats = [{"severity": "critical", "description": "exposes secrets", "pattern": "x"}]
        msg = credential_guard.build_warn_message("docker compose config", threats, blocking=False)
        self.assertIn("docker compose config", msg)

    def test_blocking_message_says_blocking(self):
        threats = [{"severity": "critical", "description": "exposes secrets", "pattern": "x"}]
        msg = credential_guard.build_warn_message("docker compose config", threats, blocking=True)
        self.assertIn("Blocking", msg)

    def test_non_blocking_says_proceeding(self):
        threats = [{"severity": "high", "description": "exposes vars", "pattern": "x"}]
        msg = credential_guard.build_warn_message("printenv", threats, blocking=False)
        self.assertIn("Proceeding", msg)

    def test_contains_threat_description(self):
        threats = [{"severity": "critical", "description": "dumps ALL environment", "pattern": "x"}]
        msg = credential_guard.build_warn_message("cmd", threats, blocking=False)
        self.assertIn("dumps ALL environment", msg)


class TestResponseFormats(unittest.TestCase):

    def test_allow_response_is_empty(self):
        resp = credential_guard._allow_response()
        self.assertEqual(resp, {})

    def test_warn_response_allows(self):
        resp = credential_guard._warn_response("Watch out!")
        decision = resp["hookSpecificOutput"]["permissionDecision"]
        self.assertEqual(decision, "allow")

    def test_block_response_denies(self):
        resp = credential_guard._block_response("Blocked!")
        decision = resp["hookSpecificOutput"]["permissionDecision"]
        self.assertEqual(decision, "deny")
        self.assertIn("denyReason", resp["hookSpecificOutput"])


class TestMainFunction(unittest.TestCase):
    """Integration: full hook dispatch via stdin."""

    def _run(self, payload: dict, env: dict | None = None) -> tuple[int, dict]:
        import io
        captured = []
        exit_code = 0

        def fake_exit(code=0):
            nonlocal exit_code
            exit_code = code
            raise SystemExit(code)

        env = env or {}
        with patch("sys.stdin", io.StringIO(json.dumps(payload))):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.write = lambda s: captured.append(s)
                with patch.dict("os.environ", env, clear=False):
                    with patch("sys.exit", side_effect=fake_exit):
                        try:
                            credential_guard.main()
                        except SystemExit:
                            pass

        output = "".join(captured)
        try:
            result = json.loads(output) if output.strip() else {}
        except json.JSONDecodeError:
            result = {}
        return exit_code, result

    def test_non_bash_tool_passes_through(self):
        payload = {"tool_name": "Read", "tool_input": {"file_path": "/etc/passwd"}}
        _, resp = self._run(payload)
        self.assertEqual(resp, {})

    def test_safe_bash_passes_through(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        _, resp = self._run(payload)
        self.assertEqual(resp, {})

    def test_dangerous_command_warns_by_default(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "printenv"}}
        _, resp = self._run(payload)
        decision = resp.get("hookSpecificOutput", {}).get("permissionDecision")
        self.assertEqual(decision, "allow")  # Warn, not block

    def test_disabled_allows_everything(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "docker compose config"}}
        _, resp = self._run(payload, env={"CLAUDE_CRED_GUARD_DISABLED": "1"})
        self.assertEqual(resp, {})

    def test_block_mode_blocks_critical(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "docker compose config"}}
        _, resp = self._run(payload, env={"CLAUDE_CRED_GUARD_BLOCK": "1"})
        decision = resp.get("hookSpecificOutput", {}).get("permissionDecision")
        self.assertEqual(decision, "deny")

    def test_critical_blocked_even_without_block_flag(self):
        # Critical-severity threats are blocked regardless of BLOCK flag
        payload = {"tool_name": "Bash", "tool_input": {"command": "cat .env"}}
        _, resp = self._run(payload, env={"CLAUDE_CRED_GUARD_BLOCK": "0"})
        decision = resp.get("hookSpecificOutput", {}).get("permissionDecision")
        self.assertEqual(decision, "deny")


if __name__ == "__main__":
    unittest.main()
