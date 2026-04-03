#!/usr/bin/env python3
"""terminal_chain.py — CLI session self-chaining for one-off terminal CCA sessions.

Called by autoloop_trigger.py when a one-off terminal session wraps.
Waits for the parent claude process to exit, then launches start_autoloop.sh
to continue the work loop autonomously.

This fills the gap between:
  - Desktop Electron autoloop (autoloop_trigger.py + AppleScript)
  - CLI outer loop (start_autoloop.sh)
  - One-off terminal session (THIS MODULE)

Usage (called by autoloop_trigger.py):
    python3 terminal_chain.py --pid <parent_pid> [--dry-run]

Options:
    --pid PID       Parent claude process PID to wait for (required)
    --dry-run       Simulate without spawning anything
    --status        Print current state and exit
    --timeout N     Max seconds to wait for PID (default: 120)

Exit codes:
    0  Success — autoloop spawned (or dry-run)
    1  Error — invalid args, script not found
    2  Timeout — parent didn't exit within timeout
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = str(Path(__file__).parent.resolve())
AUTOLOOP_SH = os.path.join(PROJECT_DIR, "start_autoloop.sh")
LOG_FILE = os.path.expanduser("~/.cca-terminal-chain.jsonl")

_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def wait_for_pid(pid: int, timeout: float = 120.0, poll_interval: float = 0.5) -> bool:
    """Wait until PID no longer exists (process exited).

    Args:
        pid:           Process ID to watch.
        timeout:       Max seconds to wait.
        poll_interval: How often to check (seconds).

    Returns:
        True if PID exited within timeout, False if timeout reached.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            waited_pid, _status = os.waitpid(pid, os.WNOHANG)
            if waited_pid == pid:
                return True
        except ChildProcessError:
            pass
        try:
            os.kill(pid, 0)  # signal 0: check existence, no effect
        except ProcessLookupError:
            return True  # PID gone — process exited
        except PermissionError:
            # PID exists but we can't signal it — count as alive
            time.sleep(poll_interval)
            continue
        time.sleep(poll_interval)
    return False  # timed out


def launch_autoloop(
    autoloop_sh: str,
    project_dir: str,
    dry_run: bool = False,
) -> bool:
    """Spawn start_autoloop.sh to continue the session chain.

    Args:
        autoloop_sh: Absolute path to start_autoloop.sh.
        project_dir: CCA project directory.
        dry_run:     If True, print what would happen but do nothing.

    Returns:
        True if spawned (or dry-run), False if script not found.
    """
    if dry_run:
        print(f"terminal chain: DRY RUN — would spawn {autoloop_sh}")
        _log("chain_dry_run", {"autoloop_sh": autoloop_sh})
        return True

    if not os.path.exists(autoloop_sh):
        print(f"terminal chain: ERROR — {autoloop_sh} not found")
        _log("chain_error", {"reason": "autoloop_sh_not_found", "path": autoloop_sh})
        return False

    # Spawn detached: strip ANTHROPIC_API_KEY, clear outer-loop flag
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("CCA_AUTOLOOP_CLI", None)

    proc = subprocess.Popen(
        ["bash", autoloop_sh],
        cwd=project_dir,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # detach from current process group
    )
    pid_value = getattr(proc, "pid", None)
    safe_pid = pid_value if isinstance(pid_value, int) else str(pid_value)
    print(f"terminal chain: start_autoloop.sh spawned (PID {safe_pid})")
    _log("chain_spawned", {"autoloop_pid": safe_pid, "autoloop_sh": autoloop_sh})
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(args=None):
    """Parse args and run the chain logic."""
    parser = argparse.ArgumentParser(
        prog="terminal_chain",
        description="CCA one-off terminal session self-chainer",
    )
    parser.add_argument(
        "--pid", type=int, required=False, default=None,
        help="Parent claude PID to wait for",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulate without spawning",
    )
    parser.add_argument(
        "--timeout", type=float, default=120.0,
        help="Max seconds to wait for PID exit (default: 120)",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Print current state and exit 0",
    )
    parser.add_argument(
        "--version", action="store_true",
        help="Print version and exit",
    )

    parsed = parser.parse_args(args)

    if parsed.version:
        print(f"terminal_chain {_VERSION}")
        sys.exit(0)

    if parsed.status:
        log_path = LOG_FILE
        if os.path.exists(log_path):
            print(f"Log: {log_path} (exists)")
            try:
                with open(log_path) as f:
                    lines = f.readlines()
                print(f"Entries: {len(lines)}")
                if lines:
                    print(f"Last: {lines[-1].strip()}")
            except OSError:
                pass
        else:
            print("Log: not found (no chain has run yet)")
        sys.exit(0)

    if parsed.pid is None:
        parser.print_usage(sys.stderr)
        sys.stderr.write("terminal_chain: error: --pid is required\n")
        sys.exit(1)

    pid = parsed.pid
    dry_run = parsed.dry_run
    timeout = parsed.timeout

    _log("chain_start", {"pid": pid, "dry_run": dry_run, "timeout": timeout})
    print(f"terminal chain: waiting for PID {pid} to exit (timeout={timeout}s)...")

    exited = wait_for_pid(pid, timeout=timeout)
    if not exited:
        print(f"terminal chain: TIMEOUT — PID {pid} still alive after {timeout}s")
        _log("chain_timeout", {"pid": pid})
        return 2

    print(f"terminal chain: PID {pid} exited — launching autoloop")
    ok = launch_autoloop(AUTOLOOP_SH, PROJECT_DIR, dry_run=dry_run)
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _log(event: str, data: dict = None):
    """Append to chain audit log."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": event,
        **(data or {}),
    }
    import json
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
