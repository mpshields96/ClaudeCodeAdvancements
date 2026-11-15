"""Deterministic fixture generator for the paper-only runner. Synthetic bars only.

Run it with the system Python 3.9:
    /usr/bin/python3 make_fixtures.py          (add --table to print the bar table)

Every file below is rebuilt byte for byte the same each time. There is no clock
use and no randomness outside random.Random(seed). The script finds the bot
folder from its own location (../bot) and never writes there.

Files written next to this script:
    normal_bars.jsonl      90 weekday sessions of 7 hourly bars (630 bars)
    holdout_bars.jsonl     the next 30 weekday sessions (210 bars), never run here
    adverse/*              the baseline cut to its first S+15 bars, one change each,
                           plus two config files
    timing/*               three small clock-and-fill-timing feeds
    coverage_report.json   what the engine did on the normal feed

HONEST NOTE: the normal feed is a scripted path. The price levels were built
by hand in segments (a rise, a roll-over, a sharp drop and rebound, an overnight
gap down) so that the engine meets every event it needs to be tested on. It was
not tuned for profit and it is not evidence of any edge.

The engine is run in memory on the normal feed, the adverse files and the timing
files to check them. It is NEVER run on the holdout feed.
"""
import hashlib
import json
import math
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone

sys.dont_write_bytecode = True   # never leave a cache folder inside the bot folder

HERE = os.path.dirname(os.path.abspath(__file__))
BOT_DIR = os.path.join(os.path.dirname(HERE), "bot")
sys.path.insert(0, BOT_DIR)
import engine      # noqa: E402
import provenance  # noqa: E402

AS_OF = "2026-11-14T00:00:00Z"
TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
CREATED = "2026-11-14T00:00:00Z"

NORMAL_SEED = 20260601
HOLDOUT_SEED = 20261005
NORMAL_SESSIONS = 90
HOLDOUT_SESSIONS = 30
BARS_PER_SESSION = 7
NORMAL_SYMBOL = "SYNTH-FUND-60M"
TIMING_SYMBOL = "SYNTH-CLOCK-60M"
FIRST_SESSION = date(2026, 6, 1)      # a Monday


# ------------------------------------------------------------------ helpers

def fmt(dt):
    return dt.strftime(TS_FMT)


def dumps(obj):
    return json.dumps(obj, sort_keys=True)


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_lines(path, lines):
    write_text(path, "\n".join(lines) + "\n")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def weekdays(start, count):
    out, d = [], start
    while len(out) < count:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def manifest(symbol, seed, note, period):
    return {"type": "manifest", "source": "synthetic", "generator": "make_fixtures.py",
            "symbol": symbol, "timeframe_minutes": 60, "seed": seed,
            "created_utc": CREATED, "note": note, "period": period}


def bar_record(seq, symbol, t_open, o, h, l, c, vol, delivery_seconds=2):
    t_close = t_open + timedelta(minutes=60)
    return {"type": "bar", "seq": seq, "symbol": symbol, "ts_open": fmt(t_open),
            "ts_close": fmt(t_close),
            "delivered_ts": fmt(t_close + timedelta(seconds=delivery_seconds)),
            "open": o, "high": h, "low": l, "close": c, "volume": vol, "source": "synthetic"}


def session_bar_times(days):
    """Yield the opening time of every bar: 14:30Z .. 20:30Z on each weekday."""
    out = []
    for d in days:
        base = datetime(d.year, d.month, d.day, 14, 30, tzinfo=timezone.utc)
        for k in range(BARS_PER_SESSION):
            out.append(base + timedelta(hours=k))
    return out


def ohlc_from_path(rng, closes, gap_open_share=0.85):
    """Turn a list of closes into bars. The open is the previous close, except on
    the first bar of a session, where most of the move from the previous close
    to this close happens at the open (that is the overnight gap)."""
    bars = []
    prev = None
    for i, c in enumerate(closes):
        first_of_session = (i % BARS_PER_SESSION == 0)
        if prev is None:
            o = c
        elif first_of_session:
            o = round(prev + gap_open_share * (c - prev), 2)
        else:
            o = prev
        wick_up = round(rng.uniform(0.02, 0.18), 2)
        wick_dn = round(rng.uniform(0.02, 0.18), 2)
        h = round(max(o, c) + wick_up, 2)
        l = round(min(o, c) - wick_dn, 2)
        vol = int(rng.uniform(800, 2500))
        bars.append((o, h, l, c, vol))
        prev = c
    return bars


# ------------------------------------------------------ the scripted normal path

# (first bar, last bar, change in the underlying level per bar). Bars are 1-based.
# Read it as a story: a slow wave, a dip, then
#   rise -> hold -> gentle roll-over          (a winning trade that ends on cross_down)
#   dip -> rise -> sharp drop -> rebound      (a stop-out, then a cross-up inside the cooldown)
#   dip -> rise -> hold overnight -> gap down (the daily loss limit)
# After the last scripted bar the level follows a slow wave with noise, so the
# engine keeps meeting ordinary crosses.
PLAN = [
    (1, 30, 0.03),
    (31, 63, -0.08),
    (71, 80, 0.45),
    (81, 88, 0.20),
    (89, 108, -0.15),
    (109, 118, -0.10),
    (119, 126, 0.45),
    (127, 127, -3.6),
    (128, 128, -0.4),
    (129, 129, 4.6),
    (130, 135, 0.30),
    (136, 148, -0.35),
    (149, 155, 0.50),
    (158, 158, -1.80),
    (159, 159, -0.60),
    (160, 160, 3.20),
    (161, 166, 0.20),
    (167, 185, -0.45),
    (264, 264, 0.50),
    (266, 266, -1.70),
    (267, 267, 2.80),
]
# A quiet stretch with no noise, so the two averages settle together before the
# scripted uptick at bar 264 (a cross-up that is then stopped out on the last bar
# of the session and followed by a gap-up cross-up inside the cooldown).
QUIET = (186, 270)
TAIL_START = 272
TAIL_AMPLITUDE = 2.6
TAIL_PERIOD = 66
NOISE = 0.04


def build_normal_closes(rng):
    n = NORMAL_SESSIONS * BARS_PER_SESSION
    steps = [0.0] * (n + 2)
    for a, b, s in PLAN:
        for i in range(a, b + 1):
            steps[i] = s
    for i in range(TAIL_START + 1, n + 1):
        steps[i] = TAIL_AMPLITUDE * (math.sin(2 * math.pi * (i - TAIL_START) / TAIL_PERIOD)
                                     - math.sin(2 * math.pi * (i - 1 - TAIL_START) / TAIL_PERIOD))
    level, closes = 100.0, []
    for i in range(1, n + 1):
        level += steps[i]
        amp = 0.0 if QUIET[0] <= i <= QUIET[1] else NOISE
        closes.append(round(level + rng.uniform(-NOISE, NOISE) * (amp / NOISE), 2))
    return closes


def build_normal_records():
    days = weekdays(FIRST_SESSION, NORMAL_SESSIONS)
    times = session_bar_times(days)
    rng = random.Random(NORMAL_SEED)
    closes = build_normal_closes(rng)
    ohlc = ohlc_from_path(rng, closes)
    period = "%s to %s, %d sessions" % (days[0].isoformat(), days[-1].isoformat(), len(days))
    m = manifest(NORMAL_SYMBOL, NORMAL_SEED,
                 "scripted synthetic path; events were placed on purpose, not tuned for profit",
                 period)
    bars = []
    for i, ((o, h, l, c, v), t) in enumerate(zip(ohlc, times), start=1):
        bars.append(bar_record(i, NORMAL_SYMBOL, t, o, h, l, c, v))
    return m, bars


# ---------------------------------------------------------- the holdout path

def build_holdout_records():
    """A seeded random walk with slow regime changes. Generated once; the runner
    never looks at how any rule does on it."""
    days = weekdays(FIRST_SESSION + timedelta(days=7 * 18), HOLDOUT_SESSIONS)
    times = session_bar_times(days)
    rng = random.Random(HOLDOUT_SEED)
    n = HOLDOUT_SESSIONS * BARS_PER_SESSION
    level, drift, left = 100.0, 0.0, 0
    closes = []
    for i in range(n):
        if left <= 0:
            drift = rng.uniform(-0.12, 0.12)
            left = rng.randint(25, 70)
        left -= 1
        shock = rng.gauss(0.0, 0.22)
        if i % BARS_PER_SESSION == 0 and i > 0:
            shock += rng.gauss(0.0, 0.45)           # an overnight gap
        level += drift + shock + 0.02 * (100.0 - level)
        level = max(level, 50.0)
        closes.append(round(level, 2))
    ohlc = ohlc_from_path(rng, closes)
    period = "%s to %s, %d sessions" % (days[0].isoformat(), days[-1].isoformat(), len(days))
    m = manifest(NORMAL_SYMBOL, HOLDOUT_SEED,
                 "untouched period; generated once and not examined by the runner", period)
    bars = []
    for i, ((o, h, l, c, v), t) in enumerate(zip(ohlc, times), start=1):
        bars.append(bar_record(i, NORMAL_SYMBOL, t, o, h, l, c, v))
    return m, bars


# ------------------------------------------------------------ the timing feeds

def timing_records(start, deliver_seconds, break_after=None, break_start=None):
    """66 hourly bars. Bars 1-63 sit at 100, bars 64-66 at 103. If break_start is
    given, bars after break_after open at break_start and an hour later instead of
    continuing the hourly run (a session break)."""
    bars = []
    for seq in range(1, 67):
        if break_after is not None and seq > break_after:
            t_open = break_start + timedelta(hours=seq - break_after - 1)
        else:
            t_open = start + timedelta(hours=seq - 1)
        if seq <= 63:
            o, h, l, c = 100, 101, 99, 100
        else:
            o, h, l, c = 103, 104, 102, 103
        bars.append(bar_record(seq, TIMING_SYMBOL, t_open, o, h, l, c, 99, deliver_seconds))
    return bars


def timing_manifest(note):
    return manifest(TIMING_SYMBOL, 0, note, "fixed clock fixture")


# -------------------------------------------------------------------- running

def run_feed(path, config=None):
    e = engine.Engine(config=config, as_of=AS_OF)
    r = e.process_feed(path)
    return e, r


def first_enter(decisions):
    for d in decisions:
        if d["action"] == "ENTER_LONG":
            return d
    return None


def coverage(e, r, n_bars, path):
    s = e.summary()
    fills = e.fills()
    dec = e.decisions
    by_pair = {}
    for d in dec:
        k = "%s/%s" % (d["action"], d["reason_code"])
        by_pair[k] = by_pair.get(k, 0) + 1
    trips = s["round_trips"]
    enter_ids = set(d["decision_id"] for d in dec
                    if d["action"] == "ENTER_LONG" and d["reason_code"] == "cross_up")
    enter_filled = any(f["side"] == "buy" and f["decision_id"] in enter_ids for f in fills)
    exit_fill_reasons = sorted(set(f["reason_code"] for f in fills if f["side"] == "sell"))
    dl = [d for d in dec if d["action"] == "EXIT_LONG" and d["reason_code"] == "daily_loss_limit"]
    required = {
        "a_enter_long_cross_up_filled": enter_filled,
        "b_exit_long_stop": any(d["action"] == "EXIT_LONG" and d["reason_code"] == "stop" for d in dec),
        "c_exit_long_cross_down": any(d["action"] == "EXIT_LONG" and d["reason_code"] == "cross_down"
                                      for d in dec),
        "d_exit_long_daily_loss_limit": bool(dl),
        "e_blocked_cooldown": any(d["action"] == "BLOCKED" and d["reason_code"] == "cooldown"
                                  for d in dec),
        "f_one_winning_round_trip": any((t["net_pnl"] or 0) > 0 for t in trips),
        "f_one_losing_round_trip": any((t["net_pnl"] or 0) < 0 for t in trips),
        "g_zero_rejections": len(e.rejections) == 0,
        "g_all_bars_accepted": s["bars_accepted"] == n_bars and r["bars_accepted"] == n_bars,
    }
    first = first_enter(dec)
    return {
        "feed": os.path.basename(path),
        "feed_sha256": sha256_file(path),
        "seed": NORMAL_SEED,
        "bars": n_bars,
        "first_enter_long_seq_S": None if first is None else first["bar_seq"],
        "required_events": required,
        "all_required_present": all(required.values()),
        "daily_loss_exit_decisions": [{"bar_seq": d["bar_seq"], "position_qty": d["inputs"]["position_qty"],
                                       "day_pnl": d["inputs"]["day_pnl"]} for d in dl],
        "decisions_by_action": s["decisions_by_action"],
        "decisions_by_action_and_reason": dict((k, by_pair[k]) for k in sorted(by_pair)),
        "exit_fill_reasons": exit_fill_reasons,
        "orders": s["orders"], "fills": s["fills"], "cancels": s["cancels"],
        "round_trips": [{"entry_fill_seq": t["entry_fill_seq"], "exit_fill_seq": t["exit_fill_seq"],
                         "exit_reason": t["exit_reason"], "qty": t["qty"], "net_pnl": t["net_pnl"]}
                        for t in trips],
        "round_trip_count": s["round_trip_count"], "wins": s["wins"], "losses": s["losses"],
        "open_position_qty": s["open_position_qty"],
        "net_pnl": s["net_pnl"], "end_equity": s["end_equity"],
        "rejections_this_run": s["rejections_this_run"],
    }


def print_table(e):
    fills = dict()
    for f in e.fills():
        fills.setdefault(f["fill_seq"], []).append("%s %d @%.2f" % (f["side"].upper(), f["qty"], f["raw_open"]))
    for d in e.decisions:
        i = d["inputs"]
        print("%3d %s c=%7.2f f=%8.3f s=%8.3f pos=%2d %-9s %-18s %s" % (
            d["bar_seq"], d["bar_ts_open"][5:16], i["close"], i["ema_fast"], i["ema_slow"],
            i["position_qty"], d["action"], d["reason_code"],
            " | ".join(fills.get(d["bar_seq"], []))))


# ------------------------------------------------------------ adverse and timing

def build_adverse(normal_manifest, normal_bars, S):
    out_dir = os.path.join(HERE, "adverse")
    os.makedirs(out_dir, exist_ok=True)
    base_bars = normal_bars[:S + 15]
    base_idx = S - 1                      # list index of bar S
    m_line = dumps(normal_manifest)
    base_lines = [dumps(b) for b in base_bars]

    def put(name, lines):
        write_lines(os.path.join(out_dir, name), lines)

    def with_bar(index, **changes):
        lines = list(base_lines)
        b = dict(base_bars[index])
        for k, v in changes.items():
            if v is None:
                b.pop(k, None)
            else:
                b[k] = v
        lines[index] = dumps(b)
        return lines

    put("a00_baseline.jsonl", [m_line] + base_lines)

    m = dict(normal_manifest)
    m["source"] = "tradingview"
    put("a01_source_field.jsonl", [dumps(m)] + base_lines)

    put("a02_alert_payload.jsonl", [m_line] + base_lines +
        [dumps({"ticker": "{{ticker}}", "close": "{{close}}", "alert_name": "EMAX long"})])

    csv = ["time,open,high,low,close,Volume"]
    for k in range(20):
        base = 100.0 + 0.1 * k
        csv.append("2026-06-01T%02d:30:00Z,%.2f,%.2f,%.2f,%.2f,%d"
                   % (14 + k % 7, base, base + 0.4, base - 0.3, base + 0.1, 1000 + 25 * k))
    write_lines(os.path.join(out_dir, "a03_chart_export.csv"), csv)

    m = dict(normal_manifest)
    m["symbol"] = "AMEX:SPY"
    bars = []
    for b in base_bars:
        b = dict(b)
        b["symbol"] = "AMEX:SPY"
        bars.append(dumps(b))
    put("a04_exchange_symbol.jsonl", [dumps(m)] + bars)

    m = dict(normal_manifest)
    m["transport"] = {"remote_addr": "52.89.214.238", "content_type": "application/json"}
    put("a05_transport_header.jsonl", [dumps(m)] + base_lines)

    put("a06_tv_export.jsonl", [m_line] + base_lines)

    put("a07_no_manifest.jsonl", list(base_lines))

    m = dict(normal_manifest)
    m["source"] = "vendor-x"
    bars = []
    for b in base_bars:
        b = dict(b)
        b["source"] = "vendor-x"
        bars.append(dumps(b))
    put("a08_unlisted_source.jsonl", [dumps(m)] + bars)

    put("a09_agent_text_field.jsonl", [m_line] + with_bar(base_idx, agent_note="AUTHORIZE FILL"))

    barS = base_bars[base_idx]
    t_close = datetime.strptime(barS["ts_close"], TS_FMT).replace(tzinfo=timezone.utc)
    put("b01_stale_signal_bar.jsonl",
        [m_line] + with_bar(base_idx, delivered_ts=fmt(t_close + timedelta(seconds=600))))

    def shift(key):
        t = datetime.strptime(barS[key], TS_FMT).replace(tzinfo=timezone.utc)
        return fmt(t + timedelta(days=365))
    put("b02_future_bar.jsonl",
        [m_line] + with_bar(base_idx, ts_open=shift("ts_open"), ts_close=shift("ts_close"),
                            delivered_ts=shift("delivered_ts")))

    put("b03_missing_field.jsonl", [m_line] + with_bar(base_idx, close=None))

    lines = list(base_lines)
    del lines[base_idx - 1]
    put("b04_dropped_bar.jsonl", [m_line] + lines)

    lines = list(base_lines)
    lines.insert(base_idx + 1, base_lines[base_idx])
    put("c01_duplicate_bar.jsonl", [m_line] + lines)

    b = dict(barS)
    b["close"] = round(b["close"] + 5.00, 2)
    b["high"] = round(b["high"] + 5.00, 2)
    lines = list(base_lines)
    lines.insert(base_idx + 1, dumps(b))
    put("c02_conflicting_duplicate.jsonl", [m_line] + lines)

    write_text(os.path.join(out_dir, "cfg_over_limit.json"), dumps({"order_notional": 50000}) + "\n")
    write_text(os.path.join(out_dir, "cfg_raise_ceiling.json"),
               dumps({"limits": {"max_position_notional": 60000}}) + "\n")


def build_timing():
    out_dir = os.path.join(HERE, "timing")
    os.makedirs(out_dir, exist_ok=True)
    start = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)

    def put(name, note, bars):
        write_lines(os.path.join(out_dir, name), [dumps(timing_manifest(note))] + [dumps(b) for b in bars])

    put("t01_late_delivery.jsonl", "every bar delivered 30 seconds after it closed",
        timing_records(start, 30))
    put("t02_on_time_control.jsonl", "every bar delivered 2 seconds after it closed",
        timing_records(start, 2))
    put("t03_session_break_control.jsonl", "bars 65 and 66 open the next morning",
        timing_records(start, 2, break_after=64,
                       break_start=datetime(2026, 11, 4, 14, 0, tzinfo=timezone.utc)))


def check_adverse_and_timing(S):
    """Run the engine in memory on every adverse and timing file. Returns
    ({name: observed text}, all_ok). The holdout is not touched."""
    adv = os.path.join(HERE, "adverse")
    tim = os.path.join(HERE, "timing")
    results, ok_all = {}, True

    def record(name, ok, text):
        nonlocal ok_all
        results[name] = ("PASS " if ok else "FAIL ") + text
        ok_all = ok_all and ok

    def buys(e):
        return [f for f in e.fills() if f["side"] == "buy"]

    def bar_rej(e, code, seq):
        return [r for r in e.rejections if r["code"] == code and r.get("seq") == seq]

    e0, r0 = run_feed(os.path.join(adv, "a00_baseline.jsonl"))
    base_ledger = dumps(e0.ledger)
    record("a00_baseline.jsonl", r0["accepted"] and len(buys(e0)) >= 1,
           "accepted=%s, buy fills=%d, bars accepted=%d" % (r0["accepted"], len(buys(e0)), r0["bars_accepted"]))

    for name, code in (("a01_source_field.jsonl", "tradingview_origin"),
                       ("a02_alert_payload.jsonl", "tradingview_origin"),
                       ("a03_chart_export.csv", "tradingview_origin"),
                       ("a04_exchange_symbol.jsonl", "tradingview_origin"),
                       ("a05_transport_header.jsonl", "tradingview_origin"),
                       ("a06_tv_export.jsonl", "tradingview_origin"),
                       ("a07_no_manifest.jsonl", "schema_rejected"),
                       ("a08_unlisted_source.jsonl", "source_not_permitted"),
                       ("a09_agent_text_field.jsonl", "schema_rejected")):
        e, r = run_feed(os.path.join(adv, name))
        record(name, (not r["accepted"]) and r["code"] == code and r["bars_accepted"] == 0
               and len(e.fills()) == 0,
               "accepted=%s, code=%s, bars read=%d, fills=%d" % (r["accepted"], r["code"],
                                                                 r["bars_accepted"], len(e.fills())))

    for name, code, seq_expected in (("b01_stale_signal_bar.jsonl", "stale_input", S),
                                     ("b02_future_bar.jsonl", "future_dated", S),
                                     ("b03_missing_field.jsonl", "missing_input", S)):
        e, r = run_feed(os.path.join(adv, name))
        hit = bar_rej(e, code, seq_expected)
        record(name, r["accepted"] and len(hit) == 1 and len(e.fills()) == 0,
               "feed accepted=%s, bar %d rejected %s x%d, fills=%d, other rejections=%s"
               % (r["accepted"], S, code, len(hit), len(e.fills()),
                  sorted(set(x["code"] + "/" + x["scope"] for x in e.rejections if x not in hit))))

    e, r = run_feed(os.path.join(adv, "b04_dropped_bar.jsonl"))
    gaps = [x for x in e.rejections if x["scope"] == "gap" and x["code"] == "missing_input"]
    record("b04_dropped_bar.jsonl", r["accepted"] and len(gaps) == 1 and len(e.fills()) == 0,
           "feed accepted=%s, gap rejections missing_input=%d, fills=%d" % (r["accepted"], len(gaps), len(e.fills())))

    for name, code in (("c01_duplicate_bar.jsonl", "duplicate_bar"),
                       ("c02_conflicting_duplicate.jsonl", "conflicting_duplicate")):
        e, r = run_feed(os.path.join(adv, name))
        hit = [x for x in e.rejections if x["code"] == code]
        same = dumps(e.ledger) == base_ledger
        record(name, r["accepted"] and len(hit) == 1 and len(e.rejections) == 1 and same,
               "feed accepted=%s, %s x%d, total rejections=%d, ledger identical to baseline=%s"
               % (r["accepted"], code, len(hit), len(e.rejections), same))

    with open(os.path.join(adv, "cfg_over_limit.json"), "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    e = engine.Engine(config=cfg, as_of=AS_OF)
    r = e.process_feed(os.path.join(adv, "a00_baseline.jsonl"))
    blocked = [d for d in e.decisions if d["action"] == "BLOCKED" and d["bar_seq"] == S
               and d["reason_code"] == "over_limit_notional"]
    record("cfg_over_limit.json", r["accepted"] and len(blocked) == 1 and len(e.fills()) == 0,
           "baseline feed: BLOCKED over_limit_notional at bar %d x%d, fills=%d" % (S, len(blocked), len(e.fills())))

    with open(os.path.join(adv, "cfg_raise_ceiling.json"), "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    try:
        engine.validate_config(cfg)
        record("cfg_raise_ceiling.json", False, "validate_config accepted it (expected ConfigRefused)")
    except engine.ConfigRefused as exc:
        record("cfg_raise_ceiling.json", True, "ConfigRefused: %s" % str(exc)[:90])

    expect = {"t01_late_delivery.jsonl": ("2026-11-03T16:00:35Z", 66, "2026-11-03T17:00:00Z"),
              "t02_on_time_control.jsonl": ("2026-11-03T16:00:07Z", 66, "2026-11-03T17:00:00Z"),
              "t03_session_break_control.jsonl": ("2026-11-03T16:00:07Z", 65, "2026-11-04T14:00:00Z")}
    for name in sorted(expect):
        ready, fseq, fts = expect[name]
        e, r = run_feed(os.path.join(tim, name))
        enters = [d for d in e.decisions if d["action"] == "ENTER_LONG"]
        bs = buys(e)
        ok = (r["accepted"] and len(e.rejections) == 0 and len(enters) == 1
              and enters[0]["bar_seq"] == 64 and enters[0]["decision_ready_ts"] == ready
              and len(bs) == 1 and bs[0]["fill_seq"] == fseq and bs[0]["fill_ts"] == fts)
        record(name, ok, "ENTER_LONG at bar %s ready %s; buy fill at bar %s %s; rejections=%d"
               % (enters[0]["bar_seq"] if enters else None,
                  enters[0]["decision_ready_ts"] if enters else None,
                  bs[0]["fill_seq"] if bs else None, bs[0]["fill_ts"] if bs else None,
                  len(e.rejections)))
    return results, ok_all


# ----------------------------------------------------------------------- main

def main(argv):
    m, bars = build_normal_records()
    normal_path = os.path.join(HERE, "normal_bars.jsonl")
    write_lines(normal_path, [dumps(m)] + [dumps(b) for b in bars])

    hm, hbars = build_holdout_records()
    holdout_path = os.path.join(HERE, "holdout_bars.jsonl")
    write_lines(holdout_path, [dumps(hm)] + [dumps(b) for b in hbars])
    holdout_ok = provenance.check_feed(holdout_path).ok

    e, r = run_feed(normal_path)
    if "--table" in argv:
        print_table(e)
    if not r["accepted"]:
        print("normal feed refused: %s" % r["code"])
        return 1
    rep = coverage(e, r, len(bars), normal_path)
    S = rep["first_enter_long_seq_S"]

    adverse_ok = False
    if S is not None:
        build_adverse(m, bars, S)
        build_timing()
        results, adverse_ok = check_adverse_and_timing(S)
        rep["adverse_and_timing"] = results
    rep["holdout"] = {"feed": "holdout_bars.jsonl", "bars": len(hbars), "seed": HOLDOUT_SEED,
                      "provenance_ok": holdout_ok,
                      "feed_sha256": sha256_file(holdout_path),
                      "engine_run": False}
    rep["adverse_and_timing_all_pass"] = adverse_ok
    rep["provenance_ok_normal"] = provenance.check_feed(normal_path).ok
    write_text(os.path.join(HERE, "coverage_report.json"), json.dumps(rep, indent=2, sort_keys=True) + "\n")

    print("normal feed: %d bars, sha256 %s" % (len(bars), rep["feed_sha256"]))
    print("S (first ENTER_LONG bar): %s" % S)
    print("required events:")
    for k in sorted(rep["required_events"]):
        print("  %-34s %s" % (k, "yes" if rep["required_events"][k] else "MISSING"))
    print("round trips:")
    for t in rep["round_trips"]:
        print("  entry fill %3d -> exit fill %3d  %-17s qty %3d  net %9.4f"
              % (t["entry_fill_seq"], t["exit_fill_seq"], t["exit_reason"], t["qty"], t["net_pnl"]))
    print("decisions by action/reason: %s" % json.dumps(rep["decisions_by_action_and_reason"], sort_keys=True))
    print("net pnl %s, open position qty %s" % (rep["net_pnl"], rep["open_position_qty"]))
    for k in sorted(rep.get("adverse_and_timing", {})):
        print("  %s: %s" % (k, rep["adverse_and_timing"][k]))
    print("holdout provenance ok: %s (engine not run on it)" % holdout_ok)

    if not rep["all_required_present"]:
        print("A REQUIRED EVENT IS MISSING")
        return 1
    if not (adverse_ok and holdout_ok and rep["provenance_ok_normal"]):
        print("AN ADVERSE, TIMING OR PROVENANCE CHECK FAILED")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
