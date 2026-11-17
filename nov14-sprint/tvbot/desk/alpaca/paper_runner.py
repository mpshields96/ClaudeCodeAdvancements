"""Timed, operator-started PAPER session for the connected Alpaca paper desk.

The installed desk only checks for a new closed bar when someone presses "Check for new closed bar".
This runner presses that same check for you on a timer, for a bounded number of minutes, and then stops.
It is started by hand. It installs no schedule, launch agent or automatic run.

What it does, in order:
1. Refuses to start unless this is the paper desk: the approved limits worksheet exists, no other runner holds
   this desk, no live desk and no paper desk on another state folder is running, and the desk's own health and
   session say broker mode alpaca-paper, a real (not mock) broker, this state folder and the paper adapter file.
2. Attaches to the paper desk if it is already open; otherwise opens it with the normal paper launcher.
3. Runs a read-only reconcile and accepts it only when it is positive and fresh: the desk ran it, Alpaca answered
   (connected, complete order list), the report is from this call, the broker position is a number, the working
   order list is present, and the desk's session shows that same reconcile. Anything else, a broker position that
   does not match the desk's own, or an order at Alpaca the desk did not place, stops it there.
4. Every --every seconds it runs one desk check (the same call as the button) and prints one line: UTC time,
   account mode, adapter and arm state, the latest bar and its age, whether the latest decision was a strategy
   call or plumbing (warm-up, closed market, data problem), the position, and any broker-confirmed paper fills.
5. At the deadline (or Ctrl-C) it stops checking, runs the same checked reconcile, and reports FLAT or EXPOSED.
   If the reconcile cannot be confirmed it reports UNRESOLVED (exit 8): never flat, and it presses nothing.
   With --at-end close (the default) and confirmed exposure the desk itself owns, it presses the desk's Stop & Close,
   which also disables the adapter until you enable it again. With --at-end leave it only reports.
6. Closes the desk only if this runner opened it, and writes a private run record in the state folder. An
   unexpected error or lost connection anywhere still closes a desk this runner opened and records UNRESOLVED.

Two modes:
- Monitor-only (the default, no --auto): it never presses Enable, Arm, Clear Stop, Play or Schedule, and it
  cannot reach any other desk route. Whether an order is placed is still decided by the desk: it routes nothing
  unless you enabled and armed it yourself.
- Automated paper (--auto): the same steps 1-6, plus, after this one deliberate start, the runner presses the
  paper desk's Enable and Arm itself, at most once each per run and only when all of these hold on the same
  check: the strategy warm-up is complete; the desk's preflight shows the regular session open (calendar and
  venue clock rows ok, every other row ok except "adapter enabled"); the desk is not already armed; a fresh
  paper-identity check and a fresh checked reconcile (matching position, no outside order, clean) pass right
  before the press. Arm asks for an expiry equal to the run end, and the runner reads back the expiry the desk
  actually set: if it is later than the run end (or unreadable) the runner presses Stop & Close at once and
  ends the run, so its arm never outlasts the run. Checks default to every 30 seconds. It stops checking and
  goes to the clean end (step 5), never enabling or arming again, on: a desk Stop (operator Stop & Close, or
  any other Stop), a risk latch (DAILY_LOSS_STOP), an unresolved or unknown order (UNRESOLVED_SUBMIT, an
  ambiguous recovery, a blocking alarm such as UNKNOWN_STATUS or ORDER_MISSING), a foreign order or position
  (FOREIGN_ORDER, FOREIGN_POSITION, a position the desk does not match), a lost connection (a failed check,
  BROKER_DISCONNECTED, BROKER_UNREACHABLE), the adapter being disabled after it enabled it, or a desk that no
  longer identifies as this paper desk. If its arm lapses or is removed any other way, the rest of the run is
  monitor-only and every check line and the run record say so. Auto mode may also reach only Enable and Arm
  beyond the monitor routes: never Clear Stop, Play, Schedule or Disable, and never a live desk.
"""
import argparse
import fcntl
import http.client
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
DESK = HERE.parent
PAPER_MODE = "alpaca-paper"
ADAPTER_FILE = "alpaca_paper.json"
STATE_NAME = "state-alpaca-paper"
LAUNCHER = DESK / "after-approval" / "Open Connected Paper Desk.command"
PORT = 18858
MAX_MINUTES = 400
EVERY_DEFAULT, EVERY_MIN, EVERY_MAX = 60, 30, 300
START_WAIT_S = 45
STOP_WAIT_S = 15
CLOSE_WAIT_S = 90
FRESH_S = 5          # a reconcile report must be stamped within this many seconds of the call

# The only desk routes this runner may call. Enable, Arm, Clear Stop, Play and Schedule are not here.
ALLOWED = frozenset({
    ("GET", "/api/health"), ("GET", "/api/session"), ("GET", "/api/decisions"), ("GET", "/api/ledger"),
    ("POST", "/api/advance"), ("POST", "/api/alpaca/reconcile"), ("POST", "/api/stop_close"),
})
# --auto only: the same routes plus the paper desk's Enable and Arm, and its non-executing connection check
# (GET-only at Alpaca; it fills the fractional preflight rows). Clear Stop, Play, Schedule stay unreachable.
ENABLE_ROUTE, ARM_ROUTE = "/api/alpaca/enable", "/api/arm"
CONNECTION_CHECK_ROUTE = "/api/alpaca/connection_check"
AUTO_ALLOWED = ALLOWED | frozenset({("POST", ENABLE_ROUTE), ("POST", ARM_ROUTE), ("POST", CONNECTION_CHECK_ROUTE)})
AUTO_EVERY_DEFAULT = 30
# /api/health must report this true before --auto presses anything: it means /api/arm takes a body expires_utc
# and can only shorten the arm with it. A desk without it would arm to the session close + grace, past the run end.
ARM_BOUND_FLAG = "arm_bounded_expiry"
NO_ARM_BOUND = ("this desk cannot bound Arm to the run end (/api/health has no %s); it pressed neither Enable "
                "nor Arm" % ARM_BOUND_FLAG)
FRACTIONAL_ROWS = frozenset({"SPY fractionable", "non-margin cash"})   # filled by one connection check
PREFLIGHT_WAIT = "desk preflight not ready"
FOREIGN_ALARMS = frozenset({"FOREIGN_ORDER", "FOREIGN_POSITION", "POSITION_MISMATCH", "POSITION_EXCESS",
                            "POSITION_UNSUPPORTED_FRACTIONAL"})
CONNECTION_ALARMS = frozenset({"BROKER_UNREACHABLE", "BROKER_DISCONNECTED"})

ENTRY_OR_EXIT = ("enter_long", "enter_short", "exit")
PLUMBING = frozenset({
    "WARMUP_ONLY_LATE_BAR", "WARMUP_ONLY", "STRATEGY_ERROR", "VENUE_CLOSED", "OUT_OF_SESSION",
    "SESSION_NOT_REGULAR", "ZERO_VOLUME", "BAD_BAR", "OUT_OF_ORDER", "SPARSE_HOUR", "NOT_CLOSED_AT_RECEIPT",
    "SESSION_EXPIRED", "SESSION_END",
})

EXIT_OK, EXIT_SETUP, EXIT_WRITER, EXIT_NOT_PAPER, EXIT_POSITION, EXIT_NO_DESK, EXIT_EXPOSED = 0, 2, 3, 4, 5, 6, 7
EXIT_UNRESOLVED = 8   # the broker position could not be confirmed; never reported as flat
# Blocking reconcile alarms that state a definite exposure (a position or order at Alpaca the desk does not
# account for). They end as EXPOSED and the runner never closes them. Any other blocking alarm (a bad record,
# an incomplete listing, an unresolved submit, a missing order, an unknown status, an overfill...) means the
# broker answer cannot be trusted, so it is UNRESOLVED.
EXPOSURE_ALARMS = frozenset({"POSITION_MISMATCH", "POSITION_EXCESS", "FOREIGN_ORDER", "FOREIGN_POSITION",
                             "POSITION_UNSUPPORTED_FRACTIONAL"})


class Refused(Exception):
    def __init__(self, code, text):
        super().__init__(text)
        self.code, self.text = code, text


def utcnow():
    return datetime.now(timezone.utc)


def stamp(dt):
    return dt.strftime("%H:%M:%SZ")


def parse_ts(text):
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


class DeskClient:
    """Loopback HTTP to one desk port, limited to ALLOWED (AUTO_ALLOWED only when built with auto=True)."""

    def __init__(self, port, timeout=30, auto=False):
        self.port, self.timeout = port, timeout
        self.allowed = AUTO_ALLOWED if auto is True else ALLOWED

    def call(self, method, path, body=None):
        if (method, path.split("?")[0]) not in self.allowed:
            raise Refused(EXIT_SETUP, "runner may not call %s %s" % (method, path))
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=self.timeout)
        try:
            data = None if body is None else json.dumps(body).encode()
            headers = {"Content-Type": "application/json"} if data is not None else {}
            conn.request(method, path, body=data, headers=headers)
            reply = conn.getresponse()
            raw = reply.read()
            try:
                return reply.status, json.loads(raw or b"{}")
            except ValueError:
                return reply.status, {}
        finally:
            conn.close()


def other_writers(ps_lines, state_dir, own_pids=()):
    """Processes that could write to the same paper account: any live desk, or a paper desk on a different
    state folder. A paper desk on this state folder is the one we attach to and is not listed."""
    state = str(Path(state_dir).resolve())
    found = []
    for line in ps_lines:
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit() or int(parts[0]) in own_pids:
            continue
        cmd = parts[1]
        if "live_launch.py" in cmd or "--broker alpaca-live" in cmd:
            found.append(line.strip())
        elif "launch.py" in cmd and "--broker alpaca-paper" in cmd:
            if "--state-dir " + state not in cmd and "--state-dir " + str(state_dir) not in cmd:
                found.append(line.strip())
    return found


def read_ps():
    try:
        out = subprocess.run(["/bin/ps", "-axo", "pid=,command="], capture_output=True, text=True, timeout=10)
        return out.stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return None


def paper_problems(health, session, state_dir):
    """Every reason this is not the real paper desk on state_dir; empty when it is."""
    bad = []
    h, s = health or {}, session or {}
    if h.get("broker_mode") != PAPER_MODE:
        bad.append("broker mode is %r, not %s" % (h.get("broker_mode"), PAPER_MODE))
    if h.get("simulated") is not False:
        bad.append("desk reports a mock broker (simulated=%r)" % h.get("simulated"))
    if h.get("controller_attached") is not True:
        bad.append("desk controller is not attached")
    try:
        same = Path(h.get("state_dir")).resolve() == Path(state_dir).resolve()
    except TypeError:
        same = False
    if not same:
        bad.append("desk state folder is not this paper state folder")
    if s.get("_broker_mode") != PAPER_MODE:
        bad.append("session broker mode is %r" % s.get("_broker_mode"))
    if s.get("_adapter_file_name") != ADAPTER_FILE:
        bad.append("adapter file is %r, not %s" % (s.get("_adapter_file_name"), ADAPTER_FILE))
    if s.get("live"):
        bad.append("session says live")
    if "PAPER" not in str(s.get("evidence_label") or ""):
        bad.append("evidence label does not say PAPER")
    return bad


def position_view(session):
    ex = (session or {}).get("exposure") or {}
    desk, broker = ex.get("position_qty"), ex.get("broker_position_qty")
    working = ex.get("working_orders") or []
    return desk, broker, working


def position_problem(session):
    desk, broker, _ = position_view(session)
    if broker is None:
        return "broker position is unknown"
    try:
        if float(desk) != float(broker):
            return "broker position %s does not match the desk's own position %s" % (broker, desk)
    except (TypeError, ValueError):
        return "position is unreadable"
    return None


def finite_qty(value):
    """True for a real, finite JSON number. None, a string, a bool, NaN and infinity are not a quantity."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def view_exposed(view):
    return (view["desk"] != 0 or view["broker"] != 0 or bool(view["broker_working"])
            or bool(view["desk_working"]) or bool(view["external"]) or not view["clean"])


def classify(decision):
    """('STRATEGY' | 'PLUMBING', text) for one decision row."""
    if not decision:
        return "PLUMBING", "no decision yet"
    action, code = decision.get("action"), str(decision.get("reason_code") or "")
    routing = decision.get("routing") or {}
    text = "%s %s" % (action, code or "")
    if action in ENTRY_OR_EXIT:
        status = routing.get("status")
        if status in ("not_routed", "rejected", "no_order") or not status:
            text += " (not routed: %s)" % (routing.get("why") or status or "no routing")
        else:
            text += " (routed: %s)" % status
        return "STRATEGY", text.strip()
    if code in PLUMBING or code.startswith("DATA_REJECTED") or routing.get("why") in ("WARMUP_ONLY",):
        return "PLUMBING", text.strip()
    return "STRATEGY", text.strip()


def iso_z(ts):
    return datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ny_date(dt):
    """The desk's trading day key (America/New_York date) for dt, or None when it cannot be computed."""
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return None


def pressed_ok(status, reply):
    """A press counts only when the desk ran it and its controller did not refuse it."""
    inner = reply.get("controller_result")
    return (status == 200 and reply.get("ok") is True and reply.get("controller_called") is True
            and (not isinstance(inner, dict) or inner.get("ok") is not False))


def broker_fills(ledger_items):
    """Fills the broker confirmed. A mock fill is not a broker fill and is never counted here."""
    out = []
    for row in ledger_items or []:
        for f in row.get("fills") or []:
            if f.get("mock") is False and f.get("exec_id"):
                out.append({"exec_id": f["exec_id"], "side": row.get("side"), "kind": row.get("kind"),
                            "qty": f.get("qty"), "price": f.get("price"), "fee": f.get("fee"), "ts": f.get("ts")})
    return out


class Runner:
    def __init__(self, minutes, every, at_end="close", port=PORT, state_dir=None, no_browser=False,
                 client=None, find_desk=None, launch=None, ps=read_ps, now=utcnow, sleep=time.sleep,
                 out=print, launcher=LAUNCHER, auto=False):
        self.auto = auto is True
        self.minutes = int(minutes)
        self.every = int(every)
        self.at_end = at_end
        self.port = port
        self.state_dir = Path(state_dir or DESK / STATE_NAME)
        self.no_browser = no_browser
        self.client = client
        self.find_desk = find_desk or self._find_desk
        self.launch = launch or self._launch
        self.ps, self.now, self.sleep, self.out = ps, now, sleep, out
        self.launcher = launcher
        self.proc = None
        self.lock_fh = None
        self.stop_flag = None
        self.record = {"runner": "alpaca/paper_runner.py", "mode": PAPER_MODE, "checks": [],
                       "fills_seen": [], "ended_by": None}
        if self.auto:
            # one Enable and one Arm per run at most; once stop or monitor_only is set nothing is pressed again
            self.record["auto"] = {"mode": "auto", "enable_pressed_utc": None, "arm_pressed_utc": None,
                                   "arm_requested_expires_utc": None, "armed_expires_utc": None,
                                   "stop_trigger": None, "monitor_only": None, "connection_check": None}
            self.auto_state = {"enabled": False, "armed": False, "pressed": False, "stop": None,
                               "monitor_only": None, "connection_checked": False}

    # ---------------------------------------------------------------- setup
    def validate(self):
        if not 1 <= self.minutes <= MAX_MINUTES:
            raise Refused(EXIT_SETUP, "--minutes must be 1..%d" % MAX_MINUTES)
        self.every = max(EVERY_MIN, min(EVERY_MAX, self.every))
        if self.at_end not in ("close", "leave"):
            raise Refused(EXIT_SETUP, "--at-end must be close or leave")
        if self.state_dir.name != STATE_NAME:
            raise Refused(EXIT_NOT_PAPER, "state folder must be %s" % STATE_NAME)
        if not (self.state_dir / "limits_approved.json").is_file():
            raise Refused(EXIT_SETUP, "Open the paper desk, choose Setup (limits) and approve your own values first.")

    def take_lock(self):
        path = self.state_dir / "paper_runner.lock"
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
        fh = os.fdopen(fd, "r+")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            raise Refused(EXIT_WRITER, "another paper runner is already driving this desk")
        fh.seek(0)
        fh.truncate()
        fh.write("%d %s\n" % (os.getpid(), self.now().isoformat()))
        fh.flush()
        self.lock_fh = fh

    def check_writers(self):
        lines = self.ps()
        if lines is None:
            raise Refused(EXIT_WRITER, "could not list processes, so a second writer cannot be ruled out")
        found = other_writers(lines, self.state_dir, own_pids=(os.getpid(),))
        if found:
            raise Refused(EXIT_WRITER, "another desk could write to this account: " + found[0][:160])

    def _find_desk(self):
        sys.path.insert(0, str(HERE))
        import open_existing  # noqa: E402  (same folder; keeps the reopen rule in one place)
        return open_existing.find_same_desk(self.port, self.state_dir, PAPER_MODE)

    def _launch(self):
        log = os.open(str(self.state_dir / "paper_runner_desk.log"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        args = ["/bin/zsh", str(self.launcher)] + (["--no-browser"] if self.no_browser else [])
        try:
            return subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
                                    cwd=str(DESK))
        finally:
            os.close(log)

    def attach_or_open(self):
        port = self.find_desk()
        if port is not None:
            self.record["desk"] = "attached to the paper desk that was already open"
            self.out("Using the paper desk that is already open on port %d; it stays open afterwards." % port)
            return port
        if not Path(self.launcher).is_file():
            raise Refused(EXIT_NO_DESK, "paper launcher not found")
        self.proc = self.launch()
        self.record["desk"] = "opened by this runner"
        deadline = self.now().timestamp() + START_WAIT_S
        while self.now().timestamp() < deadline:
            port = self.find_desk()
            if port is not None:
                self.out("Opened the paper desk on port %d; this runner will close it at the end." % port)
                return port
            if self.proc.poll() is not None:
                break
            self.sleep(1)
        raise Refused(EXIT_NO_DESK, "the paper desk did not start; see %s" % (self.state_dir / "paper_runner_desk.log"))

    # ---------------------------------------------------------------- views
    def get(self, path):
        status, body = self.client.call("GET", path)
        return body if status == 200 and isinstance(body, dict) else None

    def post(self, path, body=None):
        if ("POST", path.split("?")[0]) not in (AUTO_ALLOWED if self.auto else ALLOWED):
            raise Refused(EXIT_SETUP, "runner may not call POST %s" % path)
        status, reply = self.client.call("POST", path, body or {})
        return status, reply if isinstance(reply, dict) else {}

    def snapshot(self):
        session = self.get("/api/session") or {}
        decisions = (self.get("/api/decisions") or {}).get("items") or []
        ledger = (self.get("/api/ledger") or {}).get("items") or []
        return session, decisions, ledger

    def line(self, now, session, decisions, ledger, check):
        adapter = session.get("adapter") or {}
        if adapter.get("enabled"):
            ad = "adapter ON"
        else:
            ad = "adapter OFF (%s)" % str(adapter.get("disabled_reason") or "not enabled")[:60]
        arm = "ARMED" if session.get("armed") else "DISARMED (%s)" % (session.get("entry_block_reason") or "-")
        last = decisions[-1] if decisions else None
        kind, text = classify(last)
        bar = "no bar"
        if last and last.get("bar_ts_close"):
            closed = parse_ts(last["bar_ts_close"])
            age = int((now - closed).total_seconds()) if closed else None
            bar = "bar %s (age %ss)" % (last["bar_ts_close"], age)
        src = (check or {}).get("source") or session.get("data_label") or "-"
        desk, broker, working = position_view(session)
        fills = broker_fills(ledger)
        pnl = (session.get("pnl") or {}).get("day_after_cost")
        blocking = [a.get("code") for a in session.get("alarms") or [] if a.get("blocking")]
        parts = [stamp(now), "PAPER", ad, arm, bar, "src " + str(src).split(" (")[0], kind + ": " + text,
                 "pos %s (broker %s, working %d)" % (desk, broker, len(working)),
                 "paper fills %d" % len(fills), "day after cost %s" % pnl]
        if blocking:
            parts.append("BLOCKING " + ",".join(str(b) for b in blocking))
        return " | ".join(parts)

    # ---------------------------------------------------------------- run
    def run(self):
        started = self.now()
        self.record["utc_start"] = started.isoformat()
        try:
            self.validate()
            self.take_lock()
            self.check_writers()
            port = self.attach_or_open()
            if self.client is None:
                self.client = DeskClient(port, auto=self.auto)
            health = self.get("/api/health") or {}
            session = self.get("/api/session") or {}
            bad = paper_problems(health, session, self.state_dir)
            if bad:
                raise Refused(EXIT_NOT_PAPER, "not the paper desk: " + "; ".join(bad))
            view, why = self.verified_reconcile()
            if view is None:
                raise Refused(EXIT_POSITION, "could not confirm the broker position, not running: " + why)
            session = view["session"]
            ledger = (self.get("/api/ledger") or {}).get("items") or []
            self.out("ALPACA PAPER ACCOUNT (simulated, no real money). " + str(session.get("badge") or ""))
            self.out("Broker check %s: position %s (desk %s), %d working order(s) at Alpaca."
                     % (view["ts"], view["broker"], view["desk"], len(view["broker_working"])))
            if self.auto:
                self.out("AUTOMATED PAPER run: after warm-up, with the regular session open, this runner presses "
                         "Enable and Arm once (arm expiry no later than %s), checks every %ds, and never re-arms. "
                         "Ends %s or on Ctrl-C."
                         % (iso_z(started.timestamp() + 60 * self.minutes), self.every,
                            stamp(datetime.fromtimestamp(started.timestamp() + 60 * self.minutes, timezone.utc))))
                if health.get(ARM_BOUND_FLAG) is not True:
                    self.out(self.monitor_only(NO_ARM_BOUND))
            else:
                self.out("Regular-hours desk; the runner only presses Check on a timer. Ends %s or on Ctrl-C."
                         % stamp(datetime.fromtimestamp(started.timestamp() + 60 * self.minutes, timezone.utc)))
            if view["desk"] != view["broker"]:
                raise Refused(EXIT_POSITION, "unexplained position, not running: broker position %s does not "
                                             "match the desk's own position %s" % (view["broker"], view["desk"]))
            if view["external"]:
                raise Refused(EXIT_POSITION, "unexplained position, not running: %d working order(s) at Alpaca "
                                             "that this desk did not place" % len(view["external"]))
            if not view["clean"]:
                raise Refused(EXIT_POSITION, "the broker reconcile is not clean, not running: blocking alarm(s) %s"
                                             % ", ".join(view["blocking"]))
            self.record["start_broker_check"] = self.check_summary(view)
            baseline_fills = {f["exec_id"] for f in broker_fills(ledger)}
            self.record["start"] = self.summary(session)
            self.loop(started, baseline_fills)
            return self.finish(baseline_fills)
        except Refused as exc:
            self.out("REFUSED: " + exc.text)
            self.record["refused"] = exc.text
            self.record["ended_by"] = "refused"
            self.stop_desk()
            self.write_record()
            return exc.code
        except Exception as exc:     # lost connection or anything unexpected: close our desk, record, never flat
            self.out("UNRESOLVED: the runner stopped on %s (%s). The broker position was not confirmed; "
                     "check the desk and the Alpaca paper dashboard." % (exc.__class__.__name__, str(exc)[:120]))
            self.record["ended_by"] = "error: %s" % exc.__class__.__name__
            self.record["end_status"] = "unresolved"
            self.record["unresolved"] = "%s: %s" % (exc.__class__.__name__, str(exc)[:200])
            try:
                self.stop_desk()
            finally:
                self.write_record()
            return EXIT_UNRESOLVED
        finally:
            if self.lock_fh is not None:
                self.lock_fh.close()

    def loop(self, started, baseline_fills):
        end = started.timestamp() + 60 * self.minutes
        failures = 0
        while True:
            if self.stop_flag:
                self.record["ended_by"] = self.stop_flag
                return
            now = self.now()
            if now.timestamp() >= end:
                self.record["ended_by"] = "deadline"
                return
            try:
                status, reply = self.post("/api/advance")
                check = reply.get("controller_result") if isinstance(reply.get("controller_result"), dict) else {}
                session, decisions, ledger = self.snapshot()
                failures = 0 if status == 200 else failures + 1
            except (OSError, http.client.HTTPException) as exc:
                failures += 1
                self.out("%s | PAPER | check failed: %s" % (stamp(now), exc.__class__.__name__))
                if self.auto:
                    self.auto_stop("lost connection (check failed: %s)" % exc.__class__.__name__)
                    return
                if failures >= 3:
                    self.record["ended_by"] = "desk unreachable"
                    return
                self.wait_until(min(end, now.timestamp() + self.every))
                continue
            auto_text = self.auto_step(end, session, status) if self.auto else None
            text = self.line(now, session, decisions, ledger, check)
            self.out(text if auto_text is None else text + " | " + auto_text)
            for f in broker_fills(ledger):
                if f["exec_id"] not in baseline_fills and f not in self.record["fills_seen"]:
                    self.record["fills_seen"].append(f)
                    self.out("  ALPACA PAPER FILL (broker-confirmed): %s %s @ %s at %s"
                             % (f.get("side"), f.get("qty"), f.get("price"), f.get("ts")))
            last = decisions[-1] if decisions else None
            row = {"utc": now.isoformat(), "http": status, "decision": classify(last), "bars": check.get("bars"),
                   "position": position_view(session)[:2]}
            if self.auto:
                row["auto"] = auto_text
            self.record["checks"].append(row)
            if self.auto and self.auto_state["stop"]:
                self.record["ended_by"] = "stop trigger: " + self.auto_state["stop"]
                return
            if failures >= 3:
                self.record["ended_by"] = "desk refused checks"
                return
            self.wait_until(min(end, now.timestamp() + self.every))

    # ---------------------------------------------------------------- --auto
    def auto_stop(self, why):
        """Latch a stop trigger: no Enable or Arm after this, the loop ends, the clean end runs."""
        if not self.auto_state["stop"]:
            self.auto_state["stop"] = why
            self.record["auto"]["stop_trigger"] = why
        self.record["ended_by"] = "stop trigger: " + self.auto_state["stop"]
        return "AUTO: STOP (%s); this runner never enables or arms again" % why

    def monitor_only(self, why):
        if not self.auto_state["monitor_only"]:
            self.auto_state["monitor_only"] = why
            self.record["auto"]["monitor_only"] = why
        return "AUTO: MONITOR-ONLY for the rest of this run (%s); this runner never re-arms" % why

    def stop_trigger(self, session, status):
        """The first reason, read from desk state, that the automated run must stop; None when there is none."""
        if status != 200:
            return "lost connection (the desk answered the check with HTTP %s)" % status
        s = session if isinstance(session, dict) else {}
        if not s:
            return "lost connection (no session from the desk)"
        ctl = s.get("controls") if isinstance(s.get("controls"), dict) else {}
        block = str(s.get("entry_block_reason") or "")
        if ctl.get("stopped") or block == "STOPPED":
            reason = str(ctl.get("stop_reason") or "Stop active")
            if "LOSS" in reason or "RISK" in reason:
                return "risk latch (Stop %s)" % reason
            return "operator Stop (%s)" % reason
        ds = ctl.get("day_stop")
        today = ny_date(self.now())
        if block == "DAILY_LOSS_STOP" or (isinstance(ds, dict) and ds and (today is None or ds.get("day") in (None, today))):
            return "risk latch (DAILY_LOSS_STOP)"
        if block == "BROKER_DISCONNECTED":
            return "lost connection (BROKER_DISCONNECTED)"
        if block == "UNRESOLVED_SUBMIT":
            return "unresolved order (UNRESOLVED_SUBMIT)"
        rec = s.get("recovery") if isinstance(s.get("recovery"), dict) else {}
        if rec.get("ambiguous"):
            return "unresolved order (recovery ambiguous: %s)" % str(rec.get("reason") or "-")[:80]
        codes = [str(a.get("code")) for a in s.get("alarms") or [] if isinstance(a, dict) and a.get("blocking")]
        for code in codes:
            if code in FOREIGN_ALARMS:
                return "foreign order or position (%s)" % code
        for code in codes:
            if code in CONNECTION_ALARMS:
                return "lost connection (%s)" % code
        if codes:
            return "unresolved or unknown order (blocking alarm %s)" % ", ".join(codes)
        desk, broker, _ = position_view(s)
        if finite_qty(desk) and finite_qty(broker) and desk != broker:
            return "foreign or unmatched position (broker %s, desk %s)" % (broker, desk)
        if self.auto_state["enabled"] and not (s.get("adapter") or {}).get("enabled"):
            return "adapter disabled after this runner enabled it (%s)" % str(
                (s.get("adapter") or {}).get("disabled_reason") or "-")[:80]
        return None

    def not_ready(self, session, end):
        """Why Enable/Arm must still wait; None when warm-up is complete and the regular session is open."""
        wu = session.get("warmup")
        if not isinstance(wu, dict) or wu.get("ready") is not True:
            wu = wu if isinstance(wu, dict) else {}
            return "strategy warm-up %s/%s" % (wu.get("bars", "?"), wu.get("needed", "?"))
        rows = [r for r in session.get("preflight") or [] if isinstance(r, dict)]
        named = dict((r.get("check"), r) for r in rows)
        for need in ("calendar", "venue clock"):
            if (named.get(need) or {}).get("ok") is not True:
                return "regular session not open (%s)" % need
        bad = self.failing_rows(session)
        if bad:
            return "%s (%s)" % (PREFLIGHT_WAIT, ", ".join(bad))
        if end - self.now().timestamp() < self.every:
            return "too close to the run end to arm"
        return None

    @staticmethod
    def failing_rows(session):
        rows = [r for r in session.get("preflight") or [] if isinstance(r, dict)]
        return [str(r.get("check")) for r in rows if r.get("ok") is not True and r.get("check") != "adapter enabled"]

    def connection_check_once(self):
        """Press the desk's non-executing connection check once per run, only when the fractional rows it fills
        are the only preflight rows still failing. Returns (session after it, line text)."""
        self.auto_state["connection_checked"] = True
        health = self.get("/api/health") or {}
        session = self.get("/api/session") or {}
        bad = paper_problems(health, session, self.state_dir)
        if bad:
            return session, self.auto_stop("not the paper desk before the connection check: " + "; ".join(bad))
        status, reply = self.post(CONNECTION_CHECK_ROUTE, {})
        ok = pressed_ok(status, reply)
        self.record["auto"]["connection_check"] = {"utc": self.now().isoformat(), "http": status, "ok": ok}
        session = self.get("/api/session") or {}
        still = [r for r in self.failing_rows(session) if r in FRACTIONAL_ROWS]
        if still:
            return session, self.monitor_only("one connection check (GET-only at Alpaca, HTTP %s) left %s failing"
                                              % (status, ", ".join(still)))
        return session, "AUTO: pressed the connection check once (GET-only at Alpaca); fractional rows pass"

    def auto_step(self, end, session, status):
        """One check's worth of auto mode: stop triggers first, then (once) Enable and Arm. Returns its line text."""
        a = self.auto_state
        if a["stop"]:
            return self.auto_stop(a["stop"])
        why = self.stop_trigger(session, status)
        if why:
            return self.auto_stop(why)
        if a["monitor_only"]:
            return self.monitor_only(a["monitor_only"])
        if a["armed"]:
            if not session.get("armed"):
                return self.monitor_only("arm lapsed or was removed (%s)" % (session.get("entry_block_reason") or "disarmed"))
            return "AUTO: armed by this runner until %s" % self.record["auto"]["armed_expires_utc"]
        if session.get("armed"):
            return self.monitor_only("the desk was armed outside this runner; it pressed neither Enable nor Arm")
        if a["pressed"]:
            return self.monitor_only("Enable/Arm was already attempted once in this run")
        wait = self.not_ready(session, end)
        if (wait and wait.startswith(PREFLIGHT_WAIT) and not a["connection_checked"]
                and set(self.failing_rows(session)) <= FRACTIONAL_ROWS):
            try:
                session, text = self.connection_check_once()
            except (OSError, http.client.HTTPException) as exc:
                return self.auto_stop("lost connection (during the connection check: %s)" % exc.__class__.__name__)
            if a["stop"] or a["monitor_only"]:
                return text
            why = self.stop_trigger(session, 200)
            if why:
                return self.auto_stop(why)
            wait = self.not_ready(session, end)
            if wait:
                return text + "; AUTO: waiting (%s)" % wait
        if wait:
            return "AUTO: waiting (%s)" % wait
        try:
            return self.press(end)
        except (OSError, http.client.HTTPException) as exc:
            return self.auto_stop("lost connection (during Enable/Arm: %s)" % exc.__class__.__name__)

    def press(self, end):
        """Enable (if the adapter is off) and Arm, once per run, after fresh paper and reconcile checks."""
        a = self.auto_state
        a["pressed"] = True                      # whatever happens below, this run never presses again
        health = self.get("/api/health") or {}
        session = self.get("/api/session") or {}
        bad = paper_problems(health, session, self.state_dir)
        if bad:
            return self.auto_stop("not the paper desk before Enable: " + "; ".join(bad))
        if health.get(ARM_BOUND_FLAG) is not True:
            return self.monitor_only(NO_ARM_BOUND)
        view, why = self.verified_reconcile()
        if view is None:
            return self.auto_stop("unresolved broker position before Enable (%s)" % why)
        if view["external"] or any(c in FOREIGN_ALARMS for c in view["blocking"]):
            return self.auto_stop("foreign order at Alpaca before Enable (%d outside order(s))" % len(view["external"]))
        if view["desk"] != view["broker"]:
            return self.auto_stop("foreign or unmatched position before Enable (broker %s, desk %s)"
                                  % (view["broker"], view["desk"]))
        if not view["clean"]:
            return self.auto_stop("unresolved or unknown order before Enable (%s)" % ", ".join(view["blocking"]))
        session = view["session"]
        why = self.stop_trigger(session, 200)
        if why:
            return self.auto_stop(why)
        if not (session.get("adapter") or {}).get("enabled"):
            self.record["auto"]["enable_pressed_utc"] = self.now().isoformat()
            status, reply = self.post(ENABLE_ROUTE, {"confirm": True})
            if not pressed_ok(status, reply):
                return self.monitor_only("Enable was refused (HTTP %s: %s)"
                                         % (status, str(reply.get("error") or "-")[:80]))
            a["enabled"] = True
        expires = iso_z(end)
        self.record["auto"]["arm_requested_expires_utc"] = expires
        self.record["auto"]["arm_pressed_utc"] = self.now().isoformat()
        status, reply = self.post(ARM_ROUTE, {"expires_utc": expires})
        if not pressed_ok(status, reply):
            return self.monitor_only("Arm was refused (HTTP %s: %s)" % (status, str(reply.get("error") or "-")[:80]))
        session = self.get("/api/session") or {}
        got = session.get("expires_utc")
        exp = parse_ts(got)
        if session.get("armed") is not True or exp is None or exp.tzinfo is None or exp.timestamp() > end:
            text = self.auto_stop("the desk set arm expiry %r, later than the run end %s or unreadable" % (got, expires))
            try:
                status, reply = self.post("/api/stop_close", {"confirm": True})
            except (OSError, http.client.HTTPException) as exc:
                status, reply = "error %s" % exc.__class__.__name__, {}
            done = status == 200 and reply.get("ok") is True
            self.record["auto"]["unbounded_arm_action"] = ("Stop & Close pressed at once (HTTP 200)" if done else
                                                           "Stop & Close did not succeed (HTTP %s)" % status)
            return text + "; " + self.record["auto"]["unbounded_arm_action"]
        a["armed"] = True
        self.record["auto"]["armed_expires_utc"] = got
        return "AUTO: pressed Enable and Arm; armed by this runner until %s" % got

    def wait_until(self, ts):
        while not self.stop_flag and self.now().timestamp() < ts:
            self.sleep(min(1.0, max(0.0, ts - self.now().timestamp())))

    def verified_reconcile(self):
        """(view, None) after a positive, fresh broker reconcile that the desk's session reflects; (None, why)
        otherwise. A failed call, a missing field or an old answer is never read as zero."""
        asked = self.now()
        try:
            status, reply = self.post("/api/alpaca/reconcile")
        except (OSError, http.client.HTTPException) as exc:
            return None, "reconcile call failed (%s)" % exc.__class__.__name__
        if status != 200 or reply.get("ok") is not True or reply.get("controller_called") is not True:
            return None, "the desk did not run the reconcile (HTTP %s)" % status
        outer = reply.get("controller_result")
        if not isinstance(outer, dict) or outer.get("ok") is not True:
            return None, "the desk reported the reconcile as not ok"
        res = outer.get("result")
        if not isinstance(res, dict):
            return None, "the reconcile returned no broker report"
        if res.get("connected") is not True:
            return None, "Alpaca was not reachable"
        if res.get("complete") is not True:
            return None, "Alpaca's order list was incomplete"
        ts = parse_ts(res.get("ts"))
        if ts is None or ts.tzinfo is None or not (
                asked.timestamp() - FRESH_S <= ts.timestamp() <= self.now().timestamp() + FRESH_S):
            return None, "the broker report is not from this reconcile (ts %r)" % res.get("ts")
        positions = res.get("positions")
        broker = positions.get("broker") if isinstance(positions, dict) else None
        if not finite_qty(broker):
            return None, "the broker position is not a number (%r)" % (broker,)
        working, external = res.get("working_orders"), res.get("external_orders")
        if not isinstance(working, list) or not isinstance(external, list):
            return None, "the broker working-order list is missing"
        alarms = res.get("alarms")
        if not isinstance(alarms, list) or not all(isinstance(a, dict) for a in alarms):
            return None, "the broker report has no readable alarm list"
        # an alarm counts as blocking unless it says it is not
        blocking = sorted({str(a.get("code")) for a in alarms if a.get("blocking") is not False})
        if res.get("ok") is True:
            if blocking:
                return None, "the broker report says ok but carries blocking alarm(s) %s" % ", ".join(blocking)
        else:
            if not blocking:
                return None, "the broker report is not ok (%r) and names no blocking alarm" % (res.get("ok"),)
            unexplained = [c for c in blocking if c not in EXPOSURE_ALARMS]
            if unexplained:
                return None, "the broker report has blocking alarm(s) %s" % ", ".join(unexplained)
        try:
            status, session = self.client.call("GET", "/api/session")
        except (OSError, http.client.HTTPException) as exc:
            return None, "the session read failed (%s)" % exc.__class__.__name__
        if status != 200 or not isinstance(session, dict):
            return None, "the session read failed (HTTP %s)" % status
        ex = session.get("exposure")
        if not isinstance(ex, dict):
            return None, "the session has no position view"
        desk, desk_working = ex.get("position_qty"), ex.get("working_orders")
        if not finite_qty(desk) or not isinstance(desk_working, list):
            return None, "the desk position or its working-order list is unreadable"
        if ex.get("broker_confirmed_utc") != res.get("ts") or not finite_qty(ex.get("broker_position_qty")) \
                or ex.get("broker_position_qty") != broker:
            return None, "the desk session does not show this reconcile"
        return {"ts": res.get("ts"), "desk": desk, "broker": broker, "broker_working": list(working),
                "external": list(external), "desk_working": list(desk_working), "session": session,
                "clean": res.get("ok") is True and not blocking, "blocking": blocking}, None

    def check_summary(self, view):
        return {"broker_confirmed_utc": view["ts"], "broker_position_qty": view["broker"],
                "position_qty": view["desk"], "broker_working_orders": len(view["broker_working"]),
                "external_working_orders": len(view["external"]), "desk_working_orders": len(view["desk_working"]),
                "clean": view["clean"], "blocking_alarms": list(view["blocking"])}

    def finish(self, baseline_fills):
        self.out("Stopping checks (%s). Read-only reconcile:" % self.record["ended_by"])
        view, why = self.verified_reconcile()
        action = "none"
        if view is not None and view_exposed(view) and self.at_end == "close":
            if view["desk"] != view["broker"] or view["external"] or not view["clean"]:
                action = "not closed: position does not match the desk, resolve it in the desk or at Alpaca"
                if view["blocking"]:
                    action += " (blocking alarm(s) %s)" % ", ".join(view["blocking"])
            else:
                try:
                    status, reply = self.post("/api/stop_close", {"confirm": True})
                except (OSError, http.client.HTTPException) as exc:
                    status, reply = "error %s" % exc.__class__.__name__, {}
                if status == 200 and reply.get("ok") is True:
                    action = "Stop & Close pressed (HTTP 200); adapter is now disabled until you enable it"
                else:
                    action = "Stop & Close did not succeed (HTTP %s); close it in the desk or at Alpaca" % status
                deadline = self.now().timestamp() + CLOSE_WAIT_S
                while True:
                    self.sleep(3)
                    view, why = self.verified_reconcile()
                    if (view is not None and not view_exposed(view)) or self.now().timestamp() >= deadline:
                        break
        elif view is not None and view_exposed(view):
            action = "left open (--at-end leave)"
        elif view is None:
            action = "nothing pressed: broker position not confirmed"
        ledger = None
        try:
            ledger = (self.get("/api/ledger") or {}).get("items")
        except (OSError, http.client.HTTPException):
            pass
        for f in broker_fills(ledger):
            if f["exec_id"] not in baseline_fills and f not in self.record["fills_seen"]:
                self.record["fills_seen"].append(f)
        self.record["at_end"] = action
        if view is None:
            self.record["end_status"] = "unresolved"
            self.record["unresolved"] = why
            self.out("UNRESOLVED at end: %s. Not reported as flat; check the desk and the Alpaca paper dashboard. %s"
                     % (why, action))
            code = EXIT_UNRESOLVED
        else:
            self.record["end"] = self.summary(view["session"])
            self.record["end_broker_check"] = self.check_summary(view)
            if view_exposed(view):
                self.record["end_status"] = "exposed"
                self.out("EXPOSED at end (broker check %s): position %s (broker %s), %d working order(s) at Alpaca, "
                         "%d not placed by this desk%s. %s"
                         % (view["ts"], view["desk"], view["broker"], len(view["broker_working"]),
                            len(view["external"]),
                            ", blocking alarm(s) " + ", ".join(view["blocking"]) if view["blocking"] else "", action))
                code = EXIT_EXPOSED
            else:
                self.record["end_status"] = "flat"
                self.out("FLAT at end (broker check %s): broker position %s, desk position %s, no working orders."
                         % (view["ts"], view["broker"], view["desk"]))
                code = EXIT_OK
        self.out("Broker-confirmed paper fills during this run: %d" % len(self.record["fills_seen"]))
        self.stop_desk()
        self.write_record()
        return code

    def summary(self, session):
        adapter = session.get("adapter") or {}
        desk, broker, working = position_view(session)
        return {"utc": self.now().isoformat(), "badge": session.get("badge"), "adapter_enabled": adapter.get("enabled"),
                "adapter_reason": adapter.get("disabled_reason"), "armed": session.get("armed"),
                "entry_block_reason": session.get("entry_block_reason"), "position_qty": desk,
                "broker_position_qty": broker, "working_orders": len(working),
                "blocking_alarms": [a.get("code") for a in session.get("alarms") or [] if a.get("blocking")]}

    def stop_desk(self):
        if self.proc is None:
            return
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
                self.proc.wait(timeout=STOP_WAIT_S)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                    self.proc.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        still = None
        try:
            still = self.find_desk()
        except Exception:
            pass
        self.record["desk_closed"] = self.proc.poll() is not None and still is None
        self.out("Closed the paper desk this runner opened." if self.record["desk_closed"]
                 else "WARNING: the paper desk this runner opened may still be running.")

    def write_record(self):
        self.record["utc_end"] = self.now().isoformat()
        folder = self.state_dir / "runner"
        try:
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
            path = folder / ("paper-run-%s.json" % self.now().strftime("%Y%m%dT%H%M%SZ"))
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as fh:
                json.dump(self.record, fh, indent=1, default=str)
            self.out("Run record: " + str(path))
        except OSError as exc:
            self.out("Could not write the run record: %s" % exc.__class__.__name__)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=int, default=60, help="how long to run (1..%d)" % MAX_MINUTES)
    ap.add_argument("--every", type=int, default=None,
                    help="seconds between checks (%d..%d; default %d, or %d with --auto)"
                         % (EVERY_MIN, EVERY_MAX, EVERY_DEFAULT, AUTO_EVERY_DEFAULT))
    ap.add_argument("--at-end", choices=("close", "leave"), default="close",
                    help="close: press the desk's Stop & Close if it still holds paper exposure; leave: only report")
    ap.add_argument("--no-browser", action="store_true", help="do not open the desk page in the browser")
    ap.add_argument("--auto", action="store_true",
                    help="automated PAPER run: press the paper desk's Enable and Arm once, after warm-up with the "
                         "regular session open; without it the runner is monitor-only")
    a = ap.parse_args(argv)
    every = a.every if a.every is not None else (AUTO_EVERY_DEFAULT if a.auto else EVERY_DEFAULT)
    runner = Runner(a.minutes, every, at_end=a.at_end, no_browser=a.no_browser, auto=a.auto)

    def on_signal(signum, _frame):
        runner.stop_flag = "operator stop (%s)" % signal.Signals(signum).name

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    return runner.run()


if __name__ == "__main__":
    raise SystemExit(main())
