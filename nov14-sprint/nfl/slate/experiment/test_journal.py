#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Tests for journal.py. Every fixture here is made up for the test; no real price is used.

Run (any folder):
  /usr/bin/env -i PATH=/usr/bin:/bin TMPDIR=<a temp folder> /usr/bin/python3 -I -B test_journal.py
"""
import ast
import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import journal as J  # noqa: E402

EV1, EV2 = "a" * 32, "b" * 32
HOME1, AWAY1 = "Atlanta Falcons", "Kansas City Chiefs"
HOME2, AWAY2 = "Green Bay Packers", "Minnesota Vikings"
KICK1, KICK2 = "2026-11-15T18:00:00Z", "2026-11-15T21:25:00Z"
CAPTURED, QUOTE = "2026-11-15T06:55:00Z", "2026-11-15T06:50:00Z"
PLAYER = "Bijan Robinson"


def T(text):
    return J.parse_utc(text)


NOW = T("2026-11-15T07:30:00Z")           # before both kickoffs
AFTER1 = T("2026-11-15T22:00:00Z")        # game 1 can be final
AFTER2 = T("2026-11-16T00:30:00Z")        # game 2 can be final


def o(name, price, point=None, description=None):
    out = {"name": name, "price": price}
    if point is not None:
        out["point"] = point
    if description is not None:
        out["description"] = description
    return out


def mk(key, outcomes, when=QUOTE):
    return {"key": key, "last_update": when, "outcomes": outcomes}


def bk(key, markets, when=QUOTE):
    return {"key": key, "title": key, "last_update": when, "markets": markets}


def capture(captured=CAPTURED, quote=QUOTE):
    """Two games, three books. BetMGM's home moneyline (-205) is outside the price band."""
    return {
        "captured_utc": captured,
        "games": [
            {"id": EV1, "commence_time": KICK1, "home_team": HOME1, "away_team": AWAY1, "bookmakers": [
                bk("draftkings", [mk("h2h", [o(HOME1, -150), o(AWAY1, 130)], quote),
                                  mk("spreads", [o(HOME1, -110, -2.5), o(AWAY1, -110, 2.5)], quote),
                                  mk("totals", [o("Over", -110, 41), o("Under", -110, 41)], quote)], quote),
                bk("fanduel", [mk("h2h", [o(HOME1, -145), o(AWAY1, 125)], quote),
                               mk("spreads", [o(HOME1, -105, -2.5), o(AWAY1, -115, 2.5)], quote),
                               mk("totals", [o("Over", -108, 41), o("Under", -112, 41)], quote)], quote),
                bk("betmgm", [mk("h2h", [o(HOME1, -205), o(AWAY1, 170)], quote)], quote)]},
            {"id": EV2, "commence_time": KICK2, "home_team": HOME2, "away_team": AWAY2, "bookmakers": [
                bk("draftkings", [mk("h2h", [o(HOME2, -120), o(AWAY2, 100)], quote),
                                  mk("spreads", [o(HOME2, -110, -1), o(AWAY2, -110, 1)], quote)], quote),
                bk("fanduel", [mk("h2h", [o(HOME2, -118), o(AWAY2, -102)], quote)], quote)]},
        ],
        "event_odds": [
            {"id": EV1, "commence_time": KICK1, "home_team": HOME1, "away_team": AWAY1, "bookmakers": [
                {"key": "draftkings", "title": "DraftKings", "markets": [
                    mk("totals_h1", [o("Over", -110, 20.5), o("Under", -110, 20.5)], quote),
                    mk("team_totals", [o("Over", -115, 21.5, HOME1), o("Under", -105, 21.5, HOME1)], quote),
                    mk("player_rush_yds", [o("Over", -110, 60.5, PLAYER), o("Under", -110, 60.5, PLAYER)], quote)]}]},
        ],
    }


def cid(market, side, point=None, subject="", event=EV1):
    return J.candidate_id(event, market, subject, point, side)


HOME_ML = cid("h2h", HOME1)
AWAY_ML = cid("h2h", AWAY1)
HOME_SPREAD = cid("spreads", HOME1, -2.5)
AWAY_SPREAD = cid("spreads", AWAY1, 2.5)
OVER = cid("totals", "Over", 41)
UNDER = cid("totals", "Under", 41)
H1_OVER = cid("totals_h1", "Over", 20.5)
TT_OVER = cid("team_totals", "Over", 21.5, HOME1)
TT_UNDER = cid("team_totals", "Under", 21.5, HOME1)
PROP_OVER = cid("player_rush_yds", "Over", 60.5, PLAYER)
PROP_UNDER = cid("player_rush_yds", "Under", 60.5, PLAYER)
EV2_HOME_ML = cid("h2h", HOME2, event=EV2)
EV2_HOME_SPREAD = cid("spreads", HOME2, -1, event=EV2)
EV2_AWAY_SPREAD = cid("spreads", AWAY2, 1, event=EV2)


def calls_doc():
    return {"decided_utc": "2026-11-15T07:20:00Z", "calls": [
        {"event_id": EV1, "market": "spreads", "side": HOME1, "subject": "", "point": -2.5,
         "minimum_price": -110, "price": -105, "book": "fanduel", "updated": QUOTE, "kickoff": KICK1,
         "label": "Falcons -2.5", "rationale": "made up for the test", "risk": "made up"}]}


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journal-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.j = J.Journal(os.path.join(self.tmp, "data"))

    def write(self, name, obj):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return path

    def load(self, cap=None, now=NOW, name="capture.json"):
        path = self.write(name, cap if cap is not None else capture())
        return J.import_capture(self.j, path, now), path

    def load_calls(self, doc=None, now=NOW, late=False, name="calls.json"):
        path = self.write(name, doc if doc is not None else calls_doc())
        return J.import_calls(self.j, path, now, late=late)

    def raw(self, name):
        with open(self.j.path(name), "rb") as fh:
            return fh.read()

    def state(self):
        return J.State(self.j)

    def finals(self):
        J.record_final(self.j, "falcons", 21, 20, "made-up box score", AFTER1)
        J.record_final(self.j, "packers", 21, 20, "made-up box score", AFTER2)

    def grade(self, c, **kw):
        s = self.state()
        return J.grade_at(s.original(c), s, **kw)


class IdentityTests(Base):
    def test_same_bet_gives_the_same_id_whatever_the_spacing_or_case(self):
        a = J.candidate_id(EV1, "player_rush_yds", "Bijan Robinson", 60.5, "Over")
        b = J.candidate_id(EV1.upper(), "player_rush_yds", "  bijan   ROBINSON ", 60.50, "over")
        self.assertEqual(a, b)
        self.assertEqual(J.candidate_id(EV1, "spreads", "", 0, HOME1), J.candidate_id(EV1, "spreads", "", -0.0, HOME1))

    def test_every_part_of_the_identity_changes_the_id(self):
        base = (EV1, "team_totals", HOME1, 21.5, "Over")
        variants = [(EV2,) + base[1:],                               # event
                    (EV1, "team_totals_h1") + base[2:],               # period
                    (EV1, "totals") + base[2:],                       # market
                    (EV1, "team_totals", AWAY1, 21.5, "Over"),        # team or player
                    (EV1, "team_totals", HOME1, 22.5, "Over"),        # exact line
                    (EV1, "team_totals", HOME1, 21.5, "Under")]       # side
        ids = set(J.candidate_id(*v) for v in variants)
        ids.add(J.candidate_id(*base))
        self.assertEqual(len(ids), 7)

    def test_the_stored_record_names_all_six_parts(self):
        self.load()
        rec = self.state().original(H1_OVER)
        self.assertEqual(rec["identity"], {"event_id": EV1, "period": "h1", "market": "totals_h1",
                                           "subject": "", "point": 20.5, "side": "Over"})
        self.assertEqual(self.state().original(PROP_OVER)["identity"]["subject"], PLAYER)
        self.assertEqual(self.state().original(HOME_ML)["identity"]["point"], None)

    def test_a_short_id_must_match_one_bet_only(self):
        self.load()
        s = self.state()
        self.assertEqual(s.resolve(HOME_ML[:8]), HOME_ML)
        with self.assertRaises(J.JournalError):
            s.resolve("zzzz")
        with self.assertRaises(J.JournalError):
            s.resolve("ab")


class AppendOnlyTests(Base):
    def test_a_fresh_journal_verifies(self):
        self.load()
        counts, problems = self.j.verify()
        self.assertEqual(problems, [])
        self.assertEqual(counts["predictions"], 16)

    def test_an_edited_line_is_detected_and_blocks_further_writes(self):
        self.load()
        path = self.j.path("predictions")
        text = self.raw("predictions").decode("utf-8")
        self.assertIn('"price":-145', text)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace('"price":-145', '"price":-130', 1))
        counts, problems = self.j.verify()
        self.assertIsNone(counts["predictions"])
        self.assertEqual(len(problems), 1)
        with self.assertRaises(J.JournalError):
            self.load(capture(captured="2026-11-15T07:10:00Z", quote="2026-11-15T07:05:00Z"), name="c2.json")
        with self.assertRaises(J.JournalError):
            J.record_decision(self.j, HOME_ML, "take", "a reason", NOW)

    def test_a_deleted_line_is_detected(self):
        self.load()
        lines = self.raw("predictions").decode("utf-8").splitlines(True)
        with open(self.j.path("predictions"), "w", encoding="utf-8") as fh:
            fh.writelines(lines[:3] + lines[4:])
        self.assertEqual(len(self.j.verify()[1]), 1)

    def test_a_record_cannot_set_its_own_time_or_sequence(self):
        for field in ("seq", "recorded_utc", "prev", "sha"):
            with self.assertRaises(J.JournalError):
                self.j.append("closes", {field: "x"}, NOW)

    def test_the_write_time_is_the_clock_not_the_caller(self):
        self.load()
        d = J.record_decision(self.j, HOME_ML, "take", "a reason", NOW)
        self.assertEqual(d["recorded_utc"], "2026-11-15T07:30:00Z")
        t = J.record_ticket(self.j, HOME_ML, "FanDuel", -150, 5, NOW, placed_utc="2026-11-15T07:00:00Z")
        self.assertEqual(t["recorded_utc"], "2026-11-15T07:30:00Z")
        self.assertEqual(t["placed_utc_reported"], "2026-11-15T07:00:00Z")


class OriginalNeverChangesTests(Base):
    def test_loading_the_same_capture_twice_adds_nothing(self):
        first, path = self.load()
        before = self.raw("predictions")
        again = J.import_capture(self.j, path, NOW)
        self.assertEqual(first["new_records"], 16)
        self.assertEqual(again["new_records"], 0)
        self.assertEqual(again["already_recorded"], 16)
        self.assertEqual(self.raw("predictions"), before)

    def test_a_newer_capture_is_appended_and_the_first_price_stays_the_original(self):
        self.load()
        before = self.raw("predictions")
        newer = capture(captured="2026-11-15T07:10:00Z", quote="2026-11-15T07:05:00Z")
        newer["games"][0]["bookmakers"][1]["markets"][0]["outcomes"][0]["price"] = -125
        self.load(newer, name="newer.json")
        after = self.raw("predictions")
        self.assertTrue(after.startswith(before))
        self.assertGreater(len(after), len(before))
        s = self.state()
        self.assertEqual(s.original(HOME_ML)["price"], -145)
        self.assertEqual(s.original(HOME_ML)["quote_utc"], QUOTE)
        self.assertEqual([r["price"] for r in s.records[HOME_ML]], [-145, -125])

    def test_decisions_tickets_finals_grading_and_the_report_leave_predictions_untouched(self):
        self.load()
        self.load_calls()
        before = self.raw("predictions")
        J.record_hypothesis(self.j, "The Falcons run game controls this one and they cover.", NOW, events=["falcons"])
        J.record_decision(self.j, HOME_SPREAD, "alternative", "prefer the points", NOW, alt=AWAY_SPREAD)
        J.record_decision(self.j, HOME_ML, "take", "a reason", NOW, price=-160, book="BetMGM")
        J.record_ticket(self.j, HOME_ML, "BetMGM", -160, 10, NOW, placed_utc=J.stamp(NOW))
        J.record_ticket(self.j, HOME_SPREAD, "FanDuel", -180, 10, NOW, placed_utc=J.stamp(NOW), point=-0.5)
        self.finals()
        J.record_void(self.j, PROP_OVER, "player inactive", "made-up report", AFTER1)
        J.evaluate(self.state())
        J.write_report(self.j, AFTER2)
        self.assertEqual(self.raw("predictions"), before)
        self.assertEqual(self.j.verify()[1], [])

    def test_a_bot_call_is_kept_word_for_word_beside_the_capture_record(self):
        self.load()
        r = self.load_calls()
        self.assertEqual((r["new_records"], r["refused"]), (1, []))
        s = self.state()
        call = s.original(HOME_SPREAD)
        self.assertEqual(call["role"], "call")
        self.assertEqual(call["original"], calls_doc()["calls"][0])
        self.assertEqual((call["price"], call["book"], call["quote_utc"]), (-105, "fanduel", QUOTE))
        self.assertEqual(call["identity"]["point"], -2.5)
        self.assertEqual(s.pool(HOME_SPREAD)["role"], "pool")
        self.assertEqual(self.load_calls()["new_records"], 0)

    def test_a_decision_copies_the_bot_line_it_was_made_against(self):
        self.load()
        d = J.record_decision(self.j, HOME_ML, "pass", "price too short", NOW)
        self.assertEqual(d["bot_original"]["price"], -145)
        self.assertEqual(d["bot_original"]["book"], "fanduel")
        self.assertEqual(d["bot_original"]["quote_utc"], QUOTE)
        self.assertEqual(d["bot_original"]["kickoff_utc"], KICK1)


class PriceBandTests(Base):
    def test_band_edges(self):
        self.assertTrue(J.in_band(-200))
        self.assertFalse(J.in_band(-201))
        self.assertTrue(J.in_band(200))
        self.assertFalse(J.in_band(201))
        self.assertTrue(J.in_band(-100))
        self.assertTrue(J.in_band(100))
        self.assertFalse(J.in_band(-700))
        self.assertFalse(J.in_band(50))

    def test_the_recorded_price_is_the_best_one_inside_the_band(self):
        self.load()
        s = self.state()
        home, away = s.original(HOME_ML), s.original(AWAY_ML)
        self.assertEqual((home["price"], home["book"], home["in_band"]), (-145, "fanduel", True))
        self.assertEqual((away["price"], away["book"]), (170, "betmgm"))
        self.assertEqual(sorted(home["quotes"]), ["betmgm", "draftkings", "fanduel"])
        self.assertEqual(home["quotes"]["betmgm"]["price"], -205)

    def test_a_bet_no_book_prices_inside_the_band_is_kept_and_flagged(self):
        cap = capture()
        for b in cap["games"][0]["bookmakers"]:
            b["markets"][0]["outcomes"] = [o(HOME1, -700), o(AWAY1, 480)]
        self.load(cap)
        s = self.state()
        self.assertFalse(s.original(HOME_ML)["in_band"])
        self.assertFalse(s.original(AWAY_ML)["in_band"])
        self.assertEqual(s.original(HOME_ML)["price"], -700)
        self.assertEqual(J.search(s, ["falcons", "win"], NOW, band_only=True), [])


class PregameGuardTests(Base):
    def test_a_decision_at_or_after_kickoff_is_refused(self):
        self.load()
        with self.assertRaises(J.JournalError):
            J.record_decision(self.j, HOME_ML, "take", "a reason", T(KICK1))
        with self.assertRaises(J.JournalError):
            J.record_decision(self.j, HOME_ML, "pass", "a reason", AFTER1)
        self.assertEqual(self.state().decisions, [])

    def test_a_late_decision_is_kept_but_not_scored(self):
        self.load()
        d = J.record_decision(self.j, HOME_ML, "take", "hindsight", AFTER1, late=True)
        self.assertFalse(d["pregame"])
        self.finals()
        ev = J.evaluate(self.state())
        self.assertEqual(ev["decisions"], [])
        self.assertEqual(ev["score"]["your_takes"]["n"], 0)
        self.assertEqual(len(ev["late_decisions"]), 1)

    def test_an_alternative_must_also_be_before_its_own_kickoff(self):
        self.load()
        between = T("2026-11-15T19:00:00Z")   # game 1 started, game 2 not
        with self.assertRaises(J.JournalError):
            J.record_decision(self.j, EV2_HOME_ML, "alternative", "a reason", between, alt=HOME_ML)
        J.record_decision(self.j, EV2_HOME_ML, "take", "a reason", between)

    def test_a_reason_is_required_and_the_action_must_be_known(self):
        self.load()
        with self.assertRaises(J.JournalError):
            J.record_decision(self.j, HOME_ML, "take", "  ", NOW)
        with self.assertRaises(J.JournalError):
            J.record_decision(self.j, HOME_ML, "maybe", "a reason", NOW)
        with self.assertRaises(J.JournalError):
            J.record_decision(self.j, HOME_ML, "alternative", "a reason", NOW)
        with self.assertRaises(J.JournalError):
            J.record_decision(self.j, HOME_ML, "alternative", "a reason", NOW, alt=HOME_ML)
        with self.assertRaises(J.JournalError):
            J.record_decision(self.j, HOME_ML, "pass", "a reason", NOW, price=-120)

    def test_a_change_of_mind_needs_revise_and_both_entries_are_kept(self):
        self.load()
        J.record_decision(self.j, HOME_ML, "take", "first thought", NOW)
        with self.assertRaises(J.JournalError):
            J.record_decision(self.j, HOME_ML, "pass", "second thought", NOW)
        d2 = J.record_decision(self.j, HOME_ML, "pass", "second thought", NOW, revise=True)
        self.assertEqual(d2["revision_of_seq"], 1)
        self.assertEqual([d["action"] for d in self.state().decisions], ["take", "pass"])
        self.finals()
        ev = J.evaluate(self.state())
        self.assertEqual(len(ev["decisions"]), 1)
        self.assertEqual((ev["decisions"][0]["action"], ev["decisions"][0]["entries"]), ("pass", 2))
        self.assertEqual(ev["score"]["your_takes"]["n"], 0)
        self.assertEqual(ev["score"]["bets_you_passed"]["win"], 1)

    def test_a_hypothesis_is_hashed_timestamped_and_refused_after_kickoff(self):
        self.load()
        text = "Kansas City throws short all day, so the first half stays under the total."
        h = J.record_hypothesis(self.j, text, NOW, events=["chiefs"])
        self.assertEqual(h["text_sha256"], hashlib.sha256(text.encode("utf-8")).hexdigest())
        self.assertEqual((h["recorded_utc"], h["pregame"], h["event_ids"]), ("2026-11-15T07:30:00Z", True, [EV1]))
        with self.assertRaises(J.JournalError):
            J.record_hypothesis(self.j, text, NOW, events=["chiefs"])            # same text twice
        with self.assertRaises(J.JournalError):
            J.record_hypothesis(self.j, text + " Really.", T(KICK1), events=["chiefs"])
        with self.assertRaises(J.JournalError):
            J.record_hypothesis(self.j, "A slate-wide claim written after the first game began.", AFTER1)
        with self.assertRaises(J.JournalError):
            J.record_hypothesis(self.j, "too short", NOW)
        late = J.record_hypothesis(self.j, text + " Really.", AFTER1, events=["chiefs"], late=True)
        self.assertFalse(late["pregame"])

    def test_quotes_dated_after_the_capture_or_at_kickoff_are_left_out(self):
        cap = capture()
        cap["games"][0]["bookmakers"][0]["markets"][0]["last_update"] = "2026-11-15T07:00:00Z"   # after capture
        cap["games"][0]["bookmakers"][1]["markets"][0]["last_update"] = KICK1                    # at kickoff
        rows, skipped, _ = J.contracts_from_capture(cap)
        self.assertEqual(skipped["quote_after_capture_or_kickoff"], 4)
        home = [r for r in rows if r["cid"] == HOME_ML][0]
        self.assertEqual(sorted(home["quotes"]), ["betmgm"])

    def test_a_game_already_started_at_capture_time_is_left_out(self):
        cap = capture(captured="2026-11-15T18:30:00Z", quote="2026-11-15T18:25:00Z")
        rows, skipped, _ = J.contracts_from_capture(cap)
        self.assertEqual(skipped["game_started"], 2)                 # game 1 in both sections
        self.assertEqual(set(r["identity"]["event_id"] for r in rows), set([EV2]))

    def test_stale_and_untimed_quotes_are_left_out(self):
        cap = capture()
        cap["games"][1]["bookmakers"][1]["markets"][0]["last_update"] = "2026-11-15T06:00:00Z"   # 55 minutes old
        del cap["event_odds"][0]["bookmakers"][0]["markets"][0]["last_update"]
        rows, skipped, _ = J.contracts_from_capture(cap)
        self.assertEqual(skipped["stale_quote"], 2)
        self.assertEqual(skipped["no_quote_time"], 2)
        self.assertNotIn(H1_OVER, [r["cid"] for r in rows])

    def test_a_capture_dated_after_the_clock_is_refused(self):
        with self.assertRaises(J.JournalError):
            self.load(now=T("2026-11-15T06:00:00Z"))
        self.assertFalse(os.path.exists(self.j.path("predictions")))

    def test_a_final_is_refused_before_the_game_could_have_ended(self):
        self.load()
        for when in (NOW, T(KICK1), T("2026-11-15T20:29:00Z")):
            with self.assertRaises(J.JournalError):
                J.record_final(self.j, "falcons", 21, 20, "made up", when)
            with self.assertRaises(J.JournalError):
                J.record_player_result(self.j, "falcons", PLAYER, "player_rush_yds", 75, "made up", when)
        J.record_final(self.j, "falcons", 21, 20, "made up", T("2026-11-15T20:30:00Z"))
        with self.assertRaises(J.JournalError):
            J.record_final(self.j, "packers", 21, 20, "made up", AFTER1)   # game 2 not over yet
        with self.assertRaises(J.JournalError):
            J.record_final(self.j, "packers", 21, 20, "", AFTER2)          # no source

    def test_bot_calls_are_refused_after_kickoff_or_with_a_post_kickoff_quote(self):
        self.load()
        r = self.load_calls(now=AFTER1)
        self.assertEqual(r["new_records"], 0)
        self.assertEqual(len(r["refused"]), 1)
        doc = calls_doc()
        doc["calls"][0]["updated"] = "2026-11-15T18:05:00Z"
        r = self.load_calls(doc, name="calls2.json")
        self.assertEqual((r["new_records"], len(r["refused"])), (0, 1))
        r = self.load_calls(now=AFTER1, late=True, name="calls3.json")
        self.assertEqual(r["new_records"], 1)
        self.assertFalse(self.state().original(HOME_SPREAD)["pregame_verified"])


class CallImportTests(Base):
    def test_incomplete_calls_are_refused_one_by_one_and_never_guessed(self):
        self.load()
        doc = calls_doc()
        good = doc["calls"][0]
        no_line = dict(good, point=None)
        no_price = dict((k, v) for k, v in good.items() if k not in ("price", "minimum_price"))
        no_side = dict((k, v) for k, v in good.items() if k != "side")
        unknown_game = dict(good, event_id="c" * 32)
        del unknown_game["kickoff"]
        doc["calls"] = [no_line, no_price, no_side, unknown_game, good, dict(good)]
        r = self.load_calls(doc)
        self.assertEqual(r["new_records"], 1)
        self.assertEqual(len(r["refused"]), 5)
        self.assertEqual(len(self.state().first_by_role("call")), 1)

    def test_a_call_with_only_a_minimum_price_is_recorded_at_that_price_and_says_so(self):
        self.load()
        doc = calls_doc()
        del doc["calls"][0]["price"]
        self.load_calls(doc)
        call = self.state().original(HOME_SPREAD)
        self.assertEqual(call["price"], -110)
        self.assertIn("minimum", call["price_basis"])

    def test_a_file_without_a_calls_list_is_refused(self):
        self.load()
        with self.assertRaises(J.JournalError):
            self.load_calls({"picks": []})


class GradingTests(Base):
    def setUp(self):
        Base.setUp(self)
        self.load()

    def test_nothing_is_graded_before_a_final_is_entered(self):
        g = self.grade(HOME_ML)
        self.assertEqual((g["result"], g["units"]), ("unknown", None))
        J.record_decision(self.j, HOME_ML, "take", "a reason", NOW)
        ev = J.evaluate(self.state())
        t = ev["score"]["your_takes"]
        self.assertEqual((t["n"], t["unknown"], t["decided"], t["units"], t["win_rate"]), (1, 1, 0, 0.0, None))

    def test_moneyline_spread_total_and_team_total_at_21_to_20(self):
        self.finals()
        expect = {HOME_ML: "win", AWAY_ML: "loss", HOME_SPREAD: "loss", AWAY_SPREAD: "win",
                  OVER: "push", UNDER: "push", TT_OVER: "loss", TT_UNDER: "win",
                  EV2_HOME_ML: "win", EV2_HOME_SPREAD: "push", EV2_AWAY_SPREAD: "push"}
        for c, want in expect.items():
            self.assertEqual(self.grade(c)["result"], want, self.state().original(c)["label"])

    def test_units_use_the_recorded_price_and_a_push_returns_the_stake(self):
        self.finals()
        self.assertAlmostEqual(self.grade(HOME_ML)["units"], 100.0 / 145.0)      # won at -145
        self.assertAlmostEqual(self.grade(AWAY_SPREAD)["units"], 100.0 / 110.0)  # won at -110
        self.assertEqual(self.grade(HOME_SPREAD)["units"], -1.0)
        self.assertEqual(self.grade(OVER)["units"], 0.0)
        self.assertEqual(self.grade(EV2_HOME_SPREAD)["units"], 0.0)
        self.assertAlmostEqual(J.profit(130, "win"), 1.3)
        self.assertAlmostEqual(J.profit(-200, "win", 10), 5.0)
        self.assertIsNone(J.profit(-110, "unknown"))

    def test_a_tied_game_pushes_the_moneyline(self):
        J.record_final(self.j, "falcons", 20, 20, "made up", AFTER1)
        self.assertEqual(self.grade(HOME_ML)["result"], "push")
        self.assertEqual(self.grade(AWAY_ML)["units"], 0.0)

    def test_a_first_half_bet_stays_unknown_until_the_half_score_is_entered(self):
        self.finals()
        g = self.grade(H1_OVER)
        self.assertEqual((g["result"], g["units"]), ("unknown", None))
        self.assertIn("first-half", g["detail"])
        J.record_final(self.j, "falcons", 21, 20, "made up", AFTER1, h1_home=10, h1_away=14)
        self.assertEqual(self.grade(H1_OVER)["result"], "win")
        with self.assertRaises(J.JournalError):
            J.record_final(self.j, "falcons", 21, 20, "made up", AFTER1, h1_home=10)

    def test_a_player_bet_stays_unknown_until_his_number_is_entered(self):
        self.finals()
        self.assertEqual(self.grade(PROP_OVER)["result"], "unknown")
        J.record_player_result(self.j, "falcons", "bijan robinson", "player_rush_yds", 75, "made up", AFTER1)
        self.assertEqual(self.grade(PROP_OVER)["result"], "win")
        self.assertEqual(self.grade(PROP_UNDER)["result"], "loss")

    def test_a_void_returns_the_stake_whatever_the_score(self):
        self.finals()
        J.record_void(self.j, HOME_SPREAD, "made-up void", "made up", AFTER1)
        g = self.grade(HOME_SPREAD)
        self.assertEqual((g["result"], g["units"]), ("void", 0.0))

    def test_a_corrected_final_is_appended_and_the_latest_one_counts(self):
        self.finals()
        J.record_final(self.j, "falcons", 17, 20, "made-up correction", AFTER1)
        self.assertEqual(self.grade(HOME_ML)["result"], "loss")
        self.assertEqual(len([f for f in self.state().finals if f["event_id"] == EV1]), 2)

    def test_a_ticket_is_graded_at_its_own_price_and_line_and_the_bot_line_is_unchanged(self):
        J.record_ticket(self.j, HOME_ML, "BetMGM", -160, 10, NOW, placed_utc=J.stamp(NOW))
        J.record_ticket(self.j, HOME_SPREAD, "FanDuel", -180, 20, NOW, placed_utc=J.stamp(NOW), point=-0.5)
        self.finals()
        ev = J.evaluate(self.state())
        a, b = ev["tickets"]
        self.assertEqual((a["result"], a["price"], a["bot_price"]), ("win", -160, -145))
        self.assertAlmostEqual(a["units"], 6.25)
        self.assertEqual((b["result"], b["line_differs"]), ("win", True))      # -0.5 wins by one point
        self.assertAlmostEqual(b["units"], 20 * 100.0 / 180.0)
        self.assertEqual(self.grade(HOME_SPREAD)["result"], "loss")             # the bot's -2.5 still loses
        self.assertEqual(self.state().original(HOME_SPREAD)["identity"]["point"], -2.5)
        self.assertAlmostEqual(ev["score"]["your_tickets"]["dollars"]["units"], 6.25 + 20 * 100.0 / 180.0)

    def test_a_ticket_needs_a_book_a_price_and_a_stake(self):
        for kw in ({"book": "", "price": -110, "stake": 5}, {"book": "X", "price": 20, "stake": 5},
                   {"book": "X", "price": -110, "stake": 0}):
            with self.assertRaises(J.JournalError):
                J.record_ticket(self.j, HOME_ML, kw["book"], kw["price"], kw["stake"], NOW, placed_utc=J.stamp(NOW))
        with self.assertRaises(J.JournalError):
            J.record_ticket(self.j, HOME_ML, "X", -110, 5, NOW, placed_utc=J.stamp(NOW), point=-1.5)     # a moneyline has no line

    def test_take_pass_and_alternative_are_each_scored_and_passes_keep_their_result(self):
        self.load_calls()                                                   # bot call: Falcons -2.5 at -105
        J.record_decision(self.j, HOME_SPREAD, "alternative", "want the points", NOW, alt=AWAY_SPREAD)
        J.record_decision(self.j, HOME_ML, "take", "a reason", NOW, price=-160)
        J.record_decision(self.j, EV2_HOME_ML, "pass", "no view", NOW)
        self.finals()
        s = J.evaluate(self.state())["score"]
        self.assertEqual((s["bot_calls"]["n"], s["bot_calls"]["loss"], s["bot_calls"]["units"]), (1, 1, -1.0))
        self.assertEqual(s["your_alternatives"]["win"], 1)
        self.assertAlmostEqual(s["your_alternatives"]["units"], 100.0 / 110.0)
        self.assertEqual(s["your_takes"]["win"], 1)
        self.assertAlmostEqual(s["your_takes"]["units"], 100.0 / 160.0)       # his stated price, not -145
        self.assertEqual(s["bets_you_passed"]["win"], 1)
        self.assertAlmostEqual(s["bets_you_passed"]["units"], 100.0 / 118.0)  # what the passed bet did anyway, at its recorded -118
        self.assertEqual(s["bot_calls_by_your_decision"]["alternative"]["loss"], 1)
        self.assertEqual(s["bot_calls_by_your_decision"]["no decision"]["n"], 0)

    def test_benchmarks_use_the_same_slate(self):
        J.record_decision(self.j, HOME_SPREAD, "take", "a reason", NOW)
        self.finals()
        b = J.evaluate(self.state())["score"]["benchmarks"]
        self.assertEqual((b["moneyline_favorites_in_band"]["n"], b["moneyline_favorites_in_band"]["win"]), (2, 2))
        self.assertEqual(b["moneyline_favorites_any_price"]["n"], 2)
        self.assertEqual((b["price_matched_controls"]["n"], b["price_matched_controls"]["push"]), (2, 2))

    def test_the_uncertainty_range_is_wide_for_a_small_sample(self):
        lo, hi = J.wilson(2, 2)
        self.assertLess(lo, 0.35)
        self.assertEqual(hi, 1.0)
        self.assertIsNone(J.wilson(0, 0))

    def test_market_probability_removes_the_margin(self):
        pool = self.state().pool(OVER)
        self.assertAlmostEqual(pool["market_prob"], 0.5 * (0.5 + J.novig(-108, -112)))
        self.assertEqual(pool["market_prob_books"], 2)
        self.assertTrue(self.state().pool(HOME_ML)["is_favorite"])
        self.assertFalse(self.state().pool(AWAY_ML)["is_favorite"])


class LaterPriceTests(Base):
    def later(self):
        cap = capture(captured="2026-11-15T17:30:00Z", quote="2026-11-15T17:25:00Z")
        g1 = cap["games"][0]["bookmakers"]
        g1[0]["markets"][0]["outcomes"] = [o(HOME1, -160), o(AWAY1, 140)]
        g1[1]["markets"][0]["outcomes"] = [o(HOME1, -155), o(AWAY1, 135)]
        g1[0]["markets"][1]["outcomes"] = [o(HOME1, -110, -3.5), o(AWAY1, -110, 3.5)]   # the spread moved
        g1[1]["markets"][1]["outcomes"] = [o(HOME1, -105, -3.5), o(AWAY1, -115, 3.5)]
        return cap

    def test_a_later_price_is_never_borrowed_from_another_line(self):
        self.load()
        J.record_decision(self.j, HOME_ML, "take", "a reason", NOW)
        J.record_decision(self.j, HOME_SPREAD, "take", "a reason", NOW)
        before = self.raw("predictions")
        path = self.write("later.json", self.later())
        r = J.import_close(self.j, path, T("2026-11-15T17:40:00Z"))
        self.assertEqual(r, {"later_prices_recorded": 1, "tracked_bets_with_no_price_at_their_exact_line": 1})
        self.assertEqual(self.raw("predictions"), before)
        rows = dict((d["cid"], d) for d in J.evaluate(self.state())["decisions"])
        self.assertIsNone(rows[HOME_SPREAD]["later_price"])
        lp = rows[HOME_ML]["later_price"]
        self.assertEqual((lp["price"], lp["book"], lp["minutes_before_kickoff"]), (-155, "fanduel", 30))
        self.assertEqual(rows[HOME_ML]["price"], -145)
        self.assertEqual(J.import_close(self.j, path, T("2026-11-15T17:41:00Z"))["later_prices_recorded"], 0)

    def test_a_later_price_changes_no_decision_and_no_grade(self):
        self.load()
        J.record_decision(self.j, HOME_ML, "take", "a reason", NOW)
        self.finals()
        before = J.evaluate(self.state())["score"]["your_takes"]
        J.import_close(self.j, self.write("later.json", self.later()), AFTER2)
        after = J.evaluate(self.state())["score"]["your_takes"]
        self.assertEqual(before, after)
        self.assertEqual(len(self.state().decisions), 1)


class FinalsImportTests(Base):
    def test_finals_come_in_from_an_agent_made_score_file(self):
        self.load()
        doc = {"games": [
            {"teams": {"home": HOME1, "away": AWAY1}, "state": "STATUS_FINAL",
             "final_score": {"home": 21, "away": 20}, "source_url": "made-up-url"},
            {"teams": {"home": HOME2, "away": AWAY2}, "state": "STATUS_SCHEDULED", "final_score": None},
            {"teams": {"home": "Some Other Team", "away": "Another Team"}, "state": "STATUS_FINAL",
             "final_score": {"home": 3, "away": 0}}]}
        path = self.write("finals.json", doc)
        self.assertEqual(J.import_finals(self.j, path, NOW)["finals_recorded"], 0)       # too early: refused
        r = J.import_finals(self.j, path, AFTER1)
        self.assertEqual(r["finals_recorded"], 1)
        self.assertEqual(self.grade(HOME_ML)["result"], "win")
        self.assertEqual(self.grade(EV2_HOME_ML)["result"], "unknown")
        self.assertEqual(J.import_finals(self.j, path, AFTER1)["finals_recorded"], 0)    # no duplicate
        plain = self.write("plain.json", [{"home_team": HOME2, "away_team": AWAY2, "home_score": 21,
                                           "away_score": 20, "status": "final", "source": "made up"}])
        self.assertEqual(J.import_finals(self.j, plain, AFTER2)["finals_recorded"], 1)


class ManualBetTests(Base):
    def test_matthew_can_add_his_own_line_and_it_is_graded_at_his_price(self):
        self.load()
        rec = J.add_manual(self.j, "falcons", "spreads", "falcons", -120, "Caesars", NOW, point=-3)
        self.assertEqual((rec["role"], rec["identity"]["side"], rec["identity"]["point"]), ("manual", HOME1, -3.0))
        J.record_decision(self.j, HOME_SPREAD, "alternative", "better number", NOW, alt=rec["cid"])
        self.finals()
        row = J.evaluate(self.state())["decisions"][0]
        self.assertEqual((row["result"], row["units"], row["bot_result"]), ("loss", -1.0, "loss"))
        with self.assertRaises(J.JournalError):
            J.add_manual(self.j, "falcons", "spreads", "falcons", -120, "Caesars", NOW)            # no line
        with self.assertRaises(J.JournalError):
            J.add_manual(self.j, "falcons", "totals", "falcons", -110, "Caesars", NOW, point=41)   # bad side
        with self.assertRaises(J.JournalError):
            J.add_manual(self.j, "falcons", "h2h", "falcons", -120, "Caesars", AFTER1)             # after kickoff


class FormReportAndCommandLineTests(Base):
    def test_the_question_and_answer_form_saves_a_decision_and_a_ticket(self):
        self.load()
        answers = iter(["falcons", "1", "t", "Atlanta's line wins this matchup", "", "y", "FanDuel", "-120", "10", J.stamp(NOW), ""])
        said = []
        n = J.run_form(self.j, ask=lambda prompt: next(answers), out=said.append, clock=lambda: NOW)
        self.assertEqual(n, 2)
        s = self.state()
        self.assertEqual((s.decisions[0]["cid"], s.decisions[0]["action"]), (HOME_ML, "take"))
        self.assertEqual((s.tickets[0]["book"], s.tickets[0]["price"], s.tickets[0]["stake"]), ("FanDuel", -120, 10.0))
        self.assertEqual(s.original(HOME_ML)["price"], -145)

    def test_the_form_shows_bot_calls_first_and_takes_a_hypothesis_and_an_alternative(self):
        self.load()
        self.load_calls()
        answers = iter(["1", "a", "chiefs 2.5", "1", "the points matter here",
                        "Kansas City keeps it within a field goal because Atlanta settles for kicks.", "n", ""])
        said = []
        n = J.run_form(self.j, ask=lambda prompt: next(answers), out=said.append, clock=lambda: NOW)
        self.assertEqual(n, 2)
        s = self.state()
        d = s.decisions[0]
        self.assertEqual((d["cid"], d["action"], d["alt_cid"]), (HOME_SPREAD, "alternative", AWAY_SPREAD))
        self.assertEqual(d["hypothesis_id"], s.hypotheses[0]["hypothesis_id"])
        self.assertTrue(any("BOT CALL" in str(line) for line in said))

    def test_the_form_refuses_after_kickoff_without_crashing(self):
        self.load()
        clock = iter([NOW, AFTER1, AFTER1, AFTER1, AFTER1, AFTER1])
        answers = iter(["falcons", "1", "t", "a reason", "", ""])
        said = []
        n = J.run_form(self.j, ask=lambda prompt: next(answers), out=said.append, clock=lambda: next(clock, AFTER1))
        self.assertEqual(n, 0)
        self.assertEqual(self.state().decisions, [])

    def test_the_report_is_written_and_says_what_is_not_graded(self):
        self.load()
        self.load_calls()
        J.record_decision(self.j, HOME_SPREAD, "pass", "no view | really", NOW)
        out, _ev = J.write_report(self.j, NOW)
        self.assertEqual(out, os.path.join(self.j.dir, "EVALUATION.md"))
        text = read_text(out)
        for needle in ("# Pregame journal: evaluation", "## Bot calls, as first recorded", "## Your decisions",
                       "## Your tickets", "## Scorecard", "## Benchmarks", "## Later prices", "## Honest limits",
                       "not graded yet", "-105 at FanDuel", "no view / really", "every line checks out"):
            self.assertIn(needle, text)
        self.finals()
        J.write_report(self.j, AFTER2)
        text = read_text(out)
        self.assertIn("loss (-1.00 units)", text)
        self.assertNotIn("guarantee", text.lower())

    def run_cli(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = J.main(["--data", self.j.dir] + list(args))
        return code, buf.getvalue()

    def test_the_command_line_end_to_end(self):
        cap = self.write("capture.json", capture())
        calls = self.write("calls.json", calls_doc())
        with mock.patch.object(J, "utc_now", lambda: NOW):
            self.assertEqual(self.run_cli("import-capture", cap)[0], 0)
            self.assertEqual(self.run_cli("import-calls", calls)[0], 0)
            code, out = self.run_cli("list", "--calls")
            self.assertEqual(code, 0)
            self.assertIn("BOT CALL", out)
            self.assertIn(HOME_SPREAD[:8], out)
            self.assertEqual(self.run_cli("hypothesis", "--text", "Atlanta covers because its run game controls the clock.",
                                          "--event", "falcons")[0], 0)
            self.assertEqual(self.run_cli("decide", HOME_SPREAD[:8], "take", "--reason", "agree with the bot")[0], 0)
            self.assertEqual(self.run_cli("decide", HOME_SPREAD[:8], "pass", "--reason", "again")[0], 1)
            self.assertEqual(self.run_cli("ticket", HOME_SPREAD[:8], "--book", "FanDuel", "--price", "-108", "--stake", "5", "--placed-utc", J.stamp(NOW))[0], 0)
            self.assertEqual(self.run_cli("final", "falcons", "--home", "21", "--away", "20", "--source", "x")[0], 1)
            self.assertEqual(self.run_cli("show", HOME_SPREAD[:8])[0], 0)
            self.assertEqual(self.run_cli("status")[0], 0)
        with mock.patch.object(J, "utc_now", lambda: AFTER1):
            self.assertEqual(self.run_cli("decide", HOME_ML[:8], "take", "--reason", "too late")[0], 1)
            self.assertEqual(self.run_cli("final", "falcons", "--home", "21", "--away", "20", "--source", "made up")[0], 0)
            self.assertEqual(self.run_cli("report")[0], 0)
            code, out = self.run_cli("grade")
            self.assertEqual(code, 0)
            score = json.loads(out)["score"]
            self.assertEqual(score["your_takes"]["loss"], 1)
            self.assertEqual(score["your_tickets"]["dollars"]["units"], -5.0)
            code, out = self.run_cli("verify")
            self.assertEqual(code, 0)
            self.assertIn("intact", out)

    def test_listing_hides_games_that_have_started(self):
        self.load()
        s = self.state()
        self.assertEqual(len(J.search(s, [], NOW)), 16)
        between = T("2026-11-15T19:00:00Z")
        self.assertEqual(len(J.search(s, [], between)), 4)
        self.assertEqual(len(J.search(s, [], between, include_started=True)), 16)
        self.assertEqual(len(J.search(s, ["robinson"], NOW)), 2)
        self.assertEqual(len(J.search(s, [], NOW, window="late")), 4)


class NoNetworkTests(unittest.TestCase):
    def test_the_tool_imports_nothing_that_can_reach_a_network_or_run_a_program(self):
        with open(os.path.join(HERE, "journal.py"), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        banned = set(["socket", "urllib", "http", "ssl", "subprocess", "requests", "ftplib", "smtplib",
                      "asyncio", "xmlrpc", "webbrowser", "ctypes", "multiprocessing"])
        self.assertEqual(names & banned, set())
        self.assertEqual(names, set(["argparse", "datetime", "hashlib", "json", "math", "os", "sys", "fcntl", "zoneinfo"]))


EV3, EV4 = "c" * 32, "d" * 32
HOME3, AWAY3 = "Dallas Cowboys", "San Francisco 49ers"
HOME4, AWAY4 = "Las Vegas Raiders", "Seattle Seahawks"


def run_cli(journal, args, now=NOW):
    import contextlib
    import io
    from unittest import mock
    buf = io.StringIO()
    with mock.patch.object(J, "utc_now", lambda: now), contextlib.redirect_stdout(buf):
        code = J.main(["--data", journal.dir] + list(args))
    return code, buf.getvalue()


def control_capture():
    """Four games, one book. Built to hit every reason a bet is, or is not, a price-matched control."""
    def game(ev, kick, home, away, markets):
        return {"id": ev, "commence_time": kick, "home_team": home, "away_team": away,
                "bookmakers": [bk("draftkings", markets)]}
    return {"captured_utc": CAPTURED, "event_odds": [], "games": [
        game(EV1, KICK1, HOME1, AWAY1, [mk("h2h", [o(HOME1, -195), o(AWAY1, 165)]),
                                        mk("spreads", [o(HOME1, -110, -2.5), o(AWAY1, -110, 2.5)])]),
        game(EV2, KICK2, HOME2, AWAY2, [mk("h2h", [o(HOME2, -185), o(AWAY2, 155)]),
                                        mk("spreads", [o(HOME2, -110, -1), o(AWAY2, -110, 1)]),
                                        mk("totals", [o("Over", -110, 44), o("Under", -110, 44)])]),
        game(EV3, KICK2, HOME3, AWAY3, [mk("h2h", [o(HOME3, -150), o(AWAY3, 130)]),
                                        mk("spreads", [o(HOME3, -125, -3), o(AWAY3, 105, 3)])]),
        game(EV4, KICK2, HOME4, AWAY4, [mk("h2h", [o(HOME4, -205), o(AWAY4, 170)])]),
    ]}


class OfferedPriceTests(Base):
    def setUp(self):
        Base.setUp(self)
        self.load()
        self.load_calls()

    def test_offered_price_is_kept_on_the_same_ticket_line_and_never_grades_it(self):
        before = self.raw("predictions")
        t = J.record_ticket(self.j, AWAY_SPREAD, "FanDuel", -120, 12, NOW, placed_utc=J.stamp(NOW), offered_price=-110)
        self.assertEqual((t["price"], t["offered_price"]), (-120, -110))
        self.assertEqual(self.raw("predictions"), before)
        self.assertEqual(len(self.state().tickets), 1)
        self.assertEqual(sorted(n for n in os.listdir(self.j.dir) if "ticket" in n or "offer" in n), ["tickets.jsonl"])
        self.finals()
        row = J.evaluate(self.state())["tickets"][0]
        self.assertEqual(row["result"], "win")
        self.assertAlmostEqual(row["units"], 10.0)              # 12 staked at -120, not at -110
        self.assertEqual(row["offered_price"], -110)

    def test_a_ticket_without_an_offered_price_reads_as_not_recorded(self):
        t = J.record_ticket(self.j, AWAY_SPREAD, "FanDuel", -120, 12, NOW, placed_utc=J.stamp(NOW))
        self.assertIsNone(t["offered_price"])
        out, ev = J.write_report(self.j, NOW)
        self.assertIsNone(ev["tickets"][0]["offered_price"])
        self.assertIn("not recorded", read_text(out))

    def test_an_offered_price_must_be_real_odds(self):
        for bad in (50, 0, "x", True):
            with self.assertRaises(J.JournalError):
                J.record_ticket(self.j, AWAY_SPREAD, "FanDuel", -120, 12, NOW, placed_utc=J.stamp(NOW), offered_price=bad)
        self.assertEqual(self.state().tickets, [])

    def test_the_command_line_takes_offered_price_and_the_report_shows_it(self):
        code, text = run_cli(self.j, ["ticket", AWAY_SPREAD, "--book", "FanDuel", "--price", "-120",
                                      "--stake", "12", "--offered-price", "-110", "--placed-utc", J.stamp(NOW)])
        self.assertEqual(code, 0, text)
        self.assertEqual(self.state().tickets[0]["offered_price"], -110)
        out, _ev = J.write_report(self.j, NOW)
        page = read_text(out)
        self.assertIn("Price the book showed you", page)
        self.assertIn("-110", page)


class ResearchRegisterTests(Base):
    TITLE = "Automatic WR/TE receiving-yard bump after two hot target-share games"
    SUMMARY = "On the 2025 holdout the adjusted forecast was worse: mean absolute error 21.72 to 23.84 yards."

    def add(self, **kw):
        a = dict(title=self.TITLE, status="rejected", summary=self.SUMMARY, evidence="/made/up/outputs", scope_note="")
        a.update(kw)
        return J.record_research(self.j, a["title"], a["status"], a["summary"], a["evidence"], NOW,
                                 scope_note=a["scope_note"])

    def test_a_rejected_idea_is_registered_with_no_games_loaded(self):
        r = self.add(scope_note="Not a personnel-specific role change.")
        self.assertEqual(r["status"], "rejected")
        self.assertTrue(r["research_id"].startswith("R"))
        self.assertFalse(r["changed_live_rule"])
        self.assertEqual(len(self.state().research), 1)
        counts, problems = self.j.verify()
        self.assertEqual((counts["research"], problems), (1, []))

    def test_bad_entries_and_exact_duplicates_are_refused(self):
        for kw in ({"status": "proven"}, {"title": "short"}, {"summary": "too short"}, {"evidence": "  "}):
            with self.assertRaises(J.JournalError):
                self.add(**kw)
        self.add()
        with self.assertRaises(J.JournalError):
            self.add()
        self.assertEqual(len(self.state().research), 1)

    def test_the_register_cannot_be_edited_quietly(self):
        self.add()
        text = self.raw("research").decode("utf-8")
        changed = text.replace("rejected", "supported")
        self.assertNotEqual(changed, text)
        with open(self.j.path("research"), "w", encoding="utf-8") as fh:
            fh.write(changed)
        with self.assertRaises(J.JournalError):
            self.state()

    def test_registering_research_never_touches_a_prediction_and_shows_in_the_report(self):
        self.load()
        self.load_calls()
        before = self.raw("predictions")
        code, text = run_cli(self.j, ["research", "--title", self.TITLE, "--status", "rejected",
                                      "--summary", self.SUMMARY, "--evidence", "/made/up/outputs"])
        self.assertEqual(code, 0, text)
        self.assertEqual(self.raw("predictions"), before)
        out, _ev = J.write_report(self.j, NOW)
        page = read_text(out)
        for needle in ("## Research register", "REJECTED", "No live rule was changed", self.TITLE):
            self.assertIn(needle, page)
        code, text = run_cli(self.j, ["status"])
        self.assertIn("Research notes 1", text)


class ProviderQuoteTimeTests(Base):
    def test_the_picker_files_provider_time_is_the_quote_time(self):
        self.load()
        doc = calls_doc()
        call = doc["calls"][0]
        del call["updated"]
        call["provider_updated_utc"] = "2026-11-15T06:53:59Z"
        call["observed_utc"] = "2026-11-15T06:55:04Z"
        self.load_calls(doc)
        self.assertEqual(self.state().original(HOME_SPREAD)["quote_utc"], "2026-11-15T06:53:59Z")


class MatchedControlTests(Base):
    def setUp(self):
        Base.setUp(self)
        self.load(control_capture())
        J.record_decision(self.j, HOME_SPREAD, "take", "made-up reason for the test", NOW)
        J.record_decision(self.j, HOME_ML, "take", "made-up reason for the test", NOW)
        J.record_final(self.j, EV1, 21, 20, "made-up box score", AFTER2)
        J.record_final(self.j, EV2, 24, 20, "made-up box score", AFTER2)
        self.b = J.evaluate(self.state())["score"]["benchmarks"]
        self.rows = dict((r["cid"], r) for r in self.b["price_matched_control_rows"])

    def test_controls_are_same_market_other_games_in_band_and_close_in_price(self):
        self.assertEqual(set(self.rows), set([EV2_HOME_SPREAD, EV2_AWAY_SPREAD, EV2_HOME_ML]))
        left_out = {
            "the bet itself": HOME_SPREAD,
            "same game, same price": AWAY_SPREAD,
            "other market, same price": cid("totals", "Over", 44, event=EV2),
            "price too far (-125)": cid("spreads", HOME3, -3, event=EV3),
            "price too far (+105)": cid("spreads", AWAY3, 3, event=EV3),
            "price too far (-150 against -195)": cid("h2h", HOME3, event=EV3),
            "close in price but outside the band (-205)": cid("h2h", HOME4, event=EV4),
        }
        for why, c in left_out.items():
            self.assertNotIn(c, self.rows, why)
            self.state().original(c)                             # each of them is a real recorded bet

    def test_each_control_is_graded_once_at_its_own_recorded_price(self):
        self.assertEqual(self.rows[EV2_HOME_ML]["matched_to"], [HOME_ML])
        self.assertEqual(self.rows[EV2_HOME_SPREAD]["matched_to"], [HOME_SPREAD])
        self.assertEqual(self.rows[EV2_HOME_ML]["price"], -185)
        self.assertEqual((self.rows[EV2_HOME_ML]["result"], self.rows[EV2_AWAY_SPREAD]["result"]), ("win", "loss"))
        self.assertAlmostEqual(self.rows[EV2_HOME_ML]["units"], 100.0 / 185.0)
        t = self.b["price_matched_controls"]
        self.assertEqual((t["n"], t["win"], t["loss"]), (3, 2, 1))
        self.assertAlmostEqual(t["units"], 100.0 / 110.0 - 1.0 + 100.0 / 185.0)

    def test_the_pickers_control_is_the_most_likely_in_band_moneyline_per_window(self):
        rows = self.b["top_favorite_per_window_rows"]
        self.assertEqual([(r["window"], r["cid"]) for r in rows], [("early", HOME_ML), ("late", EV2_HOME_ML)])
        t = self.b["top_favorite_per_window_in_band"]
        self.assertEqual((t["n"], t["win"]), (2, 2))


class RegisteredControlTests(Base):
    RULE = "Same book, same exact price, same market and side, a different game on the same Sunday."

    def setUp(self):
        Base.setUp(self)
        self.load(control_capture())

    def test_a_pair_is_graded_at_the_controls_own_recorded_price(self):
        before = self.raw("predictions")
        c = J.record_control(self.j, HOME_SPREAD, EV2_HOME_SPREAD, self.RULE, NOW, book="draftkings", price=-110)
        self.assertEqual((c["price"], c["book"], c["pregame_verified"]), (-110, "draftkings", True))
        self.assertEqual(self.raw("predictions"), before)
        J.record_final(self.j, EV1, 21, 20, "made-up box score", AFTER2)
        J.record_final(self.j, EV2, 24, 20, "made-up box score", AFTER2)
        ev = J.evaluate(self.state())
        pair = ev["controls"][0]
        self.assertEqual((pair["result"], pair["control_result"]), ("loss", "win"))
        self.assertAlmostEqual(pair["control_units"], 100.0 / 110.0)
        s = ev["score"]["registered_controls"]
        self.assertEqual((s["bets"]["loss"], s["controls"]["win"]), (1, 1))
        out, _ev = J.write_report(self.j, AFTER2)
        self.assertIn("## Matched controls registered before kickoff", read_text(out))

    def test_wrong_or_late_controls_are_refused(self):
        cases = [(HOME_SPREAD, HOME_SPREAD, {}),                          # itself
                 (HOME_SPREAD, AWAY_SPREAD, {}),                          # same game
                 (HOME_SPREAD, EV2_HOME_SPREAD, {"book": "fanduel"}),     # no such recorded quote
                 (HOME_SPREAD, EV2_HOME_SPREAD, {"price": -105})]         # not the recorded price
        for bet, ctl, kw in cases:
            with self.assertRaises(J.JournalError):
                J.record_control(self.j, bet, ctl, self.RULE, NOW, **kw)
        with self.assertRaises(J.JournalError):
            J.record_control(self.j, HOME_SPREAD, EV2_HOME_SPREAD, "short", NOW)
        with self.assertRaises(J.JournalError):
            J.record_control(self.j, HOME_SPREAD, EV2_HOME_SPREAD, self.RULE, T(KICK1))
        self.assertEqual(self.state().controls, [])
        J.record_control(self.j, HOME_SPREAD, EV2_HOME_SPREAD, self.RULE, NOW)
        with self.assertRaises(J.JournalError):                           # no swapping after the fact
            J.record_control(self.j, HOME_SPREAD, EV2_AWAY_SPREAD, self.RULE, NOW)

    def test_a_late_control_is_kept_but_not_scored(self):
        c = J.record_control(self.j, HOME_SPREAD, EV2_HOME_SPREAD, self.RULE, T("2026-11-15T19:00:00Z"), late=True)
        self.assertFalse(c["pregame_verified"])
        s = J.evaluate(self.state())["score"]["registered_controls"]
        self.assertEqual((s["bets"]["n"], s["controls"]["n"]), (0, 0))

    def test_the_command_line_registers_a_control(self):
        code, text = run_cli(self.j, ["control", HOME_SPREAD, EV2_HOME_SPREAD, "--rule", self.RULE,
                                      "--book", "draftkings", "--price", "-110"])
        self.assertEqual(code, 0, text)
        self.assertEqual(len(self.state().controls), 1)


class TicketReconciliationTests(Base):
    def setUp(self):
        super().setUp()
        self.load()
        self.load_calls()

    def buy(self, book="BetMGM", price=-150):
        return J.record_ticket(self.j, HOME_ML, book, price, 10, NOW, placed_utc=J.stamp(NOW),
                               offered_price=-145)

    def test_cash_by_ticket_is_independent_of_the_box_score_and_other_books(self):
        a, b = self.buy("BetMGM"), self.buy("FanDuel", -250)
        self.assertNotEqual(a["ticket_id"], b["ticket_id"])
        self.assertFalse(b["accepted_in_band"])
        self.finals()
        baseline = J.evaluate(self.state())
        self.assertEqual(baseline["score"]["confirmed_ticket_returns"]["dollars"]["pending_count"], 2)
        predictions = self.raw("predictions")
        J.record_settlement(self.j, a["ticket_id"], 0, "loss", AFTER1, confirmed=True)
        interim = J.evaluate(self.state())
        self.assertEqual(interim["tickets"][0]["actual_net"], -10)
        self.assertIsNone(interim["tickets"][1]["actual_net"])
        current = J.record_settlement(self.j, b["ticket_id"], 10, "refund", AFTER1, confirmed=True)
        for kwargs in ({}, {"prior_sha": current["sha"]}, {"prior_sha": "obsolete", "note": "adjustment"}):
            with self.assertRaises(J.JournalError):
                J.record_settlement(self.j, b["ticket_id"], 14, "adjustment", AFTER1, confirmed=True, **kwargs)
        J.record_settlement(self.j, b["ticket_id"], 14, "adjustment", AFTER1, confirmed=True,
                            prior_sha=current["sha"], note="Book resettled the ticket.")
        ev = J.evaluate(self.state())
        self.assertEqual(ev["calls"], baseline["calls"])
        self.assertEqual([r["estimated_gross_return"] for r in ev["tickets"]],
                         [r["estimated_gross_return"] for r in baseline["tickets"]])
        self.assertEqual([r["actual_net"] for r in ev["tickets"]], [-10, 4])
        self.assertEqual(ev["score"]["confirmed_ticket_returns"]["dollars"],
                         dict(confirmed_count=2, pending_count=0, confirmed_stake=20, gross_return=14, net_return=-6))
        self.assertEqual(len(self.state().settlements), 3)
        self.assertEqual(self.raw("predictions"), predictions)
        self.assertFalse(self.j.verify()[1])

    def test_simultaneous_ticket_and_settlement_resubmissions_append_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        def race(call):
            barrier = Barrier(2)
            def attempt(_):
                barrier.wait()
                try:
                    return call()
                except J.JournalError:
                    return None
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(attempt, range(2)))
            self.assertEqual(sum(r is not None for r in results), 1)
            return next(r for r in results if r is not None)

        ticket = race(self.buy)
        race(lambda: J.record_settlement(self.j, ticket["ticket_id"], 10, "void", AFTER1, confirmed=True))
        self.assertEqual((len(self.state().tickets), len(self.state().settlements)), (1, 1))

    def test_confirmation_and_valid_amount_are_required(self):
        ticket = self.buy()
        for gross, confirmed in ((0, False), (-1, True), (float("nan"), True), (float("inf"), True),
                                 (True, True), (None, True)):
            with self.assertRaises(J.JournalError):
                J.record_settlement(self.j, ticket["ticket_id"], gross, "loss", AFTER1, confirmed=confirmed)
        for invalid_time in (None, KICK1, J.stamp(AFTER1), "2026-11-15T07:30:00"):
            with self.assertRaises(J.JournalError):
                J.record_ticket(self.j, HOME_ML, "FanDuel", -115, 5, NOW, placed_utc=invalid_time)
        self.assertEqual(self.j.read("settlements"), [])

    def test_old_ticket_remains_readable_and_can_be_reconciled_without_rewriting_it(self):
        # Use the prior storage format, where placed time was optional and no band flag was present.
        t = self.buy()
        body = {k: v for k, v in t.items() if k not in (*J.RESERVED, "ticket_id", "accepted_in_band")}
        body.update(placed_utc_reported=None, book="DraftKings")
        legacy = self.j.append("tickets", body, NOW)
        ticket_bytes = self.raw("tickets")
        tid = J.ticket_id(legacy)
        J.record_settlement(self.j, tid, 0, "loss", AFTER1, confirmed=True)
        row = next(r for r in J.evaluate(self.state())["tickets"] if r["ticket_id"] == tid)
        self.assertIsNone(row["placed_utc_reported"])
        self.assertEqual(row["actual_net"], -10)
        self.assertEqual(self.raw("tickets"), ticket_bytes)

    def test_price_floor_applies_to_exact_contract_and_single_book_ev_stays_unknown(self):
        when = J.stamp(NOW)
        under = J.record_ticket(self.j, HOME_SPREAD, "FanDuel", -115, 5, AFTER1, placed_utc=when)
        changed = J.record_ticket(self.j, HOME_SPREAD, "FanDuel", -120, 5, NOW, point=-1.5, placed_utc=when)
        exact = J.record_ticket(self.j, HOME_SPREAD, "DraftKings", -110, 5, NOW, placed_utc=when)
        self.assertFalse(under["meets_issued_minimum"])
        self.assertFalse(under["recorded_before_kickoff"])
        self.assertTrue(exact["meets_issued_minimum"])
        self.assertIsNone(changed["meets_issued_minimum"])
        prop = self.state().original(PROP_OVER)
        self.assertIsNone(J.describe(prop, self.state())["est_value_per_unit"])
        self.assertIn("40 minutes", J.show_text(prop, self.state(), NOW))

    def test_full_game_and_first_half_player_results_do_not_cross(self):
        full = self.state().original(PROP_OVER)
        half = copy.deepcopy(full)
        half["identity"] = J.make_identity(EV1, "player_rush_yds_h1", PLAYER, 60.5, "Over")
        half["cid"] = J.candidate_id(EV1, "player_rush_yds_h1", PLAYER, 60.5, "Over")
        J.record_player_result(self.j, "falcons", PLAYER, "player_rush_yds", 75, "test full game", AFTER1)
        self.assertEqual(J.settle(full, self.state())[0], "win")
        self.assertEqual(J.settle(half, self.state())[0], "unknown")
        J.record_player_result(self.j, "falcons", PLAYER, "player_rush_yds_h1", 30, "test first half", AFTER1)
        self.assertEqual(J.settle(half, self.state())[0], "loss")
        self.assertEqual(J.settle(full, self.state())[0], "win")


if __name__ == "__main__":
    unittest.main(verbosity=1)
