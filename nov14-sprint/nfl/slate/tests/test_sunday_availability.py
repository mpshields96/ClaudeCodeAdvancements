"""Public source fixture regressions; no network, no edits to the real weekly inputs."""
import copy
import csv
import gzip
import io
import json
from datetime import timedelta
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sunday_availability as availability

FIXTURE = Path(__file__).parent / "fixtures" / "sunday_availability_2026.json"

class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads(FIXTURE.read_text())
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "weekly_inputs"
        self.now = availability._instant("2026-11-15T08:12:50Z")
        self.clock = patch.object(availability, "_now", side_effect=lambda:self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.download = patch.object(availability, "_download", side_effect=self.feed).start()
        self.addCleanup(patch.stopall)

    def feed(self, kind, season):
        self.assertEqual(season, 2026)
        rows = self.case[kind]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
        meta = dict(self.case["evidence"][kind], observed_utc=availability._stamp(self.now))
        return gzip.compress(buf.getvalue().encode()), meta

    def capture(self, week="week10"):
        day = "2026-11-15" if week=="week10" else "2026-11-22"
        return availability.capture(day, self.case[week], self.root)

    def test_gb_and_kc_from_actual_source_rows(self):
        r = self.capture()
        self.assertEqual(r["status"], "reported")
        gb = {x["player"]:x for x in r["by_event"]["401873060"]["records"] if x["team"]=="GB"}
        self.assertEqual(gb["Zaire Franklin"]["status"], "Doubtful")
        jacobs = gb["Josh Jacobs"]
        self.assertEqual((jacobs["status"],jacobs["starter_status"],jacobs["materiality"]), ("Out","listed_first","unknown"))
        self.assertIsNone(jacobs["player_published_utc"])
        self.assertEqual(jacobs["observed_utc"],availability._stamp(self.now))
        self.assertEqual([(c["player"],c["rank"],c["injury_designation"]) for c in jacobs["candidates"]],
                         [("MarShawn Lloyd",2,"unknown"),("Chris Brooks",3,"Questionable")])
        self.assertTrue(all(c["status"]=="candidate_only" and c["chart_utc"]<c["observed_utc"] for c in jacobs["candidates"]))
        kc = [a for a in r["by_event"]["401873058"]["records"] if a["team"]=="KC"]
        self.assertEqual({(a["player"],a["status"]) for a in kc},
                         {("Jaylon Moore","Out"),("Peter Woods","Out"),("Omarr Norman-Lott","Out")})

    def test_week11_does_not_copy_week10(self):
        self.capture()
        self.download.reset_mock()
        future = self.capture("week11")
        self.assertEqual(future["status"],"no_week_data")
        self.assertTrue(all(not ev["records"] for ev in future["by_event"].values()))
        self.assertEqual(future["sources"]["injuries_2026"]["latest_regular_week"],10)
        self.download.assert_called_once_with("injuries",2026)

    def test_offline_empty_cache_ttl_and_changed_schedule(self):
        s=self.case["week10"]
        self.assertEqual(availability.read("2026-11-15",s,self.root)["status"],"uncaptured")
        self.assertFalse(self.root.exists())
        original=self.capture()
        self.download.reset_mock()
        self.assertEqual(availability.read("2026-11-15",s,self.root),original)
        self.assertEqual(self.capture(),original)
        self.download.assert_not_called()
        changed=copy.deepcopy(s)
        changed["events"][0]["date"]="2026-11-15T19:05:00Z"
        self.assertEqual(availability.read("2026-11-15",changed,self.root)["status"],"uncaptured")
        self.now+=availability.TTL
        old=availability.read("2026-11-15",s,self.root)
        self.assertEqual(old["status"],"stale")
        self.assertTrue(all(not ev["records"] for ev in old["by_event"].values()))
        self.download.assert_not_called()
        self.assertEqual(self.capture()["status"],"reported")
        self.assertEqual(len(list((self.root/"2026-11-15/availability").glob("capture-*.json"))),2)

    def test_past_or_future_depth_and_conflicting_designations(self):
        for row in self.case["depth_charts"]:
            row["dt"] = "2026-11-09T07:00:00Z" if row["team"]=="GB" else "2026-11-15T11:00:00Z"
        jac = next(r for r in self.case["injuries"] if r["full_name"]=="Josh Jacobs")
        self.case["injuries"].append(dict(jac,report_status="Questionable"))
        r=self.capture()
        self.assertEqual(r["sources"]["depth_charts_2026"]["chart_timestamps_by_team"],{})
        gb=r["by_event"]["401873060"]
        self.assertFalse(any(a["player"]=="Josh Jacobs" for a in gb["records"]))
        self.assertTrue(all(not a["depth_ranks"] and not a["candidates"] for a in gb["records"]))
        self.assertEqual(gb["team_coverage"]["GB"]["conflicting_player_statuses"],1)

    def test_archived_editions_use_their_own_capture_and_ttl(self):
        def read_at(when):
            return availability.read("2026-11-15", self.case["week10"], self.root, as_of=when)
        first_at = self.now
        first = self.capture()
        self.now += availability.TTL + timedelta(minutes=5)
        second_at = self.now
        self.case["injuries"] = [r for r in self.case["injuries"] if r["full_name"] != "Josh Jacobs"]
        second = self.capture()
        self.now += timedelta(days=2)
        self.download.reset_mock()
        self.assertEqual(read_at(first_at - timedelta(microseconds=1))["status"], "uncaptured")
        self.assertEqual(read_at(first_at), first)
        self.assertEqual(read_at((first_at + timedelta(minutes=30)).astimezone(availability.CENTRAL)), first)
        expired = read_at(first_at + availability.TTL)
        self.assertEqual(expired["status"], "stale")
        self.assertTrue(all(not game["records"] for game in expired["by_event"].values()))
        self.assertEqual(read_at(second_at), second)
        self.assertEqual(read_at(None)["status"], "stale")
        with self.assertRaises(ValueError):
            read_at(first_at.replace(tzinfo=None))
        self.download.assert_not_called()

    def test_archived_cutoff_at_kickoff(self):
        self.now = availability._instant("2026-11-15T17:30:00Z")
        self.capture()
        self.now += timedelta(days=1)
        def status(when):
            return availability.read("2026-11-15", self.case["week10"], self.root,
                                     as_of=availability._instant(when))
        self.assertEqual(status("2026-11-15T17:59:59Z")["status"], "reported")
        started = status("2026-11-15T18:00:00Z")
        self.assertEqual(started["status"], "started")
        self.assertTrue(all(not ev["records"] for ev in started["by_event"].values()))

    def test_archived_selection_requires_verified_identity_and_timestamp(self):
        first = self.capture()
        folder = self.root / "2026-11-15/availability"
        first_path = next(folder.glob("capture-*.json"))
        cutoff = self.now + timedelta(minutes=10)
        def read_at():
            return availability.read("2026-11-15", self.case["week10"], self.root, as_of=cutoff)
        # A renamed payload retains a valid checksum but cannot backdate a later capture.
        self.now += availability.TTL
        self.capture()
        later = max(folder.glob("capture-*.json"))
        mismatched = folder / availability._capture_name(cutoff, first["schedule_sha256"])
        later.rename(mismatched)
        self.assertEqual(read_at(), first)
        first_path.unlink()
        self.assertEqual(read_at()["status"], "unreadable")
        mismatched.write_text(json.dumps({"revision": 1}))
        self.assertEqual(read_at()["status"], "refresh_required")
        changed = copy.deepcopy(self.case["week10"])
        changed["events"][0]["date"] = "2026-11-15T19:00:00Z"
        self.assertEqual(availability.read("2026-11-15", changed, self.root, as_of=cutoff)["status"],
                         "uncaptured")

    def test_team_coverage_and_postkickoff(self):
        self.case["injuries"]=[r for r in self.case["injuries"] if r["team"]!="ATL"]
        self.assertEqual(self.capture()["by_event"]["401873058"]["status"],"partial")
        self.now=availability._instant("2026-11-15T23:00:00Z")
        r=self.capture()
        self.assertEqual(r["status"],"started")
        self.assertTrue(all(not g["records"] for g in r["by_event"].values()))

    def test_injury_and_depth_outages_keep_distinct_evidence(self):
        self.download.side_effect=OSError("offline")
        self.assertEqual(self.capture()["status"],"source_error")
        def missing_depth(kind,season):
            if kind=="depth_charts":raise OSError("offline")
            return self.feed(kind,season)
        self.download.side_effect=missing_depth
        self.now+=timedelta(seconds=1)
        r=self.capture()
        self.assertEqual(r["status"],"partial")
        self.assertEqual(r["sources"]["depth_charts_2026"]["status"],"error")
        self.assertTrue(all(not a["candidates"] and a["starter_status"]=="unknown" for e in r["by_event"].values() for a in e["records"]))
        self.assertTrue(any("Depth chart unavailable" in s for s in r["limitations"]))
        self.download.side_effect=self.feed
        self.now+=timedelta(seconds=1)
        self.assertEqual(self.capture()["status"],"reported")

    def test_reject_duplicate_team_and_ambiguous_candidate(self):
        bad = copy.deepcopy(self.case["week10"])
        bad["events"][1]["competitions"][0]["competitors"][0]["team"]["abbreviation"]="KC"
        with self.assertRaises(ValueError):
            availability.read("2026-11-15",bad,self.root)
        self.case["injuries"].append(dict(self.case["injuries"][0],team="GB",full_name="MarShawn Lloyd",gsis_id="wrong",report_status="Out"))
        next(d for d in self.case["depth_charts"] if d["player_name"]=="Chris Brooks")["gsis_id"]=""
        gb=self.capture()["by_event"]["401873060"]["records"]
        self.assertEqual(next(r for r in gb if r["player"]=="Josh Jacobs")["candidates"],[])

    def test_partial_report_and_corrupt_saved_event(self):
        for r in self.case["injuries"]:
            if r["team"]=="KC":r["report_status"]=""
        r=self.capture()
        self.assertEqual(r["by_event"]["401873058"]["status"],"partial")
        self.assertEqual(r["by_event"]["401873058"]["team_coverage"]["KC"]["status"],"rows_without_game_designations")
        p=next((self.root/"2026-11-15/availability").glob("capture-*.json"))
        body=json.loads(p.read_text())
        body["by_event"]["401873058"]["week"]=11
        p.write_text(json.dumps(body))
        v=availability.read("2026-11-15",self.case["week10"],self.root)
        self.assertEqual(v["status"],"unreadable")
        self.assertFalse(any(e["records"] for e in v["by_event"].values()))

if __name__ == "__main__":
    unittest.main()
