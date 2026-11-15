#!/usr/bin/python3
"""Tests for role_check.py. Stores are new temp folders; the journal is only read.

Run:
    /usr/bin/env -i PATH=/usr/bin:/bin TMPDIR=<scratch> /usr/bin/python3 -I -B test_role_check.py
"""
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # -I leaves the script folder off the path
import role_check as rc  # noqa: E402

UTC = datetime.timezone.utc
SPEC = rc.SPECS["H3fb769df"]
BEFORE = datetime.datetime(2026, 11, 15, 10, 0, tzinfo=UTC)
AFTER = datetime.datetime(2026, 11, 16, 6, 0, tzinfo=UTC)
FINAL = "2026-11-16T04:30:00Z"


def seen(**values):
    base = {"rodgers_started": True, "warren_offensive_snaps": 40, "warren_targets": 5,
            "warren_receiving_yards": 31}
    base.update(values)
    return base


class Evaluate(unittest.TestCase):
    def verdict(self, **values):
        return rc.evaluate(SPEC, seen(**values))["verdict"]

    def test_supported_and_contradicted_turn_on_targets_only(self):
        self.assertEqual(self.verdict(warren_targets=4), "supported")
        self.assertEqual(self.verdict(warren_targets=9), "supported")
        self.assertEqual(self.verdict(warren_targets=3), "contradicted")
        self.assertEqual(self.verdict(warren_targets=0), "contradicted")

    def test_long_catch_that_wins_the_over_still_contradicts(self):
        result = rc.evaluate(SPEC, seen(warren_targets=1, warren_receiving_yards=45))
        self.assertEqual(result["verdict"], "contradicted")
        self.assertEqual(result["linked_prop"]["arithmetic"], "win")
        self.assertFalse(result["linked_prop"]["changes_the_verdict"])

    def test_volume_met_but_over_lost_is_still_supported(self):
        result = rc.evaluate(SPEC, seen(warren_targets=6, warren_receiving_yards=12))
        self.assertEqual(result["verdict"], "supported")
        self.assertEqual(result["linked_prop"]["arithmetic"], "loss")

    def test_condition_unmet(self):
        self.assertEqual(self.verdict(rodgers_started=False), "condition_unmet")
        self.assertEqual(self.verdict(warren_offensive_snaps=0), "condition_unmet")
        # a false condition wins over an unknown one and over an unknown outcome
        self.assertEqual(self.verdict(rodgers_started=False, warren_offensive_snaps=None,
                                      warren_targets=None), "condition_unmet")
        result = rc.evaluate(SPEC, seen(warren_offensive_snaps=0, warren_targets=0,
                                        warren_receiving_yards=0))
        self.assertIn("did not play", result["linked_prop"]["arithmetic"])

    def test_unknown_is_never_a_verdict_for_or_against(self):
        self.assertEqual(self.verdict(rodgers_started=None), "unknown")
        self.assertEqual(self.verdict(warren_offensive_snaps=None), "unknown")
        self.assertEqual(self.verdict(warren_targets=None), "unknown")
        self.assertEqual(rc.evaluate(SPEC, {})["verdict"], "unknown")
        self.assertEqual(rc.evaluate(SPEC, {})["linked_prop"]["arithmetic"], "unknown")

    def test_early_exit_is_recorded_not_excused(self):
        result = rc.evaluate(SPEC, seen(warren_targets=2, early_exit=True))
        self.assertEqual(result["verdict"], "contradicted")
        self.assertIs(result["early_exit"], True)

    def test_prop_push_and_half_point(self):
        spec = json.loads(json.dumps(SPEC))
        spec["linked_prop"]["line"] = 22
        self.assertEqual(rc.evaluate(spec, seen(warren_receiving_yards=22))
                         ["linked_prop"]["arithmetic"], "push")
        self.assertEqual(rc.evaluate(SPEC, seen(warren_receiving_yards=23))
                         ["linked_prop"]["arithmetic"], "win")
        self.assertEqual(rc.evaluate(SPEC, seen(warren_receiving_yards=22))
                         ["linked_prop"]["arithmetic"], "loss")


class Parsing(unittest.TestCase):
    def test_values(self):
        got = rc.parse_sets(SPEC, ["rodgers_started=yes", "warren_offensive_snaps=41",
                                   "warren_targets=unknown", "warren_receiving_yards=-3",
                                   "early_exit=no", "early_exit_note= left in the  third "])
        self.assertEqual(got, {"rodgers_started": True, "warren_offensive_snaps": 41,
                               "warren_targets": None, "warren_receiving_yards": -3,
                               "early_exit": False, "early_exit_note": "left in the third"})

    def test_refusals(self):
        cases = [("not a field", ["warren_rushing_yards=50"]),
                 ("key=value", ["warren_targets"]),
                 ("must be yes, no or unknown", ["rodgers_started=maybe"]),
                 ("must be a number", ["warren_targets=several"]),
                 ("must be a number", ["warren_targets=nan"]),
                 ("cannot be negative", ["warren_targets=-1"]),
                 ("given twice", ["warren_targets=4", "warren_targets=5"])]
        for text, pairs in cases:
            with self.subTest(pairs=pairs):
                with self.assertRaises(rc.Refused) as caught:
                    rc.parse_sets(SPEC, pairs)
                self.assertIn(text, str(caught.exception))


class JournalMatch(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="role-j-"))
        self.addCleanup(shutil.rmtree, str(self.folder), True)

    def journal(self, text="forecast text", **change):
        row = {"hypothesis_id": "Htest", "text": text,
               "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
               "cids": ["c1"], "first_kickoff_utc": "2026-11-16T01:20:00Z",
               "recorded_utc": "2026-11-15T08:00:00Z"}
        row.update(change)
        path = self.folder / "hypotheses.jsonl"
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        return path

    def spec(self, text="forecast text"):
        spec = json.loads(json.dumps(SPEC))
        spec.update(hypothesis_id="Htest", cids=["c1"],
                    journal_text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
        return {"Htest": spec}

    def test_real_journal_still_holds_the_carried_text(self):
        self.assertEqual(rc.verify_against_journal(rc.SPECS), [])

    def test_match_and_each_mismatch(self):
        self.assertEqual(rc.verify_against_journal(self.spec(), self.journal()), [])
        # each case rewrites the one journal file, so write it inside the loop
        cases = [("no longer matches", dict(text="reworded after the fact",
                                            text_sha256=None)),
                 ("own text hash", dict(text_sha256="0" * 64)),
                 ("candidate ids differ", dict(cids=["c2"])),
                 ("kickoff differs", dict(first_kickoff_utc="2026-11-15T18:00:00Z")),
                 ("not recorded before kickoff", dict(recorded_utc="2026-11-16T02:00:00Z")),
                 ("not registered", dict(hypothesis_id="Hother"))]
        for text, change in cases:
            with self.subTest(text=text):
                found = rc.verify_against_journal(self.spec(), self.journal(**change))
                self.assertTrue(any(text in item for item in found), found)
        missing = rc.verify_against_journal(self.spec(), self.folder / "absent.jsonl")
        self.assertIn("not found", missing[0])


class Recording(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="role-"))
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.store = rc.Store(self.folder, rc.LEDGER)

    def record(self, observed=None, now=AFTER, **over):
        fields = dict(final_utc=FINAL, source_ref="public box score", recorded_by="tester")
        fields.update(over)
        return rc.record(self.store, SPEC, seen() if observed is None else observed,
                         now=now, **fields)

    def refused(self, text, **kwargs):
        before = len(self.store.rows())
        with self.assertRaises(rc.Refused) as caught:
            self.record(**kwargs)
        self.assertIn(text, str(caught.exception))
        self.assertEqual(len(self.store.rows()), before)

    def test_record_rules_and_status(self):
        pending = rc.build_status(rc.SPECS, [], now=BEFORE)["hypotheses"][0]
        self.assertEqual(pending["state"], "pending (before kickoff)")
        unknown = rc.build_status(rc.SPECS, [], now=AFTER)["hypotheses"][0]
        self.assertEqual(unknown["state"], "unknown (no observation recorded)")
        self.refused("before kickoff", now=BEFORE, final_utc="2026-11-15T09:00:00Z")
        self.refused("before kickoff", final_utc="2026-11-16T01:00:00Z")
        self.refused("in the future", final_utc="2026-11-16T07:00:00Z")
        self.refused("at least one", observed={"warren_targets": None})
        self.refused("source reference is required", source_ref=" ")
        self.refused("no earlier observation", correct=True, reason="typo")
        row = self.record(seen(warren_targets=3, early_exit=True,
                               early_exit_note="ankle, third quarter"))
        self.assertEqual(row["verdict"], "contradicted")
        self.assertEqual(row["journal_text_sha256"], SPEC["journal_text_sha256"])
        self.refused("already has an observation")
        self.refused("needs a reason", correct=True)
        fixed = self.record(seen(warren_targets=4), correct=True,
                            reason="official scoring change")
        self.assertEqual((fixed["verdict"], fixed["corrects_seq"]), ("supported", 1))
        self.assertEqual(len(self.store.rows()), 2)  # the first row is kept
        self.assertEqual(self.store.problems(), [])
        status = rc.build_status(rc.SPECS, self.store.rows(), now=AFTER)
        item = status["hypotheses"][0]
        self.assertEqual((item["state"], item["corrected"]), ("supported", True))
        text = rc.render_status(status)
        self.assertIn("separate from the verdict", text)
        self.assertIn("no profit claim", text)

    def test_tamper_blocks_writes(self):
        self.record()
        row = json.loads(self.store.path.read_text(encoding="utf-8"))
        row["verdict"] = "contradicted"
        self.store.path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        self.assertTrue(self.store.problems())
        self.refused("failed verification", correct=True, reason="x")


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="role-cli-"))
        self.addCleanup(shutil.rmtree, str(self.folder), True)

    def run_cli(self, *args):
        done = subprocess.run([sys.executable, "-I", "-B", str(HERE / "role_check.py"),
                               "--data", str(self.folder)] + list(args),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)
        return done.returncode, done.stdout, done.stderr

    def test_list_verify_evaluate_status_write_nothing(self):
        code, out, err = self.run_cli("list")
        self.assertEqual(code, 0)
        self.assertIn("H3fb769df", out)
        self.assertIn("supported at 4 or more", out)
        code, out, err = self.run_cli("verify")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("match the journal text", out)
        code, out, err = self.run_cli("evaluate", "--id", "H3fb769df", "--set",
                                      "rodgers_started=yes", "--set",
                                      "warren_offensive_snaps=38", "--set",
                                      "warren_targets=2", "--set",
                                      "warren_receiving_yards=30")
        self.assertEqual(code, 0)
        self.assertIn("verdict: contradicted", out)
        self.assertIn("separate from the verdict: win", out)
        code, out, err = self.run_cli("status", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)["hypotheses"]), 1)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_refusals_and_bad_command(self):
        code, out, err = self.run_cli("evaluate", "--id", "Hnope")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED: no carried hypothesis", err)
        code, out, err = self.run_cli("record", "--id", "H3fb769df", "--set",
                                      "warren_targets=5", "--final-utc",
                                      "2026-11-15T09:00:00Z", "--source-ref", "x",
                                      "--recorded-by", "tester")
        self.assertEqual(code, 1)
        self.assertIn("no observation before kickoff", err)
        self.assertEqual(self.run_cli("nonsense")[0], 2)
        self.assertEqual(self.run_cli()[0], 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
