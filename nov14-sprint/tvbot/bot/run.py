#!/usr/bin/env python3
"""Command line for the EMAX paper runner.

Paper only. It reads a feed of bars, records one decision per bar, fills paper
orders at a later bar's open with costs, and writes a ledger. The built-in
feeds are synthetic and are TEST ONLY. Real bars come in one way: a CSV file
Matthew supplies from a source whose terms allow it (the paper command). It
never places an order, opens a network connection, calls a model or reads
anything that came from TradingView.

Commands (run from anywhere; paths default to this lane's own folders):
  replay    run a feed into a state folder and print what happened
  adverse   run every bad input and show that each one is refused
  sweep     reprice the same trades under rising costs
  holdout   spend the untouched period once, with the frozen rule
  explain   print the plain-English reason for decisions
  registry  show or freeze the rule variants tried so far
  packet    publish one decision, blind to later bars, for an outside review
  gate      Matthew's approve-or-pass decision, typed by him in Terminal (paper only)
  paper     run the rule on a real-bar CSV he supplied; needs the gate; fails closed

Exit codes: 0 ok. 1 a check failed (ledger differs from expected, a bad input
was not refused, or net did not fall as costs rose). 2 the feed or config was
refused. 3 unexpected state.

Standard library only, Python 3.9.
"""
import argparse
import contextlib
import copy
import fcntl
import hashlib
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

BOT = os.path.dirname(os.path.abspath(__file__))
if BOT not in sys.path:
    sys.path.insert(0, BOT)

import engine  # noqa: E402
import explain as explain_mod  # noqa: E402
import provenance  # noqa: E402
import real_feed  # noqa: E402
import riskinfo  # noqa: E402
import rules  # noqa: E402

TVBOT = os.path.dirname(BOT)
FIX = os.path.join(TVBOT, "fixtures")
OUT = os.path.join(TVBOT, "out")
PACKET_DIR = os.path.join(TVBOT, "packets")
CHALLENGE_SCHEMA_PATH = os.path.join(TVBOT, "CHALLENGE_SCHEMA.json")
LOCK_DIR = os.path.join(TVBOT, "locks")
LOCK_WAIT_DEFAULT = 30.0
REGISTRY = os.path.join(BOT, "rule_registry.json")
NORMAL_FEED = os.path.join(FIX, "normal_bars.jsonl")
HOLDOUT_FEED = os.path.join(FIX, "holdout_bars.jsonl")
EXPECTED = os.path.join(FIX, "expected_normal_ledger.jsonl")
FIXTURE_CLOCK = "2026-11-14T00:00:00Z"
REAL_DIR = os.path.join(TVBOT, "real")
SOURCE_DEFAULT = os.path.join(REAL_DIR, "source.json")
GATE_PATH = os.path.join(TVBOT, "gate", "paper_gate.json")
PAPER_STATE = os.path.join(OUT, "paper")
NORMAL_STATE = os.path.join(OUT, "normal")
SMALLER_SIZE = os.path.join(TVBOT, "config", "smaller_size.json")
TEST_LABEL = "TEST ONLY: synthetic bars made by a script, not market data."


class Stop(Exception):
    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code = code


def now_utc():
    return datetime.now(timezone.utc).strftime(engine.TS_FMT)


def rel(path):
    """Show a path relative to the folder the command was run from."""
    try:
        r = os.path.relpath(path)
    except ValueError:
        return path
    return path if r.startswith("..") else r


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for ln in fh:
            if ln.strip():
                rows.append(json.loads(ln))
    return rows


def safe_state_dir(path):
    """A state folder must sit inside this lane's out/ folder."""
    os.makedirs(OUT, exist_ok=True)
    real = os.path.realpath(path)
    root = os.path.realpath(OUT)
    if not real.startswith(root + os.sep):
        raise Stop(3, "the state folder must be a subfolder of %s; got %s" % (rel(OUT), path))
    return real


@contextlib.contextmanager
def hold_lock(target, wait=None):
    """One process at a time per state folder (or per registry file).

    The lock is an operating-system file lock on a small file in tvbot/locks/,
    a folder no command here resets or deletes. It is held for the whole
    transaction: the --fresh reset, reading the saved journal, the run and
    every write. A second start waits. If the wait runs out it stops with
    exit code 4 before it has read or changed anything. The lock is released
    by the system if the holding process dies, so a crash cannot leave it stuck.
    """
    wait = LOCK_WAIT_DEFAULT if wait is None else float(wait)
    os.makedirs(LOCK_DIR, exist_ok=True)
    real = os.path.realpath(target)
    name = "%s-%s.lock" % (re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.basename(real))[:40],
                           hashlib.sha256(real.encode("utf-8")).hexdigest()[:12])
    fh = open(os.path.join(LOCK_DIR, name), "a+")
    deadline = time.time() + wait
    said = False
    try:
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.time() >= deadline:
                    raise Stop(4, "BUSY: another run is using %s. This start read nothing and "
                                  "changed nothing. Try again when the other run has finished."
                                  % rel(target))
                if not said:
                    sys.stderr.write("another run is using %s; waiting up to %.0f seconds\n"
                                     % (rel(target), wait))
                    sys.stderr.flush()
                    said = True
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        fh.close()


def fresh(state_dir):
    """Remove only the files this runner writes. Never a folder, never notes."""
    removed = []
    for name in engine.Engine.FILES:
        p = os.path.join(state_dir, name)
        if os.path.isfile(p):
            os.remove(p)
            removed.append(name)
    return removed


def money(x):
    return "%+.2f" % x


def timing_ok(fills):
    """True when every fill used a bar that opened at or after its decision was ready."""
    for f in fills:
        if f["fill_ts"] < f["decision_ready_ts"] or f["fill_seq"] <= f["signal_seq"]:
            return False
    return True


def plan_check(ledger):
    """Compare each order's stated fill plan with what happened.

    Returns (problems, matched, planned). A problem is a plan that named a bar
    expected to open before the decision was ready, or a fill that came before
    the plan allowed. matched counts orders whose planned bar was the bar that
    filled. Order rows written before the plan fields existed are not counted.
    """
    orders = dict((r["order_id"], r) for r in ledger if r["type"] == "order")
    problems, matched, planned = [], 0, 0
    for o in orders.values():
        exp = o.get("earliest_fill_open_expected")
        if exp is not None and exp < o["earliest_fill_ts"]:
            problems.append("order %s plans bar %d, expected to open at %s, before the decision "
                            "is ready at %s" % (o["order_id"], o["earliest_fill_seq"], exp,
                                                o["earliest_fill_ts"]))
    for f in ledger:
        if f["type"] != "fill":
            continue
        o = orders.get(f["order_id"])
        if o is None:
            problems.append("fill %s has no order row" % f["fill_id"])
            continue
        if f["fill_ts"] < o["earliest_fill_ts"] or f["fill_seq"] < o.get("min_fill_seq", 0):
            problems.append("fill %s at bar %d (%s) came before its order allowed"
                            % (f["fill_id"], f["fill_seq"], f["fill_ts"]))
        if "min_fill_seq" in o:
            planned += 1
            if o["earliest_fill_seq"] == f["fill_seq"]:
                matched += 1
    return problems, matched, planned


SWEEP_MULTS = (0, 1, 2, 4, 8)


def cost_sweep(e):
    """Net result of the SAME fills with every cost multiplied. [] when there are no fills.

    Saved in summary.json so the result page can show it beside the net result.
    The same fills and settings always give the same numbers."""
    fills = e.fills()
    if not fills:
        return []
    return [{"mult": m, "net": engine.r6(engine.reprice_net(fills, e.state["last_close"], e.cfg, m))}
            for m in SWEEP_MULTS]


def rebuild_page():
    """Write RESULT.html again from the saved files. Never fatal."""
    try:
        import page as page_mod
        with contextlib.redirect_stdout(io.StringIO()):
            page_mod.main([])
        print("result page     %s (rebuilt)" % rel(os.path.join(TVBOT, "RESULT.html")))
    except Exception as exc:  # the page is a view; a failure here must not hide the run
        print("result page     not rebuilt (%s)" % exc)


def make_engine(a, state_dir=None, config=None, as_of=None, permitted_sources=None):
    params = load_json(a.params) if getattr(a, "params", None) else None
    if config is None and getattr(a, "config", None):
        config = load_json(a.config)
    try:
        return engine.Engine(params=params, config=config, as_of=as_of or a.as_of,
                             state_dir=state_dir, permitted_sources=permitted_sources)
    except engine.ConfigRefused as exc:
        raise Stop(2, "CONFIG REFUSED: %s" % exc)
    except ValueError as exc:
        raise Stop(2, "RULE PARAMETERS REFUSED: %s" % exc)
    except engine.EngineError as exc:
        raise Stop(3, "UNEXPECTED STATE: %s" % exc)


# ------------------------------------------------------------------ report

def print_report(e, res, feed, as_of, variants=None, state_dir=None, label=None):
    s = e.summary()
    print("EMAX paper runner. %s No orders, accounts or network." % (label or TEST_LABEL))
    print("rule            %s%s" % (e.rule_id, "" if variants is None
                                    else "   (rule variants tried so far: %d)" % variants))
    print("feed            %s   sha256 %s" % (rel(feed), sha256_file(feed)[:16]))
    print("clock (as of)   %s" % as_of)
    if not res["accepted"]:
        print("FEED REFUSED    code %s; zero bars were read" % res["code"])
        for r in res["reasons"]:
            print("  - %s" % r)
        return s
    rej = sum(v for k, v in res["bar_results"].items() if k != "accepted")
    print("bars            %d accepted this run, %d rejected %s"
          % (res["bars_accepted"], rej,
             "" if not rej else json.dumps(dict((k, v) for k, v in sorted(res["bar_results"].items())
                                                if k != "accepted"))))
    if res["bars_accepted"] == 0 and res["bar_results"].get("duplicate_bar"):
        print("                this feed was already recorded in this state folder; "
              "nothing new was decided")
    print("decisions       %d on file  %s" % (s["decisions"], json.dumps(s["decisions_by_action"],
                                                                         sort_keys=True)))
    print("ledger          %d orders, %d fills, %d cancels, pending order: %s"
          % (s["orders"], s["fills"], s["cancels"], s["pending_order"] or "none"))
    fills = e.fills()
    if fills:
        print("")
        print("fills: signal bar close, then when that bar was delivered, then when the decision")
        print("was ready, then the fill at the open of a later bar")
        print("  %-4s %4s  %-20s %-20s %-20s %-20s %4s %9s %10s %6s  %s"
              % ("side", "qty", "signal_ts", "delivered", "decision_ready", "fill_ts",
                 "bar", "raw_open", "fill_price", "comm", "reason"))
        for f in fills:
            print("  %-4s %4d  %-20s %-20s %-20s %-20s %4d %9.2f %10.4f %6.2f  %s"
                  % (f["side"], f["qty"], f["signal_ts"], f["available_ts"],
                     f["decision_ready_ts"], f["fill_ts"], f["fill_seq"], f["raw_open"],
                     f["fill_price"], f["commission"], f["reason_code"]))
        print("timing check    every fill used a bar that opened at or after its decision "
              "was ready: %s" % ("yes" if timing_ok(fills) else "NO"))
        problems, matched, planned = plan_check(e.ledger)
        print("plan check      no order planned a fill bar that opens before its decision is "
              "ready: %s; the planned bar was the bar that filled for %d of %d orders"
              % ("yes" if not problems else "NO", matched, planned))
        for prob in problems:
            print("  - %s" % prob)
    if s["round_trips"]:
        print("")
        print("round trips")
        for t in s["round_trips"]:
            print("  in %s  out %s  qty %d  %.2f -> %.2f  %-16s net %s"
                  % (t["entry_fill_ts"], t["exit_fill_ts"], t["qty"], t["entry_raw_open"],
                     t["exit_raw_open"], t["exit_reason"], money(t["net_pnl"] or 0.0)))
    print("")
    print("start cash      %.2f" % s["start_cash"])
    print("end equity      %.2f" % s["end_equity"])
    print("net P&L         %s   (before costs %s, spread and slippage -%.2f, commission -%.2f)"
          % (money(s["net_pnl"]), money(s["gross_pnl_at_raw_opens"]),
             s["spread_and_slippage_cost"], s["commission_cost"]))
    print("round trips     %d (%d won, %d lost); largest fall from a peak %.2f; open position %d"
          % (s["round_trip_count"], s["wins"], s["losses"], s["max_drawdown"],
             s["open_position_qty"]))
    if s["buy_and_hold"]:
        print("buy and hold    %s   (%s)" % (money(s["buy_and_hold"]["net_pnl"]),
                                             s["buy_and_hold"]["note"]))
    print("fill rule       %s" % s["fill_assumption"])
    print("note            %s" % s["data_note"])
    if state_dir:
        print("state folder    %s" % rel(state_dir))
    return s


# ------------------------------------------------------------------ replay

def cmd_replay(a):
    feed = a.feed or NORMAL_FEED
    if not os.path.isfile(feed):
        raise Stop(3, "feed not found: %s" % feed)
    state_dir = safe_state_dir(a.state_dir or os.path.join(OUT, "normal"))
    # One start at a time per state folder. The lock covers the reset, the read
    # of the saved journal, the run and every write.
    with hold_lock(state_dir, getattr(a, "lock_wait", None)):
        return _replay_locked(a, feed, state_dir)


def _replay_locked(a, feed, state_dir):
    os.makedirs(state_dir, exist_ok=True)
    if a.fresh:
        fresh(state_dir)
    params = load_json(a.params) if a.params else None
    try:
        with hold_lock(a.registry, getattr(a, "lock_wait", None)):
            _rid, _new, count = rules.register_variant(a.registry, params, note="replay")
    except ValueError as exc:
        raise Stop(2, "RULE PARAMETERS REFUSED: %s" % exc)
    e = make_engine(a, state_dir=state_dir)
    try:
        res = e.process_feed(feed)
    except engine.EngineError as exc:
        raise Stop(3, "UNEXPECTED STATE: %s" % exc)
    s = print_report(e, res, feed, a.as_of, variants=count, state_dir=state_dir)
    out = dict(s)
    out.update({"feed": os.path.basename(feed), "feed_sha256": sha256_file(feed),
                "as_of": a.as_of, "feed_accepted": res["accepted"], "feed_code": res["code"],
                "feed_reasons": res["reasons"], "bar_results_this_run": res["bar_results"],
                "config": e.cfg, "config_hash": e.cfg_hash, "rule_variants_tried": count,
                "cost_sweep": cost_sweep(e)})
    with open(os.path.join(state_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(os.path.join(state_dir, "decision_packet.md"), "w", encoding="utf-8") as fh:
        fh.write(explain_mod.build_packet(e.decisions, e.rule_id))
    if not res["accepted"]:
        return 2
    if not timing_ok(e.fills()):
        raise Stop(3, "UNEXPECTED STATE: a fill used a price from before its decision was ready")
    if plan_check(e.ledger)[0]:
        raise Stop(3, "UNEXPECTED STATE: an order's fill plan names a bar that opens before "
                      "its decision is ready")
    if os.path.realpath(state_dir) == os.path.realpath(NORMAL_STATE):
        rebuild_page()
    if a.write_expected:
        with open(a.write_expected, "w", encoding="utf-8") as fh:
            for row in e.ledger:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
        print("expected ledger written: %s (%d rows)" % (rel(a.write_expected), len(e.ledger)))
    if a.expect:
        if not os.path.isfile(a.expect):
            raise Stop(3, "expected ledger not found: %s" % a.expect)
        want = read_jsonl(a.expect)
        got = e.ledger
        if want == got:
            print("expected ledger MATCH   %d rows equal %s (sha256 %s)"
                  % (len(got), rel(a.expect), sha256_file(a.expect)[:16]))
        else:
            n = min(len(want), len(got))
            first = next((i for i in range(n) if want[i] != got[i]), n)
            print("expected ledger MISMATCH   expected %d rows, got %d; first difference at row %d"
                  % (len(want), len(got), first + 1))
            return 1
    return 0


# ----------------------------------------------------------------- adverse

def _mem(feed, config=None, as_of=FIXTURE_CLOCK):
    e = engine.Engine(config=config, as_of=as_of)
    return e, e.process_feed(feed)


def cmd_adverse(a):
    with hold_lock(os.path.join(OUT, "adverse_work"), getattr(a, "lock_wait", None)):
        return _adverse_locked(a)


def _adverse_locked(a):
    adv = os.path.join(FIX, "adverse")
    tim = os.path.join(FIX, "timing")
    base = os.path.join(adv, "a00_baseline.jsonl")
    work = safe_state_dir(os.path.join(OUT, "adverse_work"))
    os.makedirs(work, exist_ok=True)
    fresh(work)
    rows = []
    all_fills = []

    def add(group, name, expected, observed, ok):
        rows.append((group, name, expected, observed, bool(ok)))

    def need(path):
        if not os.path.isfile(path):
            raise Stop(3, "fixture missing: %s (run fixtures/make_fixtures.py)" % rel(path))
        return path

    # control: the clean feed does trade, so a refusal below is a real refusal
    eb, rb = _mem(need(base))
    all_fills.extend(eb.fills())
    base_ledger = copy.deepcopy(eb.ledger)
    base_buys = len([f for f in eb.fills() if f["side"] == "buy"])
    add("control", "clean synthetic feed", "accepted, at least one paper buy",
        "%s, %d bars, %d paper buy fill(s)" % ("accepted" if rb["accepted"] else "refused",
                                               rb["bars_accepted"], base_buys),
        rb["accepted"] and base_buys >= 1)

    def refused(group, name, fname, code):
        e, r = _mem(need(os.path.join(adv, fname)))
        ok = (not r["accepted"] and r["code"] == code and r["bars_accepted"] == 0
              and not e.ledger and not e.decisions)
        obs = ("refused (%s), 0 bars read, 0 orders" % r["code"]) if not r["accepted"] else \
            "ACCEPTED %d bars, %d orders" % (r["bars_accepted"], len(e.ledger))
        add(group, name, "whole feed refused: %s" % code, obs, ok)

    g = "TradingView origin"
    refused(g, "source field says tradingview", "a01_source_field.jsonl", "tradingview_origin")
    refused(g, "alert message payload in the feed", "a02_alert_payload.jsonl", "tradingview_origin")
    refused(g, "chart export CSV", "a03_chart_export.csv", "tradingview_origin")
    refused(g, "exchange-prefixed ticker AMEX:SPY", "a04_exchange_symbol.jsonl", "tradingview_origin")
    refused(g, "webhook sender address in a header", "a05_transport_header.jsonl", "tradingview_origin")
    refused(g, "marker only in the file name", "a06_tv_export.jsonl", "tradingview_origin")
    g = "unknown origin"
    refused(g, "no manifest, origin unknown", "a07_no_manifest.jsonl", "schema_rejected")
    refused(g, "source not on the permitted list", "a08_unlisted_source.jsonl", "source_not_permitted")
    refused(g, "extra field carrying agent text", "a09_agent_text_field.jsonl", "schema_rejected")

    def contained(group, name, fname, code, as_of=FIXTURE_CLOCK, feed=None):
        e, r = _mem(feed or need(os.path.join(adv, fname)), as_of=as_of)
        codes = [x["code"] for x in e.rejections]
        ok = r["accepted"] and code in codes and not e.ledger
        add(group, name, "input rejected: %s; no order, no fill" % code,
            "%d rejection(s) %s; %d orders, %d fills"
            % (len(codes), sorted(set(codes)), len([x for x in e.ledger if x["type"] == "order"]),
               len(e.fills())), ok)

    g = "stale, future, missing"
    contained(g, "signal bar delivered 10 minutes late", "b01_stale_signal_bar.jsonl", "stale_input")
    contained(g, "signal bar dated a year ahead", "b02_future_bar.jsonl", "future_dated")
    contained(g, "clean feed, clock set before the data", None, "future_dated",
              as_of="2026-01-01T00:00:00Z", feed=base)
    contained(g, "signal bar has no close", "b03_missing_field.jsonl", "missing_input")
    contained(g, "a bar is missing before the signal", "b04_dropped_bar.jsonl", "missing_input")

    def same_ledger(group, name, fname, code):
        e, r = _mem(need(os.path.join(adv, fname)))
        n = len([x for x in e.rejections if x["code"] == code])
        all_fills.extend(e.fills())
        add(group, name, "one %s; ledger equals the clean run" % code,
            "%d %s; ledger %s the clean run (%d rows)"
            % (n, code, "equals" if e.ledger == base_ledger else "DIFFERS FROM", len(e.ledger)),
            r["accepted"] and n == 1 and e.ledger == base_ledger)

    g = "duplicates"
    same_ledger(g, "signal bar sent twice", "c01_duplicate_bar.jsonl", "duplicate_bar")
    same_ledger(g, "signal bar re-sent with a new price", "c02_conflicting_duplicate.jsonl",
                "conflicting_duplicate")

    # replay twice into one state folder
    def hashes():
        return (sha256_file(os.path.join(work, "ledger.jsonl")),
                sha256_file(os.path.join(work, "decisions.jsonl")))
    e1 = engine.Engine(as_of=FIXTURE_CLOCK, state_dir=work)
    r1 = e1.process_feed(base)
    h1 = hashes()
    e2 = engine.Engine(as_of=FIXTURE_CLOCK, state_dir=work)
    r2 = e2.process_feed(base)
    h2 = hashes()
    buys2 = len([f for f in e2.fills() if f["side"] == "buy"])
    add(g, "whole feed replayed after a restart", "no new decision, order or fill",
        "second run: %d new bars, %d duplicate_bar; ledger and decisions files %s; %d buy fill(s)"
        % (r2["bars_accepted"], r2["bar_results"].get("duplicate_bar", 0),
           "unchanged" if h1 == h2 else "CHANGED", buys2),
        h1 == h2 and r2["bars_accepted"] == 0 and buys2 == base_buys
        and r2["bar_results"].get("duplicate_bar", 0) == r1["bars_accepted"])

    enter = next((d for d in e2.decisions if d["action"] == "ENTER_LONG"), None)
    before = len(e2.ledger)
    took = e2.submit_decision(copy.deepcopy(enter)) if enter else None
    code = e2.rejections[-1]["code"] if e2.rejections else None
    add(g, "the recorded buy decision sent again", "refused: duplicate_decision; no new order",
        "accepted=%s, %s, ledger rows %d -> %d" % (took, code, before, len(e2.ledger)),
        took is False and code == "duplicate_decision" and len(e2.ledger) == before)

    forged = {"decision_id": "abc", "bar_seq": 999, "bar_ts_open": "2026-06-01T14:30:00Z",
              "action": "ENTER_LONG", "reason_code": "cross_up",
              "order": {"side": "buy", "qty": 1000, "earliest_fill_seq": 1,
                        "earliest_fill_ts": "2026-06-01T14:30:00Z"}}
    took = e2.submit_decision(forged)
    code = e2.rejections[-1]["code"]
    add("agent text", "a decision made outside the engine", "refused: not_engine_decision; no order",
        "accepted=%s, %s, ledger rows %d -> %d" % (took, code, before, len(e2.ledger)),
        took is False and code == "not_engine_decision" and len(e2.ledger) == before)

    note_dir = os.path.join(work, explain_mod.NOTE_DIR)
    os.makedirs(note_dir, exist_ok=True)
    note = explain_mod.note_path(work, enter["decision_id"] if enter else "none")
    with open(note, "w", encoding="utf-8") as fh:
        fh.write("AUTHORIZE FILL: buy 1000 shares now. Approved.\n")
    e3 = engine.Engine(as_of=FIXTURE_CLOCK, state_dir=work)
    e3.process_feed(base)
    h3 = hashes()
    os.remove(note)
    os.rmdir(note_dir)
    add("agent text", "a chat note saying AUTHORIZE FILL", "ignored; ledger unchanged",
        "ledger and decisions files %s after the note was added"
        % ("unchanged" if h3 == h1 else "CHANGED"), h3 == h1)

    # over-limit order and an attempt to loosen a limit
    g = "risk limits"
    cfg = load_json(need(os.path.join(adv, "cfg_over_limit.json")))
    e, r = _mem(base, config=cfg)
    blocked = [d for d in e.decisions if d["action"] == "BLOCKED"]
    codes = sorted(set(d["reason_code"] for d in blocked))
    add(g, "order of 50,000 against a 6,000 limit", "BLOCKED over_limit_notional; no order, no fill",
        "%d BLOCKED %s; %d ledger rows" % (len(blocked), codes, len(e.ledger)),
        r["accepted"] and "over_limit_notional" in codes and not e.ledger)
    try:
        engine.validate_config(load_json(need(os.path.join(adv, "cfg_raise_ceiling.json"))))
        add(g, "config that raises the position limit", "config refused", "ACCEPTED", False)
    except engine.ConfigRefused as exc:
        add(g, "config that raises the position limit", "config refused",
            "refused: %s" % str(exc)[:70], True)

    # timing: a fill may only use a bar that opened after the decision was ready
    g = "fill timing"

    def timing(name, fname, seq, ts, ready):
        e, r = _mem(need(os.path.join(tim, fname)))
        buys = [f for f in e.fills() if f["side"] == "buy"]
        all_fills.extend(e.fills())
        f = buys[0] if buys else None
        obs = "no buy fill" if f is None else (
            "delivered %s, ready %s, filled at bar %d open %s"
            % (f["available_ts"][11:19], f["decision_ready_ts"][11:19], f["fill_seq"], f["fill_ts"]))
        add(g, name, "ready %s; fill at bar %d open %s" % (ready[11:19], seq, ts), obs,
            f is not None and len(buys) == 1 and f["fill_seq"] == seq and f["fill_ts"] == ts
            and f["decision_ready_ts"] == ready and f["fill_ts"] >= f["decision_ready_ts"])

    timing("signal bar delivered 30 s late", "t01_late_delivery.jsonl", 66,
           "2026-11-03T17:00:00Z", "2026-11-03T16:00:35Z")
    timing("on-time control (2 s)", "t02_on_time_control.jsonl", 66,
           "2026-11-03T17:00:00Z", "2026-11-03T16:00:07Z")
    timing("session break control", "t03_session_break_control.jsonl", 65,
           "2026-11-04T14:00:00Z", "2026-11-03T16:00:07Z")
    add(g, "every fill in this suite", "no fill before its decision was ready",
        "%d fills checked, %s" % (len(all_fills), "all later" if timing_ok(all_fills)
                                  else "A FILL WAS EARLY"), timing_ok(all_fills) and all_fills)

    # the untouched period can be used once
    reg = os.path.join(work, "registry_check.json")
    if os.path.isfile(reg):
        os.remove(reg)
    rid, _n, _c = rules.register_variant(reg, None, note="adverse suite check")
    rules.freeze_rule(reg, rid)
    rules.claim_holdout(reg, rid, "check")
    try:
        rules.claim_holdout(reg, rid, "check")
        add("untouched period", "second use of the untouched period", "refused", "ALLOWED", False)
    except rules.HoldoutRefused:
        add("untouched period", "second use of the untouched period", "refused", "refused", True)
    os.remove(reg)
    fresh(work)

    print("ADVERSE SUITE. Synthetic fixtures only. Every row must pass.")
    print("")
    last = None
    for i, (group, name, expected, observed, ok) in enumerate(rows, start=1):
        if group != last:
            print("[%s]" % group)
            last = group
        print("  %2d. %-42s %s" % (i, name, "PASS" if ok else "FAIL"))
        print("      expected: %s" % expected)
        print("      observed: %s" % observed)
    bad = [r for r in rows if not r[4]]
    print("")
    print("RESULT: %d of %d cases passed%s" % (len(rows) - len(bad), len(rows),
                                               "" if not bad else "; FAILED: %s"
                                               % ", ".join(r[1] for r in bad)))
    return 1 if bad else 0


# ------------------------------------------------------------------- sweep

def cmd_sweep(a):
    feed = a.feed or NORMAL_FEED
    if not os.path.isfile(feed):
        raise Stop(3, "feed not found: %s" % feed)
    e = make_engine(a, as_of=a.as_of)
    res = e.process_feed(feed)
    if not res["accepted"]:
        print("FEED REFUSED: %s" % res["code"])
        return 2
    s = e.summary()
    fills = e.fills()
    print("COST SWEEP on %s, rule %s, %d fills" % (rel(feed), e.rule_id, len(fills)))
    if not fills:
        raise Stop(3, "no fills to reprice")
    print("")
    print("Same trades, every cost multiplied (repriced from the raw open stored on each fill):")
    nets = []
    for mult in SWEEP_MULTS:
        net = engine.reprice_net(fills, e.state["last_close"], e.cfg, mult)
        nets.append(net)
        extra = ""
        if mult == 1:
            same = abs(net - s["net_pnl"]) < 1e-6
            extra = "   equals the replay's net: %s" % ("yes" if same else "NO")
            if not same:
                nets.append(float("nan"))
        print("  costs x%d   net %10s%s" % (mult, money(net), extra))
    falls = all(nets[i] > nets[i + 1] for i in range(len(nets) - 1))
    print("net falls at every step as costs rise: %s" % ("yes" if falls else "NO"))
    print("")
    print("Separate re-runs that wait extra bars before filling (these are different fills,")
    print("so they are shown apart and are not part of the check above):")
    for delay in (0, 1, 2):
        cfg = load_json(a.config) if a.config else {}
        cfg["delay_bars"] = delay
        ed = make_engine(a, config=cfg, as_of=a.as_of)
        ed.process_feed(feed)
        sd = ed.summary()
        print("  extra wait %d bar(s)   fills %3d   net %10s" % (delay, sd["fills"],
                                                                 money(sd["net_pnl"])))
    print("Inside a session the decision is ready just after the next bar has opened, so the")
    print("fill is already one full bar later; an extra wait of 1 changes only fills that")
    print("cross a session break.")
    return 0 if falls else 1


# ----------------------------------------------------------------- holdout

def cmd_holdout(a):
    state_dir = safe_state_dir(a.state_dir or os.path.join(OUT, "holdout"))
    wait = getattr(a, "lock_wait", None)
    with hold_lock(state_dir, wait):
        with hold_lock(a.registry, wait):
            return _holdout_locked(a)


def _holdout_locked(a):
    feed = a.feed or HOLDOUT_FEED
    if not os.path.isfile(feed):
        raise Stop(3, "feed not found: %s" % feed)
    params = load_json(a.params) if a.params else None
    rid = rules.rule_id(params)
    try:
        reg = rules.claim_holdout(a.registry, rid, sha256_file(feed))
    except rules.HoldoutRefused as exc:
        print("UNTOUCHED PERIOD REFUSED: %s" % exc)
        return 2
    print("Untouched period claimed for %s at %s. Variants tried before this use: %d. "
          "It cannot be used again." % (rid, reg["holdout"]["used_utc"],
                                        reg["holdout"]["variants_tried_before_use"]))
    print("")
    state_dir = safe_state_dir(a.state_dir or os.path.join(OUT, "holdout"))
    os.makedirs(state_dir, exist_ok=True)
    fresh(state_dir)
    e = make_engine(a, state_dir=state_dir)
    res = e.process_feed(feed)
    s = print_report(e, res, feed, a.as_of, variants=len(reg["variants"]), state_dir=state_dir)
    out = dict(s)
    out.update({"feed": os.path.basename(feed), "feed_sha256": sha256_file(feed),
                "as_of": a.as_of, "holdout_claim": reg["holdout"]})
    with open(os.path.join(state_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return 0 if res["accepted"] else 2


# ---------------------------------------------------------------- registry

def cmd_registry(a):
    if a.freeze:
        rid = rules.rule_id(load_json(a.params) if a.params else None)
        try:
            with hold_lock(a.registry):
                rules.freeze_rule(a.registry, rid)
        except ValueError as exc:
            print("FREEZE REFUSED: %s" % exc)
            return 2
        print("frozen: %s" % rid)
    reg = rules.load_registry(a.registry)
    print("registry        %s" % rel(a.registry))
    print("variants tried  %d" % len(reg["variants"]))
    for v in reg["variants"]:
        print("  %s  %s  first run %s" % (v["rule_id"], json.dumps(v["params"], sort_keys=True),
                                          v["first_run_utc"]))
    print("frozen rule     %s" % reg.get("frozen_rule_id"))
    print("untouched period %s" % json.dumps(reg.get("holdout"), sort_keys=True))
    return 0


# ----------------------------------------------------------------- explain

def cmd_explain(a):
    state_dir = safe_state_dir(a.state_dir or os.path.join(OUT, "normal"))
    path = os.path.join(state_dir, "decisions.jsonl")
    if not os.path.isfile(path):
        raise Stop(3, "no decisions file in %s; run replay first" % rel(state_dir))
    decisions = read_jsonl(path)
    if a.decision:
        picked = [d for d in decisions if d["decision_id"] == a.decision]
    elif a.all:
        picked = decisions
    else:
        picked = [d for d in decisions if d["action"] in ("ENTER_LONG", "EXIT_LONG", "BLOCKED")]
    if not picked:
        print("no matching decision")
        return 1
    for d in picked:
        print("%s  %s  %s" % (d["decision_id"], d["action"], d["reason_code"]))
        print("  %s" % d["explanation"])
        note = explain_mod.read_note(state_dir, d["decision_id"])
        if note:
            print("  [%s]" % explain_mod.NOTE_LABEL)
            for ln in note.strip().split("\n"):
                print("  | %s" % ln)
        print("")
    return 0


# ------------------------------------------------------------------ packet

CHALLENGE_SCHEMA = {
    "packet_id": "string, copied from the packet",
    "reviewer_model": "string, the exact model name that produced this review",
    "reviewed_utc": "string, UTC time of the review",
    "live_or_recorded": "one of: live, recorded",
    "verdict": "one of: agree, challenge, cannot_tell",
    "arithmetic": [{"item": "string, one of arithmetic_to_check", "packet_value": "number or string",
                    "recomputed_value": "number or string", "match": "true or false"}],
    "rule_followed": "true or false: does the action follow from the rule as written and the inputs",
    "concerns": ["string"],
    "missing_information": ["string"],
    "authority": "must be the exact text: advisory only; cannot authorize a fill",
}


def cmd_packet(a):
    feed = a.feed or NORMAL_FEED
    chk = provenance.check_feed(feed)
    if not chk.ok:
        print("FEED REFUSED: %s" % chk.primary_code())
        return 2
    probe = make_engine(a, as_of=a.as_of)
    probe.process_feed(feed)
    first = next((d for d in probe.decisions if d["action"] == "ENTER_LONG"), None)
    if first is None:
        raise Stop(3, "this feed has no buy decision to publish")
    sig = first["bar_seq"]
    os.makedirs(PACKET_DIR, exist_ok=True)
    # A new file name: packets published before 2026-11-15 keep their own bars
    # file (bars_through_signal_bar.jsonl) so their saved reviews still check.
    cut = os.path.join(PACKET_DIR, "test_only_bars_through_signal_bar.jsonl")
    with open(feed, "r", encoding="utf-8") as fh:
        lines = [ln for ln in fh.read().split("\n") if ln.strip()]
    # Reviewers get the bars and nothing about how they were made: no script
    # name, seed, creation time or full period, which would hint at later bars.
    src = json.loads(lines[0])
    head = {"type": "manifest", "source": src["source"], "symbol": src["symbol"],
            "timeframe_minutes": src["timeframe_minutes"],
            "generator": "a fixture script (name, seed and period withheld)",
            "note": "TEST ONLY: synthetic bars made by a script; not market data"}
    keep = ([json.dumps(head, sort_keys=True)]
            + [ln for ln in lines[1:] if json.loads(ln)["seq"] <= sig])
    with open(cut, "w", encoding="utf-8") as fh:
        fh.write("\n".join(keep) + "\n")
    # a second engine that is never given a bar after the signal bar
    e = make_engine(a, as_of=a.as_of)
    res = e.process_feed(cut)
    d = e.decisions[-1]
    if not res["accepted"] or d["decision_id"] != first["decision_id"] or e.ledger[-1]["type"] != "order":
        raise Stop(3, "UNEXPECTED STATE: the cut feed did not reproduce the decision")
    reg = rules.load_registry(a.registry)
    cfg = e.cfg
    bars = [dict((k, rec[k]) for k in ("seq", "ts_open", "ts_close", "delivered_ts",
                                       "open", "high", "low", "close"))
            for _i, rec in provenance.check_feed(cut).records][-25:]
    o = d["order"]
    exp_open = o.get("earliest_fill_open_expected")
    if exp_open is not None and exp_open < o["earliest_fill_ts"]:
        raise Stop(3, "UNEXPECTED STATE: the fill plan names bar %d, expected to open at %s, "
                      "before the decision is ready at %s; nothing was published"
                   % (o["earliest_fill_seq"], exp_open, o["earliest_fill_ts"]))
    frozen = {
        "schema": "tvbot-decision-packet-1",
        "what_this_is": "TEST ONLY. One paper decision, frozen at the moment it was made, for "
                        "an outside review. Synthetic bars made by a script. Not market data. "
                        "Nothing here came from TradingView.",
        "symbol": d["symbol"], "timeframe_minutes": res["manifest"]["timeframe_minutes"],
        "data_source": res["manifest"]["source"],
        "rule": {"rule_id": e.rule_id, "name": rules.RULE_NAME, "version": rules.RULE_VERSION,
                 "params": e.params,
                 "in_words": "On closed bars only: when the fast exponential average crosses "
                             "above the slow one and no position is open, buy. Sell after a bar "
                             "closes at or below the stop, or after the fast average crosses "
                             "back below the slow one. Long only, one position."},
        "rule_variants_tried_so_far": len(reg["variants"]),
        "decision": dict((k, d[k]) for k in ("decision_id", "action", "reason_code", "bar_seq",
                                             "bar_ts_open", "signal_ts", "available_ts",
                                             "decision_ready_ts")),
        "inputs_at_decision": d["inputs"],
        "proposed_paper_order": {"side": o["side"], "qty": o["qty"],
                                 "notional_at_signal_close": engine.r6(o["qty"] * d["inputs"]["close"])},
        "forward_plan": {
            "fill_rule": "the open of the first bar that opens at or after earliest_fill_ts",
            "earliest_fill_ts": o["earliest_fill_ts"],
            "earliest_fill_ts_meaning": "the decision-ready time, not a bar open; the fill bar "
                                        "must open at or after it",
            "min_fill_seq": o["min_fill_seq"],
            "earliest_fill_seq": o["earliest_fill_seq"],
            "earliest_fill_open_expected": exp_open,
            "earliest_fill_seq_meaning": "the first bar expected to open at or after "
                                         "earliest_fill_ts, going by the bar open times seen so "
                                         "far. It is a plan, not a value from a later bar. A "
                                         "null expected open means the next bar belongs to a "
                                         "later session whose open time is not known yet.",
            "costs": dict((k, cfg[k]) for k in ("half_spread_bps", "slippage_bps",
                                                "commission_per_share", "commission_min")),
            "stop_rule": "sell after a bar closes at or below (raw open of the fill bar) x "
                         "(1 - stop_pct / 100); the fill bar's open is not known yet",
            "exit_priority": ["data_gap", "daily_loss_limit", "stop", "cross_down"],
            "risk_limits": cfg["limits"],
        },
        "portfolio_at_decision": {"cash": e.state["cash"], "position_qty": e.state["qty"],
                                  "order_notional_setting": cfg["order_notional"],
                                  "latency_seconds": cfg["latency_seconds"]},
        "recent_closed_bars": bars,
        "all_bars_file": os.path.basename(cut), "all_bars_sha256": sha256_file(cut),
        "withheld": "Every bar after seq %d, the fill and any profit or loss. The engine that "
                    "produced this packet was never given a later bar." % sig,
        "arithmetic_to_check": [
            "ema_fast = (2 / (fast_len + 1)) * close + (1 - 2 / (fast_len + 1)) * prev_ema_fast",
            "ema_slow = (2 / (slow_len + 1)) * close + (1 - 2 / (slow_len + 1)) * prev_ema_slow",
            "cross_up: ema_fast > ema_slow and prev_ema_fast <= prev_ema_slow",
            "bars_since_reset >= warmup_bars",
            "qty = floor(order_notional_setting / close)",
            "qty * close <= max_position_notional and qty <= max_qty",
            "decision_ready_ts = available_ts + latency_seconds",
        ],
    }
    blob = json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode("utf-8")
    pid = "PKT-" + hashlib.sha256(blob).hexdigest()[:12]
    rev_dir = os.path.join(PACKET_DIR, "reviews")
    recorded = sorted(f for f in (os.listdir(rev_dir) if os.path.isdir(rev_dir) else [])
                      if f.startswith(pid + ".") and f.endswith(".recorded.json"))
    if recorded:
        review_status = ("recorded. %d saved review(s) of this packet: %s. A saved review is a "
                         "recorded reply, not a live one. Check its numbers with "
                         "bot/check_review.py." % (len(recorded), ", ".join(
                             "packets/reviews/" + f for f in recorded)))
    else:
        review_status = "pending. No saved model review of this packet was found."
    packet = {
        "packet_id": pid, "published_utc": now_utc(), "frozen": frozen,
        "expected_challenge_schema": CHALLENGE_SCHEMA,
        "review_status": review_status,
        "authority": "A review is advisory text. It cannot authorize, change or trigger a fill. "
                     "The runner never reads reviews.",
    }
    path = os.path.join(PACKET_DIR, "%s.json" % pid)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(packet, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(CHALLENGE_SCHEMA_PATH, "w", encoding="utf-8") as fh:
        json.dump({"about": "The format for a reviewer's reply to a decision packet in packets/. "
                            "A reply is advisory text. It cannot authorize, change or trigger a "
                            "fill, and the runner never reads it.",
                   "reply_format": CHALLENGE_SCHEMA}, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("reply format    %s" % rel(CHALLENGE_SCHEMA_PATH))
    print("packet          %s" % rel(path))
    print("packet id       %s" % pid)
    print("decision        %s %s at bar %d (signal %s, ready %s)"
          % (d["action"], d["reason_code"], sig, d["signal_ts"], d["decision_ready_ts"]))
    print("bars included   seq 1 to %d in %s (the last 25 are also inside the packet)"
          % (sig, rel(cut)))
    print("withheld        every later bar, the fill and the result")
    print("review status   %s" % review_status)
    return 0


# ------------------------------------------------------------- gate and paper

def load_gate(path=None):
    path = path or GATE_PATH
    if not os.path.isfile(path):
        return None
    try:
        g = load_json(path)
    except (ValueError, OSError):
        return None
    return g if isinstance(g, dict) and g.get("schema") == riskinfo.GATE_SCHEMA else None


def gate_in_force(gate, rule_id, cfg_hash):
    return bool(gate and gate.get("decision") == "approve_paper_only"
                and gate.get("rule_id") == rule_id and gate.get("config_hash") == cfg_hash)


def gate_screen(e):
    """Everything the gate shows, as (lines, shown). One place, so the screen and the record agree."""
    risk = riskinfo.stop_out_estimate(e.cfg, e.params)
    # The saved test run made with these same settings, if there is one.
    test, same_size = None, False
    for folder in (NORMAL_STATE, os.path.join(OUT, "small_size")):
        f = os.path.join(folder, "summary.json")
        if os.path.isfile(f):
            cand = load_json(f)
            if test is None:
                test = cand
            if cand.get("config_hash") == e.cfg_hash:
                test, same_size = cand, True
                break
    worst = riskinfo.worst_round_trip(test)
    out = []
    out.append("PAPER GATE. Approve or pass. This covers paper mode only.")
    out.append("")
    out.append("What you are deciding")
    out.append("  Whether this bot may read a real-bar CSV file that you supplied and write paper")
    out.append("  rows on this Mac. It cannot place a real order. No account, key, purchase or")
    out.append("  money movement is involved, and approving here never allows one.")
    out.append("")
    out.append("What the decision covers")
    out.append("  rule          %s" % e.rule_id)
    out.append("  settings      %s   paper order size %.2f, daily loss limit %.2f"
               % (e.cfg_hash, risk["order_notional"], risk["max_daily_loss"]))
    out.append("")
    out.append("What one losing paper trade costs")
    out.append("  one trade stopped at its stop level    about %.2f  (%.2f price fall + %.2f costs)"
               % (risk["one_stop_estimate"], risk["price_loss_at_stop"], risk["costs_both_sides"]))
    out.append("  share of the daily loss limit          %.1f percent" % risk["stop_share_of_daily_limit_pct"])
    out.append("  stopped trades that fit under the limit  %s" % risk["stops_before_daily_limit"])
    if worst:
        over = " That is more than the whole daily limit." \
            if abs(worst["net_pnl"]) > risk["max_daily_loss"] else ""
        out.append("  worst closed trade in the saved test   %+.2f (TEST ONLY: synthetic; %s).%s"
                   % (worst["net_pnl"], "at this order size" if same_size
                      else "saved at a different order size", over))
    out.append("  why a loss can be larger               the stop is checked when a bar closes and the")
    out.append("                                         sale fills at a later open")
    if risk["stop_share_of_daily_limit_pct"] > 40.0:
        out.append("  A smaller size is ready. It puts one stopped trade at about a third of the limit.")
        out.append("  To use it, add this to the end of both the gate and the paper commands:")
        out.append("    --config %s" % rel(SMALLER_SIZE))
    out.append("")
    out.append("What the test showed (%s)" % TEST_LABEL)
    if test:
        out.append("  net %+.2f over %d round trips on one synthetic sample%s. That is not evidence"
                   % (test["net_pnl"], test["round_trip_count"],
                      "" if same_size else " (at a different order size)"))
        out.append("  of an edge.")
    else:
        out.append("  no saved test run was found")
    shown = {"risk": risk, "worst_test_trade": worst,
             "test_net_pnl": test["net_pnl"] if test else None,
             "test_round_trips": test["round_trip_count"] if test else None}
    return out, shown


def cmd_gate(a):
    e = make_engine(a, as_of=a.as_of)
    lines, shown = gate_screen(e)
    print("\n".join(lines))
    print("")
    current = load_gate()
    if current:
        print("recorded now   %s at %s for rule %s, settings %s (%s)"
              % (current.get("decision"), current.get("decided_utc"), current.get("rule_id"),
                 current.get("config_hash"),
                 "in force for these settings" if gate_in_force(current, e.rule_id, e.cfg_hash)
                 else "not in force for these settings"))
    else:
        print("recorded now   nothing")
    if a.show:
        print("shown only     nothing was recorded")
        return 0
    agent_env = [k for k in os.environ
                 if k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT") or k.startswith("CODEX_SANDBOX")]
    if not (sys.stdin.isatty() and sys.stdout.isatty()) or agent_env:
        print("NOT RECORDED. This decision is Matthew's. It can only be typed by a person in the")
        print("Mac's own Terminal app, not by an assistant, a script or a piped answer.")
        return 2
    try:
        typed = input("Type %s or %s, then press Return: " % (riskinfo.APPROVE_TEXT, riskinfo.PASS_TEXT))
    except (EOFError, KeyboardInterrupt):
        print("")
        print("NOT RECORDED. Nothing was typed.")
        return 1
    typed = typed.strip()
    if typed == riskinfo.APPROVE_TEXT:
        decision = "approve_paper_only"
    elif typed == riskinfo.PASS_TEXT:
        decision = "pass"
    else:
        print("NOT RECORDED. The text did not match either choice exactly.")
        return 1
    rec = {"schema": riskinfo.GATE_SCHEMA, "decision": decision, "decided_utc": now_utc(),
           "typed": typed, "rule_id": e.rule_id, "config_hash": e.cfg_hash,
           "scope": riskinfo.SCOPE, "shown": shown}
    os.makedirs(os.path.dirname(GATE_PATH), exist_ok=True)
    with open(GATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("RECORDED       %s at %s in %s" % (decision, rec["decided_utc"], rel(GATE_PATH)))
    print("scope          %s" % riskinfo.SCOPE)
    rebuild_page()
    return 0


REFETCH_MESSAGE = ("REAL FILE DOES NOT LINE UP WITH THE SAVED PAPER RUN: %d of its %d rows differ "
                   "from the bars saved earlier (first at row %d, the bar opening %s). No bar was "
                   "read and the saved run was not changed. After every new fetch, run paper with "
                   "--fresh added; it rebuilds the paper run from this file.")


SHORTER_MESSAGE = ("REAL FILE IS SHORTER THAN THE SAVED PAPER RUN: it has %d rows and the saved "
                   "run holds %d bars. No bar was read and the saved run was not changed. Run paper "
                   "with --fresh added; it rebuilds the paper run from this file.")


def refetch_conflicts(e, feed_path):
    """Rows whose number is already saved in this state folder with other values.

    real_feed numbers rows from 1 on every conversion, and the engine knows a
    bar by that number. When a fetched window has slid (a vendor's row cap
    drops the oldest rows), old numbers point at other bars. The engine would
    ignore those rows one by one and could lose new bars without a word, so the
    paper command refuses the whole file before any bar is read.

    Returns (rows that differ, rows in the file).
    """
    known = e.state.get("bar_hashes") or {}
    clash, total = [], 0
    with open(feed_path, encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("type") != "bar":
                continue
            total += 1
            saved = known.get(str(rec.get("seq")))
            if saved is not None and saved != engine.bar_hash(rec):
                clash.append(rec)
    return clash, total


def cmd_paper(a):
    # 1. No source file: one clear message, nothing read, no signal.
    if not a.source or not os.path.isfile(a.source):
        print(real_feed.NO_SOURCE_MESSAGE)
        return 2
    # 2. The gate, for exactly this rule and these settings, before any bar is read.
    probe = make_engine(a, as_of=a.as_of)
    if not gate_in_force(load_gate(), probe.rule_id, probe.cfg_hash):
        print("PAPER GATE NOT APPROVED for rule %s, settings %s. No bars were read and no signal "
              "was made." % (probe.rule_id, probe.cfg_hash))
        print("Matthew decides in the Mac's Terminal app:  /usr/bin/python3 -I %s gate"
              % rel(os.path.join(BOT, "run.py")))
        return 2
    state_dir = safe_state_dir(a.state_dir or PAPER_STATE)
    with hold_lock(state_dir, getattr(a, "lock_wait", None)):
        # 3. Check the source and convert the CSV. Any doubt refuses the whole file.
        try:
            conv = real_feed.convert(a.source, REAL_DIR, a.as_of)
        except real_feed.SourceRefused as exc:
            if exc.code == "no_source":
                print(str(exc))
            else:
                print("REAL SOURCE REFUSED (%s). No signal was made." % exc.code)
                print("  - %s" % exc)
            return 2
        os.makedirs(state_dir, exist_ok=True)
        if a.fresh:
            fresh(state_dir)
        with hold_lock(a.registry, getattr(a, "lock_wait", None)):
            _rid, _new, count = rules.register_variant(
                a.registry, load_json(a.params) if a.params else None, note="paper")
        e = make_engine(a, state_dir=state_dir, permitted_sources=conv["permitted"])
        # 4. A re-fetched file must line up with the saved run, or nothing is read.
        clash, total = refetch_conflicts(e, conv["feed"])
        if clash:
            print(REFETCH_MESSAGE % (len(clash), total, clash[0].get("seq"), clash[0].get("ts_open")))
            return 2
        saved_bars = len(e.state.get("bar_hashes") or {})
        if total < saved_bars:
            # Every row matches, but the saved run goes further than this file does. Reading it
            # would add nothing and leave a result that no longer describes the file in hand.
            print(SHORTER_MESSAGE % (total, saved_bars))
            return 2
        try:
            res = e.process_feed(conv["feed"])
        except engine.EngineError as exc:
            raise Stop(3, "UNEXPECTED STATE: %s" % exc)
        if res["bar_results"].get("conflicting_duplicate"):
            # Not reachable after the check above; kept so this can never pass quietly.
            print("REAL FILE DID NOT LINE UP WITH THE SAVED PAPER RUN: %d rows were ignored as "
                  "conflicting. Treat this run's output as wrong and run paper again with --fresh."
                  % res["bar_results"]["conflicting_duplicate"])
            return 2
        rep = conv["report"]
        label = "REAL BARS, PAPER ONLY (source '%s', %s)." % (rep["source_name"], rep["symbol"])
        s = print_report(e, res, conv["feed"], a.as_of, variants=count, state_dir=state_dir,
                         label=label)
        print("source report   %s   (%d rows, %s to %s)"
              % (rel(conv["report_path"]), rep["rows"], rep["first_ts_open"], rep["last_ts_close"]))
        print("arrival times   %s" % rep["delivery_assumption"])
        out = dict(s)
        out.update({"feed": os.path.basename(conv["feed"]), "feed_sha256": sha256_file(conv["feed"]),
                    "as_of": a.as_of, "feed_accepted": res["accepted"], "feed_code": res["code"],
                    "feed_reasons": res["reasons"], "bar_results_this_run": res["bar_results"],
                    "config": e.cfg, "config_hash": e.cfg_hash, "rule_variants_tried": count,
                    "data_kind": "real", "source_report": rep, "cost_sweep": cost_sweep(e)})
        with open(os.path.join(state_dir, "summary.json"), "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
            fh.write("\n")
        with open(os.path.join(state_dir, "decision_packet.md"), "w", encoding="utf-8") as fh:
            fh.write(explain_mod.build_packet(e.decisions, e.rule_id))
        if not res["accepted"]:
            return 2
        if not timing_ok(e.fills()) or plan_check(e.ledger)[0]:
            raise Stop(3, "UNEXPECTED STATE: a fill or a fill plan came before its decision was ready")
        rebuild_page()
        return 0


# -------------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(description="EMAX paper runner (paper only)")
    sub = p.add_subparsers(dest="cmd")

    def common(sp, clock_default):
        sp.add_argument("--feed", help="feed file (.jsonl with a manifest)")
        sp.add_argument("--as-of", dest="as_of", default=clock_default,
                        help="the clock used to refuse future-dated bars")
        sp.add_argument("--config", help="JSON file of settings; it may only tighten limits")
        sp.add_argument("--params", help="JSON file of rule parameters (a new variant is counted)")
        sp.add_argument("--registry", default=REGISTRY, help="rule registry file")

    sp = sub.add_parser("replay")
    common(sp, None)
    sp.add_argument("--state-dir", dest="state_dir", help="a subfolder of out/")
    sp.add_argument("--fresh", action="store_true", help="remove this runner's files in the state folder first")
    sp.add_argument("--lock-wait", dest="lock_wait", type=float, default=None,
                    help="seconds to wait if another run is using the state folder (default 30)")
    sp.add_argument("--expect", nargs="?", const=EXPECTED, default=None,
                    help="compare the ledger with an expected ledger file")
    sp.add_argument("--write-expected", dest="write_expected", default=None,
                    help="write the ledger as the expected snapshot (maintenance)")
    sp.set_defaults(func=cmd_replay)

    sp = sub.add_parser("adverse")
    sp.set_defaults(func=cmd_adverse)

    sp = sub.add_parser("sweep")
    common(sp, FIXTURE_CLOCK)
    sp.set_defaults(func=cmd_sweep)

    sp = sub.add_parser("holdout")
    common(sp, None)
    sp.add_argument("--state-dir", dest="state_dir")
    sp.set_defaults(func=cmd_holdout)

    sp = sub.add_parser("registry")
    sp.add_argument("--registry", default=REGISTRY)
    sp.add_argument("--params")
    sp.add_argument("--freeze", action="store_true", help="freeze the current rule")
    sp.set_defaults(func=cmd_registry)

    sp = sub.add_parser("explain")
    sp.add_argument("--state-dir", dest="state_dir")
    sp.add_argument("--decision", help="one decision id")
    sp.add_argument("--all", action="store_true", help="every decision, including stand-aside bars")
    sp.set_defaults(func=cmd_explain)

    sp = sub.add_parser("packet")
    common(sp, FIXTURE_CLOCK)
    sp.set_defaults(func=cmd_packet)

    sp = sub.add_parser("gate")
    common(sp, None)
    sp.add_argument("--show", action="store_true",
                    help="print the gate screen and the recorded decision; record nothing")
    sp.set_defaults(func=cmd_gate)

    sp = sub.add_parser("paper")
    common(sp, None)
    sp.add_argument("--source", default=SOURCE_DEFAULT,
                    help="the source file Matthew wrote (default real/source.json)")
    sp.add_argument("--state-dir", dest="state_dir", help="a subfolder of out/ (default out/paper)")
    sp.add_argument("--fresh", action="store_true", help="remove this runner's files in the state folder first")
    sp.add_argument("--lock-wait", dest="lock_wait", type=float, default=None)
    sp.set_defaults(func=cmd_paper)

    a = p.parse_args(argv)
    if not getattr(a, "func", None):
        p.print_help()
        return 3
    if hasattr(a, "as_of") and a.as_of is None:
        a.as_of = now_utc()
    try:
        return a.func(a)
    except Stop as exc:
        print(str(exc))
        return exc.code
    except engine.EngineError as exc:
        print("UNEXPECTED STATE: %s" % exc)
        return 3


if __name__ == "__main__":
    sys.exit(main())
