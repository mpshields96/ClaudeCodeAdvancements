#!/usr/bin/python3
"""One-action launcher for the offline paper desk (SIMULATED, paper only).

    /usr/bin/python3 -I desk/launch.py            # start the desk and open it in the browser
    /usr/bin/python3 -I desk/launch.py --check    # offline self-check, no browser, exit 0/1
    /usr/bin/python3 -I desk/launch.py --demo     # fresh scratch run to the end, weekly review, then the UI

Everything runs on this computer with stdlib only: the session runner
(desk/session.py), the offline fake broker, the order engine and the loopback
UI server (desk/ui/server.py). There is no broker account, no credential, no
network order path and no TradingView data feed. TradingView is a link the
operator opens in their own browser; the desk never reads it.

Limits are TEST VALUES. Matthew sets real sizing and limits himself.
"""
import argparse
import fcntl
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import threading
import time
import webbrowser

DESK = os.path.dirname(os.path.abspath(__file__))
if DESK not in sys.path:
    sys.path.insert(0, DESK)

import session as S  # noqa: E402
from ui import server as ui_server  # noqa: E402

DEFAULT_PORT = 8765
# The launcher runs the EMA desk at a HYPOTHETICAL fixed 1-share demo size (--qty 1),
# which fits the $10 TEST max loss and produces labeled mock fills, including one in
# the last replayed week. --qty 0 uses the strategy's own sizing: ema then sizes ~20
# shares and every entry is refused MAX_LOSS (by design: the limit is enforced).
LAUNCH_STRATEGY = "ema"
DEFAULT_QTY = 1


def strategy_cfg_for(qty):
    return {"fixed_qty": int(qty)} if qty and int(qty) > 0 else {}

EXTRA_ROUTES = {
    "/api/resume": ("resume", "resume"),
    "/api/advance": ("advance", "advance"),
    "/api/advance10": ("advance10", "advance10"),
    "/api/play": ("play", "play"),
    "/api/stop_play": ("stop_play", "stop_play"),
    "/api/run_to_end": ("run_to_end", "run_to_end"),
    "/api/clear_stop": ("clear_stop", "clear_stop"),
    "/api/schedule_on": ("schedule_on", "schedule_on"),
    "/api/schedule_off": ("schedule_off", "schedule_off"),
    "/api/close_session": ("close_session", "close_session"),
    "/api/preflight": ("preflight", "preflight"),
    "/api/weekly_report": ("weekly_report", "weekly_report"),
}


class DeskControls(object):
    """No-argument control methods for the UI server's record_control(), which
    writes each request durably before calling the method."""

    def __init__(self, runner, play_rate=4.0):
        self.r = runner
        self.play_rate = play_rate

    def arm(self):
        return self.r.arm()

    def pause(self):
        return self.r.pause()

    def resume(self):
        return self.r.resume()

    def stop_and_close(self):
        with self.r.lock:
            self.r.stop_play()
        return self.r.stop_and_close(reason="OPERATOR")

    def clear_stop(self):
        # The UI asks the operator to confirm before it posts this route.
        return self.r.clear_stop(confirm=True)

    def advance(self):
        return self.r.advance(1)

    def advance10(self):
        return self.r.advance(10)

    def play(self):
        return self.r.play(self.play_rate)

    def stop_play(self):
        with self.r.lock:
            self.r.stop_play()
            self.r._write_state()
        return {"ok": True, "simulated": True}

    def run_to_end(self):
        return self.r.run_to_end()

    def schedule_on(self):
        return self.r.set_schedule(True)

    def schedule_off(self):
        return self.r.set_schedule(False)

    def close_session(self):
        return self.r.close_session()

    def preflight(self):
        return self.r.preflight()

    def weekly_report(self, week=None):
        """Write the weekly review, then the <=3-page weekly PDF (HTML if no headless browser).

        In Alpaca mode the review covers this desk's own paper session only."""
        if week is not None and not re.match(r"^\d{4}-W\d{2}$", str(week)):
            return {"ok": False, "error": "week must look like 2026-W40"}
        with self.r.lock:
            rv = self.r.review(week=week)
        wk = rv.get("week") or rv.get("default_week")
        path = _write_report(self.r.state_dir, wk)
        if not path:
            return {"ok": False, "week": wk, "error": "report not written (see launcher output)"}
        try:
            import report as _report  # noqa: WPS433
            pages = getattr(_report.build_report, "last_pages", None)
        except ImportError:
            pages = None
        name = os.path.basename(path)
        self.r._desk_audit("weekly_report", week=wk, file=name, pages=pages)
        return {"ok": True, "simulated": True, "week": wk, "file": name, "url": "/reports/" + name,
                "pages": pages, "label": "SIMULATED weekly report (mock fills, TEST VALUES)"}


class AlpacaDeskControls(DeskControls):
    """Controls for the opt-in Alpaca PAPER session (desk/alpaca_session.py).

    Manual only: each step is one "Check for new bars" click. There is no Play, no schedule and
    no background job. Enable needs the UI's explicit confirm; Disable needs a reason; Stop also
    disables the adapter persistently; Reconcile is read-only and works while disabled or stopped."""

    def advance(self):
        return self.r.check_new_bars()

    def advance10(self):
        return self.r.check_new_bars()     # one manual check, never a loop

    def check_new_bars(self):
        return self.r.check_new_bars()

    def play(self):
        return self.r.play()

    def run_to_end(self):
        return self.r.run_to_end()

    def alpaca_enable(self, confirm=False):
        return self.r.alpaca_enable(confirm=confirm is True)

    def alpaca_disable(self, reason="OPERATOR"):
        return self.r.alpaca_disable(reason=reason)

    def reconcile_now(self):
        return self.r.reconcile_now()

    def lab_view(self):
        return self.r.lab_view()

    def lab_verify(self, forecast_id):
        return self.r.lab_verify(forecast_id)


def _alpaca():
    import alpaca_session as AS  # noqa: WPS433  (imported only for --broker alpaca-paper)
    return AS


def alpaca_state_dir(transport):
    return os.path.join(DESK, "state-alpaca-%s" % ("paper" if transport == "https" else "mock"))


def build_alpaca_runner(state_dir, strategy, transport, limits_path, provider="keychain"):
    """Mock: in-process fake Alpaca, synthetic ids and bars, no socket, no credential.

    https: approved limits are validated FIRST; only then is Matthew's credential provider
    constructed (constructing it reads nothing; the Keychain is read only when the first
    request is sent). Agents never start this mode."""
    AS = _alpaca()
    if transport == "https":
        AS.resolve_limits(AS.MODE_HTTPS, state_dir, limits_path)   # raises without approved limits
        from alpaca.setup import make_provider                      # noqa: WPS433
        from alpaca.transport import HttpsTransport                 # noqa: WPS433
        tr = HttpsTransport(make_provider(provider), timeout_s=10)
        return AS.AlpacaSessionController(state_dir, strategy=strategy, mode=AS.MODE_HTTPS,
                                          transport=tr, limits_path=limits_path)
    return AS.AlpacaSessionController(state_dir, strategy=strategy, mode=AS.MODE_MOCK,
                                      limits_path=limits_path)


def alpaca_self_check(strategy, keep_dir=None):
    """Mock Alpaca walkthrough in a temp dir (no socket, no credential, synthetic ids).

    Enable needs confirm; warm start reaches warm-up without routing history; the operator arms
    each day and clicks Check for new bars; every entry POST is a bounded SPY limit buy within the
    TEST notional cap; Stop disables the adapter persistently and a restart keeps it disabled;
    read-only reconcile still works after Stop."""
    AS = _alpaca()
    import alpaca as A  # noqa: WPS433
    base = keep_dir or tempfile.mkdtemp(prefix="desk-alpaca-check-")
    report, ok = {"state_dir": base, "steps": [], "evidence": A.LABEL_MOCK_LOCAL,
                  "data": A.DATA_LABEL_MOCK}, True

    def step(name, cond, **info):
        nonlocal ok
        ok = ok and bool(cond)
        report["steps"].append(dict(name=name, ok=bool(cond), **info))

    def posts(c):
        return [b for (m, p, q, b) in c.transport.trading.calls if m == "POST" and p == "/v2/orders"]

    c = c2 = None
    try:
        d = os.path.join(base, "run")
        c = AS.AlpacaSessionController(d, strategy=strategy, mode=AS.MODE_MOCK)
        st = c.session_state()
        step("labels_mock", st["simulated"] and st["evidence_label"] == A.LABEL_MOCK_LOCAL
             and st["data_label"] == A.DATA_LABEL_MOCK, broker_mode=st["broker_mode"])
        step("limits_are_test_values", "TEST VALUE" in str(c.limits_source.get("label")),
             label=c.limits_source.get("label"))
        step("adapter_off_until_enabled", not st["adapter"]["enabled"])
        step("enable_needs_confirm", c.alpaca_enable().get("reason") == "CONFIRM_REQUIRED")
        step("no_play_or_schedule", c.play().get("reason") == "NO_PLAY_IN_ALPACA_MODE"
             and c.set_schedule(True).get("reason") == "NO_SCHEDULE_IN_ALPACA_MODE")
        step("enable_confirmed", c.alpaca_enable(confirm=True).get("ok") is True)
        r = c.check_new_bars()
        wv = c.warmup_view()
        step("warm_start_ready", r.get("ok") and wv.get("ready"), bars=wv.get("bars"))
        step("history_never_routed", posts(c) == [])
        day = None
        for _ in range(14):
            if c.clock.now().date() != day:
                day = c.clock.now().date()
                c.arm()
            c.check_new_bars()
        buys = [b for b in posts(c) if b.get("side") == "buy"]
        cap = float(c.limits.get("per_trade_notional") or 0)
        step("bounded_limit_buys", bool(buys) and all(
            b.get("symbol") == "SPY" and b.get("type") == "limit" and "notional" not in b
            and int(b["qty"]) * float(b["limit_price"]) <= cap + 1e-9 for b in buys),
             buys=len(buys), cap=cap, limits=sorted(float(b["limit_price"]) for b in buys)[:5])
        step("bars_labeled_mock", all(b.get("source") == A.DATA_LABEL_MOCK for b in c.bars))
        c.stop_and_close(reason="CHECK")
        step("stop_disables_adapter", not c.adapter_state.enabled
             and c.alpaca_enable(confirm=True).get("reason") == "STOPPED")
        step("reconcile_after_stop", c.reconcile_now().get("ok") is True)
        c.close()
        c = None
        c2 = AS.AlpacaSessionController(d, strategy=strategy, mode=AS.MODE_MOCK)
        step("restart_keeps_disabled", not c2.adapter_state.enabled)
        try:
            AS.AlpacaSessionController(os.path.join(base, "h"), strategy=strategy, mode=AS.MODE_HTTPS)
            step("https_needs_approved_limits", False)
        except Exception as exc:
            step("https_needs_approved_limits", "limits" in str(exc).lower(), refused=exc.__class__.__name__)
    except Exception as exc:
        ok = False
        report["error"] = "%s: %s" % (exc.__class__.__name__, exc)
    finally:
        for x in (c, c2):
            if x is not None:
                try:
                    x.close()
                except Exception:
                    pass
        if keep_dir is None:
            shutil.rmtree(base, ignore_errors=True)
            report["state_dir"] += " (removed)"
    report["ok"] = ok
    return ok, report


READINESS_CMD = ("/usr/bin/python3 -IB desk/alpaca/readiness.py --state-dir <your paper state dir> "
                 "--limits <your approved limits file>")


def _write_report(state_dir, week):
    """Weekly PDF via desk/report.py when present (owned by the strategies/report worker)."""
    try:
        import report as _report  # noqa: WPS433
    except ImportError:
        return None
    fn = getattr(_report, "build_report", None)
    if fn is None:
        return None
    try:
        return fn(state_dir, week=week)
    except Exception as exc:  # the desk keeps running; the report error is shown
        print("[desk] weekly report failed: %s: %s" % (exc.__class__.__name__, exc))
        return None


def install_routes():
    added = []
    for route, spec in EXTRA_ROUTES.items():
        if route not in ui_server.CONTROL_ROUTES:
            ui_server.CONTROL_ROUTES[route] = spec
            added.append(route)
    return added


def free_port(host, port, tries=20):
    for p in range(port, port + tries):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((host, p))
            return p
        except OSError:
            continue
        finally:
            s.close()
    raise RuntimeError("no free loopback port in %d..%d" % (port, port + tries - 1))


def _summary(runner):
    st = runner.session_state()
    fills = runner.mgr.fills
    bfills = [f for o in runner.broker._orders.values() for f in o["fills"]]
    rejected = sum(1 for d in runner.decisions if str(d.get("reason_code", "")).startswith("DATA_REJECTED"))
    return {
        "strategy": runner.strategy, "bars_done": st["bars_done"], "bars_total": st["bars_total"],
        "phase": st["phase"], "fills": len(fills),
        "fills_all_mock": all(f.get("mock") and f.get("simulated") for f in bfills),
        "fees_usd": round(sum(float(f.get("fee") or 0) for f in bfills), 2),
        "min_cost_bps": min([f.get("cost_bps", 0) for f in bfills] or [0]),
        "position_qty": st["exposure"]["position_qty"],
        "decisions": len(runner.decisions), "data_rejected": rejected,
        "limits_label": st["limits"]["label"], "broker": st["broker"]["name"],
        "external_broker": st["external_broker_badge"],
    }


def self_check(strategy, keep_dir=None, qty=DEFAULT_QTY):
    """Offline end-to-end check. Returns (ok, report). Uses a temporary state dir."""
    base = keep_dir or tempfile.mkdtemp(prefix="desk-check-")
    report, ok = {"state_dir": base, "steps": []}, True

    def step(name, cond, **info):
        nonlocal ok
        ok = ok and bool(cond)
        report["steps"].append(dict(name=name, ok=bool(cond), **info))

    try:
        d1 = os.path.join(base, "run")
        cfg = strategy_cfg_for(qty)
        r = S.SessionController(d1, strategy=strategy, strategy_cfg=cfg)
        pf = r.preflight()
        step("preflight", isinstance(pf, list) and all(c.get("ok") for c in pf),
             failed=[c["check"] for c in pf if not c.get("ok")])
        step("schedule_on", r.set_schedule(True).get("ok"))
        # Advance until a mock position is open with a working protective stop, so the
        # restart below has a real book (fills, open position, working order) to keep.
        while r.i < len(r.bars) and not (r.broker._pos_qty and any(
                o["status"] == "working" for o in r.broker._orders.values())):
            r.advance(1)
        mid = _summary(r)
        step("restart_point_has_open_book", r.broker._pos_qty != 0, bar=r.i, position=r.broker._pos_qty)
        exec_ids = sorted(f["exec_id"] for o in r.broker._orders.values() for f in o["fills"])
        pos = r.broker._pos_qty
        working = sorted(c for c, o in r.broker._orders.items() if o["status"] == "working")
        r.close()
        r2 = S.SessionController(d1, strategy=strategy, strategy_cfg=cfg)   # full restart from disk
        exec2 = sorted(f["exec_id"] for o in r2.broker._orders.values() for f in o["fills"])
        work2 = sorted(c for c, o in r2.broker._orders.items() if o["status"] == "working")
        step("restart_keeps_broker_book", r2.broker_restored and exec2 == exec_ids and r2.broker._pos_qty == pos
             and work2 == working, fills_before=len(exec_ids), position=pos, working=len(working))
        step("restart_engine_agrees", r2.mgr.state()["exposure"]["position_qty"] == r2.broker._pos_qty)
        r2.run_to_end()
        fin = _summary(r2)
        step("mock_fills_present", fin["fills"] > 0, fills=fin["fills"])
        step("fills_labeled_mock", fin["fills_all_mock"])
        step("fills_have_costs", fin["fees_usd"] > 0 and fin["min_cost_bps"] > 0,
             fees_usd=fin["fees_usd"], min_cost_bps=fin["min_cost_bps"])
        step("ends_flat", fin["position_qty"] == 0, position=fin["position_qty"])
        rv = r2.review()
        step("review_written", os.path.exists(os.path.join(d1, "review.json")) and "best_pass" in rv)
        step("review_is_weekly", rv.get("week") == rv.get("default_week") and len(rv.get("weeks") or []) > 1
             and set(rv.get("by_week") or {}) == set(rv.get("weeks") or []),
             week=rv.get("week"), weeks=len(rv.get("weeks") or []))
        ents = [d for d in r2.decisions if str(d.get("action", "")).startswith("enter")]
        want = int(qty) if qty else None
        step("entry_qty_as_selected", bool(ents) and (want is None or all(
            d.get("qty") == want for d in ents if (d.get("routing") or {}).get("status") == "acked")),
             qty=want, entries=len(ents), sizing=r2.sizing()["label"])
        refused_ids = {x["decision_id"] for wk in (rv.get("by_week") or {}).values()
                       for x in wk.get("refused_decisions") or []}
        step("refused_never_filled", not any(row["fills"] for row in r2.mgr.ledger_rows()
                                             if row.get("decision_id") in refused_ids),
             refused=len(refused_ids))
        step("no_external_broker", fin["external_broker"].startswith("EXTERNAL BROKER: NONE"),
             badge=fin["external_broker"])
        r2.close()
        # A different size on the same state dir is refused, never applied mid-session.
        other = {"fixed_qty": (int(qty) + 3) if qty else 4}
        try:
            S.SessionController(d1, strategy=strategy, strategy_cfg=other)
            step("size_change_refused", False, requested=other)
        except S.SessionConfigChanged as exc:
            step("size_change_refused", "strategy_cfg" in str(exc), requested=other)
        # Intake guard on a corrupted feed: a gap bar must not fill a working order.
        d2 = os.path.join(base, "gap")
        g = S.SessionController(d2, strategy="cash")
        g.arm()
        g.advance(1)
        b0 = g.seen[-1]
        iid = g.mgr.submit_intent({"decision_id": "check-gap", "kind": "entry", "side": "buy", "qty": 1,
                                   "ref_price": b0["close"], "invalidation": b0["close"] - 0.5,
                                   "signal_ts": b0["ts_close"]})
        g.bars.pop(1)
        g.advance(1)
        it = g.mgr.intents[iid]
        step("gap_bar_no_fill", it["filled_qty"] == 0, status=it["status"], intake=g.mgr._bar_status)
        g.close()
        report["mid"] = mid
        report["final"] = fin
    except Exception as exc:
        ok = False
        report["error"] = "%s: %s" % (exc.__class__.__name__, exc)
    finally:
        if keep_dir is None:
            shutil.rmtree(base, ignore_errors=True)
            report["state_dir"] += " (removed)"
    report["ok"] = ok
    return ok, report


LOCK_SUFFIX = ".launch.lock"


def hold_scenario_lock(state_dir):
    """Hold a stable sibling lock (<state_dir>.launch.lock) for this launcher's lifetime.

    It sits beside the state dir, so --fresh/--demo rotation cannot move it. A second launcher on the
    same scenario (with or without --fresh) is refused before it renames or opens anything.
    Returns the open file (keep it referenced) or None when another launcher holds it.
    """
    path = state_dir.rstrip(os.sep) + LOCK_SUFFIX
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if os.path.islink(path):
        raise RuntimeError("refusing symlinked lock file: %s" % path)
    fh = open(path, "a")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def _take_inner_lock(state_dir):
    """Try the OrderManager lock inside an existing state dir. Returns (held_by_other, fh)."""
    path = os.path.join(state_dir, ".orders.lock")
    if not os.path.exists(path):
        return False, None
    if os.path.islink(path):
        return True, None
    fh = open(path, "a")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return True, None
    return False, fh


def _refuse_in_use(state_dir, why):
    print("[desk] REFUSED: state dir %s is in use (%s). Nothing was renamed, created or changed. "
          "Stop that launcher first, or start this one with a unique new --state-dir; old and new "
          "limits are never mixed." % (state_dir, why))
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description="Offline paper desk launcher (SIMULATED, paper only)")
    ap.add_argument("--state-dir", default=S.DEFAULT_STATE_DIR,
                    help="scratch state directory (default desk/state; created if missing)")
    ap.add_argument("--strategy", default=LAUNCH_STRATEGY, choices=S.strategy_names())
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    ap.add_argument("--fresh", action="store_true",
                    help="move an existing state dir aside (renamed, never deleted) and start clean")
    ap.add_argument("--play-rate", type=float, default=4.0, help="bars per second for Play (max %d)"
                    % S.MAX_PLAY_RATE)
    ap.add_argument("--autoplay", action="store_true", help="enable the simulated schedule and start Play")
    ap.add_argument("--qty", type=int, default=DEFAULT_QTY,
                    help="HYPOTHETICAL fixed entry size in shares (TEST VALUE, default 1); 0 = strategy sizing")
    ap.add_argument("--check", action="store_true", help="offline self-check in a temp dir, then exit")
    ap.add_argument("--demo", action="store_true",
                    help="fresh scratch state, run the whole replay, write the weekly review, then serve the UI")
    ap.add_argument("--broker", choices=("offline", "alpaca-paper"), default="offline",
                    help="offline (default): in-process FakeBroker replay. alpaca-paper: opt-in SPY paper "
                         "session, manual checks only")
    ap.add_argument("--transport", choices=("mock", "https"), default="mock",
                    help="alpaca-paper only. mock (default): in-process fake Alpaca, synthetic ids, no "
                         "network. https: Alpaca's fixed paper host; needs --limits (operator-approved)")
    ap.add_argument("--limits", help="alpaca-paper: operator-approved limits snapshot from the Setup worksheet")
    ap.add_argument("--provider", choices=("keychain", "env"), default="keychain",
                    help="alpaca-paper https: where the paper keys are read from at the first request")
    a = ap.parse_args(argv)
    alpaca = a.broker == "alpaca-paper"

    if alpaca and (a.demo or a.autoplay):
        print("[desk] REFUSED: --demo and --autoplay are replay-only; the Alpaca paper session is manual "
              "(arm each day, then click Check for new bars). Nothing was started.")
        return 2
    if not alpaca and (a.transport != "mock" or a.limits):
        print("[desk] REFUSED: --transport and --limits apply only with --broker alpaca-paper.")
        return 2

    if a.check:
        if alpaca:
            if a.transport != "mock":
                print("[desk] REFUSED: --check runs the mock walkthrough only; it never contacts a broker.")
                return 2
            ok, rep = alpaca_self_check(a.strategy)
            print(json.dumps(rep, indent=2, default=str))
            print("ALPACA MOCK CHECK %s (MOCK LOCAL fake Alpaca, synthetic ids and bars, TEST limits, "
                  "no network)" % ("PASS" if ok else "FAIL"))
            print("[desk] First real paper connection (operator only, after approving limits): %s" % READINESS_CMD)
            return 0 if ok else 1
        ok, rep = self_check(a.strategy, qty=a.qty)
        print(json.dumps(rep, indent=2, default=str))
        print("CHECK %s (SIMULATED, mock fills, TEST limits)" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1

    if alpaca and a.state_dir == S.DEFAULT_STATE_DIR:
        a.state_dir = alpaca_state_dir(a.transport)
    if alpaca and a.qty != DEFAULT_QTY:
        print("[desk] note: --qty is ignored with --broker alpaca-paper; the fixed share quantity comes "
              "from the limits (mock: TEST VALUE; https: your approved snapshot).")
    state_dir = os.path.abspath(a.state_dir)
    if a.demo and a.state_dir == S.DEFAULT_STATE_DIR:
        state_dir = os.path.abspath(os.path.join(DESK, "state-demo"))
    scenario_lock = hold_scenario_lock(state_dir)   # held until this process exits
    if scenario_lock is None:
        return _refuse_in_use(state_dir, "another launcher holds %s" % (state_dir.rstrip(os.sep) + LOCK_SUFFIX))
    held, inner = _take_inner_lock(state_dir)
    if held:
        scenario_lock.close()
        return _refuse_in_use(state_dir, "its order manager lock is held by another process")
    try:
        if (a.fresh or a.demo) and os.path.exists(state_dir):
            aside = "%s.prev-%s" % (state_dir, time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
            os.rename(state_dir, aside)
            print("[desk] previous state moved to %s" % aside)
    finally:
        if inner is not None:
            inner.close()
    try:
        if alpaca:
            runner = build_alpaca_runner(state_dir, a.strategy, a.transport, a.limits, a.provider)
        else:
            runner = S.SessionController(state_dir, strategy=a.strategy, strategy_cfg=strategy_cfg_for(a.qty))
    except S.SessionConfigChanged as exc:
        print("[desk] %s" % exc)
        scenario_lock.close()
        return 2
    except RuntimeError as exc:
        scenario_lock.close()
        return _refuse_in_use(state_dir, str(exc))
    except Exception as exc:
        if not alpaca:
            raise
        # Limits missing/unapproved (sizing.LimitsError), adapter module missing, bad snapshot.
        print("[desk] REFUSED: %s: %s. Nothing was sent to any broker." % (exc.__class__.__name__, exc))
        scenario_lock.close()
        return 2
    if a.demo:
        runner.set_schedule(True)
        runner.run_to_end()
        rv = runner.review()
        print("[desk] demo replay done: %d bars, %d weeks, default week %s (%d round trips, %d fills); "
              "all weeks: %d round trips" % (runner.i, len(rv["weeks"]), rv["default_week"],
                                            len(rv["round_trips"]), rv["fills"],
                                            rv["all_weeks_summary"]["round_trips"]))
        rp = _write_report(state_dir, rv["default_week"])
        if rp:
            print("[desk] weekly report %s" % rp)
    controls = (AlpacaDeskControls if alpaca else DeskControls)(runner, play_rate=a.play_rate)
    added = install_routes()
    host = "127.0.0.1"
    port = free_port(host, a.port)
    httpd = ui_server.make_server(state_dir, host, port, manager=controls)
    url = "http://%s:%d/" % (host, port)
    t = threading.Thread(target=httpd.serve_forever, name="desk-ui", daemon=True)
    t.start()
    if alpaca:
        st = runner.session_state()
        print("[desk] %s" % st.get("badge"))
        print("[desk] evidence  %s" % runner.evidence_label)
        print("[desk] data      %s" % runner.data_label)
        print("[desk] UI        %s" % url)
        print("[desk] state     %s" % state_dir)
        print("[desk] strategy  %s   limits: %s" % (a.strategy, runner.limits_source.get("label")))
        print("[desk] sizing    %s" % runner.sizing()["label"])
        print("[desk] adapter   %s (Enable in the UI needs your confirm; Stop disables it again)"
              % ("ENABLED" if runner.adapter_state.enabled else "DISABLED"))
        print("[desk] manual    arm each trading day, then click Check for new bars. No Play, no schedule, "
              "no background job: nothing happens while you are not clicking.")
        if a.transport == "https":
            print("[desk] first connection check (read-only, no orders): %s" % READINESS_CMD)
    else:
        print("[desk] SIMULATED paper desk. Mock fills only. No broker account, no credentials, no real orders.")
        print("[desk] UI        %s" % url)
        print("[desk] state     %s" % state_dir)
        print("[desk] strategy  %s   limits: %s" % (a.strategy, runner.limits.get("label")))
        print("[desk] sizing    %s" % runner.sizing()["label"])
        print("[desk] controls  arm / pause / resume / stop_close / clear_stop / play / advance / schedule (%d routes "
              "added by launcher)" % len(added))
    print("[desk] Ctrl-C to quit. State is saved after every bar; relaunching resumes it.")
    if a.autoplay:
        runner.set_schedule(True)
        runner.play(a.play_rate)
    if not a.no_browser:
        webbrowser.open(url)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        httpd.server_close()
        runner.close()
        scenario_lock.close()
        print("[desk] stopped; state kept in %s" % state_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
