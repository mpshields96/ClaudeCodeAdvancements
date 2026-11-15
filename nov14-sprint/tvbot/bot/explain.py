"""Plain-English explanation of each decision, built only from numbers the
engine already computed. No model is called here or anywhere in this runner.

There is also an optional hook: a person may later ask a Claude chat to write
commentary on a decision and save it as claude_notes/<decision_id>.md inside
the state folder. The engine never opens that folder. Only the `explain`
command reads it, and it prints the note under a warning label. Text from an
assistant can describe a decision. It cannot make one or approve a fill.
"""
import os

NOTE_DIR = "claude_notes"
NOTE_LABEL = ("Commentary written by a chat assistant. Unverified. It was not used to "
              "make this decision and it cannot approve, change or trigger any order.")


def money(x):
    return "{:,.2f}".format(x)


def _px(x):
    return "n/a" if x is None else "{:.4f}".format(x)


def _when(d):
    ready = d.get("decision_ready_ts")
    if not ready:
        return "It can fill only at the open of a later bar"
    return ("The bar arrived at %s and the decision was ready at %s. The order can fill only "
            "at the open of the first bar that opens at or after that moment"
            % (d.get("available_ts"), ready))


def explain(d):
    """Return one paragraph for a decision record."""
    i = d["inputs"]
    head = "Bar %d of %s closed at %s on %s." % (
        d["bar_seq"], d["symbol"], _px(i["close"]), d["signal_ts"])
    avg = "The fast average is %s and the slow average is %s (one bar earlier: %s and %s)." % (
        _px(i["ema_fast"]), _px(i["ema_slow"]), _px(i["prev_ema_fast"]), _px(i["prev_ema_slow"]))
    rule = "Rule %s." % d["rule_id"]
    a, r = d["action"], d["reason_code"]
    if a == "ENTER_LONG":
        o = d["order"]
        body = ("The fast average crossed above the slow average on this closed bar and no "
                "position was open, which is the long setup. Risk checks passed: %d shares at "
                "about %s is %s, inside the position limit of %s; day profit and loss is %s "
                "against a daily loss limit of %s. A paper buy order for %d shares was recorded. "
                "%s, with spread, slippage and commission added. It never uses this bar's "
                "close or any price that printed before the decision was ready."
                % (o["qty"], _px(i["close"]), money(o["qty"] * i["close"]),
                   money(i["limit_position_notional"]), money(i["day_pnl"]),
                   money(i["limit_daily_loss"]), o["qty"], _when(d)))
    elif a == "EXIT_LONG":
        why = {
            "stop": "the bar closed at or below the stop level of %s (entry open %s minus the "
                    "stop percent)" % (_px(i["stop_level"]), _px(i["entry_ref"])),
            "cross_down": "the fast average crossed below the slow average and the stop was not hit",
            "daily_loss_limit": "the day's loss of %s reached the daily loss limit of %s"
                                % (money(-i["day_pnl"]), money(i["limit_daily_loss"])),
            "data_gap": "bars went missing while the position was open, so the averages can "
                        "no longer be trusted and the position is closed",
        }.get(r, r)
        body = ("A paper position of %d shares was open and %s. A paper sell order was "
                "recorded. %s, with costs taken off."
                % (i["position_qty"], why, _when(d)))
    elif a == "BLOCKED":
        body = ("The long setup appeared, but the risk check refused the order: %s. Nothing "
                "was ordered. An order that breaks a limit is refused in full, not trimmed."
                % d.get("risk_detail", r))
    elif a == "HOLD":
        if r == "order_pending":
            body = "An earlier paper order is still waiting for its fill bar, so nothing new is decided."
        else:
            body = ("A paper position of %d shares is open. The stop level is %s and the close "
                    "is above it, and the fast average has not crossed below the slow one. "
                    "Nothing to do." % (i["position_qty"], _px(i["stop_level"])))
    else:  # STAND_ASIDE
        if r == "warmup":
            body = ("Only %d bars have been seen since the last reset and the rule needs %d "
                    "before it may act. Standing aside." % (i["bars_since_reset"], i["warmup_bars"]))
        else:
            body = "No position is open and the fast average did not cross above the slow one. Standing aside."
    return " ".join([head, avg, rule, body])


def note_path(state_dir, decision_id):
    return os.path.join(state_dir, NOTE_DIR, "%s.md" % decision_id)


def read_note(state_dir, decision_id):
    """Used by the `explain` command only. Never called by the engine."""
    p = note_path(state_dir, decision_id)
    if not os.path.isfile(p):
        return None
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def build_packet(decisions, rid):
    """A text file a person can hand to a Claude chat later. It holds only
    code-computed numbers. Nothing here calls a model."""
    lines = [
        "# Decision packet for rule %s" % rid,
        "",
        "For a person to give to a Claude chat, if they want commentary. Optional.",
        "Every number below was computed in code from synthetic or permitted bars.",
        "Ask for plain-English commentary only. Do not ask for, and do not accept, new",
        "numbers, signals or approvals. Save any commentary as",
        "`claude_notes/<decision_id>.md` in the state folder. The runner never reads it.",
        "",
    ]
    for d in decisions:
        if d["action"] in ("ENTER_LONG", "EXIT_LONG", "BLOCKED"):
            lines.append("## %s  %s  (%s)" % (d["decision_id"], d["action"], d["reason_code"]))
            lines.append("")
            lines.append(d["explanation"])
            lines.append("")
    return "\n".join(lines) + "\n"
