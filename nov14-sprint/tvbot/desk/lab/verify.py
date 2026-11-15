"""verify(state_dir, forecast_id): recompute one lab forecast from its stored records.

Returns {"ok", "forecast_id", "checks": [{id, passed, detail}], "before", "after", "inputs"}.
`passed` is True, False, or None for a check that cannot run yet (SCORE before the
later bars exist). ok is True only when no check failed and the forecast exists.
"""
from strategies import base as B
from strategies import challenger as CH

from . import record as R
from . import score as S


def _check(cid, passed, detail):
    return {"id": cid, "passed": passed, "detail": detail}


def verify(state_dir, forecast_id):
    st = R.Store(state_dir)
    f = st.forecast_index.get(forecast_id)
    if f is None:
        return {"ok": False, "forecast_id": forecast_id, "before": None, "after": None,
                "checks": [_check("FOUND", False, "no forecast with this id")]}
    checks = [_check("FOUND", True, "forecast row %d of %d" % (st.rows["forecasts"].index(f) + 1,
                                                              len(st.rows["forecasts"])))]
    fi = st.rows["forecasts"].index(f)
    ok, det = R.check_chain(st.rows["forecasts"], fi)
    checks.append(_check("CHAIN", ok, "forecasts: " + det))
    bok, bdet = R.check_chain(st.rows["bars"])
    checks.append(_check("BAR_STORE_CHAIN", bok, "bars: " + bdet))

    inp = st.input_index.get(f["input_sha256"])
    bars = st.bars_by_sha(inp["bar_shas"]) if inp else []
    good = bool(inp) and None not in bars and all(R.bar_sha(b) == s for b, s in zip(bars, inp["bar_shas"]))
    good = good and R.input_sha(bars) == f["input_sha256"] and len(bars) == f["n_inputs"]
    checks.append(_check("INPUT_HASH", good, "sha256 of %d stored input bars %s the recorded %s"
                         % (len(bars), "matches" if good else "does NOT match", f["input_sha256"][:16])))

    if good:
        last = bars[-1]
        cut = B.parse_ts(last["ts_close"])
        kn = (B.ts_knowable(last) == f["ts_knowable"] and last.get("ts_close") == f["bar_ts_close"]
              and all(B.parse_ts(b["ts_close"]) <= cut for b in bars)
              and max(st.bar_index.get(s, 10 ** 9) for s in inp["bar_shas"]) < f["bars_known_count"])
        checks.append(_check("KNOWABLE", kn, "inputs close by %s; knowable %s; all inputs were in the store "
                             "before the forecast row" % (f["bar_ts_close"], f["ts_knowable"])))
        try:
            d = R.run_decision(f["strategy"], bars, f.get("cfg") or {}, f["now"])
            same = R.sha(d) == f["decision_sha"] and d.get("action") == f["action"]
            checks.append(_check("DECISION", same, "re-ran %s on the stored bars: %s %s (recorded %s)"
                                 % (f["strategy"], d.get("action"), d.get("reason_code"), f["action"])))
        except Exception as exc:
            checks.append(_check("DECISION", False, "re-run raised %s" % exc.__class__.__name__))
    else:
        checks.append(_check("KNOWABLE", False, "inputs missing or altered"))
        checks.append(_check("DECISION", False, "cannot re-run on altered inputs"))

    if f["strategy"] == "challenger":
        fr = f.get("cfg_hash") == CH.CFG_HASH and f.get("rule_id") == CH.RULE_ID and f.get("frozen_at") == CH.FROZEN_AT
        checks.append(_check("FROZEN", fr, "challenger %s frozen %s cfg %s (recorded cfg %s)"
                             % (CH.RULE_ID, CH.FROZEN_AT, CH.CFG_HASH, f.get("cfg_hash"))))

    sc = st.scored.get(forecast_id)
    if sc is None:
        later, _ = S.later_bars(st, f)
        checks.append(_check("LATER_ONLY", None, "not scored yet: %s" % (
            "later bars exist; scoring runs at the next observe" if later else "waiting for the next closed bar")))
        checks.append(_check("SCORE", None, "pending"))
    else:
        sok, sdet = R.check_chain(st.rows["scores"], st.rows["scores"].index(sc))
        checks.append(_check("SCORE_CHAIN", sok, "scores: " + sdet))
        later, shas = S.later_bars(st, f, horizon=sc["horizon_bars"])
        lo = (shas == sc["later_bar_shas"] and later == sc["later_bars"]
              and all(B.parse_ts(b["ts_close"]) > B.parse_ts(f["ts_knowable"]) for b in sc["later_bars"])
              and all(st.bar_index.get(s, -1) >= f["bars_known_count"] for s in sc["later_bar_shas"])
              and sc.get("forecast_row_hash") == f["row_hash"])
        checks.append(_check("LATER_ONLY", lo, "%d later bar(s) closing after %s, all stored after the forecast"
                             % (len(sc["later_bars"]), f["ts_knowable"])))
        core = S.compute_core(f, sc["later_bars"])
        same = all(core[k] == sc.get(k) for k in S.CORE_KEYS)
        if same and f["strategy"] == "challenger":
            e = st.forecast_index.get("fc-ema-%s" % f["group_id"][4:])
            cmp_ = S.comparison(core, None if e is None else S.compute_core(e, sc["later_bars"]))
            same = all(sc.get(k) == v for k, v in cmp_.items())
        checks.append(_check("SCORE", same, "recomputed net %s bps (2x friction %s) %s the stored score"
                             % (core["net_bps"], core["net_bps_2x"], "matches" if same else "does NOT match")))
    failed = [c for c in checks if c["passed"] is False]
    return {"ok": not failed, "forecast_id": forecast_id, "label": R.SCORE_LABEL,
            "checks": checks, "before": f, "after": sc,
            "inputs": {"n": len(bars), "first_ts_open": bars[0]["ts_open"] if bars and bars[0] else None,
                       "last": bars[-1] if bars and bars[-1] else None}}
