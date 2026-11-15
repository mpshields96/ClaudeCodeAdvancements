#!/usr/bin/env python3
"""Tests for wf.py. Run:
    /usr/bin/python3 -I nov14-sprint/nfl/walkforward/test_wf.py
"""
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wf  # noqa: E402

CFG = json.load(open(wf.PREREG))
GAMES = wf.load_games(wf.DATA, CFG["data"]["sha256"])


class OddsMath(unittest.TestCase):
    def test_implied(self):
        self.assertAlmostEqual(wf.implied(-110), 110 / 210)
        self.assertAlmostEqual(wf.implied(+150), 0.4)
        self.assertAlmostEqual(wf.implied(-200), 2 / 3)
        self.assertAlmostEqual(wf.implied(100), 0.5)

    def test_profit_and_settle(self):
        self.assertAlmostEqual(wf.profit(-110), 100 / 110)
        self.assertAlmostEqual(wf.profit(+150), 1.5)
        self.assertAlmostEqual(wf.profit(-250), 0.4)
        self.assertAlmostEqual(wf.settle("win", -110), 100 / 110)
        self.assertEqual(wf.settle("loss", -110), -1.0)
        self.assertEqual(wf.settle("push", +300), 0.0)
        # breakeven win rate at -110 is 52.38%: EV is zero there
        p = wf.implied(-110)
        self.assertAlmostEqual(p * wf.profit(-110) - (1 - p), 0.0)

    def test_devig(self):
        a, b = wf.devig(-110, -110)
        self.assertAlmostEqual(a, 0.5)
        self.assertAlmostEqual(b, 0.5)
        a, b = wf.devig(-200, +170)
        qa, qb = 2 / 3, 100 / 270
        self.assertAlmostEqual(a, qa / (qa + qb))
        self.assertAlmostEqual(a + b, 1.0)
        self.assertGreater(a, 0.5)

    def test_worse_cents(self):
        self.assertEqual(wf.worse_cents(-110), -120)
        self.assertEqual(wf.worse_cents(+150), +140)
        self.assertEqual(wf.worse_cents(+105), -105)
        self.assertEqual(wf.worse_cents(+110), +100)
        self.assertEqual(wf.worse_cents(-100), -110)
        for o in (-300, -110, 100, 105, 250):
            self.assertLess(wf.profit(wf.worse_cents(o)), wf.profit(o))

    def test_grade_and_half_point(self):
        # home -3 (spread_line 3): home wins by 3 -> push; by 4 -> win
        self.assertEqual(wf.grade("cover", "home", 3.0, 24, 21), "push")
        self.assertEqual(wf.grade("cover", "home", 3.0, 25, 21), "win")
        self.assertEqual(wf.grade("cover", "away", 3.0, 23, 21), "win")
        self.assertEqual(wf.grade("cover", "home", 3.5, 24, 21), "loss")  # half point worse
        self.assertEqual(wf.grade("cover", "away", 2.5, 24, 21), "loss")
        self.assertEqual(wf.grade("over", "over", 44.0, 24, 20), "push")
        self.assertEqual(wf.grade("over", "under", 44.0, 24, 21), "loss")
        self.assertEqual(wf.grade("win", "away", None, 17, 20), "win")
        self.assertEqual(wf.grade("win", "home", None, 20, 20), "push")

    def test_make_bet_stress(self):
        g = {"game_id": "x", "season": 2020, "week": 1, "home_score": 24.0, "away_score": 21.0,
             "spread_line": 3.0, "total_line": 46.0, "ml_home": -150.0, "ml_away": 130.0}
        b = wf.make_bet(g, "cover", "away", 0.55, 0.5, -110.0, False)
        self.assertEqual(b["outcome"], "push")
        self.assertEqual(b["outcome_minus_half_point"], "loss")  # away now +2.5
        self.assertEqual(b["profit_both"], -1.0)
        b = wf.make_bet(g, "over", "under", 0.55, 0.5, -105.0, False)
        self.assertEqual(b["outcome"], "win")
        self.assertAlmostEqual(b["profit_minus_10c"], 100 / 115)


class Logistic(unittest.TestCase):
    def test_recovers_signal_and_penalty_shrinks(self):
        import random
        rng = random.Random(1)
        X, y = [], []
        for _ in range(4000):
            x = rng.gauss(0, 1)
            X.append([x])
            y.append(1 if rng.random() < wf.sigmoid(0.3 + 1.2 * x) else 0)
        w = wf.fit_logistic(X, y, 0.0, 50, 1e-10)
        self.assertAlmostEqual(w[0], 0.3, delta=0.12)
        self.assertAlmostEqual(w[1], 1.2, delta=0.12)
        w5 = wf.fit_logistic(X, y, 500.0, 50, 1e-10)
        self.assertLess(abs(w5[1]), abs(w[1]))


class NoLookahead(unittest.TestCase):
    CUT = "2019-10-20"

    def mutated(self):
        gs = copy.deepcopy(GAMES)
        for g in gs:
            if g["gameday"] >= self.CUT and wf.scored(g):
                g["home_score"], g["away_score"] = g["away_score"] + 17, g["home_score"]
        return gs

    def test_features_ignore_same_day_and_future_scores(self):
        f0 = wf.compute_features(GAMES, CFG)
        f1 = wf.compute_features(self.mutated(), CFG)
        same = [g["game_id"] for g in GAMES if g["gameday"] <= self.CUT]
        later = [g["game_id"] for g in GAMES if g["gameday"] > self.CUT and g["season"] == 2019]
        self.assertTrue(same and later)
        for gid in same:
            self.assertEqual(f0[gid], f1[gid], gid)
        # sanity: the mutation does reach later games, so the test can fail
        self.assertTrue(any(f0[gid] != f1[gid] for gid in later))

    def test_predictions_and_fits_ignore_future(self):
        cfg = copy.deepcopy(CFG)
        cfg["walk_forward"]["test_seasons"] = [2019, 2020]
        p0, _, c0 = wf.walk_forward(GAMES, wf.compute_features(GAMES, cfg), cfg)
        gs = self.mutated()
        p1, _, c1 = wf.walk_forward(gs, wf.compute_features(gs, cfg), cfg)
        day = {g["game_id"]: g["gameday"] for g in GAMES}
        k0 = {(p["game_id"], p["market"]): p["p_model"] for p in p0 if day[p["game_id"]] <= self.CUT}
        k1 = {(p["game_id"], p["market"]): p["p_model"] for p in p1 if day[p["game_id"]] <= self.CUT}
        self.assertTrue(k0)
        self.assertEqual(k0, k1)
        for m in ("win", "cover", "over"):
            self.assertEqual(c0["2019_" + m], c1["2019_" + m])  # 2019 fit uses <=2018 only
            self.assertNotEqual(c0["2020_" + m], c1["2020_" + m])  # 2020 fit sees 2019

    def test_fit_rows_exclude_test_season(self):
        names = CFG["models"]["cover"]["features"]
        feats = wf.compute_features(GAMES, CFG)
        X, y = wf.fit_rows(GAMES, feats, "cover", names, 2002, 2014)
        n = sum(1 for g in GAMES if 2002 <= g["season"] <= 2014 and wf.scored(g)
                and g["spread_line"] is not None and wf.target(g, "cover") is not None)
        self.assertEqual(len(X), n)

    def test_pregame_view_has_no_scores(self):
        v = wf.pregame_view(GAMES[0])
        self.assertNotIn("home_score", v)
        self.assertNotIn("away_score", v)


class Determinism(unittest.TestCase):
    def test_two_runs_identical(self):
        outs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory(prefix="wf_det_") as d:
                r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "wf.py"), "--out", d, "--no-log"],
                                   capture_output=True, text=True, timeout=900)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                h = []
                for name in ("walkforward_results.json", "bets_primary.csv"):
                    with open(os.path.join(d, name), "rb") as fh:
                        h.append(hashlib.sha256(fh.read()).hexdigest())
                outs.append(h)
        self.assertEqual(outs[0], outs[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
