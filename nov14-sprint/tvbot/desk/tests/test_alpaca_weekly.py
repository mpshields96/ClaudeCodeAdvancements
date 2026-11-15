from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alpaca.weekly import fill_economics, render_week


class WeeklyPaperReview(unittest.TestCase):
    def test_stress_counts_filled_orders_not_fill_fragments(self):
        trips = [{"gross_pnl": 1.5, "fills": [{"intent_id": "entry"}, {"intent_id": "entry"},
                                              {"intent_id": "close"}]}]
        self.assertEqual(fill_economics(trips), (1.5, -0.5))
        self.assertEqual(fill_economics([]), (0.0, 0.0))
        self.assertEqual(fill_economics([{"gross_pnl": 0.0, "fills": [{}]}]), (None, None))

    def test_paper_provenance_and_unconfirmed_stop(self):
        session = {"broker_mode": "alpaca-paper", "controls": {"stopped": True, "flat_confirmed": False},
                   "sizing": {"fixed_qty": 3}, "limits_source": {"provenance": "operator-approved"}}
        week = {"best_pass": {"decision": {"reason_text": "<example>"}}, "comparison": [{"metric": "passes", "value": 1}]}
        html = render_week("", session, week, "2026-W46")
        self.assertIn("Alpaca paper simulator fills", html)
        self.assertIn("Account fees are unverified", html)
        self.assertIn("awaiting broker confirmation", html)
        self.assertIn("&lt;example&gt;", html)
        self.assertNotIn("venue confirmed flat.", html)
        self.assertNotIn("synthetic SPY bars", html)
        session["broker_mode"] = "alpaca-mock"
        session["controls"]["flat_confirmed"] = True
        html = render_week("", session, {}, None)
        self.assertIn("synthetic SPY bars", html)
        self.assertIn("venue confirmed flat.", html)
        self.assertIn("No recorded week", html)


if __name__ == "__main__":
    unittest.main()
