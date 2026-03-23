"""desktop_autoloop.py — MT-22: Desktop Auto-Loop Orchestrator.

Self-sustaining loop that runs CCA sessions in Claude.app (Electron).
Like OpenClaw's Mac Mini pattern: starts a session, watches it work,
detects when it wraps, starts the next session. Matthew watches and
interacts freely while it runs.

Signal mechanism: SESSION_RESUME.md mtime change = session wrapped.
When /cca-wrap writes a new resume file, this loop detects it and
starts the next iteration.

Usage:
    python3 desktop_autoloop.py start                     # Run the loop
    python3 desktop_autoloop.py start --dry-run            # Simulate
    python3 desktop_autoloop.py start --max-iterations 5   # Limit runs
    python3 desktop_autoloop.py preflight                  # Check readiness
    python3 desktop_autoloop.py status                     # Show state

Safety:
    - Max iterations (default 50)
    - 3 consecutive crashes = stop
    - 3 consecutive short sessions (<30s) = stop
    - Cooldown between sessions (default 15s)
    - Full JSONL audit trail
    - Matthew can interact with the desktop app freely during sessions

Stdlib only. No external dependencies.
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from desktop_automator import DesktopAutomator

# --- Constants ---

DEFAULT_PROJECT_DIR = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
DEFAULT_MAX_ITERATIONS = 50
DEFAULT_COOLDOWN = 15
MIN_COOLDOWN = 5
MIN_SESSION_DURATION = 30  # seconds — shorter = something broke
MAX_CONSECUTIVE_CRASHES = 3
MAX_CONSECUTIVE_SHORT = 3
MAX_PROMPT_SIZE = 100_000
FALLBACK_PROMPT = "Run /cca-init then /cca-auto. No resume prompt was found."
VALID_MODEL_STRATEGIES = ("round-robin", "opus-primary", "sonnet-primary")
DEFAULT_AUDIT_LOG = os.path.expanduser("~/.cca-desktop-autoloop.jsonl")
DEFAULT_STATE_FILE = os.path.expanduser("~/.cca-desktop-autoloop-state.json")


# --- Config ---

@dataclass
class DesktopLoopConfig:
    """Configuration for the desktop auto-loop."""
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    cooldown_seconds: int = DEFAULT_COOLDOWN
    session_timeout: int = 14400  # 4 hours max per session
    project_dir: str = DEFAULT_PROJECT_DIR
    resume_file: str = ""
    audit_log: str = DEFAULT_AUDIT_LOG
    state_file: str = DEFAULT_STATE_FILE
    model_strategy: str = "round-robin"
    dry_run: bool = False
    activate_delay: float = 0.5
    poll_interval: float = 10.0  # how often to check for session end

    def __post_init__(self):
        if self.max_iterations < 1:
            self.max_iterations = 1
        if self.cooldown_seconds < MIN_COOLDOWN:
            self.cooldown_seconds = MIN_COOLDOWN
        if self.model_strategy not in VALID_MODEL_STRATEGIES:
            self.model_strategy = "round-robin"
        if not self.resume_file:
            self.resume_file = os.path.join(self.project_dir, "SESSION_RESUME.md")

    @classmethod
    def from_dict(cls, d: dict) -> "DesktopLoopConfig":
        valid_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)


# --- State ---

@dataclass
class DesktopLoopState:
    """Runtime state for the desktop auto-loop."""
    iteration: int = 0
    total_sessions: int = 0
    total_crashes: int = 0
    last_exit_code: Optional[int] = None
    should_stop: bool = False
    stop_reason: str = ""
    max_iterations: int = DEFAULT_MAX_ITERATIONS

    _consecutive_crashes: int = field(default=0, repr=False)
    _consecutive_short: int = field(default=0, repr=False)
    _session_durations: list = field(default_factory=list, repr=False)

    def record_session(self, exit_code: int, duration: float):
        """Record a completed session."""
        self.iteration += 1
        self.total_sessions += 1
        self.last_exit_code = exit_code
        self._session_durations.append(duration)

        # Track crashes
        if exit_code != 0:
            self.total_crashes += 1
            self._consecutive_crashes += 1
        else:
            self._consecutive_crashes = 0

        # Track short sessions
        if duration < MIN_SESSION_DURATION:
            self._consecutive_short += 1
        else:
            self._consecutive_short = 0

        # Check stop conditions
        if self._consecutive_crashes >= MAX_CONSECUTIVE_CRASHES:
            self.should_stop = True
            self.stop_reason = f"{MAX_CONSECUTIVE_CRASHES}_consecutive_crashes"
        elif self._consecutive_short >= MAX_CONSECUTIVE_SHORT:
            self.should_stop = True
            self.stop_reason = f"{MAX_CONSECUTIVE_SHORT}_consecutive_short_sessions"
        elif self.iteration >= self.max_iterations:
            self.should_stop = True
            self.stop_reason = "max_iterations_reached"

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "total_sessions": self.total_sessions,
            "total_crashes": self.total_crashes,
            "last_exit_code": self.last_exit_code,
            "should_stop": self.should_stop,
            "stop_reason": self.stop_reason,
        }

    def summary(self) -> str:
        avg_dur = (
            sum(self._session_durations) / len(self._session_durations)
            if self._session_durations
            else 0
        )
        lines = [
            f"Iterations: {self.iteration}/{self.max_iterations}",
            f"Sessions: {self.total_sessions}  Crashes: {self.total_crashes}",
            f"Avg duration: {avg_dur:.0f}s",
            f"Last exit: {self.last_exit_code}",
        ]
        if self.should_stop:
            lines.append(f"STOPPED: {self.stop_reason}")
        return "\n".join(lines)


# --- Resume file watcher ---

class ResumeWatcher:
    """Watches SESSION_RESUME.md for changes (mtime-based).

    When /cca-wrap runs at the end of a session, it writes a new
    SESSION_RESUME.md. This watcher detects that change as the signal
    that the session has completed.
    """

    def __init__(self, resume_path: str):
        self.resume_path = resume_path
        self._last_mtime: Optional[float] = None

    def read_resume(self) -> str:
        """Read the resume prompt. Returns FALLBACK_PROMPT on error."""
        try:
            with open(self.resume_path) as f:
                content = f.read().strip()
            if not content:
                return FALLBACK_PROMPT
            if len(content) > MAX_PROMPT_SIZE:
                content = content[:MAX_PROMPT_SIZE] + "\n\n[TRUNCATED — resume prompt exceeded 100KB]"
            return content
        except OSError:
            return FALLBACK_PROMPT

    def snapshot_mtime(self):
        """Record current mtime of the resume file."""
        try:
            self._last_mtime = os.path.getmtime(self.resume_path)
        except OSError:
            self._last_mtime = None

    def has_changed(self) -> bool:
        """Check if resume file mtime has changed since last snapshot."""
        if self._last_mtime is None:
            return False
        try:
            current_mtime = os.path.getmtime(self.resume_path)
            return current_mtime != self._last_mtime
        except OSError:
            return False


# --- Main loop ---

class DesktopAutoLoop:
    """Orchestrates the self-sustaining desktop auto-loop.

    Flow per iteration:
    1. Read SESSION_RESUME.md
    2. Activate Claude.app
    3. Start new conversation (Cmd+N) — skip on first iteration
    4. Paste resume prompt via clipboard
    5. Send with Cmd+Return
    6. Monitor SESSION_RESUME.md for changes (= session wrapped)
    7. Cooldown, then repeat
    """

    def __init__(self, config: DesktopLoopConfig):
        self.config = config
        self.automator = DesktopAutomator(
            activate_delay=config.activate_delay,
            response_timeout=config.session_timeout,
            audit_log=Path(config.audit_log),
            dry_run=config.dry_run,
        )
        self.watcher = ResumeWatcher(config.resume_file)
        self.state = DesktopLoopState(max_iterations=config.max_iterations)
        self._is_first_iteration = True

    def _log(self, event: str, data: dict = None):
        """Append to loop audit log."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event": event,
            **(data or {}),
        }
        try:
            with open(self.config.audit_log, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def _save_state(self):
        """Persist state to disk."""
        try:
            with open(self.config.state_file, "w") as f:
                json.dump(self.state.to_dict(), f, indent=2)
        except OSError:
            pass

    def _select_model(self, iteration: int) -> str:
        """Select model for this iteration."""
        if self.config.model_strategy == "opus-primary":
            return "opus"
        elif self.config.model_strategy == "sonnet-primary":
            return "sonnet"
        else:
            return "sonnet" if iteration % 2 == 1 else "opus"

    def _build_prompt(self) -> str:
        """Build the full prompt from resume file."""
        resume = self.watcher.read_resume()
        return (
            "/cca-init then review the resume prompt below then /cca-auto\n\n"
            f"{resume}"
        )

    def _send_prompt_to_app(self, prompt: str) -> bool:
        """Activate Claude, optionally start new conversation, send prompt.

        On first iteration, assumes the user already has a fresh chat
        open (or the app just launched), so skips Cmd+N.
        """
        # Step 1: Activate Claude
        if not self.automator.activate_claude():
            self._log("send_failed", {"reason": "activate_failed"})
            return False

        # Step 2: New conversation (skip on first iteration)
        if not self._is_first_iteration:
            time.sleep(0.3)
            if not self.automator.new_conversation():
                self._log("send_failed", {"reason": "new_conversation_failed"})
                return False
            time.sleep(1.0)  # wait for new chat to load

        # Step 3: Send prompt
        if not self.automator.send_prompt(prompt):
            self._log("send_failed", {"reason": "prompt_send_failed"})
            return False

        self._is_first_iteration = False
        return True

    def _wait_for_session_end(self, poll_interval: float = None) -> tuple:
        """Wait for session to complete by watching resume file + CPU idle.

        Primary signal: SESSION_RESUME.md mtime change (= /cca-wrap ran).
        Secondary signal: CPU idle logging for observability.

        Returns (exit_code, duration).
        exit_code 0 = session wrapped successfully (file changed).
        exit_code 1 = timeout (session may have stalled).
        """
        poll = poll_interval or self.config.poll_interval
        start = time.time()
        timeout = self.config.session_timeout
        last_cpu_log = 0.0
        cpu_log_interval = 60.0  # log CPU state every 60s

        while (time.time() - start) < timeout:
            # Primary: check for file change
            if self.watcher.has_changed():
                duration = time.time() - start
                self._log("session_end_detected", {
                    "method": "file_change",
                    "duration": round(duration, 1),
                })
                return (0, duration)

            # Secondary: periodic CPU state logging (observability only)
            elapsed = time.time() - start
            if elapsed - last_cpu_log >= cpu_log_interval:
                cpu = self.automator.get_claude_cpu_usage()
                idle = self.automator.is_claude_idle()
                self._log("cpu_check", {
                    "cpu_pct": round(cpu, 1),
                    "idle": idle,
                    "elapsed": round(elapsed, 0),
                })
                last_cpu_log = elapsed

            if not self.config.dry_run:
                time.sleep(poll)
            else:
                break

        duration = time.time() - start
        self._log("session_timeout", {"duration": round(duration, 1)})
        return (1, duration)

    def _run_one_iteration(self) -> dict:
        """Run a single loop iteration."""
        iteration = self.state.iteration + 1
        model = self._select_model(iteration)
        result = {
            "iteration": iteration,
            "model": model,
            "success": False,
            "duration": 0.0,
        }

        self._log("iteration_start", {"iteration": iteration, "model": model})

        # Build and send prompt
        prompt = self._build_prompt()
        result["prompt_length"] = len(prompt)

        # Snapshot resume file mtime BEFORE sending
        self.watcher.snapshot_mtime()

        if not self._send_prompt_to_app(prompt):
            result["error"] = "send_failed"
            result["duration"] = 0.0
            return result

        # Wait for session to complete
        exit_code, duration = self._wait_for_session_end()
        result["success"] = True
        result["exit_code"] = exit_code
        result["duration"] = duration

        self._log("iteration_complete", result)
        return result

    def preflight(self) -> dict:
        """Run pre-flight checks for the desktop loop."""
        checks = {}

        # Automator pre-flight (osascript, Claude installed/running)
        auto_checks = self.automator.preflight()
        checks["automator_preflight"] = (
            "PASS" if all(v != "FAIL" for v in auto_checks.values()) else "FAIL"
        )

        # Resume file exists
        if os.path.exists(self.config.resume_file):
            checks["resume_file"] = "PASS"
        else:
            checks["resume_file"] = "WARN"

        # Project directory exists
        checks["project_dir"] = (
            "PASS" if os.path.isdir(self.config.project_dir) else "FAIL"
        )

        # Audit log writable
        try:
            Path(self.config.audit_log).parent.mkdir(parents=True, exist_ok=True)
            checks["audit_log"] = "PASS"
        except OSError:
            checks["audit_log"] = "FAIL"

        self._log("loop_preflight", checks)
        return checks

    def run(self):
        """Run the desktop auto-loop until stopped.

        Loops: build prompt -> send to Claude.app -> wait for wrap ->
        cooldown -> repeat.
        """
        self._log("loop_start", {
            "max_iterations": self.config.max_iterations,
            "model_strategy": self.config.model_strategy,
            "dry_run": self.config.dry_run,
        })

        while not self.state.should_stop:
            result = self._run_one_iteration()

            if result.get("success"):
                exit_code = result.get("exit_code", 0)
                duration = result.get("duration", 0.0)
            else:
                # Send failure = crash
                exit_code = 1
                duration = result.get("duration", 0.0)

            self.state.record_session(exit_code, duration)
            self._save_state()

            if self.state.should_stop:
                break

            # Cooldown between sessions
            if not self.config.dry_run:
                time.sleep(self.config.cooldown_seconds)

        self._log("loop_end", self.state.to_dict())
        self._save_state()


# --- CLI ---

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: desktop_autoloop.py <command> [options]")
        print("Commands:")
        print("  start              Start the desktop auto-loop")
        print("  preflight          Run pre-flight checks")
        print("  status             Show current state")
        print()
        print("Options for 'start':")
        print("  --dry-run          Simulate without sending keystrokes")
        print("  --max-iterations N Limit loop iterations (default 50)")
        print("  --model opus       Use opus for all sessions")
        print("  --model sonnet     Use sonnet for all sessions")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "preflight":
        loop = DesktopAutoLoop(DesktopLoopConfig())
        checks = loop.preflight()
        print("Desktop Auto-Loop Pre-Flight Checks:")
        for k, v in checks.items():
            marker = "[OK]" if v == "PASS" else ("[!!]" if v == "FAIL" else "[??]")
            print(f"  {marker} {k}: {v}")
        failed = [k for k, v in checks.items() if v == "FAIL"]
        if failed:
            print(f"\nFAILED: {', '.join(failed)}")
            sys.exit(1)
        else:
            print("\nAll checks passed. Ready to start.")
            sys.exit(0)

    elif cmd == "status":
        state_file = DEFAULT_STATE_FILE
        if os.path.exists(state_file):
            with open(state_file) as f:
                state = json.load(f)
            print("Desktop Auto-Loop State:")
            for k, v in state.items():
                print(f"  {k}: {v}")
        else:
            print("No state file found. Loop has not been run yet.")
        sys.exit(0)

    elif cmd == "start":
        kwargs = {}
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--dry-run":
                kwargs["dry_run"] = True
            elif args[i] == "--max-iterations" and i + 1 < len(args):
                kwargs["max_iterations"] = int(args[i + 1])
                i += 1
            elif args[i] == "--model" and i + 1 < len(args):
                model = args[i + 1]
                if model == "opus":
                    kwargs["model_strategy"] = "opus-primary"
                elif model == "sonnet":
                    kwargs["model_strategy"] = "sonnet-primary"
                i += 1
            elif args[i] == "--cooldown" and i + 1 < len(args):
                kwargs["cooldown_seconds"] = int(args[i + 1])
                i += 1
            i += 1

        cfg = DesktopLoopConfig(**kwargs)
        loop = DesktopAutoLoop(cfg)

        print("=" * 50)
        print("  CCA Desktop Auto-Loop")
        print(f"  Max iterations: {cfg.max_iterations}")
        print(f"  Model strategy: {cfg.model_strategy}")
        print(f"  Dry run: {cfg.dry_run}")
        print(f"  Cooldown: {cfg.cooldown_seconds}s")
        print("=" * 50)
        print()

        loop.run()

        print()
        print(loop.state.summary())

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
