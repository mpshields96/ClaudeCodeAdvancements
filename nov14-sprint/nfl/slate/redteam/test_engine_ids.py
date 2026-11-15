"""Read-only red-team repros for the Sunday engine (selection_markets, selection_decisions).

Writer: Claude NFL red-team writer (side session of sprint-coord local_<session>).
Scope: tests only. Never edits, merges into, overwrites or reverts engine files.
Imports only selection_markets and selection_decisions (stdlib only). Never imports
odds_feed, sunday_quotes or verify_card. Makes no network calls and uses no key.

Run:
  /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I \
    nov14-sprint/nfl/slate/redteam/test_engine_ids.py -v

Each test name carries its repro number (1-7). Synthetic Odds-API-shaped fixtures
exercise each rule; "real_" tests re-read the saved 06:55:06Z capture and the
recorded results read-only, when those files exist.
"""
import copy
import hashlib
import json
import os
import sys
import unittest
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SLATE = os.path.dirname(HERE)
sys.path.insert(0, SLATE)

ENGINE = ("picker.py", "selection_markets.py", "selection_decisions.py")


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


ENGINE_SHA_BEFORE = {n: _sha(os.path.join(SLATE, n)) for n in ENGINE}

import selection_markets as markets  # noqa: E402
import selection_decisions as decisions  # noqa: E402

assert "odds_feed" not in sys.modules and "sunday_quotes" not in sys.modules and "verify_card" not in sys.modules

REAL_CAPTURE = os.path.expanduser("~/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live/sunday-odds.json")
REAL_SELECTIONS = os.path.join(SLATE, "results", "sunday_20261115_selections.json")
REAL_CANDIDATES = os.path.join(SLATE, "results", "sunday_20261115_candidates.json")

CAPTURED = "2026-11-15T06:55:06Z"
OBSERVED = "2026-11-15T06:55:04Z"
UPDATED = "2026-11-15T06:50:00Z"
RUN = "2026-11-15T07:15:00Z"
DECIDED = "2026-11-15T07:05:00Z"
NOON = "2026-11-15T18:00:00Z"      # 12:00 Chicago -> "early"
LATE = "2026-11-15T21:25:00Z"      # 15:25 Chicago -> "late"


def o(name, price, point=None, description=None):
    out = {"name": name, "price": price}
    if point is not None:
        out["point"] = point
    if description is not None:
        out["description"] = description
    return out


def book(key, markets_):
    return {"key": key, "title": key, "last_update": UPDATED,
            "markets": [{"key": k, "last_update": UPDATED, "outcomes": oo} for k, oo in markets_]}


BOOK_KEYS = ("draftkings", "fanduel", "betmgm", "betrivers")


def game_markets(away, home, total=45.5, spread=3.0, ml=(-150, 130), band_price=-110):
    return [("h2h", [o(away, ml[1]), o(home, ml[0])]),
            ("spreads", [o(away, band_price, spread), o(home, band_price, -spread)]),
            ("totals", [o("Over", band_price, total), o("Under", band_price, total)])]


def event_markets(away, home, line=22.5, total=45.5):
    return [("player_reception_yds", [o("Over", -115, line, "Player A"), o("Under", -115, line, "Player A"),
                                      o("Over", -115, line, "Player B"), o("Under", -115, line, "Player B"),
                                      o("Over", -110, 24.5, "Player A"), o("Under", -110, 24.5, "Player A")]),
            ("totals_h1", [o("Over", -110, total), o("Under", -110, total)]),
            ("team_totals", [o("Over", -110, 20.5, away), o("Under", -110, 20.5, away),
                             o("Over", -110, 20.5, home), o("Under", -110, 20.5, home)])]


def capture_for(games, observed=OBSERVED, captured=CAPTURED, extra_games=None, extra_events=None):
    """games: list of (eid, away, home, kick)."""
    doc = {"captured_utc": captured, "observations": [{"endpoint": "odds", "observed_utc": observed}],
           "games": [], "event_odds": []}
    for eid, away, home, kick in games:
        base = {"id": eid, "commence_time": kick, "away_team": away, "home_team": home}
        gm = (extra_games or {}).get(eid) or game_markets(away, home)
        em = (extra_events or {}).get(eid) or event_markets(away, home)
        doc["games"].append(dict(base, bookmakers=[book(b, gm) for b in BOOK_KEYS]))
        doc["event_odds"].append(dict(base, bookmakers=[book(b, em) for b in BOOK_KEYS]))
        doc["observations"].append({"endpoint": "events/%s/odds" % eid, "observed_utc": observed})
    return doc


def run_collect(doc, run=RUN):
    schedule = {g["id"]: g for g in doc["games"]}
    return markets.collect(doc, None, [], schedule, run)


def priced(doc, run=RUN):
    cands, _, skipped = run_collect(doc, run)
    kick = {g["id"]: g["commence_time"] for g in doc["games"]}
    for c in cands:
        markets.price_candidate(c)
        c["window"] = markets.window(kick[c["event_id"]])
    return cands, skipped


def call(eid, market, subject, side, point, floor=-200):
    return {"event_id": eid, "market": market, "subject": subject, "side": side, "point": point,
            "minimum_price": floor, "rationale": "red-team fixture rationale", "risk": "red-team fixture risk"}


def overlay(calls, decided=DECIDED):
    return {"capture_sha256": "fixture", "author": "red-team fixture", "decided_utc": decided,
            "calls": calls, "window_notes": {}}


def apply(calls, cands, first=NOON, decided=DECIDED, run=RUN):
    return decisions.apply_overlay(overlay(calls, decided), cands, "fixture", CAPTURED, first, run)


ONE = [("E1", "Away One", "Home One", NOON)]
THREE_NOON = [("E1", "Away One", "Home One", NOON), ("E2", "Away Two", "Home Two", NOON),
              ("E3", "Away Three", "Home Three", NOON)]


class Repro1PropIds(unittest.TestCase):
    def test_1_key_for_distinct_players(self):
        a = markets.key_for("E1", "player_reception_yds", "Player A", "Over", 22.5)
        b = markets.key_for("E1", "player_reception_yds", "Player B", "Over", 22.5)
        self.assertNotEqual(a, b)
        self.assertIn("full_game", a)  # period is part of the id

    def test_1_collect_carries_player_as_subject(self):
        cands, _, _ = run_collect(capture_for(ONE))
        rows = [c for c in cands if c["provider_market"] == "player_reception_yds"
                and c["outcome"] == "Over" and c["line"] == 22.5]
        self.assertEqual(sorted(c["subject"] for c in rows), ["Player A", "Player B"])
        self.assertEqual(len({c["id"] for c in rows}), 2)
        for c in rows:
            self.assertIn(c["subject"], c["label"])
            self.assertEqual(len(c["quotes"]), len(BOOK_KEYS))  # quotes were not merged across players

    def test_1_real_capture_player_pairs_distinct(self):
        if not os.path.isfile(REAL_CAPTURE):
            self.skipTest("saved capture not present")
        with open(REAL_CAPTURE) as f:
            doc = json.load(f)
        cands, _, _ = run_collect(doc, "2026-11-15T07:15:44Z")
        props = [c for c in cands if c["market"] == "prop"]
        shared = defaultdict(set)
        for c in props:
            shared[(c["event_id"], c["provider_market"], c["outcome"], c["line"])].add(c["id"])
        multi = {k: v for k, v in shared.items() if len(v) > 1}
        tuples = {(c["event_id"], c["period"], c["provider_market"], c["subject"], c["outcome"], c["line"]) for c in cands}
        self.assertEqual(len(tuples), len(cands), "two candidates share one proposition tuple")
        self.assertEqual(len({c["id"] for c in cands}), len(cands), "id collision in real capture")
        print("\n  [1] real capture: %d candidates, %d prop sides; %d (event,market,side,line) groups hold "
              "2+ players and all keep distinct ids" % (len(cands), len(props), len(multi)))


class Repro2PeriodIds(unittest.TestCase):
    def test_2_totals_vs_totals_h1_same_line(self):
        self.assertNotEqual(markets.key_for("E1", "totals", "", "Over", 45.5),
                            markets.key_for("E1", "totals_h1", "", "Over", 45.5))
        cands, _, _ = run_collect(capture_for(ONE))
        rows = [c for c in cands if c["market"] == "total" and c["outcome"] == "Over" and c["line"] == 45.5]
        self.assertEqual(sorted(c["period"] for c in rows), ["first_half", "full_game"])
        self.assertEqual(len({c["id"] for c in rows}), 2)
        h1 = [c for c in rows if c["period"] == "first_half"][0]
        self.assertTrue(h1["label"].startswith("First half"))


class Repro3TeamTotalIds(unittest.TestCase):
    def test_3_home_away_team_totals_distinct(self):
        cands, _, _ = run_collect(capture_for(ONE))
        rows = [c for c in cands if c["provider_market"] == "team_totals" and c["outcome"] == "Under"]
        self.assertEqual(sorted(c["subject"] for c in rows), ["Away One", "Home One"])
        self.assertEqual(len({c["id"] for c in rows}), 2)

    def test_3_team_total_without_team_is_refused(self):
        doc = capture_for(ONE, extra_events={"E1": [("team_totals", [o("Over", -110, 20.5, "Not A Team"),
                                                                       o("Under", -110, 20.5, "Not A Team")])]})
        cands, _, skipped = run_collect(doc)
        self.assertFalse([c for c in cands if c["provider_market"] == "team_totals"])
        self.assertGreater(skipped.get("malformed outcome", 0), 0)


class Repro4BothSides(unittest.TestCase):
    def setUp(self):
        self.cands, _ = priced(capture_for(ONE))

    def assertRefused(self, calls):
        with self.assertRaises(ValueError) as cm:
            apply(calls, copy.deepcopy(self.cands))
        self.assertIn("Duplicate, opposing, or excess", str(cm.exception))

    def test_4_total_over_and_under(self):
        self.assertRefused([call("E1", "totals", "", "Over", 45.5), call("E1", "totals", "", "Under", 45.5)])

    def test_4_moneyline_both_teams(self):
        self.assertRefused([call("E1", "h2h", "", "Away One", None), call("E1", "h2h", "", "Home One", None)])

    def test_4_spread_both_teams(self):
        self.assertRefused([call("E1", "spreads", "", "Home One", -3.0), call("E1", "spreads", "", "Away One", 3.0)])

    def test_4_player_over_and_under_same_line(self):
        self.assertRefused([call("E1", "player_reception_yds", "Player A", "Over", 22.5),
                            call("E1", "player_reception_yds", "Player A", "Under", 22.5)])

    def test_4_team_total_over_and_under(self):
        self.assertRefused([call("E1", "team_totals", "Home One", "Over", 20.5),
                            call("E1", "team_totals", "Home One", "Under", 20.5)])

    def test_4_opposing_directions_at_different_thresholds(self):
        totals = [o(side, -110, line) for side in ("Over", "Under") for line in (45.5, 47.5)]
        spreads = [o(team, -110, sign * line) for team, sign in (("Home One", -1), ("Away One", 1))
                   for line in (2.5, 3.5)]
        self.cands, _ = priced(capture_for(ONE, extra_games={"E1": [("totals", totals), ("spreads", spreads)]}))
        for market, subject, side, line, other, other_line in (
                ("player_reception_yds", "Player A", "Over", 22.5, "Under", 24.5),
                ("totals", "", "Over", 45.5, "Under", 47.5),
                ("spreads", "", "Home One", -3.5, "Away One", 2.5)):
            with self.subTest(market=market):
                a = call("E1", market, subject, side, line)
                b = call("E1", market, subject, other, other_line)
                for pair in ([a, b], [b, a]):
                    candidates = copy.deepcopy(self.cands)
                    with self.assertRaisesRegex(ValueError, "Duplicate, opposing, or excess"):
                        apply(pair, candidates)
                    self.assertEqual(candidates, self.cands)

    def test_4_different_subject_or_same_direction_can_share_the_game(self):
        a = call("E1", "player_reception_yds", "Player A", "Over", 22.5)
        for subject, side, line in (("Player B", "Under", 22.5), ("Player A", "Over", 24.5)):
            other = call("E1", "player_reception_yds", subject, side, line)
            self.assertEqual(len(apply([a,other], copy.deepcopy(self.cands))), 2)


class Repro5PriceBand(unittest.TestCase):
    def test_5_all_out_of_band_never_callable(self):
        gm = {"E1": [("h2h", [o("Away One", 240), o("Home One", -290)]),
                     ("spreads", [o("Away One", -110, 6.5), o("Home One", -110, -6.5)]),
                     ("totals", [o("Over", -110, 45.5), o("Under", -110, 45.5)])]}
        cands, _ = priced(capture_for(ONE, extra_games=gm))
        ml = {c["outcome"]: c for c in cands if c["provider_market"] == "h2h"}
        for c in ml.values():
            self.assertFalse(c["in_price_band"])
            c["model_estimate"] = 0.9
            self.assertEqual(decisions.screen_reason(c), "All observed prices are outside the personal price band.")
        with self.assertRaises(ValueError):
            apply([call("E1", "h2h", "", "Home One", None, -200)], cands)

    def test_5_best_price_is_inside_band(self):
        doc = capture_for(ONE)
        for b in doc["games"][0]["bookmakers"]:
            for m in b["markets"]:
                if m["key"] == "h2h":
                    m["outcomes"] = [o("Away One", 210 if b["key"] == "draftkings" else 190), o("Home One", -240)]
        cands, _ = priced(doc)
        away = [c for c in cands if c["provider_market"] == "h2h" and c["outcome"] == "Away One"][0]
        self.assertTrue(away["in_price_band"])
        self.assertEqual(away["price"], 190)  # +210 offer is shopped out
        self.assertLessEqual(abs(away["price"]), 200)

    def test_5_floor_outside_band_refused(self):
        cands, _ = priced(capture_for(ONE))
        for floor in (-201, 201, -250, 99, -99):
            with self.assertRaises(ValueError):
                apply([call("E1", "totals", "", "Over", 45.5, floor)], copy.deepcopy(cands))
        for floor in (-200, -110):
            self.assertEqual(len(apply([call("E1", "totals", "", "Over", 45.5, floor)], copy.deepcopy(cands))), 1)

    def test_5_real_selected_calls_in_band(self):
        if not os.path.isfile(REAL_SELECTIONS):
            self.skipTest("no selections file")
        with open(REAL_SELECTIONS) as f:
            sel = json.load(f)
        for c in sel["calls"]:
            self.assertLessEqual(abs(c["price"]), 200, c["id"])
            self.assertLessEqual(abs(c["minimum_price"]), 200, c["id"])
            self.assertGreaterEqual(abs(c["price"]), 100, c["id"])


class Repro6WindowCap(unittest.TestCase):
    def setUp(self):
        self.cands, _ = priced(capture_for(THREE_NOON))

    def test_6_third_call_in_window_refused(self):
        calls = [call("E1", "totals", "", "Over", 45.5), call("E2", "totals", "", "Over", 45.5),
                 call("E3", "totals", "", "Over", 45.5)]
        with self.assertRaises(ValueError):
            apply(calls, copy.deepcopy(self.cands))
        self.assertEqual(len(apply(calls[:2], copy.deepcopy(self.cands))), 2)

    def test_6_distinct_contracts_in_one_game_can_share_a_window(self):
        calls = [call("E1", "totals", "", "Over", 45.5),
                 call("E1", "player_reception_yds", "Player A", "Over", 22.5)]
        candidates = copy.deepcopy(self.cands)
        picks = apply(calls, candidates)
        self.assertEqual(len(set(picks)), 2)
        by_id = {row["id"]: row for row in candidates}
        self.assertEqual(by_id[picks[0]]["same_game_contract_ids"], [picks[1]])
        self.assertEqual(by_id[picks[1]]["same_game_contract_ids"], [picks[0]])

    def test_6_full_game_and_first_half_can_coexist_but_exact_duplicates_cannot(self):
        full = call("E1", "totals", "", "Over", 45.5)
        half = call("E1", "totals_h1", "", "Over", 45.5)
        picks = apply([full, half], copy.deepcopy(self.cands))
        self.assertEqual(len(set(picks)), 2)
        with self.assertRaises(ValueError):
            apply([full, full], copy.deepcopy(self.cands))

    def test_6_real_selections_window_cap(self):
        if not os.path.isfile(REAL_SELECTIONS):
            self.skipTest("no selections file")
        with open(REAL_SELECTIONS) as f:
            sel = json.load(f)
        per = defaultdict(list)
        for c in sel["calls"]:
            per[c["window"]].append(c["event_id"])
        for w, eids in per.items():
            self.assertLessEqual(len(eids), 2, w)
            self.assertEqual(len(eids), len(set(eids)), "same game twice in window " + w)


class Repro7AfterKickoff(unittest.TestCase):
    def test_7_quote_observed_after_kickoff_refused(self):
        doc = capture_for(ONE, observed="2026-11-15T18:05:00Z", captured="2026-11-15T18:05:01Z")
        for e in doc["games"] + doc["event_odds"]:
            for b in e["bookmakers"]:
                b["last_update"] = "2026-11-15T18:00:30Z"
                for m in b["markets"]:
                    m["last_update"] = "2026-11-15T18:00:30Z"
        cands, _, skipped = run_collect(doc, run="2026-11-15T18:10:00Z")
        self.assertEqual(cands, [])
        self.assertGreater(skipped.get("missing or invalid pregame retrieval time", 0), 0)

    def test_7_quote_observed_exactly_at_kickoff_refused(self):
        doc = capture_for(ONE, observed=NOON, captured="2026-11-15T18:00:01Z")
        for e in doc["games"] + doc["event_odds"]:
            for b in e["bookmakers"]:
                for m in b["markets"]:
                    m["last_update"] = "2026-11-15T17:59:00Z"
        cands, _, _ = run_collect(doc, run="2026-11-15T18:10:00Z")
        self.assertEqual(cands, [])

    def test_7_late_game_quote_kept_until_its_own_kickoff(self):
        doc = capture_for([("E1", "Away One", "Home One", NOON), ("E4", "Away Four", "Home Four", LATE)],
                          observed="2026-11-15T19:00:00Z", captured="2026-11-15T19:00:01Z")
        for e in doc["games"] + doc["event_odds"]:
            for b in e["bookmakers"]:
                for m in b["markets"]:
                    m["last_update"] = "2026-11-15T18:59:00Z"
        cands, _, _ = run_collect(doc, run="2026-11-15T19:05:00Z")
        self.assertTrue(cands)
        self.assertEqual({c["event_id"] for c in cands}, {"E4"})

    def test_7_missing_request_time_refused(self):
        doc = capture_for(ONE)
        doc["observations"] = []
        cands, _, skipped = run_collect(doc)
        self.assertEqual(cands, [])
        self.assertGreater(skipped.get("missing or invalid pregame retrieval time", 0), 0)

    def test_7_review_decided_at_or_after_first_kickoff_refused(self):
        cands, _ = priced(capture_for(ONE))
        for decided in (NOON, "2026-11-15T18:00:01Z"):
            with self.assertRaises(ValueError):
                apply([call("E1", "totals", "", "Over", 45.5)], copy.deepcopy(cands),
                      decided=decided, run="2026-11-15T18:30:00Z")

    def test_7_real_candidates_all_pregame(self):
        if not os.path.isfile(REAL_CANDIDATES):
            self.skipTest("no candidates file")
        with open(REAL_CANDIDATES) as f:
            doc = json.load(f)
        n = 0
        for c in doc["slate"]["candidates"]:
            kick = markets.instant(c["kickoff_utc"])
            for q in c["quotes"].values():
                n += 1
                self.assertLess(markets.instant(q["observed_utc"]), kick, c["id"])
        print("\n  [7] real candidates: %d quotes, all observed before their own kickoff" % n)


class EngineUntouched(unittest.TestCase):
    def test_zz_engine_files_unchanged_by_tests(self):
        after = {n: _sha(os.path.join(SLATE, n)) for n in ENGINE}
        self.assertEqual(after, ENGINE_SHA_BEFORE)
        self.assertNotIn("odds_feed", sys.modules)
        self.assertNotIn("sunday_quotes", sys.modules)
        self.assertNotIn("verify_card", sys.modules)


if __name__ == "__main__":
    unittest.main()
