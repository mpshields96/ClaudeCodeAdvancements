"""Mechanical NFL rule definitions shared by backtest.py and paper_ledger.py.

Pure functions, standard library only, Python 3.9 compatible.
Pre-registration text: RULES.md (written before the first backtest run).

Foreknowledge boundary: decide() reads only fields that are known before
kickoff: the spread line, the total line, and each team's rest days (a
schedule fact). It never reads scores, results, weather or QB fields.

Line convention (nflverse games.csv): spread_line > 0 means the HOME team
is favored by that many points. result = home_score - away_score.
  home bet covers  if result - spread_line > 0
  away bet covers  if result - spread_line < 0
  push             if result - spread_line == 0
"""

RULESET_VERSION = "v1"

# family -> market, parameter name, pre-registered variant grid
FAMILIES = {
    "HOME_DOG": {
        "market": "spread",
        "param": "T",
        "grid": [1.0, 3.0, 7.0],
        "desc": "Bet the HOME team against the spread when it is an underdog "
                "of at least T points (spread_line <= -T).",
    },
    "BIG_DOG": {
        "market": "spread",
        "param": "T",
        "grid": [7.0, 10.0, 14.0],
        "desc": "Bet the UNDERDOG (home or away) against the spread when the "
                "spread is at least T points (abs(spread_line) >= T).",
    },
    "REST_EDGE": {
        "market": "spread",
        "param": "D",
        "grid": [3, 6],
        "desc": "Bet the team with at least D more rest days than its "
                "opponent, against the spread.",
    },
    "HIGH_TOTAL_UNDER": {
        "market": "total",
        "param": "T",
        "grid": [47.0, 50.0],
        "desc": "Bet UNDER the total when total_line >= T.",
    },
}

FAMILY_ORDER = ["HOME_DOG", "BIG_DOG", "REST_EDGE", "HIGH_TOTAL_UNDER"]


def version_id(family, value):
    """Stable id for one variant, e.g. HOME_DOG-v1.T3 or REST_EDGE-v1.D6."""
    spec = FAMILIES[family]
    return "%s-%s.%s%g" % (family, RULESET_VERSION, spec["param"], float(value))


def all_variants():
    """Every pre-registered (family, value, version_id), in a fixed order."""
    out = []
    for fam in FAMILY_ORDER:
        for v in FAMILIES[fam]["grid"]:
            out.append((fam, v, version_id(fam, v)))
    return out


def _need(g, key):
    v = g.get(key)
    if v is None:
        raise ValueError("missing input: %s" % key)
    return v


def decide(family, value, g):
    """Decide take or pass for one game.

    g: dict with spread_line (float), total_line (float), away_rest (int),
       home_rest (int). Only the fields the family needs must be present;
       a needed field that is None raises ValueError("missing input: ...").

    Returns dict:
      action  "take" or "pass"
      market  "spread" or "total"
      side    "home" / "away" / "under", or None when the rule has no side
              for this game. For a pass, side is the rule's default side
              (the shadow side) so passes can be scored too.
      line    the line the bet is priced against (spread_line or total_line,
              exactly as given in the input)
      reason  short text
    """
    if family not in FAMILIES:
        raise KeyError("unknown rule family: %s" % family)
    value = float(value)

    if family == "HOME_DOG":
        sl = float(_need(g, "spread_line"))
        take = sl <= -value
        return {
            "action": "take" if take else "pass",
            "market": "spread", "side": "home", "line": sl,
            "reason": "home is +%g, threshold +%g" % (-sl, value) if sl < 0
            else "home is not an underdog (spread_line %g)" % sl,
        }

    if family == "BIG_DOG":
        sl = float(_need(g, "spread_line"))
        if sl == 0:
            return {"action": "pass", "market": "spread", "side": None,
                    "line": sl, "reason": "pick'em, no underdog"}
        side = "away" if sl > 0 else "home"
        take = abs(sl) >= value
        return {
            "action": "take" if take else "pass",
            "market": "spread", "side": side, "line": sl,
            "reason": "%s is +%g, threshold +%g" % (side, abs(sl), value),
        }

    if family == "REST_EDGE":
        sl = float(_need(g, "spread_line"))
        ar = int(_need(g, "away_rest"))
        hr = int(_need(g, "home_rest"))
        diff = hr - ar
        if diff == 0:
            return {"action": "pass", "market": "spread", "side": None,
                    "line": sl, "reason": "equal rest"}
        side = "home" if diff > 0 else "away"
        take = abs(diff) >= value
        return {
            "action": "take" if take else "pass",
            "market": "spread", "side": side, "line": sl,
            "reason": "%s has %d more rest days, threshold %g"
                      % (side, abs(diff), value),
        }

    # HIGH_TOTAL_UNDER
    tl = float(_need(g, "total_line"))
    take = tl >= value
    return {
        "action": "take" if take else "pass",
        "market": "total", "side": "under", "line": tl,
        "reason": "total %g, threshold %g" % (tl, value),
    }


def grade(market, side, line, home_score, away_score):
    """Grade a bet against the line it was priced at. Returns win/loss/push.

    spread: line is spread_line (home favored when positive).
    total:  line is total_line.
    moneyline: line is ignored; a tie is a push.
    """
    hs = float(home_score)
    as_ = float(away_score)
    if market == "spread":
        m = (hs - as_) - float(line)
        if m == 0:
            return "push"
        if side == "home":
            return "win" if m > 0 else "loss"
        if side == "away":
            return "win" if m < 0 else "loss"
        raise ValueError("bad spread side: %r" % (side,))
    if market == "total":
        t = (hs + as_) - float(line)
        if t == 0:
            return "push"
        if side == "over":
            return "win" if t > 0 else "loss"
        if side == "under":
            return "win" if t < 0 else "loss"
        raise ValueError("bad total side: %r" % (side,))
    if market == "moneyline":
        if hs == as_:
            return "push"
        if side == "home":
            return "win" if hs > as_ else "loss"
        if side == "away":
            return "win" if as_ > hs else "loss"
        raise ValueError("bad moneyline side: %r" % (side,))
    raise ValueError("unknown market: %r" % (market,))


def american_profit(price, stake=1.0):
    """Profit on a winning bet of `stake` at American odds `price`."""
    p = float(price)
    if p == 0:
        raise ValueError("price 0 is not a valid American price")
    return stake * (p / 100.0) if p > 0 else stake * (100.0 / -p)
