"""Integration tests for the desk session runner (SIMULATED, paper only, TEST limits).

Run:  /usr/bin/python3 -IB -m unittest discover -s desk/tests -p 'test_integration.py'
"""
import os
import shutil
import sys
import tempfile
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK not in sys.path:
    sys.path.insert(0, DESK)

import session as S  # noqa: E402


def _broker_fills(runner):
    return [f for o in runner.broker._orders.values() for f in o["fills"]]


class _Tmp(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="desk-int-")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def runner(self, name, strategy="cash"):
        return S.SessionController(os.path.join(self.base, name), strategy=strategy)


class IntakeGuardTest(_Tmp):
    """A rejected bar reaches neither the fake broker nor the strategy."""

    def _case(self, case):
        r = self.runner(case)
        r.arm()
        r.advance(1)
        first = r.seen[-1]
        iid = r.mgr.submit_intent({"decision_id": "t-" + case, "kind": "entry", "side": "buy", "qty": 1,
                                   "ref_price": first["close"], "invalidation": first["close"] - 0.5,
                                   "signal_ts": first["ts_close"]})
        if case == "gap":
            r.bars.pop(1)
        elif case == "stale":
            r.bars[1] = dict(r.bars[1], exchange_ts=first["ts_close"])
        elif case == "zero":
            r.bars[1] = dict(r.bars[1], volume=0)
        elif case == "future":
            # Reviewer case: fresh exchange/receipt stamps 59 minutes before the stated close.
            early = S.iso(S.parse_ts(r.bars[1]["ts_open"]) + S._dt.timedelta(seconds=60))
            r.bars[1] = dict(r.bars[1], exchange_ts=early, delivered_ts=early, received_ts=early,
                             low=first["close"] - 4.0)
        r.advance(1)
        out = dict(r.mgr.intents[iid]), r.seen[-1], first, list(r.decisions), _broker_fills(r)
        r.close()
        return out

    def test_control_fills_after_decision_with_costs(self):
        intent, bar, first, _, fills = self._case("control")
        self.assertEqual(intent["filled_qty"], 1)
        self.assertEqual(len(fills), 1)
        f = fills[0]
        self.assertTrue(f.get("mock") and f.get("simulated"))
        self.assertEqual(f["event_ts"], bar["ts_close"])   # next bar's close, not the signal bar
        self.assertNotEqual(f["event_ts"], first["ts_close"])
        self.assertGreater(f["cost_bps"], 0)
        self.assertGreater(f["price"], bar["close"])        # a buy pays the half spread + slippage
        self.assertGreaterEqual(float(f["fee"]), 1.0)       # $1 commission minimum

    def test_bad_bars_never_fill(self):
        for case, code in (("gap", "GAP_IN_SESSION"), ("stale", "STALE_EXCHANGE_TS"), ("zero", "ZERO_VOLUME"),
                           ("future", "NOT_CLOSED_AT_RECEIPT")):
            with self.subTest(case=case):
                intent, _, _, decisions, fills = self._case(case)
                self.assertEqual(intent["filled_qty"], 0)
                self.assertEqual(fills, [])
                last = decisions[-1]
                self.assertEqual(last["reason_code"], "DATA_REJECTED_" + code)
                self.assertEqual(last["routing"]["status"], "no_order")


class ExecCapTest(_Tmp):
    """Reviewer 17:40Z/17:47Z: a gap between decision and fill must not breach a hard cap."""

    def test_one_share_gap_over_cap_is_refused_not_filled(self):
        r = self.runner("gap")
        r.arm()
        r.advance(1)
        first = r.seen[-1]
        r.bars[1] = dict(r.bars[1], open=2001.0, high=2001.0, low=2001.0, close=2001.0)
        iid = r.mgr.submit_intent({"decision_id": "gap-cap", "kind": "entry", "side": "buy", "qty": 1,
                                   "ref_price": 1995.0, "invalidation": 1994.0, "signal_ts": first["ts_close"]})
        r.advance(1)
        self.assertEqual(_broker_fills(r), [])
        self.assertEqual(r.mgr.intents[iid]["filled_qty"], 0)
        st = r.session_state()
        self.assertTrue(any(a.get("code") == "EXEC_NOTIONAL_OVER_CAP" for a in st["alarms"]))
        self.assertLessEqual(st["exposure"]["gross_including_working"], st["limits"]["gross_exposure"])
        r.close()

    def test_strategy_sized_fills_never_exceed_caps(self):
        r = S.SessionController(os.path.join(self.base, "frs"), strategy="fixed_risk_single", strategy_cfg={})
        r.set_schedule(True)
        r.run_to_end()
        per = r.limits["per_trade_notional"]
        for o in r.broker._orders.values():
            opened = sum(f["qty"] * f["price"] for f in o["fills"])
            if o.get("tag") in (None, "entry") or o["side"] == "buy":
                self.assertLessEqual(opened, per + 1e-6, o["client_id"])
        r.close()


class WeeklyReviewTest(_Tmp):
    def _full(self, name, strategy="ema", cfg=None):
        r = S.SessionController(os.path.join(self.base, name), strategy=strategy, strategy_cfg=cfg)
        r.set_schedule(True)
        r.run_to_end()
        return r

    def test_review_is_one_week_with_prior_weeks_available(self):
        r = self._full("wk")
        rv = r.review()
        self.assertEqual(len(rv["weeks"]), 18)                  # 630 hourly bars, Jun 1 - Oct 2 2026
        self.assertEqual(rv["week"], rv["default_week"])
        self.assertEqual(rv["default_week"], rv["weeks"][-1])
        self.assertEqual(sorted(rv["by_week"]), rv["weeks"])
        self.assertLessEqual(len(rv["sessions"]), 5)            # one week of local sessions, not the run
        prior = r.review(week=rv["weeks"][-2])
        self.assertEqual(prior["week"], rv["weeks"][-2])
        total = sum(len(b["round_trips"]) for b in rv["by_week"].values())
        self.assertEqual(total, rv["all_weeks_summary"]["round_trips"])
        empty = [w for w, b in rv["by_week"].items() if not b["round_trips"]]
        self.assertTrue(empty, "fixture has no-fill weeks; they must still appear")
        for w in empty:
            self.assertEqual(rv["by_week"][w]["fills"], 0)
        r.close()

    def test_fixed_qty_preset_is_used_and_labeled(self):
        r = self._full("q1", cfg={"fixed_qty": 1})
        ents = [d for d in r.decisions if d.get("action", "").startswith("enter")]
        self.assertTrue(ents)
        for d in ents:
            self.assertEqual(d["qty"], 1)
            self.assertIn("HYPOTHETICAL", d["qty_basis"])
        for o in r.broker._orders.values():
            for f in o["fills"]:
                self.assertEqual(f["qty"], 1)
        self.assertEqual(r.session_state()["sizing"]["fixed_qty"], 1)
        r.close()

    def test_refused_decisions_shown_as_refused_never_filled(self):
        r = self._full("q0", cfg={})                             # strategy sizing, refused at TEST max loss
        rv = r.review()
        refused = [x for b in rv["by_week"].values() for x in b["refused_decisions"]]
        self.assertTrue(refused)
        ids = {x["decision_id"] for x in refused}
        for x in refused:
            self.assertIn("NOT FILLED", x["label"])
        self.assertFalse(any(row["fills"] for row in r.mgr.ledger_rows() if row.get("decision_id") in ids))
        self.assertEqual(_broker_fills(r), [])
        r.close()


class RestartTest(_Tmp):
    def test_restart_keeps_broker_book(self):
        r = self.runner("run", strategy="fixed_risk_single")
        r.set_schedule(True)
        while r.i < len(r.bars) and not (r.broker._pos_qty and any(
                o["status"] == "working" for o in r.broker._orders.values())):
            r.advance(1)
        self.assertNotEqual(r.broker._pos_qty, 0, "fixture should open a mock position")
        execs = sorted(f["exec_id"] for f in _broker_fills(r))
        pos = r.broker._pos_qty
        working = sorted(c for c, o in r.broker._orders.items() if o["status"] == "working")
        r.close()
        r2 = self.runner("run", strategy="fixed_risk_single")
        self.assertTrue(r2.broker_restored)
        self.assertEqual(sorted(f["exec_id"] for f in _broker_fills(r2)), execs)
        self.assertEqual(r2.broker._pos_qty, pos)
        self.assertEqual(sorted(c for c, o in r2.broker._orders.items() if o["status"] == "working"), working)
        self.assertEqual(r2.mgr.state()["exposure"]["position_qty"], pos)
        r2.run_to_end()
        fills = _broker_fills(r2)
        self.assertTrue(fills)
        for f in fills:
            self.assertTrue(f.get("mock") and f.get("simulated"))
            self.assertGreater(f["cost_bps"], 0)
            self.assertGreaterEqual(float(f["fee"]), 1.0)
        self.assertEqual(r2.broker._pos_qty, 0)
        r2.close()

    def test_stop_survives_restart_and_blocks_rearm(self):
        r = self.runner("stop")
        r.set_schedule(True)
        r.advance(5)
        r.stop_and_close(reason="TEST")
        self.assertTrue(r.session_state()["controls"]["stopped"])
        r.close()
        r2 = self.runner("stop")
        self.assertTrue(r2.session_state()["controls"]["stopped"])
        r2.arm()
        r2.set_schedule(True)
        r2.advance(10)
        st = r2.session_state()
        self.assertFalse(st["armed"])
        self.assertTrue(st["controls"]["stopped"])
        r2.close()


class SessionConfigLockTest(_Tmp):
    """Reviewer 17:57Z: sizing, limits and strategy are fixed per state dir."""

    def test_size_change_on_same_state_is_refused(self):
        d = os.path.join(self.base, "lock")
        r = S.SessionController(d, strategy="ema", strategy_cfg={"fixed_qty": 1})
        r.set_schedule(True)
        r.advance(20)
        r.close()
        for cfg, limits in (({"fixed_qty": 4}, None), ({}, None),
                            ({"fixed_qty": 1}, dict(S.TEST_LIMITS, max_loss_per_trade=50.0))):
            with self.subTest(cfg=cfg, limits=bool(limits)):
                with self.assertRaises(S.SessionConfigChanged) as cm:
                    S.SessionController(d, strategy="ema", strategy_cfg=cfg, limits=limits)
                self.assertIn("fresh", str(cm.exception))
        audit = S._read_jsonl(os.path.join(d, "desk_audit.jsonl"))
        self.assertEqual(sum(1 for a in audit if a["kind"] == "session_config_change_refused"), 3)
        same = S.SessionController(d, strategy="ema", strategy_cfg={"fixed_qty": 1})
        self.assertEqual(same.session_config["strategy_cfg"], {"fixed_qty": 1})
        self.assertEqual(same.session_state()["session_config"]["limits"]["max_loss_per_trade"],
                         S.TEST_LIMITS["max_loss_per_trade"])
        same.close()

    def test_old_state_without_config_is_refused(self):
        d = os.path.join(self.base, "old")
        os.makedirs(d)
        with open(os.path.join(d, "progress.json"), "w") as fh:
            fh.write('{"bars_done": 5, "strategy": "ema"}')
        with self.assertRaises(S.SessionConfigChanged):
            S.SessionController(d, strategy="ema")
        self.assertFalse(os.path.exists(os.path.join(d, "broker_state.json")))


if __name__ == "__main__":
    unittest.main()
