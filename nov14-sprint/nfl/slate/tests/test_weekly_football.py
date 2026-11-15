"""Use the saved Nov 22 capture and its real market-only API. Never acquire prices."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "weekly")]
import sunday_club_news
import weekly_api
import weekly_football


class WeeklyFootballTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reproducible even after the slate kicks off or newer editions arrive.
        actual_time = weekly_api.parse_ts("2026-11-15T07:50:00Z")
        edition = "a5d6b1057b4536b3d44be3b53c698489b6026067245587022d1e14a2c2ececb6"
        with patch.object(weekly_api, "clock", return_value=actual_time):
            cls.screen = weekly_api.screen("2026-11-22", edition=edition)
        cls.result = weekly_football.enrich(cls.screen)

    def test_real_archive_and_schedule(self):
        h = self.result["history"]
        self.assertEqual(h["data_through"], "2026-11-12")
        self.assertEqual(h["latest_complete_regular_week"], 9)
        self.assertEqual(h["sha256"], hashlib.sha256(weekly_football.DEFAULT_GAMES.read_bytes()).hexdigest())
        self.assertEqual(len(self.result["by_event"]), 11)
        night = self.screen["windows"][-1]["games"][0]
        ctx = self.result["by_event"][night["event_id"]]
        self.assertTrue(ctx["neutral_site"])
        self.assertFalse(ctx["home_field_applied"])
        self.assertEqual(ctx["home"]["team"], "SF")
        self.assertTrue(any(r["week"] == 10 for s in ("away","home") for r in ctx[s]["intervening_ungraded_games"]))

    def test_shortlist_matches_terms_and_can_abstain(self):
        contracts = {c["id"]:c for w in self.screen["windows"] for g in w["games"] for c in g["contracts"]}
        rows = self.result["shortlist"]
        self.assertEqual([len(self.result["by_window"][w]) for w in ("early","late","night")], [2,2,0])
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        late = [row for row in rows if row["window"] == "late"]
        self.assertEqual(late[0]["event_id"], late[1]["event_id"])
        self.assertIn(late[1]["id"], late[0]["shared_game_contract_ids"])
        for row in rows:
            c = contracts[row["id"]]
            self.assertEqual(c["best_in_band"]["price"], row["price"])
            self.assertEqual(c["best_in_band"]["book"], row["book"])
            self.assertGreaterEqual(row["market_books"], 2)
            self.assertGreater(min(row["model_probability"], row["market_probability"]), .5)
            self.assertGreaterEqual(200, abs(row["price"]))
            self.assertEqual(row["status"], "provisional")
            self.assertNotIn("minimum_price", row)
        potentials = self.result["ranked_potentials"]
        self.assertEqual([r["rank"] for r in potentials], [1, 2, 3, 4, 5])
        self.assertEqual(len({r["id"] for r in potentials}), 5)
        self.assertTrue(all(r["status"] == "watchlist" and r["id"] in contracts for r in potentials))

    def test_ineligible_and_unmatched_games(self):
        modified = copy.deepcopy(self.screen)
        original = json.dumps(modified, sort_keys=True)
        self.assertEqual(weekly_football.enrich(modified), self.result)
        self.assertEqual(json.dumps(modified, sort_keys=True), original)
        games = [g for w in modified["windows"] for g in w["games"]]
        for g in games:
            g["state"] = "started"
        self.assertFalse(weekly_football.enrich(modified)["shortlist"])
        game = games[0]
        game.update(state="scheduled", espn_event_id=None)
        self.assertIsNone(weekly_football.enrich(modified)["by_event"][game["event_id"]]["model"])

    def test_future_dated_absence_can_hold_without_changing_ratings(self):
        # Artificial personnel fixture on a real event: it tests control flow only.
        game = next(g for w in self.screen["windows"] for g in w["games"]
                    if g["event_id"] == self.result["shortlist"][0]["event_id"])
        eid, name = game["event_id"], game["away"]["name"]
        built = "2026-11-15T07:40:00Z"
        role = {"schema_version":"replacement_context/1", "event_id":eid, "team":name, "vs_starter":"unknown",
                "qualifier":"Test absence; replacement workload unknown.", "flag":"qualify",
                "absent":[{"player":"TEST ONLY"}], "next_men":[], "built_utc":built, "as_of_utc":built}
        event = {"event_id":eid, "away_team":name, "home_team":game["home"]["name"], "commence_utc":game["kickoff_utc"]}
        team = {"screen_status":"unknown_next_man", "replacement_context":role}
        report = {"schema_version":"replacement_report/1", "paper_only":True, "built_utc":built, "as_of_utc":built,
                  "inputs":[{"sha256":self.screen["edition"]["sha256"], "captured_utc":self.screen["edition"]["captured_utc"]}], "by_event":{eid:{"event":event,"teams":{name:team}}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"test-role.json"
            path.write_text(json.dumps(report))
            test = weekly_football.enrich(self.screen, replacement_path=path)
            self.assertEqual(test["by_event"][eid]["review_status"],"hold_for_replacement_review")
            self.assertEqual(test["by_event"][eid]["model"],self.result["by_event"][eid]["model"])
            self.assertNotIn(eid, [r["event_id"] for r in test["ranked_potentials"]])
            report["inputs"] = [{"sha256":"another capture"}]
            path.write_text(json.dumps(report))
            self.assertEqual(weekly_football.enrich(self.screen,replacement_path=path)["shortlist"],self.result["shortlist"])

    def test_real_available_starter_must_match_absent_player_and_team(self):
        path = ROOT / "weekly_inputs/2026-11-15/availability/capture-20261115T081240889917Z-e631c718b29760b8a0fd1acfe9d059af5ee47dd75bea695c087bb4ee23d140e1.json"
        saved = json.loads(path.read_bytes())
        ev = next(e for e in saved["by_event"].values() if e["teams"] == ["MIN","GB"])
        game = {"away":{"name":"Minnesota Vikings"}, "home":{"name":"Green Bay Packers"},
                "kickoff_utc":ev["kickoff_utc"], "espn_event_id":ev["espn_event_id"]}
        as_of = "2026-11-15T08:15:00Z"
        role = {"screen_status":"screened", "team":"Green Bay Packers", "absent":[{"player":"Josh Jacobs"},{"player":"Sean Rhyan"}],
                "capability":{"starter":{"player":"Josh Jacobs"}},
                "opportunity":[{"player":"TEST ONLY","role":[{"text":"fixture role", "source":{"url":"https://example.com"}}]}],
                "next_men":[{"player":"TEST ONLY"}]}
        result = weekly_football._availability_for(game,saved,[role],as_of)
        self.assertNotIn("Josh Jacobs", {r["player"] for r in result["unresolved_starters"]})
        self.assertIn("Sean Rhyan", {r["player"] for r in result["unresolved_starters"]})
        names_only = weekly_football._availability_for(game,saved,[dict(role,opportunity=[])],as_of)
        self.assertIn("Josh Jacobs",{r["player"] for r in names_only["unresolved_starters"]})
        other = dict(role,team="Minnesota Vikings")
        unknown = weekly_football._availability_for(game,saved,[other],as_of)
        self.assertIn("Josh Jacobs", {r["player"] for r in unknown["unresolved_starters"]})
        self.assertTrue(all(r["observed_utc"] and r["source_url"] for r in unknown["unresolved_starters"]))
        early = weekly_football._availability_for(game,saved,[other],"2026-11-15T07:00:00Z")
        self.assertFalse(early["records"])

    def test_assessing_one_player_cannot_clear_a_material_teammate(self):
        game = next(g for w in self.screen["windows"] for g in w["games"]
                    if g["event_id"] == self.result["shortlist"][0]["event_id"])
        eid = game["event_id"]
        name = game["away"]["name"]
        away, home = (weekly_football.picker.ABBR[game[s]["name"]] for s in ("away","home"))
        stamp = "2026-11-15T07:40:00Z"
        source = {"url":"https://www.nfl.com/", "retrieved_utc":stamp}
        role = {"schema_version":"replacement_context/1","team":name,"event_id":eid,"as_of_utc":stamp,
                "absent":[{"player":"Fixture RB"},{"player":"Fixture OT"}],
                "next_men":[{"player":"Fixture backup"}],"qualifier":"Fixture lead role."}
        team = {"screen_status":"screened","starter":{"player":"Fixture RB"},"replacement_context":role,
                "candidates":[{"player":"Fixture backup","role_evidence":[{"text":"Fixture lead role.","source":source}]}]}
        matchup = dict(event_id=eid, away_team=name, home_team=game["home"]["name"], commence_utc=game["kickoff_utc"])
        receipt = {"schema_version":"replacement_report/1","paper_only":True,"built_utc":stamp,"as_of_utc":stamp,
                   "inputs":[{"sha256":self.screen["edition"]["sha256"], "captured_utc":self.screen["edition"]["captured_utc"]}],
                   "by_event":{eid:{"event":matchup,"teams":{name:team}}}}
        base = dict(team=away, status="Out", source_url=source["url"], observed_utc=stamp)
        records = [dict(base,player="Fixture RB",position="RB",starter_status="listed_first"),
                   dict(base,player="Fixture OT",position="OT",origin="operator_bulletin",
                        starter_status="operator_identified",reported_material=True)]
        event = dict(status="partial", teams=[away,home], kickoff_utc=game["kickoff_utc"],records=records)
        data = dict(status="partial",by_event={game["espn_event_id"]:event})
        with tempfile.TemporaryDirectory() as tmp, patch.object(weekly_football,"_read_availability",return_value=data):
            path = Path(tmp)/"roles.json"
            path.write_text(json.dumps(receipt))
            held = weekly_football.enrich(self.screen,replacement_path=path)
            ctx = held["by_event"][eid]
            self.assertEqual([r["player"] for r in ctx["availability"]["unresolved_starters"]],["Fixture OT"])
            self.assertEqual(ctx["review_status"],"hold_for_replacement_review")
            self.assertEqual(ctx["model"],self.result["by_event"][eid]["model"])
            self.assertNotIn(eid, [r["event_id"] for r in held["shortlist"]])
            records[-1]["reported_material"] = False
            released = weekly_football.enrich(self.screen,replacement_path=path)
            self.assertEqual(released["by_event"][eid]["review_status"],"conditional_role_review")
            self.assertIn(eid, [r["event_id"] for r in released["shortlist"]])

    def test_pregame_role_news_flows_from_saved_club_notes_to_rankings(self):
        day = self.screen["date"]
        eid = self.result["shortlist"][0]["event_id"]
        game = next(g for w in self.screen["windows"] for g in w["games"] if g["event_id"] == eid)
        name, opponent = game["away"]["name"], game["home"]["name"]
        team = weekly_football.picker.ABBR[name]
        other = weekly_football.picker.ABBR[opponent]
        cutoff, assembled = "2026-11-15T07:38:00Z", "2026-11-15T07:43:00Z"
        prior_text = "Fixture Lead is expected to take the lead role."
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / day
            folder.mkdir()
            raw = (ROOT / "weekly_inputs" / day / "schedule.json").read_bytes()
            (folder / "schedule.json").write_bytes(raw)
            schedule = json.loads(raw)

            def bulletin(player, status, minute, club=team):
                fields = dict(club_team=game["espn_event_id"] + "/" + club, player=player, position="RB",
                              designation=status, source="https://www.nfl.com/", published="2026-11-15",
                              material="yes", role="Synthetic fixture for later pregame news.")
                sunday_club_news.store(day, schedule, root, fields, now=weekly_api.parse_ts("2026-11-15T" + minute + ":00Z"))

            def role_file(committee):
                next_men = ["Fixture Lead", "Fixture Depth"] + (["Fixture Committee"] if committee else [])
                role = {"schema_version":"replacement_context/1", "team":name, "event_id":eid, "as_of_utc":cutoff,
                        "absent":[{"player":"Fixture Starter","status":"out"}],
                        "next_men":[{"player":n} for n in next_men], "qualifier":prior_text, "flag":"qualify"}
                candidates = []
                for n in next_men:
                    url = "https://www.nfl.com/team/depth-chart" if n == "Fixture Depth" else "https://www.nfl.com/news/role"
                    candidates.append({"player":n, "role_evidence":[{"text":"Synthetic role observation.",
                                       "source":{"url":url,"retrieved_utc":cutoff}}]})
                assessed = {"screen_status":"screened", "starter":{"player":"Fixture Starter"},
                            "replacement_context":role, "candidates":candidates}
                event = {"event_id":eid,"away_team":name,"home_team":opponent,"commence_utc":game["kickoff_utc"]}
                receipt = {"schema_version":"replacement_report/1", "paper_only":True, "built_utc":assembled,
                           "as_of_utc":cutoff, "inputs":[self.screen["edition"]],
                           "by_event":{eid:{"event":event,"teams":{name:assessed}}}}
                path = root / ("committee.json" if committee else "sole.json")
                path.write_text(json.dumps(receipt))
                return path

            sole, committee = role_file(False), role_file(True)
            def run(minute, path=sole):
                screen = dict(self.screen, generated_utc="2026-11-15T" + minute + ":00Z")
                output = weekly_football.enrich(screen, replacement_path=path, inputs_root=root)
                ctx = output["by_event"][eid]
                self.assertEqual(ctx["model"], self.result["by_event"][eid]["model"])
                shortlisted = any(r["event_id"] == eid for r in output["shortlist"])
                return ctx["review_status"], shortlisted, ctx["replacement_context"][0]

            # Club notes are stored independently and may be read in a different order.
            bulletin("Fixture Starter", "Out", "07:37")
            bulletin("Fixture Lead", "Out", "07:40", club=other)
            before = run("07:43")
            self.assertEqual(before[:2], ("hold_for_replacement_review", False))  # material opposing absence
            self.assertEqual(before[2]["display"], prior_text)  # identically named opponent never supersedes the role
            bulletin("Fixture Lead", "Designation removed", "07:41", club=other)
            self.assertTrue(run("07:43")[1])
            bulletin("Fixture Lead", "Out", "07:45")
            held, matches, now = run("07:46")
            self.assertEqual((held, matches), ("hold_for_replacement_review", False))
            self.assertEqual(now["prior_review"]["display"], prior_text)
            self.assertNotIn("Fixture Depth", now["display"])
            self.assertEqual(now["next_men"], [])
            self.assertEqual(run("07:43")[2], before[2])

            status, matches, split = run("07:46", committee)
            self.assertEqual((status, matches), ("conditional_role_review", True))
            self.assertEqual([n["player"] for n in split["next_men"]], ["Fixture Committee"])
            self.assertIn("split", split["display"])
            self.assertNotIn(prior_text, split["display"])

            bulletin("Fixture Starter", "Designation removed", "07:48")
            _, _, returned = run("07:49")
            self.assertEqual(returned["screen_status"], "starter_cleared")
            self.assertEqual(returned["next_men"], [])
            self.assertNotIn(prior_text, returned["display"])
            self.assertIn("designation was removed", returned["display"])

            # A note observed after the source cutoff but BEFORE report assembly also supersedes the role.
            bulletin("Fixture Lead", "Out", "07:39")
            status, matches, revised = run("07:43")
            self.assertEqual((status, matches), ("hold_for_replacement_review", False))
            self.assertEqual(weekly_api.parse_ts(revised["latest_source_utc"]), weekly_api.parse_ts("2026-11-15T07:39:00Z"))
            self.assertEqual(revised["effective_as_of_utc"], assembled)

    def test_late_entry_cannot_reorder_published_player_news(self):
        # Exercise the normalized Kansas City assessment with hypothetical entries, never current news.
        from selection_release import read_report
        eid = "3c71d515b726f1096aabb435badb83fd"
        prices = "2a50d6951366342f8656ee01e113c44cceff0acdfa027ea933f9286c0c73d56f"
        game = dict(away_name="Kansas City Chiefs", home_name="Atlanta Falcons", kickoff_utc="2026-11-15T18:00:00Z")
        roles, _ = read_report("2026-11-15", prices, {eid:game}, "2026-11-15T09:44:00Z")
        role = next(r for r in roles[eid] if r["team"] == game["away_name"])
        match = dict(event_id=eid, espn_event_id="401873058", away={"name":game["away_name"]},
                     home={"name":game["home_name"]}, kickoff_utc=game["kickoff_utc"])
        note = dict(team="KC", player="Kenneth Walker III", status="Designation removed", origin="operator_bulletin",
                    position="RB", source_url="https://www.chiefs.com/", observed_utc="2026-11-15T09:44:00Z")
        def review(published):
            ev = dict(teams=["KC","ATL"], kickoff_utc=game["kickoff_utc"], status="partial",
                      records=[dict(note, published=published)])
            return weekly_football._availability_for(match, {"status":"partial","by_event":{"401873058":ev}}, [role],
                                                     "2026-11-15T09:45:00Z")
        older = review("2026-11-12")
        self.assertEqual(older["replacement_context"], [role])
        self.assertEqual(older["superseded_records"][0]["player"], note["player"])
        same_day = review("2026-11-14")["replacement_context"][0]
        self.assertEqual(same_day["flag"], "qualify")
        self.assertIn("publication order is unknown", same_day["display"])
        self.assertNotEqual(same_day["screen_status"], "starter_cleared")
        later = review("2026-11-15")["replacement_context"][0]
        self.assertEqual(later["screen_status"], "starter_cleared")
        self.assertEqual(later["prior_review"], role)

    def test_real_green_bay_role_with_fractional_publication_seconds(self):
        from selection_release import read_report
        eid = "5d8d85473b87f772a979ecf294acab94"
        prices = "2a50d6951366342f8656ee01e113c44cceff0acdfa027ea933f9286c0c73d56f"
        game = dict(away_name="Minnesota Vikings", home_name="Green Bay Packers", kickoff_utc="2026-11-15T18:00:00Z")
        roles, _ = read_report("2026-11-15", prices, {eid:game}, "2026-11-15T09:44:00Z")
        role = next(r for r in roles[eid] if r["team"] == game["home_name"])
        publications = weekly_football._prior_publications(role)
        self.assertEqual(publications["kalebjohnson"].microsecond, 160000)
        rec = dict(team="GB", player="Josh Jacobs", status="Designation removed", source_url="https://www.packers.com/",
                   observed_utc="2026-11-15T09:44:00Z", published="2026-11-15")
        current, _, _ = weekly_football._current_role(role, "GB", {("GB","joshjacobs"):rec}, None)
        self.assertEqual(current["screen_status"], "starter_cleared")
        self.assertEqual(current["prior_review"]["display"], role["display"])
        older = dict(rec, published="2026-11-10")
        conflict, _, _ = weekly_football._current_role(role, "GB", {("GB","joshjacobs"):older}, None)
        self.assertEqual(conflict["flag"], "qualify")
        self.assertNotEqual(conflict["screen_status"], "starter_cleared")
        self.assertIn("2026-11-10", conflict["display"])
        self.assertIn("publication order is unknown", conflict["display"])

    def test_weekly_archive_and_club_note_replay_at_the_same_time(self):
        day = "2026-11-15"
        source = ROOT / "weekly_inputs" / day
        filename = ("capture-20261115T081736812027Z-"
                    "e631c718b29760b8a0fd1acfe9d059af5ee47dd75bea695c087bb4ee23d140e1.json")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / day
            (folder / "availability").mkdir(parents=True)
            raw = (source / "schedule.json").read_bytes()
            (folder / "schedule.json").write_bytes(raw)
            (folder / "availability" / filename).write_bytes((source / "availability" / filename).read_bytes())
            screen = dict(date=day, inputs={"schedule":{"sha256":hashlib.sha256(raw).hexdigest()}})
            fields = dict(club_team="401873058/KC", player="Fixture Player", position="RB", designation="Out",
                          source="https://www.chiefs.com/", published=day, role="Synthetic bulletin.")
            sunday_club_news.store(day, json.loads(raw), root, fields, now=weekly_api.parse_ts(day + "T08:30:00Z"))

            def replay(time):
                return weekly_football._read_availability(dict(screen, generated_utc=day + "T" + time + "Z"), root)

            self.assertEqual(replay("08:00:00")["status"], "uncaptured")
            before, after = replay("08:29:00"), replay("08:50:00")
            for result in (before, after):
                self.assertEqual(result["captured_utc"], day + "T08:17:36.812027Z")
            def players(result):
                return {r["player"] for r in result["by_event"]["401873058"]["records"]}
            self.assertNotIn("Fixture Player", players(before))
            self.assertEqual(players(after), players(before) | {"Fixture Player"})
            self.assertEqual(before, replay("08:29:00"))

    def test_missing_receipt_and_post_edition_archive_hold(self):
        self.assertFalse(weekly_football.enrich(self.screen, ROOT/"missing-games.csv")["shortlist"])
        old = dict(self.screen, edition=dict(self.screen["edition"], captured_utc="2026-11-13T00:00:00Z"))
        result = weekly_football.enrich(old)
        self.assertFalse(result["shortlist"])
        self.assertIn("after this price edition", result["warnings"][0])


if __name__ == "__main__":
    unittest.main()
