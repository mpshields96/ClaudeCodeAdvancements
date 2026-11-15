"""CONTRACT v2 tests for the desk strategies (worker C). Stdlib only, offline.

* Purity: a warm (cached) call equals a cold replay for the same inputs,
  including corrected, removed or in-place-edited bars (Codex's 17:25Z
  repro: a zero-volume correction after an EMA entry).
* MAX_LOSS: every entry carries a numeric stop, and with the desk's TEST
  VALUE cap in cfg every entry satisfies
  qty * |intended_entry - invalidation| + est round-trip cost <= cap.

Run:
  /usr/bin/python3 -I -m unittest discover -s <desk>/tests -p 'test_strategies*'
"""
import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
TVBOT = os.path.dirname(DESK)
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from strategies import base as B          # noqa: E402
from strategies import registry as R      # noqa: E402

FIXTURE = os.path.join(TVBOT, "fixtures", "normal_bars.jsonl")
CAP10 = {"limits": {"max_loss_per_trade": 10.0, "label": "TEST VALUES"}}
ENTRY = ("enter_long", "enter_short")


def load_bars():
    bars = []
    with open(FIXTURE, "r", encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                row = json.loads(ln)
                if row.get("type") == "bar":
                    bars.append(row)
    bars.sort(key=lambda b: (b["ts_close"], b["seq"]))
    return bars


BARS = load_bars()
KINDS = tuple(R.STRATEGIES)


def canon(d):
    return json.dumps(d, sort_keys=True, default=repr)


def cold(kind, bars, position=None, cfg=None):
    R.clear_cache()
    return R.STRATEGIES[kind](copy.deepcopy(bars), position, copy.deepcopy(cfg))


def warm_to(kind, bars, k, cfg=None):
    """Call every bar up to k so the cache holds bars[:k]."""
    R.clear_cache()
    fn = R.STRATEGIES[kind]
    out = None
    for j in range(1, k + 1):
        out = fn(bars[:j], None, cfg)
    return out


def stream(kind, bars, cfg=None):
    R.clear_cache()
    fn = R.STRATEGIES[kind]
    return [fn(bars[:k], None, cfg) for k in range(1, len(bars) + 1)]


def corrections(h):
    last, prev = h[-1], h[-2]
    return {
        "last_volume_zero": h[:-1] + [dict(last, volume=0)],
        "last_high_low": h[:-1] + [dict(last, high=last["high"] + 5.0, low=last["low"] - 5.0)],
        "last_close": h[:-1] + [dict(last, close=round(last["close"] * 1.01, 4))],
        "earlier_volume_zero": h[:-2] + [dict(prev, volume=0), last],
        "last_removed": h[:-1],
        "fresh_short_history": h[-7:],
    }


def entry_followers(kind):
    """Bar counts k whose previous decision (bars[:k-1]) was an entry."""
    ds = stream(kind, BARS)
    return [i + 2 for i, d in enumerate(ds[:-1]) if d["action"] in ENTRY]


class WarmEqualsCold(unittest.TestCase):
    def test_codex_case_ema_entry_then_zero_volume(self):
        ks = entry_followers("ema")
        self.assertTrue(ks)
        for k in ks:
            warm_to("ema", BARS, k)
            fixed = BARS[:k - 1] + [dict(BARS[k - 1], volume=0)]
            w = R.STRATEGIES["ema"](fixed, None, None)
            self.assertEqual(canon(w), canon(cold("ema", fixed)), "k=%d" % k)
            self.assertNotEqual(w["reason_code"], "HOLD_IN_TREND", "k=%d: a denied fill must not look filled" % k)

    def test_corrected_histories_match_cold_for_every_kind(self):
        for kind in KINDS:
            ks = sorted(set(entry_followers(kind)[:4] + [8, 15, 40, 90]))
            for k in ks:
                h = BARS[:k]
                for name, fixed in corrections(h).items():
                    warm_to(kind, BARS, k)
                    w = R.STRATEGIES[kind](fixed, None, None)
                    self.assertEqual(canon(w), canon(cold(kind, fixed)), "%s k=%d %s" % (kind, k, name))

    def test_in_place_edit_of_an_earlier_bar_forces_cold_replay(self):
        for kind in KINDS:
            for k in sorted(set(entry_followers(kind)[:3] + [30])):
                hist = [dict(b) for b in BARS[:k]]
                R.clear_cache()
                fn = R.STRATEGIES[kind]
                for j in range(1, k + 1):
                    fn(hist[:j], None, None)
                hist[-1]["volume"] = 0          # same dict objects, edited in place
                hist[-2]["high"] = hist[-2]["high"] + 3.0
                self.assertEqual(canon(fn(hist, None, None)), canon(cold(kind, hist)), "%s k=%d" % (kind, k))

    def test_rejected_bar_dropped_then_history_continues(self):
        # session.py drops an untrusted bar and keeps feeding later bars.
        for kind in KINDS:
            for k in sorted(set(entry_followers(kind)[:3] + [20])):
                if k + 4 > len(BARS):
                    continue
                warm_to(kind, BARS, k)
                fn = R.STRATEGIES[kind]
                for extra in range(1, 4):
                    h = BARS[:k - 1] + BARS[k:k + extra]
                    self.assertEqual(canon(fn(h, None, None)), canon(cold(kind, h)), "%s k=%d +%d" % (kind, k, extra))

    def test_full_stream_warm_equals_cold_spot_checks(self):
        for kind in KINDS:
            ds = stream(kind, BARS)
            for k in range(7, len(BARS) + 1, 53):
                self.assertEqual(canon(ds[k - 1]), canon(cold(kind, BARS[:k])), "%s k=%d" % (kind, k))

    def test_mutating_a_returned_decision_cannot_change_the_next_call(self):
        for kind in KINDS:
            for k in (12, 60):
                warm_to(kind, BARS, k)
                fn = R.STRATEGIES[kind]
                d = fn(BARS[:k], None, None)
                d["refusal_checks"].append({"id": "TAMPER", "passed": False, "detail": "x"})
                d["est_cost"]["usd"] = 999.0
                d["action"] = "enter_long"
                self.assertEqual(canon(fn(BARS[:k], None, None)), canon(cold(kind, BARS[:k])), "%s k=%d" % (kind, k))

    def test_cfg_change_and_now_are_handled(self):
        for kind in ("ema", "gold_basket"):
            k = 90
            warm_to(kind, BARS, k)
            fn = R.STRATEGIES[kind]
            c2 = {"cost_mult": 2.0}
            self.assertEqual(canon(fn(BARS[:k], None, c2)), canon(cold(kind, BARS[:k], cfg=c2)))
            now = BARS[k - 1]["ts_close"]
            self.assertEqual(canon(fn(BARS[:k + 5], None, {"now": now})), canon(cold(kind, BARS[:k])))


class MaxLossCap(unittest.TestCase):
    def _entries(self, kind, cfg):
        return [d for d in stream(kind, BARS, cfg) if d["action"] in ENTRY]

    def test_every_entry_has_a_numeric_stop_without_a_cap(self):
        for kind in KINDS:
            for d in self._entries(kind, None):
                self.assertIsInstance(d["invalidation"]["price"], float, kind)
                self.assertIsInstance(d["intended_entry"]["price"], float, kind)
                ml = [c for c in d["refusal_checks"] if c["id"] == "MAX_LOSS_WOULD_BREACH"]
                self.assertEqual(len(ml), 1, kind)
                self.assertTrue(ml[0]["passed"], kind)

    def test_entries_fit_the_test_value_cap(self):
        n = 0
        for kind in KINDS:
            for d in self._entries(kind, CAP10):
                n += 1
                risk = d["qty"] * abs(d["intended_entry"]["price"] - d["invalidation"]["price"]) + d["est_cost"]["usd"]
                self.assertLessEqual(risk, 10.0 + 1e-9, "%s %s" % (kind, d["decision_id"]))
                self.assertTrue(all(c["passed"] for c in d["refusal_checks"]), kind)
        self.assertGreater(n, 0, "gold entries (about $6 risk) should still fit $10")

    def test_ema_breaches_ten_dollars_at_test_size_and_is_refused(self):
        ds = stream("ema", BARS, CAP10)
        self.assertFalse([d for d in ds if d["action"] in ENTRY])
        refused = [d for d in ds if d["reason_code"] == "MAX_LOSS_WOULD_BREACH"]
        self.assertTrue(refused)
        for d in refused:
            self.assertEqual((d["action"], d["qty"]), ("pass", 0))
            self.assertFalse(d["refusal_checks"][-1]["passed"])

    def test_tiny_cap_leaves_no_phantom_position(self):
        for kind in KINDS:
            acts = set(d["action"] for d in stream(kind, BARS, {"limits": {"max_loss_per_trade": 1.0}}))
            self.assertEqual(acts, {"pass"}, kind)

    def test_cap_never_resizes(self):
        for kind in KINDS:
            a = [(d["action"], d["qty"]) for d in stream(kind, BARS, None)]
            b = [(d["action"], d["qty"]) for d in stream(kind, BARS, {"limits": {"max_loss_per_trade": 1000.0}})]
            self.assertEqual(a, b, kind)


class FixedQty(unittest.TestCase):
    """HYPOTHETICAL fixed-quantity demo preset (TEST VALUE): cfg["fixed_qty"]
    is used as is, never above the TEST per-trade notional cap ($2,000)."""

    def test_positive_int_is_used_within_the_cap(self):
        self.assertEqual(B.base_qty(100.0, {"fixed_qty": 1}), 1)
        self.assertEqual(B.base_qty(100.0, {"fixed_qty": 20}), 20)      # 2000 == cap
        self.assertEqual(B.base_qty(1999.0, {"fixed_qty": 1}), 1)

    def test_over_the_cap_is_zero_not_resized(self):
        self.assertEqual(B.base_qty(2500.0, {"fixed_qty": 1}), 0)       # 2500 > 2000
        self.assertEqual(B.base_qty(100.0, {"fixed_qty": 30}), 0)       # 3000 > 2000
        lim = {"fixed_qty": 1, "limits": {"per_trade_notional": 50.0}}
        self.assertEqual(B.base_qty(100.0, lim), 0)                     # tighter desk cap wins

    def test_invalid_values_fall_back_to_the_floor_formula(self):
        floor = B.base_qty(100.0, {})
        self.assertEqual(floor, 20)
        for bad in (True, False, 0, -1, 1.0, "1", None):
            self.assertEqual(B.base_qty(100.0, {"fixed_qty": bad}), floor, repr(bad))
        self.assertEqual(B.base_qty(0.0, {"fixed_qty": 1}), 0)

    def test_ema_stream_with_one_share_fits_the_cap_and_matches_cold(self):
        cfg = dict(CAP10, fixed_qty=1)
        ds = stream("ema", BARS, cfg)
        entries = [d for d in ds if d["action"] in ENTRY]
        self.assertTrue(entries, "1 share risks about $4.70, so EMA enters under $10")
        for d in entries:
            self.assertEqual(d["qty"], 1)
            risk = abs(d["intended_entry"]["price"] - d["invalidation"]["price"]) + d["est_cost"]["usd"]
            self.assertLessEqual(risk, 10.0 + 1e-9, d["decision_id"])
            self.assertTrue(all(c["passed"] for c in d["refusal_checks"]), d["decision_id"])
        for k in range(7, len(BARS) + 1, 61):
            self.assertEqual(canon(ds[k - 1]), canon(cold("ema", BARS[:k], cfg=cfg)), "k=%d" % k)

    def test_over_cap_fixed_qty_shows_the_zero_size_refusal(self):
        ds = stream("ema", BARS, {"fixed_qty": 50})                    # 50 * ~100 > 2000
        self.assertFalse([d for d in ds if d["action"] in ENTRY])
        self.assertTrue([d for d in ds if d["reason_code"] == "ZERO_SIZE"])


if __name__ == "__main__":
    unittest.main()
