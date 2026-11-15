"""Checks for the real-data door (bot/real_feed.py) and the paper gate.

What is tested: with no source set up nothing is read and no signal is made;
a TradingView-shaped file or marker is refused; a bad CSV is refused whole; a
good CSV converts and the engine reads it only with the source's permission
file; the paper command refuses without Matthew's gate approval; the gate
refuses an answer that was not typed in a terminal.

TEST ONLY: the CSV rows here are made up by this test. They are not market
data. The gate files written here are test fixtures in a temp folder; the real
gate file (gate/paper_gate.json) is never read or written by these tests.

Standard library unittest, Python 3.9. Temp folders sit under <tvbot>/out and
are removed in tearDown.

Run:
    /usr/bin/python3 -I -m unittest discover -s nov14-sprint/tvbot/tests -p "test_real_feed.py" -v
"""
import contextlib
import io
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
TVBOT = os.path.normpath(os.path.join(HERE, ".."))
BOT = os.path.join(TVBOT, "bot")
OUT = os.path.join(TVBOT, "out")
if BOT not in sys.path:
    sys.path.insert(0, BOT)

import engine  # noqa: E402
import provenance  # noqa: E402
import real_feed  # noqa: E402
import riskinfo  # noqa: E402
import run  # noqa: E402

FMT = "%Y-%m-%dT%H:%M:%SZ"
CLOCK = "2026-11-14T00:00:00Z"
HEADER = "ts,open,high,low,close,volume"
N_ROWS = 100


def good_rows(n=N_ROWS, start="2026-11-02T00:00:00Z"):
    t0 = datetime.strptime(start, FMT)
    out = []
    prev = 100.0
    for i in range(n):
        close = round(100.0 + 3.0 * math.sin(i / 9.0) + 0.02 * i, 2)
        o = prev
        hi, lo = round(max(o, close) + 0.1, 2), round(min(o, close) - 0.1, 2)
        out.append("%s,%.2f,%.2f,%.2f,%.2f,%d" % ((t0 + timedelta(hours=i)).strftime(FMT),
                                                 o, hi, lo, close, 1000 + i))
        prev = close
    return out


class Case(unittest.TestCase):

    def setUp(self):
        os.makedirs(OUT, exist_ok=True)
        self.tmp = tempfile.mkdtemp(dir=OUT)
        self.real = os.path.join(self.tmp, "real")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def csv(self, rows=None, header=HEADER, name="bars.csv"):
        return self.write(name, "\n".join([header] + (good_rows() if rows is None else rows)) + "\n")

    def source(self, name="source.json", **over):
        cfg = {"schema": "tvbot-real-source-1", "source_name": "unit-test-csv",
               "terms_url": "https://example.com/terms",
               "terms_quote": "Made-up terms text for a unit test; not a real licence.",
               "approved_by": "Unit Test Person", "approved_utc": "2026-11-13T00:00:00Z",
               "csv_path": "bars.csv", "symbol": "TESTCO", "timeframe_minutes": 60}
        cfg.update(over)
        for k in [k for k, v in cfg.items() if v is None]:
            del cfg[k]
        return self.write(name, json.dumps(cfg))

    def refused(self, src, code):
        with self.assertRaises(real_feed.SourceRefused) as cm:
            real_feed.convert(src, self.real, CLOCK)
        self.assertEqual(cm.exception.code, code, str(cm.exception))
        wrote = os.listdir(self.real) if os.path.isdir(self.real) else []
        self.assertEqual(wrote, [], "a refused source must leave nothing behind")
        return str(cm.exception)


class FailClosed(Case):

    def test_no_source_file_reads_nothing_and_says_so_once(self):
        msg = self.refused(os.path.join(self.tmp, "missing.json"), "no_source")
        self.assertEqual(msg, real_feed.NO_SOURCE_MESSAGE)
        self.assertIn("No bars were read and no signal was made", msg)

    def test_source_file_naming_a_missing_csv_is_refused(self):
        self.refused(self.source(), "no_source")

    def test_chart_export_header_is_refused_as_tradingview(self):
        self.csv(header="time,open,high,low,close,Volume")
        self.refused(self.source(), "tradingview_origin")

    def test_marker_words_in_the_source_file_are_refused(self):
        self.csv()
        self.refused(self.source(note="exported from TradingView"), "tradingview_origin")

    def test_marker_in_the_csv_file_name_is_refused(self):
        self.csv(name="tradingview_export.csv")
        self.refused(self.source(csv_path="tradingview_export.csv"), "tradingview_origin")

    def test_exchange_prefixed_symbol_text_in_the_csv_is_refused(self):
        rows = good_rows()
        rows[3] = rows[3] + ",NASDAQ:AAPL"
        self.csv(rows=rows)
        with self.assertRaises(real_feed.SourceRefused):
            real_feed.convert(self.source(), self.real, CLOCK)

    def test_wrong_header_is_refused(self):
        self.csv(header="date,open,high,low,close,volume")
        self.refused(self.source(), "schema_rejected")

    def test_one_bad_row_refuses_the_whole_file(self):
        rows = good_rows()
        rows[40] = "2026-11-03T16:00:00Z,100.00,99.00,98.00,100.50,10"   # high below the close
        self.csv(rows=rows)
        self.refused(self.source(), "schema_rejected")

    def test_rows_out_of_time_order_are_refused(self):
        rows = good_rows()
        rows[10], rows[11] = rows[11], rows[10]
        self.csv(rows=rows)
        self.refused(self.source(), "schema_rejected")

    def test_a_bar_that_has_not_closed_is_refused(self):
        self.csv(rows=good_rows(start="2026-11-12T00:00:00Z"))   # runs past the clock
        self.assertIn("has not closed yet", self.refused(self.source(), "schema_rejected"))

    def test_plain_dates_need_a_stated_open_time(self):
        self.csv(rows=["2026-11-02,100,101,99,100.5,10", "2026-11-03,100.5,102,100,101,10"])
        self.refused(self.source(timeframe_minutes=390), "schema_rejected")

    def test_an_assistant_cannot_be_the_approver(self):
        self.csv()
        for who in ("Claude", "codex", "an AI assistant"):
            self.refused(self.source(approved_by=who), "schema_rejected")

    def test_synthetic_cannot_be_passed_off_as_real(self):
        self.csv()
        self.refused(self.source(source_name="synthetic"), "schema_rejected")
        self.refused(self.source(symbol="SYNTH-FUND-60M"), "schema_rejected")

    def test_missing_or_extra_fields_are_refused(self):
        self.csv()
        self.refused(self.source(terms_quote=None), "schema_rejected")
        self.refused(self.source(api_key="not allowed here"), "schema_rejected")
        self.refused(self.source(terms_url="http://example.com/terms"), "schema_rejected")


class GoodFile(Case):

    def test_good_csv_converts_and_the_engine_reads_it_only_with_permission(self):
        self.csv()
        conv = real_feed.convert(self.source(), self.real, CLOCK)
        rep = conv["report"]
        self.assertEqual(rep["rows"], N_ROWS)
        self.assertEqual(rep["source_name"], "unit-test-csv")
        self.assertEqual(rep["first_ts_open"], "2026-11-02T00:00:00Z")
        self.assertEqual(rep["last_ts_close"], "2026-11-06T04:00:00Z")
        self.assertEqual(sorted(os.listdir(self.real)),
                         ["last_source.json", "permitted_sources.json", "real_bars.jsonl"])
        self.assertTrue(provenance.check_feed(conv["feed"], conv["permitted"]).ok)

        # Without the permission file the same bars are refused: zero bars read, no decision.
        bare = engine.Engine(as_of=CLOCK)
        res = bare.process_feed(conv["feed"])
        self.assertFalse(res["accepted"])
        self.assertEqual(res["code"], "source_not_permitted")
        self.assertEqual((res["bars_accepted"], bare.decisions, bare.ledger), (0, [], []))

        e = engine.Engine(as_of=CLOCK, permitted_sources=conv["permitted"])
        res = e.process_feed(conv["feed"])
        self.assertTrue(res["accepted"], res["reasons"])
        self.assertEqual(res["bars_accepted"], N_ROWS)
        self.assertEqual(len(e.decisions), N_ROWS)
        self.assertTrue(run.timing_ok(e.fills()))
        self.assertEqual(run.plan_check(e.ledger)[0], [])
        note = e.summary()["data_note"]
        self.assertTrue(note.startswith("REAL BARS, PAPER ONLY"), note)
        self.assertIn("not evidence of an edge", note)

    def test_synthetic_runs_are_labelled_test_only(self):
        e = engine.Engine(as_of=CLOCK)
        e.process_feed(os.path.join(TVBOT, "fixtures", "normal_bars.jsonl"))
        self.assertTrue(e.summary()["data_note"].startswith("TEST ONLY: synthetic"))

    def test_daily_rows_with_a_stated_open_time_convert(self):
        self.csv(rows=["2026-11-02,100,101,99,100.5,10", "2026-11-03,100.5,102,100,101,10"])
        conv = real_feed.convert(self.source(timeframe_minutes=390, daily_open_utc="14:30:00"),
                                 self.real, CLOCK)
        self.assertEqual(conv["report"]["first_ts_open"], "2026-11-02T14:30:00Z")
        self.assertEqual(conv["report"]["last_ts_close"], "2026-11-03T21:00:00Z")

    # A vendor file shaped `datetime,open,high,low,close,volume` with zone-less stamps.
    VENDOR_ROWS = ["2026-11-02 14:30:00,100,101,99,100.5,10",
                   "2026-11-02 15:30:00,100.5,102,100,101,10"]
    VENDOR_HEADER = "datetime,open,high,low,close,volume"

    def test_vendor_datetime_column_converts_when_the_source_file_says_utc(self):
        self.csv(rows=self.VENDOR_ROWS, header=self.VENDOR_HEADER)
        conv = real_feed.convert(self.source(naive_ts_is_utc=True), self.real, CLOCK)
        self.assertEqual(conv["report"]["rows"], 2)
        self.assertEqual(conv["report"]["first_ts_open"], "2026-11-02T14:30:00Z")
        self.assertEqual(conv["report"]["last_ts_close"], "2026-11-02T16:30:00Z")

    def test_zone_less_times_are_refused_without_that_statement(self):
        self.csv(rows=self.VENDOR_ROWS, header=self.VENDOR_HEADER)
        msg = self.refused(self.source(), "schema_rejected")
        self.assertIn("naive_ts_is_utc", msg)

    def test_the_utc_statement_must_be_exactly_true(self):
        self.csv(rows=self.VENDOR_ROWS, header=self.VENDOR_HEADER)
        for bad in (False, "true", 1, "yes"):
            self.refused(self.source(naive_ts_is_utc=bad), "schema_rejected")

    def test_a_chart_export_header_is_still_refused_with_the_utc_statement(self):
        self.csv(rows=["2026-11-02 14:30:00,100,101,99,100.5,10"],
                 header="time,open,high,low,close,Volume")
        self.refused(self.source(naive_ts_is_utc=True), "tradingview_origin")

    def test_a_semicolon_vendor_file_is_refused(self):
        self.csv(rows=["2026-11-02 14:30:00;100;101;99;100.5;10"],
                 header="datetime;open;high;low;close;volume")
        self.refused(self.source(naive_ts_is_utc=True), "schema_rejected")

    def test_market_shaped_vendor_file_runs_through_the_template_and_the_engine(self):
        """Seven hourly bars a weekday, nights and weekends missing, and the US clock change
        on 2026-11-01 moving the open from 13:30Z to 14:30Z. Made-up prices."""
        rows, prev, i = [], 100.0, 0
        day = datetime(2026, 10, 12)
        while day <= datetime(2026, 11, 13):
            if day.weekday() < 5:
                first = day.replace(hour=13 if day < datetime(2026, 11, 1) else 14, minute=30)
                for k in range(7):
                    close = round(100.0 + 3.0 * math.sin(i / 9.0) + 0.02 * i, 2)
                    hi, lo = round(max(prev, close) + 0.1, 2), round(min(prev, close) - 0.1, 2)
                    rows.append("%s,%.2f,%.2f,%.2f,%.2f,%d" % (
                        (first + timedelta(hours=k)).strftime("%Y-%m-%d %H:%M:%S"),
                        prev, hi, lo, close, 1000 + i))
                    prev, i = close, i + 1
            day += timedelta(days=1)
        with open(os.path.join(TVBOT, "config", "source_template_twelvedata.json"),
                  encoding="utf-8") as fh:
            tpl = json.load(fh)
        self.csv(rows=rows, header=self.VENDOR_HEADER, name=tpl["csv_path"])
        # The template as shipped has three blanks, so it is refused.
        msg = self.refused(self.write("source.json", json.dumps(tpl)), "schema_rejected")
        for field in ("terms_quote", "approved_by", "approved_utc"):
            self.assertIn(field, msg)
        tpl.update(terms_quote="Made-up quote for a unit test.", approved_by="Unit Test Person",
                   approved_utc="2026-11-13T00:00:00Z")
        conv = real_feed.convert(self.write("source.json", json.dumps(tpl)), self.real, CLOCK)
        self.assertEqual(conv["report"]["rows"], 175)
        self.assertEqual(conv["report"]["first_ts_open"], "2026-10-12T13:30:00Z")
        e = engine.Engine(as_of=CLOCK, permitted_sources=conv["permitted"])
        res = e.process_feed(conv["feed"])
        self.assertTrue(res["accepted"], res["reasons"])
        self.assertEqual((res["bars_accepted"], len(e.decisions)), (175, 175))
        self.assertTrue(any(d["action"] == "ENTER_LONG" for d in e.decisions))
        self.assertTrue(run.timing_ok(e.fills()))
        self.assertEqual(run.plan_check(e.ledger)[0], [])


class FakeTerminal(io.StringIO):
    def isatty(self):
        return True


class PaperCommandAndGate(Case):
    """The CLI, with every path it writes pointed at the temp folder."""

    def setUp(self):
        super().setUp()
        self.gate = os.path.join(self.tmp, "gate", "paper_gate.json")
        self.state = os.path.join(self.tmp, "paper")
        self.registry = os.path.join(self.tmp, "rule_registry.json")
        shutil.copyfile(run.REGISTRY, self.registry)
        patches = [mock.patch.object(run, "GATE_PATH", self.gate),
                   mock.patch.object(run, "REAL_DIR", self.real),
                   mock.patch.object(run, "PAPER_STATE", self.state),
                   mock.patch.object(run, "LOCK_DIR", os.path.join(self.tmp, "locks")),
                   mock.patch.object(run, "rebuild_page", lambda: None)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        probe = engine.Engine(as_of=CLOCK)
        self.rule_id, self.cfg_hash = probe.rule_id, probe.cfg_hash

    def cli(self, *argv, stdin=None, stdout=None):
        buf = stdout or io.StringIO()
        with contextlib.redirect_stdout(buf), mock.patch.object(sys, "stdin", stdin or io.StringIO("")):
            code = run.main(list(argv) + ["--as-of", CLOCK, "--registry", self.registry])
        return code, buf.getvalue()

    def fixture_gate(self, decision="approve_paper_only", cfg_hash=None):
        os.makedirs(os.path.dirname(self.gate), exist_ok=True)
        with open(self.gate, "w", encoding="utf-8") as fh:
            json.dump({"schema": riskinfo.GATE_SCHEMA, "decision": decision,
                       "decided_utc": CLOCK, "typed": "TEST FIXTURE, not a real decision",
                       "rule_id": self.rule_id, "config_hash": cfg_hash or self.cfg_hash}, fh)

    def nothing_was_read(self):
        self.assertFalse(os.path.isdir(self.real))
        self.assertFalse(os.path.isdir(self.state))

    def test_paper_with_no_source_prints_the_one_message(self):
        code, out = self.cli("paper", "--source", os.path.join(self.tmp, "missing.json"))
        self.assertEqual(code, 2)
        self.assertEqual(out.strip(), real_feed.NO_SOURCE_MESSAGE)
        self.nothing_was_read()

    def test_paper_without_a_gate_decision_reads_nothing(self):
        self.csv()
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 2)
        self.assertIn("PAPER GATE NOT APPROVED", out)
        self.nothing_was_read()

    def test_paper_after_a_pass_decision_reads_nothing(self):
        self.csv()
        self.fixture_gate(decision="pass")
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 2)
        self.assertIn("PAPER GATE NOT APPROVED", out)
        self.nothing_was_read()

    def test_an_approval_for_other_settings_does_not_carry_over(self):
        self.csv()
        self.fixture_gate(cfg_hash="000000000000")
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 2)
        self.nothing_was_read()

    def test_paper_with_approval_and_a_bad_file_makes_no_signal(self):
        self.csv(header="time,open,high,low,close,Volume")
        self.fixture_gate()
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 2)
        self.assertIn("REAL SOURCE REFUSED (tradingview_origin)", out)
        self.assertFalse(os.path.isfile(os.path.join(self.state, "decisions.jsonl")))

    def test_paper_with_approval_and_a_good_file_runs_and_is_labelled_real(self):
        self.csv()
        self.fixture_gate()
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 0, out)
        first = out.splitlines()[0]
        self.assertIn("REAL BARS, PAPER ONLY", first)
        self.assertNotIn("TEST ONLY", first)
        with open(os.path.join(self.state, "summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual(s["data_kind"], "real")
        self.assertEqual(s["source_report"]["rows"], N_ROWS)
        self.assertTrue(s["data_note"].startswith("REAL BARS, PAPER ONLY"))
        # Running it again adds nothing.
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 0, out)
        with open(os.path.join(self.state, "decisions.jsonl"), encoding="utf-8") as fh:
            self.assertEqual(len([ln for ln in fh if ln.strip()]), N_ROWS)

    def decision_count(self):
        with open(os.path.join(self.state, "decisions.jsonl"), encoding="utf-8") as fh:
            return len([ln for ln in fh if ln.strip()])

    def test_a_longer_file_on_a_later_run_adds_only_the_new_bars(self):
        self.fixture_gate()
        self.csv(rows=good_rows(100))
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 0, out)
        self.assertEqual(self.decision_count(), 100)
        self.csv(rows=good_rows(110))
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 0, out)
        self.assertEqual(self.decision_count(), 110)

    def state_files(self):
        out = {}
        for name in sorted(os.listdir(self.state)):
            with open(os.path.join(self.state, name), "rb") as fh:
                out[name] = fh.read()
        return out

    def refetch_is_refused(self, first_rows, second_rows, differ):
        """A second file whose rows no longer line up with the saved run.

        real_feed numbers rows from 1 each time and the engine knows a bar by
        that number, so a slid window used to lose bars while the feed was
        still reported accepted (advisor finding B4, 2026-11-15).
        """
        self.fixture_gate()
        self.csv(rows=first_rows)
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 0, out)
        self.assertEqual(self.decision_count(), len(first_rows))
        saved = self.state_files()
        self.csv(rows=second_rows)
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 2, out)
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        self.assertIn("DOES NOT LINE UP WITH THE SAVED PAPER RUN", out)
        self.assertIn("%d of its %d rows differ" % (differ, len(second_rows)), out)
        self.assertIn("--fresh", out)
        self.assertNotIn("accepted", out)
        self.assertEqual(self.state_files(), saved, "a refused re-fetch must leave the saved run alone")
        # The documented repeat step: the same command with --fresh rebuilds from the new file.
        code, out = self.cli("paper", "--source", self.source(), "--fresh")
        self.assertEqual(code, 0, out)
        self.assertNotIn("conflicting_duplicate", out)
        self.assertIn("%d accepted this run, 0 rejected" % len(second_rows), out)
        self.assertEqual(self.decision_count(), len(second_rows))

    def test_a_refetch_whose_window_slid_is_refused_until_fresh(self):
        # Advisor case 2: a row cap dropped the 7 oldest rows and 35 new bars arrived.
        # Before the fix, 28 of the 35 were accepted, 7 were lost, and the feed was "accepted".
        rows = good_rows(175)
        self.refetch_is_refused(rows[:140], rows[7:], differ=140)

    def test_a_refetch_with_the_same_row_count_is_refused_until_fresh(self):
        # Advisor case 3: a full-cap re-fetch, the same 140 rows count, 35 bars later.
        # Before the fix, none of the 35 new bars were accepted and the feed was "accepted".
        rows = good_rows(175)
        self.refetch_is_refused(rows[:140], rows[35:], differ=140)

    def test_a_refetch_that_only_grew_still_needs_no_fresh(self):
        # Advisor case 1 stays as it was: same start, 35 more rows, all 35 accepted.
        self.fixture_gate()
        rows = good_rows(175)
        self.csv(rows=rows[:140])
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 0, out)
        self.csv(rows=rows)
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 0, out)
        self.assertIn("35 accepted this run", out)
        self.assertEqual(self.decision_count(), 175)

    def test_a_shorter_file_on_a_later_run_is_refused_until_fresh(self):
        # Codex's boundary (codex/NOV15_B4_CODEX.md, 2026-11-15): a strictly shorter file whose
        # rows all match used to add nothing and keep the longer saved run, while the new
        # source report described the shorter file.
        self.fixture_gate()
        rows = good_rows(156)
        self.csv(rows=rows)
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 0, out)
        self.assertEqual(self.decision_count(), 156)
        saved = self.state_files()
        self.csv(rows=rows[:141])
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 2, out)
        self.assertEqual(len(out.strip().splitlines()), 1, out)
        self.assertIn("REAL FILE IS SHORTER THAN THE SAVED PAPER RUN", out)
        self.assertIn("it has 141 rows and the saved run holds 156 bars", out)
        self.assertIn("--fresh", out)
        self.assertNotIn("accepted", out)
        self.assertEqual(self.state_files(), saved, "a refused shorter file must leave the saved run alone")
        code, out = self.cli("paper", "--source", self.source(), "--fresh")
        self.assertEqual(code, 0, out)
        self.assertIn("141 accepted this run, 0 rejected", out)
        self.assertEqual(self.decision_count(), 141)

    def test_the_same_file_again_still_needs_no_fresh(self):
        self.fixture_gate()
        self.csv(rows=good_rows(100))
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 0, out)
        code, out = self.cli("paper", "--source", self.source())
        self.assertEqual(code, 0, out)
        self.assertIn("0 accepted this run", out)
        self.assertEqual(self.decision_count(), 100)

    def test_the_smaller_size_needs_its_own_approval(self):
        small = os.path.join(TVBOT, "config", "smaller_size.json")
        self.csv()
        self.fixture_gate()                      # an approval for the default settings
        code, out = self.cli("paper", "--source", self.source(), "--config", small)
        self.assertEqual(code, 2, out)
        self.nothing_was_read()
        self.fixture_gate(cfg_hash="7985e87d4578")   # the smaller-size settings
        code, out = self.cli("paper", "--source", self.source(), "--config", small)
        self.assertEqual(code, 0, out)
        self.assertIn("REAL BARS, PAPER ONLY", out.splitlines()[0])

    def test_gate_refuses_an_answer_that_was_not_typed_in_a_terminal(self):
        code, out = self.cli("gate", stdin=io.StringIO("APPROVE PAPER ONLY\n"))
        self.assertEqual(code, 2)
        self.assertIn("NOT RECORDED", out)
        self.assertFalse(os.path.exists(self.gate))

    def test_gate_show_records_nothing(self):
        code, out = self.cli("gate", "--show")
        self.assertEqual(code, 0)
        self.assertIn("share of the daily loss limit", out)
        self.assertIn("not evidence", out)
        self.assertFalse(os.path.exists(self.gate))

    def typed(self, text):
        """What the gate does with a typed answer, using a stand-in terminal and a temp gate file."""
        clean = dict((k, v) for k, v in os.environ.items()
                     if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")
                     and not k.startswith("CODEX_SANDBOX"))
        with mock.patch.dict(os.environ, clean, clear=True):
            return self.cli("gate", stdin=FakeTerminal(text + "\n"), stdout=FakeTerminal())

    def test_gate_records_only_the_two_exact_answers(self):
        code, out = self.typed("yes")
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(self.gate))
        code, out = self.typed("approve paper only")
        self.assertEqual(code, 1)
        self.assertFalse(os.path.exists(self.gate))
        code, out = self.typed("PASS")
        self.assertEqual(code, 0)
        with open(self.gate, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["decision"], "pass")
        code, out = self.typed("APPROVE PAPER ONLY")
        self.assertEqual(code, 0)
        with open(self.gate, encoding="utf-8") as fh:
            g = json.load(fh)
        self.assertEqual(g["schema"], riskinfo.GATE_SCHEMA)
        self.assertEqual(g["decision"], "approve_paper_only")
        self.assertEqual((g["rule_id"], g["config_hash"]), (self.rule_id, self.cfg_hash))
        self.assertEqual(g["scope"], riskinfo.SCOPE)
        self.assertEqual(g["shown"]["risk"]["stop_share_of_daily_limit_pct"], 80.0)
        self.assertTrue(run.gate_in_force(run.load_gate(), self.rule_id, self.cfg_hash))

    def test_gate_inside_an_assistant_session_is_refused_even_with_a_terminal(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            code, out = self.cli("gate", stdin=FakeTerminal("APPROVE PAPER ONLY\n"),
                                 stdout=FakeTerminal())
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(self.gate))


if __name__ == "__main__":
    unittest.main()
