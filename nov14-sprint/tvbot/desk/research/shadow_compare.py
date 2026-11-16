#!/usr/bin/env python3
"""REVERT-1 shadow comparison. Supply a cutoff from a pre-existing, independently recorded protocol.

Reads one desk state_dir's lab files READ-ONLY (lab_bars, lab_inputs, lab_forecasts,
lab_scores .jsonl). For every lab forecast group it rebuilds the exact input bars from the
inputs row, checks their hash, decides REVERT-1 on them at the same cut-off, and scores it
with the lab's own unchanged scorer (lab/score.py later_bars + compute_core, v3) on the same
later bars as cash, ema and the frozen challenger. Results go only to a fresh output directory.

Provenance guard (runner 1.1.0; the rule and its parameters are unchanged from 1.0.0):
- A window counts as forward evidence only if every lab hash chain verifies, the lab's own
  baseline decisions reproduce and the stored v3 scores match (whole snapshot and the window
  itself), every input and outcome bar is genuine IEX data (not mock or synthetic), the
  signal bar closed after the freeze, and the scorer marks the window eligible.
- Evidence classes: WITNESSED_FORWARD means a REVERT-1 forecast stored by an EARLIER run of
  this runner (--witness-dir) before the outcome bar closed and before it was stored.
  RECONSTRUCTED_OUT_OF_SAMPLE means a post-freeze window decided afterwards under the frozen
  rule. Baseline lab forecasts get their own witnessed flag from the lab's recorded time.
- Every run writes to a new or empty directory (--out) or a new run-<UTC>-<pid> directory
  (--out-parent), so an earlier snapshot's forecasts are never overwritten.
- Only lab rows marked shadow and never_routed are read. Broker, order and probe logs are
  never opened, so no engineering broker probe can enter these figures.

It places no orders: no broker, transport, session or order-manager module is imported
(checked at exit), socket connects are patched to raise, and the desk state_dir is opened
read-only. A partial last line (the desk mid-write) is ignored, so it can run while a
connected desk is recording.

Usage (system Python 3.9.6):
  /usr/bin/python3 -I -B shadow_compare.py --freeze-utc <ISO8601Z> --desk <DESK> --state-dir <STATE_DIR> --out-parent <RUNS_DIR> \
      [--witness-dir <EARLIER_RUN_DIR> ...]
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import socket
import sys


def _no_network(*_a, **_k):
    raise RuntimeError("network disabled: REVERT-1 shadow runner is offline and read-only")


socket.socket.connect = _no_network
socket.socket.connect_ex = _no_network
socket.create_connection = _no_network

PREREG_FILE = "caller-supplied protocol"
PREREG_TS = None  # required at the command line; a caller-supplied timestamp is not proof of registration
VARIANT = "revert1"
RULE_VERSION = "1.0.0"
RUNNER_VERSION = "1.1.0-provenance-guard"
PARAMS = {"min_bars": 10, "atr_len": 6, "vol_floor_bps": 10.0, "vol_cap_bps": 150.0,
          "shock_mult": 1.0, "revert_frac": 0.5, "hurdle_mult": 1.0, "horizon_bars": 1,
          "sensitivity_mult": 2.0}
CFG_HASH = hashlib.sha256(json.dumps(PARAMS, sort_keys=True).encode("utf-8")).hexdigest()[:12]
RULE_ID = "REVERT1-%s-%s" % (RULE_VERSION, CFG_HASH[:8])
BASES = ("cash", "ema", "challenger")
FORBIDDEN = ("alpaca.broker", "alpaca.transport", "alpaca.live", "alpaca.live_launch", "alpaca.mock",
             "alpaca.setup", "orders.manager", "orders.intake", "orders.fake_broker", "session",
             "alpaca_session", "launch", "live_check", "http.client", "urllib.request", "ssl")
OUT_FILES = ("revert1_forecasts.jsonl", "revert1_scores.jsonl")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def read_snapshot(path):
    """(rows, partial_tail_ignored, sha256_of_bytes_used, bytes_used); read-only, tolerant."""
    if not os.path.exists(path):
        return [], False, None, 0
    with open(path, "rb") as fh:
        data = fh.read()
    cut = data.rfind(b"\n") + 1
    used, tail = data[:cut], data[cut:]
    rows = [json.loads(ln.decode("utf-8")) for ln in used.split(b"\n") if ln.strip()]
    return rows, bool(tail.strip()), hashlib.sha256(used).hexdigest(), len(used)


class SnapStore(object):
    """Read-only stand-in for lab.record.Store with the fields lab.score.later_bars reads."""

    def __init__(self, R, state_dir):
        self.dir = state_dir
        self.rows, self.partial, self.snap = {}, {}, {}
        for k, f in (("bars", R.BARS), ("inputs", R.INPUTS), ("forecasts", R.FORECASTS), ("scores", R.SCORES)):
            rows, partial, digest, n = read_snapshot(os.path.join(state_dir, f))
            self.rows[k], self.partial[k], self.snap[k] = rows, partial, {"file": f, "sha256": digest, "bytes": n,
                                                                          "rows": len(rows)}
        self.bar_index = {r["bar_sha"]: i for i, r in enumerate(self.rows["bars"])}
        self.input_index = {r["input_sha256"]: r for r in self.rows["inputs"]}
        self.forecast_index = {r["forecast_id"]: r for r in self.rows["forecasts"]}
        self.scored = {r["forecast_id"]: r for r in self.rows["scores"]}

    def bars_by_sha(self, shas):
        return [None if self.bar_index.get(s) is None else self.rows["bars"][self.bar_index[s]]["bar"]
                for s in shas]

    def bar_row(self, s):
        i = self.bar_index.get(s)
        return None if i is None else self.rows["bars"][i]


def decide_variant(B, CH, bars_so_far, now, test_size):
    """REVERT-1 1.0.0 exactly as preregistered. Returns a plain shadow decision dict."""
    p = PARAMS
    bars = B.knowable_bars(bars_so_far, now)
    base = {"strategy": VARIANT, "rule_id": RULE_ID, "cfg_hash": CFG_HASH, "shadow": True, "never_routed": True}
    if len(bars) < p["min_bars"]:
        base.update({"action": "pass", "qty": 0, "exposure": 0, "reason_code": "NOT_ENOUGH_BARS",
                     "signal_side": 0, "indicators": None, "cost_view": None})
        return base
    c1, c0 = float(bars[-1]["close"]), float(bars[-2]["close"])
    r = (c1 / c0 - 1.0) * 1e4
    atr = CH._atr(bars, p["atr_len"]) / c1 * 1e4
    qty = B.base_qty(c1, {"test_size": test_size})
    _, rt = CH._rt_bps(qty, c1, 1.0)
    _, rt2 = CH._rt_bps(qty, c1, p["sensitivity_mult"])
    exp_move = p["revert_frac"] * abs(r)
    shock = r != 0 and abs(r) >= p["shock_mult"] * atr
    side = (-1 if r > 0 else 1) if shock else 0
    hurdle = None if rt is None else rt * p["hurdle_mult"]
    if qty <= 0:
        code = "ZERO_SIZE"
    elif atr < p["vol_floor_bps"]:
        code = "VOL_TOO_LOW"
    elif atr > p["vol_cap_bps"]:
        code = "VOL_TOO_HIGH"
    elif side == 0:
        code = "NO_SHOCK"
    elif hurdle is None or exp_move < hurdle:
        code = "COST_HURDLE"
    else:
        code = None
    trade = code is None
    base.update({
        "action": ("enter_long" if side > 0 else "enter_short") if trade else "pass",
        "qty": qty if trade else 0, "exposure": side if trade else 0,
        "reason_code": ("REVERT_LONG" if side > 0 else "REVERT_SHORT") if trade else code,
        "signal_side": side,
        "indicators": {"close": round(c1, 6), "r_last_bps": round(r, 4), "atr_bps": round(atr, 4)},
        "cost_view": {"round_trip_bps": None if rt is None else round(rt, 4),
                      "round_trip_bps_2x": None if rt2 is None else round(rt2, 4),
                      "expected_move_bps": round(exp_move, 4),
                      "clears_1x": hurdle is not None and exp_move >= hurdle,
                      "clears_2x": rt2 is not None and exp_move >= rt2 * p["hurdle_mult"]}})
    return base


def _stats(xs):
    n = len(xs)
    if n == 0:
        return {"n": 0, "sum": 0.0, "mean": None, "sd": None, "se": None, "t": None, "upper95": None}
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else None
    se = sd / math.sqrt(n) if sd is not None else None
    t = (m / se) if se else None
    return {"n": n, "sum": round(sum(xs), 4), "mean": round(m, 4), "sd": None if sd is None else round(sd, 4),
            "se": None if se is None else round(se, 4), "t": None if t is None else round(t, 3),
            "upper95": None if se is None else round(m + 1.96 * se, 4)}


def _metrics(ws):
    """Per-strategy and paired after-cost statistics on a list of scored eligible windows."""
    per = {}
    for n in BASES + (VARIANT,):
        rows = [w["cores"][n] for w in ws if n in w["cores"]]
        trades = [c for c in rows if c["kind"] == "trade"]
        per[n] = {"windows": len(rows), "trades": len(trades),
                  "passes": sum(1 for c in rows if c["kind"] == "pass/flat"),
                  "holds": sum(1 for c in rows if c["kind"].startswith("hold")),
                  "per_window_net_bps": _stats([c["net_bps"] for c in rows]),
                  "per_window_net_bps_2x": _stats([c["net_bps_2x"] for c in rows]),
                  "per_trade_net_bps": _stats([c["net_bps"] for c in trades]),
                  "per_trade_net_bps_2x": _stats([c["net_bps_2x"] for c in trades])}
    paired = {}
    for n in BASES:
        common = [w for w in ws if n in w["cores"]]
        paired["%s_minus_%s" % (VARIANT, n)] = {
            "net_bps": _stats([w["cores"][VARIANT]["net_bps"] - w["cores"][n]["net_bps"] for w in common]),
            "net_bps_2x": _stats([w["cores"][VARIANT]["net_bps_2x"] - w["cores"][n]["net_bps_2x"] for w in common])}
    return per, paired


def _sides(ws):
    """How REVERT-1 observations split between what a long-only account could take and
    what is hypothetical (a short, or a gated setup that never traded)."""
    c = {"long_trade_long_only_compatible": 0, "short_trade_hypothetical": 0,
         "setup_pass_hypothetical": 0, "flat_pass_no_signal": 0}
    for w in ws:
        if w["cores"][VARIANT]["kind"] == "trade":
            c["long_trade_long_only_compatible" if w["signal_side"] > 0 else "short_trade_hypothetical"] += 1
        elif w["signal_side"]:
            c["setup_pass_hypothetical"] += 1
        else:
            c["flat_pass_no_signal"] += 1
    n = len(ws)
    trades = c["long_trade_long_only_compatible"] + c["short_trade_hypothetical"]
    return {"observations": n, "counts": c,
            "fraction_of_observations": {k: (round(v / float(n), 4) if n else None) for k, v in c.items()},
            "fraction_of_trades_short_hypothetical": (round(c["short_trade_hypothetical"] / float(trades), 4)
                                                      if trades else None)}


def _genuine_iex(R, bar, row):
    """Genuine IEX provenance: the lab's own test and the stored row flag both say not synthetic."""
    src = str((bar or {}).get("source") or "").upper()
    return (bar is not None and row is not None and not R._synthetic(bar) and "IEX" in src
            and "MOCK" not in src and "SYNTHETIC" not in src and row.get("synthetic") is False)


def _stored_before_outcome(B, st, rec_ts, signal_close, later, shas):
    """(ok, reason): a forecast recorded at rec_ts was stored before its outcome existed."""
    if not rec_ts:
        return False, "no recorded timestamp"
    t = B.parse_ts(rec_ts)
    if t < B.parse_ts(signal_close):
        return False, "recorded before its own signal bar closed (clock or replay inconsistent)"
    if t >= B.parse_ts(later[-1]["ts_close"]):
        return False, "recorded at or after the outcome bar closed"
    for s in shas:
        row = st.bar_row(s)
        if row is None or not row.get("ts_added") or B.parse_ts(row["ts_added"]) < t:
            return False, "an outcome bar was stored before the forecast"
    return True, "stored before the outcome bar closed and before it was stored"


def _load_witnesses(dirs):
    """REVERT-1 forecasts that earlier runs of this runner stored, keyed by forecast_id
    (earliest ts_recorded wins). A run counts only if its summary hashes its forecasts file
    and the file still matches, under the same rule ID and parameters."""
    found, report = {}, []
    for wd in dirs:
        wd = os.path.realpath(wd)
        info = {"dir": os.path.basename(wd), "rows_used": 0}
        try:
            with open(os.path.join(wd, "summary.json"), encoding="utf-8") as fh:
                sm = json.load(fh)
            fp = os.path.join(wd, OUT_FILES[0])
            want = (sm.get("outputs") or {}).get(OUT_FILES[0])
            if not want or not os.path.exists(fp) or sha256_file(fp) != want:
                info["status"] = "unverifiable: forecasts file hash missing from its summary or mismatched"
            elif sm.get("rule_id") != RULE_ID or sm.get("params") != PARAMS or sm.get("prereg_ts") != PREREG_TS or sm.get("runner_sha256") != sha256_file(os.path.abspath(__file__)):
                info["status"] = "different rule, parameters, freeze or runner: not a matching witness"
            else:
                rows, _, _, _ = read_snapshot(fp)
                for row in rows:
                    if row.get("rule_id") != RULE_ID or not row.get("ts_recorded"):
                        continue
                    prev = found.get(row["forecast_id"])
                    if prev is None or row["ts_recorded"] < prev["ts_recorded"]:
                        found[row["forecast_id"]] = row
                    info["rows_used"] += 1
                info["status"] = "ok"
        except (OSError, ValueError) as e:
            info["status"] = "unreadable: %s" % type(e).__name__
        report.append(info)
    return found, report


def main(argv=None):
    global PREREG_TS
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--desk", required=True)
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--out", help="a new or empty output directory for this run")
    ap.add_argument("--out-parent", help="create a fresh run-<UTC>-<pid> directory inside this directory")
    ap.add_argument("--witness-dir", action="append", default=[],
                    help="an earlier run's output directory whose stored REVERT-1 forecasts may witness outcomes")
    ap.add_argument("--prereg", default=PREREG_FILE, help="preregistration record name, copied into the output")
    ap.add_argument("--label", default="")
    ap.add_argument("--freeze-utc", required=True, help="pre-existing written protocol cutoff, UTC with Z")
    a = ap.parse_args(argv)
    import re
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", a.freeze_utc):
        ap.error("--freeze-utc requires YYYY-MM-DDTHH:MM:SSZ")
    try:
        freeze = datetime.datetime.strptime(a.freeze_utc,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        ap.error("--freeze-utc is not a valid date and time")
    if freeze > datetime.datetime.now(datetime.timezone.utc):
        ap.error("the freeze must already have happened")
    PREREG_TS = a.freeze_utc
    started = now_iso()
    if bool(a.out) == bool(a.out_parent):
        raise SystemExit("refused: give exactly one of --out or --out-parent")
    if a.out_parent:
        out = os.path.join(os.path.realpath(a.out_parent),
                           "run-%s-%d" % (started.replace("-", "").replace(":", ""), os.getpid()))
    else:
        out = os.path.realpath(a.out)
    desk, state = (os.path.realpath(x) for x in (a.desk, a.state_dir))
    if out == state or out.startswith(state + os.sep):
        raise SystemExit("refused: --out must be outside the desk state_dir (the runner never writes there)")
    if os.path.exists(out) and (not os.path.isdir(out) or os.listdir(out)):
        raise SystemExit("refused: output directory already exists and is not empty; each run needs a fresh "
                         "directory so an earlier snapshot's forecasts are never overwritten")
    sys.path.insert(0, desk)
    from strategies import base as B
    from strategies import challenger as CH
    from lab import record as R
    from lab import score as S

    st = SnapStore(R, state)
    chains = {k: list(R.check_chain(st.rows[k])) for k in st.rows}
    witnesses, witness_report = _load_witnesses(a.witness_dir)
    size = B.load_test_size()
    groups, excluded = {}, {"not_shadow_or_routed": 0, "unknown_strategy": 0}
    for f in st.rows["forecasts"]:
        if f.get("shadow") is not True or f.get("never_routed") is not True:
            excluded["not_shadow_or_routed"] += 1
            continue
        if f.get("strategy") not in BASES:
            excluded["unknown_strategy"] += 1
            continue
        groups.setdefault(f["group_id"], {})[f["strategy"]] = f
    os.makedirs(out, exist_ok=True)
    fpath, spath = (os.path.join(out, n) for n in OUT_FILES)
    windows, repro, stored_match = [], {"checked": 0, "mismatch": 0}, {"checked": 0, "mismatch": 0}
    with open(fpath, "x", encoding="utf-8") as ff:
        for gid in sorted(groups, key=lambda g: (next(iter(groups[g].values()))["ts_knowable"], g)):
            g = groups[gid]
            ref = g.get("challenger") or next(iter(g.values()))
            inp = st.input_index.get(ref["input_sha256"])
            inputs = None if inp is None else st.bars_by_sha(inp["bar_shas"])
            if inputs is None or any(b is None for b in inputs) or R.input_sha(inputs) != ref["input_sha256"]:
                windows.append({"group_id": gid, "status": "inputs_unverifiable"})
                continue
            w_repro = 0
            for name in BASES:   # the lab's own decisions reproduce on the same inputs
                if name in g:
                    d = R.run_decision(name, inputs, dict(g[name].get("cfg") or {}), ref["ts_knowable"])
                    repro["checked"] += 1
                    if (d.get("action"), d.get("qty")) != (g[name].get("action"), g[name].get("qty")):
                        repro["mismatch"] += 1
                        w_repro += 1
            later, shas = S.later_bars(st, ref)
            d = decide_variant(B, CH, inputs, ref["ts_knowable"], size)
            vf = {"forecast_id": "fv-%s-%s" % (VARIANT, ref["input_sha256"][:16]), "group_id": gid,
                  "prereg": a.prereg, "ts_knowable": ref["ts_knowable"], "bar_ts_open": ref.get("bar_ts_open"),
                  "bar_ts_close": ref["bar_ts_close"], "bars_known_count": ref["bars_known_count"],
                  "input_sha256": ref["input_sha256"], "n_inputs": len(inputs),
                  "synthetic_inputs": any(R._synthetic(b) for b in inputs), "cfg": dict(ref.get("cfg") or {}),
                  "params": PARAMS, "ts_recorded": now_iso(), "ts_recorded_source": "runner wall clock",
                  "outcome_in_snapshot_when_recorded": bool(later), "runner_version": RUNNER_VERSION}
            vf.update(d)
            ff.write(json.dumps(vf, sort_keys=True) + "\n")
            if not later:
                windows.append({"group_id": gid, "status": "pending", "ts_knowable": ref["ts_knowable"],
                                "forecast_id": vf["forecast_id"],
                                "note": "REVERT-1 forecast stored before any outcome bar; a later run can "
                                        "use this directory as --witness-dir"})
                continue
            cores = {name: S.compute_core(g[name], later) for name in BASES if name in g}
            cores[VARIANT] = S.compute_core(vf, later)
            w_stored = 0
            for name in BASES:   # recomputed baseline cores agree with the desk's stored v3 scores
                sc = st.scored.get(g[name]["forecast_id"]) if name in g else None
                if sc is not None and sc.get("score_version") == S.SCORE_VERSION:
                    stored_match["checked"] += 1
                    if any(sc.get(k) != cores[name].get(k) for k in ("kind", "net_bps", "net_bps_2x")):
                        stored_match["mismatch"] += 1
                        w_stored += 1
            syn = vf["synthetic_inputs"] or any(R._synthetic(b) for b in later)
            genuine = all(_genuine_iex(R, st.bars_by_sha([s])[0], st.bar_row(s))
                          for s in list(inp["bar_shas"]) + list(shas))
            base_witness = {}
            for name in BASES:
                if name in g:
                    ok, why = _stored_before_outcome(B, st, g[name].get("ts_recorded"), ref["bar_ts_close"],
                                                     later, shas)
                    base_witness[name] = {"stored_before_outcome": ok, "reason": why}
            wv, wv_why = False, "no earlier run stored this REVERT-1 forecast"
            prior = witnesses.get(vf["forecast_id"])
            if prior is not None:
                if any(prior.get(k) != vf.get(k) for k in ("input_sha256", "action", "qty", "reason_code")):
                    wv_why = "an earlier stored forecast differs from this decision"
                else:
                    wv, wv_why = _stored_before_outcome(B, st, prior.get("ts_recorded"), ref["bar_ts_close"],
                                                        later, shas)
            windows.append({
                "group_id": gid, "status": "scored", "forecast_id": vf["forecast_id"],
                "ts_knowable": ref["ts_knowable"], "bar_ts_close": ref["bar_ts_close"], "later_bar_shas": shas,
                "synthetic": syn, "genuine_iex": genuine,
                "signal_bar_after_freeze": B.parse_ts(ref["bar_ts_close"]) > B.parse_ts(PREREG_TS),
                "window_reproduction_mismatch": w_repro, "window_stored_score_mismatch": w_stored,
                "eligible": bool(cores[VARIANT].get("eligible")),
                "ineligible_reason": cores[VARIANT].get("ineligible_reason"),
                "signal_side": d["signal_side"], "reason_code": d["reason_code"], "cores": cores,
                "baseline_lab_forecast_witness": base_witness,
                "revert1_witness": {"stored_before_outcome": wv, "reason": wv_why}})

    integrity = []
    for k, v in sorted(chains.items()):
        if not v[0]:
            integrity.append("chain_broken:%s" % k)
    if repro["mismatch"]:
        integrity.append("baseline_reproduction_failed")
    if stored_match["mismatch"]:
        integrity.append("stored_score_mismatch")
    scored = [w for w in windows if w["status"] == "scored"]
    refusals = {}
    for w in scored:
        why = list(integrity)
        if w["window_reproduction_mismatch"]:
            why.append("window_reproduction_failed")
        if w["window_stored_score_mismatch"]:
            why.append("window_stored_score_mismatch")
        if w["synthetic"] or not w["genuine_iex"]:
            why.append("not_genuine_iex")
        if not w["signal_bar_after_freeze"]:
            why.append("signal_bar_not_after_freeze")
        if not w["eligible"]:
            why.append("scorer_ineligible")
        w["forward"] = not why
        w["forward_refusals"] = why
        w["evidence_class"] = ("NOT_FORWARD_EVIDENCE" if why else
                               "WITNESSED_FORWARD" if w["revert1_witness"]["stored_before_outcome"] else
                               "RECONSTRUCTED_OUT_OF_SAMPLE")
        for r in why:
            refusals[r] = refusals.get(r, 0) + 1
    with open(spath, "x", encoding="utf-8") as sf:
        for w in scored:
            sf.write(json.dumps(dict(w, score_version=S.SCORE_VERSION, rule_id=RULE_ID,
                                     label="HYPOTHETICAL shadow score; never realized P&L"),
                                sort_keys=True) + "\n")

    elig = [w for w in scored if w["eligible"]]
    per, paired = _metrics(elig)
    diag = {"label": "DIAGNOSTIC ONLY: signal side taken on gated passes, TEST-notional hypothetical",
            "net_bps": [], "net_bps_2x": []}
    for w in elig:
        c = w["cores"][VARIANT]
        hyp = c.get("hypothetical") or {}
        leg = hyp.get("if_long" if w["signal_side"] > 0 else "if_short") if w["signal_side"] else None
        if c["kind"] == "pass/flat" and leg:
            diag["net_bps"].append(leg["net_bps"])
            diag["net_bps_2x"].append(leg["net_bps_2x"])
    diag = {"label": diag["label"], "net_bps": _stats(diag["net_bps"]), "net_bps_2x": _stats(diag["net_bps_2x"])}
    fwd = [w for w in scored if w["forward"]]
    fwd_per, fwd_paired = _metrics(fwd)
    fwd_trades = sum(1 for w in fwd if w["cores"][VARIANT]["kind"] == "trade")
    fwd_sessions = len({w["bar_ts_close"][:10] for w in fwd})
    witnessed = [w for w in fwd if w["evidence_class"] == "WITNESSED_FORWARD"]
    base_wit = {n: sum(1 for w in fwd if (w["baseline_lab_forecast_witness"].get(n) or {}).get(
        "stored_before_outcome")) for n in BASES}
    if integrity:
        status = ("REFUSED: integrity check failed (%s); no window counts as forward evidence"
                  % ", ".join(integrity))
    elif not fwd:
        status = "NO FORWARD EVIDENCE: execution proof or context only"
    elif fwd_trades == 0:
        status = ("FORWARD WINDOWS OBSERVED, ZERO FORWARD REVERT-1 TRADES: no evidence for or against H1 yet")
    else:
        status = ("OUT-OF-SAMPLE EVIDENCE (counts toward the prereg): %d reconstructed, %d witnessed windows"
                  % (len(fwd) - len(witnessed), len(witnessed)))
    reasons, gates = {}, {}
    for w in scored:
        if not w["eligible"]:
            reasons[w["ineligible_reason"]] = reasons.get(w["ineligible_reason"], 0) + 1
        gates[w["reason_code"]] = gates.get(w["reason_code"], 0) + 1
    loaded = sorted(m for m, mod in list(sys.modules.items())
                    if getattr(mod, "__file__", None) and os.path.realpath(mod.__file__).startswith(desk + os.sep))
    forbidden_loaded = sorted(m for m in FORBIDDEN if m in sys.modules)
    summary = {
        "label": a.label, "prereg": a.prereg, "prereg_ts": PREREG_TS, "rule_id": RULE_ID, "params": PARAMS,
        "runner_version": RUNNER_VERSION, "runner_sha256": sha256_file(os.path.abspath(__file__)),
        "run": {"started": started, "out_dir": os.path.basename(out), "fresh_out_dir": True},
        "state_dir_snapshot": st.snap, "partial_tail_ignored": st.partial, "hash_chains": chains,
        "windows": {"groups": len(groups), "scored": len(scored), "eligible": len(elig),
                    "ineligible": len(scored) - len(elig),
                    "pending": sum(1 for w in windows if w["status"] == "pending"),
                    "inputs_unverifiable": sum(1 for w in windows if w["status"] == "inputs_unverifiable"),
                    "synthetic_scored": sum(1 for w in scored if w["synthetic"]),
                    "ineligible_reasons": reasons, "revert1_reason_codes": gates},
        "rows_excluded": dict(excluded, note="only lab rows marked shadow and never_routed are read; broker, "
                                             "order and probe logs are never opened", broker_probes_counted=0),
        "lab_decisions_reproduced": repro, "baseline_cores_vs_stored_v3_scores": stored_match,
        "per_strategy_eligible": per, "paired_on_identical_eligible_windows": paired, "diagnostic": diag,
        "revert1_side_split_eligible": _sides(elig),
        "evidence": {"integrity_failures": integrity, "forward_refusals": refusals,
                     "forward_eligible_windows": len(fwd), "forward_trades": fwd_trades,
                     "forward_sessions": fwd_sessions,
                     "reconstructed_out_of_sample_windows": len(fwd) - len(witnessed),
                     "witnessed_forward_windows": len(witnessed),
                     "witnessed_forward_trades": sum(1 for w in witnessed
                                                     if w["cores"][VARIANT]["kind"] == "trade"),
                     "baseline_lab_forecasts_stored_before_outcome": base_wit,
                     "witness_dirs": witness_report,
                     "revert1_side_split_forward": _sides(fwd),
                     "per_strategy_forward": fwd_per, "paired_forward": fwd_paired,
                     "status": status,
                     "verdict_look_allowed": (not integrity) and (fwd_trades >= 30 or fwd_sessions >= 20)},
        "zero_orders": {"network": "socket connect patched to raise", "forbidden_modules_loaded": forbidden_loaded,
                        "desk_modules_loaded": loaded, "wrote_only": [os.path.basename(p) for p in (fpath, spath)]
                        + ["summary.json"]},
        "outputs": {OUT_FILES[0]: sha256_file(fpath), OUT_FILES[1]: sha256_file(spath)},
    }
    if forbidden_loaded:
        raise SystemExit("refused: order-capable module loaded: %s" % forbidden_loaded)
    sumpath = os.path.join(out, "summary.json")
    with open(sumpath, "x", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    print(json.dumps({"out": out, "summary_sha256": sha256_file(sumpath), "outputs": summary["outputs"],
                      "windows": summary["windows"], "revert1": per[VARIANT],
                      "paired": {k: {"n": v["net_bps_2x"]["n"], "mean_2x": v["net_bps_2x"]["mean"],
                                     "t_2x": v["net_bps_2x"]["t"]} for k, v in paired.items()},
                      "evidence": {k: summary["evidence"][k] for k in (
                          "status", "integrity_failures", "forward_refusals", "forward_eligible_windows",
                          "forward_trades", "reconstructed_out_of_sample_windows", "witnessed_forward_windows",
                          "verdict_look_allowed")},
                      "side_split_eligible": summary["revert1_side_split_eligible"],
                      "reproduced": repro, "stored_match": stored_match,
                      "chains_ok": {k: v[0] for k, v in chains.items()},
                      "forbidden_modules_loaded": forbidden_loaded, "desk_modules_loaded": loaded}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
