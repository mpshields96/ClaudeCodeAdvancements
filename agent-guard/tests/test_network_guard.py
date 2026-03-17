#!/usr/bin/env python3
"""Tests for network_guard.py — AG-5: Network/port exposure guard.

Prevents Claude from accidentally exposing ports to the internet,
modifying firewall rules, or changing network configuration.
Validates BUILD verdict from "We got hacked" incident (458pts, r/ClaudeCode).
"""

import json
import os
import sys
import unittest
from unittest.mock import patch
from io import StringIO

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
HOOKS_DIR = os.path.join(MODULE_DIR, "hooks")
sys.path.insert(0, HOOKS_DIR)
sys.path.insert(0, MODULE_DIR)

import network_guard


class TestPortExposureDetection(unittest.TestCase):
    """Test detection of commands that expose ports to the internet."""

    def test_adb_tcpip_detected(self):
        """The exact attack vector from 'We got hacked' — ADB exposed on port 5555."""
        threats = network_guard.check_command("adb tcpip 5555")
        self.assertGreater(len(threats), 0)
        self.assertTrue(any("adb" in t["description"].lower() for t in threats))

    def test_socat_listen_all_interfaces(self):
        threats = network_guard.check_command("socat TCP-LISTEN:8080,reuseaddr,fork EXEC:./app")
        self.assertGreater(len(threats), 0)

    def test_nc_listen(self):
        threats = network_guard.check_command("nc -lvp 4444")
        self.assertGreater(len(threats), 0)

    def test_python_server_all_interfaces(self):
        threats = network_guard.check_command("python3 -m http.server 8080 --bind 0.0.0.0")
        self.assertGreater(len(threats), 0)

    def test_python_server_default_bind(self):
        """python -m http.server without --bind defaults to all interfaces."""
        threats = network_guard.check_command("python3 -m http.server 8080")
        self.assertGreater(len(threats), 0)

    def test_node_listen_all_interfaces(self):
        threats = network_guard.check_command("node -e \"require('http').createServer().listen(3000, '0.0.0.0')\"")
        self.assertGreater(len(threats), 0)

    def test_docker_port_all_interfaces(self):
        """Docker -p without 127.0.0.1 binds to 0.0.0.0 by default."""
        threats = network_guard.check_command("docker run -p 8080:80 nginx")
        self.assertGreater(len(threats), 0)

    def test_docker_port_explicit_all(self):
        threats = network_guard.check_command("docker run -p 0.0.0.0:8080:80 nginx")
        self.assertGreater(len(threats), 0)

    def test_docker_port_localhost_safe(self):
        """Docker -p 127.0.0.1:PORT:PORT is safe."""
        threats = network_guard.check_command("docker run -p 127.0.0.1:8080:80 nginx")
        port_threats = [t for t in threats if "docker" in t["description"].lower() and "port" in t["description"].lower()]
        self.assertEqual(len(port_threats), 0)

    def test_ssh_remote_forward_all(self):
        threats = network_guard.check_command("ssh -R 0.0.0.0:8080:localhost:8080 user@server")
        self.assertGreater(len(threats), 0)

    def test_ssh_local_forward_safe(self):
        """ssh -L localhost:8080:remote:80 is safe (local only)."""
        threats = network_guard.check_command("ssh -L 127.0.0.1:8080:remote:80 user@server")
        ssh_threats = [t for t in threats if "ssh" in t["description"].lower() and "forward" in t["description"].lower()]
        self.assertEqual(len(ssh_threats), 0)


class TestFirewallModification(unittest.TestCase):
    """Test detection of firewall/iptables modifications."""

    def test_ufw_allow(self):
        threats = network_guard.check_command("ufw allow 8080")
        self.assertGreater(len(threats), 0)

    def test_ufw_delete(self):
        threats = network_guard.check_command("ufw delete deny 22")
        self.assertGreater(len(threats), 0)

    def test_ufw_disable(self):
        threats = network_guard.check_command("ufw disable")
        self.assertGreater(len(threats), 0)
        self.assertTrue(any(t["severity"] == "critical" for t in threats))

    def test_iptables_flush(self):
        threats = network_guard.check_command("iptables -F")
        self.assertGreater(len(threats), 0)
        self.assertTrue(any(t["severity"] == "critical" for t in threats))

    def test_iptables_append_accept(self):
        threats = network_guard.check_command("iptables -A INPUT -p tcp --dport 8080 -j ACCEPT")
        self.assertGreater(len(threats), 0)

    def test_nftables(self):
        threats = network_guard.check_command("nft add rule inet filter input tcp dport 8080 accept")
        self.assertGreater(len(threats), 0)

    def test_firewalld(self):
        threats = network_guard.check_command("firewall-cmd --add-port=8080/tcp")
        self.assertGreater(len(threats), 0)

    def test_ufw_status_safe(self):
        """ufw status is read-only — should not trigger."""
        threats = network_guard.check_command("ufw status")
        self.assertEqual(len(threats), 0)

    def test_iptables_list_safe(self):
        """iptables -L is read-only — should not trigger."""
        threats = network_guard.check_command("iptables -L")
        self.assertEqual(len(threats), 0)


class TestNetworkConfigChanges(unittest.TestCase):
    """Test detection of network configuration changes."""

    def test_etc_hosts_modification(self):
        threats = network_guard.check_command("echo '1.2.3.4 evil.com' >> /etc/hosts")
        self.assertGreater(len(threats), 0)

    def test_sshd_config_modification(self):
        threats = network_guard.check_command("sed -i 's/PermitRootLogin no/PermitRootLogin yes/' /etc/ssh/sshd_config")
        self.assertGreater(len(threats), 0)

    def test_ngrok_tunnel(self):
        """ngrok exposes local ports to the public internet."""
        threats = network_guard.check_command("ngrok http 8080")
        self.assertGreater(len(threats), 0)

    def test_cloudflared_tunnel(self):
        threats = network_guard.check_command("cloudflared tunnel run")
        self.assertGreater(len(threats), 0)

    def test_reading_etc_hosts_safe(self):
        """cat /etc/hosts is read-only — should not trigger."""
        threats = network_guard.check_command("cat /etc/hosts")
        self.assertEqual(len(threats), 0)


class TestSafeCommands(unittest.TestCase):
    """Test that normal commands don't trigger false positives."""

    def test_git_push(self):
        threats = network_guard.check_command("git push origin main")
        self.assertEqual(len(threats), 0)

    def test_npm_install(self):
        threats = network_guard.check_command("npm install express")
        self.assertEqual(len(threats), 0)

    def test_curl_fetch(self):
        threats = network_guard.check_command("curl https://api.example.com/data")
        self.assertEqual(len(threats), 0)

    def test_python_script(self):
        threats = network_guard.check_command("python3 my_script.py")
        self.assertEqual(len(threats), 0)

    def test_docker_build(self):
        threats = network_guard.check_command("docker build -t myapp .")
        self.assertEqual(len(threats), 0)

    def test_ssh_connect(self):
        """Plain ssh connection is safe."""
        threats = network_guard.check_command("ssh user@server.com")
        self.assertEqual(len(threats), 0)

    def test_localhost_server(self):
        """Python server explicitly bound to localhost is safe."""
        threats = network_guard.check_command("python3 -m http.server 8080 --bind 127.0.0.1")
        self.assertEqual(len(threats), 0)

    def test_flask_localhost(self):
        threats = network_guard.check_command("flask run --host=127.0.0.1")
        self.assertEqual(len(threats), 0)

    def test_grep_port(self):
        """Grepping for 'port' in code should not trigger."""
        threats = network_guard.check_command("grep -r 'port' src/")
        self.assertEqual(len(threats), 0)


class TestSeverityClassification(unittest.TestCase):
    """Test that threat severity levels are correct."""

    def test_ufw_disable_is_critical(self):
        threats = network_guard.check_command("ufw disable")
        self.assertTrue(any(t["severity"] == "critical" for t in threats))

    def test_iptables_flush_is_critical(self):
        threats = network_guard.check_command("iptables -F")
        self.assertTrue(any(t["severity"] == "critical" for t in threats))

    def test_adb_tcpip_is_critical(self):
        threats = network_guard.check_command("adb tcpip 5555")
        self.assertTrue(any(t["severity"] == "critical" for t in threats))

    def test_ngrok_is_critical(self):
        threats = network_guard.check_command("ngrok http 3000")
        self.assertTrue(any(t["severity"] == "critical" for t in threats))

    def test_docker_port_is_high(self):
        threats = network_guard.check_command("docker run -p 8080:80 nginx")
        self.assertTrue(any(t["severity"] == "high" for t in threats))

    def test_nc_listen_is_high(self):
        threats = network_guard.check_command("nc -lp 4444")
        self.assertTrue(any(t["severity"] == "high" for t in threats))


class TestHookResponse(unittest.TestCase):
    """Test hook JSON response format."""

    def test_allow_response(self):
        r = network_guard._allow_response()
        self.assertEqual(r, {})

    def test_warn_response_has_permission_decision(self):
        r = network_guard._warn_response("test warning")
        self.assertEqual(
            r["hookSpecificOutput"]["permissionDecision"], "allow"
        )
        self.assertEqual(r["reason"], "test warning")

    def test_block_response_denies(self):
        r = network_guard._block_response("test block")
        self.assertEqual(
            r["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIn("test block", r["hookSpecificOutput"]["denyReason"])

    def test_build_warn_message_format(self):
        threats = [{"severity": "high", "description": "test threat"}]
        msg = network_guard.build_warn_message("test cmd", threats, False)
        self.assertIn("AG-5", msg)
        self.assertIn("test threat", msg)
        self.assertIn("test cmd", msg)

    def test_build_warn_message_blocking(self):
        threats = [{"severity": "critical", "description": "critical threat"}]
        msg = network_guard.build_warn_message("bad cmd", threats, True)
        self.assertIn("Blocking", msg)


class TestHookMainFunction(unittest.TestCase):
    """Test the main() hook entry point."""

    def _run_hook(self, payload, env_overrides=None):
        """Run the hook with a given payload and return the JSON response."""
        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)

        with patch.dict(os.environ, env, clear=False):
            with patch("sys.stdin", StringIO(json.dumps(payload))):
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    with self.assertRaises(SystemExit) as ctx:
                        network_guard.main()
                    self.assertEqual(ctx.exception.code, 0)
                    output = mock_out.getvalue().strip()
                    return json.loads(output) if output else {}

    def test_non_bash_tool_passes(self):
        payload = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/test"}}
        result = self._run_hook(payload)
        self.assertEqual(result, {})

    def test_safe_bash_passes(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "git status"}}
        result = self._run_hook(payload)
        self.assertEqual(result, {})

    def test_dangerous_command_blocks_by_default(self):
        """Critical threats block even without BLOCK env var."""
        payload = {"tool_name": "Bash", "tool_input": {"command": "ufw disable"}}
        result = self._run_hook(payload)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_high_threat_warns_by_default(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "nc -lp 4444"}}
        result = self._run_hook(payload)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")
        self.assertIn("reason", result)

    def test_block_mode_blocks_high(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "nc -lp 4444"}}
        result = self._run_hook(payload, env_overrides={"CLAUDE_NET_GUARD_BLOCK": "1"})
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_disabled_passes_everything(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "ufw disable"}}
        result = self._run_hook(payload, env_overrides={"CLAUDE_NET_GUARD_DISABLED": "1"})
        self.assertEqual(result, {})

    def test_empty_command_passes(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": ""}}
        result = self._run_hook(payload)
        self.assertEqual(result, {})

    def test_string_tool_input_parsed(self):
        """tool_input can be a JSON string."""
        payload = {"tool_name": "Bash", "tool_input": json.dumps({"command": "ufw disable"})}
        result = self._run_hook(payload)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
