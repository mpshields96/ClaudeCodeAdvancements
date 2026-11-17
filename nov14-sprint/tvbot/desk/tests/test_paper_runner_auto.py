"""alpaca/paper_runner.py --auto: after one deliberate paper start the runner presses Enable and Arm itself, at
most once each, only on the paper desk, only after warm-up and regular-session eligibility, with an arm expiry
no later than the run end; it stops and never re-enables or re-arms after a Stop, a risk latch, an unresolved
or unknown order, a foreign order or a lost connection. Offline: in-process fake desk, synthetic clock."""
import os
import unittest
from pathlib import Path

import test_paper_runner as T

PR = T.PR
ENABLE = ("POST", "/api/alpaca/enable")
ARM = ("POST", "/api/arm")
ADVANCE = ("POST", "/api/advance")
STOP_CLOSE = ("POST", "/api/stop_close")
CONN_CHECK = ("POST", "/api/alpaca/connection_check")


class AutoDesk(T.FakeDesk):
    """The paper desk with the session fields auto mode reads (warm-up, preflight, controls, expiry) and the two
    routes auto mode may press. Any other route still fails the test."""

    def __init__(self, state_dir, ready_after=1, honour_expiry=True, bounded=True, **kw):
        T.FakeDesk.__init__(self, state_dir, **kw)
        self.ready_after = ready_after          # warm-up completes on this check number
        self.honour_expiry = honour_expiry      # False: the desk ignores the requested expiry (today's /api/arm)
        if bounded:                             # the desk advertises that /api/arm honours a body expires_utc
            self.health[PR.ARM_BOUND_FLAG] = True
        self.cc_fills = True                    # the connection check fills the fractional rows
        self.default_expiry = "2026-11-17T21:05:00Z"   # NYSE close + 5 minutes
        self.session.update({
            "warmup": {"bars": 0, "needed": 63, "ready": False, "text": "strategy warm-up 0/63"},
            "controls": {"stopped": False, "stop_reason": None, "paused": False, "day_stop": None},
            "expires_utc": None, "recovery": {"ambiguous": False, "reason": None},
            "preflight": [{"check": "adapter enabled", "ok": False, "detail": "disabled"},
                          {"check": "calendar", "ok": True, "detail": "session open"},
                          {"check": "venue clock", "ok": True, "detail": "market open"},
                          {"check": "stop", "ok": True, "detail": "no Stop active"}]})
        self.on_check = None                    # fn(desk, n) after the warm-up update

    def row(self, name, ok):
        for r in self.session["preflight"]:
            if r["check"] == name:
                r["ok"] = ok

    def call(self, method, path, body=None):
        if (method, path) == CONN_CHECK:
            self.calls.append((method, path, body))
            if self.cc_fills:
                for name in PR.FRACTIONAL_ROWS:
                    self.row(name, True)
            return 200, {"ok": True, "controller_called": True,
                         "controller_result": {"ok": self.cc_fills, "method": "GET only", "orders_sent": 0}}
        if (method, path) in (ENABLE, ARM):
            self.calls.append((method, path, body))
            if path == "/api/alpaca/enable":
                if not (body or {}).get("confirm") is True:
                    return 400, {"ok": False}
                self.session["adapter"] = {"enabled": True, "disabled_reason": None}
                self.row("adapter enabled", True)
                return 200, {"ok": True, "controller_called": True,
                             "controller_result": {"ok": True, "adapter": {"enabled": True}}}
            exp = (body or {}).get("expires_utc") if self.honour_expiry else None
            self.session.update(armed=True, expires_utc=exp or self.default_expiry, entry_block_reason=None,
                                badge="ALPACA PAPER: ARMED")
            return 200, {"ok": True, "controller_called": True,
                         "controller_result": {"ok": True, "expires_utc": self.session["expires_utc"]}}
        if (method, path) == ADVANCE:
            n = len(self.decisions) + 1
            if n >= self.ready_after:
                self.session["warmup"] = {"bars": 63, "needed": 63, "ready": True, "text": "ready"}
            if self.on_check:
                self.on_check(self, n)
        return T.FakeDesk.call(self, method, path, body)

    def presses(self):
        return [r for r in self.routes() if r in (ENABLE, ARM)]


class AutoBase(T.Base):
    def auto(self, desk, minutes=3, every=30, at_end="close"):
        desk.clock = self.clock
        return PR.Runner(minutes, every, at_end=at_end, state_dir=self.state, client=desk,
                         find_desk=lambda: 18858, launch=lambda: self.fail("must attach, not launch"),
                         ps=lambda: [], now=self.clock.now, sleep=self.clock.sleep, out=self.lines.append,
                         auto=True)


class AutoStartTests(AutoBase):
    def test_auto_presses_enable_then_arm_once_after_warmup_with_expiry_at_the_run_end(self):
        desk = AutoDesk(self.state, ready_after=2)
        r = self.auto(desk, minutes=3)
        self.assertEqual(r.run(), PR.EXIT_OK)
        routes = desk.routes()
        self.assertEqual(desk.presses(), [ENABLE, ARM])
        first_press = routes.index(ENABLE)
        self.assertEqual(routes[:first_press].count(ADVANCE), 2)          # waited for warm-up (check 2)
        enable_body = [b for m, p, b in desk.calls if (m, p) == ENABLE][0]
        arm_body = [b for m, p, b in desk.calls if (m, p) == ARM][0]
        self.assertEqual(enable_body, {"confirm": True})
        self.assertEqual(arm_body, {"expires_utc": "2026-11-17T14:33:00Z"})  # started 14:30Z, 3 minutes
        self.assertEqual(r.record["auto"]["armed_expires_utc"], "2026-11-17T14:33:00Z")
        self.assertTrue(any("AUTO: armed by this runner" in s for s in self.lines), self.lines)

    def test_auto_waits_for_the_regular_session_before_pressing(self):
        desk = AutoDesk(self.state, ready_after=1)
        desk.row("venue clock", False)

        def opens(d, n):
            if n == 3:
                d.row("venue clock", True)
        desk.on_check = opens
        r = self.auto(desk, minutes=3)
        self.assertEqual(r.run(), PR.EXIT_OK)
        routes = desk.routes()
        self.assertEqual(desk.presses(), [ENABLE, ARM])
        self.assertEqual(routes[:routes.index(ENABLE)].count(ADVANCE), 3)
        self.assertTrue(any("AUTO: waiting (regular session not open (venue clock))" in s for s in self.lines))

    def test_reconcile_runs_right_before_enable(self):
        desk = AutoDesk(self.state)
        self.assertEqual(self.auto(desk).run(), PR.EXIT_OK)
        routes = desk.routes()
        i = routes.index(ENABLE)
        self.assertEqual(routes[i - 2:i], [("POST", "/api/alpaca/reconcile"), ("GET", "/api/session")])

    def test_desk_already_armed_outside_the_runner_is_never_pressed(self):
        desk = AutoDesk(self.state)
        desk.session.update(armed=True, expires_utc="2026-11-17T21:05:00Z")
        r = self.auto(desk)
        self.assertEqual(r.run(), PR.EXIT_OK)
        self.assertEqual(desk.presses(), [])
        self.assertIn("armed outside this runner", r.record["auto"]["monitor_only"])

    def test_unbounded_arm_expiry_is_ended_at_once_with_stop_and_close(self):
        desk = AutoDesk(self.state, honour_expiry=False)   # today's /api/arm ignores the requested expiry
        r = self.auto(desk, minutes=3)
        r.run()
        routes = desk.routes()
        self.assertEqual(desk.presses(), [ENABLE, ARM])
        self.assertEqual(routes[routes.index(ARM) + 1:routes.index(ARM) + 3], [("GET", "/api/session"), STOP_CLOSE])
        self.assertEqual(routes[routes.index(ARM):].count(ADVANCE), 0)    # the run ends; no further check
        self.assertIn("later than the run end", r.record["auto"]["stop_trigger"])
        self.assertIn("Stop & Close pressed at once", r.record["auto"]["unbounded_arm_action"])
        self.assertTrue(r.record["ended_by"].startswith("stop trigger:"))

    def test_arm_that_lapses_is_never_re_armed_and_the_rest_is_monitor_only(self):
        desk = AutoDesk(self.state)

        def lapse(d, n):
            if n == 3:
                d.session.update(armed=False, entry_block_reason="NOT_ARMED")
        desk.on_check = lapse
        r = self.auto(desk, minutes=3)
        self.assertEqual(r.run(), PR.EXIT_OK)
        self.assertEqual(desk.presses(), [ENABLE, ARM])
        self.assertEqual(desk.routes().count(ADVANCE), 6)                  # the run continues to the deadline
        self.assertIn("arm lapsed", r.record["auto"]["monitor_only"])
        self.assertEqual(r.record["ended_by"], "deadline")
        after = [c["auto"] for c in r.record["checks"][2:]]
        self.assertTrue(all("MONITOR-ONLY" in t and "never re-arms" in t for t in after), after)
        self.assertTrue(sum("MONITOR-ONLY" in s for s in self.lines) >= 4)

    def test_owned_exposure_at_the_deadline_gets_the_clean_end(self):
        desk = AutoDesk(self.state)

        def held(d, n):
            if n == 2:
                d.session["exposure"] = {"position_qty": 1, "broker_position_qty": 1, "working_orders": [{"id": "x"}]}
        desk.on_check = held

        def close(d):
            d.session["exposure"] = {"position_qty": 0, "broker_position_qty": 0, "working_orders": []}
        desk.on_stop_close = close
        r = self.auto(desk, minutes=2)
        self.assertEqual(r.run(), PR.EXIT_OK)
        self.assertEqual(desk.presses(), [ENABLE, ARM])
        self.assertIn(("POST", "/api/stop_close", {"confirm": True}), desk.calls)
        self.assertEqual(r.record["end_status"], "flat")


class AutoCapabilityTests(AutoBase):
    """Enable/Arm need a desk whose /api/arm can be bounded to the run end; the fractional preflight rows get
    one non-executing connection check."""

    def test_desk_without_bounded_arm_is_monitor_only_and_never_pressed(self):
        desk = AutoDesk(self.state, bounded=False)       # today's server: /api/arm drops a body expires_utc
        r = self.auto(desk, minutes=3)
        self.assertEqual(r.run(), PR.EXIT_OK)
        self.assertEqual(desk.presses(), [])
        self.assertNotIn(CONN_CHECK, desk.routes())
        self.assertNotIn(STOP_CLOSE, desk.routes())
        self.assertIn("cannot bound Arm to the run end", r.record["auto"]["monitor_only"])
        self.assertEqual(r.record["ended_by"], "deadline")
        self.assertEqual(desk.routes().count(ADVANCE), 6)                # it still checks to the deadline
        self.assertTrue(any("MONITOR-ONLY" in s and "cannot bound Arm" in s for s in self.lines), self.lines)

    def test_bounded_arm_flag_lost_before_the_press_is_monitor_only(self):
        desk = AutoDesk(self.state, ready_after=2)
        desk.on_check = lambda d, n: d.health.pop(PR.ARM_BOUND_FLAG, None) if n == 2 else None
        r = self.auto(desk, minutes=3)
        self.assertEqual(r.run(), PR.EXIT_OK)
        self.assertEqual(desk.presses(), [])
        routes = desk.routes()
        last_check = len(routes) - 1 - routes[::-1].index(ADVANCE)
        between = routes[routes.index(ADVANCE):last_check]          # no pre-press reconcile between checks
        self.assertNotIn(("POST", "/api/alpaca/reconcile"), between)
        self.assertIn(("POST", "/api/alpaca/reconcile"), routes[last_check:])   # the clean end still reconciles
        self.assertIn("cannot bound Arm to the run end", r.record["auto"]["monitor_only"])

    def fractional(self, **kw):
        desk = AutoDesk(self.state, **kw)
        desk.session["preflight"] += [
            {"check": "SPY fractionable", "ok": False, "detail": "FRACTIONABLE_UNVERIFIED: run the connection check"},
            {"check": "non-margin cash", "ok": False, "detail": "CASH_UNAVAILABLE: run the connection check"}]
        return desk

    def test_fractional_rows_get_one_connection_check_then_enable_and_arm(self):
        desk = self.fractional()
        r = self.auto(desk, minutes=3)
        self.assertEqual(r.run(), PR.EXIT_OK)
        routes = desk.routes()
        self.assertEqual(routes.count(CONN_CHECK), 1)
        self.assertEqual(desk.presses(), [ENABLE, ARM])
        self.assertLess(routes.index(CONN_CHECK), routes.index(ENABLE))
        self.assertEqual([b for m, p, b in desk.calls if (m, p) == CONN_CHECK], [{}])
        self.assertTrue(r.record["auto"]["connection_check"]["ok"])
        self.assertEqual(r.record["auto"]["armed_expires_utc"], "2026-11-17T14:33:00Z")

    def test_connection_check_that_leaves_the_rows_failing_is_not_repeated_and_never_arms(self):
        desk = self.fractional()
        desk.cc_fills = False
        r = self.auto(desk, minutes=3)
        self.assertEqual(r.run(), PR.EXIT_OK)
        self.assertEqual(desk.routes().count(CONN_CHECK), 1)
        self.assertEqual(desk.presses(), [])
        self.assertIn("one connection check", r.record["auto"]["monitor_only"])
        self.assertEqual(r.record["ended_by"], "deadline")

    def test_no_connection_check_while_another_preflight_row_fails(self):
        desk = self.fractional()
        desk.session["preflight"].append({"check": "limits approved", "ok": False, "detail": "no approval"})
        r = self.auto(desk, minutes=3)
        self.assertEqual(r.run(), PR.EXIT_OK)
        self.assertNotIn(CONN_CHECK, desk.routes())
        self.assertEqual(desk.presses(), [])
        self.assertTrue(any("AUTO: waiting (desk preflight not ready" in s for s in self.lines), self.lines)

    def test_no_connection_check_on_a_desk_without_bounded_arm(self):
        desk = self.fractional(bounded=False)
        r = self.auto(desk, minutes=3)
        r.run()
        self.assertNotIn(CONN_CHECK, desk.routes())
        self.assertEqual(desk.presses(), [])

    def test_monitor_only_default_never_presses_the_connection_check(self):
        desk = self.fractional()
        r = self.runner(desk, minutes=2)
        self.assertEqual(r.run(), PR.EXIT_OK)
        self.assertNotIn(CONN_CHECK, desk.routes())
        with self.assertRaises(PR.Refused):
            r.post("/api/alpaca/connection_check", {})


class AutoStopTriggerTests(AutoBase):
    """Each trigger, read from desk state, ends the run; no Enable or Arm POST follows it."""

    def after_arm(self, change, at=3, minutes=5):
        desk = AutoDesk(self.state)

        def hit(d, n):
            if n == at:
                change(d)
        desk.on_check = hit
        r = self.auto(desk, minutes=minutes)
        code = r.run()
        routes = desk.routes()
        self.assertEqual(desk.presses(), [ENABLE, ARM], routes)
        self.assertEqual(routes.count(ADVANCE), at, routes)          # stopped on the check that saw it
        self.assertTrue(r.record["ended_by"].startswith("stop trigger: "), r.record["ended_by"])
        self.assertEqual(r.record["auto"]["stop_trigger"], r.record["ended_by"][len("stop trigger: "):])
        return r, code, desk

    def before_press(self, change):
        desk = AutoDesk(self.state, ready_after=1)
        desk.on_check = lambda d, n: change(d) if n == 1 else None
        r = self.auto(desk)
        code = r.run()
        self.assertEqual(desk.presses(), [], desk.routes())
        self.assertTrue(r.record["ended_by"].startswith("stop trigger: "), r.record["ended_by"])
        return r, code, desk

    @staticmethod
    def stopped(reason):
        def change(d):
            d.session["controls"] = dict(d.session["controls"], stopped=True, stop_reason=reason)
            d.session.update(armed=False, entry_block_reason="STOPPED")
        return change

    @staticmethod
    def alarm(code):
        def change(d):
            d.session["alarms"] = [{"code": code, "blocking": True, "detail": "test"}]
        return change

    def test_operator_stop_after_arm(self):
        r, code, _ = self.after_arm(self.stopped("OPERATOR"))
        self.assertIn("operator Stop (OPERATOR)", r.record["ended_by"])
        self.assertEqual(code, PR.EXIT_OK)

    def test_operator_stop_before_the_press(self):
        r, _, _ = self.before_press(self.stopped("OPERATOR"))
        self.assertIn("operator Stop", r.record["ended_by"])

    def test_risk_latch_daily_loss_stop_after_arm(self):
        r, _, _ = self.after_arm(lambda d: d.session.update(entry_block_reason="DAILY_LOSS_STOP"))
        self.assertIn("risk latch (DAILY_LOSS_STOP)", r.record["ended_by"])

    def test_risk_latch_from_todays_day_stop_before_the_press(self):
        def latch(d):
            d.session["controls"] = dict(d.session["controls"], day_stop={"day": "2026-11-17", "reason": "DAILY_LOSS"})
        r, _, _ = self.before_press(latch)
        self.assertIn("risk latch", r.record["ended_by"])

    def test_yesterdays_day_stop_does_not_block(self):
        desk = AutoDesk(self.state)
        desk.session["controls"]["day_stop"] = {"day": "2026-11-16", "reason": "DAILY_LOSS"}
        self.assertEqual(self.auto(desk).run(), PR.EXIT_OK)
        self.assertEqual(desk.presses(), [ENABLE, ARM])

    def test_unresolved_submit_after_arm(self):
        r, _, _ = self.after_arm(lambda d: d.session.update(entry_block_reason="UNRESOLVED_SUBMIT"))
        self.assertIn("unresolved order (UNRESOLVED_SUBMIT)", r.record["ended_by"])

    def test_unknown_order_status_alarm_after_arm(self):
        r, _, _ = self.after_arm(self.alarm("UNKNOWN_STATUS"))
        self.assertIn("unresolved or unknown order (blocking alarm UNKNOWN_STATUS)", r.record["ended_by"])

    def test_ambiguous_recovery_before_the_press(self):
        r, _, _ = self.before_press(lambda d: d.session.update(recovery={"ambiguous": True, "reason": "unresolved submit(s): x"}))
        self.assertIn("unresolved order (recovery ambiguous", r.record["ended_by"])

    def test_foreign_order_alarm_after_arm(self):
        r, _, _ = self.after_arm(self.alarm("FOREIGN_ORDER"))
        self.assertIn("foreign order or position (FOREIGN_ORDER)", r.record["ended_by"])

    def test_foreign_order_at_alpaca_found_by_the_reconcile_before_enable(self):
        r, _, desk = self.before_press(lambda d: setattr(d, "external", [{"client_id": "outside-1", "status": "new"}]))
        self.assertIn("foreign order at Alpaca before Enable", r.record["ended_by"])
        self.assertEqual(r.record["end_status"], "exposed")
        self.assertNotIn(STOP_CLOSE, desk.routes())

    def test_unmatched_broker_position_after_arm(self):
        r, _, _ = self.after_arm(lambda d: d.session.update(
            exposure={"position_qty": 0, "broker_position_qty": 1, "working_orders": []}))
        self.assertIn("foreign or unmatched position", r.record["ended_by"])

    def test_lost_connection_on_a_check_after_arm(self):
        desk = AutoDesk(self.state)
        base = desk.call

        def call(method, path, body=None, state={"n": 0}):
            if (method, path) == ADVANCE:
                state["n"] += 1
                if state["n"] == 3:
                    desk.calls.append((method, path, body))
                    raise ConnectionResetError("desk gone")
            return base(method, path, body)
        desk.call = call
        r = self.auto(desk, minutes=5)
        r.run()
        self.assertEqual(desk.presses(), [ENABLE, ARM])
        self.assertEqual(desk.routes().count(ADVANCE), 3)
        self.assertIn("lost connection (check failed: ConnectionResetError)", r.record["ended_by"])

    def test_broker_disconnected_after_arm(self):
        r, _, _ = self.after_arm(lambda d: d.session.update(entry_block_reason="BROKER_DISCONNECTED"))
        self.assertIn("lost connection (BROKER_DISCONNECTED)", r.record["ended_by"])

    def test_adapter_disabled_after_the_runner_enabled_it(self):
        r, _, _ = self.after_arm(lambda d: d.session.update(adapter={"enabled": False, "disabled_reason": "OPERATOR"}))
        self.assertIn("adapter disabled after this runner enabled it (OPERATOR)", r.record["ended_by"])

    def test_desk_that_stops_saying_paper_before_the_press(self):
        r, _, _ = self.before_press(lambda d: d.health.update(broker_mode="alpaca-live"))
        self.assertIn("not the paper desk before Enable", r.record["ended_by"])


class AutoRouteTests(AutoBase):
    def test_monitor_only_default_never_presses_enable_or_arm(self):
        desk = AutoDesk(self.state)
        r = self.runner(desk, minutes=2)
        self.assertEqual(r.run(), PR.EXIT_OK)
        self.assertEqual(desk.presses(), [])
        self.assertNotIn("auto", r.record)
        with self.assertRaises(PR.Refused):
            r.post("/api/alpaca/enable", {"confirm": True})
        with self.assertRaises(PR.Refused):
            r.post("/api/arm", {})

    def test_auto_client_reaches_enable_and_arm_but_never_clear_stop_play_schedule_or_disable(self):
        client = PR.DeskClient(1, auto=True)
        for method, path in (("POST", "/api/clear_stop"), ("POST", "/api/schedule"), ("POST", "/api/schedule_on"),
                             ("POST", "/api/play"), ("POST", "/api/run_to_end"), ("POST", "/api/alpaca/disable"),
                             ("POST", "/api/resume"), ("POST", "/api/close_session")):
            with self.assertRaises(PR.Refused):
                client.call(method, path, {"confirm": True})
        self.assertEqual(PR.AUTO_ALLOWED - PR.ALLOWED, {ENABLE, ARM, CONN_CHECK})

    def test_auto_runner_refuses_any_other_post(self):
        r = self.auto(AutoDesk(self.state))
        for path in ("/api/clear_stop", "/api/play", "/api/schedule", "/api/alpaca/disable"):
            with self.assertRaises(PR.Refused):
                r.post(path, {"confirm": True})

    def test_live_desk_is_refused_in_auto_before_any_press(self):
        desk = AutoDesk(self.state, mode="alpaca-live")
        self.assertEqual(self.auto(desk).run(), PR.EXIT_NOT_PAPER)
        self.assertEqual(desk.presses(), [])
        self.assertNotIn(ADVANCE, desk.routes())


class AutoLauncherTests(unittest.TestCase):
    def test_launcher_runs_auto_with_a_bounded_default_and_installs_no_schedule(self):
        cmd = Path(T.DESK, "after-approval", "Start Automated Paper Session.command").read_text()
        self.assertIn("alpaca/paper_runner.py", cmd)
        self.assertIn("--auto", cmd)
        self.assertIn("--minutes 120", cmd)
        self.assertIn("--every 30", cmd)
        for word in ("launchctl", "LaunchAgents", "crontab", "at -f", "schedule_on", "clear_stop"):
            self.assertNotIn(word, cmd)
        self.assertNotIn("live", cmd.replace("deliver", "").lower().replace("alive", ""))
        self.assertTrue(os.access(str(Path(T.DESK, "after-approval", "Start Automated Paper Session.command")), os.X_OK))

    def test_cli_auto_defaults_to_a_30_second_check(self):
        seen = {}

        class Stub(object):
            def __init__(self, minutes, every, **kw):
                seen.update(minutes=minutes, every=every, **kw)
                self.stop_flag = None

            def run(self):
                return 0
        real, PR.Runner = PR.Runner, Stub
        try:
            import signal
            old = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)
            try:
                PR.main(["--auto", "--minutes", "120"])
                self.assertEqual((seen["every"], seen["auto"], seen["minutes"]), (30, True, 120))
                PR.main([])
                self.assertEqual((seen["every"], seen["auto"]), (60, False))
            finally:
                signal.signal(signal.SIGINT, old[0])
                signal.signal(signal.SIGTERM, old[1])
        finally:
            PR.Runner = real


if __name__ == "__main__":
    unittest.main()
