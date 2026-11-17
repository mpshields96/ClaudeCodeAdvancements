"""One trading profile shared by the connected SPY desks: Balanced DNA / Moderate risk.

Balanced pace (medium patience): the desk decides only on closed 1-hour bars, checks for a new
signal about every 60 s, re-checks fills and protective-stop coverage about every 30 s, and takes
a new entry only on a quote at most 30 s old and a bar at most 15 minutes past its close.

Moderate risk, sized from each account's own uncommitted cash on every new buy:
- available = min(cash, equity, non-margin buying power[, buying power]) minus every working buy;
  margin never adds to it (alpaca/sizing.available_cash).
- size = SHARES_PER_USD x available, floored to 9 decimals (fractional desks) or a whole share.
- Paper has its own scale: the four dollar caps are recomputed from the same available cash on
  every entry (notional and gross NOTIONAL_FRACTION, price risk to the stop STOP_RISK_FRACTION,
  daily loss including fees DAILY_LOSS_FRACTION), the size is cut to fit the notional and stop
  caps, and cost and risk are recalculated on the resulting quantity. Paper keeps its own daily
  entry count (its worksheet's, else PAPER_MAX_DAILY_ENTRIES).
- Live keeps the operator's signed absolutes: the size is never above the approved size, and the
  approved dollar caps, entry count and stop rules are unchanged.
- A size the venue cannot take (zero, or a fraction under the $1 minimum) is an explicit pass.

The profile never starts, arms or activates a desk. Stdlib only (Python 3.9).
"""
from decimal import Decimal, ROUND_FLOOR

PROFILE_ID = "balanced-moderate"
LABEL = "Balanced DNA / Moderate risk"
VERSION = 1

# Pace (Balanced)
BAR_MINUTES = 60
SIGNAL_CHECK_S = 60
PROTECT_CHECK_S = 30
MAX_QUOTE_AGE_S = 30
BAR_MAX_AGE_S = 900

# Wind-down before the close. An arm ends WIND_DOWN_S before the regular close (the desk calendar's,
# early closes included), so the reduce-only Stop & Close goes out while the venue still takes a
# fractional DAY order, with time for Check retries before the bell. After the arm ends the funded
# supervisor keeps reconciling for at most RECONCILE_S (reduce-only; no entry, never re-arms) until
# the broker confirms flat, else it hands over an explicit unresolved state.
WIND_DOWN_S = 900
RECONCILE_S = 900

# Risk (Moderate), per dollar of available cash
SHARES_PER_USD = Decimal("0.000028")
NOTIONAL_FRACTION = Decimal("0.023")
GROSS_FRACTION = Decimal("0.023")
STOP_RISK_FRACTION = Decimal("0.0004")
DAILY_LOSS_FRACTION = Decimal("0.001")
PAPER_MAX_DAILY_ENTRIES = 4

CENT = Decimal("0.01")


def _floor_cents(d):
    return float(Decimal(d).quantize(CENT, rounding=ROUND_FLOOR))


def paper_caps(available):
    """The four paper dollar caps for this much available cash, floored to cents."""
    a = Decimal(available)
    return {"per_trade_notional": _floor_cents(a * NOTIONAL_FRACTION),
            "gross_exposure": _floor_cents(a * GROSS_FRACTION),
            "max_loss_per_trade": _floor_cents(a * STOP_RISK_FRACTION),
            "daily_loss": _floor_cents(a * DAILY_LOSS_FRACTION)}


def describe(mode):
    """The operative profile as plain data for session state, controls and decision evidence.
    mode is "paper" (own scale) or "live" (signed absolutes)."""
    paper = mode == "paper"
    return {
        "id": PROFILE_ID, "label": LABEL, "version": VERSION, "mode": mode,
        "pace": {"bars": "closed %d-minute bars only" % BAR_MINUTES, "signal_check_s": SIGNAL_CHECK_S,
                 "protect_check_s": PROTECT_CHECK_S, "max_quote_age_s": MAX_QUOTE_AGE_S,
                 "bar_max_age_s": BAR_MAX_AGE_S, "wind_down_s": WIND_DOWN_S, "reconcile_s": RECONCILE_S},
        "risk": {"shares_per_usd_available": str(SHARES_PER_USD),
                 "caps": ("recomputed from available cash on every entry: notional and gross %s%%, "
                          "stop price risk %s%%, daily loss incl. fees %s%%"
                          % (NOTIONAL_FRACTION * 100, STOP_RISK_FRACTION * 100, DAILY_LOSS_FRACTION * 100))
                 if paper else "operator-approved signed absolutes, unchanged",
                 "size": ("profile size from available cash, cut to fit the notional and stop caps"
                          if paper else "the smaller of the approved size and the profile size")},
        "daily_entries": ("paper worksheet's count, else %d" % PAPER_MAX_DAILY_ENTRIES) if paper
        else "approved count, unchanged",
        "summary": ("%s: closed 1-hour bars, checks every %ds, protection every %ds; size %s shares per "
                    "available dollar%s" % (LABEL, SIGNAL_CHECK_S, PROTECT_CHECK_S, SHARES_PER_USD,
                                            ", paper caps rescaled each entry" if paper
                                            else ", never above the approved size or caps")),
    }
