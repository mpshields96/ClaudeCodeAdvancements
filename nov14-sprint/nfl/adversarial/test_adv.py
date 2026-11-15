"""Tests for the adversarial harness (adv_lib.py). Stdlib unittest only.

Run:  /usr/bin/python3 -I -m unittest discover -s <this dir> -p 'test_adv.py' -v
The last test class reads the lane's games.csv read-only and checks two lane numbers.
"""
import csv
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import adv_lib as A  # noqa: E402

GAMES = os.path.join(os.path.dirname(HERE), "data", "raw", "games.csv")


def game(**kw):
    g = {"game_id": "x", "season": 2024, "week": 1, "game_type": "REG", "gameday": "2024-09-08",
         "gametime": "13:00", "weekday": "Sunday", "away": "A", "home": "H", "location": "Home",
         "hs": None, "as": None, "sl": None, "tl": None, "hr": 7.0, "ar": 7.0,
         "hml": None, "aml": None, "hso": None, "aso": None, "uo": None, "oo": None}
    g.update(kw)
    return g


class Pushes(unittest.TestCase):
    def test_spread_exactly_on_line_is_push(self):
        # home favored by 3 (nflverse spread_line 3), home wins by 3
        self.assertEqual(A.grade("spread", "home", 3.0, 20, 17), "P")
        self.assertEqual(A.grade("spread", "away", 3.0, 20, 17), "P")

    def test_spread_cover_directions(self):
        # home dog +7 (spread_line -7): home loses by 6 -> home covers
        self.assertEqual(A.grade("spread", "home", -7.0, 17, 23), "W")
        self.assertEqual(A.grade("spread", "away", -7.0, 17, 23), "L")
        # home loses by 8 -> home does not cover
        self.assertEqual(A.grade("spread", "home", -7.0, 17, 25), "L")

    def test_total_exactly_on_line_is_push(self):
        self.assertEqual(A.grade("total", "under", 47.0, 27, 20), "P")
        self.assertEqual(A.grade("total", "under", 47.5, 27, 20), "W")
        self.assertEqual(A.grade("total", "over", 47.5, 27, 20), "L")

    def test_moneyline_tie_is_push(self):
        self.assertEqual(A.grade("moneyline", "home", None, 20, 20), "P")
        self.assertEqual(A.grade("moneyline", "away", None, 17, 20), "W")
        self.assertEqual(A.grade("moneyline", "home", None, 17, 20), "L")

    def test_push_pays_zero_and_stays_in_denominator(self):
        bets = [(game(hs=20, **{"as": 17}), "spread", "home", 3.0),   # push
                (game(hs=24, **{"as": 17}), "spread", "home", 3.0)]   # win
        s = A.summarize(bets)
        self.assertEqual((s["bets"], s["w"], s["l"], s["p"]), (2, 1, 0, 1))
        self.assertAlmostEqual(s["profit"], 100.0 / 110.0)
        self.assertAlmostEqual(s["roi"], (100.0 / 110.0) / 2)


class PayoutMath(unittest.TestCase):
    def test_profits(self):
        self.assertAlmostEqual(A.payout("W", -110.0), 0.909090909, places=8)
        self.assertAlmostEqual(A.payout("W", 150.0), 1.5)
        self.assertEqual(A.payout("L", -110.0), -1.0)
        self.assertEqual(A.payout("P", -110.0), 0.0)

    def test_implied_and_novig(self):
        self.assertAlmostEqual(A.implied(-110.0), 110.0 / 210.0)
        self.assertAlmostEqual(A.implied(150.0), 0.4)
        a, b = A.novig(-110.0, -110.0)
        self.assertAlmostEqual(a, 0.5)
        self.assertAlmostEqual(a + b, 1.0)

    def test_breakeven_price(self):
        # 110 wins, 100 losses nets zero at -110
        self.assertAlmostEqual(A.breakeven_price(110, 100), -110.0)
        # 1 win per 2 losses needs +200
        self.assertAlmostEqual(A.breakeven_price(1, 2), 200.0)
        self.assertIsNone(A.breakeven_price(0, 5))
        self.assertEqual(A.breakeven_price(5, 0), float("inf"))
        # the breakeven price really nets zero
        w, l = 38, 23
        pr = A.breakeven_price(w, l)
        self.assertAlmostEqual(w * A.american_profit(pr) - l, 0.0, places=9)

    def test_worsen_american_crosses_gap(self):
        self.assertEqual(A.worsen_american(-150.0, 10), -160.0)
        self.assertEqual(A.worsen_american(105.0, 10), -105.0)
        self.assertEqual(A.worsen_american(120.0, 10), 110.0)
        self.assertEqual(A.worsen_american(-110.0, 0), -110.0)

    def test_juice_changes_roi(self):
        bets = [(game(hs=30, **{"as": 10}), "spread", "home", 3.0),
                (game(hs=10, **{"as": 30}), "spread", "home", 3.0)]
        s110 = A.summarize(bets, price=-110.0)
        s120 = A.summarize(bets, price=-120.0)
        self.assertLess(s120["roi"], s110["roi"])


class AdverseLines(unittest.TestCase):
    def test_directions(self):
        self.assertEqual(A.adverse_line("spread", "home", -7.0, 0.5), -6.5)   # +7 becomes +6.5
        self.assertEqual(A.adverse_line("spread", "away", 7.0, 0.5), 6.5)     # away +7 becomes +6.5
        self.assertEqual(A.adverse_line("total", "under", 47.5, 1.0), 46.5)
        self.assertEqual(A.adverse_line("total", "over", 47.5, 1.0), 48.5)

    def test_key_number_hook_loss(self):
        # home dog +7.5 loses by 7: wins at 7.5, pushes at 7, loses at 6.5
        g = game(hs=10, **{"as": 17})
        self.assertEqual(A.grade("spread", "home", -7.5, 10, 17), "W")
        s = A.summarize([(g, "spread", "home", -7.5)], d=0.5)
        self.assertEqual(s["p"], 1)
        s = A.summarize([(g, "spread", "home", -7.5)], d=1.0)
        self.assertEqual(s["l"], 1)


class Decisions(unittest.TestCase):
    def test_home_dog_threshold(self):
        self.assertEqual(A.decide("HOME_DOG", 7, game(sl=-7.0)), (True, "spread", "home"))
        self.assertEqual(A.decide("HOME_DOG", 7, game(sl=-6.5)), (False, "spread", "home"))
        self.assertEqual(A.decide("HOME_DOG", 7, game(sl=None)), (False, "spread", None))

    def test_big_dog_pickem_has_no_side(self):
        self.assertEqual(A.decide("BIG_DOG", 10, game(sl=0.0)), (False, "spread", None))
        self.assertEqual(A.decide("BIG_DOG", 10, game(sl=10.0)), (True, "spread", "away"))
        self.assertEqual(A.decide("BIG_DOG", 10, game(sl=-10.5)), (True, "spread", "home"))

    def test_rest_edge_equal_rest_has_no_side(self):
        self.assertEqual(A.decide("REST_EDGE", 6, game(hr=7.0, ar=7.0)), (False, "spread", None))
        self.assertEqual(A.decide("REST_EDGE", 6, game(hr=13.0, ar=7.0)), (True, "spread", "home"))
        self.assertEqual(A.decide("REST_EDGE", 6, game(hr=7.0, ar=13.0)), (True, "spread", "away"))
        self.assertEqual(A.decide("REST_EDGE", 6, game(hr=None, ar=7.0)), (False, "spread", None))

    def test_high_total_under(self):
        self.assertEqual(A.decide("HIGH_TOTAL_UNDER", 47, game(tl=47.0)), (True, "total", "under"))
        self.assertEqual(A.decide("HIGH_TOTAL_UNDER", 47, game(tl=46.5)), (False, "total", "under"))

    def test_line_override(self):
        g = game(sl=-7.0)
        self.assertEqual(A.decide("HOME_DOG", 7, g, sl=-6.5)[0], False)


class AsOfFiltering(unittest.TestCase):
    def test_cutoff_is_exclusive_and_needs_scores(self):
        gs = [game(game_id="a", gameday="2024-09-01", hs=20, **{"as": 10}),
              game(game_id="b", gameday="2024-09-08", hs=21, **{"as": 14}),   # on cutoff
              game(game_id="c", gameday="2024-09-02", hs=None, **{"as": None}),  # no score
              game(game_id="d", gameday="2024-09-15", hs=3, **{"as": 0})]     # after
        self.assertEqual([g["game_id"] for g in A.as_of(gs, "2024-09-08")], ["a"])

    def test_load_games_parses_na_and_relocations(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "g.csv")
        cols = ["game_id", "season", "week", "game_type", "gameday", "gametime", "weekday",
                "away_team", "home_team", "location", "home_score", "away_score", "spread_line",
                "total_line", "home_rest", "away_rest", "home_moneyline", "away_moneyline",
                "home_spread_odds", "away_spread_odds", "under_odds", "over_odds"]
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerow(["2016_01_OAK_NO", 2016, 1, "REG", "2016-09-11", "13:00", "Sunday", "OAK",
                        "NO", "Home", 34, 35, "NA", 50.5, 7, 7, "NA", "", -110, -110, -110, -110])
        g = A.load_games(p)[0]
        self.assertEqual(g["away"], "LV")
        self.assertIsNone(g["sl"])
        self.assertIsNone(g["hml"])
        self.assertEqual(g["tl"], 50.5)
        self.assertEqual(g["hs"], 34.0)

    def test_elo_walk_never_uses_same_day_results(self):
        # two games on one date: the second game's prediction must not move with the first's result
        import json
        with open(os.path.join(os.path.dirname(HERE), "slate", "frozen_picker.json")) as f:
            fp = json.load(f)
        P = fp.get("params", fp)
        base = [game(game_id="g1", gameday="2024-09-08", home="H1", away="A1", hs=40, sl=0.0, tl=45.0,
                     **{"as": 0}),
                game(game_id="g2", gameday="2024-09-08", home="H1", away="A2", hs=10, sl=0.0, tl=45.0,
                     **{"as": 10})]
        flipped = [dict(base[0], hs=0.0, **{"as": 40.0}), base[1]]
        p1 = A.elo_walk(base, P, "2024-09-09")
        p2 = A.elo_walk(flipped, P, "2024-09-09")
        g2a = [x for x in p1 if x["g"]["game_id"] == "g2"]
        g2b = [x for x in p2 if x["g"]["game_id"] == "g2"]
        self.assertTrue(g2a and g2b)
        self.assertAlmostEqual(g2a[0]["p_home"], g2b[0]["p_home"])


class Stats(unittest.TestCase):
    def test_wilson_and_binom(self):
        lo, hi = A.wilson(38, 61)
        self.assertLess(lo, 38 / 61)
        self.assertGreater(hi, 38 / 61)
        self.assertAlmostEqual(A.binom_sf(0, 10, 0.5), 1.0)
        self.assertAlmostEqual(A.binom_sf(10, 10, 0.5), 0.5 ** 10)

    def test_family_null_shares_coins_and_is_deterministic(self):
        vb = {"a": [("g1", "spread", "home"), ("g2", "spread", "home")],
              "b": [("g1", "spread", "away"), ("g2", "spread", "away")]}
        r1 = A.family_null(vb, sims=200, seed=1)
        r2 = A.family_null(vb, sims=200, seed=1)
        self.assertEqual(r1, r2)
        # opposite sides on shared coins: the best of the two is never a 0-2 result
        self.assertGreater(min(r1), -1.0)


@unittest.skipUnless(os.path.exists(GAMES), "lane games.csv not present")
class LaneReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        games = A.load_games(GAMES)
        cls.reg = [g for g in games if g["game_type"] == "REG" and A.completed(g)]

    def test_home_dog_7_holdout_matches_lane(self):
        hold = [g for g in self.reg if 2023 <= g["season"] <= 2025]
        s = A.summarize(A.bets_for("HOME_DOG", 7, hold))
        self.assertEqual((s["bets"], s["w"], s["l"], s["p"]), (63, 38, 23, 2))
        self.assertAlmostEqual(round(100 * s["roi"], 2), 18.33)

    def test_high_total_under_47_train_matches_lane(self):
        train = [g for g in self.reg if 2006 <= g["season"] <= 2022]
        s = A.summarize(A.bets_for("HIGH_TOTAL_UNDER", 47, train))
        self.assertEqual((s["bets"], s["w"], s["l"], s["p"]), (1304, 673, 614, 17))


class WalkforwardAuditHelpers(unittest.TestCase):
    """Helpers used by audit_walkforward.py: hold, ROI, cheaper-side and the flat re-price."""

    def setUp(self):
        import audit_walkforward as W
        self.W = W

    def test_hold(self):
        self.assertAlmostEqual(self.W.hold(-110, -110), 0.047619, places=5)
        self.assertAlmostEqual(self.W.hold(-105, -105), 0.024390, places=5)
        self.assertAlmostEqual(self.W.hold(100, -100), 0.0, places=9)

    def test_roi_counts_pushes_in_denominator(self):
        rows = [{"x": A.payout("W", -110)}, {"x": A.payout("L", -110)}, {"x": A.payout("P", -110)}]
        self.assertAlmostEqual(self.W.roi(rows, "x"), round(100 * (0.909091 - 1) / 3, 2), places=2)
        self.assertIsNone(self.W.roi([], "x"))

    def test_flat_reprice_removes_cheap_juice_advantage(self):
        # A 51-49 record is +EV at +100 (the cheaper side) but -EV at a flat -110.
        at_plus100 = 51 * A.payout("W", 100) + 49 * A.payout("L", 100)
        at_flat = 51 * A.payout("W", -110) + 49 * A.payout("L", -110)
        self.assertGreater(at_plus100, 0)
        self.assertLess(at_flat, 0)
        self.assertTrue(A.implied(100) < A.implied(-120))

    def test_num_parses_missing(self):
        self.assertIsNone(self.W.num("NA"))
        self.assertIsNone(self.W.num(""))
        self.assertEqual(self.W.num("-3.5"), -3.5)


if __name__ == "__main__":
    unittest.main()
