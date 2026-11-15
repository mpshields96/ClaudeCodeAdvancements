"""Offline tests for binding ESPN's final box to exact full-game journal contracts."""
import concurrent.futures
import copy
import datetime
import json
import os
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from test_postgame import Base, KICK, LATER, PIT, IND, iso
import espn_fetch as F
import journal as J
import postgame as P

def player(pid,name,stats):
    return {"athlete":{"id":pid,"displayName":name},"stats":stats}
def group(category,keys,athletes):
    return {"name":category,"keys":keys,"athletes":athletes}
def sample():
    sides = [{"homeAway":side,"team":{"id":tid,"displayName":team},"score":score,
              "linescores":[{"displayValue":n} for n in halves]}
             for side,tid,team,score,halves in (("home","23",PIT,"34",["7","10"]),("away","11",IND,"22",["6","7"]))]
    comp={"id":"401872985","date":iso(KICK),"competitors":sides,
          "status":{"type":{"completed":True,"name":"STATUS_FINAL","state":"post"}}}
    header={"id":comp["id"],"league":{"slug":"nfl"},"competitions":[comp]}
    pstats=[group("receiving",["receptions","receivingYards"],[player("1","Jaylen Warren",["6","87"])]),
            group("rushing",["rushingYards","rushingAttempts"],[player("1","Jaylen Warren",["101","15"])]),
            group("passing",["passingYards","completions/passingAttempts"],[player("2","Aaron Rodgers",["235","22/31"])])]
    istats=[group("receiving",["receivingYards","receptions"],[player("3","Tyler Warren",["83","7"])])]
    return {"header":header,"boxscore":{"players":[{"team":sides[0]["team"],"statistics":pstats},
                                                   {"team":sides[1]["team"],"statistics":istats}]}}

class TestESPNBox(Base):
    def box(self, d, name="summary.json"):
        return self.write(name,d)
    def test_two_warrens_named_stats_combined_pass_and_halves(self):
        self.pit_journal(props=[("Jaylen Warren","player_rush_yds",70.5),("Jaylen Warren","player_reception_yds",20.5),
            ("Tyler Warren","player_reception_yds",45.5),("Aaron Rodgers","player_pass_completions",20.5),
            ("Aaron Rodgers","player_pass_attempts",30.5)], h1=True)
        path=self.box(sample())
        r=self.run_intake([path])
        self.assertEqual(r["exit_code"],0,r)
        self.assertEqual(r["recorded_finals"][0]["h1"],[13,17])
        self.assertEqual(sorted(x["value"] for x in r["recorded_players"]),[22,31,83,87,101])
        self.assertEqual(self.run_intake([path])["already_recorded"],6)
    def test_no_row_or_dnp_is_pending_and_posted_zero_is_accepted(self):
        self.pit_journal(props=[("Jaylen Warren","player_reception_yds",20.5),("Tyler Warren","player_rush_yds",1.5),
                                ("Aaron Rodgers","player_pass_yds",249.5)])
        d=sample()
        d["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["stats"]=["0","0"]
        d["boxscore"]["players"][0]["statistics"][2]["athletes"][0]["didNotPlay"]=True
        s=self.run_intake([self.box(d)])
        self.assertEqual([(p["player"],p["value"]) for p in s["recorded_players"]],[("Jaylen Warren",0)])
        self.assertEqual(len(s["pending"]),2)
    def test_lineup_and_match_identity(self):
        self.pit_journal()
        d=sample()
        d["boxscore"]["players"][1]["statistics"][0]["athletes"].append(player("4","Jaylen Warren",["9","1"]))
        first=self.run_intake([self.box(d)])
        self.assertEqual([p["player"] for p in first["recorded_players"]], ["Tyler Warren"])
        bad=sample()
        bad["header"]["competitions"][0]["date"]=iso(KICK+datetime.timedelta(minutes=1))
        self.assertFalse(self.run_intake([self.box(bad,"mismatch.json")])["recorded_players"])
        bad=sample()
        bad["boxscore"]["players"][0]["team"]={"displayName":IND,"id":"23"}
        self.assertTrue(self.run_intake([self.box(bad)])["refused"])
    def test_nonfinal_summary_and_receipt_binding(self):
        self.pit_journal()
        d=sample()
        d["header"]["competitions"][0]["status"]["type"]["completed"]=False
        p=self.box(d)
        self.assertFalse(self.run_intake([p])["recorded_finals"])
        p=self.box(sample())
        receipt=dict(url=F.SUMMARY%"401872990",http_status=200,error=None,
                     retrieved_utc=iso(LATER),sha256=J.sha256_file(p))
        r=P.import_from_public(self.data,[p],LATER,receipts={p:receipt})
        self.assertTrue(r["refused"])
        self.assertFalse(self.state().finals)
    def test_final_conflict_is_order_independent_and_manual_half_cannot_settle_full(self):
        self.pit_journal()
        good=sample(); bad=copy.deepcopy(good)
        bad["header"]["competitions"][0]["competitors"][0]["score"]="35"
        paths=[self.box(good),self.box(bad,"conflict.json")]
        for ps in (paths,list(reversed(paths))):
            r=self.run_intake(ps)
            self.assertTrue(r["refused"])
            self.assertFalse(self.state().finals)
        d={"players":[dict(home_team=PIT,away_team=IND,player="Jaylen Warren",team=PIT,market="player_reception_yds_h1",value=37,source="fixture")]}
        r=self.run_intake([self.manual_final(),self.write("manual.json",d)])
        self.assertFalse(r["recorded_players"])
    def test_replay_with_conflicting_player_correction_reports_refusal(self):
        self.pit_journal()
        original=sample(); p=self.box(original)
        self.run_intake([p])
        correction=copy.deepcopy(original)
        correction["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["stats"][1]="99"
        r=self.run_intake([p,self.box(correction,"correction.json")])
        self.assertTrue(r["refused"])
        self.assertFalse(r["recorded_players"])
    def test_simultaneous_imports_append_once(self):
        self.pit_journal()
        p=self.box(sample())
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as workers:
            rs=list(workers.map(lambda unused:self.run_intake([p]),range(2)))
        self.assertEqual(sum(len(r["recorded_finals"]) for r in rs),1)
        self.assertEqual(sum(len(r["recorded_players"]) for r in rs),3)
        self.assertFalse(self.journal.verify()[1])
    def test_pending_halftime_still_triggers_capture_after_final(self):
        self.pit_journal(props=[],h1=True)
        self.run_intake([self.manual_final()])
        state=self.state()
        self.assertEqual(F.due_dates(state,LATER),["20261011"])
        comp=sample()["header"]["competitions"][0]
        for side in comp["competitors"]: side.pop("linescores")
        board={"events":[{"id":comp["id"],"date":comp["date"],"competitions":[comp]}]}
        self.assertEqual(F._summary_targets(state,board),["401872985"])
        self.run_intake([self.box(sample())])
        self.assertEqual(F.due_dates(self.state(),LATER),[])

if __name__=="__main__":
    unittest.main()
