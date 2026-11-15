"""The role evidence is additive, dated and bound to a real offered contract."""
import copy
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import picker
import selection_release as release


class DecisionReplacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = json.loads((HERE/"results/sunday_20261115_selections.json").read_bytes())

    def test_integrity_checks_hash_the_code_that_actually_scores(self):
        frozen = json.loads((HERE/"frozen_picker.json").read_bytes())
        self.assertEqual(frozen["code_sha256"], picker.freeze_inputs())
        self.assertEqual(frozen["code_sha256"]["picker.py"], picker.sha256_file(HERE/"issued_picker_20261115.py"))
        self.assertNotEqual(frozen["code_sha256"]["picker.py"], picker.sha256_file(HERE/"picker.py"))

    def test_missing_evidence_and_bad_identity(self):
        sel = self.selection
        call = copy.deepcopy(sel["calls"][0])
        release._bound_call(call, [], sel["slate_date"], sel["capture_sha256"])
        self.assertEqual(call["replacement_context"], [])
        self.assertIn("Unknown", call["replacement_review_status"])
        call["period"] = "first_half"
        with self.assertRaises(ValueError):
            release._bound_call(call, [], sel["slate_date"], sel["capture_sha256"])

    def test_append_only_and_wrong_capture_refused(self):
        s = self.selection
        c = copy.deepcopy(s["calls"][0])
        material = {k:v for k,v in c.items() if not k.startswith("replacement_")}
        role = {"date":s["slate_date"],"event_id":c["event_id"], "capture_sha256":s["capture_sha256"],
                "effective_as_of_utc":"2026-11-15T07:52:05Z", "players":["a matched player"], "status":"estimated"}
        release._bound_call(c, [role], s["slate_date"], s["capture_sha256"])
        record = c["replacement_context"][0]
        self.assertTrue(record["evidence_after_issue"])
        self.assertEqual(record["applies_to"]["id"],c["id"])
        self.assertEqual(material,{k:v for k,v in c.items() if not k.startswith("replacement_")})
        with self.assertRaises(ValueError):
            release._bound_call(c, [dict(role, capture_sha256="other")], s["slate_date"], s["capture_sha256"])

    def test_sources_and_record_must_be_pregame(self):
        s = self.selection
        c = copy.deepcopy(s["calls"][0])
        row = {"date":s["slate_date"],"event_id":c["event_id"],"capture_sha256":s["capture_sha256"],
               "effective_as_of_utc":"2026-11-15T07:52:05Z"}
        for invalid in (dict(row, effective_as_of_utc=c["kickoff"]),
                        dict(row, sources=[{"observed_utc":c["kickoff"]}]),
                        dict(row, sources=[{"observed_utc":"2026-11-15T07:53:00Z"}])):
            with self.assertRaises(ValueError):
                release._bound_call(c,[invalid],s["slate_date"],s["capture_sha256"])

    def test_real_release_contains_source_bound_chiefs_and_packers_assessments(self):
        full = json.loads((HERE/"results/sunday_20261115_candidates.json").read_bytes())
        receipt = full["inputs"]["replacement_evidence"]
        self.assertEqual(receipt["sha256"],picker.sha256_file(HERE/"replacements/replacement_report_20261115.json"))
        self.assertFalse(receipt["skipped"])
        games = {g["game"]:g for g in full["slate"]["games"]}
        kc, = games["KC at ATL"]["replacement_context"]
        gb, = games["MIN at GB"]["replacement_context"]
        self.assertEqual(kc["team_price_effect"]["win_probability_adjustment"],None)
        self.assertEqual(kc["versus_priced_expectation"]["incremental_surprise"],"unknown")
        priced = next(v for v in kc["opportunity"] if v["player"] == "Emmett Johnson")["markets"]["stats"]
        self.assertEqual(priced["rush_attempts"]["line_median"],16.5)
        self.assertEqual(len({q["book"] for q in priced["rush_attempts"]["books"]}),3)
        self.assertEqual((priced["rush_yds"]["line_min"],priced["rush_yds"]["line_max"]),(72.5,75.5))
        self.assertTrue(any(p["interpretation"] for p in kc["game_script"]))
        self.assertTrue({"Kaleb Johnson","MarShawn Lloyd"}.issubset(gb["players"]))
        self.assertTrue(all(row["effective_as_of_utc"] > self.selection["decided_utc"] for row in (kc,gb)))
        self.assertEqual(len(self.selection["calls"][0]["replacement_context"]),1)
        self.assertEqual(len(self.selection["calls"][1]["replacement_context"]),0)
        self.assertFalse(games["PIT at CIN"]["replacement_context"])

    def test_unavailable_backup_cannot_lead_the_summary(self):
        team = {"team":"Example", "starter":{"player":"Starter"}, "replacement_context":{
                "next_men":[{"player":"Former backup"}], "absent":[{"player":"Starter","status":"Out"}]},
                "candidates":[{"player":"Former backup","availability":{"status":"Out"},
                               "market":{"stats":{"rush_yds":{"line_min":50.5, "line_max":50.5}}}}]}
        self.assertNotIn("Former backup",release._display(team,"Opponent"))
        self.assertFalse(release._active_next_men(team))

    def test_prop_needs_person_in_the_same_event(self):
        s = self.selection
        c = copy.deepcopy(s["calls"][1])
        row = {"date": s["slate_date"],"event_id":c["event_id"],"capture_sha256":s["capture_sha256"],
               "effective_as_of_utc":"2026-11-15T07:52:05Z","players":["different player"]}
        release._bound_call(c,[row],s["slate_date"],s["capture_sha256"])
        self.assertFalse(c["replacement_context"])


if __name__ == "__main__":
    unittest.main()
