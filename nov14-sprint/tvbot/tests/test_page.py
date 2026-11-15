"""Checks for bot/page.py, the static result page. Paper only; stdlib only.

Run: /usr/bin/python3 -I nov14-sprint/tvbot/tests/test_page.py

All files the tests write go into a temp directory. The saved test run is only read.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TVBOT = os.path.dirname(HERE)
BOT = os.path.join(TVBOT, "bot")
if BOT not in sys.path:
    sys.path.insert(0, BOT)

import engine  # noqa: E402
import page  # noqa: E402
import riskinfo  # noqa: E402
import run  # noqa: E402

NOW = "2026-11-14T03:00:00Z"
SAVED_RUN = os.path.join(TVBOT, "out", "normal")
FIXTURE_CLOCK = "2026-11-14T00:00:00Z"
# Made-up numbers, so a pass proves the page reads them from the summary.
SWEEP = [{"mult": 0, "net": 301.11}, {"mult": 1, "net": 222.22}, {"mult": 2, "net": 143.33},
         {"mult": 4, "net": 55.44}, {"mult": 8, "net": -12.34}]
SWEEP_CAPTION = "Same trades, every cost multiplied"


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="tvbot_page_test_")
        cls.state = os.path.join(cls.tmp, "normal")
        os.makedirs(cls.state)
        for name in ("summary.json", "ledger.jsonl"):
            shutil.copy(os.path.join(SAVED_RUN, name), os.path.join(cls.state, name))
        with open(os.path.join(cls.state, "summary.json"), "r", encoding="utf-8") as fh:
            cls.summary = json.load(fh)
        with open(os.path.join(cls.state, "ledger.jsonl"), "r", encoding="utf-8") as fh:
            cls.rule_id = json.loads(fh.readline())["rule_id"]
        cls.missing = os.path.join(cls.tmp, "does_not_exist")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build(self, gate=None, source=None, paper=None, state=None):
        return page.build_html(state or self.state, paper or self.missing,
                               gate or os.path.join(self.missing, "gate.json"),
                               source or os.path.join(self.missing, "source.json"), NOW)

    def gate_file(self, name, rule_id, config_hash, decision="approve_paper_only"):
        path = os.path.join(self.tmp, name)
        write_json(path, {"schema": riskinfo.GATE_SCHEMA, "decision": decision,
                          "decided_utc": "2026-11-14T02:00:00Z", "typed": riskinfo.APPROVE_TEXT,
                          "rule_id": rule_id, "config_hash": config_hash,
                          "scope": riskinfo.SCOPE, "shown": {}})
        return path

    def test_caveat_sentence_uses_net_from_summary(self):
        net = self.summary["net_pnl"]
        expected = "%s on one synthetic sample is not evidence of an edge." % ("{:+,.2f}".format(net))
        self.assertIn(expected, self.build())

    def test_test_only_label_present(self):
        self.assertIn("TEST ONLY: synthetic", self.build())

    def test_no_gate_file_says_not_decided(self):
        html_text = self.build()
        self.assertIn("Not decided yet", html_text)
        self.assertNotIn("Approved for paper mode only", html_text)
        self.assertIn("/usr/bin/python3 -I nov14-sprint/tvbot/bot/run.py gate", html_text)
        self.assertIn("Then type APPROVE PAPER ONLY or PASS.", html_text)

    def test_matching_gate_says_approved(self):
        gate = self.gate_file("gate_ok.json", self.rule_id, self.summary["config_hash"])
        self.assertIn("Approved for paper mode only", self.build(gate=gate))

    def test_mismatched_rule_id_is_not_approved(self):
        gate = self.gate_file("gate_bad_rule.json", "EMAX-9.9.9-deadbeef", self.summary["config_hash"])
        html_text = self.build(gate=gate)
        self.assertNotIn("Approved for paper mode only", html_text)
        self.assertIn("different rule or settings", html_text)

    def test_mismatched_config_hash_is_not_approved(self):
        gate = self.gate_file("gate_bad_hash.json", self.rule_id, "000000000000")
        self.assertNotIn("Approved for paper mode only", self.build(gate=gate))

    def test_pass_decision_says_passed(self):
        gate = self.gate_file("gate_pass.json", self.rule_id, self.summary["config_hash"], decision="pass")
        html_text = self.build(gate=gate)
        self.assertIn("Passed", html_text)
        self.assertNotIn("Approved for paper mode only", html_text)

    def test_no_script_tag(self):
        self.assertNotIn("<script", self.build().lower())

    def test_source_report_values_are_escaped(self):
        report = os.path.join(self.tmp, "source.json")
        write_json(report, {"schema": "tvbot-real-source-report-1", "source_name": "<b>Evil</b>",
                            "terms_url": "https://example.test/terms", "approved_by": "Matthew",
                            "approved_utc": "2026-11-14T01:00:00Z", "symbol": "TEST",
                            "timeframe_minutes": 60, "rows": 10,
                            "first_ts_open": "2026-01-01T00:00:00Z", "last_ts_close": "2026-01-02T00:00:00Z",
                            "csv_sha256": "ab" * 32, "delivery_assumption": "<script>x</script>",
                            "converted_utc": "2026-11-14T01:05:00Z"})
        html_text = self.build(source=report)
        self.assertNotIn("<b>Evil</b>", html_text)
        self.assertIn("&lt;b&gt;Evil&lt;/b&gt;", html_text)
        self.assertNotIn("<script", html_text.lower())

    def test_no_source_report_says_no_real_source(self):
        self.assertIn("No real data source is connected.", self.build())

    def test_real_run_uses_real_label(self):
        report = os.path.join(self.tmp, "source_ok.json")
        write_json(report, {"schema": "tvbot-real-source-report-1", "source_name": "Test source",
                            "terms_url": "https://example.test/terms", "approved_by": "Matthew",
                            "approved_utc": "2026-11-14T01:00:00Z", "symbol": "TEST",
                            "timeframe_minutes": 60, "rows": 10,
                            "first_ts_open": "2026-01-01T00:00:00Z", "last_ts_close": "2026-01-02T00:00:00Z",
                            "csv_sha256": "ab" * 32, "delivery_assumption": "on close",
                            "converted_utc": "2026-11-14T01:05:00Z"})
        html_text = self.build(source=report, paper=self.state)
        self.assertIn("REAL BARS, PAPER ONLY", html_text)
        self.assertIn("One run on one file is still not evidence of an edge.", html_text)

    def test_missing_summary_still_writes_a_page(self):
        empty = os.path.join(self.tmp, "empty_state")
        os.makedirs(empty, exist_ok=True)
        html_text = self.build(state=empty)
        self.assertIn("No test run has been saved yet", html_text)
        self.assertIn("Paper only. Nothing on this page can place an order.", html_text)
        self.assertNotIn("<script", html_text.lower())

    # ---- a converted file that the saved paper run was not made from

    def source_report(self, name=None, **over):
        rep = {"schema": "tvbot-real-source-report-1", "source_name": "Test source",
               "terms_url": "https://example.test/terms", "approved_by": "Matthew",
               "approved_utc": "2026-11-14T01:00:00Z", "symbol": "TEST", "timeframe_minutes": 60,
               "rows": 156, "first_ts_open": "2026-01-01T00:00:00Z",
               "last_ts_close": "2026-01-07T12:00:00Z", "csv_sha256": "aa" * 32,
               "delivery_assumption": "on close", "converted_utc": "2026-11-14T01:05:00Z"}
        rep.update(over)
        if name:
            write_json(os.path.join(self.tmp, name), rep)
        return rep

    def test_a_refused_later_file_is_not_shown_as_the_source_of_the_saved_run(self):
        # The paper command converts a file before it can refuse it, so the newest source
        # report can describe a file the saved run never read (codex/NOV15_B4_CODEX.md).
        used = self.source_report()
        self.source_report("later.json", rows=141, csv_sha256="bb" * 32,
                           last_ts_close="2026-01-06T21:00:00Z", converted_utc="2026-11-15T09:00:00Z")
        paper = self.state_with("paper_earlier_file", lambda s: s.update(source_report=used))
        html_text = self.build(source=os.path.join(self.tmp, "later.json"), paper=paper)
        self.assertIn("is not the file the saved paper run was made from", html_text)
        self.assertIn("141 rows, converted 2026-11-15T09:00:00Z", html_text)
        self.assertIn("--fresh", html_text)
        self.assertIn("aa" * 32, html_text, "the table must describe the file the run was made from")
        self.assertNotIn("bb" * 32, html_text)
        self.assertIn("<td>Rows</td><td class=\"l\">156</td>", html_text)

    def test_the_source_the_run_was_made_from_has_no_such_note(self):
        used = self.source_report("same.json")
        paper = self.state_with("paper_same_file", lambda s: s.update(source_report=used))
        html_text = self.build(source=os.path.join(self.tmp, "same.json"), paper=paper)
        self.assertNotIn("is not the file the saved paper run was made from", html_text)
        self.assertIn("aa" * 32, html_text)

    def test_a_run_report_in_the_wrong_format_is_never_used_for_the_table(self):
        self.source_report("latest.json", csv_sha256="cc" * 32)
        paper = self.state_with("paper_bad_report", lambda s: s.update(
            source_report={"schema": "something-else", "csv_sha256": "<b>dd</b>", "rows": 9}))
        html_text = self.build(source=os.path.join(self.tmp, "latest.json"), paper=paper)
        self.assertIn("cc" * 32, html_text)
        self.assertNotIn("<b>dd</b>", html_text)
        self.assertNotIn("is not the file the saved paper run was made from", html_text)

    # ---- the cost sweep ("what if every cost were higher"), read from the summary

    def state_with(self, name, change):
        """A copy of the saved test state whose summary has been changed by change(summary)."""
        state = os.path.join(self.tmp, name)
        os.makedirs(state, exist_ok=True)
        shutil.copy(os.path.join(self.state, "ledger.jsonl"), os.path.join(state, "ledger.jsonl"))
        summary = json.loads(json.dumps(self.summary))
        change(summary)
        write_json(os.path.join(state, "summary.json"), summary)
        return state

    def test_cost_sweep_shows_the_net_at_each_multiplier(self):
        state = self.state_with("sweep", lambda s: s.update(cost_sweep=SWEEP))
        html_text = self.build(state=state)
        self.assertIn(SWEEP_CAPTION, html_text)
        for value in ("+301.11", "+222.22", "+143.33", "+55.44", "-12.34"):
            self.assertIn(value, html_text)
        self.assertIn("At 8 times the costs in the settings, the same trades end at a loss of 12.34.",
                      html_text)

    def test_cost_sweep_with_no_loss_says_so(self):
        gains = [dict(row, net=abs(row["net"])) for row in SWEEP]
        state = self.state_with("sweep_gain", lambda s: s.update(cost_sweep=gains))
        html_text = self.build(state=state)
        self.assertIn(SWEEP_CAPTION, html_text)
        self.assertIn("still a gain at 8 times the costs in the settings", html_text)
        self.assertNotIn("end at a loss of", html_text)

    def test_summary_without_a_cost_sweep_leaves_the_table_out(self):
        state = self.state_with("no_sweep", lambda s: s.pop("cost_sweep", None))
        self.assertNotIn(SWEEP_CAPTION, self.build(state=state))

    def test_a_malformed_cost_sweep_is_left_out_and_never_shown_raw(self):
        bad = [{"mult": "<b>8</b>", "net": "<script>x</script>"}, "junk", {"mult": 2}]
        state = self.state_with("bad_sweep", lambda s: s.update(cost_sweep=bad))
        html_text = self.build(state=state)
        self.assertNotIn(SWEEP_CAPTION, html_text)
        self.assertNotIn("<b>8</b>", html_text)
        self.assertNotIn("<script", html_text.lower())


class CostSweepNumbers(unittest.TestCase):
    """run.cost_sweep: the numbers the replay saves for the page. Synthetic bars only."""

    @classmethod
    def setUpClass(cls):
        cls.e = engine.Engine(as_of=FIXTURE_CLOCK)
        res = cls.e.process_feed(run.NORMAL_FEED)
        assert res["accepted"], res["reasons"]
        cls.sweep = run.cost_sweep(cls.e)

    def test_multipliers_are_zero_one_two_four_eight(self):
        self.assertEqual([row["mult"] for row in self.sweep], [0, 1, 2, 4, 8])

    def test_times_one_equals_the_net_result(self):
        self.assertAlmostEqual(self.sweep[1]["net"], self.e.summary()["net_pnl"], places=5)

    def test_times_zero_equals_the_result_before_costs(self):
        self.assertAlmostEqual(self.sweep[0]["net"], self.e.summary()["gross_pnl_at_raw_opens"], places=5)

    def test_net_falls_as_costs_rise(self):
        nets = [row["net"] for row in self.sweep]
        self.assertTrue(all(a > b for a, b in zip(nets, nets[1:])), nets)

    def test_no_fills_gives_an_empty_sweep(self):
        self.assertEqual(run.cost_sweep(engine.Engine(as_of=FIXTURE_CLOCK)), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
