#!/usr/bin/env python3
"""The distinct LIVE-money command. Separate from launch.py on purpose: no flag there reaches live.

    /usr/bin/python3 -I alpaca/live_launch.py approve-limits --draft-from MY_LIVE_LIMITS.json
    /usr/bin/python3 -I alpaca/live_launch.py start --limits state-alpaca-live/limits_approved.json

`start` runs every check of the live gate (alpaca/live.py) before anything else: a live state dir
(state-alpaca-live, never a paper one), a non-paper port, an operator-approved limits snapshot stored in
that dir and approved with `approve-limits`, a real terminal, and the typed phrase
"LIVE SPY <shares> SHARES <today's CT date>". It reads no key and opens no socket while checking.

Only after the gate passes does `start` build the live session: the live transport from the
authorization the gate minted, the session controller in mode "live" for the live state folder, and the
desk UI on the checked live port, bound exactly (a taken port is refused, never moved). The live adapter
always starts DISABLED; you enable it yourself in the UI. Starting sends no order.

Once you have enabled and armed it yourself, the desk manages the session with no repeated Check clicks
(alpaca/live_supervisor.py): it runs its own Check every 30 s while armed, enabled and not stopped, and
the arm ends 15 minutes before the regular close (early closes included) with Stop & Close, then it
reconciles to flat or an explicit UNRESOLVED handoff. It never enables, arms or re-arms itself.

If this build's alpaca_session.py has no live mode, `start` stops after the gate with exit 3. Any
failure after the gate names the stage that failed and gives the real error; once the controller's
start-up has begun it says the key may have been read and read-only requests made. See LIVE_READINESS.md.

Exit codes: 0 limits saved, or the live session ran and you stopped it; 2 refused (the message says what
may have been read; no order is ever sent); 3 gate passed, but this build's session controller has no live
mode (nothing sent).
"""
import argparse
import os
import sys
import threading
import time

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from alpaca import live as L  # noqa: E402
from alpaca import live_supervisor  # noqa: E402
from alpaca import sizing  # noqa: E402

DEFAULT_LIVE_STATE = os.path.join(DESK, L.LIVE_STATE_DIRNAME)
NOT_WIRED = ("LIVE GATE PASSED for %s, %s shares. Nothing was sent: the live session controller is not "
             "wired in this build (alpaca_session.py has no matching live mode). No key was "
             "read and no connection was opened.")
LIVE_HOST = "127.0.0.1"
LIVE_STRATEGY = "ema"          # the paper launcher's default (launch.LAUNCH_STRATEGY)
START_DISABLED_REASON = "NEW_LIVE_SESSION (live_launch start; enable it yourself in the UI)"


def _session_module():
    """alpaca_session with a live mode, or None (then `start` stops at exit 3 as before)."""
    try:
        import alpaca_session as AS  # noqa: WPS433
    except ImportError:
        return None
    if getattr(AS, "MODE_LIVE", None) != "live" or not hasattr(AS, "AlpacaSessionController"):
        return None
    return AS


def _make_transport(provider_kind, auth):
    """The live transport. Building it reads no key; the key is read only when a request is sent."""
    return L.LiveHttpsTransport(L.make_live_provider(provider_kind), auth)


def _make_server(state_dir, host, port, manager):
    from ui import server as ui_server  # noqa: WPS433
    return ui_server.make_server(state_dir, host, port, manager=manager)


def _open_browser(url):
    import webbrowser  # noqa: WPS433
    webbrowser.open(url)


def _wait_until_interrupted():
    while True:
        time.sleep(0.5)


def _parser():
    p = argparse.ArgumentParser(prog="live_launch.py", description="LIVE-money Alpaca gate (off by default)")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("start", help="run the per-session live gate")
    s.add_argument("--limits", default=None, help="your approved LIVE limits inside state-alpaca-live/")
    s.add_argument("--state-dir", default=DEFAULT_LIVE_STATE)
    s.add_argument("--port", type=int, default=L.LIVE_PORT)
    s.add_argument("--provider", choices=sorted(L.LIVE_PROVIDERS), default="keychain")
    s.add_argument("--no-browser", action="store_true", help="do not open the desk in the browser")
    a = sub.add_parser("approve-limits", help="approve LIVE limits you wrote yourself")
    a.add_argument("--state-dir", default=DEFAULT_LIVE_STATE)
    a.add_argument("--draft-from", default=None, help="a JSON file with your five values")
    return p


START_READS = "read-only start-up reads only: open orders, positions, market clock"


def _refuse(err, msg):
    err.write("REFUSED (live): %s\nNothing was sent; no key was read; no connection was opened.\n" % msg)
    return 2


def _refuse_after_build(err, msg):
    """A refusal once the live controller's start-up has begun: its reconcile may already have read the key
    and made read-only requests, so the plain "nothing was sent" line would be untrue."""
    err.write("REFUSED (live): %s\nNo order was sent. The session controller's start-up had begun, so it may "
              "have read the live key and made %s.\n" % (msg, START_READS))
    return 2


def _start(args, out, err, isatty, read_line):
    try:
        state_dir = L.check_live_state_dir(args.state_dir)
        L.check_live_port(args.port)
        loaded = L.check_live_limits(args.limits, state_dir)
        if not isatty():
            raise L.LiveGateRefused("the live confirmation must be typed at a terminal (piped input refused)")
        want = L.confirm_phrase(loaded["values"]["fixed_shares"], L.session_date())
        out.write("%s\nLimits: %s\nTo start REAL-MONEY trading for this session only, type exactly:\n  %s\n> "
                  % (L.LABEL_ALPACA_LIVE, loaded["values"], want))
        out.flush()
        typed = read_line()
        auth = L.live_gate_authorize(args.limits, state_dir, args.port, typed, isatty(),
                                     shown_hash=loaded["hash"])
    except L.LiveGateRefused as e:
        return _refuse(err, str(e))
    AS = _session_module()
    if AS is None:
        out.write(NOT_WIRED % (auth.session_date, L.Q.text(L.Q.parse(auth.shares))) + "\n")
        return 3
    return _serve_live(args, auth, state_dir, AS, out, err)


def _serve_live(args, auth, state_dir, AS, out, err):
    """Runs only after the gate passed. Order: locks, exact port check, adapter forced off, transport,
    controller, server. Every refusal before the server starts sends nothing."""
    import launch  # noqa: WPS433  (the paper launcher's locks and controls)
    scenario_lock = launch.hold_scenario_lock(state_dir)
    if scenario_lock is None:
        return _refuse(err, "another launcher holds this live state folder (%s)" % state_dir)
    runner, started, stage = None, False, "state folder lock"
    try:
        held, inner = launch._take_inner_lock(state_dir)
        if inner is not None:
            inner.close()
        if held:
            raise L.LiveGateRefused("this live state folder's order manager lock is held by another process")
        stage = "exact live port check"
        probe = L.bind_live_port_exactly(args.port)      # taken: refused here, never moved
        probe.close()
        stage = "live adapter reset"
        live_state = L.LiveAdapterState(state_dir)
        if live_state.enabled:                           # a new session never inherits "enabled"
            live_state.disable(START_DISABLED_REASON, by="live_launch start")
        stage = "live transport"
        if not auth.state_dir or os.path.realpath(auth.state_dir) != os.path.realpath(state_dir):
            raise L.LiveGateRefused("the live authorization is for a different state folder")
        transport = _make_transport(args.provider, auth)
        if getattr(transport, "MODE", None) != "live":
            raise L.LiveGateRefused("the live session accepts only the live transport")
        stage, started = "session controller start-up", True    # its reconcile may send read-only GETs
        runner = AS.AlpacaSessionController(state_dir=state_dir, strategy=LIVE_STRATEGY, mode=AS.MODE_LIVE,
                                            transport=transport, live_authorization=auth)
        stage = "live adapter check"
        if runner.mgr.state()["armed"]:
            runner.mgr.disarm(reason="NEW_LIVE_SESSION")
            if runner.phase in ("ARMED", "PAUSED"):
                runner.phase = "PRE_SESSION"
            runner._write_state()  # publish the disarmed state before the local UI can be served
        if getattr(runner.adapter_state, "enabled", True) is not False:
            raise L.LiveGateRefused("the live adapter did not start disabled")
        stage = "desk server"
        controls = launch.AlpacaDeskControls(runner)
        launch.install_routes()
        try:
            httpd = _make_server(state_dir, LIVE_HOST, args.port, controls)
        except OSError as e:
            raise L.LiveGateRefused("live port %d could not be bound (%s); live does not move to another port"
                                    % (args.port, e.strerror or e))
    except Exception as e:      # LiveGateRefused, LiveModeRefused, LimitsError, RuntimeError ...
        if runner is not None and hasattr(runner, "close"):
            runner.close()
        scenario_lock.close()
        msg = str(e) if isinstance(e, L.LiveGateRefused) else "%s: %s" % (e.__class__.__name__, e)
        msg = "%s failed: %s" % (stage, msg)
        return (_refuse_after_build if started else _refuse)(err, msg)
    url = "http://%s:%d/" % (LIVE_HOST, args.port)
    threading.Thread(target=httpd.serve_forever, name="desk-ui-live", daemon=True).start()
    supervisor = live_supervisor.LiveSupervisor(runner).start()   # idle until YOU enable and arm
    out.write("[live] %s\n[live] UI        %s\n[live] state     %s\n[live] shares    %s (approved %s)\n"
              "[live] adapter   DISABLED. Enable it yourself in the UI; Stop disables it again.\n"
              "[live] sent      no order (%s)\n"
              "[live] auto      after YOU enable and arm, the desk runs its own Check every %ds until the arm "
              "ends (15 min before the close, early closes included, then Stop & Close) or you press Stop; "
              "it never enables or arms "
              "itself\n[live] Ctrl-C to quit.\n"
              % (getattr(runner, "evidence_label", L.LABEL_ALPACA_LIVE), url, state_dir, L.Q.text(L.Q.parse(auth.shares)),
                 auth.session_date, START_READS, supervisor.every_s))
    out.flush()
    if not getattr(args, "no_browser", False):
        _open_browser(url)
    try:
        _wait_until_interrupted()
    except KeyboardInterrupt:
        pass
    finally:
        supervisor.stop()
        httpd.shutdown()
        httpd.server_close()
        if hasattr(runner, "close"):
            runner.close()
        scenario_lock.close()
        out.write("[live] stopped; state kept in %s\n" % state_dir)
    return 0


def _approve(args, out, err, isatty, read_line):
    try:
        path = os.path.abspath(args.state_dir)
        if os.path.basename(path.rstrip(os.sep)) != L.LIVE_STATE_DIRNAME:
            raise L.LiveGateRefused("live limits are approved only in a folder named %s" % L.LIVE_STATE_DIRNAME)
        os.makedirs(path, exist_ok=True)
        L.check_live_state_dir(path)
        if not isatty():
            raise L.LiveGateRefused("live limits must be approved at a terminal (piped input refused)")
        if args.draft_from:
            obj, why = sizing._read_json(args.draft_from)
            if not isinstance(obj, dict):
                raise L.LiveGateRefused("draft file: %s" % (why or "not a JSON object"))
            sizing.save_draft(path, obj.get("values", obj), copied_from=os.path.basename(args.draft_from))
        draft = sizing.read_draft(path)
        if not draft:
            raise L.LiveGateRefused("no live draft yet; pass --draft-from with your five values")
        out.write("LIVE limits draft: %s\nType exactly: %s\n> " % (draft.get("values"), L.LIVE_CONFIRM_LIMITS))
        out.flush()
        if (read_line() or "").strip() != L.LIVE_CONFIRM_LIMITS:
            raise L.LiveGateRefused("approval phrase did not match")
        out.write("Reason (one line): ")
        out.flush()
        reason = read_line()
        old = sizing.read_approved(path) or {}
        snap = sizing.approve(path, sizing.CONFIRM_PHRASE, reason,
                              reviewed_draft_hash=sizing.content_hash(draft.get("values")),
                              prior_approved_hash=old.get("hash"), by=L.LIVE_APPROVER)
    except (L.LiveGateRefused, sizing.LimitsError) as e:
        return _refuse(err, str(e))
    out.write("Approved LIVE limits saved: %s\n" % sizing.approved_path(path))
    return 0 if snap else 2


def main(argv=None, out=None, err=None, isatty=None, read_line=None):
    out, err = out or sys.stdout, err or sys.stderr
    isatty = isatty or (lambda: bool(sys.stdin and sys.stdin.isatty()))
    read_line = read_line or (lambda: sys.stdin.readline())
    args = _parser().parse_args(argv)
    if args.cmd == "start":
        return _start(args, out, err, isatty, read_line)
    if args.cmd == "approve-limits":
        return _approve(args, out, err, isatty, read_line)
    return _refuse(err, "choose a subcommand: start or approve-limits (see LIVE_READINESS.md)")


if __name__ == "__main__":
    sys.exit(main())
