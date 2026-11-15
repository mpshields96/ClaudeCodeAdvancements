"""Decision lab (CONTRACT section 7): challenger, recorder, scorer and verify, offline only.

Bars here are MOCK (alpaca/mock_data.py through the mock transport) or hand-made SYNTHETIC
test bars. No network, no credentials, no broker. The local server test binds 127.0.0.1:0.
"""
import datetime as _dt
import http.client
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK not in sys.path:
    sys.path.insert(0, DESK)

import lab  # noqa: E402
from lab import record as R  # noqa: E402
from lab import score as S  # noqa: E402
from lab import verify as V  # noqa: E402
from strategies import base as B  # noqa: E402
from strategies import challenger as CH  # noqa: E402
from strategies.registry import STRATEGIES  # noqa: E402
from alpaca import DATA_LABEL_MOCK  # noqa: E402
from alpaca.mock_data import MockData  # noqa: E402
from alpaca.mock import MockAlpacaTransport, MockTrading  # noqa: E402
from alpaca.feed import IexSpyFeed  # noqa: E402
from orders.calendar import SessionCalendar  # noqa: E402

LAB_ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,200}")   # same pattern as ui/server.py
FROZEN_CFG_HASH = "979d22a2e510"                    # pinned: changing PARAMS must fail this test
SYN_SOURCE = "SYNTHETIC TEST BARS (no market data)"


def _ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def drive_mock_feed(state_dir, days=("2026-11-16", "2026-11-17", "2026-11-18")):
    """Fetch the mock IEX feed one closed slot at a time, the way a manual session would,
    and observe each new bar. Returns the bars seen."""
    cal = SessionCalendar.nyse_2026_2027()
    feed = IexSpyFeed(MockAlpacaTransport(trading=MockTrading(), data=MockData(days=days, calendar=cal)),
                      cal, minutes=60, source=DATA_LABEL_MOCK)
    slots = feed.fetch_closed_bars(after_ts_close="2026-11-13T21:00:00Z", now_utc="2026-11-18T22:00:00Z")
    rec, hist, last = lab.LabRecorder(state_dir), [], "2026-11-13T21:00:00Z"
    for s in slots:
        now = _ts(B.parse_ts(s["ts_close"]) + _dt.timedelta(seconds=2))
        for g in feed.fetch_closed_bars(after_ts_close=last, now_utc=now):
            hist.append(g)
            last = g["ts_close"]
            rec.observe(list(hist), {"ema": {"decision_id": "d-test", "action": "pass", "qty": 0}}, g)
    return hist


def trend_bars(n=14, step=0.003, start="2026-11-16T14:30:00Z"):
    """Steadily rising hourly bars (SYNTHETIC, labeled) so the challenger has a trade to make."""
    t0, px, out = B.parse_ts(start), 500.0, []
    for i in range(n):
        o = px
        c = round(o * (1.0 + step), 4)
        ts_o, ts_c = t0 + _dt.timedelta(hours=i), t0 + _dt.timedelta(hours=i + 1)
        out.append({"ts_open": _ts(ts_o), "ts_close": _ts(ts_c), "open": o, "high": round(c * 1.001, 4),
                    "low": round(o * 0.999, 4), "close": c, "volume": 1000, "symbol": "SPY",
                    "source": SYN_SOURCE, "delivered_ts": _ts(ts_c)})   # lag 0: next open attainable (v2)
        px = c
    return out


def drive_bars(state_dir, bars):
    rec, hist = lab.LabRecorder(state_dir), []
    for b in bars:
        hist.append(b)
        rec.observe(list(hist), {}, b)
    return rec


class LabBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="desk-lab-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def rows(self, name):
        return R.read_rows(os.path.join(self.dir, name))

    def rewrite(self, name, fn):
        path = os.path.join(self.dir, name)
        rows = R.read_rows(path)
        fn(rows)
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(R.canon(r) + "\n")


class TestShadowOnly(unittest.TestCase):
    def test_challenger_is_not_routable(self):
        self.assertNotIn("challenger", STRATEGIES)
        self.assertIn("challenger", lab.SHADOW)
        import session
        with self.assertRaises(ValueError):
            session.load_strategy("challenger", {})

    def test_frozen_params_are_pinned(self):
        self.assertEqual(CH.CFG_HASH, FROZEN_CFG_HASH)
        self.assertEqual(CH.FROZEN_AT, "2026-11-15")
        self.assertTrue(CH.RULE_ID.startswith("CHALLENGER-1.0.0-"))
        d = CH.decide(trend_bars(), None, {"fixed_qty": 99, "ema_len": 2, "cost_mult": 0.0})
        self.assertEqual(d["params"], CH.PARAMS, "cfg must never change frozen PARAMS")
        self.assertTrue(d["shadow"] and d["never_routed"])

    def test_session_default_lab_is_the_recorder(self):
        import alpaca_session
        d = tempfile.mkdtemp(prefix="desk-lab-test-")
        try:
            self.assertIsInstance(alpaca_session.AlpacaSessionController._default_lab(d), lab.LabRecorder)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestMockFeedEndToEnd(LabBase):
    def test_three_strategies_identical_inputs_and_verify_passes(self):
        bars = drive_mock_feed(self.dir)
        self.assertEqual(len(bars), 21)
        v = lab.view(self.dir)
        self.assertTrue(v["ok"] and v["synthetic"])
        self.assertIn("MOCK", v["data_label"])
        self.assertIn("HYPOTHETICAL", v["label"])
        self.assertEqual(v["counts"]["forecasts"], 63)
        self.assertEqual(v["counts"]["scores"], 60)      # the newest bar has no later bar yet
        for g in v["groups"]:
            self.assertEqual(sorted(g["rows"]), ["cash", "challenger", "ema"])
            fc = [R.Store(self.dir).forecast_index[r["forecast_id"]] for r in g["rows"].values()]
            self.assertEqual(len({f["input_sha256"] for f in fc}), 1, "all three decide on identical inputs")
        for f in self.rows(R.FORECASTS):
            self.assertTrue(LAB_ID_RE.fullmatch(f["forecast_id"]), f["forecast_id"])
            self.assertTrue(f["shadow"] and f["never_routed"] and f["synthetic_inputs"])
            res = V.verify(self.dir, f["forecast_id"])
            self.assertTrue(res["ok"], [c for c in res["checks"] if c["passed"] is False])

    def test_newest_forecast_is_pending_not_failed(self):
        drive_mock_feed(self.dir)
        newest = lab.view(self.dir)["groups"][0]["rows"]["challenger"]["forecast_id"]
        res = V.verify(self.dir, newest)
        self.assertTrue(res["ok"])
        self.assertIsNone(res["after"])
        self.assertEqual({c["id"]: c["passed"] for c in res["checks"]}["SCORE"], None)

    def test_scores_use_only_later_bars(self):
        drive_mock_feed(self.dir)
        st = R.Store(self.dir)
        for s in st.rows["scores"]:
            f = st.forecast_index[s["forecast_id"]]
            for b, h in zip(s["later_bars"], s["later_bar_shas"]):
                self.assertGreater(B.parse_ts(b["ts_close"]), B.parse_ts(f["ts_knowable"]))
                self.assertGreaterEqual(st.bar_index[h], f["bars_known_count"])
            self.assertEqual(s["forecast_row_hash"], f["row_hash"])

    def test_observe_is_idempotent(self):
        hist = drive_mock_feed(self.dir)
        before = {k: len(v) for k, v in R.Store(self.dir).rows.items()}
        rec = lab.LabRecorder(self.dir)
        for i in range(1, len(hist) + 1):
            rec.observe(hist[:i], {}, hist[i - 1])
        self.assertEqual({k: len(v) for k, v in R.Store(self.dir).rows.items()}, before)

    def test_passes_are_labeled_hypothetical(self):
        drive_mock_feed(self.dir)
        for s in self.rows(R.SCORES):
            self.assertIn("HYPOTHETICAL", s["label"])
            if s["kind"] == "pass/flat":
                self.assertEqual(s["net_bps"], 0.0)
                self.assertEqual(s["hypothetical"]["label"], S.PASS_LABEL)


class TestContractNames(LabBase):
    def test_lab_alias_record_and_verify_methods(self):
        self.assertIs(lab.Lab, lab.LabRecorder)
        rec, hist = lab.Lab(self.dir), []
        self.assertEqual(rec.record([], {}), [])
        for b in trend_bars(n=4):
            hist.append(b)
            rec.record(list(hist), {})
        fid = rec.view()["groups"][1]["rows"]["challenger"]["forecast_id"]
        res = rec.verify(fid)
        self.assertTrue(res["ok"], [c for c in res["checks"] if c["passed"] is False])
        self.assertEqual(res, V.verify(self.dir, fid))

    def test_every_lab_row_is_labeled_synthetic_on_mock_bars(self):
        drive_mock_feed(self.dir, days=("2026-11-16",))
        self.assertTrue(all(r["synthetic"] for r in self.rows(R.BARS)))
        self.assertTrue(all(r["synthetic"] for r in self.rows(R.INPUTS)))
        self.assertTrue(all(r["synthetic_inputs"] for r in self.rows(R.FORECASTS)))
        scores = self.rows(R.SCORES)
        self.assertTrue(scores and all(r["synthetic"] for r in scores))
        fid = scores[-1]["forecast_id"]
        self.assertTrue(V.verify(self.dir, fid)["ok"])

    def test_every_score_row_labels_the_cost_qty(self):
        drive_mock_feed(self.dir, days=("2026-11-16",))
        scores = self.rows(R.SCORES)
        self.assertTrue(scores)
        for r in scores:
            self.assertIn("cost_qty", r)
            self.assertTrue(r["cost_qty_source"])
            self.assertIsNone(r["cost_reference_shares"])
            if r["kind"] == "trade":
                self.assertEqual(r["cost_qty"], r["qty"])
            elif r.get("hypothetical"):
                self.assertEqual(r["cost_qty"], r["hypothetical"]["qty"])

    def test_historical_study_slot_is_a_disabled_placeholder(self):
        with open(os.path.join(DESK, "ui", "lab.html"), encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn("Historical SPY study", page)
        m = re.search(r'<button id="hist-link"[^>]*>', page)
        self.assertTrue(m and " disabled" in m.group(0))
        self.assertNotIn("hist-link\").href", page)
        self.assertIn("not yet a valid comparison", page)
        self.assertNotIn("t.sum_net_bps", page)


class TestReportLabSection(LabBase):
    def write_review(self):
        review = {"weeks": ["2026-W47"], "default_week": "2026-W47", "by_week": {"2026-W47": {"comparison": []}}}
        with open(os.path.join(self.dir, "review.json"), "w", encoding="utf-8") as fh:
            json.dump(review, fh)

    def test_section_absent_without_lab_files(self):
        import report as RP
        self.write_review()
        self.assertEqual(RP.lab_section(self.dir), "")
        _, page = RP.build_html(self.dir)
        self.assertNotIn("Decision lab", page)

    def test_section_shows_hypothetical_totals(self):
        import report as RP
        self.write_review()
        drive_bars(self.dir, trend_bars(n=6))
        _, page = RP.build_html(self.dir)
        self.assertIn("Decision lab (shadow)", page)
        self.assertIn("HYPOTHETICAL", page)
        self.assertIn("not yet a valid comparison", page)
        self.assertNotIn("Sum net bps", page)
        self.assertIn(CH.RULE_ID, page)
        self.assertIn("ASSUMED", page)
        for name in ("cash", "challenger", "ema"):
            self.assertIn("<td>%s</td>" % name, page)


class TestChallengerTrade(LabBase):
    def test_trade_is_scored_net_of_costs_and_verifies(self):
        drive_bars(self.dir, trend_bars())
        st = R.Store(self.dir)
        trades = [s for s in st.rows["scores"] if s["strategy"] == "challenger" and s["kind"] == "trade"]
        self.assertTrue(trades, "a steady synthetic trend should give the challenger a trade")
        for s in trades:
            self.assertEqual(s["exposure"], 1)
            self.assertLess(s["net_bps"], s["gross_bps"], "costs are taken out")
            self.assertLess(s["net_bps_2x"], s["net_bps"], "doubled friction costs more")
            self.assertIn("vs_ema_net_bps", s)
            self.assertEqual(s["vs_cash_net_bps"], s["net_bps"])
            res = V.verify(self.dir, s["forecast_id"])
            self.assertTrue(res["ok"], [c for c in res["checks"] if c["passed"] is False])
        v = lab.view(self.dir)
        self.assertGreaterEqual(v["totals"]["challenger"]["trades"], 1)
        self.assertEqual(v["totals"]["cash"]["sum_net_bps"], 0.0)

    def test_short_side(self):
        drive_bars(self.dir, trend_bars(step=-0.003))
        acts = {f["action"] for f in self.rows(R.FORECASTS) if f["strategy"] == "challenger"}
        self.assertIn("enter_short", acts)


def minute_bars(n=14, lag_s=2, drop=()):
    """trend_bars knowable lag_s after each close, with SYNTHETIC genuine-style minute opens."""
    bars = trend_bars(n=n)
    for b in bars:
        b["delivered_ts"] = _ts(B.parse_ts(b["ts_close"]) + _dt.timedelta(seconds=lag_s))
        t0 = B.parse_ts(b["ts_open"])
        b["minute_opens"] = [[_ts(t0 + _dt.timedelta(minutes=k)), round(b["open"] * (1 + 0.0001 * k), 4)]
                             for k in range(16) if k not in drop]
    return bars


class TestMinuteProxyEntry(LabBase):
    """v3: a genuine later minute open replaces an unattainable next-bar open (Codex 23:31Z)."""

    def _scores(self, **kw):
        drive_bars(self.dir, minute_bars(**kw))
        return R.Store(self.dir).rows["scores"]

    def _entry_minute(self, s):
        return (B.parse_ts(s["entry"]["ts"]) - B.parse_ts(s["later_bars"][0]["ts_open"])).total_seconds() / 60

    def test_two_second_lag_scores_from_next_minute_open_and_verifies(self):
        scores = self._scores()
        self.assertTrue(scores)
        for s in scores:
            self.assertEqual(s["score_version"], 3)
            self.assertTrue(s["eligible"], s.get("ineligible_reason"))
            self.assertEqual(s["entry"]["basis"], S.PROXY_BASIS)
            self.assertEqual(self._entry_minute(s), 1.0)
            self.assertEqual(s["entry"]["raw"], s["later_bars"][0]["minute_opens"][1][1])
            self.assertEqual(s["entry"]["bar_open_raw"], s["later_bars"][0]["open"])
            self.assertIn("2 s before", s["entry"]["rationale"])
            res = V.verify(self.dir, s["forecast_id"])
            self.assertTrue(res["ok"], [c for c in res["checks"] if c["passed"] is False])
        ch = [s for s in scores if s["strategy"] == "challenger"]
        self.assertTrue(any(isinstance(s["vs_ema_net_bps"], float) for s in ch))

    def test_never_an_earlier_minute_and_missing_minutes_not_filled(self):
        for s in self._scores(lag_s=90, drop=(2,)):
            self.assertEqual(self._entry_minute(s), 3.0)     # 1 is earlier than knowable, 2 is missing

    def test_no_stored_minute_late_enough_stays_ineligible(self):
        for s in self._scores(lag_s=1200):                   # past the 16 stored minutes
            self.assertFalse(s["eligible"])
            self.assertIn("no genuine later minute", s["ineligible_reason"])

    def test_old_bars_without_minute_marks_stay_strict_and_v2_rule_is_kept(self):
        bars = trend_bars(n=4)
        for b in bars:
            b["delivered_ts"] = _ts(B.parse_ts(b["ts_close"]) + _dt.timedelta(seconds=2))
        st = R.Store(drive_bars(self.dir, bars).state_dir)
        f = [x for x in st.rows["forecasts"] if x["strategy"] == "challenger"][0]
        later, _ = S.later_bars(st, f)
        self.assertEqual(S.compute_core(f, later)["kind"], "ineligible")
        mb = minute_bars(n=4)
        later_m = [dict(b, minute_opens=m["minute_opens"]) for b, m in zip(later, mb[1:])]
        self.assertEqual(S.compute_core(f, later_m, version=2)["kind"], "ineligible")
        self.assertNotEqual(S.compute_core(f, later_m, version=3)["kind"], "ineligible")


class TestIneligibleWindows(LabBase):
    """v2 scoring: unattainable entry, gap/session cross and partial bars earn no P&L (Codex 23:25Z)."""

    def _drive(self):
        bars = trend_bars(n=16)
        bars[5]["delivered_ts"] = _ts(B.parse_ts(bars[5]["ts_close"]) + _dt.timedelta(seconds=600))  # late
        bars[12]["partial"] = True                                                                     # partial
        del bars[9]                                                                                    # gap
        drive_bars(self.dir, bars)
        return R.Store(self.dir).rows["scores"]

    def test_three_cases_are_ineligible_with_no_numbers_and_verify(self):
        scores = self._drive()
        bad = [s for s in scores if s.get("eligible") is False]
        reasons = " | ".join(sorted({s["ineligible_reason"] for s in bad}))
        for frag in ("not attainable", "not contiguous", "partial"):
            self.assertIn(frag, reasons)
        for s in bad:
            self.assertEqual(s["kind"], "ineligible")
            self.assertEqual(s["score_version"], S.SCORE_VERSION)
            for k in ("gross_bps", "net_bps", "net_bps_2x", "net_usd", "net_usd_2x"):
                self.assertIsNone(s[k], k)
            if s["strategy"] == "challenger":
                self.assertIsNone(s["vs_ema_net_bps"])
                self.assertIsNone(s["vs_cash_net_bps"])
                self.assertIn("disabled", s["comparison_status"])
            res = V.verify(self.dir, s["forecast_id"])
            self.assertTrue(res["ok"], [c for c in res["checks"] if c["passed"] is False])
        good = [s for s in scores if s.get("eligible") is True]
        self.assertTrue(good and all(isinstance(s["net_bps"], float) for s in good))

    def test_view_counts_ineligible_and_sums_only_eligible(self):
        self._drive()
        t = lab.view(self.dir)["totals"]["challenger"]
        self.assertGreaterEqual(t["ineligible"], 3)
        self.assertTrue(all(r.get("eligible") is not False or r.get("net_bps") is None
                            for g in lab.view(self.dir)["groups"] for r in g["rows"].values()))

    def test_any_positive_lag_is_ineligible_zero_lag_is_scored(self):
        st = R.Store(drive_bars(self.dir, trend_bars(n=4)).state_dir)
        f = [x for x in st.rows["forecasts"] if x["strategy"] == "challenger"][0]
        nxt = [b for b in trend_bars(n=4) if b["ts_open"] == f["bar_ts_close"]]
        for lag, ok in ((0, True), (2, False), (59, False), (60, False), (61, False)):
            g = dict(f, ts_knowable=_ts(B.parse_ts(f["bar_ts_close"]) + _dt.timedelta(seconds=lag)))
            core = S.compute_core(g, nxt)
            self.assertEqual(core["eligible"], ok, lag)
            self.assertEqual(core["net_bps"] is None, not ok, lag)

    def test_legacy_v1_rule_still_recomputes_for_old_rows(self):
        self._drive()
        st = R.Store(self.dir)
        s = [x for x in st.rows["scores"] if x.get("eligible") is False][0]
        f = st.forecast_index[s["forecast_id"]]
        v1 = S.compute_core(f, s["later_bars"], version=1)
        self.assertEqual(set(v1), set(S.CORE_KEYS_V1))
        self.assertIsInstance(v1["net_bps"], float)   # the old rule scored it; v2 does not


class TestTamperEvidence(LabBase):
    def _scored_challenger(self):
        st = R.Store(self.dir)
        return [s["forecast_id"] for s in st.rows["scores"] if s["strategy"] == "challenger"]

    def test_edited_forecast_breaks_chain(self):
        drive_bars(self.dir, trend_bars())
        fid = self._scored_challenger()[0]

        def edit(rows):
            for r in rows:
                if r["forecast_id"] == fid:
                    r["action"] = "enter_short" if r["action"] != "enter_short" else "enter_long"
        self.rewrite(R.FORECASTS, edit)
        res = V.verify(self.dir, fid)
        self.assertFalse(res["ok"])
        self.assertFalse({c["id"]: c["passed"] for c in res["checks"]}["CHAIN"])

    def test_edited_bar_breaks_input_hash(self):
        drive_bars(self.dir, trend_bars())
        fid = self._scored_challenger()[-1]

        def edit(rows):
            rows[0]["bar"]["close"] = rows[0]["bar"]["close"] + 1.0
        self.rewrite(R.BARS, edit)
        got = {c["id"]: c["passed"] for c in V.verify(self.dir, fid)["checks"]}
        self.assertFalse(got["INPUT_HASH"])
        self.assertFalse(got["BAR_STORE_CHAIN"])

    def test_edited_score_breaks_score_check(self):
        drive_bars(self.dir, trend_bars())
        fid = self._scored_challenger()[-1]

        def edit(rows):
            for r in rows:
                if r["forecast_id"] == fid:
                    r["net_bps"] = 999.0
        self.rewrite(R.SCORES, edit)
        got = {c["id"]: c["passed"] for c in V.verify(self.dir, fid)["checks"]}
        self.assertFalse(got["SCORE_CHAIN"])
        self.assertFalse(got["SCORE"])

    def test_unknown_id(self):
        res = V.verify(self.dir, "fc-challenger-0000000000000000")
        self.assertFalse(res["ok"])
        self.assertEqual(res["checks"][0]["id"], "FOUND")


class _LabController(object):
    def __init__(self, d):
        self.d = d

    def lab_view(self):
        return lab.view(self.d)

    def lab_verify(self, forecast_id):
        return V.verify(self.d, forecast_id)


class TestLabRoutesLocal(LabBase):
    """GET /api/lab, /api/lab/verify and /lab.html on a loopback server with port 0."""

    def setUp(self):
        LabBase.setUp(self)
        from ui import server
        drive_bars(self.dir, trend_bars())
        self.srv = server.make_server(self.dir, host="127.0.0.1", port=0, controller=_LabController(self.dir))
        self.th = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.th.start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        LabBase.tearDown(self)

    def get(self, path):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=10)
        try:
            c.request("GET", path)
            r = c.getresponse()
            return r.status, r.read()
        finally:
            c.close()

    def test_view_verify_and_page(self):
        code, body = self.get("/api/lab")
        self.assertEqual(code, 200)
        v = json.loads(body)
        fid = v["groups"][1]["rows"]["challenger"]["forecast_id"]
        code, body = self.get("/api/lab/verify?id=" + fid)
        self.assertEqual(code, 200)
        res = json.loads(body)
        self.assertTrue(res["ok"])
        self.assertIsNotNone(res["before"])
        self.assertIsNotNone(res["after"])
        code, _ = self.get("/api/lab/verify?id=bad%20id%3Cx%3E")
        self.assertEqual(code, 400)
        code, page = self.get("/lab.html")
        self.assertEqual(code, 200)
        self.assertIn(b"/api/lab/verify", page)
        self.assertIn(b"HYPOTHETICAL", page)


if __name__ == "__main__":
    unittest.main()
