"""alpaca/paper_runner.py: the timed, operator-started paper runner refuses anything that is not the paper
desk, refuses a second writer, never calls Enable/Arm, stops on time, reconciles, and records true fills only."""
import fcntl
import importlib.util
import os
import stat
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    spec = importlib.util.spec_from_file_location("paper_runner", os.path.join(DESK, "alpaca", "paper_runner.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PR = load()


class Clock:
    def __init__(self):
        self.t = datetime(2026, 11, 17, 14, 30, tzinfo=timezone.utc)

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += timedelta(seconds=max(s, 0.5))


class FakeDesk:
    def __init__(self, state_dir, mode="alpaca-paper", simulated=False, broker_qty=0, desk_qty=0):
        self.calls = []
        self.health = {"ok": True, "broker_mode": mode, "simulated": simulated, "controller_attached": True,
                       "state_dir": str(state_dir)}
        self.session = {"_broker_mode": mode, "_adapter_file_name": "alpaca_paper.json", "live": False,
                        "evidence_label": "ALPACA PAPER (Alpaca's simulated paper account; no real money)",
                        "badge": "ALPACA PAPER: DISARMED", "armed": False, "entry_block_reason": "NOT_ARMED",
                        "adapter": {"enabled": False, "disabled_reason": "operator has not enabled"},
                        "exposure": {"position_qty": desk_qty, "broker_position_qty": broker_qty, "working_orders": []},
                        "pnl": {"day_after_cost": 0.0}, "alarms": []}
        self.decisions = []
        self.ledger = []
        self.on_advance = None
        self.on_stop_close = None

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if (method, path) not in PR.ALLOWED:
            raise AssertionError("runner called a forbidden route %s %s" % (method, path))
        if path == "/api/health":
            return 200, self.health
        if path == "/api/session":
            return 200, self.session
        if path == "/api/decisions":
            return 200, {"items": list(self.decisions)}
        if path == "/api/ledger":
            return 200, {"items": list(self.ledger)}
        if path == "/api/advance":
            n = len(self.decisions) + 1
            self.decisions.append({"decision_id": "d%d" % n, "action": "pass", "reason_code": "VENUE_CLOSED",
                                   "bar_ts_close": "2026-11-17T14:29:00Z", "routing": {"status": "no_order"}})
            if self.on_advance:
                self.on_advance(self, n)
            return 200, {"ok": True, "controller_result": {"ok": True, "bars": n, "source": "ALPACA IEX (free)"}}
        if path == "/api/alpaca/reconcile":
            return 200, {"ok": True}
        if path == "/api/stop_close":
            if self.on_stop_close:
                self.on_stop_close(self)
            return 200, {"ok": True}
        raise AssertionError(path)

    def routes(self):
        return [(m, p) for m, p, _ in self.calls]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state-alpaca-paper"
        self.state.mkdir()
        (self.state / "limits_approved.json").write_text("{}")
        self.clock = Clock()
        self.lines = []

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self, desk, minutes=1, every=30, at_end="close", ps=lambda: [], state=None):
        return PR.Runner(minutes, every, at_end=at_end, state_dir=state or self.state, client=desk,
                         find_desk=lambda: 18858, launch=lambda: self.fail("must attach, not launch"), ps=ps,
                         now=self.clock.now, sleep=self.clock.sleep, out=self.lines.append)

    def records(self):
        folder = self.state / "runner"
        return sorted(folder.iterdir()) if folder.exists() else []


class RefusalTests(Base):
    def test_live_desk_is_refused_before_any_check(self):
        desk = FakeDesk(self.state, mode="alpaca-live")
        self.assertEqual(self.runner(desk).run(), PR.EXIT_NOT_PAPER)
        self.assertNotIn(("POST", "/api/advance"), desk.routes())
        self.assertTrue(any("REFUSED" in s and "not the paper desk" in s for s in self.lines))

    def test_mock_desk_is_refused(self):
        desk = FakeDesk(self.state, mode="alpaca-paper", simulated=True)
        self.assertEqual(self.runner(desk).run(), PR.EXIT_NOT_PAPER)
        self.assertNotIn(("POST", "/api/advance"), desk.routes())

    def test_desk_on_another_state_folder_is_refused(self):
        desk = FakeDesk(Path(self.tmp.name) / "elsewhere")
        self.assertEqual(self.runner(desk).run(), PR.EXIT_NOT_PAPER)

    def test_state_folder_must_be_the_paper_one(self):
        other = Path(self.tmp.name) / "state-alpaca-live"
        other.mkdir()
        (other / "limits_approved.json").write_text("{}")
        self.assertEqual(self.runner(FakeDesk(other), state=other).run(), PR.EXIT_NOT_PAPER)

    def test_missing_approved_limits_is_refused(self):
        (self.state / "limits_approved.json").unlink()
        desk = FakeDesk(self.state)
        self.assertEqual(self.runner(desk).run(), PR.EXIT_SETUP)
        self.assertEqual(desk.calls, [])

    def test_second_runner_is_refused(self):
        fh = open(self.state / "paper_runner.lock", "a+")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            desk = FakeDesk(self.state)
            self.assertEqual(self.runner(desk).run(), PR.EXIT_WRITER)
            self.assertEqual(desk.calls, [])
        finally:
            fh.close()

    def test_live_or_other_paper_desk_process_is_refused(self):
        for line in ("123 /usr/bin/python3 -IB /x/alpaca/live_launch.py --port 18860",
                     "124 /usr/bin/python3 -IB /x/launch.py --broker alpaca-live --state-dir /x/state-alpaca-live",
                     "125 /usr/bin/python3 -IB /x/launch.py --broker alpaca-paper --state-dir /y/state-alpaca-paper"):
            desk = FakeDesk(self.state)
            self.assertEqual(self.runner(desk, ps=lambda l=line: [l]).run(), PR.EXIT_WRITER, line)
            self.assertEqual(desk.calls, [])

    def test_same_paper_desk_process_is_attached_not_refused(self):
        line = "126 /usr/bin/python3 -IB /x/launch.py --broker alpaca-paper --transport https --state-dir %s" % self.state
        self.assertEqual(self.runner(FakeDesk(self.state), ps=lambda: [line]).run(), PR.EXIT_OK)

    def test_unreadable_process_list_is_refused(self):
        self.assertEqual(self.runner(FakeDesk(self.state), ps=lambda: None).run(), PR.EXIT_WRITER)

    def test_unexplained_position_stops_before_any_check(self):
        desk = FakeDesk(self.state, broker_qty=1, desk_qty=0)
        self.assertEqual(self.runner(desk).run(), PR.EXIT_POSITION)
        self.assertNotIn(("POST", "/api/advance"), desk.routes())
        self.assertNotIn(("POST", "/api/stop_close"), desk.routes())

    def test_unknown_broker_position_is_refused(self):
        desk = FakeDesk(self.state, broker_qty=None)
        self.assertEqual(self.runner(desk).run(), PR.EXIT_POSITION)

    def test_client_cannot_reach_enable_arm_or_schedule(self):
        client = PR.DeskClient(1)
        for method, path in (("POST", "/api/alpaca/enable"), ("POST", "/api/arm"), ("POST", "/api/clear_stop"),
                             ("POST", "/api/schedule_on"), ("POST", "/api/play"), ("POST", "/api/run_to_end")):
            with self.assertRaises(PR.Refused):
                client.call(method, path, {"confirm": True})


class TimedRunTests(Base):
    def test_flat_run_checks_on_a_timer_then_reconciles_and_stops(self):
        desk = FakeDesk(self.state)
        self.assertEqual(self.runner(desk, minutes=2, every=30).run(), PR.EXIT_OK)
        routes = desk.routes()
        self.assertEqual(routes.count(("POST", "/api/advance")), 4)       # 0s, 30s, 60s, 90s of a 2-minute run
        self.assertEqual(routes[-3:], [("GET", "/api/session"), ("GET", "/api/decisions"), ("GET", "/api/ledger")])
        last_reconcile = max(i for i, r in enumerate(routes) if r == ("POST", "/api/alpaca/reconcile"))
        self.assertGreater(last_reconcile, max(i for i, r in enumerate(routes) if r == ("POST", "/api/advance")))
        self.assertNotIn(("POST", "/api/stop_close"), routes)
        self.assertTrue(any(" | PAPER | " in s and "PLUMBING: pass VENUE_CLOSED" in s for s in self.lines))
        self.assertTrue(any(s.startswith("FLAT at end") for s in self.lines))
        recs = self.records()
        self.assertEqual(len(recs), 1)
        self.assertEqual(stat.S_IMODE(recs[0].stat().st_mode), 0o600)
        self.assertIn('"ended_by": "deadline"', recs[0].read_text())

    def test_every_is_clamped_and_minutes_bounded(self):
        desk = FakeDesk(self.state)
        self.assertEqual(self.runner(desk, minutes=1, every=1).run(), PR.EXIT_OK)
        self.assertEqual(desk.routes().count(("POST", "/api/advance")), 2)   # clamped to 30s
        self.assertEqual(self.runner(FakeDesk(self.state), minutes=PR.MAX_MINUTES + 1).run(), PR.EXIT_SETUP)
        self.assertEqual(self.runner(FakeDesk(self.state), minutes=0).run(), PR.EXIT_SETUP)

    def test_operator_stop_ends_the_run_early(self):
        desk = FakeDesk(self.state)
        r = self.runner(desk, minutes=60)

        def stop(_d, n):
            if n == 2:
                r.stop_flag = "operator stop (SIGINT)"
        desk.on_advance = stop
        self.assertEqual(r.run(), PR.EXIT_OK)
        self.assertEqual(desk.routes().count(("POST", "/api/advance")), 2)
        self.assertIn("operator stop", r.record["ended_by"])

    def test_only_broker_confirmed_new_fills_are_reported(self):
        desk = FakeDesk(self.state)
        desk.ledger = [{"side": "buy", "kind": "entry", "fills": [{"exec_id": "old", "qty": "1", "mock": False}]}]

        def fill(d, n):
            if n == 2:
                d.ledger.append({"side": "buy", "kind": "entry",
                                 "fills": [{"exec_id": "mock-1", "qty": "1", "price": 1.0, "mock": True},
                                           {"exec_id": "paper-1", "qty": "1", "price": 2.0, "mock": False}]})
        desk.on_advance = fill
        r = self.runner(desk)
        self.assertEqual(r.run(), PR.EXIT_OK)
        self.assertEqual([f["exec_id"] for f in r.record["fills_seen"]], ["paper-1"])
        self.assertTrue(any("ALPACA PAPER FILL (broker-confirmed)" in s for s in self.lines))

    def test_exposure_at_end_presses_stop_and_close_then_confirms_flat(self):
        desk = FakeDesk(self.state)

        def held(d, n):
            d.session["exposure"] = {"position_qty": 1, "broker_position_qty": 1, "working_orders": [{"id": "x"}]}
        desk.on_advance = held

        def close(d):
            d.session["exposure"] = {"position_qty": 0, "broker_position_qty": 0, "working_orders": []}
        desk.on_stop_close = close
        r = self.runner(desk)
        self.assertEqual(r.run(), PR.EXIT_OK)
        self.assertIn(("POST", "/api/stop_close", {"confirm": True}), desk.calls)
        self.assertIn("Stop & Close", r.record["at_end"])

    def test_leave_reports_exposure_without_closing(self):
        desk = FakeDesk(self.state)

        def held(d, n):
            d.session["exposure"] = {"position_qty": 1, "broker_position_qty": 1, "working_orders": []}
        desk.on_advance = held
        self.assertEqual(self.runner(desk, at_end="leave").run(), PR.EXIT_EXPOSED)
        self.assertNotIn(("POST", "/api/stop_close"), desk.routes())
        self.assertTrue(any(s.startswith("EXPOSED at end") for s in self.lines))

    def test_mismatched_exposure_at_end_is_not_closed_by_the_runner(self):
        desk = FakeDesk(self.state)

        def foreign(d, n):
            d.session["exposure"] = {"position_qty": 0, "broker_position_qty": 1, "working_orders": []}
        desk.on_advance = foreign
        r = self.runner(desk)
        self.assertEqual(r.run(), PR.EXIT_EXPOSED)
        self.assertNotIn(("POST", "/api/stop_close"), desk.routes())
        self.assertIn("does not match", r.record["at_end"])


class LabelTests(unittest.TestCase):
    def test_decisions_are_split_into_strategy_calls_and_plumbing(self):
        self.assertEqual(PR.classify({"action": "pass", "reason_code": "WARMUP_ONLY_LATE_BAR",
                                      "routing": {"status": "no_order", "why": "WARMUP_ONLY"}})[0], "PLUMBING")
        self.assertEqual(PR.classify({"action": "pass", "reason_code": "DATA_REJECTED_GAP"})[0], "PLUMBING")
        kind, text = PR.classify({"action": "enter_long", "reason_code": "ORB_BREAK",
                                  "routing": {"status": "not_routed", "why": "NOT_ARMED (decision recorded only)"}})
        self.assertEqual(kind, "STRATEGY")
        self.assertIn("not routed: NOT_ARMED", text)
        self.assertIn("routed: accepted", PR.classify({"action": "exit", "routing": {"status": "accepted"}})[1])
        self.assertEqual(PR.classify({"action": "pass", "reason_code": "NO_SETUP"})[0], "STRATEGY")
        self.assertEqual(PR.classify(None)[0], "PLUMBING")


class NoScheduleTests(unittest.TestCase):
    def test_runner_and_its_shortcut_install_no_schedule(self):
        src = Path(DESK, "alpaca", "paper_runner.py").read_text()
        cmd = Path(DESK, "after-approval", "Run Timed Paper Session.command").read_text()
        for text in (src, cmd):
            for word in ("launchctl", "LaunchAgents", "crontab", "at -f", "schedule_on"):
                self.assertNotIn(word, text)
        self.assertIn("alpaca/paper_runner.py", cmd)
        self.assertNotIn("live", cmd.replace("deliver", "").lower().replace("alive", ""))


if __name__ == "__main__":
    unittest.main()
