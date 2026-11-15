"""Sizing and limits worksheet (alpaca/sizing.py). Every number here is a synthetic test value."""
import json
import os
import shutil
import sys
import tempfile
import unittest

DESK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK_DIR not in sys.path:
    sys.path.insert(0, DESK_DIR)

from alpaca import sizing  # noqa: E402

# Synthetic test values for the arithmetic only; not anyone's limits.
VALS = {"fixed_shares": 3, "max_loss_per_trade": 12.0, "daily_loss": 40.0,
        "per_trade_notional": 1500.0, "gross_exposure": 1600.0}
PHRASE = sizing.CONFIRM_PHRASE


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="sizing-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, name, obj):
        path = os.path.join(self.dir, name)
        with open(path, "w") as fh:
            json.dump(obj, fh)
        return path


class TestDraft(Base):
    def test_incomplete_draft_is_allowed(self):
        row = sizing.save_draft(self.dir, {"fixed_shares": 2})
        self.assertEqual(row["provenance"], "draft")
        self.assertFalse(row["complete"])
        self.assertIsNone(row["values"]["daily_loss"])
        self.assertEqual(sizing.read_draft(self.dir)["values"]["fixed_shares"], 2)

    def test_bad_values_refused(self):
        for bad in ({"fixed_shares": 1.5}, {"fixed_shares": 0}, {"daily_loss": -1},
                    {"daily_loss": 0}, {"gross_exposure": "lots"}, {"max_loss_per_trade": True},
                    {"per_trade_notional": float("inf")}):
            with self.assertRaises(sizing.LimitsError):
                sizing.save_draft(self.dir, bad)
        self.assertIsNone(sizing.read_draft(self.dir))

    def test_no_defaults_ever(self):
        clean, problems = sizing.validate({}, allow_null=False)
        self.assertEqual(set(clean.values()), {None})
        self.assertEqual(len(problems), 5)


class TestApprove(Base):
    def test_requires_phrase_reason_and_complete_draft(self):
        with self.assertRaises(sizing.LimitsError):
            sizing.approve(self.dir, PHRASE, "reason")              # no draft
        sizing.save_draft(self.dir, {"fixed_shares": 2})
        with self.assertRaises(sizing.LimitsError) as cm:
            sizing.approve(self.dir, PHRASE, "reason")              # incomplete
        self.assertIn("not complete", str(cm.exception))
        sizing.save_draft(self.dir, VALS)
        with self.assertRaises(sizing.LimitsError):
            sizing.approve(self.dir, "yes", "reason")
        with self.assertRaises(sizing.LimitsError):
            sizing.approve(self.dir, PHRASE, "  ")
        self.assertIsNone(sizing.read_approved(self.dir))

    def test_approval_snapshot(self):
        sizing.save_draft(self.dir, VALS)
        snap = sizing.approve(self.dir, PHRASE, "first paper session")
        self.assertEqual(snap["provenance"], "operator-approved")
        self.assertEqual(snap["hash"], sizing.content_hash(VALS))
        self.assertEqual({d["field"] for d in snap["diff"]}, set(sizing.FIELDS))
        self.assertTrue(snap["approved_utc"].endswith("Z"))
        on_disk = sizing.read_approved(self.dir)
        self.assertEqual(on_disk["values"], snap["values"])
        loaded = sizing.load_limits(state_dir=self.dir)
        self.assertEqual(loaded["provenance"], "operator-approved")
        self.assertEqual(loaded["values"], VALS)
        # a second approval records only what changed
        sizing.save_draft(self.dir, dict(VALS, daily_loss=35.0))
        snap2 = sizing.approve(self.dir, PHRASE, "tighter day")
        self.assertEqual(snap2["diff"], [{"field": "daily_loss", "old": 40.0, "new": 35.0}])
        self.assertEqual(snap2["previous_hash"], snap["hash"])

    def test_same_numbers_as_test_example_are_fine_once_approved(self):
        example = sizing.TEST_EXAMPLES[0]["values"]
        sizing.save_draft(self.dir, example, copied_from="test example")
        sizing.approve(self.dir, PHRASE, "I chose these myself")
        self.assertEqual(sizing.load_limits(state_dir=self.dir)["values"]["daily_loss"], example["daily_loss"])


class TestLoadLimits(Base):
    def test_missing_and_malformed(self):
        with self.assertRaises(sizing.LimitsError):
            sizing.load_limits()
        with self.assertRaises(sizing.LimitsError) as cm:
            sizing.load_limits(path=os.path.join(self.dir, "nope.json"))
        self.assertIn("not found", str(cm.exception))
        bad = os.path.join(self.dir, "bad.json")
        with open(bad, "w") as fh:
            fh.write("{not json")
        with self.assertRaises(sizing.LimitsError):
            sizing.load_limits(path=bad)
        with self.assertRaises(sizing.LimitsError) as cm:
            sizing.load_limits(state_dir=self.dir)
        self.assertIn("no approved limits", str(cm.exception))

    def test_template_file_is_all_null_and_refused(self):
        path = os.path.join(DESK_DIR, "alpaca", "limits.template.json")
        with open(path) as fh:
            tpl = json.load(fh)
        self.assertEqual(tpl["provenance"], "template")
        self.assertEqual(set(tpl["values"]), set(sizing.FIELDS))
        self.assertEqual(set(tpl["values"].values()), {None})
        with self.assertRaises(sizing.LimitsError) as cm:
            sizing.load_limits(path=path)
        self.assertIn("template", str(cm.exception))

    def test_refused_provenances(self):
        for prov in ("draft", "template", "test-example", None, "operator"):
            path = self.write("l.json", {"provenance": prov, "values": VALS, "hash": sizing.content_hash(VALS)})
            with self.assertRaises(sizing.LimitsError):
                sizing.load_limits(path=path)

    def test_hash_mismatch_refused(self):
        path = self.write("l.json", {"provenance": "operator-approved", "values": dict(VALS, daily_loss=400.0),
                                     "hash": sizing.content_hash(VALS)})
        with self.assertRaises(sizing.LimitsError) as cm:
            sizing.load_limits(path=path)
        self.assertIn("edited after approval", str(cm.exception))

    def test_null_nonpositive_missing_shares_refused_even_with_good_hash(self):
        for vals in (dict(VALS, daily_loss=None), dict(VALS, gross_exposure=0),
                     {k: v for k, v in VALS.items() if k != "fixed_shares"}, dict(VALS, fixed_shares=2.5)):
            path = self.write("l.json", {"provenance": "operator-approved", "values": vals,
                                         "hash": sizing.content_hash(vals)})
            with self.assertRaises(sizing.LimitsError):
                sizing.load_limits(path=path)

    def test_draft_only_for_mock_rehearsal(self):
        sizing.save_draft(self.dir, VALS)
        with self.assertRaises(sizing.LimitsError):
            sizing.load_limits(state_dir=self.dir)
        loaded = sizing.load_limits(state_dir=self.dir, allow_draft=True)
        self.assertEqual(loaded["provenance"], "draft")
        self.assertEqual(loaded["label"], sizing.DRAFT_LABEL)
        sizing.save_draft(self.dir, {"fixed_shares": 1})
        with self.assertRaises(sizing.LimitsError):
            sizing.load_limits(state_dir=self.dir, allow_draft=True)   # incomplete draft not enforceable

    def test_as_session_limits(self):
        sizing.save_draft(self.dir, VALS)
        sizing.approve(self.dir, PHRASE, "r")
        lim = sizing.as_session_limits(sizing.load_limits(state_dir=self.dir))
        for k in sizing.CAP_FIELDS:
            self.assertEqual(lim[k], VALS[k])
        self.assertEqual(lim["fixed_shares"], 3)
        self.assertEqual(lim["provenance"], "operator-approved")
        self.assertNotIn("TEST", lim["label"])


class TestEffects(unittest.TestCase):
    def test_arithmetic_and_checks(self):
        e = sizing.effects(VALS, ref_price=400.0, stop_distance=2.0, fee_per_share=0.0, slippage_per_share=0.01)
        self.assertEqual(e["notional"], 1200.0)
        self.assertEqual(e["payoff_per_1usd_move"], 3.0)
        self.assertEqual(e["est_loss_at_stop"], 6.06)        # 3*2 + 3*2*0.01
        self.assertEqual(e["assumptions"]["label"], sizing.ASSUMED_LABEL)
        self.assertTrue(e["all_pass"])
        self.assertEqual({c["cap"] for c in e["checks"]}, set(sizing.CAP_FIELDS))
        self.assertEqual(e["remaining_capacity"]["gross_exposure_remaining"], 1600.0)

    def test_over_caps_explained(self):
        e = sizing.effects(VALS, ref_price=600.0, stop_distance=5.0, open_exposure=500.0,
                           realized_loss_today=30.0, working_notional=100.0)
        by = {c["cap"]: c for c in e["checks"]}
        self.assertFalse(by["per_trade_notional"]["ok"])      # 1800 > 1500
        self.assertIn("OVER", by["per_trade_notional"]["reason"])
        self.assertFalse(by["max_loss_per_trade"]["ok"])      # 15 > 12
        self.assertFalse(by["daily_loss"]["ok"])              # 30 + 15 > 40
        self.assertFalse(by["gross_exposure"]["ok"])          # 500 + 100 + 1800 > 1600
        self.assertEqual(e["worst_case_if_all_working_fill"], 2400.0)
        self.assertFalse(e["all_pass"])

    def test_unset_fields_fail_plainly(self):
        e = sizing.effects({"fixed_shares": None}, ref_price=400.0, stop_distance=1.0)
        self.assertFalse(e["all_pass"])
        self.assertIn("fixed_shares", e["checks"][0]["reason"])
        self.assertEqual(e["suggestions"], [])

    def test_suggestions_read_only(self):
        draft = dict(VALS)
        e = sizing.effects(draft, ref_price=400.0, stop_distance=2.0)
        self.assertEqual(draft, VALS)
        texts = {s["text"]: s["shares"] for s in e["suggestions"]}
        self.assertIn(6, texts.values())       # floor(12 / 2)
        self.assertIn(3, texts.values())       # floor(1500 / 400)
        self.assertTrue(all(s["label"] == sizing.SUGGESTION_LABEL for s in e["suggestions"]))

    def test_bad_inputs(self):
        for kw in ({"ref_price": 0, "stop_distance": 1}, {"ref_price": 400, "stop_distance": -1},
                   {"ref_price": "x", "stop_distance": 1}, {"ref_price": 400, "stop_distance": 1, "fee_per_share": -0.1}):
            with self.assertRaises(sizing.LimitsError):
                sizing.effects(VALS, **kw)


class TestWorksheet(Base):
    def test_view_shows_pending_diff_and_examples(self):
        sizing.save_draft(self.dir, VALS)
        sizing.approve(self.dir, PHRASE, "r")
        sizing.save_draft(self.dir, dict(VALS, fixed_shares=2))
        w = sizing.worksheet(self.dir)
        self.assertEqual(w["pending_diff"], [{"field": "fixed_shares", "old": 3, "new": 2}])
        self.assertIs(w["approved_ok"], True)
        self.assertEqual(w["active"]["provenance"], "operator-approved")
        self.assertEqual(w["test_examples"][0]["provenance"], "test-example")
        self.assertIn("TEST EXAMPLE", w["test_examples"][0]["label"])
        self.assertEqual(w["confirm_phrase"], PHRASE)

    def test_empty_state_dir(self):
        w = sizing.worksheet(self.dir)
        self.assertIsNone(w["draft"])
        self.assertIn("error", w["active"])


if __name__ == "__main__":
    unittest.main()
