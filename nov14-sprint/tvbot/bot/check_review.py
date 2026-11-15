#!/usr/bin/env python3
"""Replay a SAVED model review of a decision packet and check its numbers in code.

This script never calls a model and never touches the paper ledger. It reads
three files (the packet, the bars the reviewer was given, the saved reply),
recomputes the arithmetic with the same rule code the runner uses, and reports
for every number in the reply where that number comes from, or that it cannot
be traced. A review is advice for a person. It cannot approve or trigger a fill.

Standard library only, Python 3.9.

    /usr/bin/python3 nov14-sprint/tvbot/bot/check_review.py

Exit code 0: every check passed and every number was traced.
Exit code 1: a check failed or a number could not be traced.
Exit code 2: a file is missing or unreadable.
"""
import argparse
import hashlib
import html
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TVBOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import rules  # noqa: E402

AUTHORITY = "advisory only; cannot authorize a fill"
VERDICTS = ("agree", "challenge", "cannot_tell")
SKIP_KEYS = ("packet_id", "reviewed_utc", "reviewer_model")
ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
CLOCK = re.compile(r"(?<![\d.:])\d{1,2}:\d{2}(?::\d{2})?Z?")
NUM = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?![\w]|\.\d)")
DEFAULT_PACKET = os.path.join(TVBOT, "packets", "PKT-7069f9b05f2a.json")
DEFAULT_REPLY = os.path.join(TVBOT, "packets", "reviews",
                             "PKT-7069f9b05f2a.claude-sonnet-5-5.reply.txt")


def ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def decimals(text):
    return len(text.split(".")[1]) if "." in text else 0


def walk(node, path=""):
    """Yield (path, leaf) for every string or number in a JSON value."""
    if isinstance(node, dict):
        for k in sorted(node):
            if k in SKIP_KEYS and path == "":
                continue
            for x in walk(node[k], "%s.%s" % (path, k) if path else k):
                yield x
    elif isinstance(node, list):
        for i, v in enumerate(node):
            for x in walk(v, "%s[%d]" % (path, i)):
                yield x
    elif isinstance(node, bool) or node is None:
        return
    else:
        yield path, node


def tokens(leaf):
    """Split one leaf into (kind, text) tokens: iso, date, clock, num."""
    if isinstance(leaf, (int, float)):
        return [("num", repr(leaf))]
    out = []
    rest = leaf
    for kind, rx in (("iso", ISO), ("date", DATE), ("clock", CLOCK)):
        for m in rx.findall(rest):
            out.append((kind, m))
        rest = rx.sub(" ", rest)
    for m in NUM.findall(rest):
        out.append(("num", m))
    return out


def main():
    ap = argparse.ArgumentParser(description="Check a saved packet review in code.")
    ap.add_argument("--packet", default=DEFAULT_PACKET)
    ap.add_argument("--reply", default=DEFAULT_REPLY)
    a = ap.parse_args()
    try:
        packet = json.load(open(a.packet, "r", encoding="utf-8"))
        frozen = packet["frozen"]
        bars_path = os.path.join(os.path.dirname(a.packet), frozen["all_bars_file"])
        raw_bars = open(bars_path, "rb").read()
        raw_reply = open(a.reply, "r", encoding="utf-8").read()
        reply = json.loads(html.unescape(raw_reply))
    except (OSError, ValueError, KeyError) as e:
        print("CANNOT CHECK: %s" % e)
        return 2

    print("RECORDED REPLY. This is a saved reply being replayed, not a live model call.")
    print("packet  %s" % os.path.relpath(a.packet))
    print("reply   %s (sha256 %s)" % (os.path.relpath(a.reply),
                                      hashlib.sha256(raw_reply.encode("utf-8")).hexdigest()[:16]))
    print("reviewer says: model %s, reviewed %s, verdict %s" % (
        reply.get("reviewer_model"), reply.get("reviewed_utc"), reply.get("verdict")))
    print("")

    bars = [json.loads(l) for l in raw_bars.decode("utf-8").splitlines() if l.strip()]
    bars = [b for b in bars if b.get("type") == "bar"]
    by_seq = dict((b["seq"], b) for b in bars)
    dec, inp = frozen["decision"], frozen["inputs_at_decision"]
    plan, port = frozen["forward_plan"], frozen["portfolio_at_decision"]
    order = frozen["proposed_paper_order"]
    params = frozen["rule"]["params"]
    sig = dec["bar_seq"]

    # Recompute the averages with the runner's own rule code.
    ind = rules.new_indicator_state()
    hist, ups, downs = {}, [], []
    for b in bars:
        ind = rules.step_indicators(ind, b["close"], params)
        hist[b["seq"]] = dict(ind)
        s = rules.signals(ind, params)
        if s["cross_up"]:
            ups.append(b["seq"])
        if s["cross_down"]:
            downs.append(b["seq"])
    now, prev = hist[sig], hist[sig - 1]
    code = {"ema_fast": now["fast"], "ema_slow": now["slow"],
            "prev_ema_fast": prev["fast"], "prev_ema_slow": prev["slow"]}
    ratio = port["order_notional_setting"] / inp["close"]
    qty = int(math.floor(ratio))
    notional = qty * inp["close"]
    ready = ts(dec["available_ts"]) + timedelta(seconds=port["latency_seconds"])
    close_ts = ts(by_seq[sig]["ts_close"])
    plan_ok = (ts(plan["earliest_fill_ts"]) != ready) and close_ts >= ready

    checks = []

    def check(name, ok, detail):
        checks.append(ok)
        print("%-4s %s: %s" % ("ok" if ok else "FAIL", name, detail))

    print("Checks made in code")
    check("packet id", reply.get("packet_id") == packet["packet_id"], packet["packet_id"])
    check("authority line", reply.get("authority") == AUTHORITY, repr(reply.get("authority")))
    check("verdict is one of the allowed words", reply.get("verdict") in VERDICTS,
          repr(reply.get("verdict")))
    check("bars file is the one the packet names",
          hashlib.sha256(raw_bars).hexdigest() == frozen["all_bars_sha256"],
          "sha256 %s" % hashlib.sha256(raw_bars).hexdigest()[:16])

    # What code finds for each line of arithmetic, to compare with the reply's own flag.
    facts = [
        ("ema_fast", "bar before", abs(code["prev_ema_fast"] - inp["prev_ema_fast"]) < 1e-6,
         "prev_ema_fast"),
        ("ema_fast", "", abs(code["ema_fast"] - inp["ema_fast"]) < 1e-6, "ema_fast"),
        ("ema_slow", "bar before", abs(code["prev_ema_slow"] - inp["prev_ema_slow"]) < 1e-6,
         "prev_ema_slow"),
        ("ema_slow", "", abs(code["ema_slow"] - inp["ema_slow"]) < 1e-6, "ema_slow"),
        ("cross_up", "", now["fast"] > now["slow"] and prev["fast"] <= prev["slow"], None),
        ("bars_since_reset", "", len(bars) == inp["bars_since_reset"]
         and inp["bars_since_reset"] >= inp["warmup_bars"], None),
        ("qty = floor", "", qty == order["qty"], None),
        ("qty * close", "", abs(notional - order["notional_at_signal_close"]) < 1e-6
         and notional <= plan["risk_limits"]["max_position_notional"]
         and qty <= plan["risk_limits"]["max_qty"], None),
        ("decision_ready_ts =", "", iso(ready) == dec["decision_ready_ts"], None),
        ("earliest_fill", "", plan_ok, None),
    ]
    for row in reply.get("arithmetic", []):
        item = row.get("item", "")
        hit = None
        for key, extra, ok, field in facts:
            if (item.startswith(key) or (key == "earliest_fill" and key in item)) \
                    and (extra in item if extra else True):
                hit = (ok, field)
                break
        if hit is None:
            check("arithmetic row", False, "no code check exists for: %s" % item[:70])
            continue
        ok, field = hit
        detail = "reply says match=%s, code finds %s" % (row.get("match"), ok)
        good = (row.get("match") is ok)
        if field is not None:
            pv, rv = row.get("packet_value"), row.get("recomputed_value")
            num_ok = (isinstance(pv, (int, float)) and isinstance(rv, (int, float))
                      and abs(pv - inp[field]) < 1e-9 and abs(rv - code[field]) < 1e-6)
            good = good and num_ok
            detail += "; packet %s, reply recomputed %s, code recomputed %.6f" % (
                inp[field], rv, code[field])
        check("row '%s'" % item[:44], good, detail)
    check("forward-plan mismatch reported by the reviewer", not plan_ok,
          "packet earliest_fill_ts %s equals the ready time %s and is not a bar open; bar %d "
          "closes at %s, before the ready time, so a bar opening then cannot be the fill bar"
          % (plan["earliest_fill_ts"], iso(ready), sig, by_seq[sig]["ts_close"]))
    if reply.get("live_or_recorded") == "recorded":
        print("note the reply's own live_or_recorded field says 'recorded'. The reviewer wrote "
              "that itself during a live call; the label on this replay comes from this script.")

    # Where every number in the reply comes from.
    known_num, known_time = [], set()
    for path, leaf in walk(frozen):
        for kind, text in tokens(leaf):
            if kind == "num":
                known_num.append((float(text), "packet %s" % path))
            elif kind == "iso":
                known_time.add(text)
    derived = [
        (code["ema_fast"], "fast average at the signal bar, recomputed here"),
        (code["ema_slow"], "slow average at the signal bar, recomputed here"),
        (code["prev_ema_fast"], "fast average one bar earlier, recomputed here"),
        (code["prev_ema_slow"], "slow average one bar earlier, recomputed here"),
        (now["fast"] - now["slow"], "fast minus slow at the signal bar, recomputed here"),
        (prev["fast"] - prev["slow"], "fast minus slow one bar earlier, recomputed here"),
        (ratio, "order size setting divided by the close, recomputed here"),
        (qty, "whole shares, recomputed here"),
        (notional, "shares times close, recomputed here"),
        ((plan["risk_limits"]["max_position_notional"] / qty / inp["close"] - 1) * 100,
         "percent rise that would breach the position limit, recomputed here"),
        (len(bars), "number of bars in the file"),
        (len(frozen.get("recent_closed_bars", [])), "number of recent bars listed in the packet"),
        (plan["earliest_fill_seq"] + 1,
         "one past the packet's earliest_fill_seq (the reviewer's inference about a withheld bar)"),
        (max(sum(1 for b in bars if b["ts_open"][:10] == d)
             for d in set(b["ts_open"][:10] for b in bars)), "most bars in one day in the file"),
    ]
    for s in ups:
        derived.append((s, "a bar where the recomputed fast average crossed above the slow one"))
    for s in downs:
        derived.append((s, "a bar where the recomputed fast average crossed below the slow one"))
    for back in (1, 2, 3, 4, 5):
        if sig - back in by_seq:
            c0 = by_seq[sig - back]["close"]
            derived.append((inp["close"] - c0, "close of bar %d minus close of bar %d"
                            % (sig, sig - back)))
            derived.append(((inp["close"] - c0) / c0 * 100, "percent change in close from bar %d "
                            "to bar %d" % (sig - back, sig)))
    for q in sorted(by_seq):
        if q - 1 in by_seq and by_seq[q]["ts_open"] != by_seq[q - 1]["ts_close"]:
            derived.append((by_seq[q]["open"] - by_seq[q - 1]["close"],
                            "open of bar %d minus close of bar %d (a session gap)" % (q, q - 1)))
    bar_num = []
    for b in bars:
        for k in ("close", "open", "high", "low", "seq"):
            bar_num.append((float(b[k]), "bars file, %s of bar %d" % (k, b["seq"])))
        for k in ("ts_open", "ts_close", "delivered_ts"):
            known_time.add(b[k])
    known_time.add(iso(ready))
    inferred_time = {iso(close_ts + timedelta(hours=1)):
                     "one bar length after the signal bar's close (reviewer's inference)"}

    print("")
    print("Where each number in the reply comes from")
    print("(small whole numbers can match a source by chance; the checks above are the test)")
    seen, untraced, counts = set(), [], {"packet": 0, "recomputed": 0, "bars": 0, "time": 0}
    for path, leaf in walk(reply):
        for kind, text in tokens(leaf):
            if (kind, text) in seen:
                continue
            seen.add((kind, text))
            src = None
            if kind == "iso":
                src = ("time in the packet or bars file" if text in known_time
                       else inferred_time.get(text))
                bucket = "time"
            elif kind == "date":
                src = "date in the bars file" if any(t.startswith(text) for t in known_time) else None
                bucket = "time"
            elif kind == "clock":
                core = text.rstrip("Z")
                pool = list(known_time) + list(inferred_time)
                if any(t[11:11 + len(core)] == core for t in pool):
                    src = "time of day in the packet, bars file or one bar later"
                bucket = "time"
            else:
                # Exact matches first, in every source. A rounded match is accepted only
                # against a value recomputed here, and is labelled as rounded.
                v, tol = float(text), 0.5 * 10 ** (-decimals(text)) + 1e-9
                for pool, bucket, slack, tag in ((known_num, "packet", 1e-9, ""),
                                                 (derived, "recomputed", 1e-9, ""),
                                                 (bar_num, "bars", 1e-9, ""),
                                                 (derived, "recomputed", tol, " (rounded)")):
                    for kv, label in pool:
                        if abs(v - kv) <= slack:
                            src = label + tag
                            break
                    if src:
                        break
            if src is None:
                untraced.append((text, path))
                print("  NOT TRACED  %-22s first seen at %s" % (text, path))
            else:
                counts[bucket] += 1
                print("  %-22s %s" % (text, src))
    print("")
    total = len(seen)
    print("numbers and times in the reply: %d distinct; %d traced (%d packet, %d recomputed, "
          "%d bars file, %d times); %d not traced"
          % (total, total - len(untraced), counts["packet"], counts["recomputed"],
             counts["bars"], counts["time"], len(untraced)))
    ok = all(checks) and not untraced
    print("RESULT: %s. %d of %d code checks passed. This review is advice only. It cannot "
          "approve, change or trigger any order." % ("PASS" if ok else "FAIL",
                                                     sum(1 for c in checks if c), len(checks)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
