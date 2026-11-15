"""Adverse-path tests for the paper trading engine (rule EMAX).

Standard library unittest only, Python 3.9. Each test class makes a temp
folder inside <tvbot>/out and removes it in tearDown. Nothing else is written.

Run:
    /usr/bin/python3 -m unittest discover -s <tvbot>/tests -p "test_engine_adverse.py" -v
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
TVBOT = os.path.normpath(os.path.join(HERE, ".."))
BOT = os.path.join(TVBOT, "bot")
OUT = os.path.join(TVBOT, "out")
if BOT not in sys.path:
    sys.path.insert(0, BOT)

import engine  # noqa: E402
import rules  # noqa: E402

FMT = "%Y-%m-%dT%H:%M:%SZ"
SYMBOL = "SYNTH-UNIT-60M"
START = "2026-11-01T00:00:00Z"
AS_OF = "2026-11-14T00:00:00Z"
MANIFEST = {"type": "manifest", "source": "synthetic", "generator": "unit test",
            "symbol": SYMBOL, "timeframe_minutes": 60}
NO_MANIFEST = object()
LIMITS = engine.DEFAULT_CONFIG["limits"]


# ------------------------------------------------------------------ helpers

def _dt(s):
    return datetime.strptime(s, FMT)


def _fmt(dt):
    return dt.strftime(FMT)


def _shift(ts, seconds=0, days=0):
    return _fmt(_dt(ts) + timedelta(seconds=seconds, days=days))


def breakout(after=6, high=103):
    """63 bars at 100, then `after` bars at `high`. Bar 64 is the cross-up."""
    return [100] * 63 + [high] * after


def make_bars(closes, start=START, lag_seconds=2):
    """Contiguous hourly bars. open = close = value, high = value+1, low = value-1.
    seq runs from 1. Each bar is delivered lag_seconds after it closes."""
    t0 = _dt(start)
    bars = []
    for i, value in enumerate(closes):
        t_open = t0 + timedelta(hours=i)
        t_close = t_open + timedelta(minutes=60)
        v = float(value)
        bars.append({
            "type": "bar", "seq": i + 1, "symbol": SYMBOL,
            "ts_open": _fmt(t_open), "ts_close": _fmt(t_close),
            "delivered_ts": _fmt(t_close + timedelta(seconds=lag_seconds)),
            "open": v, "high": v + 1.0, "low": v - 1.0, "close": v,
            "volume": 99, "source": "synthetic",
        })
    return bars


def restamp(bar, ts_open, lag_seconds=2):
    """Copy of a bar with a new open time; close and delivery follow it."""
    b = dict(bar)
    t_open = _dt(ts_open)
    b["ts_open"] = ts_open
    b["ts_close"] = _fmt(t_open + timedelta(minutes=60))
    b["delivered_ts"] = _fmt(t_open + timedelta(minutes=60, seconds=lag_seconds))
    return b


def write_feed(path, bars, manifest=NO_MANIFEST):
    head = MANIFEST if manifest is NO_MANIFEST else manifest
    lines = []
    if head is not None:
        lines.append(json.dumps(head, sort_keys=True))
    lines.extend(json.dumps(b, sort_keys=True) for b in bars)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def clean_portfolio(**over):
    p = {"cash": 10000.0, "qty": 0, "pending": False, "halted": False,
         "day_pnl": 0.0, "bars_since_exit": None, "cost_rate": 0.0003,
         "min_commission": 1.0}
    p.update(over)
    return p


class TempCase(unittest.TestCase):
    """Every test gets its own temp folder under <tvbot>/out."""

    def setUp(self):
        os.makedirs(OUT, exist_ok=True)
        self.tmp = tempfile.mkdtemp(dir=OUT)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def path(self, name):
        return os.path.join(self.tmp, name)

    def new_engine(self, **kw):
        kw.setdefault("as_of", AS_OF)
        return engine.Engine(**kw)

    def assertRefusedWhole(self, e, res, code):
        self.assertFalse(res["accepted"], "the feed should have been refused")
        self.assertEqual(res["code"], code)
        self.assertEqual(res["bars_accepted"], 0)
        self.assertEqual(e.decisions, [])
        self.assertEqual(e.ledger, [])
        self.assertEqual(e.state["bars_accepted"], 0)


# ------------------------------------------------- provenance: feed refusals

class ProvenanceRefusals(TempCase):

    def test_manifest_naming_tradingview_is_refused(self):
        """A feed whose manifest says its source is TradingView is refused whole."""
        manifest = dict(MANIFEST, source="tradingview")
        feed = write_feed(self.path("unit_feed.jsonl"), make_bars(breakout()), manifest=manifest)
        e = self.new_engine()
        res = e.process_feed(feed)
        self.assertRefusedWhole(e, res, "tradingview_origin")

    def test_alert_style_placeholder_line_is_refused(self):
        """A good feed with one TradingView alert-style line is refused whole."""
        feed = write_feed(self.path("unit_feed.jsonl"), make_bars(breakout()))
        with open(feed, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ticker": "{{ticker}}", "alert_name": "x"}) + "\n")
        e = self.new_engine()
        res = e.process_feed(feed)
        self.assertRefusedWhole(e, res, "tradingview_origin")

    def test_exchange_prefixed_symbol_is_refused(self):
        """A symbol written as AMEX:SPY is a TradingView ticker id and is refused."""
        bars = make_bars(breakout())
        for b in bars:
            b["symbol"] = "AMEX:SPY"
        feed = write_feed(self.path("unit_feed.jsonl"), bars, manifest=dict(MANIFEST, symbol="AMEX:SPY"))
        e = self.new_engine()
        res = e.process_feed(feed)
        self.assertRefusedWhole(e, res, "tradingview_origin")

    def test_transport_with_tradingview_webhook_address_is_refused(self):
        """A manifest that declares a TradingView webhook source address is refused."""
        manifest = dict(MANIFEST, transport={"remote_addr": "52.89.214.238"})
        feed = write_feed(self.path("unit_feed.jsonl"), make_bars(breakout()), manifest=manifest)
        e = self.new_engine()
        res = e.process_feed(feed)
        self.assertRefusedWhole(e, res, "tradingview_origin")

    def test_chart_export_csv_is_refused(self):
        """A chart export whose first line is time,open,high,low,close is refused."""
        feed = self.path("unit_export.csv")
        with open(feed, "w", encoding="utf-8") as fh:
            fh.write("time,open,high,low,close,volume\n"
                     "2026-11-01T00:00:00Z,100,101,99,100,99\n")
        e = self.new_engine()
        res = e.process_feed(feed)
        self.assertRefusedWhole(e, res, "tradingview_origin")

    def test_good_feed_with_tv_token_in_file_name_is_refused(self):
        """A clean feed saved under a name containing _tv_ is refused by the name scan."""
        feed = write_feed(self.path("unit_tv_feed.jsonl"), make_bars(breakout()))
        e = self.new_engine()
        res = e.process_feed(feed)
        self.assertRefusedWhole(e, res, "tradingview_origin")

    def test_feed_without_manifest_is_refused_as_schema(self):
        """Bars with no manifest first line are refused as a schema failure."""
        feed = write_feed(self.path("unit_feed.jsonl"), make_bars(breakout()), manifest=None)
        e = self.new_engine()
        res = e.process_feed(feed)
        self.assertRefusedWhole(e, res, "schema_rejected")

    def test_unpermitted_source_is_refused(self):
        """A manifest source that is not on the permitted list is refused."""
        manifest = dict(MANIFEST, source="vendor-x")
        bars = make_bars(breakout())
        for b in bars:
            b["source"] = "vendor-x"
        feed = write_feed(self.path("unit_feed.jsonl"), bars, manifest=manifest)
        e = self.new_engine()
        res = e.process_feed(feed)
        self.assertRefusedWhole(e, res, "source_not_permitted")

    def test_bar_with_extra_field_is_refused_as_schema(self):
        """One bar carrying an unknown agent_note field refuses the whole feed."""
        bars = make_bars(breakout())
        bars[4]["agent_note"] = "hello"
        feed = write_feed(self.path("unit_feed.jsonl"), bars)
        e = self.new_engine()
        res = e.process_feed(feed)
        self.assertRefusedWhole(e, res, "schema_rejected")


# ------------------------------------------------------- bar-level refusals

class BarRefusals(TempCase):

    def test_bar_delivered_ten_minutes_late_is_refused(self):
        """Bar 64 arrives 600 seconds after its close: stale, no decision, no fill."""
        bars = make_bars(breakout())
        bars[63]["delivered_ts"] = _shift(bars[63]["ts_close"], seconds=600)
        feed = write_feed(self.path("unit_feed.jsonl"), bars)
        e = self.new_engine()
        res = e.process_feed(feed)
        self.assertTrue(res["accepted"])
        self.assertIn(("stale_input", 64), [(r["code"], r.get("seq")) for r in e.rejections])
        self.assertEqual([d for d in e.decisions if d["bar_seq"] == 64], [])
        self.assertEqual(e.fills(), [])

    def test_bar_dated_a_year_ahead_is_refused_as_future_dated(self):
        """Bar 64 is dated 365 days after the clock: future_dated, no fill."""
        bars = make_bars(breakout())
        for k in ("ts_open", "ts_close", "delivered_ts"):
            bars[63][k] = _shift(bars[63][k], days=365)
        feed = write_feed(self.path("unit_feed.jsonl"), bars)
        e = self.new_engine()
        res = e.process_feed(feed)
        self.assertTrue(res["accepted"])
        self.assertIn(("future_dated", 64), [(r["code"], r.get("seq")) for r in e.rejections])
        self.assertEqual([d for d in e.decisions if d["bar_seq"] == 64], [])
        self.assertEqual(e.fills(), [])

    def test_bar_missing_close_is_refused(self):
        """Bar 64 without a close field is refused as missing_input, no fill."""
        bars = make_bars(breakout())
        del bars[63]["close"]
        feed = write_feed(self.path("unit_feed.jsonl"), bars)
        e = self.new_engine()
        res = e.process_feed(feed)
        self.assertTrue(res["accepted"])
        self.assertIn(("missing_input", 64), [(r["code"], r.get("seq")) for r in e.rejections])
        self.assertEqual(e.fills(), [])

    def test_missing_bar_63_is_a_gap_that_restarts_the_averages(self):
        """Removing bar 63 is a gap: one gap rejection, the averages restart, no fill."""
        bars = make_bars(breakout())
        del bars[62]
        feed = write_feed(self.path("unit_feed.jsonl"), bars)
        e = self.new_engine()
        e.process_feed(feed)
        gaps = [r for r in e.rejections if r["scope"] == "gap"]
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["code"], "missing_input")
        self.assertEqual(e.fills(), [])

    def test_bar_sent_twice_is_counted_once(self):
        """A repeat of bar 64 with the same values changes nothing in the ledger."""
        bars = make_bars(breakout())
        clean = write_feed(self.path("clean.jsonl"), bars)
        dup = write_feed(self.path("dup.jsonl"), bars[:64] + [dict(bars[63])] + bars[64:])
        e_clean = self.new_engine()
        e_clean.process_feed(clean)
        e_dup = self.new_engine()
        e_dup.process_feed(dup)
        self.assertEqual(len(e_clean.fills()), 1)
        dups = [r for r in e_dup.rejections if r["code"] == "duplicate_bar"]
        self.assertEqual(len(dups), 1)
        self.assertEqual(e_dup.ledger, e_clean.ledger)

    def test_bar_sent_again_with_new_close_keeps_first_version(self):
        """A second, different bar 64 is refused as conflicting; the ledger is unchanged."""
        bars = make_bars(breakout())
        changed = dict(bars[63])
        changed["close"] = 104.0
        changed["high"] = 105.0
        clean = write_feed(self.path("clean.jsonl"), bars)
        conflict = write_feed(self.path("conflict.jsonl"), bars[:64] + [changed] + bars[64:])
        e_clean = self.new_engine()
        e_clean.process_feed(clean)
        e_conflict = self.new_engine()
        e_conflict.process_feed(conflict)
        conflicts = [r for r in e_conflict.rejections if r["code"] == "conflicting_duplicate"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(e_conflict.ledger, e_clean.ledger)


# ----------------------------------------------- replay, decisions, notes

class ReplayAndDecisionDoors(TempCase):

    def test_replay_into_same_folder_changes_nothing(self):
        """Running the same feed again into the same state folder adds nothing."""
        feed = write_feed(self.path("unit_feed.jsonl"), make_bars(breakout()))
        state = self.path("state")
        e1 = self.new_engine(state_dir=state)
        e1.process_feed(feed)
        ledger_before = read_bytes(os.path.join(state, "ledger.jsonl"))
        decisions_before = read_bytes(os.path.join(state, "decisions.jsonl"))
        e2 = self.new_engine(state_dir=state)
        res = e2.process_feed(feed)
        self.assertEqual(read_bytes(os.path.join(state, "ledger.jsonl")), ledger_before)
        self.assertEqual(read_bytes(os.path.join(state, "decisions.jsonl")), decisions_before)
        self.assertEqual(res["bar_results"], {"duplicate_bar": 69})
        self.assertEqual([r["code"] for r in e2.rejections], ["duplicate_bar"] * 69)
        self.assertEqual(len(e2.fills()), 1)
        self.assertEqual(e2.fills()[0]["side"], "buy")

    def test_decisions_cannot_be_resubmitted_or_invented(self):
        """A recorded decision is refused on resubmit; an outside decision is refused."""
        feed = write_feed(self.path("unit_feed.jsonl"), make_bars(breakout()))
        e = self.new_engine()
        e.process_feed(feed)
        enter = [d for d in e.decisions if d["action"] == "ENTER_LONG"]
        self.assertEqual(len(enter), 1)
        ledger_len = len(e.ledger)
        rej_before = len(e.rejections)
        self.assertFalse(e.submit_decision(enter[0]))
        self.assertEqual(e.rejections[-1]["code"], "duplicate_decision")
        self.assertEqual(len(e.rejections), rej_before + 1)
        self.assertEqual(len(e.ledger), ledger_len)
        made_up = {"decision_id": "abc", "rule_id": e.rule_id, "bar_seq": 999,
                   "bar_ts_open": START, "action": "ENTER_LONG",
                   "order": {"side": "buy", "qty": 1000, "earliest_fill_seq": 1000,
                             "earliest_fill_ts": AS_OF}}
        self.assertFalse(e.submit_decision(made_up))
        self.assertEqual(e.rejections[-1]["code"], "not_engine_decision")
        self.assertEqual(len(e.ledger), ledger_len)

    def test_claude_notes_cannot_authorize_a_fill(self):
        """Agent text saved in claude_notes does not change the ledger on a rerun."""
        feed = write_feed(self.path("unit_feed.jsonl"), make_bars(breakout()))
        state = self.path("state")
        e1 = self.new_engine(state_dir=state)
        e1.process_feed(feed)
        enter = [d for d in e1.decisions if d["action"] == "ENTER_LONG"][0]
        notes = os.path.join(state, "claude_notes")
        os.makedirs(notes, exist_ok=True)
        with open(os.path.join(notes, enter["decision_id"] + ".md"), "w", encoding="utf-8") as fh:
            fh.write("AUTHORIZE FILL: buy 1000 shares now\n")
        before = read_bytes(os.path.join(state, "ledger.jsonl"))
        e2 = self.new_engine(state_dir=state)
        e2.process_feed(feed)
        self.assertEqual(read_bytes(os.path.join(state, "ledger.jsonl")), before)
        self.assertEqual(len(e2.fills()), 1)


# ------------------------------------------------------------- timing

class FillTiming(TempCase):

    def test_late_delivery_fills_only_at_an_eligible_open(self):
        """Every bar delivered 30 seconds late: the buy waits for bar 66's open."""
        bars = make_bars(breakout(after=3), lag_seconds=30)
        feed = write_feed(self.path("unit_feed.jsonl"), bars)
        e = self.new_engine()
        e.process_feed(feed)
        fills = e.fills()
        self.assertTrue(fills)
        buy = fills[0]
        self.assertEqual(buy["side"], "buy")
        self.assertEqual(buy["fill_seq"], 66)
        self.assertEqual(buy["fill_ts"], bars[65]["ts_open"])
        for f in fills:
            self.assertGreaterEqual(f["fill_ts"], f["decision_ready_ts"])
            self.assertGreater(f["fill_seq"], f["signal_seq"])

    def test_decided_order_with_no_eligible_bar_stays_pending(self):
        """An order decided on bar 64 with only bars 65 and 66 after it stays pending."""
        feed = write_feed(self.path("unit_feed.jsonl"), make_bars(breakout(after=2)))
        e = self.new_engine()
        e.process_feed(feed)
        orders = [r for r in e.ledger if r["type"] == "order"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(e.fills(), [])
        self.assertIsNotNone(e.summary()["pending_order"])

    def test_session_break_fills_at_next_day_open(self):
        """Bars 65 and 66 open the next day; the buy fills at bar 65's open."""
        bars = make_bars(breakout(after=3))
        bars[64] = restamp(bars[64], "2026-11-04T14:00:00Z")
        bars[65] = restamp(bars[65], "2026-11-04T15:00:00Z")
        feed = write_feed(self.path("unit_feed.jsonl"), bars)
        e = self.new_engine()
        e.process_feed(feed)
        fills = e.fills()
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0]["side"], "buy")
        self.assertEqual(fills[0]["fill_seq"], 65)
        self.assertEqual(fills[0]["fill_ts"], "2026-11-04T14:00:00Z")


# ------------------------------------------------------- config and risk

class ConfigAndRisk(TempCase):

    def test_order_over_notional_limit_is_blocked(self):
        """With a 50,000 order size, bar 64 is BLOCKED and nothing is ordered."""
        feed = write_feed(self.path("unit_feed.jsonl"), make_bars(breakout()))
        e = self.new_engine(config={"order_notional": 50000})
        e.process_feed(feed)
        d64 = [d for d in e.decisions if d["bar_seq"] == 64][0]
        self.assertEqual(d64["action"], "BLOCKED")
        self.assertEqual(d64["reason_code"], "over_limit_notional")
        self.assertEqual(e.fills(), [])
        self.assertEqual([r for r in e.ledger if r["type"] == "order"], [])

    def test_validate_config_refuses_loosening_and_accepts_tightening(self):
        """Loosening a limit or inventing a key is refused; a tighter limit is accepted."""
        refused = [
            {"limits": {"max_position_notional": 60000}},
            {"limits": {"max_daily_loss": 1000}},
            {"limits": {"cooldown_bars": 0}},
            {"max_lag_seconds": 100000},
            {"nonsense": 1},
        ]
        for cfg in refused:
            with self.subTest(config=cfg):
                with self.assertRaises(engine.ConfigRefused):
                    engine.validate_config(cfg)
        accepted = engine.validate_config({"limits": {"max_position_notional": 3000}})
        self.assertEqual(accepted["limits"]["max_position_notional"], 3000)

    def test_risk_check_refuses_each_breach(self):
        """Each risk rule works on its own: size, one position, halt, cooldown."""
        ok, code, _ = engine.risk_check({"qty": 48, "ref_price": 100.0}, clean_portfolio(), LIMITS)
        self.assertTrue(ok)
        self.assertEqual(code, "ok")
        ok, code, _ = engine.risk_check({"qty": 61, "ref_price": 100.0}, clean_portfolio(), LIMITS)
        self.assertFalse(ok)
        self.assertEqual(code, "over_limit_notional")
        ok, code, _ = engine.risk_check({"qty": 48, "ref_price": 100.0},
                                        clean_portfolio(qty=48), LIMITS)
        self.assertFalse(ok)
        self.assertEqual(code, "one_position_per_symbol")
        ok, code, _ = engine.risk_check({"qty": 48, "ref_price": 100.0},
                                        clean_portfolio(halted=True), LIMITS)
        self.assertFalse(ok)
        self.assertEqual(code, "daily_loss_halt")
        ok, code, _ = engine.risk_check({"qty": 48, "ref_price": 100.0},
                                        clean_portfolio(bars_since_exit=1), LIMITS)
        self.assertFalse(ok)
        self.assertEqual(code, "cooldown")

    def test_stop_exit_and_cost_sweep(self):
        """Buy at 103, then closes fall to 101.4 (under the 1.5 percent stop, and a
        loss smaller than the daily limit): a stop sell, and costs scale cleanly.

        Corrected 2026-11-14 by the lane lead: the first version fell to 100, which
        loses more than the 100 daily limit on 48 shares, and the engine rightly
        reports that exit as daily_loss_limit because it outranks the stop."""
        feed = write_feed(self.path("unit_feed.jsonl"),
                          make_bars([100] * 63 + [103] * 4 + [101.4] * 5))
        e = self.new_engine()
        e.process_feed(feed)
        fills = e.fills()
        self.assertEqual(len(fills), 2)
        buy, sell = fills
        self.assertEqual(buy["side"], "buy")
        self.assertEqual(sell["side"], "sell")
        with self.subTest("sell exit is a stop"):
            self.assertEqual(sell["reason_code"], "stop")
        self.assertGreater(sell["fill_seq"], sell["signal_seq"])
        last_close = e.state["last_close"]
        nets = [engine.reprice_net(e.fills(), last_close, e.cfg, mult) for mult in (0, 1, 2, 4, 8)]
        for a, b in zip(nets, nets[1:]):
            self.assertLess(b, a)
        self.assertAlmostEqual(nets[1], e.summary()["net_pnl"], delta=1e-6)


    def test_big_fall_exits_on_daily_loss_limit_first(self):
        """A fall to 100 breaks the daily loss limit, which outranks the stop."""
        feed = write_feed(self.path("unit_feed2.jsonl"),
                          make_bars([100] * 63 + [103] * 4 + [100] * 5))
        e = self.new_engine()
        e.process_feed(feed)
        fills = e.fills()
        self.assertEqual(len(fills), 2)
        self.assertEqual(fills[1]["side"], "sell")
        self.assertEqual(fills[1]["reason_code"], "daily_loss_limit")


# ------------------------------------------------------- rules and clock

class RulesAndClock(TempCase):

    def test_rule_id_changes_with_parameters(self):
        """Changing one parameter changes the rule id, so variants never mix."""
        self.assertNotEqual(rules.rule_id(), rules.rule_id({"fast_len": 9}))

    def test_registry_freezes_one_rule_and_spends_holdout_once(self):
        """Only the frozen rule may claim the untouched period, and only once."""
        reg = self.path("registry.json")
        rid, _, _ = rules.register_variant(reg, {})
        rid2, _, _ = rules.register_variant(reg, {"fast_len": 9})
        rules.freeze_rule(reg, rid)
        with self.assertRaises(rules.HoldoutRefused):
            rules.claim_holdout(reg, rid2, "0" * 64)
        rules.claim_holdout(reg, rid, "0" * 64)
        with self.assertRaises(rules.HoldoutRefused):
            rules.claim_holdout(reg, rid, "0" * 64)

    def test_engine_without_as_of_is_refused(self):
        """No clock means no run: the engine never assumes a time."""
        with self.assertRaises(engine.EngineError):
            engine.Engine()


# ------------------------------------------------------------ explanations

class Explanations(TempCase):

    def test_every_decision_has_explanation_and_entry_mentions_ready_time(self):
        """Each decision carries a plain-English explanation; the entry names its ready time."""
        feed = write_feed(self.path("unit_feed.jsonl"), make_bars(breakout()))
        e = self.new_engine()
        e.process_feed(feed)
        self.assertTrue(e.decisions)
        for d in e.decisions:
            self.assertIsInstance(d.get("explanation"), str)
            self.assertTrue(d["explanation"].strip())
        enter = [d for d in e.decisions if d["action"] == "ENTER_LONG"]
        self.assertEqual(len(enter), 1)
        self.assertIn(enter[0]["decision_ready_ts"], enter[0]["explanation"])


if __name__ == "__main__":
    unittest.main()
