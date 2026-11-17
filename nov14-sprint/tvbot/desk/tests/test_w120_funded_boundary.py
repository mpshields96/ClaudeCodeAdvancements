"""W120 fractional boundary under the operator rule: the per-trade cap is price risk to the stop
only, and fees are budgeted separately inside the daily cap (the daily side is pinned in
test_w120_funded_risk_path.py). The six values below are FICTITIOUS test figures chosen only to
pin the arithmetic; this test writes no limits file and changes no limit."""
import os
import sys
import types
import unittest
from decimal import Decimal

DESK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK_DIR not in sys.path:
    sys.path.insert(0, DESK_DIR)

from strategies import base as B, engine as E  # noqa: E402

TERMS = {"fixed_shares": "0.0021", "per_trade_notional": 1.80, "gross_exposure": 1.80,
         "max_loss_per_trade": 0.03, "daily_loss": 0.06, "max_daily_entries": 1}   # fictitious
BAND = (476.20, 750.0, 857.14)   # $1 minimum notional to the per-trade notional cap at 0.0021 sh
STOP_PCT = 1.5   # bot/rules.py DEFAULT_PARAMS

def _checker():
    return next(v for v in vars(E).values() if isinstance(v, type) and "_max_loss_check" in vars(v))

class FractionalBoundary(unittest.TestCase):
    def setUp(self):
        self.cfg = {"fractional": True, "cost_profile": "alpaca_equity",
                    "limits": {"max_loss_per_trade": TERMS["max_loss_per_trade"]}}
        self.c = B.cost_cfg(self.cfg)
        self.q = Decimal(TERMS["fixed_shares"])

    def _check(self, px):
        est = B.est_cost(self.q, px, self.c, sides=2, note="round trip")
        stop = px * (1 - STOP_PCT / 100.0)
        return est, _checker()._max_loss_check(types.SimpleNamespace(cfg=self.cfg), self.q, px, stop, est)

    def test_round_trip_fees_are_two_cents(self):
        for px in BAND:
            est, _ = self._check(px)
            self.assertAlmostEqual(est["fees"]["day"]["total"], 0.02)
            self.assertEqual(est["fees"]["day"]["taf"], 0.0)

    def test_price_only_cap_passes_across_the_price_band(self):
        # Price risk to the stop is 0.0021 x 1.5% x price = $0.0150 to $0.0270, under the $0.03 cap.
        # Fees (about $0.02 round trip) and modeled spread are reported but count against the daily cap.
        for px in BAND:
            est, chk = self._check(px)
            self.assertTrue(chk["passed"], px)
            self.assertEqual(chk["id"], "MAX_LOSS_WOULD_BREACH")
            self.assertIn("vs cap $0.03", chk["detail"])
            self.assertIn("count against the daily loss cap", chk["detail"])
            risk = float(self.q) * px * STOP_PCT / 100.0
            self.assertLess(risk, TERMS["max_loss_per_trade"])
            self.assertLess(risk + est["usd"], TERMS["daily_loss"])            # 0.036 to 0.049 fits in $0.06
            self.assertGreater(TERMS["max_loss_per_trade"] + risk + est["usd"],
                               TERMS["daily_loss"])                            # but not after a $0.03 loss

    def test_price_risk_over_cap_still_refused_never_resized(self):
        # A stop far enough away that price risk alone exceeds $0.03 is refused, whatever the fees.
        px = 750.0
        est = B.est_cost(self.q, px, self.c, sides=2, note="round trip")
        stop = px - 0.031 / float(self.q)
        chk = _checker()._max_loss_check(types.SimpleNamespace(cfg=self.cfg), self.q, px, stop, est)
        self.assertFalse(chk["passed"])

    def test_notional_band_edges(self):
        cap = Decimal(repr(TERMS["per_trade_notional"]))
        self.assertLessEqual(self.q * Decimal("857.14"), cap)
        self.assertGreater(self.q * Decimal("857.15"), cap)
        self.assertGreaterEqual(self.q * Decimal("476.20"), Decimal("1"))
        self.assertLess(self.q * Decimal("476.19"), Decimal("1"))

    def test_fees_are_what_a_fee_inclusive_cap_would_block(self):
        # Stop + modeled spread fits under the per-trade cap at every band price; stop + spread + fees
        # does not. That is the case the operator rule changes, kept as a pin on the arithmetic.
        for px in BAND:
            est, _ = self._check(px)
            risk = float(self.q) * px * STOP_PCT / 100.0
            no_fee = risk + (est["usd"] - est["fees"]["day"]["total"])
            self.assertLess(no_fee, TERMS["max_loss_per_trade"], px)
            self.assertGreater(risk + est["usd"], TERMS["max_loss_per_trade"], px)

    def test_fictitious_terms_pinned(self):
        self.assertEqual(TERMS, {"fixed_shares": "0.0021", "per_trade_notional": 1.80, "gross_exposure": 1.80,
                                 "max_loss_per_trade": 0.03, "daily_loss": 0.06, "max_daily_entries": 1})

if __name__ == "__main__":
    unittest.main()
