#!/usr/bin/env python3
"""autoloop_stop_hook.py — Stop hook that ensures autoloop trigger fires
even when context exhaustion kills /cca-wrap before Step 10.

Problem: The autoloop trigger (autoloop_trigger.py) is Step 10 of /cca-wrap.
When a session hits the context critical zone, the stop hook blocks exit
BEFORE Step 10 runs, breaking the autoloop chain.

Solution: This Stop hook fires the autoloop trigger independently. It runs
at session exit regardless of whether /cca-wrap completed, ensuring the
next CCA session always gets spawned.

Anti-double-fire: A breadcrumb file prevents both /cca-wrap Step 10 AND
this hook from firing the trigger. Whoever fires first writes the breadcrumb;
the other sees it and skips.

Conditions to fire:
  1. Autoloop is enabled (env var CCA_AUTOLOOP_ENABLED=1 or flag file)
  2. This is a CCA session (CWD contains ClaudeCodeAdvancements)
  3. SESSION_RESUME.md exists and was modified recently (< 10 min)
  4. No fresh breadcrumb exists (trigger hasn't already fired this cycle)

Wire as Stop hook in .claude/settings.local.json:
  {
    "hooks": {
      "Stop": [
        {
          "matcher": "",
          "hooks": [{"type": "command", "command": "python3 /path/to/autoloop_stop_hook.py"}]
        }
      ]
    }
  }

S150 — fixes S149 autoloop chain break from context exhaustion.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
RESUME_FILE = os.path.join(PROJECT_DIR, "SESSION_RESUME.md")
BREADCRUMB_FILE = os.path.expanduser("~/.cca-autoloop-fired")
AUTOLOOP_FLAG_FILE = os.path.expanduser("~/.cca-autoloop-enabled")
AUTOLOOP_PAUSE_FILE = os.path.expanduser("~/.cca-autoloop-paused")
TRIGGER_SCRIPT = os.path.join(PROJECT_DIR, "autoloop_trigger.py")

DEFAULT_MAX_RESUME_AGE = 600  # 10 minutes
DEFAULT_BREADCRUMB_MAX_AGE = 600  # 10 minutes


def is_autoloop_enabled() -> bool:
    """Check if autoloop mode is enabled.

    Sources (in priority order):
      1. CCA_AUTOLOOP_ENABLED env var ("1" = on, "0" = off)
      2. Flag file ~/.cca-autoloop-enabled (exists = on)
      3. Default: disabled (opt-in)
    """
    env_val = os.environ.get("CCA_AUTOLOOP_ENABLED")
    if env_val is not None:
        return env_val == "1"
    return os.path.exists(AUTOLOOP_FLAG_FILE)


def is_autoloop_paused(pause_path: str = AUTOLOOP_PAUSE_FILE) -> bool:
    """Check if autoloop is temporarily paused.

    Paused via ~/.cca-autoloop-paused flag file. When paused, the loop
    stays enabled but skips triggering new sessions until unpaused.
    MT-35 Phase 4: toggle via `python3 autoloop_pause.py toggle`.
    """
    return os.path.exists(pause_path)


def is_cca_session() -> bool:
    """Check if current session is a CCA project session."""
    try:
        cwd = os.getcwd()
        return "ClaudeCodeAdvancements" in cwd
    except OSError:
        return False


def should_trigger(
    resume_path: str = RESUME_FILE,
    breadcrumb_path: str = BREADCRUMB_FILE,
    autoloop_enabled: bool = None,
    max_resume_age_seconds: float = DEFAULT_MAX_RESUME_AGE,
    breadcrumb_max_age_seconds: float = DEFAULT_BREADCRUMB_MAX_AGE,
    pause_path: str = None,
) -> bool:
    """Decide whether to fire the autoloop trigger.

    Returns True only when all conditions are met:
      1. Autoloop is enabled
      2. SESSION_RESUME.md exists, is non-empty, and is fresh
      3. No fresh breadcrumb (trigger hasn't fired recently)
          — UNLESS resume is newer than breadcrumb (new session completed
            after last trigger, so fire again). S152 fix for stale breadcrumb
            preventing back-to-back sessions under 10 minutes.
    """
    # Condition 0: not paused (MT-35 Phase 4)
    if is_autoloop_paused(pause_path or AUTOLOOP_PAUSE_FILE):
        return False

    # Condition 1: autoloop enabled
    if autoloop_enabled is None:
        autoloop_enabled = is_autoloop_enabled()
    if not autoloop_enabled:
        return False

    # Condition 2: resume file exists and is fresh
    if not os.path.exists(resume_path):
        return False
    try:
        with open(resume_path) as f:
            content = f.read().strip()
        if not content:
            return False
        resume_age = time.time() - os.path.getmtime(resume_path)
        if resume_age > max_resume_age_seconds:
            return False
    except OSError:
        return False

    # Condition 3: no fresh breadcrumb — unless resume is newer (new session completed)
    if os.path.exists(breadcrumb_path):
        try:
            bc_mtime = os.path.getmtime(breadcrumb_path)
            bc_age = time.time() - bc_mtime
            if bc_age < breadcrumb_max_age_seconds:
                # Breadcrumb is fresh — but check if resume is newer.
                # If resume was written AFTER the breadcrumb, a new session
                # completed since the last trigger fired. Fire again.
                resume_mtime = os.path.getmtime(resume_path)
                if resume_mtime <= bc_mtime:
                    return False  # Same cycle — trigger already fired
                # Resume is newer than breadcrumb — new session completed
        except OSError:
            pass  # Can't read breadcrumb — proceed cautiously

    return True


def write_breadcrumb(path: str = BREADCRUMB_FILE):
    """Write breadcrumb file to prevent double-fire."""
    try:
        with open(path, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass


def fire_trigger(dry_run: bool = False) -> bool:
    """Spawn autoloop_trigger.py as a detached background process.

    Fire-and-forget: the subprocess continues even after this hook exits.
    Returns True if the subprocess was spawned successfully.
    """
    cmd = [sys.executable, TRIGGER_SCRIPT]
    if dry_run:
        cmd.append("--dry-run")
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except OSError:
        return False


def process_hook(hook_input: str) -> str:
    """Process the Stop hook event.

    Reads hook input JSON, decides whether to fire trigger, and returns
    a JSON response. Stop hooks should NEVER block — always allow exit.
    """
    # Check if this is a CCA session
    if not is_cca_session():
        return json.dumps({})

    if should_trigger():
        success = fire_trigger()
        if success:
            write_breadcrumb()

    # Never block session exit
    return json.dumps({})


if __name__ == "__main__":
    # Read hook input from stdin
    try:
        hook_input = sys.stdin.read()
    except Exception:
        hook_input = "{}"

    result = process_hook(hook_input)
    print(result)
