"""Score entries from a frozen desk on strictly subsequent same-session SPY bars.

The output is pooled statistics, with no raw bar prices, quotes, or individual forecasts.
This is an entry-signal diagnostic. One slot is a fixed exit horizon, not strategy P&L.
"""
import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sample import prepare

NON_ENTER = {"pass", "hold", "exit"}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def describe(records):
    active = [r for r in records if r["entered"]]
    net = [r["gross"] - r["cost"] for r in active]
    totals = defaultdict(float)
    peak = current = drawdown = 0.0
    for row in records:
        if row["entered"]:
            current += row["gross"] - row["cost"]
        peak = max(peak, current)
        drawdown = max(drawdown, peak - current)
        totals[row["day"]] = current
    return dict(slots=len(records), entered=len(active), abstained=len(records)-len(active),
                wins=sum(x>0 for x in net), gross=round(sum(r["gross"] for r in active),4),
                modeled_cost=round(sum(r["cost"] for r in active),4), net=round(sum(net),4),
                double_cost_net=round(sum(r["gross"]-2*r["cost"] for r in active),4),
                max_drawdown=round(drawdown,4), cumulative_by_day={k: round(v,4) for k,v in totals.items()},
                count_by_reason=dict(Counter(r["reason"] for r in records)))

def study(desk, archive, baseline_only, shares=1, cases=None):
    sys.path.insert(0,str(desk.resolve()))
    from strategies.registry import STRATEGIES
    counts,bars,slots=prepare(archive)
    rules = {"ema": STRATEGIES["ema"], "cash":STRATEGIES["cash"]}
    if not baseline_only:
        from strategies.challenger import decide
        rules["challenger"] = decide
    cfg = {"fixed_qty":shares,"session_tz":"America/New_York","session_close":"16:00"}
    # This intentionally scores fresh entries only. Position management is outside this one-slot diagnostic.
    records = defaultdict(list)
    break_evens=[]
    for i in range(len(bars)):
        current=bars[i]
        eligible = (slots[i]["day"] >= counts["holdout_start"] and i+1 < len(bars) and
                    slots[i+1]["day"]==slots[i]["day"])
        decisions = {}
        for name, choose in rules.items():
            config = dict(cfg, now=current["ts_close"])
            if name == "challenger":
                # The v1 rule sizes its cost hurdle from a notional, even with fixed_qty present.
                # Use the selected count times the last known price for the same reference quantity.
                config["test_size"] = {"order_notional": shares*current["close"], "label": "fixed-reference historical study"}
            decision=choose(bars[:i+1],0,config)
            if decision["action"] in {"enter_long","enter_short"} and decision["qty"] != shares:
                raise ValueError("Signal and markout quantity mismatch")
            ts = decision["ts_knowable"]
            if ts < current["ts_close"]:
                raise ValueError("Forecast claims knowledge before its bar closed")
            decisions[name]=decision
        if not eligible:
            continue
        later=slots[i+1]
        entry,exit_price=later["entry"],later["exit"]
        # From the precommitted desk stress, one share, assumed $1 + 3 bps on EACH side.
        cost=2*max(1,0.005*shares)+shares*(entry+exit_price)*0.0003
        gross=shares*(exit_price-entry)
        break_evens.append(cost)
        for name,decision in decisions.items():
            if decision["ts_knowable"] >= later["entry_ts"]:
                raise ValueError("Decision used information at or after modeled entry")
            action=decision["action"]
            if action not in NON_ENTER | {"enter_long","enter_short"}:
                raise ValueError("Unexpected action: "+str(action))
            entered=action in {"enter_long","enter_short"}
            direction = -1 if action=="enter_short" else 1
            records[name].append(dict(day=later["day"],entered=entered,reason=decision["reason_code"],
                                      gross=direction*gross,cost=cost))
        records["unconditional_long"].append(dict(day=later["day"],entered=True,reason="ALL_WINDOWS",
                                                   gross=gross,cost=cost))
        if cases is not None and "challenger" in decisions:
            d=decisions["challenger"]
            costs=d["cost_view"]
            ind=d["indicators"]
            # Coarse derived indicators + quarter-dollar markouts, never underlying OHLC/V or order prices.
            def quarters(v):
                return round(v*4)/4
            direction=-1 if d["action"]=="enter_short" else 1
            entered=d["action"] in ("enter_long","enter_short")
            cases.append({"decision":current["ts_close"],"entry":later["entry_ts"],"exit":bars[i+1]["ts_close"],
                          "action":d["action"],"reason":d["reason_code"],"ema_reason":decisions["ema"]["reason_code"],
                          "trend":next(x["passed"] for x in d["refusal_checks"] if x["id"]=="TREND"),
                          "slope":round(ind["slope_bps_per_bar"],1),"vol":round(ind["atr_bps"]),
                          "cost":round(costs["round_trip_bps"]),"move":round(costs["expected_move_bps"],1),
                          "qty":shares,"mark":quarters(direction*gross-cost) if entered else 0,
                          "stress":quarters(direction*gross-2*cost) if entered else 0,
                          "if_long":quarters(gross-cost),"if_long_stress":quarters(gross-2*cost)})

    return dict(quality=counts, reference_shares=shares, score="Fixed shares per entry signal; next same-session slot, one-minute delayed entry, exit at its close.",
                hypothetical_cost="1 bps half spread + 2 bps slippage + $1 commission EACH side; doubled includes all three terms.",
                reference_commission="Stress assumption for comparability; not a verified account fee.",
                eligible_slots=len(break_evens), median_modeled_round_trip_cost=round(statistics.median(break_evens),4),
                results={name:describe(v) for name,v in records.items()},
                rule_hashes={k:sha(desk/'strategies'/v) for k,v in
                             ([('ema_engine','engine.py'),('registry','registry.py')]+([] if baseline_only else [('challenger','challenger.py')]))})

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("desk",type=Path)
    p.add_argument("archive",type=Path)
    p.add_argument("--baseline-only",action="store_true")
    p.add_argument("--reference-shares",type=int,choices=(1,2),default=1)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--cases-out",type=Path)
    args=p.parse_args()
    cases=[] if args.cases_out else None
    evidence=study(args.desk,args.archive,args.baseline_only,args.reference_shares,cases)
    if args.cases_out:
        args.cases_out.write_text(json.dumps(cases,indent=2)+"\n")
    args.out.write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8")
    for name,v in evidence["results"].items():
        print(f"{name}: {v['entered']} signals across {v['slots']} opportunities; net {v['net']:.2f}, stress {v['double_cost_net']:.2f}")
