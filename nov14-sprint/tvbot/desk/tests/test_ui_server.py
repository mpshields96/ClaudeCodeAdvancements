"""Tests for the desk UI server (worker B). Stdlib only, offline, loopback.

Run:
  /usr/bin/python3 -I -m unittest discover -s <desk>/tests -p 'test_ui*'
"""
import http.client
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest

DESK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK_DIR not in sys.path:
    sys.path.insert(0, DESK_DIR)

from ui import server  # noqa: E402

SAMPLE = os.path.join(DESK_DIR, "ui", "sample_state")


class FakeManager(object):
    def __init__(self):
        self.calls = []

    def pause(self):
        self.calls.append("pause")
        return {"paused": True, "simulated": True}

    def stop_and_close(self):
        self.calls.append("stop_and_close")
        return {"stopped": True, "flat_confirmed": False, "simulated": True}


class _Base(unittest.TestCase):
    manager = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ui_test_")
        cls.state = os.path.join(cls.tmp, "state")
        shutil.copytree(SAMPLE, cls.state)
        cls.srv = server.make_server(cls.state, host="127.0.0.1", port=0, manager=cls.manager)
        cls.port = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.th.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def req(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": "127.0.0.1:%d" % self.port}
        if headers:
            h.update(headers)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            h.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=data, headers=h)
        r = conn.getresponse()
        raw = r.read()
        hdrs = dict((k.lower(), v) for k, v in r.getheaders())
        conn.close()
        return r.status, hdrs, raw

    def get_json(self, path):
        st, h, raw = self.req("GET", path)
        self.assertEqual(st, 200, raw[:300])
        self.assertIn("application/json", h.get("content-type", ""))
        return json.loads(raw.decode("utf-8"))

    def control_lines(self):
        p = os.path.join(self.state, "control_requests.jsonl")
        if not os.path.exists(p):
            return []
        with open(p, "r", encoding="utf-8") as f:
            return [json.loads(x) for x in f if x.strip()]


class TestGetEndpoints(_Base):
    def test_index_is_self_contained(self):
        st, h, raw = self.req("GET", "/")
        self.assertEqual(st, 200)
        self.assertIn("text/html", h.get("content-type", ""))
        html = raw.decode("utf-8")
        self.assertIn("SIMULATED", html)
        self.assertIn("MOCK FILL", html)
        self.assertIn("tradingview.com/chart/?symbol=", html)
        # no external scripts, styles or iframes: TradingView is a link only
        self.assertNotIn("<iframe", html.lower())
        self.assertNotIn('src="http', html)
        self.assertNotIn("<link", html.lower())
        csp = h.get("content-security-policy", "")
        self.assertIn("default-src 'none'", csp)
        self.assertIn("connect-src 'self'", csp)

    def test_session(self):
        s = self.get_json("/api/session")
        for k in ("mode", "session_id", "expires_utc", "symbol", "controls", "exposure",
                  "protective_orders", "pnl", "limits", "broker"):
            self.assertIn(k, s)
        self.assertTrue(s["simulated"])
        self.assertTrue(s["limits"]["label"].startswith("TEST VALUES"))
        for k in ("realized", "unrealized", "fees", "after_cost"):
            self.assertIn(k, s["pnl"])
        self.assertIn("_meta", s)
        self.assertFalse(s["_manager_attached"])

    def test_bars(self):
        b = self.get_json("/api/bars")
        self.assertGreater(b["count"], 10)
        self.assertEqual(b["count"], len(b["items"]))
        bar = b["items"][0]
        for k in ("ts_open", "ts_close", "open", "high", "low", "close", "volume", "seq"):
            self.assertIn(k, bar)
        ts = [x["ts_close"] for x in b["items"]]
        self.assertEqual(ts, sorted(ts))
        self.assertIn("never TradingView", b["source"])

    def test_decisions_hide_outcome_until_reveal(self):
        d = self.get_json("/api/decisions")
        self.assertTrue(d["outcomes_hidden"])
        self.assertGreater(d["marker_count"], 0)
        with_outcome = [x for x in d["items"] if x.get("has_outcome")]
        self.assertTrue(with_outcome)
        for x in d["items"]:
            self.assertNotIn("outcome", x)
        did = with_outcome[0]["decision_id"]
        r = self.get_json("/api/decisions?reveal=" + did)
        self.assertEqual(r["item"]["decision_id"], did)
        self.assertIn("outcome", r["item"])
        st, _, _ = self.req("GET", "/api/decisions?reveal=NOPE-404")
        self.assertEqual(st, 404)

    def test_ledger_and_audit(self):
        l = self.get_json("/api/ledger")
        self.assertGreater(l["count"], 0)
        for row in l["items"]:
            self.assertTrue(row.get("simulated"))
            for k in ("trade_id", "decision_id", "fills", "fees", "pnl_net"):
                self.assertIn(k, row)
        a = self.get_json("/api/audit")
        kinds = set(x.get("kind") for x in a["items"])
        for k in ("knew", "requested", "acked", "filled"):
            self.assertIn(k, kinds)

    def test_review(self):
        r = self.get_json("/api/review")
        self.assertTrue(r["simulated"])
        self.assertFalse(r["no_fills"])
        self.assertIsNotNone(r["best_trade"])
        self.assertIsNotNone(r["worst_trade"])
        self.assertLessEqual(r["worst_trade"]["pnl_net"], r["best_trade"]["pnl_net"])
        bp = r["best_pass"]
        self.assertIsNotNone(bp)
        self.assertTrue(bp["hypothetical"])
        self.assertFalse(bp["counted_in_pnl"])
        self.assertIn("rule", r["best_pass_rule"].lower() + " rule")
        names = [x.get("name") or x.get("strategy") for x in r["comparison"]["rows"]]
        self.assertTrue(any("cash" in str(n).lower() for n in names), names)
        checks = dict((c["name"], c["status"]) for c in r["operating_audit"]["checks"])
        self.assertTrue(checks)

    def test_unknown_route_and_method(self):
        st, _, _ = self.req("GET", "/api/nope")
        self.assertEqual(st, 404)
        st, _, _ = self.req("DELETE", "/api/session")
        self.assertEqual(st, 405)

    def test_rejects_foreign_host_header(self):
        st, _, _ = self.req("GET", "/api/session", headers={"Host": "evil.example:8765"})
        self.assertEqual(st, 403)


class TestControlsNoManager(_Base):
    def test_pause_writes_control_request(self):
        before = len(self.control_lines())
        st, _, raw = self.req("POST", "/api/pause", body={})
        self.assertEqual(st, 200, raw)
        j = json.loads(raw.decode("utf-8"))
        self.assertTrue(j["ok"])
        self.assertEqual(j["request"], "pause")
        self.assertFalse(j["manager_called"])
        self.assertTrue(j["simulated"])
        lines = self.control_lines()
        self.assertGreater(len(lines), before)
        first = [x for x in lines if x.get("request_id") == j["request_id"]][0]
        self.assertEqual(first["request"], "pause")
        self.assertEqual(first["status"], "requested")
        self.assertEqual(first["source"], "ui")
        self.assertTrue(first["simulated"])

    def test_stop_close_needs_confirm(self):
        before = len(self.control_lines())
        st, _, _ = self.req("POST", "/api/stop_close", body={})
        self.assertEqual(st, 400)
        self.assertEqual(len(self.control_lines()), before)
        st, _, raw = self.req("POST", "/api/stop_close", body={"confirm": True})
        self.assertEqual(st, 200, raw)
        j = json.loads(raw.decode("utf-8"))
        self.assertEqual(j["request"], "stop_close")

    def test_cross_origin_post_refused(self):
        before = len(self.control_lines())
        st, _, _ = self.req("POST", "/api/pause", body={}, headers={"Origin": "https://evil.example"})
        self.assertEqual(st, 403)
        # a "simple" cross-site form/text POST is refused: controls must be JSON
        st, _, _ = self.req("POST", "/api/pause", body=None,
                            headers={"Content-Type": "text/plain", "Content-Length": "0"})
        self.assertEqual(st, 415)
        st, _, _ = self.req("POST", "/api/pause", body=None,
                            headers={"Content-Type": "application/x-www-form-urlencoded",
                                     "Content-Length": "0"})
        self.assertEqual(st, 415)
        self.assertEqual(len(self.control_lines()), before)

    def test_truncated_body_not_recorded(self):
        before = len(self.control_lines())
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("POST", "/api/pause", skip_host=True)
        conn.putheader("Host", "127.0.0.1:%d" % self.port)
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", "40")
        conn.endheaders()
        conn.send(b'{"a":')
        conn.sock.shutdown(socket.SHUT_WR)
        r = conn.getresponse()
        r.read()
        conn.close()
        self.assertEqual(r.status, 400)
        self.assertEqual(len(self.control_lines()), before)


class TestControlsWithManager(_Base):
    manager = FakeManager()

    def test_pause_and_stop_call_manager(self):
        st, _, raw = self.req("POST", "/api/pause", body={})
        self.assertEqual(st, 200, raw)
        j = json.loads(raw.decode("utf-8"))
        self.assertTrue(j["manager_called"])
        st, _, raw = self.req("POST", "/api/stop_close", body={"confirm": True})
        self.assertEqual(st, 200, raw)
        self.assertEqual(self.manager.calls, ["pause", "stop_and_close"])
        statuses = [x["status"] for x in self.control_lines()]
        self.assertIn("requested", statuses)
        self.assertIn("controller_ok", statuses)
        s = self.get_json("/api/session")
        self.assertTrue(s["_manager_attached"])


class TestEmptyStateDir(unittest.TestCase):
    def test_missing_files_do_not_crash(self):
        tmp = tempfile.mkdtemp(prefix="ui_empty_")
        srv = server.make_server(tmp, host="127.0.0.1", port=0)
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            port = srv.server_address[1]
            for path in ("/api/session", "/api/bars", "/api/decisions", "/api/ledger",
                         "/api/audit", "/api/review"):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", path)
                r = conn.getresponse()
                body = json.loads(r.read().decode("utf-8"))
                conn.close()
                self.assertEqual(r.status, 200, path)
                self.assertIn("_meta", body)
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/api/review")
            rv = json.loads(conn.getresponse().read().decode("utf-8"))
            conn.close()
            self.assertTrue(rv["no_fills"])
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(tmp, ignore_errors=True)

    def test_open_only_trade_is_not_called_no_fills(self):
        tmp = tempfile.mkdtemp(prefix="ui_open_")
        try:
            with open(os.path.join(tmp, "ledger.jsonl"), "w") as f:
                f.write(json.dumps({"trade_id": "T9", "decision_id": "D9", "side": "long", "qty": 5,
                                    "fills": [{"qty": 5, "price": 100.0, "mock": True, "simulated": True}],
                                    "fees": 1.0, "pnl_net": None, "simulated": True}) + "\n")
            rv = server.build_review(tmp)
            self.assertFalse(rv["no_fills"])
            self.assertIsNone(rv["best_trade"])
            self.assertIn("still open", rv["trade_note"])
            self.assertIn("open trade", rv["comparison"]["rows"][0]["source"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_non_loopback_host_refused(self):
        with self.assertRaises(ValueError):
            server.make_server(tempfile.gettempdir(), host="0.0.0.0", port=0)


# --------------------------------------------------------------------------
# CONTRACT v2: nine control routes, envelope, fallbacks, review, CSP
# --------------------------------------------------------------------------

class FakeController(object):
    """Shaped like session.SessionController: methods take v2 arguments and
    return {"ok": ...}. Records every call with its arguments."""

    def __init__(self):
        self.calls = []
        self.state_dir = None  # set by the test class so calls can check the request line

    def _rec(self, name, **kw):
        lines = 0
        if self.state_dir:
            p = os.path.join(self.state_dir, "control_requests.jsonl")
            if os.path.exists(p):
                with open(p) as f:
                    lines = sum(1 for x in f if x.strip())
        self.calls.append((name, kw, lines))
        return {"ok": True, "simulated": True}

    def arm(self):
        return self._rec("arm")

    def advance(self, n=1):
        return self._rec("advance", n=n)

    def play(self, bars_per_sec=4.0):
        return self._rec("play", bars_per_sec=bars_per_sec)

    def stop_play(self):
        return self._rec("stop_play")

    def pause(self):
        return self._rec("pause")

    def resume(self):
        return self._rec("resume")

    def stop_and_close(self):
        return self._rec("stop_and_close")

    def clear_stop(self, confirm=False):
        if confirm is not True:
            return {"ok": False, "reason": "CONFIRM_REQUIRED"}
        return self._rec("clear_stop", confirm=confirm)

    def set_schedule(self, enabled=False):
        return self._rec("set_schedule", enabled=enabled)

    def close_session(self):
        self.calls.append(("close_session", {}, None))
        return {"ok": False, "reason": "NOT_FLAT", "simulated": True}


class NoArgControls(object):
    """Shaped like launch.py DeskControls: no-argument methods only."""

    def __init__(self):
        self.calls = []

    def advance(self):
        self.calls.append("advance")
        return {"ok": True}

    def schedule_on(self):
        self.calls.append("schedule_on")
        return {"ok": True}

    def schedule_off(self):
        self.calls.append("schedule_off")
        return {"ok": True}

    def pause_play(self):
        self.calls.append("pause_play")
        return {"ok": True}


class TestV2Controller(_Base):
    manager = FakeController()

    @classmethod
    def setUpClass(cls):
        super(TestV2Controller, cls).setUpClass()
        cls.manager.state_dir = cls.state

    def post(self, path, body=None):
        st, _, raw = self.req("POST", path, body if body is not None else {})
        return st, json.loads(raw.decode("utf-8"))

    def test_all_nine_routes_dispatch_with_arguments(self):
        self.manager.calls[:] = []
        plan = [("/api/arm", {}, ("arm", {})),
                ("/api/advance", {"n": 3}, ("advance", {"n": 3})),
                ("/api/play", {"bars_per_sec": 8}, ("play", {"bars_per_sec": 8.0})),
                ("/api/pause", {}, ("pause", {})),
                ("/api/resume", {}, ("resume", {})),
                ("/api/stop_close", {"confirm": True}, ("stop_and_close", {})),
                ("/api/clear_stop", {"confirm": True}, ("clear_stop", {"confirm": True})),
                ("/api/schedule", {"enabled": True}, ("set_schedule", {"enabled": True}))]
        for path, body, want in plan:
            st, j = self.post(path, body)
            self.assertEqual(st, 200, (path, j))
            self.assertTrue(j["ok"], (path, j))
            self.assertTrue(j["controller_called"], path)
            self.assertIn("session", j)
            self.assertIsNone(j.get("error"))
            self.assertTrue(j["simulated"])
        self.assertEqual([(c[0], c[1]) for c in self.manager.calls], [w for _, _, w in plan])

    def test_request_line_is_written_before_the_call(self):
        self.manager.calls[:] = []
        before = len(self.control_lines())
        self.post("/api/pause")
        name, _, lines_at_call = self.manager.calls[-1]
        self.assertEqual(name, "pause")
        self.assertEqual(lines_at_call, before + 1)
        req_row = self.control_lines()[before]
        self.assertEqual(req_row["action"], "pause")
        self.assertIn("ts", req_row)
        self.assertIn("body", req_row)

    def test_play_zero_means_stop_playing(self):
        self.manager.calls[:] = []
        st, j = self.post("/api/play", {"bars_per_sec": 0})
        self.assertEqual(st, 200)
        self.assertEqual(self.manager.calls[-1][0], "stop_play")

    def test_advance_and_play_are_capped(self):
        self.manager.calls[:] = []
        self.post("/api/advance", {"n": 100000})
        self.post("/api/play", {"bars_per_sec": 1e9})
        self.assertEqual(self.manager.calls[0][1], {"n": server.MAX_ADVANCE})
        self.assertEqual(self.manager.calls[1][1], {"bars_per_sec": server.MAX_PLAY_RATE})

    def test_clear_stop_without_confirm_is_refused_and_not_called(self):
        self.manager.calls[:] = []
        st, j = self.post("/api/clear_stop", {})
        self.assertEqual(st, 400)
        self.assertFalse(j["ok"])
        self.assertEqual(self.manager.calls, [])

    def test_controller_refusal_is_ok_false_with_reason(self):
        st, j = self.post("/api/close_session")
        self.assertEqual(st, 200)
        self.assertFalse(j["ok"])
        self.assertTrue(j["controller_called"])
        self.assertEqual(j["error"], "NOT_FLAT")
        last = self.control_lines()[-1]
        self.assertEqual(last["status"], "controller_refused")

    def test_bad_advance_body_is_400(self):
        st, j = self.post("/api/advance", {"n": "lots"})
        self.assertEqual(st, 400)
        self.assertFalse(j["ok"])


class TestNoArgFallbacks(_Base):
    manager = NoArgControls()

    def post(self, path, body=None):
        st, _, raw = self.req("POST", path, body if body is not None else {})
        return st, json.loads(raw.decode("utf-8"))

    def test_no_arg_advance_called_n_times(self):
        self.manager.calls[:] = []
        st, j = self.post("/api/advance", {"n": 4})
        self.assertTrue(j["ok"], j)
        self.assertEqual(self.manager.calls, ["advance"] * 4)

    def test_schedule_falls_back_to_on_off(self):
        self.manager.calls[:] = []
        self.post("/api/schedule", {"enabled": True})
        self.post("/api/schedule", {"enabled": False})
        self.assertEqual(self.manager.calls, ["schedule_on", "schedule_off"])

    def test_play_zero_falls_back_to_pause_play(self):
        self.manager.calls[:] = []
        self.post("/api/play", {"bars_per_sec": 0})
        self.assertEqual(self.manager.calls, ["pause_play"])

    def test_missing_method_is_reported_not_crashed(self):
        st, j = self.post("/api/arm")
        self.assertEqual(st, 200)
        self.assertFalse(j["ok"])
        self.assertIn("arm", j["error"])


class TestV2ReadSide(_Base):
    def test_bars_follow_the_replay_clock(self):
        p = os.path.join(self.state, "session.json")
        with open(p) as f:
            sess = json.load(f)
        bars = [b for b in self.get_json("/api/bars")["items"]]
        self.assertGreater(len(bars), 12)
        clock = bars[10]["ts_close"]
        sess["replay_clock_utc"] = clock
        with open(p, "w") as f:
            json.dump(sess, f)
        got = self.get_json("/api/bars")
        self.assertEqual(got["count"], 11)
        self.assertTrue(all(b["ts_close"] <= clock for b in got["items"]))
        self.assertEqual(got["_meta"]["bars_in_file"], len(bars))

    def test_best_pass_is_most_failed_checks_and_hidden_until_reveal(self):
        rv = self.get_json("/api/review")
        bp = rv["best_pass"]
        self.assertEqual(bp["reason_code"], "trend_filter_down")
        self.assertEqual(bp["failed_refusal_checks"], 2)
        self.assertEqual(sum(1 for x in bp["refusal_checks"] if x.get("passed") is False), 2)
        self.assertFalse(bp["counted_in_pnl"])
        self.assertTrue(bp["hypothetical"])
        self.assertNotIn("hypothetical_after_reveal", bp)
        self.assertTrue(bp["hypothetical_hidden"])
        shown = self.get_json("/api/review?reveal_pass=1")["best_pass"]
        self.assertIn("hypothetical_after_reveal", shown)
        self.assertFalse(shown["counted_in_pnl"])

    def test_csp_allows_only_self_and_tradingview_embed(self):
        st, h, _ = self.req("GET", "/")
        csp = h.get("content-security-policy", "")
        self.assertIn("connect-src 'self'", csp)
        self.assertIn("https://s3.tradingview.com", csp)
        self.assertIn("frame-src", csp)
        self.assertIn("frame-ancestors 'none'", csp)

    def test_page_has_v2_flow_and_badges(self):
        st, _, raw = self.req("GET", "/")
        html = raw.decode("utf-8")
        for needle in ("EXTERNAL BROKER", "TEST VALUES", "Stop &amp; Close", "Review",
                       "operator view only", "Open my TradingView chart"):
            self.assertIn(needle, html, needle)



class TestWeeklyReviewAndReports(_Base):
    """review.json weeks/by_week, reports route, reveal join, signal time."""

    @classmethod
    def setUpClass(cls):
        super(TestWeeklyReviewAndReports, cls).setUpClass()
        dp = os.path.join(cls.state, "decisions.jsonl")
        with open(dp, "r", encoding="utf-8") as f:
            rows = [json.loads(x) for x in f if x.strip()]
        rows[0].pop("outcome", None)
        cls.dec = rows[0]
        with open(dp, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        did = cls.dec["decision_id"]
        trip = {"entry_decision_id": did, "entry_ts": "2026-09-28T18:30:02Z", "exit_kind": "exit",
                "exit_ts": "2026-09-28T21:30:02Z", "fees": 2.0, "gross_pnl": 0.67, "net_pnl": -1.33,
                "side": "buy", "simulated": True,
                "fills": [{"fee": 1.0, "intent_id": "I-entry1", "kind": "entry", "mock": True, "price": 99.66,
                           "qty": 1, "side": "buy", "ts": "2026-09-28T18:30:02Z"},
                          {"fee": 1.0, "intent_id": "I-exit1", "kind": "exit", "mock": True, "price": 100.33,
                           "qty": 1, "side": "sell", "ts": "2026-09-28T21:30:02Z"}]}
        empty = {"week": "2026-W01", "no_trade_filled": True, "fills": [], "round_trips": [],
                 "best_trade": None, "worst_trade": None, "no_trade_note": "No entry filled.",
                 "best_pass": {"decision_id": did, "hypothetical_after_reveal": {"secret": "W01"}},
                 "comparison": [{"metric": "fees (simulated)", "value": 0.0}], "simulated": True}
        full = {"week": "2026-W02", "no_trade_filled": False, "round_trips": [trip], "fills": trip["fills"],
                "best_trade": trip, "worst_trade": trip,
                "best_pass": {"decision_id": did, "hypothetical_after_reveal": {"secret": "W02"}},
                "comparison": [{"metric": "fees (simulated)", "value": 2.0}], "simulated": True}
        review = dict(full)
        review.update({"weeks": ["2026-W01", "2026-W02"], "default_week": "2026-W02",
                       "by_week": {"2026-W01": empty, "2026-W02": full}})
        with open(os.path.join(cls.state, "review.json"), "w", encoding="utf-8") as f:
            json.dump(review, f)
        rd = os.path.join(cls.state, "reports")
        os.makedirs(rd, exist_ok=True)
        with open(os.path.join(rd, "report_2026-W02.pdf"), "wb") as f:
            f.write(b"%PDF-1.4\n% simulated test report\n")
        with open(os.path.join(rd, "report_2026-W02.html"), "w", encoding="utf-8") as f:
            f.write("<html><body>SIMULATED</body></html>")
        with open(os.path.join(rd, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("not served")
        with open(os.path.join(cls.state, "secret.pdf"), "wb") as f:
            f.write(b"%PDF outside reports")

    def test_default_week_is_latest_and_weeks_listed(self):
        r = self.get_json("/api/review")
        self.assertEqual(r["weeks"], ["2026-W01", "2026-W02"])
        self.assertEqual(r["week"], "2026-W02")
        self.assertEqual(r["week_report"], "report_2026-W02.pdf")
        self.assertNotIn("by_week", r)
        self.assertNotIn("secret", json.dumps(r))  # no week's hypothetical path leaks

    def test_no_fill_week_shown_faithfully(self):
        r = self.get_json("/api/review?week=2026-W01")
        self.assertEqual(r["week"], "2026-W01")
        self.assertTrue(r["no_fills"])
        self.assertIsNone(r.get("best_trade"))
        self.assertIsNone(r["week_report"])
        self.assertNotIn("secret", json.dumps(r))  # hypothetical stays hidden

    def test_unknown_week_falls_back_to_default(self):
        self.assertEqual(self.get_json("/api/review?week=../../etc")["week"], "2026-W02")

    def test_signal_is_decision_knowable_time_not_first_fill(self):
        bt = self.get_json("/api/review")["best_trade"]
        self.assertEqual(bt["signal_ts"], self.dec["ts_knowable"])
        self.assertEqual(bt["first_fill_ts"], "2026-09-28T18:30:02Z")

    def test_reveal_joins_round_trip_outcome(self):
        d = self.get_json("/api/decisions")
        row = [x for x in d["items"] if x.get("decision_id") == self.dec["decision_id"]]
        self.assertTrue(row and row[0].get("outcome") is None)
        r = self.get_json("/api/decisions?reveal=" + self.dec["decision_id"])
        o = r["item"]["outcome"]
        self.assertEqual(o["net_pnl"], -1.33)
        self.assertEqual(o["entry_fill_ids"], "I-entry1")
        self.assertEqual(o["exit_fill_ids"], "I-exit1")
        self.assertEqual(o["exit_fill_ts"], "2026-09-28T21:30:02Z")
        self.assertTrue(o["simulated"])

    def test_reports_route_serves_only_pdf_html_in_reports_dir(self):
        st, h, raw = self.req("GET", "/reports/report_2026-W02.pdf")
        self.assertEqual(st, 200)
        self.assertEqual(h.get("content-type"), "application/pdf")
        self.assertTrue(raw.startswith(b"%PDF"))
        st, h, raw = self.req("GET", "/reports/report_2026-W02.html")
        self.assertEqual(st, 200)
        self.assertIn("sandbox", h.get("content-security-policy", ""))
        for bad in ("/reports/notes.txt", "/reports/../secret.pdf", "/reports/%2e%2e%2fsecret.pdf",
                    "/reports/..%2Fsecret.pdf", "/reports/nope.pdf", "/reports/.hidden.pdf"):
            st, _, _ = self.req("GET", bad)
            self.assertEqual(st, 404, bad)
        self.assertEqual(self.get_json("/api/reports")["items"], ["report_2026-W02.html", "report_2026-W02.pdf"])

    def test_page_has_reference_pane_week_picker_and_route_gating(self):
        st, _, raw = self.req("GET", "/")
        html = raw.decode("utf-8")
        for needle in ("AMEX:SPY", "REFERENCE ONLY, real market, not the desk's data, nothing flows into the bot",
                       "SYNTHETIC", 'data-f="runend"', "/api/run_to_end", "wkSel", "Prior week",
                       "Weekly report (", "/api/health", "routeOk", "Reveal outcome"):
            self.assertIn(needle, html, needle)
        self.assertNotIn("s.tradingview_symbol || s.symbol", html)  # synthetic symbol never sent to TradingView


class TestWeeklyReportAndPolish(unittest.TestCase):
    def test_weekly_report_week_passthrough_is_validated(self):
        from ui import server as srv
        self.assertEqual(srv._plan_call("weekly_report", "weekly_report", {})[1], {})
        self.assertEqual(srv._plan_call("weekly_report", "weekly_report", {"week": "2026-W39"})[1], {"week": "2026-W39"})
        for bad in ("2026-W39\n", "../x", "2026-W3", 202639, "2026-W39; rm"):
            with self.assertRaises(ValueError):
                srv._plan_call("weekly_report", "weekly_report", {"week": bad})
        self.assertIn("week", srv._clean_body({"week": "2026-W39"}))

    def test_page_has_build_pdf_label_config_and_polish(self):
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "index.html")) as fh:
            html = fh.read()
        for needle in ("Build weekly PDF", "/api/weekly_report", "tradingview_label", "session_config",
                       "REFUSED, no fill", "Session complete (", "limitsCompact", "chart=1", "desk.tvOn"):
            self.assertIn(needle, html)
        self.assertNotIn("s.tradingview_symbol || s.symbol", html)


# --------------------------------------------------------------------------
# Decision-price lines: strategies write {"price": float, "text": str} objects
# --------------------------------------------------------------------------

def _page():
    with open(os.path.join(DESK_DIR, "ui", "index.html")) as fh:
        return fh.read()


STRATEGY_DECISION = {
    "decision_id": "ema-x-1", "ts_knowable": "2026-06-01T15:30:02Z", "symbol": "SPY",
    "strategy": "ema", "action": "enter_long", "qty": 4, "reason_code": "EMA_CROSS_UP",
    "reason_text": "fast EMA crossed above slow", "case_for": "", "case_against": "",
    "est_cost": {"usd": 0.37, "per_side_usd": 0.185, "basis": "bps model", "simulated": True},
    "pass_condition": "", "refusal_checks": [], "simulated": True,
    "trigger": {"price": 401.25, "text": "close above the slow EMA"},
    "intended_entry": {"price": 401.3, "text": "next bar open"},
    "intended_exit": {"price": None, "text": "exit on the cross back"},
    "invalidation": {"price": 399.8, "text": "below the swing low"},
}


class TestDecisionPriceLines(unittest.TestCase):
    def test_num_unwraps_price_objects(self):
        self.assertEqual(server._num({"price": 401.25, "text": "x"}), 401.25)
        self.assertEqual(server._num({"price": "399.5", "text": "x"}), 399.5)
        self.assertIsNone(server._num({"price": None, "text": "none"}))
        self.assertIsNone(server._num({"text": "no price key"}))
        self.assertIsNone(server._num({"price": True}))
        self.assertEqual(server._num(12), 12.0)
        self.assertIsNone(server._num(None))
        self.assertIsNone(server._num(False))

    def test_decision_lines_flattens_both_shapes(self):
        lines = server.decision_lines(STRATEGY_DECISION)
        self.assertEqual(lines["trigger"], {"price": 401.25, "text": "close above the slow EMA"})
        self.assertEqual(lines["intended_exit"], {"price": None, "text": "exit on the cross back"})
        self.assertEqual(lines["invalidation"]["price"], 399.8)
        plain = server.decision_lines({"trigger": 100.5, "intended_entry": None})
        self.assertEqual(plain["trigger"], {"price": 100.5, "text": None})
        self.assertEqual(plain["intended_entry"], {"price": None, "text": None})
        self.assertEqual(set(plain), {"trigger", "intended_entry", "intended_exit", "invalidation"})

    def test_api_decisions_carries_numeric_lines(self):
        tmp = tempfile.mkdtemp(prefix="ui_lines_")
        try:
            with open(os.path.join(tmp, "decisions.jsonl"), "w") as f:
                f.write(json.dumps(STRATEGY_DECISION) + "\n")
            srv = server.make_server(tmp, host="127.0.0.1", port=0)
            th = threading.Thread(target=srv.serve_forever, daemon=True)
            th.start()
            try:
                port = srv.server_address[1]
                for path in ("/api/decisions", "/api/decisions?reveal=ema-x-1"):
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request("GET", path)
                    body = json.loads(conn.getresponse().read().decode("utf-8"))
                    conn.close()
                    item = body["items"][0] if "items" in body else body["item"]
                    self.assertEqual(item["lines"]["trigger"]["price"], 401.25, path)
                    self.assertEqual(item["lines"]["invalidation"]["text"], "below the swing low")
                    self.assertEqual(item["est_cost_usd"], 0.37)
                    # the original objects are kept as written
                    self.assertEqual(item["trigger"], STRATEGY_DECISION["trigger"])
            finally:
                srv.shutdown()
                srv.server_close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_page_num_unwraps_price_and_shows_line_text(self):
        html = _page()
        # num() unwraps {price, text} before the numeric test (chart lines + decision panel)
        self.assertIn("typeof v === 'object' && 'price' in v", html)
        self.assertIn("lineText(", html)
        self.assertIn("costNum(d.est_cost)", html)


# --------------------------------------------------------------------------
# Alpaca paper (CONTRACT section 5): limits worksheet, adapter controls, lab
# --------------------------------------------------------------------------

# Synthetic fixture numbers for the worksheet mechanics only. They are not anyone's limits.
SYNTH_LIMITS = {"fixed_shares": 3, "max_loss_per_trade": 111.0, "daily_loss": 222.0,
                "per_trade_notional": 3333.0, "gross_exposure": 4444.0}


class _PostMixin(object):
    def post(self, path, body=None, headers=None):
        st, _, raw = self.req("POST", path, body if body is not None else {}, headers=headers)
        return st, json.loads(raw.decode("utf-8"))


class TestLimitsRoutes(_PostMixin, _Base):
    def _approved(self):
        return os.path.join(self.state, "limits_approved.json")

    def test_worksheet_draft_effects_approve(self):
        ws = self.get_json("/api/limits")
        self.assertEqual(ws["confirm_phrase"], "APPROVE PAPER LIMITS")
        self.assertIn("fixed_shares", ws["fields"])
        self.assertTrue(ws["test_examples"])
        # an incomplete draft saves, but cannot be approved
        st, j = self.post("/api/limits/draft", {"values": {"fixed_shares": 3}})
        self.assertEqual(st, 200, j)
        self.assertFalse(j["draft"]["complete"])
        st, j = self.post("/api/limits/approve", {"confirm": "APPROVE PAPER LIMITS", "reason": "t"})
        self.assertEqual(st, 400)
        self.assertIn("not complete", j["error"])
        self.assertFalse(os.path.exists(self._approved()))
        # complete draft, effects, wrong phrase, then the real approval
        st, j = self.post("/api/limits/draft", {"values": SYNTH_LIMITS})
        self.assertEqual(st, 200, j)
        self.assertTrue(j["draft"]["complete"])
        st, j = self.post("/api/limits/effects", {"ref_price": 400, "stop_distance": 2,
                                                  "fee_per_share": 0.01})
        self.assertEqual(st, 200, j)
        self.assertEqual(j["effects"]["notional"], 1200.0)
        self.assertTrue(j["effects"]["all_pass"])
        self.assertEqual(j["effects"]["assumptions"]["label"], "ASSUMED (not measured)")
        st, j = self.post("/api/limits/effects", {"stop_distance": 2})
        self.assertEqual(st, 400)
        st, j = self.post("/api/limits/approve", {"confirm": "approve", "reason": "t"})
        self.assertEqual(st, 400)
        self.assertIn("APPROVE PAPER LIMITS", j["error"])
        st, j = self.post("/api/limits/approve", {"confirm": True, "reason": "t"})
        self.assertEqual(st, 400)
        st, j = self.post("/api/limits/approve", {"confirm": "APPROVE PAPER LIMITS", "reason": " "})
        self.assertEqual(st, 400)
        self.assertFalse(os.path.exists(self._approved()))
        seen = self.get_json("/api/limits")             # what the operator reviewed on screen
        self.assertTrue(seen["draft_hash"])
        self.assertIsNone(seen["approved_hash"])
        # an approval without the reviewed hashes, or with a stale draft hash, is refused
        st, j = self.post("/api/limits/approve", {"confirm": "APPROVE PAPER LIMITS", "reason": "t"})
        self.assertEqual(st, 400)
        self.assertIn("draft you reviewed", j["error"])
        st, j = self.post("/api/limits/approve", {"confirm": "APPROVE PAPER LIMITS", "reason": "t",
                                                  "draft_hash": "0" * 64, "prior_approved_hash": None})
        self.assertEqual(st, 400)
        self.assertIn("draft changed", j["error"])
        st, j = self.post("/api/limits/approve", {"confirm": "APPROVE PAPER LIMITS", "reason": "t",
                                                  "draft_hash": seen["draft_hash"]})
        self.assertEqual(st, 400)                        # prior approved hash not named
        st, j = self.post("/api/limits/approve", {"confirm": "APPROVE PAPER LIMITS", "reason": "t",
                                                  "draft_hash": seen["draft_hash"], "prior_approved_hash": 7})
        self.assertEqual(st, 400)                        # a non-text hash never matches
        self.assertFalse(os.path.exists(self._approved()))
        st, j = self.post("/api/limits/approve", {"confirm": "APPROVE PAPER LIMITS",
                                                  "reason": "synthetic fixture",
                                                  "draft_hash": seen["draft_hash"],
                                                  "prior_approved_hash": seen["approved_hash"]})
        self.assertEqual(st, 200, j)
        self.assertEqual(j["approved"]["provenance"], "operator-approved")
        self.assertIn("keeps the limits it loaded at start", j["note"])
        self.assertTrue(os.path.exists(self._approved()))
        self.assertIs(self.get_json("/api/limits")["approved_ok"], True)
        # the audit trail names the action and hash, never the numbers
        rows = [r for r in self.control_lines() if str(r.get("action", "")).startswith("limits_")]
        self.assertEqual([r["action"] for r in rows][-1], "limits_approve")
        for r in rows:
            self.assertNotIn("values", r)
            self.assertNotIn("3333", json.dumps(r))
        self.assertEqual(rows[-1]["hash"], j["approved"]["hash"])

    def test_bad_draft_refused(self):
        for body in ({"values": {"fixed_shares": -1}}, {"values": {"fixed_shares": 1.5}},
                     {"values": "x"}, {}):
            st, j = self.post("/api/limits/draft", body)
            self.assertEqual(st, 400, (body, j))
            self.assertFalse(j["ok"])

    def test_limits_routes_keep_the_post_guards(self):
        st, j = self.post("/api/limits/draft", {"values": {}}, headers={"Origin": "http://evil.example"})
        self.assertEqual(st, 403)
        st, _, _ = self.req("POST", "/api/limits/approve", None, headers={"Content-Type": "text/plain"})
        self.assertEqual(st, 415)


class TestAlpacaRoutesAbsent(_PostMixin, _Base):
    """Offline desk (v2 controller without adapter methods): no Enable, nothing recorded."""
    manager = FakeController()

    def test_alpaca_routes_501_and_record_nothing(self):
        before = len(self.control_lines())
        for path, body in (("/api/alpaca/enable", {"confirm": True}),
                           ("/api/alpaca/disable", {"reason": "x"}),
                           ("/api/alpaca/reconcile", {})):
            st, j = self.post(path, body)
            self.assertEqual(st, 501, (path, j))
            self.assertIs(j["recorded"], False)
            self.assertIn("--broker alpaca-paper", j["error"])
        self.assertEqual(len(self.control_lines()), before)

    def test_health_hides_alpaca_routes_and_reports_offline(self):
        h = self.get_json("/api/health")
        self.assertFalse([r for r in h["routes"] if r.startswith("/api/alpaca/")])
        self.assertIn("/api/advance", h["routes"])
        self.assertEqual(h["broker_mode"], "offline-fake")
        self.assertIs(h["simulated"], True)
        self.assertIs(h["lab_api"], False)
        self.assertEqual(h["limits_routes"], list(server.LIMITS_ROUTES))

    def test_lab_routes_degrade(self):
        st, _, raw = self.req("GET", "/api/lab")
        self.assertEqual(st, 501)
        st, _, raw = self.req("GET", "/api/lab/verify?id=dec-1")
        self.assertEqual(st, 501)
        st, _, raw = self.req("GET", "/api/lab/verify?id=a%20b")
        self.assertEqual(st, 400)
        st, h, raw = self.req("GET", "/lab")
        if os.path.isfile(server.LAB_PATH):
            self.assertEqual(st, 200)
            self.assertIn("text/html", h["content-type"])
        else:
            self.assertEqual(st, 404)
            self.assertIn(b"not in this build", raw)

    def test_spy_study_page_served_as_html(self):
        self.assertTrue(os.path.isfile(server.SPY_STUDY_PATH), "ui/spy_study.html is part of this build")
        for path in ("/spy-study", "/spy-study.html"):
            st, h, raw = self.req("GET", path)
            self.assertEqual(st, 200, path)
            self.assertIn("text/html", h["content-type"])
            self.assertIn(b"<html", raw[:2000].lower())
        self.assertIs(self.get_json("/api/health")["spy_study_page"], True)
        page = self.req("GET", "/")[2].decode("utf-8")
        self.assertIn('href="/spy-study"', page)
        self.assertIn("SPY November study (historical, hindsight)", page)

    def test_no_controller_alpaca_501(self):
        srv = server.make_server(self.state, host="127.0.0.1", port=0)
        self.assertFalse(srv.has_method("alpaca_enable"))
        self.assertFalse([r for r in srv.available_routes() if "alpaca" in r])
        srv.server_close()


class AlpacaControls(FakeController):
    """FakeController plus the section 5/7 methods the coordinator adds to DeskControls."""

    def alpaca_enable(self, confirm=False):
        if confirm is not True:
            return {"ok": False, "reason": "CONFIRM_REQUIRED"}
        return self._rec("alpaca_enable", confirm=confirm)

    def alpaca_disable(self, reason):
        return self._rec("alpaca_disable", reason=reason)

    def reconcile_now(self):
        return self._rec("reconcile_now")

    def lab_view(self):
        self.calls.append(("lab_view", {}, None))
        return {"ok": True, "items": [{"id": "dec-1"}], "simulated": True}

    def lab_verify(self, lab_id):
        self.calls.append(("lab_verify", {"id": lab_id}, None))
        return {"ok": True, "id": lab_id, "verified": True}


class TestAlpacaRoutesPresent(_PostMixin, _Base):
    manager = AlpacaControls()

    @classmethod
    def setUpClass(cls):
        super(TestAlpacaRoutesPresent, cls).setUpClass()
        cls.manager.state_dir = cls.state

    def _names(self):
        return [c[0] for c in self.manager.calls]

    def test_enable_needs_confirm_then_calls(self):
        self.manager.calls[:] = []
        st, j = self.post("/api/alpaca/enable", {})
        self.assertEqual(st, 400)
        self.assertIn("Enable needs confirm=true", j["error"])
        self.assertEqual(self._names(), [])
        st, j = self.post("/api/alpaca/enable", {"confirm": True})
        self.assertEqual(st, 200, j)
        self.assertTrue(j["controller_called"])
        self.assertEqual(self.manager.calls[-1][:2], ("alpaca_enable", {"confirm": True}))
        # the requested row was on disk before the controller ran
        self.assertGreaterEqual(self.manager.calls[-1][2], 1)

    def test_disable_needs_reason(self):
        self.manager.calls[:] = []
        st, j = self.post("/api/alpaca/disable", {})
        self.assertEqual(st, 400)
        st, j = self.post("/api/alpaca/disable", {"reason": "   "})
        self.assertEqual(st, 400)
        self.assertEqual(self._names(), [])
        st, j = self.post("/api/alpaca/disable", {"reason": "done for today"})
        self.assertEqual(st, 200, j)
        self.assertEqual(self.manager.calls[-1][:2], ("alpaca_disable", {"reason": "done for today"}))

    def test_reconcile_calls(self):
        st, j = self.post("/api/alpaca/reconcile", {})
        self.assertEqual(st, 200, j)
        self.assertEqual(self._names()[-1], "reconcile_now")

    def test_health_lists_alpaca_routes_and_lab(self):
        h = self.get_json("/api/health")
        for r in ("/api/alpaca/enable", "/api/alpaca/disable", "/api/alpaca/reconcile"):
            self.assertIn(r, h["routes"])
        self.assertIs(h["lab_api"], True)

    def test_lab_view_and_verify(self):
        self.assertEqual(self.get_json("/api/lab")["items"][0]["id"], "dec-1")
        j = self.get_json("/api/lab/verify?id=dec-1")
        self.assertEqual(j["id"], "dec-1")
        self.assertEqual(self.manager.calls[-1], ("lab_verify", {"id": "dec-1"}, None))
        st, _, _ = self.req("GET", "/api/lab/verify")
        self.assertEqual(st, 400)

    def test_broker_mode_drives_simulated_flag(self):
        path = os.path.join(self.state, "session.json")
        with open(path) as f:
            original = f.read()
        try:
            for mode, simulated in (("alpaca-mock", True), ("alpaca-paper", False)):
                sess = json.loads(original)
                sess["broker_mode"] = mode
                with open(path, "w") as f:
                    json.dump(sess, f)
                h = self.get_json("/api/health")
                self.assertEqual((h["broker_mode"], h["simulated"]), (mode, simulated))
                st, j = self.post("/api/alpaca/reconcile", {})
                self.assertIs(j["simulated"], simulated)
                self.assertEqual(self.control_lines()[-1]["simulated"], simulated)
                self.assertEqual(self.control_lines()[-2]["broker_mode"], mode)
        finally:
            with open(path, "w") as f:
                f.write(original)

    def test_session_carries_adapter_file(self):
        p = os.path.join(self.state, "alpaca_paper.json")
        with open(p, "w") as f:
            json.dump({"enabled": False, "disabled_reason": "start", "changed_utc": "x"}, f)
        try:
            self.assertEqual(self.get_json("/api/session")["_adapter_file"]["enabled"], False)
        finally:
            os.remove(p)
        self.assertIsNone(self.get_json("/api/session")["_adapter_file"])


class TestAlpacaPage(unittest.TestCase):
    """Static checks on the operator page's Alpaca and Setup wiring (CONTRACT section 5)."""

    def setUp(self):
        self.html = _page()

    def test_banner_controls_and_setup_present(self):
        for s in ("brokerBanner", "viewSetup", "Check for new bars", "Reconcile now",
                  "/api/alpaca/enable", "/api/alpaca/disable", "/api/alpaca/reconcile",
                  "/api/limits/draft", "/api/limits/effects", "/api/limits/approve",
                  "Save draft", "Review and approve", "Check effects", "Copy into draft",
                  "APPROVE PAPER LIMITS", "PARTIAL FILL", "UNCERTAIN", "RECONCILE BLOCKING",
                  "Nothing runs in the background"):
            self.assertIn(s, self.html, s)

    def test_no_new_timers_or_external_loads(self):
        # only the two pre-existing timers (2s local file refresh, 1s clock); Alpaca and Setup add none
        self.assertEqual(self.html.count("setInterval("), 2)
        self.assertIn("setInterval(tick, 2000)", self.html)
        self.assertIn("setInterval(renderHeader, 1000)", self.html)
        self.assertNotIn("<iframe", self.html.lower())
        self.assertNotIn('src="http', self.html)
        self.assertNotIn("<link", self.html)

    def test_setup_never_auto_approves(self):
        # the only approve call is the dialog's Yes handler, which sends the typed phrase and reason
        self.assertEqual(self.html.count("postLimits('/api/limits/approve'"), 1)
        self.assertIn("{confirm: ph, reason: rs, draft_hash: bind.draft_hash", self.html)
        # the binding is captured when the dialog opens, from the worksheet the operator reviewed
        self.assertIn("S.apBind = {draft_hash: w.draft_hash", self.html)
        self.assertIn("approval approves the saved draft", self.html)

    def test_protection_check_gap_and_quote_view(self):
        # lead Codex 23:2xZ: booked qty, confirmed vs pending protective qty, exits, uncovered,
        # the gap between manual Checks, and the latest IEX quote only when it is a valid observation
        for s in ("function protectionHtml(s)", "function checkGapText(s)", "function quoteHtml(s)",
                  "h += protectionHtml(s) + quoteHtml(s);", "protective stop confirmed working",
                  "pending broker confirmation", "PENDING CONFIRMATION", "working exits", "UNCOVERED",
                  "Not a loss cap:", "Between manual Checks nothing runs.", "since_previous_check_s",
                  "q.valid === true", "q0.available !== false", "Latest IEX bid/ask (indicative, not a tradable price)",
                  "UNAVAILABLE"):
            self.assertIn(s, self.html)

    def test_second_pass_mode_and_first_viewport(self):
        # coordinator 2026-11-16 (Codex 02:53Z review): one mode badge, live only from the controller's
        # alpaca-live label, one status line, details behind a disclosure, plain Alpaca dashboard link
        for s in ("function isLive(s)", "=== 'alpaca-live'", "LIVE: REAL MONEY", "Local rehearsal",
                  "Paper (no real money)", "Mode not reported", 'id="statusLine"', 'id="modeDet"',
                  'id="bbDetail"', 'id="resPop"', 'href="https://app.alpaca.markets/"',
                  "PARTIALLY PROTECTED: ", "bb.hidden = !needsAction", 'data-f="stop"'):
            self.assertIn(s, self.html)
        # no internal filenames on the chart's empty state or source tag
        for s in ("state_dir/alpaca_bars.jsonl is empty", "state_dir/bars.jsonl is missing",
                  "(alpaca_bars.jsonl), paper account"):
            self.assertNotIn(s, self.html)
        with open(os.path.join(DESK_DIR, "ui", "lab.html"), encoding="utf-8") as fh:
            lab = fh.read()
        for s in ('id="modeBadge"', '"/api/session"', 'm === "alpaca-live"', "LIVE: REAL MONEY"):
            self.assertIn(s, lab)

    def test_broker_labels_follow_actual_transport(self):
        # Codex QA 22:45Z: arm tooltip and broker chip name mock vs paper HTTPS from the transport the
        # controller built (session.broker.transport), not the inherited offline text or the mode name alone.
        for s in ("function transportKind(s)", "((s || {}).broker || {}).transport",
                  "/^MockAlpacaTransport\\b/", "/^HttpsTransport\\b/",
                  "over HTTPS to the fixed paper host", "in-process mock transport",
                  "transport not reported", "const armText = bw.arm, armTitle = bw.title;",
                  "brokerWords(s).chip"):
            self.assertIn(s, self.html)
        self.assertNotIn("isPaper(s) ? ' &middot; <b>sends real requests", self.html)
        # the repr prefixes the page keys on are the transports' own (no network: nothing is sent)
        sys.path.insert(0, DESK_DIR)
        from alpaca.mock import MockAlpacaTransport
        from alpaca.transport import HttpsTransport, StaticTestProvider
        self.assertTrue(repr(MockAlpacaTransport()).startswith("MockAlpacaTransport("))
        self.assertTrue(repr(HttpsTransport(StaticTestProvider("SYNTHETIC-ID", "SYNTHETIC-SECRET"), opener=object())).startswith("HttpsTransport("))


class TestLivePayload(unittest.TestCase):
    """A fake live /api/session payload (W-D controller strings) must render the red LIVE badge, never Paper."""

    LIVE = {"broker_mode": "alpaca-live",
            "broker": {"transport": "HttpsTransport(SYNTHETIC-TEST)"},
            "adapter": {"enabled": False, "disabled_reason": "test", "changed_utc": None,
                        "path_name": "alpaca_live.json", "mode": "live"}}

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ui_live_")
        self.state = os.path.join(self.tmp, "state")
        shutil.copytree(SAMPLE, self.state)
        p = os.path.join(self.state, "session.json")
        with open(p, encoding="utf-8") as fh:
            sess = json.load(fh)
        sess.update(self.LIVE)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(sess, fh)
        self.srv = server.make_server(self.state, host="127.0.0.1", port=0)
        self.th = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.th.start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _session(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=5)
        conn.request("GET", "/api/session", headers={"Host": "127.0.0.1:%d" % self.srv.server_address[1]})
        r = conn.getresponse()
        body = json.loads(r.read().decode("utf-8"))
        conn.close()
        self.assertEqual(r.status, 200)
        return body

    def test_live_strings_reach_the_page_and_are_keyed(self):
        s = self._session()
        self.assertEqual(s["broker_mode"], "alpaca-live")
        self.assertEqual(s["adapter"]["path_name"], "alpaca_live.json")
        self.assertEqual(s["adapter"]["mode"], "live")
        page = _page()
        for key in ("=== 'alpaca-live'", "=== 'alpaca_live.json'", "=== 'live'"):
            self.assertIn(key, page)
        with open(os.path.join(DESK_DIR, "ui", "lab.html")) as fh:
            lab = fh.read()
        for key in ('m === "alpaca-live"', '=== "alpaca_live.json"', '=== "live"', "LIVE: REAL MONEY"):
            self.assertIn(key, lab)

    def test_used_up_flow_and_marker_clamp_are_wired(self):
        page = _page()
        self.assertNotIn("mockUsedUp", page)
        self.assertIn("ph === 'PRE_SESSION' && barsUsedUp(s) ? 'close'", page)
        self.assertIn("armB.classList.toggle('pri', !(ph === 'PRE_SESSION' && barsUsedUp(s)))", page)
        self.assertIn("if (barsUsedUp(s)) return {tone: 'warn', title: 'Replay bars used up'", page)
        self.assertIn("if (isAlpaca(s)) return false;", page)
        self.assertIn("y = Math.max(padT + r + 1, Math.min(padT + ph - r - 1, y));", page)

    @unittest.skipUnless(shutil.which("node"), "node not installed; static checks above still run")
    def test_live_payload_renders_red_live_badge_and_no_paper(self):
        import subprocess
        page = _page()
        a = page.index("function isAlpaca(s)")
        b = page.index("function adapterOf(s)")
        helpers = page[a:b]
        s = self._session()
        cases = {"full": s,
                 "mode_only": {"broker_mode": "alpaca-live", "broker": s["broker"]},
                 "path_only": {"broker_mode": "alpaca-paper", "broker": s["broker"], "adapter": {"path_name": "alpaca_live.json"}},
                 "adapter_mode_only": {"broker_mode": "alpaca-paper", "broker": s["broker"], "adapter": {"mode": "live"}},
                 "paper": {"broker_mode": "alpaca-paper", "broker": s["broker"], "adapter": {"path_name": "alpaca_paper.json"}}}
        js = helpers + "\nconst C = " + json.dumps(cases) + ";\nconst out = {};\n" \
            "for (const k in C) { const m = modeBadge(C[k]); const w = brokerWords(C[k]); out[k] = {badge: m, words: w, paper: isPaper(C[k])}; }\n" \
            "process.stdout.write(JSON.stringify(out));"
        r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        for k in ("full", "mode_only", "path_only", "adapter_mode_only"):
            o = out[k]
            self.assertEqual(o["badge"]["t"], "LIVE: REAL MONEY", k)
            self.assertEqual(o["badge"]["c"], "live", k)
            self.assertFalse(o["paper"], k)
            shown = json.dumps([o["badge"], o["words"]])
            self.assertNotIn("Paper", shown, k)
            self.assertNotIn("PAPER", shown, k)
        self.assertEqual(out["full"]["words"]["kind"], "live")
        self.assertEqual(out["paper"]["badge"]["t"], "Paper (no real money)")
        self.assertNotIn("LIVE", json.dumps(out["paper"]["badge"]))


class TestBannerTruth(unittest.TestCase):
    """Pass-4 regressions from Codex's Chromium probe: no false "used up", no false "Stop & Close finished"."""

    PF = [{"check": "limits", "ok": True}]

    def _run(self, cases):
        import subprocess
        page = _page()

        def fn(name):
            i = page.index("function %s(" % name)
            return page[i:page.index("\nfunction ", i + 5)]
        a = page.index("function isAlpaca(s)")
        ns = page.index("function nextStep(s)")
        b = page.index("\nfunction ", ns + 10)
        js = "".join(fn(n) + "\n" for n in ("num", "clockNow", "phaseOf", "preflightOk"))
        js += "const S = {conn: true, session: {}};\n"
        js += "const document = {querySelector: () => null, querySelectorAll: () => []};\n"
        js += page[a:b]
        js += "\nconst C = " + json.dumps(cases) + ";\nconst out = {};\n"
        js += "for (const k in C) { const n = nextStep(C[k]); out[k] = {title: n.title, btn: n.btn || null, detail: n.detail, used: barsUsedUp(C[k])}; }\n"
        js += "process.stdout.write(JSON.stringify(out));"
        r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return json.loads(r.stdout)

    def _paper(self, **kw):
        s = {"phase": "PRE_SESSION", "broker_mode": "alpaca-paper", "broker": {"transport": "HttpsTransport(paper)"},
             "bars_done": 64, "bars_total": 64, "preflight": self.PF, "adapter": {"enabled": True},
             "limits_source": {"label": "approved", "prov": "approved"}}
        s.update(kw)
        return s

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_alpaca_feeds_are_never_used_up(self):
        mock = self._paper(broker_mode="alpaca-mock", broker={"transport": "MockAlpacaTransport()"})
        out = self._run({
            "paper64": self._paper(),
            "armed64": self._paper(phase="ARMED"),
            "armed65": self._paper(phase="ARMED", bars_done=65, bars_total=65),
            "mock64": mock,
            "live64": self._paper(broker_mode="alpaca-live"),
        })
        for k, v in out.items():
            self.assertFalse(v["used"], k)
            self.assertNotIn("used up", (v["title"] + " " + v["detail"]).lower(), k)
        self.assertEqual(out["paper64"]["btn"], "Arm this Alpaca PAPER session")
        self.assertEqual(out["armed64"]["btn"], "Check for new bars")
        self.assertEqual(out["armed65"]["btn"], "Check for new bars")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_finished_offline_replay_is_used_up(self):
        out = self._run({"replay": {"phase": "PRE_SESSION", "bars_done": 70, "bars_total": 70, "preflight": self.PF},
                         "midway": {"phase": "PRE_SESSION", "bars_done": 12, "bars_total": 70, "preflight": self.PF}})
        self.assertTrue(out["replay"]["used"])
        self.assertEqual(out["replay"]["title"], "Replay bars used up")
        self.assertFalse(out["midway"]["used"])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_stop_close_finished_only_when_broker_confirms_flat(self):
        base = {"phase": "STOPPED", "broker_mode": "alpaca-paper", "broker": {"transport": "HttpsTransport(paper)"},
                "exposure": {"position_qty": 0}}
        unconf = dict(base, controls={"stopped": True, "flat_confirmed": False, "close_pending": "broker unreachable; retrying"},
                      recovery={"ambiguous": True, "reason": "broker response unavailable"})
        conf_but_ambiguous = dict(unconf, controls={"stopped": True, "flat_confirmed": True})
        clean = dict(base, controls={"stopped": True, "flat_confirmed": True}, recovery={})
        out = self._run({"unconf": unconf, "conf_amb": conf_but_ambiguous, "clean": clean})
        for k in ("unconf", "conf_amb"):
            self.assertEqual(out[k]["title"], "Stop & Close not confirmed", k)
            self.assertNotIn("finished", out[k]["detail"], k)
            self.assertEqual(out[k]["btn"], "Reconcile now", k)
        self.assertIn("broker has not confirmed flat", out["unconf"]["detail"])
        self.assertIn("keeps retrying the close", out["unconf"]["detail"])
        self.assertIn("recovery is ambiguous", out["conf_amb"]["detail"])
        self.assertEqual(out["clean"]["title"], "Stopped and flat")
        self.assertIn("Stop & Close finished", out["clean"]["detail"])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_finished_replay_holding_a_position_points_at_stop(self):
        rp = {"phase": "ARMED", "bars_done": 70, "bars_total": 70, "preflight": self.PF}
        out = self._run({"open": dict(rp, exposure={"position_qty": -20}), "flat": dict(rp, exposure={"position_qty": 0})})
        self.assertEqual(out["open"]["title"], "Replay finished, position still open")
        self.assertEqual(out["open"]["btn"], "Stop & Close")
        self.assertEqual(out["flat"]["title"], "Replay finished")
        self.assertEqual(out["flat"]["btn"], "Close & review")

    def test_tab_title_follows_the_mode_badge(self):
        page = _page()
        self.assertIn("<title>SPY Desk</title>", page)
        self.assertNotIn("<title>Paper Desk (SIMULATED)</title>", page)
        self.assertIn("document.title = bdg.t + ' \\u00b7 SPY Desk';", page)
        # The header brand sits beside the mode badge, so it must not claim "Paper" on a live page.
        self.assertIn('<span class="brand">SPY Desk</span>', page)
        self.assertNotIn("SPY Paper Desk", page)


class TestFirstScreen(unittest.TestCase):
    """Pass-4 first screen: one next step plus Stop & Close; other actions in one disclosure; short empty chart."""

    def test_session_actions_sit_in_one_disclosure_with_stop_outside(self):
        page = _page()
        d0 = page.index('<details id="flowMore" class="fmore" open>')
        d1 = page.index("</details>", d0)
        self.assertIn('<summary id="flowMoreSum">More session actions</summary>', page[d0:d1])
        for f in ("review", "arm", "pause", "resume", "clear", "close"):
            self.assertIn('data-f="%s"' % f, page[d0:d1], f)
        stop = page.index('id="btnStop"')
        self.assertGreater(stop, d1, "Stop & Close must stay outside the disclosure")

    def test_narrow_screen_hides_disabled_actions_and_starts_closed(self):
        page = _page()
        self.assertIn(".fmbody .ar,.fmbody button:disabled{display:none}", page)
        self.assertIn("#btnStop{order:-1}", page)
        self.assertIn("fm.open = !mq.matches;", page)
        self.assertIn("'More session actions (' + avail + ')'", page)

    def test_empty_chart_says_only_waiting_for_first_bar(self):
        page = _page()
        self.assertIn("'Waiting for the first SPY bar'", page)
        self.assertNotIn("No replay bars to show yet", page)
        self.assertNotIn("Bars appear only when you press Check", page)


class TestAlpacaBarsFile(unittest.TestCase):
    """The Alpaca session writes alpaca_bars.jsonl; the chart route must read it, labeled."""

    def _write(self, d, name, rows):
        with open(os.path.join(d, name), "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def test_alpaca_mode_reads_alpaca_bars(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "session.json"), "w") as fh:
                json.dump({"broker_mode": "alpaca-mock"}, fh)
            self._write(d, "alpaca_bars.jsonl", [{"ts_close": "2026-11-16T14:35:00Z", "seq": 1, "close": 1.0}])
            bars, _, meta = server._bars(d)
            self.assertEqual(len(bars), 1)
            self.assertIn("alpaca_bars.jsonl", meta["bars_source"])
            self.assertIn("never TradingView", meta["bars_source"])

    def test_replay_mode_keeps_replay_bars(self):
        with tempfile.TemporaryDirectory() as d:
            self._write(d, "bars.jsonl", [{"ts_close": "2026-11-16T14:35:00Z", "seq": 1}])
            self._write(d, "alpaca_bars.jsonl", [{"ts_close": "x", "seq": 1}, {"ts_close": "y", "seq": 2}])
            bars, _, meta = server._bars(d)
            self.assertEqual(len(bars), 1)
            self.assertEqual(meta["bars_source"], server.BARS_SOURCE_REPLAY)


if __name__ == "__main__":
    unittest.main()
