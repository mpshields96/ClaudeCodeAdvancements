#!/usr/bin/env python3
"""autoloop_trigger.py — CCA-internal autoloop trigger (MT-22, S138).

Called as the FINAL step of /cca-wrap. This script:
1. Reads SESSION_RESUME.md
2. Verifies Claude.app is on the Code tab
3. Clicks "+ New session" (Cmd+N) to open a fresh chat
4. Pastes the resume prompt into the NEW chat
5. Sends it (Cmd+Return)

The new CCA session picks up from /cca-init and the cycle continues.

This runs FROM WITHIN a CCA session (inside Claude.app's Code tab).
The AppleScript commands target Claude.app itself — the session automates
its own app to spawn the next session.

Usage:
    python3 autoloop_trigger.py                 # Run the trigger
    python3 autoloop_trigger.py --dry-run       # Simulate (no keystrokes)
    python3 autoloop_trigger.py --check         # Verify readiness only
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Import the automator
sys.path.insert(0, str(Path(__file__).parent))
from desktop_automator import DesktopAutomator

PROJECT_DIR = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
RESUME_FILE = os.path.join(PROJECT_DIR, "SESSION_RESUME.md")
AUDIT_LOG = os.path.expanduser("~/.cca-autoloop-trigger.jsonl")
PROMPT_PREFIX = "/cca-init then review the resume prompt below then /cca-auto\n\n"


def _log(event: str, data: dict = None):
    """Append to trigger audit log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": event,
        **(data or {}),
    }
    try:
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def read_resume() -> str:
    """Read SESSION_RESUME.md content."""
    if not os.path.exists(RESUME_FILE):
        return ""
    with open(RESUME_FILE) as f:
        return f.read().strip()


def build_prompt(resume: str) -> str:
    """Build the full prompt from resume content."""
    return PROMPT_PREFIX + resume


def check_readiness() -> dict:
    """Check if the trigger can run."""
    checks = {}

    # Resume file exists and has content
    resume = read_resume()
    if resume:
        checks["resume_file"] = "PASS"
    else:
        checks["resume_file"] = "FAIL"
        checks["resume_detail"] = "SESSION_RESUME.md missing or empty"

    # Claude.app is running
    automator = DesktopAutomator(audit_log=Path(AUDIT_LOG), dry_run=True)
    # Just check osascript works
    ok, _ = automator._run_applescript("return 1")
    checks["osascript"] = "PASS" if ok else "FAIL"

    return checks


def trigger_next_session(dry_run: bool = False) -> bool:
    """Trigger the next CCA session.

    Steps (matching CLAUDE.md Desktop Autoloop Workflow):
    1. Verify Code tab is active
    2. Click "+ New session" (Cmd+N)
    3. Wait for new chat to load
    4. Paste resume prompt
    5. Send with Cmd+Return

    Returns True if all steps succeeded.
    """
    _log("trigger_start", {"dry_run": dry_run})

    # Check pause state (MT-35 Phase 4)
    pause_file = os.path.expanduser("~/.cca-autoloop-paused")
    if os.path.exists(pause_file):
        _log("trigger_skipped", {"reason": "paused"})
        print("Autoloop PAUSED — skipping trigger. Resume with: python3 autoloop_pause.py resume")
        return False

    # Read resume
    resume = read_resume()
    if not resume:
        _log("trigger_failed", {"reason": "no_resume"})
        print("ERROR: SESSION_RESUME.md is missing or empty.")
        return False

    prompt = build_prompt(resume)
    _log("prompt_built", {"length": len(prompt)})

    automator = DesktopAutomator(
        audit_log=Path(AUDIT_LOG),
        dry_run=dry_run,
    )

    # Step -2: Wait for user idle before stealing focus (MT-35 Phase 2)
    # Polls mouse/keyboard idle via CoreGraphics. Default: wait for 3s idle,
    # up to 30s timeout. If timeout expires, proceed anyway (fail open).
    idle_threshold = float(os.environ.get("CCA_IDLE_THRESHOLD", "3.0"))
    idle_timeout = float(os.environ.get("CCA_IDLE_TIMEOUT", "30.0"))
    if idle_threshold > 0 and not dry_run:
        _log("idle_wait_start", {"threshold": idle_threshold, "timeout": idle_timeout})
        idle_ok = automator.wait_for_idle(
            idle_threshold=idle_threshold,
            timeout=idle_timeout,
        )
        if idle_ok:
            _log("idle_wait_done", {"result": "idle_detected"})
        else:
            _log("idle_wait_done", {"result": "timeout_proceeding"})
            print(f"NOTE: User active for {idle_timeout}s — proceeding anyway.")

    # Step -1: Save the app Matthew is currently using (MT-35)
    # So we can restore focus after spawning the new session.
    saved_app = automator.save_frontmost_app()
    if saved_app:
        _log("step_pre_save", {"saved_app": str(saved_app)})

    # Step 0: Activate Claude.app (bring to foreground)
    # When called from a CCA session, the bash subprocess runs in Terminal
    # context, so Claude.app is NOT frontmost. We must activate it first.
    if not automator.activate_claude():
        _log("trigger_failed", {"reason": "activate_failed"})
        print("ERROR: Could not activate Claude.app.")
        # Restore focus even on failure
        if saved_app:
            automator.restore_frontmost_app()
        return False
    _log("step_0_activate", {"status": "ok"})

    # Step 1: Verify Code tab is active
    # ensure_code_tab() detects via accessibility, clicks if needed,
    # proceeds optimistically if Electron doesn't expose tab state
    if not automator.ensure_code_tab():
        _log("trigger_failed", {"reason": "code_tab_failed"})
        print("ERROR: Could not verify/switch to Code tab.")
        return False
    _log("step_1_code_tab", {"status": "ok"})

    # Step 2: Click "+ New session" (Cmd+N)
    # new_conversation() verifies frontmost + Code tab, then sends Cmd+N
    time.sleep(0.3)
    if not automator.new_conversation():
        _log("trigger_failed", {"reason": "new_conversation_failed"})
        print("ERROR: Could not start new conversation (Cmd+N failed).")
        return False
    _log("step_2_new_session", {"status": "ok"})

    # Step 3: Wait for new chat to load
    wait_time = 2.0 if not dry_run else 0.0
    if wait_time > 0:
        time.sleep(wait_time)
    _log("step_3_wait", {"seconds": wait_time})

    # Step 4+5: Paste prompt and send (Cmd+Return)
    if not automator.send_prompt(prompt):
        _log("trigger_failed", {"reason": "send_failed"})
        print("ERROR: Could not paste/send prompt.")
        return False
    _log("step_4_send", {"status": "ok", "prompt_length": len(prompt)})

    # Step 5: Restore focus to whatever Matthew was using (MT-35)
    if saved_app:
        time.sleep(0.3)  # Brief pause for prompt to register
        if automator.restore_frontmost_app():
            _log("step_5_restore", {"restored_app": str(saved_app)})
        else:
            _log("step_5_restore_failed", {"target_app": str(saved_app)})

    _log("trigger_success")
    # Write breadcrumb to prevent double-fire from stop hook (S150)
    breadcrumb_path = os.path.expanduser("~/.cca-autoloop-fired")
    try:
        with open(breadcrumb_path, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass
    print(f"Autoloop trigger fired. Prompt ({len(prompt)} chars) sent to new session.")
    return True


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--check" in args:
        checks = check_readiness()
        print("Autoloop Trigger Readiness:")
        for k, v in checks.items():
            marker = "[OK]" if v == "PASS" else "[!!]"
            print(f"  {marker} {k}: {v}")
        all_pass = all(v == "PASS" for v in checks.values())
        sys.exit(0 if all_pass else 1)

    dry_run = "--dry-run" in args
    success = trigger_next_session(dry_run=dry_run)
    sys.exit(0 if success else 1)
