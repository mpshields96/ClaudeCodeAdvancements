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

It never presses Enable, Arm, Clear Stop, Play or Schedule, and it cannot reach any other desk route.
Whether an order is placed is still decided by the desk: it routes nothing unless you enabled and armed it.
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

ENTRY_OR_EXIT = ("enter_long", "enter_short", "exit")
PLUMBING = frozenset({
    "WARMUP_ONLY_LATE_BAR", "WARMUP_ONLY", "STRATEGY_ERROR", "VENUE_CLOSED", "OUT_OF_SESSION",
    "SESSION_NOT_REGULAR", "ZERO_VOLUME", "BAD_BAR", "OUT_OF_ORDER", "SPARSE_HOUR", "NOT_CLOSED_AT_RECEIPT",
    "SESSION_EXPIRED", "SESSION_END",
})

EXIT_OK, EXIT_SETUP, EXIT_WRITER, EXIT_NOT_PAPER, EXIT_POSITION, EXIT_NO_DESK, EXIT_EXPOSED = 0, 2, 3, 4, 5, 6, 7
EXIT_UNRESOLVED = 8   # the broker position could not be confirmed; never reported as flat


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
    """Loopback HTTP to one desk port, limited to ALLOWED."""

    def __init__(self, port, timeout=30):
        self.port, self.timeout = port, timeout

    def call(self, method, path, body=None):
        if (method, path.split("?")[0]) not in ALLOWED:
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
            or bool(view["desk_working"]))


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
                 out=print, launcher=LAUNCHER):
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
                self.client = DeskClient(port)
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
            self.out("Regular-hours desk; the runner only presses Check on a timer. Ends %s or on Ctrl-C."
                     % stamp(datetime.fromtimestamp(started.timestamp() + 60 * self.minutes, timezone.utc)))
            if view["desk"] != view["broker"]:
                raise Refused(EXIT_POSITION, "unexplained position, not running: broker position %s does not "
                                             "match the desk's own position %s" % (view["broker"], view["desk"]))
            if view["external"]:
                raise Refused(EXIT_POSITION, "unexplained position, not running: %d working order(s) at Alpaca "
                                             "that this desk did not place" % len(view["external"]))
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
                if failures >= 3:
                    self.record["ended_by"] = "desk unreachable"
                    return
                self.wait_until(min(end, now.timestamp() + self.every))
                continue
            self.out(self.line(now, session, decisions, ledger, check))
            for f in broker_fills(ledger):
                if f["exec_id"] not in baseline_fills and f not in self.record["fills_seen"]:
                    self.record["fills_seen"].append(f)
                    self.out("  ALPACA PAPER FILL (broker-confirmed): %s %s @ %s at %s"
                             % (f.get("side"), f.get("qty"), f.get("price"), f.get("ts")))
            last = decisions[-1] if decisions else None
            self.record["checks"].append({"utc": now.isoformat(), "http": status,
                                          "decision": classify(last), "bars": check.get("bars"),
                                          "position": position_view(session)[:2]})
            if failures >= 3:
                self.record["ended_by"] = "desk refused checks"
                return
            self.wait_until(min(end, now.timestamp() + self.every))

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
        res = outer.get("result") if isinstance(outer, dict) else None
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
                "external": list(external), "desk_working": list(desk_working), "session": session}, None

    def check_summary(self, view):
        return {"broker_confirmed_utc": view["ts"], "broker_position_qty": view["broker"],
                "position_qty": view["desk"], "broker_working_orders": len(view["broker_working"]),
                "external_working_orders": len(view["external"]), "desk_working_orders": len(view["desk_working"])}

    def finish(self, baseline_fills):
        self.out("Stopping checks (%s). Read-only reconcile:" % self.record["ended_by"])
        view, why = self.verified_reconcile()
        action = "none"
        if view is not None and view_exposed(view) and self.at_end == "close":
            if view["desk"] != view["broker"] or view["external"]:
                action = "not closed: position does not match the desk, resolve it in the desk or at Alpaca"
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
                self.out("EXPOSED at end (broker check %s): position %s (broker %s), %d working order(s) at Alpaca. %s"
                         % (view["ts"], view["desk"], view["broker"], len(view["broker_working"]), action))
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
    ap.add_argument("--every", type=int, default=EVERY_DEFAULT,
                    help="seconds between checks (%d..%d)" % (EVERY_MIN, EVERY_MAX))
    ap.add_argument("--at-end", choices=("close", "leave"), default="close",
                    help="close: press the desk's Stop & Close if it still holds paper exposure; leave: only report")
    ap.add_argument("--no-browser", action="store_true", help="do not open the desk page in the browser")
    a = ap.parse_args(argv)
    runner = Runner(a.minutes, a.every, at_end=a.at_end, no_browser=a.no_browser)

    def on_signal(signum, _frame):
        runner.stop_flag = "operator stop (%s)" % signal.Signals(signum).name

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    return runner.run()


if __name__ == "__main__":
    raise SystemExit(main())
