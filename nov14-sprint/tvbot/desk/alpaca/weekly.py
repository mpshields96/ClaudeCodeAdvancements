"""Render the selected SPY paper week from its closed fill ledger and session snapshot."""
from html import escape
from math import isfinite
from pathlib import Path


def text(value):
    return escape(str(value), quote=True)


def dollars(amount):
    if amount is None:
        return "Unavailable"
    return ("−" if amount < 0 else "") + "${:,.2f}".format(abs(amount))


def compact(value, width=210):
    words = " ".join(str(value or "").split())
    return text(words if len(words) <= width else words[:width - 1].rsplit(" ", 1)[0] + "…")


def fill_economics(trips):
    """Charge the sensitivity once per unique filled order, including partial executions."""
    gross = 0.0
    filled_orders = set()
    for trip in trips:
        amount = trip.get("gross_pnl")
        if isinstance(amount, bool) or not isinstance(amount, (float, int)) or not isfinite(amount):
            return None, None
        gross += amount
        fills = trip.get("fills") or []
        if not fills or any(not fill.get("intent_id") for fill in fills):
            return None, None
        filled_orders.update(fill["intent_id"] for fill in fills)
    return gross, gross - len(filled_orders)


def chart(gross, stress):
    amounts = [("Closed fills", gross), ("With $1 per filled order", stress), ("Stay in cash", 0.0)]
    scale = max([abs(v) for _, v in amounts if v is not None] + [0.01])
    rows = []
    for name, value in amounts:
        width = 0.0 if value is None else abs(value) / scale * 48.0
        side = "right:50%;background:#90521e" if (value or 0) < 0 else "left:50%;background:#216b69"
        rows.append('<div class="chartrow"><span>{}</span><div class="track"><i style="width:{:.3f}%;{}"></i></div><b>{}</b></div>'.format(
            text(name), width, side, dollars(value)))
    return "".join(rows)


def trip_line(trip):
    if not trip:
        return "No closed trade."
    stamp = str(trip.get("entry_ts") or "Time unavailable").replace("T", " ")
    result = dollars(trip.get("gross_pnl"))
    kind = {"exit": "strategy exit", "close": "close order", "protective": "protective stop"}.get(trip.get("exit_kind"), "exit recorded")
    return "{} before fees · {} · {}".format(text(result), compact(stamp, 31), kind)


def week_pass(state_dir, bw, week):
    from report import iso_week, read_jsonl
    rows = [row for row in read_jsonl(Path(state_dir) / "decisions.jsonl")
            if row.get("action") == "pass" and iso_week(row.get("bar_ts_close") or row.get("ts_knowable")) == week]
    observed = [row for row in rows if not str(row.get("reason_code") or "").startswith(("WARMUP", "DATA_REJECTED_"))]
    history_count = len(rows) - len(observed)
    if observed:
        def failed_checks(row):
            return sum(1 for check in row.get("refusal_checks", []) if check.get("passed") is False)
        return max(observed, key=failed_checks), history_count
    if rows:
        return {}, history_count
    return (bw.get("best_pass") or {}).get("decision") or {}, 0


def shadow_activity(state_dir):
    # The normal lab view safely reads its recorded inputs and the later scores.
    if not (Path(state_dir) / "lab_forecasts.jsonl").is_file():
        return "No forecasts have been recorded in the shadow lab."
    from lab.record import view
    try:
        tally = (view(str(state_dir), limit=0).get("totals") or {}).get("challenger", {})
        return "{} challenger forecasts recorded, {} with later scores. Open Decision lab to replay the evidence.".format(
            int(tally.get("forecasts", 0)), int(tally.get("scored", 0)))
    except (OSError, ValueError, KeyError, TypeError):
        return "Shadow records could not be read. Use Verify in the decision lab."


def render_week(state_dir, session, bw, week):
    """A complete print view. Session status is explicitly current, economics weekly."""
    mode = session.get("broker_mode")
    if mode not in ("alpaca-paper", "alpaca-mock"):
        raise ValueError("expected an Alpaca paper or local rehearsal session")
    connected = mode == "alpaca-paper"
    title = "SPY paper week" if connected else "SPY rehearsal week"
    source = ("Alpaca paper simulator fills · free IEX market data" if connected
              else "Local rehearsal · synthetic SPY bars and fills")
    trades = bw.get("round_trips") or []
    gross, stress = fill_economics(trades)
    comparison = {r.get("metric"): r.get("value") for r in bw.get("comparison", [])}
    passes = comparison.get("passes", 0)
    decisions = comparison.get("decisions", 0)
    if trades:
        decision = "{} closed round trip{}. The filled-price result was {} before fees.".format(
            len(trades), "" if len(trades) == 1 else "s", dollars(gross))
    else:
        decision = "No round trip closed during the selected period."
    decision += " The desk recorded {} passes across {} decisions.".format(passes, decisions)
    best = bw.get("best_trade")
    worst = bw.get("worst_trade")
    if len(trades) > 1 and best and best == worst:
        # Use a second example when multiple trades tie at the same result.
        for candidate in reversed(trades):
            if candidate != best and candidate.get("net_pnl") == best.get("net_pnl"):
                worst = candidate
                break
    pass_record, history_count = week_pass(state_dir, bw, week)
    if history_count:
        decision += " {} pass rows reflect warm-up or data checks.".format(history_count)
    if pass_record:
        why = pass_record.get("reason_text") or pass_record.get("reason_code") or "Reason unavailable."
        best_pass = compact(why) + " · " + compact(pass_record.get("bar_ts_close") or pass_record.get("ts_knowable") or "Time unavailable", 38)
    else:
        best_pass = "Only warm-up or data checks were recorded." if history_count else "No pass was recorded in this period."
    controls = session.get("controls") or {}
    stop = "No active Stop in the latest snapshot."
    if controls.get("stopped"):
        stop = ("Stop active · venue confirmed flat." if controls.get("flat_confirmed") is True
                else "Stop active · closing or awaiting broker confirmation.")
    limits = session.get("limits") or {}
    size = (session.get("sizing") or {}).get("fixed_qty")
    source_record = session.get("limits_source") or {}
    provenance = source_record.get("provenance") or "unknown"
    snapshot_id = str(source_record.get("hash") or "")[:12]
    cap_text = " · ".join("{} {}".format(label, dollars(limits.get(field))) for label, field in (
        ("Order", "per_trade_notional"), ("Stop risk", "max_loss_per_trade"), ("Gross", "gross_exposure"), ("Day loss", "daily_loss")))
    refusal = len(bw.get("refused_decisions") or [])
    alarms = session.get("alarms") or []
    alarm = ("Latest alarm " + compact(str(alarms[-1].get("code") or "see desk"), 48)) if alarms and isinstance(alarms[-1], dict) else ""
    same = "One closed trade occupies both rankings." if len(trades) == 1 else ""
    return """<!doctype html><html lang="en"><meta charset="utf-8"><title>{title}</title><style>
    @page {{size:letter;margin:0.48in 0.56in}} * {{box-sizing:border-box}} body {{max-width:740px;margin:auto;color:#1b2934;background:#fcfaf5;font:14px/1.37 -apple-system,Arial,sans-serif;print-color-adjust:exact;-webkit-print-color-adjust:exact}}
    header {{display:flex;justify-content:space-between;border-bottom:1px solid #b9c8c8;padding:4px 0 9px}} header,b.over {{color:#166983;font:700 10px/1.4 Arial,sans-serif;letter-spacing:1.5px;text-transform:uppercase}}
    h1 {{font:42px/1.06 Georgia,serif; margin:13px 0 3px}} h2 {{font:22px/1.13 Georgia,serif;margin:15px 0 7px}}
    p {{margin:5px 0}} .sub,small {{color:#455966}} .decision {{margin:13px 0 12px;padding:10px 13px;background:#e6eff0;border-left:4px solid #166983}}
    .chartrow {{display:grid;grid-template-columns:157px 1fr 92px;align-items:center;min-height:23px;gap:10px}} .chartrow b {{text-align:right;font-variant-numeric:tabular-nums}}
    .track {{height:20px;position:relative;background:linear-gradient(to right,transparent 49.8%,#b5c2c0 49.8%,#b5c2c0 50.2%,transparent 50.2%)}} .track i {{position:absolute;top:5px;height:10px}}
    .facts {{display:grid;grid-template-columns:116px 1fr;border-top:1px solid #cbd3d2}} .facts b,.facts div {{padding:6px 1px;border-bottom:1px solid #d9dfdb}} .facts b {{color:#435867}}
    footer {{margin-top:14px;border-top:1px solid #c5cfcc;padding-top:6px;color:#516570;font-size:11px}}
    @media screen {{body {{padding:2.7vw 20px}}}} @media(max-width:520px) {{.chartrow {{grid-template-columns:103px 1fr 70px}} .facts {{grid-template-columns:86px 1fr}}}}
    </style><header><span>Trading desk / weekly review</span><span>{week}</span></header>
    <h1>{title}</h1><p class="sub">{source}</p><div class="decision"><b class="over">Week in brief</b><p>{decision}</p></div>
    <h2>Closed trades against cash</h2>{chart}<p><small>Filled prices include simulated execution. The $1 sensitivity is charged once per filled order, including orders filled in parts. Account fees are unverified. Open positions are excluded.</small></p>
    <h2>Trade and pass replay</h2><div class="facts"><b>Best trade</b><div>{best}</div><b>Worst trade</b><div>{worst} {same}</div><b>Selected pass</b><div>{best_pass}</div></div>
    <h2>Limits and Stop</h2><div class="facts"><b>Weekly refusals</b><div>{refusal} decisions refused by the desk risk check.</div><b>Latest state</b><div>{stop} {alarm}</div>
    <b>Loaded sizing</b><div>{size} {unit} · {provenance} {snapshot}</div><b>Dollar limits</b><div>{caps}</div><b>Session shadow lab</b><div>{shadow}</div></div>
    <footer>Latest session snapshot {asof}. The selected week groups closed trips by entry week. Detailed fill and refusal records are available in the desk ledger.</footer></html>""".format(
        title=title, week=text(week or "No recorded week"), source=source, decision=text(decision),
        chart=chart(gross, stress), best=trip_line(best), worst=trip_line(worst), same=same,
        best_pass=best_pass, refusal=refusal, stop=stop, alarm=alarm, size=text(size if size is not None else "Unavailable"),
        unit="share" if size == 1 else "shares", provenance=text(provenance), snapshot=text(snapshot_id), caps=text(cap_text), shadow=text(shadow_activity(state_dir)), asof=compact(session.get("updated_utc") or "unavailable", 38))
