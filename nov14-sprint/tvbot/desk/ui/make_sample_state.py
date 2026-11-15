"""Write ui/sample_state/: a small hand-placed state dir matching CONTRACT.md.

The events below are placed by hand on the first 70 synthetic fixture bars so
the UI can be built before the integrated runner exists. Nothing here is a
strategy result. Every number is simulated and every fill is a mock fill.

    /usr/bin/python3 -I <abs>/desk/ui/make_sample_state.py [--out DIR]
"""

import argparse
import json
import os
from datetime import datetime, timedelta, timezone

UI_DIR = os.path.dirname(os.path.abspath(__file__))
TVBOT = os.path.dirname(os.path.dirname(UI_DIR))
FIXTURE = os.path.join(TVBOT, "fixtures", "normal_bars.jsonl")
SYMBOL = "SYNTH-FUND-60M"
SLIP = 0.0003
FEE = 1.0


def load_bars(n=70):
    out = []
    with open(FIXTURE, "r", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("type") == "manifest":
                continue
            out.append(row)
            if len(out) >= n:
                break
    return out


def plus(ts, seconds):
    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ") + timedelta(seconds=seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build(out_dir):
    bars = load_bars()
    by_seq = {b["seq"]: b for b in bars}
    decisions, ledger, audit, intents = [], [], [], []
    events = {}

    def bar(seq):
        return by_seq[seq]

    def knew(d, seq):
        b = bar(seq)
        audit.append({"ts": b["delivered_ts"], "kind": "knew", "decision_id": d["decision_id"],
                      "bar_seq": seq, "bar_ts_close": b["ts_close"], "close": b["close"],
                      "volume": b["volume"], "action": d["action"],
                      "note": "bar delivered; decision uses bars with ts_close <= %s" % b["ts_close"],
                      "simulated": True})

    def decision(seq, action, **kw):
        b = bar(seq)
        d = {"decision_id": "D%03d-%s" % (seq, action.replace("_", "")), "ts_knowable": b["ts_close"],
             "symbol": SYMBOL, "strategy": "ema", "action": action, "qty": kw.pop("qty", 0),
             "reason_code": "", "reason_text": "", "case_for": "", "case_against": "",
             "est_cost": None, "pass_condition": "", "trigger": None, "intended_entry": None,
             "intended_exit": None, "invalidation": None, "simulated": True}
        d.update(kw)
        decisions.append(d)
        events[seq] = d
        knew(d, seq)
        return d

    def order(d, side, qty, fill_specs, tag):
        """fill_specs: list of (bar_seq, qty). Market order at the next bar open."""
        intent_id = "I-" + d["decision_id"]
        client_id = "C-" + d["decision_id"]
        order_id = "FB-%s" % tag
        b = bar(fill_specs[0][0])
        req_ts = plus(bar(_seq_of(d))["delivered_ts"], 3)
        intents.append({"intent_id": intent_id, "decision_id": d["decision_id"], "client_id": client_id,
                        "side": side, "qty": qty, "ts": req_ts, "status": "persisted_before_dispatch",
                        "simulated": True})
        audit.append({"ts": req_ts, "kind": "requested", "decision_id": d["decision_id"],
                      "intent_id": intent_id, "client_id": client_id, "side": side, "qty": qty,
                      "type": "market", "note": "intent persisted to intents.jsonl before submit",
                      "simulated": True})
        audit.append({"ts": plus(req_ts, 1), "kind": "acked", "decision_id": d["decision_id"],
                      "intent_id": intent_id, "client_id": client_id, "order_id": order_id,
                      "broker": "FakeBroker (offline)", "simulated": True})
        fills = []
        for i, (seq, q) in enumerate(fill_specs):
            fb = bar(seq)
            px = round(fb["open"] * (1 + SLIP if side == "buy" else 1 - SLIP), 5)
            # wall-clock fill time can't precede the ack, even when the price basis is that bar's open
            fill_ts = max(fb["ts_open"], plus(req_ts, 2 + i))
            f = {"exec_id": "X-%s-%d" % (tag, i + 1), "ts": fill_ts, "bar_seq": seq,
                 "side": side, "qty": q, "price": px, "raw_open": fb["open"], "fee": FEE,
                 "price_basis": "open of bar %d, first bar to open after the decision" % seq,
                 "mock": True, "simulated": True}
            fills.append(f)
            audit.append({"ts": fill_ts, "kind": "filled", "decision_id": d["decision_id"],
                          "intent_id": intent_id, "client_id": client_id, "order_id": order_id,
                          "exec_id": f["exec_id"], "side": side, "qty": q, "price": px,
                          "partial": len(fill_specs) > 1 and i < len(fill_specs) - 1,
                          "mock": True, "simulated": True})
        return {"intent_id": intent_id, "order_id": order_id, "fills": fills, "quote": b["open"]}

    # ---- pass 1 (bar 5): weak cross, low volume ----
    decision(5, "pass", reason_code="low_volume_cross",
             reason_text="Fast EMA ticked above slow EMA, but the bar volume is under the 20-bar median.",
             case_for="Price made a higher close for three bars.",
             case_against="Volume does not confirm and the cross is only 0.02 wide.",
             est_cost=2.0 + round(20 * 100.18 * SLIP * 2, 2),
             pass_condition="Enter only if the cross bar volume >= 20-bar median.",
             trigger=100.18, intended_entry=100.18, intended_exit=100.48, invalidation=99.98,
             side="long")

    # ---- trade A (long, win): entry bar 11, exit bar 27 ----
    dA = decision(11, "enter_long", qty=19, reason_code="cross_up",
                  reason_text="Fast EMA crossed above slow EMA with volume above median.",
                  case_for="Cross confirmed on volume; higher lows for 4 bars.",
                  case_against="Range is narrow (0.4); a fade back to 100.2 is plausible.",
                  est_cost=2.0 + round(19 * 100.36 * SLIP * 2, 2),
                  pass_condition="Pass if the cross bar volume < 20-bar median.",
                  trigger=100.36, intended_entry=100.36, intended_exit=100.80, invalidation=100.15)
    oA = order(dA, "buy", 19, [(12, 19)], "A1")
    dAx = decision(27, "exit", qty=19, reason_code="target_zone",
                   reason_text="Price reached the intended exit zone near 100.8.",
                   case_for="Target reached; momentum is flattening.",
                   case_against="Trend still up; exiting may leave gains.",
                   est_cost=1.0 + round(19 * 100.77 * SLIP, 2), trigger=100.77, intended_exit=100.77)
    oAx = order(dAx, "sell", 19, [(28, 19)], "A2")

    # ---- trade B (long, loss, partial entry fills) ----
    dB = decision(29, "enter_long", qty=19, reason_code="breakout",
                  reason_text="New session high above 100.98 on open.",
                  case_for="Breakout above the prior session high.",
                  case_against="Opened on a gap; the first hour often fades.",
                  est_cost=3.0 + round(19 * 100.89 * SLIP * 2, 2),
                  pass_condition="Pass if the open gaps more than 0.1 above the prior close.",
                  trigger=100.98, intended_entry=100.89, intended_exit=101.30, invalidation=100.62)
    oB = order(dB, "buy", 19, [(30, 12), (31, 7)], "B1")
    dBx = decision(33, "exit", qty=19, reason_code="invalidation",
                   reason_text="Close below the invalidation line at 100.62 area.",
                   case_for="The setup's stated invalidation was reached.",
                   case_against="It may bounce at 100.5 support.",
                   est_cost=1.0 + round(19 * 100.65 * SLIP, 2), trigger=100.62, intended_exit=100.65)
    oBx = order(dBx, "sell", 19, [(34, 19)], "B2")

    # ---- pass 2 (bar 36): trend filter ----
    decision(36, "pass", reason_code="trend_filter_down",
             reason_text="A long setup appeared, but price is below the 50-bar EMA.",
             case_for="Short-term oversold after a 0.5 drop.",
             case_against="Lower highs for 7 bars; trend filter says down.",
             est_cost=2.0 + round(19 * 100.45 * SLIP * 2, 2),
             pass_condition="Long only when close >= 50-bar EMA.",
             trigger=100.45, intended_entry=100.45, intended_exit=100.85, invalidation=100.20,
             side="long")

    # ---- pause / resume control ----
    audit.append({"ts": plus(bar(45)["delivered_ts"], 10), "kind": "control", "control": "pause",
                  "by": "operator (sample)", "effect": "entries blocked; no entry remainders to cancel; "
                  "no protective exits open", "simulated": True})
    audit.append({"ts": plus(bar(48)["delivered_ts"], 10), "kind": "control", "control": "resume",
                  "by": "operator (sample)", "simulated": True})

    # ---- pass 3 (bar 50): cost vs edge, short considered ----
    decision(50, "pass", reason_code="cost_exceeds_edge",
             reason_text="Short setup, but the expected move is smaller than round-trip cost.",
             case_for="Downtrend intact.",
             case_against="Move already extended 1.0; expected edge 0.10 < cost 0.12.",
             est_cost=2.0 + round(20 * 99.32 * SLIP * 2, 2),
             pass_condition="Enter only if expected move > 2x round-trip cost.",
             trigger=99.32, intended_entry=99.32, intended_exit=99.05, invalidation=99.60,
             side="short")

    # ---- trade C (short, still open with a protective stop) ----
    dC = decision(56, "enter_short", qty=20, reason_code="cross_down",
                  reason_text="Fast EMA below slow EMA and a lower low on volume.",
                  case_for="Lower highs and lower lows for two sessions.",
                  case_against="Late in the move; a bounce to 99.0 is plausible.",
                  est_cost=2.0 + round(20 * 98.74 * SLIP * 2, 2),
                  pass_condition="Pass if price is more than 1.5% below the 50-bar EMA.",
                  trigger=98.84, intended_entry=98.74, intended_exit=98.10, invalidation=98.95)
    oC = order(dC, "sell", 20, [(57, 20)], "C1")
    stop_order = {"order_id": "FB-C1-STOP", "client_id": "C-%s-stop" % dC["decision_id"],
                  "side": "buy", "qty": 20, "type": "stop", "stop": 98.95, "reduce_only": True,
                  "protective": True, "status": "working", "simulated": True}
    audit.append({"ts": plus(bar(57)["ts_open"], 2), "kind": "requested", "decision_id": dC["decision_id"],
                  "client_id": stop_order["client_id"], "side": "buy", "qty": 20, "type": "stop",
                  "stop": 98.95, "protective": True, "simulated": True})
    audit.append({"ts": plus(bar(57)["ts_open"], 3), "kind": "acked", "decision_id": dC["decision_id"],
                  "client_id": stop_order["client_id"], "order_id": stop_order["order_id"],
                  "protective": True, "simulated": True})

    # ---- a refused add-on (gross limit counts working orders) ----
    dR = decision(60, "enter_short", qty=20, reason_code="add_on_cross",
                  reason_text="A second short signal while already short.",
                  case_for="Trend continuation.", case_against="Doubles exposure late in the move.",
                  est_cost=2.0, pass_condition="", trigger=98.47, intended_entry=98.47,
                  intended_exit=98.0, invalidation=98.78)
    audit.append({"ts": plus(bar(60)["delivered_ts"], 3), "kind": "rejected", "decision_id": dR["decision_id"],
                  "reason": "gross_exposure limit: filled 1974.2 + working 0 + requested 1969.4 > 3000 (TEST VALUES)",
                  "simulated": True})

    # ---- holds on every other bar (the runner writes one decision per bar) ----
    for b in bars:
        if b["seq"] in events:
            continue
        decisions.append({"decision_id": "D%03d-hold" % b["seq"], "ts_knowable": b["ts_close"], "symbol": SYMBOL,
                          "strategy": "ema", "action": "hold", "qty": 0, "reason_code": "no_signal",
                          "reason_text": "No entry or exit condition on this bar.", "case_for": "",
                          "case_against": "", "est_cost": None, "pass_condition": "", "trigger": None,
                          "intended_entry": None, "intended_exit": None, "invalidation": None,
                          "simulated": True})
    decisions.sort(key=lambda d: d["ts_knowable"])

    # ---- ledger ----
    def trade(tid, d_in, o_in, d_out, o_out, direction):
        fills = o_in["fills"] + (o_out["fills"] if o_out else [])
        fees = sum(f["fee"] for f in fills)
        qty_in = sum(f["qty"] for f in o_in["fills"])
        avg_in = sum(f["qty"] * f["price"] for f in o_in["fills"]) / qty_in
        row = {"trade_id": tid, "signal_ts": d_in["ts_knowable"], "quote": o_in["quote"],
               "decision_id": d_in["decision_id"], "intent_id": o_in["intent_id"],
               "order_id": o_in["order_id"], "fills": fills, "fees": fees, "side": direction,
               "qty": qty_in, "avg_entry": round(avg_in, 5), "simulated": True}
        if o_out:
            qty_out = sum(f["qty"] for f in o_out["fills"])
            avg_out = sum(f["qty"] * f["price"] for f in o_out["fills"]) / qty_out
            sign = 1 if direction == "long" else -1
            gross = (avg_out - avg_in) * qty_out * sign
            row.update({"exit_decision_id": d_out["decision_id"], "exit_order_id": o_out["order_id"],
                        "avg_exit": round(avg_out, 5), "pnl_gross": round(gross, 4),
                        "pnl_net": round(gross - fees, 4), "status": "closed"})
        else:
            row.update({"pnl_net": None, "status": "open"})
        ledger.append(row)
        return row

    tA = trade("T1", dA, oA, dAx, oAx, "long")
    tB = trade("T2", dB, oB, dBx, oBx, "long")
    tC = trade("T3", dC, oC, None, None, "short")

    last = bars[-1]
    unreal = round((tC["avg_entry"] - last["close"]) * 20, 4)
    realized = round(tA["pnl_gross"] + tB["pnl_gross"], 4)
    fees = tA["fees"] + tB["fees"] + tC["fees"]
    after_cost = round(realized + unreal - fees, 4)

    # outcomes, kept separate from what was knowable
    def outcome_for(d):
        if d["decision_id"] == dA["decision_id"]:
            return {"trade_id": "T1", "result": "win", "pnl_net": tA["pnl_net"], "exit_ts": dAx["ts_knowable"],
                    "note": "Exited at the target zone 16 bars later."}
        if d["decision_id"] == dB["decision_id"]:
            return {"trade_id": "T2", "result": "loss", "pnl_net": tB["pnl_net"], "exit_ts": dBx["ts_knowable"],
                    "note": "Breakout faded; the invalidation was hit 4 bars later."}
        if d["decision_id"] == dC["decision_id"]:
            return {"trade_id": "T3", "result": "open", "unrealized": unreal,
                    "note": "Still open at the end of the sample with a protective stop at 98.95."}
        if d["action"] == "pass":
            return {"hypothetical": True, "note": "See review: hypothetical move after the pass, never in P&L."}
        if d["action"] == "exit":
            return {"note": "Exit fill booked; see the ledger trade."}
        if d["decision_id"] == dR["decision_id"]:
            return {"note": "Refused by the gross-exposure limit; never sent to the broker."}
        return None

    for d in decisions:
        if d["action"] != "hold":
            d["outcome"] = outcome_for(d)

    # [v2] refusal checks per decision (ids from strategies/RULES.md section 4;
    # passed=True means not blocked). Hand-placed sample values, not strategy output.
    def chk(cid, passed, detail):
        return {"id": cid, "passed": passed, "detail": detail}
    base_ok = [chk("NO_BARS", True, "closed bars available"), chk("ORDER_WORKING", True, "no entry order working"),
               chk("OUTSIDE_SESSION", True, "inside fixture session hours"), chk("NEAR_CLOSE", True, "not near close")]
    pass_fail = {
        "low_volume_cross": [chk("NO_SIGNAL", False, "cross on volume below the 20-bar median"), chk("WARMUP", True, "EMA warm"),
                             chk("ZERO_SIZE", True, "TEST size 19")],
        "trend_filter_down": [chk("NO_SIGNAL", False, "cross against the higher-timeframe trend"), chk("WARMUP", True, "EMA warm"),
                              chk("ZERO_SIZE", True, "TEST size 19"),
                              chk("MAX_LOSS_WOULD_BREACH", False, "19 x 0.62 + 0.40 cost = $12.18 > $10.00 (TEST VALUE)")],
        "cost_exceeds_edge": [chk("NO_SIGNAL", True, "signal present"), chk("COST_EXCEEDS_EDGE", False, "est. cost >= expected edge"),
                              chk("ZERO_SIZE", True, "TEST size 19")],
    }
    for d in decisions:
        if "refusal_checks" in d:
            continue
        if d["action"] == "pass":
            d["refusal_checks"] = base_ok + pass_fail.get(d["reason_code"], [chk("NO_SIGNAL", False, "no qualifying signal")])
        elif d["action"] == "hold":
            d["refusal_checks"] = base_ok[:1] + [chk("NO_SIGNAL", False, "no new signal this bar")]
        else:
            d["refusal_checks"] = base_ok + [chk("NO_SIGNAL", True, "signal present"), chk("NO_STOP", True, "stop price set"),
                                             chk("MAX_LOSS_WOULD_BREACH", True, "within $10.00 max loss (TEST VALUE)")]

    audit.sort(key=lambda e: e["ts"])
    now = datetime.now(timezone.utc)
    session = {
        "mode": "REPLAY (OFFLINE, SIMULATED)", "armed": True, "session_id": "sample-ui-dev",
        # Like session.py: expiry is on the replay (simulated) clock.
        "expires_utc": (datetime.strptime(last["ts_close"], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "symbol": SYMBOL, "tradingview_symbol": "AMEX:SPY", "strategy": "ema", "data_label": "SYNTHETIC BARS",
        "replay_clock_utc": last["ts_close"],
        "controls": {"paused": False, "stopped": False, "flat_confirmed": False},
        "exposure": {"position_qty": -20, "avg_price": tC["avg_entry"], "working_orders": [stop_order],
                     "gross_including_working": round(20 * last["close"], 2)},
        "protective_orders": [stop_order],
        "pnl": {"realized": realized, "unrealized": unreal, "fees": fees, "after_cost": after_cost},
        "limits": {"per_trade_notional": 2000.0, "max_loss_per_trade": 10.0, "daily_loss": 30.0, "gross_exposure": 2000.0,
                   "label": "TEST VALUES (Matthew sets real size and limits)"},
        "broker": {"name": "FakeBroker (offline, in-process)", "external": False},
        # [v2] CONTRACT fields, shaped like session.py session_state()
        "phase": "ARMED", "badge": "SIMULATION: ARMED",
        "external_broker_badge": "EXTERNAL BROKER: NONE (offline in-process fake broker)",
        "bars_total": len(bars), "bars_done": len(bars), "play_rate_bars_per_sec": 4.0,
        "preflight": [{"check": "data", "ok": True, "detail": "sample replay bars (SYNTHETIC BARS)"},
                      {"check": "broker reconciled", "ok": True, "detail": "FakeBroker (offline, in-process); alarms: 0"},
                      {"check": "limits loaded", "ok": True, "detail": "max loss/trade $10.00, notional $2000, daily loss $30.00 (TEST VALUES)"},
                      {"check": "stop", "ok": True, "detail": "no Stop active"}],
        "schedule": {"enabled": False, "clock": "SIMULATED", "next_open_utc": None, "next_close_utc": None,
                     "calendar": "fixture", "note": "Off by default. A schedule never clears a Stop."},
        "live_path": {"enabled": False, "reason": "No venue, no personal limits, no explicit enable."},
        "undecided": ["venue / broker", "personal position size and dollar limits",
                      "stop placement policy", "session hours and overnight exposure", "paid data (no purchase)"],
        "updated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "simulated": True,
        "sample_note": "Hand-placed sample for UI development. Not a strategy result.",
    }
    controls = {"paused": False, "stopped": False, "flat_confirmed": False, "entries_enabled": True,
                "schedule_enabled": False, "updated_utc": session["updated_utc"], "simulated": True}
    review = {"generated_utc": session["updated_utc"], "simulated": True,
              "note": "Sample review.json with no overrides: the UI computes the sections."}

    os.makedirs(out_dir, exist_ok=True)

    def wjsonl(name, rows):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")

    def wjson(name, obj):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True)
            fh.write("\n")

    manifest = {"type": "manifest", "source": "synthetic", "symbol": SYMBOL, "timeframe_minutes": 60,
                "label": "SYNTHETIC BARS", "note": "first 70 bars of tvbot/fixtures/normal_bars.jsonl"}
    wjsonl("bars.jsonl", [manifest] + bars)
    wjsonl("decisions.jsonl", decisions)
    wjsonl("ledger.jsonl", ledger)
    wjsonl("audit.jsonl", audit)
    wjsonl("intents.jsonl", intents)
    wjson("session.json", session)
    wjson("controls.json", controls)
    wjson("review.json", review)
    open(os.path.join(out_dir, "control_requests.jsonl"), "a").close()
    return out_dir


def _seq_of(d):
    return int(d["decision_id"][1:4])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(UI_DIR, "sample_state"))
    print(build(os.path.abspath(ap.parse_args().out)))
