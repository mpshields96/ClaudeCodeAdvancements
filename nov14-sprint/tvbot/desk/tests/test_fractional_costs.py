"""ALPACA_EQUITY_COSTS fee math and exact fractional sizing on the EMA path.

Every number here is an arbitrary synthetic test value, not anyone's sizing,
limits or account. Offline: no broker, no network.
"""
import json
import os
import sys
import unittest
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from orders import qty as Q               # noqa: E402
from strategies import base as B          # noqa: E402
from strategies import engine as E        # noqa: E402

FIXTURE = os.path.join(os.path.dirname(DESK), "fixtures", "normal_bars.jsonl")
ALP = {"cost_profile": "alpaca_equity"}


def load_bars():
    out = []
    with open(FIXTURE, "r", encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                row = json.loads(ln)
                if row.get("type") == "bar":
                    out.append(row)
    out.sort(key=lambda b: (b["ts_close"], b["seq"]))
    return out


class DefaultCostsUntouched(unittest.TestCase):
    def test_default_dict_is_the_stress(self):
        self.assertEqual(B.DEFAULT_COSTS, {"kind": "bps", "half_spread_bps": 1.0, "slippage_bps": 2.0,
                                           "commission_per_share": 0.005, "commission_min": 1.0})

    def test_default_selected_without_profile(self):
        for cfg in (None, {}, {"cost_profile": "other"}, {"cost_profile": "ALPACA_EQUITY"}, {"fractional": True}):
            c = B.cost_cfg(cfg)
            self.assertEqual(c["commission_min"], 1.0)
            self.assertNotIn("profile", c)

    def test_default_est_cost_unchanged(self):
        c = B.cost_cfg({})
        est = B.est_cost(2, 100.0, c, sides=2, note="round trip")
        # 3 bps x $100 x 2 units = $0.06 per side + $1.00 minimum commission per side.
        self.assertAlmostEqual(est["usd"], 2.12, places=4)
        self.assertIn("commission $0.005/share", est["basis"])
        self.assertNotIn("fees", est)
        self.assertEqual(B.reg_fees(2, 100.0, -1, c)["total"], 0.0)


class AlpacaFeeMath(unittest.TestCase):
    def setUp(self):
        self.c = B.cost_cfg(ALP)

    def test_profile_selected_only_by_key(self):
        self.assertEqual(self.c["profile"], "alpaca_equity")
        self.assertEqual(self.c["commission_per_share"], 0.0)
        self.assertEqual(B.commission(5, self.c), 0.0)
        self.assertEqual(self.c["half_spread_bps"], 1.0)
        self.assertEqual(self.c["slippage_bps"], 2.0)

    def test_sub_penny_fee_rounds_up_to_a_cent(self):
        # 0.01 share x $50: CAT 0.00000003, SEC 0.00001 -> $0.01 each for one order; TAF $0 (retail).
        buy = B.reg_fees(Decimal("0.01"), 50.0, 1, self.c)
        sell = B.reg_fees(Decimal("0.01"), 50.0, -1, self.c)
        self.assertEqual((buy["sec"], buy["taf"], buy["cat"]), (0.0, 0.0, 0.01))
        self.assertEqual((sell["sec"], sell["taf"], sell["cat"]), (0.01, 0.0, 0.01))
        self.assertAlmostEqual(buy["total"], 0.01)
        self.assertAlmostEqual(sell["total"], 0.02)

    def test_side_treatment_sec_and_taf_sell_only(self):
        buy = B.reg_fees(1000, 200.0, 1, self.c)
        self.assertEqual(buy["sec"], 0.0)
        self.assertEqual(buy["taf"], 0.0)
        self.assertGreater(buy["cat"], 0.0)

    def test_larger_order_rates(self):
        # 1000 x $200 = $200,000 sold: SEC 4.12; TAF $0 (retail); CAT 0.003 -> 0.01.
        sell = B.reg_fees(1000, 200.0, -1, self.c)
        self.assertAlmostEqual(sell["sec"], 4.12)
        self.assertAlmostEqual(sell["taf"], 0.0)
        self.assertAlmostEqual(sell["cat"], 0.01)

    def test_taf_cap_still_applies_if_a_rate_is_set(self):
        # The cap logic is kept for a profile that sets a TAF rate (FINRA 2026 member rate shown).
        c = dict(self.c, taf_per_share=0.000195)
        sell = B.reg_fees(100000, 1.0, -1, c)
        self.assertAlmostEqual(sell["taf"], 9.79)

    def test_taf_is_alpaca_retail_zero(self):
        # Alpaca's Oct 12, 2026 schedule lists retail TAF $0 per share (W120 correction).
        self.assertEqual(self.c["taf_per_share"], 0.0)
        self.assertEqual(self.c["taf_max"], 9.79)
        self.assertEqual(self.c["fee_round"], "daily_per_type_penny_up")
        self.assertEqual(B.reg_fees(100000, 1.0, -1, self.c)["taf"], 0.0)

    def test_exact_quantity_used(self):
        # 0.5 share pays the same rounded cent as 1 share at these tiny sizes.
        self.assertEqual(B.reg_fees(Decimal("0.5"), 10.0, 1, self.c)["cat"], 0.01)
        self.assertEqual(B.reg_fees(0, 10.0, 1, self.c)["total"], 0.0)

    def test_est_cost_round_trip_and_basis(self):
        q = Decimal("0.05")
        est = B.est_cost(q, 100.0, self.c, sides=2, note="round trip")
        spread = 100.0 * 3e-4 * 0.05
        # Same-day round trip, billed per fee type per day: SEC $0.01 + CAT $0.01 (both sides summed).
        self.assertAlmostEqual(est["usd"], round(spread * 2 + 0.02, 4), places=4)
        self.assertTrue(est["simulated"])
        b = est["basis"]
        for frag in ("ESTIMATE", "commission $0", "SEC $0.0000206", "CAT $0.000003",
                     "TAF $0", "lists retail TAF $0", "aggregated per day and rounded UP to $0.01",
                     "same-day round trip $0.02",
                     "BrokFeeSched.pdf", "docs.alpaca.markets/us/docs/regulatory-fees",
                     "slippage 2.0 bps"):
            self.assertIn(frag, b)
        for gone in ("0.000166", "8.30", "0.000195", "TAF reserve", "per order;"):
            self.assertNotIn(gone, b)
        self.assertEqual(est["fees"]["rounding"], "daily_per_type_penny_up")
        self.assertAlmostEqual(est["fees"]["sell"]["total"], 0.02)
        self.assertAlmostEqual(est["fees"]["day"]["total"], 0.02)
        self.assertEqual((est["fees"]["day"]["sec"], est["fees"]["day"]["taf"], est["fees"]["day"]["cat"]),
                         (0.01, 0.0, 0.01))
        one = B.est_cost(q, 100.0, self.c, sides=1, note="one side to close")
        self.assertAlmostEqual(one["usd"], round(spread + 0.02, 4), places=4)
        self.assertIn("one order $0.02", one["basis"])
        json.dumps(est)

    def test_stress_multiplier_applies(self):
        c = B.cost_cfg({"cost_profile": "alpaca_equity", "cost_mult": 2.0})
        self.assertAlmostEqual(B.reg_fees(Decimal("0.01"), 50.0, -1, c)["total"], 0.04)
        self.assertAlmostEqual(B.day_fees(Decimal("0.01"), 50.0, c)["total"], 0.04)

    def test_fees_never_zero_for_a_real_order(self):
        est = B.est_cost(Decimal("0.001"), 600.0, self.c)
        self.assertGreaterEqual(est["usd"], 0.02)


class FractionalSizing(unittest.TestCase):
    SIZE = {"order_notional": 5.0}

    def test_int_path_unchanged(self):
        cfg = {"test_size": self.SIZE}
        self.assertEqual(B.base_qty(2.0, cfg), 2)
        self.assertEqual(B.base_qty(2.0, cfg, allow_fraction=True), 2)
        self.assertEqual(B.base_qty(600.0, cfg, allow_fraction=True), 0)
        self.assertEqual(B.base_qty(2.0, {"test_size": self.SIZE, "fixed_qty": 0.25}), 2)
        self.assertEqual(B.base_qty(1.0, {"test_size": self.SIZE, "fixed_qty": 3}), 3)

    def test_fraction_needs_both_flag_and_caller(self):
        frac = {"test_size": self.SIZE, "fractional": True}
        self.assertEqual(B.base_qty(600.0, frac), 0)  # gold and other callers stay int
        self.assertEqual(B.base_qty(600.0, {"test_size": self.SIZE, "fractional": "yes"}, allow_fraction=True), 0)
        q = B.base_qty(600.0, frac, allow_fraction=True)
        self.assertIsInstance(q, Decimal)
        self.assertEqual(q, Decimal("0.008333333"))

    def test_notional_floor_never_rounds_up(self):
        frac = {"test_size": {"order_notional": 1.0}, "fractional": True}
        for px in (3.0, 7.0, 501.04, 0.3333):
            q = B.base_qty(px, frac, allow_fraction=True)
            self.assertLessEqual(Q.dec(q) * Decimal(repr(px)), Decimal("1.0"))
            self.assertGreater((Q.dec(q) + Decimal("1e-9")) * Decimal(repr(px)), Decimal("1.0"))

    def test_per_trade_notional_cap_respected(self):
        cfg = {"test_size": {"order_notional": 50.0}, "fractional": True, "limits": {"per_trade_notional": 2.0}}
        q = B.base_qty(400.0, cfg, allow_fraction=True)
        self.assertEqual(q, Decimal("0.005"))

    def test_exact_fixed_fraction(self):
        cfg = {"test_size": self.SIZE, "fractional": True, "fixed_qty": "0.0125"}
        self.assertEqual(B.base_qty(200.0, cfg, allow_fraction=True), Decimal("0.0125"))
        cfg["fixed_qty"] = 0.0125
        self.assertEqual(B.base_qty(200.0, cfg, allow_fraction=True), Decimal("0.0125"))
        cfg["fixed_qty"] = "0.03"  # 0.03 x 200 = 6 > 5: refused, never cut
        self.assertEqual(B.base_qty(200.0, cfg, allow_fraction=True), 0)
        cfg["fixed_qty"] = "0.0000000001"  # 10 decimals: Q refuses
        self.assertEqual(B.base_qty(200.0, cfg, allow_fraction=True), B.base_qty(200.0, dict(cfg, fixed_qty=None), allow_fraction=True))

    def test_decision_carries_exact_qty(self):
        bar = {"symbol": "SYN", "ts_close": "2026-01-05T15:00:00Z", "seq": 7}
        q = Decimal("0.008333333")
        d = B.make_decision("ema", "r", bar, "enter_long", q, "CROSS_UP", "t", "f", "a",
                            B.est_cost(q, 600.0, B.cost_cfg(ALP)), "p", None, None, None, None)
        self.assertEqual(d["qty"], 0.008333333)
        self.assertEqual(d["qty_text"], "0.008333333")
        self.assertEqual(Q.parse(d["qty"]), q)
        json.dumps(d)
        w = B.make_decision("ema", "r", bar, "enter_long", 4, "CROSS_UP", "t", "f", "a",
                            B.est_cost(0, None, B.cost_cfg({})), "p", None, None, None, None)
        self.assertEqual(w["qty"], 4)
        self.assertIsInstance(w["qty"], int)
        self.assertNotIn("qty_text", w)
        self.assertNotEqual(d["decision_id"], B.make_decision("ema", "r", bar, "enter_long", 0, "X", "t", "f", "a",
                                                              None, "p", None, None, None, None)["decision_id"])


class EmaFractionalEntry(unittest.TestCase):
    """The natural EMA engine on the repo's synthetic fixture bars."""

    @classmethod
    def setUpClass(cls):
        cls.bars = load_bars()

    def _first(self, cfg, code):
        r = E.Replayer("ema", cfg)
        for b in self.bars:
            d = r.step(b)
            if d["reason_code"] == code:
                return d, b
        return None, None

    def test_whole_share_desk_cannot_size_tiny_notional(self):
        d, _ = self._first({"test_size": {"order_notional": 1.0}}, "ZERO_SIZE")
        self.assertIsNotNone(d)
        self.assertEqual(d["case_for"], "No fractional sizing.")

    def test_fractional_leg_is_exact_and_costed(self):
        cfg = {"test_size": {"order_notional": 5.0}, "fractional": True, "cost_profile": "alpaca_equity"}
        d, b = self._first(cfg, "CROSS_UP")
        self.assertIsNotNone(d, "fixture produced no cross-up")
        close = float(b["close"])
        want = B.base_qty(close, cfg, allow_fraction=True)
        self.assertTrue(Q.is_fractional(want))
        self.assertEqual(Q.parse(d["qty"]), want)
        self.assertEqual(d["qty_text"], Q.text(want))
        self.assertIn("Long %s " % Q.text(want), d["intended_entry"]["text"])
        self.assertIn("ESTIMATE, Alpaca equity profile", d["est_cost"]["basis"])
        self.assertGreaterEqual(d["est_cost"]["usd"], 0.02)
        self.assertLessEqual(Q.dec(want) * Decimal(repr(close)), Decimal("5.0"))

    def test_fractional_cap_refusal_is_honest(self):
        # Generic cap below the legitimate cost alone: refused, never resized, cost not zeroed.
        cfg = {"test_size": {"order_notional": 5.0}, "fractional": True, "cost_profile": "alpaca_equity",
               "limits": {"max_loss_per_trade": 0.02}}
        d, _ = self._first(cfg, "MAX_LOSS_WOULD_BREACH")
        self.assertIsNotNone(d)
        self.assertEqual(d["action"], "pass")
        self.assertEqual(d["qty"], 0)
        self.assertGreater(d["est_cost"]["usd"], 0.02)
        chk = [c for c in d["refusal_checks"] if c["id"] == "MAX_LOSS_WOULD_BREACH"][0]
        self.assertFalse(chk["passed"])
        self.assertIn("vs cap $0.02", chk["detail"])

    def test_replay_book_takes_fractional_fill(self):
        cfg = {"test_size": {"order_notional": 5.0}, "fractional": True, "cost_profile": "alpaca_equity"}
        r = E.Replayer("ema", cfg)
        for b in self.bars:
            r.step(b)
        self.assertTrue(r.fills, "no simulated fills")
        f = r.fills[0]
        self.assertTrue(0 < f["qty"] < 1)
        self.assertGreaterEqual(f["commission"], 0.01)  # CAT on the buy, rounded up



class ParseTsFractions(unittest.TestCase):
    """base.parse_ts takes any RFC 3339 fraction length on Python 3.9 (keeps 6 digits)."""

    UTC = B.timezone.utc

    def test_nine_digit_fraction_truncates_to_micro(self):
        d = B.parse_ts("2026-11-13T20:59:59.999999999Z")
        self.assertEqual(d, B.datetime(2026, 11, 13, 20, 59, 59, 999999, tzinfo=self.UTC))
        self.assertEqual(d.utcoffset().total_seconds(), 0)

    def test_one_digit_fraction_pads(self):
        d = B.parse_ts("2026-11-13T20:59:59.5Z")
        self.assertEqual(d, B.datetime(2026, 11, 13, 20, 59, 59, 500000, tzinfo=self.UTC))

    def test_offset_and_lowercase_z(self):
        d = B.parse_ts("2026-11-13T15:59:59.123456789-05:00")
        self.assertEqual(d, B.datetime(2026, 11, 13, 20, 59, 59, 123456, tzinfo=self.UTC))
        self.assertEqual(B.parse_ts("2026-11-13T20:59:59.25z").microsecond, 250000)

    def test_naive_still_assumed_utc(self):
        d = B.parse_ts("2026-11-13T20:59:59.1234567")
        self.assertEqual(d, B.datetime(2026, 11, 13, 20, 59, 59, 123456, tzinfo=self.UTC))
        self.assertEqual(B.parse_ts("2026-11-13T20:59:00").tzinfo, self.UTC)
        self.assertEqual(B.parse_ts(B.datetime(2026, 11, 13, 20, 59)).tzinfo, self.UTC)

    def test_existing_forms_unchanged(self):
        self.assertEqual(B.parse_ts("2026-11-13T20:59:00Z"),
                         B.datetime(2026, 11, 13, 20, 59, tzinfo=self.UTC))
        self.assertEqual(B.parse_ts("2026-11-13T20:59:00.123Z").microsecond, 123000)

if __name__ == "__main__":
    unittest.main()
