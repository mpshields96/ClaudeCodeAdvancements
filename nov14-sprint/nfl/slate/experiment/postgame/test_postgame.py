#!/usr/bin/env python3
"""Tests for postgame.py. Every journal and input lives in a fresh temp dir; nothing touches experiment/data/.

Run: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B test_postgame.py -v
"""
import contextlib
import datetime
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
for d in (os.path.dirname(HERE), HERE):
    if d not in sys.path:
        sys.path.insert(0, d)

import journal as J  # noqa: E402
import postgame as P  # noqa: E402

UTC = datetime.timezone.utc
PIT, IND = "Pittsburgh Steelers", "Indianapolis Colts"
NYG, WSH = "New York Giants", "Washington Commanders"
KICK = datetime.datetime(2026, 10, 11, 17, 0, tzinfo=UTC)          # IND at PIT, week 5
LATER = KICK + datetime.timedelta(hours=6)
REC_FIRST = ["REC", "YDS", "AVG", "LNG", "TD", "ATT", "YDS", "AVG", "LNG", "TD", "FUM", "LOST"]
RUSH_FIRST = ["ATT", "YDS", "AVG", "LNG", "TD", "REC", "YDS", "AVG", "LNG", "TD", "FUM", "LOST"]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def ou(key, point, player=""):
    outs = []
    for side in ("Over", "Under"):
        o = {"name": side, "price": -110, "point": point}
        if player:
            o["description"] = player
        outs.append(o)
    return {"key": key, "outcomes": outs}


def game(ev_id, home, away, kick, markets, captured):
    quote = iso(captured - datetime.timedelta(minutes=5))
    for m in markets:
        m["last_update"] = quote
    return {"id": ev_id, "commence_time": iso(kick), "home_team": home, "away_team": away,
            "bookmakers": [{"key": "fixturebook", "last_update": quote, "markets": markets}]}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="postgame-test-")
        self.data = os.path.join(self.tmp, "data")
        self.journal = J.Journal(self.data)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, name, doc):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as fh:
            json.dump(doc, fh)
        return path

    def load(self, games, captured):
        path = self.write("capture-%d.json" % len(os.listdir(self.tmp)),
                          {"captured_utc": iso(captured), "games": games})
        J.import_capture(self.journal, path, captured)

    def pit_journal(self, props=(("Jaylen Warren", "player_rush_yds", 70.5),
                                 ("Jaylen Warren", "player_reception_yds", 20.5),
                                 ("Tyler Warren", "player_reception_yds", 45.5)), h1=False):
        cap = KICK - datetime.timedelta(hours=1)
        markets = [ou("totals", 44.5)] + ([ou("totals_h1", 21.5)] if h1 else [])
        markets += [ou(m, pt, who) for who, m, pt in props]
        self.load([game("E-PIT", PIT, IND, KICK, markets, cap)], cap)

    def manual_final(self, home_score=34, away_score=22, status="final", **extra):
        row = {"home_team": PIT, "away_team": IND, "home_score": home_score, "away_score": away_score,
               "status": status, "source": "test transcription"}
        row.update(extra)
        return self.write("finals.json", {"captured_utc": iso(LATER - datetime.timedelta(hours=1)), "finals": [row]})

    def logs(self, players, cutoff=None, name="logs.json"):
        """players: list of (name, team, headers, rows) -> an NFL.com-log-shaped file."""
        doc = {"captured_utc": iso(LATER - datetime.timedelta(hours=1)), "players": {}, "logs": {}}
        if cutoff:
            doc["cutoff_exclusive"] = cutoff
        for i, (name, team, headers, rows) in enumerate(players):
            url = "https://www.nfl.com/players/p%d/stats/logs/2026/" % i
            doc["players"]["%s %d" % (name, i)] = {"name": name, "team_name": team, "log_url": url}
            doc["logs"][url] = {"official_name": name, "headers": headers, "games": rows,
                                "source": {"source_url": url, "retrieved_utc": iso(LATER), "sha256": "ab" * 32}}
        return self.write(name, doc)

    def run_intake(self, paths, now=LATER):
        return P.import_from_public(self.data, paths=paths, now=now)

    def pending_items(self, summary):
        return dict((p["item"], p["reason"]) for p in summary["pending"])

    def state(self):
        return J.State(self.journal)


def jaylen(rows=None):
    return ("Jaylen Warren", PIT, RUSH_FIRST, rows or [
        {"date": "2026-10-11", "opponent": "Colts", "result": "W 34 - 22",
         "values": ["15", "101", "6.7", "20", "1", "6", "87", "14.5", "30", "0", None, None]}])


def tyler(rows=None):
    return ("Tyler Warren", IND, REC_FIRST, rows or [
        {"date": "2026-10-11", "opponent": "@Steelers", "result": "L 22 - 34",
         "values": ["7", "83", "11.9", "25", "0", "1", "1", "1", "1", "0", None, None]}])


class TestPlayers(Base):
    def test_warrens_matched_by_full_name_and_team(self):
        self.pit_journal()
        s = self.run_intake([self.manual_final(), self.logs([jaylen(), tyler()])])
        got = dict(((p["player"], p["market"]), (p["team"], p["value"])) for p in s["recorded_players"])
        self.assertEqual(got[("Jaylen Warren", "player_rush_yds")], (PIT, 101.0))
        self.assertEqual(got[("Jaylen Warren", "player_reception_yds")], (PIT, 87.0))
        self.assertEqual(got[("Tyler Warren", "player_reception_yds")], (IND, 83.0))
        self.assertEqual(s["exit_code"], 0, s)
        st = self.state()
        self.assertEqual(st.player_results[("E-PIT", "tyler warren", "player_reception_yds")]["value"], 83.0)

    def test_last_name_or_alias_does_not_match(self):
        self.pit_journal(props=(("J. Warren", "player_rush_yds", 70.5),))
        s = self.run_intake([self.manual_final(), self.logs([jaylen(), tyler()])])
        self.assertEqual(s["recorded_players"], [])
        self.assertIn("J. Warren player_rush_yds", self.pending_items(s))

    def test_suffix_dot_matches_both_ways_and_keeps_the_journal_name(self):
        row = jaylen()[3]
        for journal_name, log_name in (("Jaylen Warren Jr", "Jaylen Warren Jr."),
                                       ("Jaylen Warren Jr.", "Jaylen Warren Jr"),
                                       ("Jaylen Warren III", "Jaylen Warren III.")):
            with self.subTest(journal=journal_name, log=log_name):
                self.tearDown()
                self.setUp()
                self.pit_journal(props=((journal_name, "player_rush_yds", 70.5),))
                s = self.run_intake([self.manual_final(), self.logs([(log_name, PIT, RUSH_FIRST, row)])])
                self.assertEqual([(p["player"], p["value"]) for p in s["recorded_players"]],
                                 [(journal_name, 101.0)], s)
                self.assertEqual(s["exit_code"], 0, s)
                key = ("E-PIT", J.norm_text(journal_name), "player_rush_yds")
                self.assertEqual(self.state().player_results[key]["value"], 101.0)
                again = self.run_intake([self.manual_final(), self.logs([(log_name, PIT, RUSH_FIRST, row)])])
                self.assertEqual((again["recorded_players"], again["already_recorded"]), ([], 2))

    def test_missing_or_different_suffix_does_not_match(self):
        row = jaylen()[3]
        for journal_name, log_name in (("Jaylen Warren", "Jaylen Warren Jr."),
                                       ("Jaylen Warren Jr", "Jaylen Warren"),
                                       ("Jaylen Warren Jr", "Jaylen Warren Sr."),
                                       ("Jaylen Warren II", "Jaylen Warren III")):
            with self.subTest(journal=journal_name, log=log_name):
                self.tearDown()
                self.setUp()
                self.pit_journal(props=((journal_name, "player_rush_yds", 70.5),))
                s = self.run_intake([self.manual_final(), self.logs([(log_name, PIT, RUSH_FIRST, row)])])
                self.assertEqual(s["recorded_players"], [])
                self.assertIn("%s player_rush_yds" % journal_name, self.pending_items(s))

    def test_suffix_dot_still_needs_a_team_in_the_game(self):
        self.pit_journal(props=(("Jaylen Warren Jr", "player_rush_yds", 70.5),))
        s = self.run_intake([self.manual_final(),
                             self.logs([("Jaylen Warren Jr.", "Dallas Cowboys", RUSH_FIRST, jaylen()[3])])])
        self.assertEqual(s["recorded_players"], [])

    def test_same_full_name_on_both_teams_stays_pending(self):
        self.pit_journal(props=(("Chris Moore", "player_reception_yds", 30.5),))
        row_pit = {"date": "2026-10-11", "opponent": "Colts", "result": "W 34 - 22",
                   "values": ["3", "40", "13", "20", "0", None, None, None, None, None, None, None]}
        row_ind = {"date": "2026-10-11", "opponent": "@Steelers", "result": "L 22 - 34",
                   "values": ["2", "15", "7.5", "9", "0", None, None, None, None, None, None, None]}
        s = self.run_intake([self.manual_final(), self.logs([("Chris Moore", PIT, REC_FIRST, [row_pit]),
                                                             ("Chris Moore", IND, REC_FIRST, [row_ind])])])
        self.assertEqual(s["recorded_players"], [])
        self.assertIn("ambiguous", self.pending_items(s)["Chris Moore player_reception_yds"])

    def test_player_on_another_team_does_not_match(self):
        self.pit_journal(props=(("Tyler Warren", "player_reception_yds", 45.5),))
        s = self.run_intake([self.manual_final(), self.logs([("Tyler Warren", "Dallas Cowboys", REC_FIRST,
                                                              tyler()[3])])])
        self.assertEqual(s["recorded_players"], [])

    def test_missing_stat_stays_pending_never_zero(self):
        self.pit_journal(props=(("Tyler Warren", "player_rush_yds", 0.5),))
        row = {"date": "2026-10-11", "opponent": "@Steelers", "result": "L 22 - 34",
               "values": ["4", "44", "11", "13", "0", None, None, None, None, None, None, None]}
        s = self.run_intake([self.manual_final(), self.logs([tyler([row])])])
        self.assertEqual(s["recorded_players"], [])
        self.assertIn("never zero", self.pending_items(s)["Tyler Warren player_rush_yds"])
        self.assertEqual(self.state().player_results, {})

    def test_all_null_row_is_dnp_pending(self):
        self.pit_journal(props=(("Tyler Warren", "player_reception_yds", 45.5),))
        row = {"date": "2026-10-11", "opponent": "@Steelers", "result": "L 22 - 34", "values": [None] * 12}
        s = self.run_intake([self.manual_final(), self.logs([tyler([row])])])
        self.assertIn("DNP", self.pending_items(s)["Tyler Warren player_reception_yds"])
        self.assertEqual(self.state().player_results, {})

    def test_no_row_for_the_game_is_pending(self):
        self.pit_journal(props=(("Tyler Warren", "player_reception_yds", 45.5),))
        other = {"date": "2026-10-04", "opponent": "Raiders", "result": "W 20 - 10", "values": ["5"] * 12}
        s = self.run_intake([self.manual_final(), self.logs([tyler([other])])])
        self.assertEqual(s["recorded_players"], [])
        self.assertIn("Tyler Warren player_reception_yds", self.pending_items(s))

    def test_logs_cut_off_before_the_game_say_so(self):
        self.pit_journal(props=(("Tyler Warren", "player_reception_yds", 45.5),))
        other = {"date": "2026-10-04", "opponent": "Raiders", "result": "W 20 - 10", "values": ["5"] * 12}
        item = "Tyler Warren player_reception_yds"
        # The collector's cutoff is exclusive: a file cut off at the game's own date cannot hold it.
        s = self.run_intake([self.manual_final(), self.logs([tyler([other])], cutoff="2026-10-11")])
        self.assertIn("cutoff_exclusive 2026-10-11", self.pending_items(s)[item])
        self.assertEqual(self.state().player_results, {})
        # A file whose cutoff is after the game keeps the plain no-row reason.
        s = self.run_intake([self.manual_final(), self.logs([tyler([other])], cutoff="2026-10-12")])
        self.assertNotIn("cutoff", self.pending_items(s)[item])
        # So does a run where a second logs file covers the date.
        s = self.run_intake([self.manual_final(), self.logs([tyler([other])], cutoff="2026-10-11"),
                             self.logs([tyler([other])], cutoff="2026-10-12", name="logs2.json")])
        self.assertNotIn("cutoff", self.pending_items(s)[item])

    def test_real_zero_is_recorded(self):
        self.pit_journal(props=(("Tyler Warren", "player_reception_yds", 0.5),))
        row = {"date": "2026-10-11", "opponent": "@Steelers", "result": "L 22 - 34",
               "values": ["0", "0", "0", "0", "0", None, None, None, None, None, None, None]}
        s = self.run_intake([self.manual_final(), self.logs([tyler([row])])])
        self.assertEqual([(p["player"], p["value"]) for p in s["recorded_players"]], [("Tyler Warren", 0.0)])

    def test_log_score_disagreeing_with_final_stays_pending(self):
        self.pit_journal(props=(("Jaylen Warren", "player_rush_yds", 70.5),))
        row = dict(jaylen()[3][0], result="W 30 - 22")
        s = self.run_intake([self.manual_final(), self.logs([jaylen([row])])])
        self.assertIn("disagrees", self.pending_items(s)["Jaylen Warren player_rush_yds"])

    def test_wrong_home_away_flag_does_not_match(self):
        self.pit_journal(props=(("Jaylen Warren", "player_rush_yds", 70.5),))
        row = dict(jaylen()[3][0], opponent="@Colts")
        s = self.run_intake([self.manual_final(), self.logs([jaylen([row])])])
        self.assertEqual(s["recorded_players"], [])

    def test_players_wait_for_the_team_final(self):
        self.pit_journal()
        s = self.run_intake([self.logs([jaylen(), tyler()])])
        self.assertEqual(s["recorded_players"], [])
        self.assertIn("final score is not in the journal", self.pending_items(s)["Jaylen Warren player_rush_yds"])
        self.assertEqual(s["exit_code"], 2)

    def test_manual_dnp_and_blank_stay_pending(self):
        self.pit_journal()
        path = self.write("manual.json", {"captured_utc": iso(LATER), "players": [
            {"player": "Jaylen Warren", "team": PIT, "event": "E-PIT", "market": "player_rush_yds",
             "status": "DNP", "value": 0, "source": "box score"},
            {"player": "Tyler Warren", "team": IND, "home_team": PIT, "away_team": IND,
             "market": "player_reception_yds", "value": None, "source": "box score"},
            {"player": "Jaylen Warren", "team": PIT, "event": "E-PIT", "market": "player_reception_yds",
             "value": "87", "source": "box score"}]})
        s = self.run_intake([self.manual_final(), path])
        self.assertEqual([(p["player"], p["market"], p["value"]) for p in s["recorded_players"]],
                         [("Jaylen Warren", "player_reception_yds", 87.0)])
        items = self.pending_items(s)
        self.assertIn("DNP", items["Jaylen Warren player_rush_yds"])
        self.assertIn("never zero", items["Tyler Warren player_reception_yds"])

    def test_conflicting_player_result_is_refused_not_overwritten(self):
        self.pit_journal(props=(("Tyler Warren", "player_reception_yds", 45.5),))
        J.record_final(self.journal, "E-PIT", 34, 22, "earlier", LATER)
        J.record_player_result(self.journal, "E-PIT", "Tyler Warren", "player_reception_yds", 80, "earlier", LATER)
        s = self.run_intake([self.logs([tyler()])])
        self.assertEqual(s["exit_code"], 1)
        self.assertIn("Not overwritten", s["refused"][0]["reason"])
        rows = [f for f in self.state().finals if f["type"] == "player"]
        self.assertEqual([r["value"] for r in rows], [80.0])


class TestFinals(Base):
    def test_not_final_status_stays_pending(self):
        self.pit_journal()
        path = self.write("lines.json", {"capture_complete_utc": iso(LATER), "games": [
            {"teams": {"home": PIT, "away": IND}, "kickoff_utc": iso(KICK), "state": "STATUS_IN_PROGRESS",
             "final_score": {"home": 20, "away": 13}, "source_url": "https://example.test/scoreboard"}]})
        s = self.run_intake([path])
        self.assertEqual(s["recorded_finals"], [])
        self.assertIn("not final", self.pending_items(s)["final score"])
        self.assertEqual(self.state().finals, [])
        self.assertEqual(s["exit_code"], 2)

    def test_final_before_earliest_final_time_is_refused(self):
        self.pit_journal()
        path = self.write("early.json", {"captured_utc": iso(KICK + datetime.timedelta(minutes=55)), "finals": [
            {"home_team": PIT, "away_team": IND, "home_score": 34, "away_score": 22, "status": "final",
             "source": "x"}]})
        s = self.run_intake([path], now=KICK + datetime.timedelta(minutes=60))
        self.assertEqual(s["exit_code"], 1)
        self.assertIn("cannot be final before", s["refused"][0]["reason"])
        self.assertEqual(self.state().finals, [])

    def test_capture_saying_final_too_early_is_refused(self):
        self.pit_journal()
        path = self.write("lines.json", {"capture_complete_utc": iso(KICK + datetime.timedelta(minutes=100)),
                                         "games": [{"teams": {"home": PIT, "away": IND}, "kickoff_utc": iso(KICK),
                                                    "state": "STATUS_FINAL", "final_score": {"home": 34, "away": 22},
                                                    "source_url": "https://example.test/scoreboard"}]})
        s = self.run_intake([path])
        self.assertEqual(s["exit_code"], 1)
        self.assertEqual(self.state().finals, [])

    def test_finished_time_before_earliest_final_is_refused(self):
        self.pit_journal()
        early = iso(KICK + datetime.timedelta(minutes=120))
        s = self.run_intake([self.manual_final(finished_utc=early)])
        self.assertEqual(s["exit_code"], 1)
        self.assertEqual(self.state().finals, [])

    def test_capture_from_the_future_is_refused(self):
        self.pit_journal()
        path = self.write("finals.json", {"captured_utc": iso(LATER + datetime.timedelta(hours=1)), "finals": [
            {"home_team": PIT, "away_team": IND, "home_score": 34, "away_score": 22, "status": "final",
             "source": "x"}]})
        s = self.run_intake([path])
        self.assertEqual(s["exit_code"], 1)
        self.assertEqual(self.state().finals, [])

    def test_halftime_absent_stays_pending(self):
        self.pit_journal(h1=True)
        s = self.run_intake([self.manual_final()])
        self.assertEqual(len(s["recorded_finals"]), 1)
        self.assertIn("first-half score", self.pending_items(s))
        self.assertEqual(s["exit_code"], 2)

    def espn(self, name="STATUS_FINAL", completed=True, state="post", captured=None):
        def side(where, team, score, lines):
            return {"homeAway": where, "team": {"displayName": team}, "score": str(score),
                    "linescores": [{"value": v} for v in lines]}
        doc = {"source_url": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261011",
               "events": [{"date": "2026-10-11T17:00Z", "competitions": [{
                   "status": {"type": {"name": name, "completed": completed, "state": state}},
                   "competitors": [side("home", PIT, 34, [7, 10, 7, 10]), side("away", IND, 22, [3, 6, 6, 7])]}]}]}
        if captured:
            doc["captured_utc"] = captured
        return self.write("espn.json", doc)

    def test_espn_scoreboard_final_with_halftime_from_linescores(self):
        self.pit_journal(h1=True, props=())
        s = self.run_intake([self.espn()])
        self.assertEqual(s["exit_code"], 0, s)
        sc = self.state().scores["E-PIT"]
        self.assertEqual((sc["home_score"], sc["away_score"], sc["h1_home"], sc["h1_away"]), (34, 22, 17, 9))
        h1 = [r for r in self.state().predictions if r["identity"]["market"] == "totals_h1"
              and r["identity"]["side"] == "Over"][0]
        self.assertEqual(J.settle(h1, self.state())[0], "win")       # 26 > 21.5

    def test_espn_needs_the_strict_final_status(self):
        self.pit_journal(props=())
        s = self.run_intake([self.espn(name="STATUS_END_PERIOD")])
        self.assertEqual(s["recorded_finals"], [])
        self.assertIn("not final", self.pending_items(s)["final score"])
        s = self.run_intake([self.espn(completed=False)])
        self.assertEqual(s["recorded_finals"], [])

    def test_conflicting_existing_final_is_refused_not_overwritten(self):
        self.pit_journal(props=())
        J.record_final(self.journal, "E-PIT", 20, 17, "earlier", LATER)
        s = self.run_intake([self.manual_final()])
        self.assertEqual(s["exit_code"], 1)
        self.assertIn("Not overwritten", s["refused"][0]["reason"])
        scores = [f for f in self.state().finals if f["type"] == "score"]
        self.assertEqual([(f["home_score"], f["away_score"]) for f in scores], [(20, 17)])

    def test_second_run_records_nothing_new(self):
        self.pit_journal()
        paths = [self.manual_final(), self.logs([jaylen(), tyler()])]
        first = self.run_intake(paths)
        n = len(self.state().finals)
        second = self.run_intake(paths)
        self.assertEqual((second["recorded_finals"], second["recorded_players"]), ([], []))
        self.assertEqual(second["already_recorded"], 4)
        self.assertEqual(len(self.state().finals), n)
        self.assertEqual(first["exit_code"], second["exit_code"])

    def test_halftime_added_later_is_recorded_once(self):
        self.pit_journal(h1=True, props=())
        self.run_intake([self.manual_final()])
        s = self.run_intake([self.manual_final(h1_home=17, h1_away=9)])
        self.assertEqual(s["exit_code"], 0, s)
        self.assertEqual(self.state().scores["E-PIT"]["h1_home"], 17)

    def test_rematch_with_far_kickoff_is_not_matched(self):
        self.pit_journal(props=())
        s = self.run_intake([self.manual_final(kickoff_utc=iso(KICK + datetime.timedelta(days=21)))])
        self.assertEqual(s["recorded_finals"], [])
        self.assertIn("final score", self.pending_items(s))

    def test_reversed_home_and_away_does_not_match(self):
        self.pit_journal(props=())
        path = self.write("finals.json", {"finals": [{"home_team": IND, "away_team": PIT, "home_score": 22,
                                                       "away_score": 34, "status": "final", "source": "x"}]})
        s = self.run_intake([path])
        self.assertEqual(s["recorded_finals"], [])

    def test_unknown_shape_is_refused(self):
        self.pit_journal(props=())
        s = self.run_intake([self.write("odd.json", {"hello": 1})])
        self.assertEqual(s["exit_code"], 1)
        self.assertIn("not a shape", s["refused"][0]["reason"])


class TestCliAndSafety(Base):
    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = P.main(["--data", self.data] + list(args))
        return code, out.getvalue()

    def test_exit_codes(self):
        self.pit_journal(props=())
        code, text = self.cli("--json", self.write("lines.json", {"capture_complete_utc": iso(LATER), "games": [
            {"teams": {"home": PIT, "away": IND}, "state": "STATUS_SCHEDULED", "final_score": {}}]}))
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(text)["exit_code"], 2)
        code, text = self.cli(self.manual_final())
        self.assertEqual(code, 0, text)
        self.assertIn("final: Indianapolis Colts at Pittsburgh Steelers, 22-34", text)
        code, _text = self.cli(self.write("odd.json", [1, 2]))
        self.assertEqual(code, 1)

    def test_empty_inbox_reports_everything_pending(self):
        self.pit_journal()
        empty = os.path.join(self.tmp, "inbox")
        os.makedirs(empty)
        old = P.INBOX
        P.INBOX = empty
        try:
            s = P.import_from_public(self.data, now=LATER)
        finally:
            P.INBOX = old
        self.assertEqual(s["exit_code"], 2)
        self.assertEqual(len(s["pending"]), 4)           # final + 3 player props

    def test_writes_only_journal_files_and_leaves_inputs_alone(self):
        self.pit_journal()
        paths = [self.manual_final(), self.logs([jaylen(), tyler()])]
        before = dict((p, J.sha256_file(p)) for p in paths)
        self.run_intake(paths)
        self.assertEqual(dict((p, J.sha256_file(p)) for p in paths), before)
        self.assertEqual(sorted(os.listdir(self.data)), [".lock", "finals.jsonl", "predictions.jsonl"])
        self.assertEqual(self.journal.verify()[1], [])

    def test_source_has_no_network_or_odds_feed(self):
        with open(os.path.join(HERE, "postgame.py")) as fh:
            src = fh.read()
        for word in ("urlopen", "urllib", "socket", "http.client", "requests", "odds_feed", "authorized_key"):
            self.assertNotIn(word, src)

    def test_help_lists_the_arguments(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                P.main(["--help"])
        self.assertIn("--data", out.getvalue())


if __name__ == "__main__":
    unittest.main()
