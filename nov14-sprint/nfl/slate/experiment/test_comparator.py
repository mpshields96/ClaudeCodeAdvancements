#!/usr/bin/python3
"""Tests for comparator.py. Every store is a new temp folder; nothing real is touched.

Run:
    /usr/bin/env -i PATH=/usr/bin:/bin TMPDIR=<scratch> /usr/bin/python3 -I -B test_comparator.py
"""
import datetime
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # -I leaves the script folder off the path
import comparator as cmp  # noqa: E402

UTC = datetime.timezone.utc
KICK = "2026-11-15T18:00:00Z"
BEFORE = datetime.datetime(2026, 11, 15, 7, 30, tzinfo=UTC)
AFTER = datetime.datetime(2026, 11, 15, 22, 0, tzinfo=UTC)
FINAL = "2026-11-15T21:10:00Z"


def call(**over):
    fields = dict(
        handle="tester_one", slate="2026-11-15", event="AAA at BBB", kickoff_utc=KICK,
        market="player_pass_yds", side="Over", price="-125", book="unstated",
        posted_utc="2026-11-15T00:15:32.000Z", observed_utc="2026-11-15T07:16:49Z",
        source_ref="https://example.invalid/post/1", observed_by="test observer",
        selection_basis="every priced standalone pick, no selection by record",
        line="249.5", subject="Test Passer", event_id="evt-1")
    fields.update(over)
    return fields


class Base(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="cmp-"))
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.store = cmp.Store(self.folder)

    def add(self, now=BEFORE, **over):
        return cmp.add_call(self.store, now=now, **call(**over))

    def refused(self, text, function, *args, **kwargs):
        before = len(self.store.rows())
        with self.assertRaises(cmp.Refused) as caught:
            function(*args, **kwargs)
        self.assertIn(text, str(caught.exception))
        self.assertEqual(len(self.store.rows()), before, "a refusal must write nothing")


class AddCalls(Base):
    def test_valid_call_is_frozen_and_chained(self):
        row = self.add()
        self.assertEqual(row["kind"], "call")
        self.assertEqual(row["price"], -125)
        self.assertEqual(row["line"], 249.5)
        self.assertEqual(row["grade_as"], "over_under")
        self.assertEqual(row["posted_utc"], "2026-11-15T00:15:32Z")
        self.assertEqual(row["recorded_utc"], "2026-11-15T07:30:00Z")
        self.assertEqual(row["prev"], cmp.GENESIS)
        second = self.add(subject="Other Player", source_ref="https://example.invalid/2")
        self.assertEqual(second["prev"], row["sha"])
        self.assertEqual(self.store.problems(), [])

    def test_refusals_write_nothing(self):
        cases = [
            ("price is missing", dict(price=None)),
            ("price is missing", dict(price="  ")),
            ("American odds", dict(price="even")),
            ("American odds", dict(price="-50")),
            ("not a pregame call", dict(posted_utc=KICK)),
            ("not a pregame call", dict(posted_utc="2026-11-15T19:00:00Z")),
            ("not frozen pregame", dict(observed_utc=KICK)),
            ("before the post time", dict(observed_utc="2026-11-15T00:00:00Z")),
            ("in the future", dict(observed_utc="2026-11-15T09:00:00Z")),
            ("edited", dict(edited=True)),
            ("needs a line", dict(line=None)),
            ("UTC ending in Z", dict(posted_utc="2026-11-15 00:15")),
            ("UTC ending in Z", dict(posted_utc=None)),
            ("handle is required", dict(handle=" ")),
            ("source reference is required", dict(source_ref=None)),
            ("selection basis is required", dict(selection_basis="")),
            ("slate must be a date", dict(slate="Sunday")),
            ("line must be a number", dict(line="about 250")),
        ]
        for text, change in cases:
            with self.subTest(change=change):
                self.refused(text, self.add, **change)

    def test_cannot_freeze_after_kickoff(self):
        self.refused("kickoff has passed", self.add, now=AFTER)

    def test_duplicate_contract_refused_but_other_line_is_new(self):
        first = self.add()
        self.refused("duplicate", self.add)
        self.refused("duplicate", self.add, handle="TESTER_ONE", side="over")
        other_line = self.add(line="259.5")
        other_handle = self.add(handle="tester_two")
        self.assertEqual(len({first["call_id"], other_line["call_id"],
                              other_handle["call_id"]}), 3)

    def test_moneyline_and_spread_kinds(self):
        money = self.add(market="h2h", side="AAA", line=None, subject=None)
        spread = self.add(market="spreads", side="AAA", line="-3", subject=None)
        self.assertEqual(money["grade_as"], "moneyline")
        self.assertEqual(spread["grade_as"], "spread")
        self.assertNotEqual(money["call_id"], spread["call_id"])


class MissingAndNoPlay(Base):
    def missing(self, now=BEFORE, **over):
        fields = dict(handle="watched_handle", slate="2026-11-15",
                      checked_utc="2026-11-15T07:16:49Z", source_ref="observer ledger",
                      observed_by="test observer")
        fields.update(over)
        return cmp.record_missing(self.store, now=now, **fields)

    def no_play(self, now=BEFORE, **over):
        fields = dict(handle="watched_handle", slate="2026-11-15",
                      first_kickoff_utc="2026-11-15T14:30:00Z",
                      posted_utc="2026-11-15T03:00:00Z", observed_utc="2026-11-15T07:00:00Z",
                      source_ref="https://example.invalid/noplay", observed_by="test observer")
        fields.update(over)
        return cmp.record_no_play(self.store, now=now, **fields)

    def test_missing_is_not_a_loss_or_a_pick(self):
        self.missing()
        report = cmp.build_report(self.store.rows(), now=AFTER)
        self.assertEqual(report["slates"][0]["state"], "missing")
        self.assertEqual(report["slates"][0]["calls_frozen"], 0)
        self.assertEqual(report["records"], {})
        self.assertEqual(report["pooled"]["loss"], 0)
        self.assertEqual(report["pooled"]["graded_win_loss"], 0)
        self.assertIn("not a loss or a pass", cmp.render(report, True))

    def test_missing_rules(self):
        self.missing()
        self.refused("duplicate", self.missing)
        self.missing(checked_utc="2026-11-15T07:25:00Z")  # a later check is a new row
        self.refused("in the future", self.missing, checked_utc="2026-11-15T08:00:00Z")
        # a call found later, still before kickoff, replaces the missing state
        self.add(handle="watched_handle")
        report = cmp.build_report(self.store.rows(), now=BEFORE)
        self.assertEqual(report["slates"][0]["state"], "calls")
        self.refused("already has a frozen call", self.missing,
                     checked_utc="2026-11-15T07:29:00Z")

    def test_no_play_rules(self):
        self.refused("before the first kickoff", self.no_play,
                     posted_utc="2026-11-15T15:00:00Z", observed_utc="2026-11-15T15:10:00Z")
        self.refused("before the first kickoff", self.no_play, now=AFTER)
        self.no_play()
        self.refused("duplicate", self.no_play)
        self.refused("no_play row", self.add, handle="watched_handle")
        self.refused("no_play row", self.missing)
        report = cmp.build_report(self.store.rows(), now=AFTER)
        self.assertEqual(report["slates"][0]["state"], "no_play")
        self.assertEqual(report["pooled"]["graded_win_loss"], 0)

    def test_no_play_refused_once_calls_exist(self):
        self.add(handle="watched_handle")
        self.refused("already has a frozen call", self.no_play)


class Blinding(Base):
    def test_pick_hidden_until_kickoff(self):
        self.add()
        before = cmp.build_report(self.store.rows(), now=BEFORE)
        text = cmp.render(before, True)
        self.assertEqual(before["unblinded_calls"], [])
        self.assertEqual(before["pooled"]["blinded"], 1)
        for secret in ("Test Passer", "249.5", "Over", "-125", "player_pass_yds"):
            self.assertNotIn(secret, text)
            self.assertNotIn(secret, json.dumps(before))
        self.assertIn("1 call(s) are hidden until their kickoff", text)
        after = cmp.build_report(self.store.rows(), now=AFTER)
        shown = cmp.render(after, True)
        self.assertIn("Test Passer", shown)
        self.assertIn("249.5", shown)
        self.assertIn("unknown (no final recorded)", shown)
        self.assertNotIn("Test Passer", cmp.render(after, False))  # status never lists picks
        self.assertEqual(after["pooled"]["unknown_final"], 1)
        self.assertEqual(after["pooled"]["loss"], 0)

    def test_mixed_kickoffs(self):
        self.add()
        self.add(subject="Late Player", kickoff_utc="2026-11-16T01:20:00Z",
                 event="CCC at DDD", event_id="evt-2")
        report = cmp.build_report(self.store.rows(), now=AFTER)
        self.assertEqual(len(report["unblinded_calls"]), 1)
        self.assertEqual(report["pooled"]["blinded"], 1)
        self.assertNotIn("Late Player", cmp.render(report, True))


class Results(Base):
    def result(self, call_id, now=AFTER, **over):
        fields = dict(final_utc=FINAL, source_ref="public box score", recorded_by="tester")
        fields.update(over)
        return cmp.record_result(self.store, call_id, now=now, **fields)

    def test_grading_at_posted_line_and_price(self):
        cases = [
            (dict(), 260, "win", 0.8),
            (dict(), 249, "loss", -1.0),
            (dict(line="250"), 250, "push", 0.0),
            (dict(side="Under", price="+120"), 240, "win", 1.2),
            (dict(side="Under"), 251, "loss", -1.0),
            (dict(market="spreads", side="AAA", line="-3", subject=None), 3, "push", 0.0),
            (dict(market="spreads", side="AAA", line="-3", subject=None), 4, "win", 0.8),
            (dict(market="spreads", side="AAA", line="+3.5", subject=None), -4, "loss", -1.0),
            (dict(market="h2h", side="AAA", line=None, subject=None, price="-166"), 7,
             "win", 0.6024),
            (dict(market="h2h", side="AAA", line=None, subject=None), -1, "loss", -1.0),
        ]
        for number, (change, value, expected, units) in enumerate(cases):
            with self.subTest(change=change, value=value):
                row = self.add(handle="grader_%d" % number, **change)
                done = self.result(row["call_id"], value=value)
                self.assertEqual(done["result"], expected)
                self.assertEqual(done["flat_units_at_posted_price"], units)
                self.assertEqual(done["graded_at"]["price"], row["price"])
                self.assertEqual(done["graded_at"]["line"], row["line"])

    def test_result_rules(self):
        row = self.add()
        cid = row["call_id"]
        self.refused("before kickoff", self.result, cid, now=BEFORE, value=260,
                     final_utc="2026-11-15T07:00:00Z")
        self.refused("before kickoff", self.result, cid, value=260,
                     final_utc="2026-11-15T17:00:00Z")
        self.refused("in the future", self.result, cid, value=260,
                     final_utc="2026-11-15T23:00:00Z")
        self.refused("exactly one", self.result, cid)
        self.refused("exactly one", self.result, cid, value=260, void_reason="did not play")
        self.refused("must be a number", self.result, cid, value="lots")
        self.refused("no frozen call", self.result, "000000000000", value=260)
        self.refused("no earlier result", self.result, cid, value=260, correct=True,
                     reason="typo")
        self.result(cid, value=240)
        self.refused("already has a result", self.result, cid, value=260)
        self.refused("needs a reason", self.result, cid, value=260, correct=True)
        fixed = self.result(cid, value=260, correct=True, reason="box score corrected")
        self.assertEqual(fixed["result"], "win")
        self.assertEqual(fixed["corrects_seq"], 2)
        report = cmp.build_report(self.store.rows(), now=AFTER)
        self.assertEqual(report["pooled"]["win"], 1)  # the latest result counts once
        self.assertEqual(report["pooled"]["loss"], 0)
        self.assertEqual(len(self.store.rows()), 3)  # the first result row is kept
        self.assertEqual(self.store.problems(), [])

    def test_void_and_record_arithmetic(self):
        won = self.add(handle="h", subject="A")
        lost = self.add(handle="h", subject="B", price="+150")
        void = self.add(handle="h", subject="C")
        self.add(handle="h", subject="D")  # no final: stays unknown
        self.result(won["call_id"], value=300)
        self.result(lost["call_id"], value=100)
        self.result(void["call_id"], void_reason="player inactive")
        report = cmp.build_report(self.store.rows(), now=AFTER)
        record = report["records"]["h"]
        self.assertEqual((record["win"], record["loss"], record["void"],
                          record["unknown_final"]), (1, 1, 1, 1))
        self.assertEqual(record["graded_win_loss"], 2)
        self.assertEqual(record["win_rate"], 0.5)
        self.assertEqual(record["flat_units_at_posted_prices"], -0.2)
        self.assertAlmostEqual(record["mean_breakeven_at_posted_prices"],
                               round((125 / 225.0 + 100 / 250.0) / 2, 4))
        low, high = record["wilson95"]
        self.assertTrue(0.09 < low < 0.10 and 0.90 < high < 0.91)
        text = cmp.render(report, True)
        self.assertIn("No profit claim", text)
        self.assertIn("1 unknown final", text)


class Arithmetic(unittest.TestCase):
    def test_wilson(self):
        self.assertIsNone(cmp.wilson(0, 0))
        low, high = cmp.wilson(5, 10)
        self.assertAlmostEqual(low, 0.2366, places=4)
        self.assertAlmostEqual(high, 0.7634, places=4)
        low, high = cmp.wilson(0, 3)
        self.assertEqual(low, 0.0)
        self.assertTrue(0.5 < high < 0.6)

    def test_units_and_breakeven(self):
        self.assertEqual(cmp.flat_units("win", -113), 0.885)
        self.assertEqual(cmp.flat_units("win", 120), 1.2)
        self.assertEqual(cmp.flat_units("loss", -113), -1.0)
        self.assertEqual(cmp.flat_units("push", -113), 0.0)
        self.assertEqual(cmp.flat_units("void", -113), 0.0)
        self.assertAlmostEqual(cmp.breakeven(-130), 130 / 230.0)
        self.assertAlmostEqual(cmp.breakeven(120), 100 / 220.0)

    def test_price_and_time_parsing(self):
        self.assertEqual(cmp.parse_price("+120"), 120)
        self.assertEqual(cmp.parse_price(-113), -113)
        self.assertEqual(cmp.parse_price("−125"), -125)
        self.assertEqual(cmp.iso(cmp.parse_utc("2026-11-15T04:11:33.000Z")),
                         "2026-11-15T04:11:33Z")
        self.assertEqual(cmp.iso(cmp.parse_utc("2026-11-15T18:00Z")), "2026-11-15T18:00:00Z")


class Tamper(Base):
    def test_changed_row_is_detected_and_blocks_writes(self):
        self.add()
        self.add(subject="Other Player")
        lines = self.store.path.read_text(encoding="utf-8").splitlines()
        first = json.loads(lines[0])
        first["price"] = 150
        lines[0] = json.dumps(first, sort_keys=True)
        self.store.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        problems = self.store.problems()
        self.assertTrue(any("changed after it was written" in item for item in problems))
        self.refused("failed verification", self.add, subject="Third Player")

    def test_deleted_row_is_detected(self):
        self.add()
        self.add(subject="Other Player")
        lines = self.store.path.read_text(encoding="utf-8").splitlines()
        self.store.path.write_text(lines[1] + "\n", encoding="utf-8")
        self.assertTrue(self.store.problems())


class ImportLedger(Base):
    def write_pair(self, edited=False, definition_price=-113, slate="2026-11-15"):
        posts = {
            "observed_utc": "2026-11-15T07:16:49Z", "slate": slate,
            "sample_rule": "every unedited priced standalone pick",
            "posts": [
                {"author": "poster_a", "original_post": "https://example.invalid/a",
                 "published_utc": "2026-11-15T04:11:33.000Z", "edited": edited,
                 "posted_price": "-113", "matchup": "EEE at FFF"},
                {"author": "poster_b", "original_post": "https://example.invalid/b",
                 "published_utc": "2026-11-15T03:21:42.000Z", "edited": False,
                 "posted_price": "-130", "matchup": "GGG at HHH"},
            ]}
        prices = {"definitions": [
            {"label": "x", "event_id": "evt-a", "kickoff": "2026-11-15T21:05:00Z",
             "market": "player_rush_yds", "subject": "Test Runner", "side": "Over",
             "point": 57.5, "minimum_price": definition_price, "author": "poster_a",
             "post": "https://example.invalid/a"},
            {"label": "y", "event_id": "evt-b", "kickoff": "2026-11-16T01:20:00Z",
             "market": "spreads", "subject": "", "side": "HHH", "point": -3,
             "minimum_price": -130, "author": "poster_b",
             "post": "https://example.invalid/b"},
        ]}
        source = Path(tempfile.mkdtemp(prefix="cmp-src-"))
        self.addCleanup(shutil.rmtree, str(source), True)
        (source / "posts.json").write_text(json.dumps(posts), encoding="utf-8")
        (source / "prices.json").write_text(json.dumps(prices), encoding="utf-8")
        return str(source / "posts.json"), str(source / "prices.json")

    def run_import(self, pair, slate="2026-11-15", basis=None, now=BEFORE):
        return cmp.import_ledger(self.store, pair[0], pair[1], slate, "test observer",
                                 basis, now=now)

    def test_import_freezes_every_row(self):
        pair = self.write_pair()
        rows = self.run_import(pair)
        self.assertEqual([row["handle"] for row in rows], ["poster_a", "poster_b"])
        self.assertEqual(rows[0]["grade_as"], "over_under")
        self.assertEqual(rows[1]["grade_as"], "spread")
        self.assertEqual(rows[1]["line"], -3.0)
        self.assertEqual(rows[0]["event"], "EEE at FFF")
        self.assertEqual(rows[0]["selection_basis"], "every unedited priced standalone pick")
        self.assertEqual(rows[0]["observed_utc"], "2026-11-15T07:16:49Z")
        self.assertEqual(rows[0]["source_files"]["posts_sha256"], cmp.sha256_file(pair[0]))
        self.assertEqual(self.store.problems(), [])
        self.assertFalse((self.folder / ".import-check.jsonl").exists())
        self.refused("duplicate", self.run_import, pair)

    def test_import_is_all_or_nothing(self):
        self.refused("differ", self.run_import, self.write_pair(definition_price=-115))
        self.refused("edited", self.run_import, self.write_pair(edited=True))
        self.refused("is for slate", self.run_import, self.write_pair(), slate="2026-11-22")
        self.refused("kickoff has passed", self.run_import, self.write_pair(), now=AFTER)
        self.assertEqual(self.store.rows(), [])
        self.assertFalse((self.folder / ".import-check.jsonl").exists())

    def test_import_refused_when_second_row_already_frozen(self):
        cmp.add_call(self.store, now=BEFORE, **call(
            handle="poster_b", event="GGG at HHH", event_id="evt-b", market="spreads",
            side="HHH", line="-3", subject=None, price="-130",
            kickoff_utc="2026-11-16T01:20:00Z"))
        self.refused("duplicate", self.run_import, self.write_pair())
        self.assertEqual(len(self.store.rows()), 1)


class CommandLine(Base):
    FAR = ["--slate", "2099-01-04", "--event", "AAA at BBB", "--kickoff-utc",
           "2099-01-04T18:00:00Z", "--market", "player_pass_yds", "--side", "Over",
           "--line", "249.5", "--subject", "Test Passer", "--book", "unstated",
           "--posted-utc", "2026-11-01T00:00:00Z", "--observed-utc", "2026-11-01T01:00:00Z",
           "--source-ref", "https://example.invalid/post/1", "--observed-by", "tester",
           "--selection-basis", "test rule"]

    def command(self, *args):
        return [sys.executable, "-I", "-B", str(HERE / "comparator.py"),
                "--data", str(self.folder)] + list(args)

    def run_cli(self, *args):
        done = subprocess.run(self.command(*args), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        return done.returncode, done.stdout, done.stderr

    def test_add_status_grade_verify(self):
        code, out, err = self.run_cli("add", "--handle", "cli_one", "--price", "-125",
                                      *self.FAR)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("stays hidden until kickoff", out)
        code, out, err = self.run_cli("grade")
        self.assertEqual(code, 0)
        self.assertNotIn("Test Passer", out)
        self.assertIn("No profit claim", out)
        self.assertIn("1 call(s) are hidden until their kickoff", out)
        code, out, err = self.run_cli("status", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["pooled"]["blinded"], 1)
        code, out, err = self.run_cli("verify")
        self.assertEqual((code, out.strip()), (0, "Chain intact: 1 row(s)."))

    def test_missing_price_is_refused_with_exit_1(self):
        code, out, err = self.run_cli("add", "--handle", "cli_one", *self.FAR)
        self.assertEqual(code, 1)
        self.assertIn("REFUSED: price is missing", err)
        self.assertEqual(self.store.rows(), [])

    def test_result_before_kickoff_and_bad_command(self):
        self.run_cli("add", "--handle", "cli_one", "--price", "-125", *self.FAR)
        cid = self.store.rows()[0]["call_id"]
        code, out, err = self.run_cli("result", "--call-id", cid, "--value", "300",
                                      "--final-utc", "2026-11-01T02:00:00Z",
                                      "--source-ref", "x", "--recorded-by", "tester")
        self.assertEqual(code, 1)
        self.assertIn("no result before kickoff", err)
        code, out, err = self.run_cli("nonsense")
        self.assertEqual(code, 2)

    def test_missing_command_and_tamper_exit_code(self):
        code, out, err = self.run_cli("missing", "--handle", "watched", "--slate",
                                      "2026-11-15", "--checked-utc", "2026-11-15T07:16:49Z",
                                      "--source-ref", "observer ledger", "--observed-by",
                                      "tester")
        self.assertEqual(code, 0)
        self.assertIn("not a loss or a pass", out)
        row = json.loads(self.store.path.read_text(encoding="utf-8"))
        row["handle"] = "someone_else"
        self.store.path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        self.assertEqual(self.run_cli("verify")[0], 1)
        self.assertEqual(self.run_cli("status")[0], 1)

    def test_two_writers_same_call_leave_one_row(self):
        args = self.command("add", "--handle", "cli_race", "--price", "-125", *self.FAR)
        procs = [subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True) for _ in range(6)]
        codes = []
        for proc in procs:
            proc.communicate()
            codes.append(proc.returncode)
        self.assertEqual(sorted(codes), [0, 1, 1, 1, 1, 1])
        self.assertEqual(len(self.store.rows()), 1)
        self.assertEqual(self.store.problems(), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
