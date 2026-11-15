"""Independent adversarial harness for the NFL lane (paper and research only).

Written from the lane's written specs (RULES.md, rules.py docstrings, frozen_rules.json,
frozen_picker.json, the issued picker's model description). It imports nothing from the
lane. Standard library only, Python 3.9.

Conventions (nflverse games.csv): spread_line > 0 means the home team is favored;
result = home_score - away_score. A home spread bet wins when result - line > 0.
"""
import csv
import math
import random

FRANCHISE = {"OAK": "LV", "SD": "LAC", "STL": "LA"}
BREAKEVEN_110 = 110.0 / 210.0


# ---------------------------------------------------------------- loading

def fnum(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.upper() == "NA":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_games(path):
    with open(path, newline="") as f:
        raw = list(csv.DictReader(f))
    out = []
    for r in raw:
        g = {
            "game_id": r["game_id"], "season": int(r["season"]), "week": int(r["week"]),
            "game_type": r["game_type"], "gameday": r["gameday"],
            "gametime": r.get("gametime", "") or "", "weekday": r.get("weekday", ""),
            "away": FRANCHISE.get(r["away_team"], r["away_team"]),
            "home": FRANCHISE.get(r["home_team"], r["home_team"]),
            "location": r.get("location", ""),
        }
        for k_out, k_in in [("hs", "home_score"), ("as", "away_score"),
                            ("sl", "spread_line"), ("tl", "total_line"),
                            ("hr", "home_rest"), ("ar", "away_rest"),
                            ("hml", "home_moneyline"), ("aml", "away_moneyline"),
                            ("hso", "home_spread_odds"), ("aso", "away_spread_odds"),
                            ("uo", "under_odds"), ("oo", "over_odds")]:
            g[k_out] = fnum(r.get(k_in))
        out.append(g)
    out.sort(key=lambda g: (g["gameday"], g["gametime"], g["game_id"]))
    return out


def as_of(games, cutoff):
    """Completed games strictly before `cutoff` (YYYY-MM-DD). Reads nothing on or after it."""
    return [g for g in games if g["gameday"] < cutoff and g["hs"] is not None and g["as"] is not None]


def completed(g):
    return g["hs"] is not None and g["as"] is not None


# ---------------------------------------------------------------- prices

def american_profit(a):
    """Profit per 1 unit staked on a win at American price a."""
    return a / 100.0 if a > 0 else 100.0 / (-a)


def implied(a):
    return 100.0 / (a + 100.0) if a > 0 else (-a) / (-a + 100.0)


def novig(a, b):
    pa, pb = implied(a), implied(b)
    s = pa + pb
    return pa / s, pb / s


def breakeven_price(w, l):
    """American price at which w wins and l losses net exactly zero. None if no wins."""
    if w <= 0:
        return None
    if l <= 0:
        return float("inf")
    need = l / w  # profit per unit needed on a win
    return 100.0 * need if need >= 1.0 else -100.0 / need


def payout(outcome, price=-110.0):
    if outcome == "W":
        return american_profit(price)
    if outcome == "L":
        return -1.0
    return 0.0


# ---------------------------------------------------------------- grading

def grade(market, side, line, hs, as_):
    """W, L or P. Spread line in home-favored convention; total line in points."""
    if market == "spread":
        m = (hs - as_) - line
        if m == 0:
            return "P"
        home_cover = m > 0
        return "W" if home_cover == (side == "home") else "L"
    if market == "total":
        t = (hs + as_) - line
        if t == 0:
            return "P"
        return "W" if (t > 0) == (side == "over") else "L"
    if market == "moneyline":
        if hs == as_:
            return "P"
        return "W" if (hs > as_) == (side == "home") else "L"
    raise ValueError(market)


def adverse_line(market, side, line, d):
    """The line `d` points worse for the bettor than `line`."""
    if market == "spread":
        return line + d if side == "home" else line - d
    if market == "total":
        return line - d if side == "under" else line + d
    raise ValueError(market)


# ---------------------------------------------------------------- frozen rules (from RULES.md spec)

FAMILIES = {
    "HOME_DOG": [1, 3, 7], "BIG_DOG": [7, 10, 14],
    "REST_EDGE": [3, 6], "HIGH_TOTAL_UNDER": [47, 50],
}
FROZEN = [("HOME_DOG", 7), ("BIG_DOG", 10), ("REST_EDGE", 6), ("HIGH_TOTAL_UNDER", 47)]


def decide(family, v, g, sl=None, tl=None):
    """Return (take, market, side). side None means the rule has no side here.

    `sl`/`tl` override the row's line (used to test decisions made on a different line)."""
    sl = g["sl"] if sl is None else sl
    tl = g["tl"] if tl is None else tl
    if family == "HOME_DOG":
        if sl is None:
            return False, "spread", None
        return sl <= -v, "spread", "home"
    if family == "BIG_DOG":
        if sl is None or sl == 0:
            return False, "spread", None
        side = "away" if sl > 0 else "home"
        return abs(sl) >= v, "spread", side
    if family == "REST_EDGE":
        if g["hr"] is None or g["ar"] is None:
            return False, "spread", None
        diff = g["hr"] - g["ar"]
        if diff == 0:
            return False, "spread", None
        return abs(diff) >= v, "spread", ("home" if diff > 0 else "away")
    if family == "HIGH_TOTAL_UNDER":
        if tl is None:
            return False, "total", None
        return tl >= v, "total", "under"
    raise ValueError(family)


def recorded_price(g, market, side):
    if market == "spread":
        return g["hso"] if side == "home" else g["aso"]
    if market == "total":
        return g["uo"] if side == "under" else g["oo"]
    return g["hml"] if side == "home" else g["aml"]


def bets_for(family, v, games):
    """List of (game, market, side, line) for every take."""
    out = []
    for g in games:
        take, market, side = decide(family, v, g)
        if take and side is not None:
            line = g["sl"] if market == "spread" else g["tl"]
            out.append((g, market, side, line))
    return out


def summarize(bets, d=0.0, price=-110.0, price_mode="flat", default_missing=None):
    """W-L-P, profit and ROI. price_mode 'flat' uses `price`; 'recorded' uses the row's odds
    (missing odds -> `default_missing`, or the bet is dropped when that is None)."""
    w = l = p = 0
    profit = 0.0
    dropped = 0
    for g, market, side, line in bets:
        if price_mode == "recorded":
            pr = recorded_price(g, market, side)
            if pr is None:
                if default_missing is None:
                    dropped += 1
                    continue
                pr = default_missing
        else:
            pr = price
        o = grade(market, side, adverse_line(market, side, line, d) if d else line, g["hs"], g["as"])
        if o == "W":
            w += 1
        elif o == "L":
            l += 1
        else:
            p += 1
        profit += payout(o, pr)
    n = w + l + p
    return {"bets": n, "w": w, "l": l, "p": p, "profit": profit,
            "roi": (profit / n) if n else None, "dropped_missing_odds": dropped}


# ---------------------------------------------------------------- statistics

def wilson(w, n, z=1.96):
    if n == 0:
        return None, None
    ph = w / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


def binom_sf(k, n, p):
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    tot = 0.0
    for i in range(k, n + 1):
        tot += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                        + i * math.log(p) + (n - i) * math.log(1 - p))
    return min(1.0, tot)


# ---------------------------------------------------------------- picker model (from the frozen picker's spec)

def _expit(x):
    return 1.0 / (1.0 + math.exp(-x))


def _logit(p):
    return math.log(p / (1.0 - p))


def _clip(p, e=1e-6):
    return min(1.0 - e, max(e, p))


def elo_walk(games, P, cutoff):
    """Past-only ratings walk. Games on one date are all predicted before any is learned from."""
    elo, off, dfn = {}, {}, {}
    mu = P["mu_start"]
    season = None
    preds = []
    done = as_of(games, cutoff)
    i = 0
    while i < len(done):
        day = done[i]["gameday"]
        j = i
        while j < len(done) and done[j]["gameday"] == day:
            j += 1
        batch = []
        for g in done[i:j]:
            if season is not None and g["season"] != season:
                for t in elo:
                    elo[t] = P["elo_mean"] + (elo[t] - P["elo_mean"]) * (1 - P["elo_season_regress"])
                for t in off:
                    off[t] *= (1 - P["pts_season_regress"])
                    dfn[t] *= (1 - P["pts_season_regress"])
            season = g["season"]
            for t in (g["home"], g["away"]):
                if t not in elo:
                    elo[t] = P["elo_mean"]
                    off[t] = 0.0
                    dfn[t] = 0.0
            at_home = g["location"] == "Home"
            diff = elo[g["home"]] - elo[g["away"]] + (P["elo_hfa"] if at_home else 0.0)
            ph = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
            hfa = P["pts_hfa"] if at_home else 0.0
            hp = mu + off[g["home"]] + dfn[g["away"]] + hfa / 2
            ap = mu + off[g["away"]] + dfn[g["home"]] - hfa / 2
            margin = P["margin_mix_elo"] * diff / P["elo_points_per_point"] + (1 - P["margin_mix_elo"]) * (hp - ap)
            batch.append({"g": g, "p_home": ph, "diff": diff, "hp": hp, "ap": ap,
                          "margin": margin, "total": hp + ap})
        preds.extend(batch)
        for b in batch:
            g = b["g"]
            m = g["hs"] - g["as"]
            s = 1.0 if m > 0 else (0.0 if m < 0 else 0.5)
            if m == 0:
                mult = 1.0
            else:
                wd = b["diff"] if m > 0 else -b["diff"]
                mult = math.log(abs(m) + 1.0) * 2.2 / (wd * 0.001 + 2.2)
            delta = P["elo_k"] * mult * (s - b["p_home"])
            elo[g["home"]] += delta
            elo[g["away"]] -= delta
            rh = g["hs"] - b["hp"]
            ra = g["as"] - b["ap"]
            a = P["pts_alpha"]
            off[g["home"]] += a * rh
            dfn[g["away"]] += a * rh
            off[g["away"]] += a * ra
            dfn[g["home"]] += a * ra
            mu += P["mu_alpha"] * ((g["hs"] + g["as"]) / 2.0 - mu)
        i = j
    return preds


def log_loss(preds, w):
    ll = br = 0.0
    n = 0
    for b in preds:
        g = b["g"]
        if g["hml"] is None or g["aml"] is None or g["hs"] == g["as"]:
            continue
        pm = novig(g["hml"], g["aml"])[0]
        p = _clip(_expit(w * _logit(pm) + (1 - w) * _logit(_clip(b["p_home"]))))
        y = 1.0 if g["hs"] > g["as"] else 0.0
        ll += -(y * math.log(p) + (1 - y) * math.log(1 - p))
        br += (p - y) ** 2
        n += 1
    return (ll / n if n else None), (br / n if n else None), n


def side_test(preds, market, thr=3.0):
    out = {"all": {"W": 0, "L": 0, "P": 0}, "edge": {"W": 0, "L": 0, "P": 0}}
    for b in preds:
        g = b["g"]
        if market == "spread":
            line = g["sl"]
            if line is None:
                continue
            edge = b["margin"] - line
            side = "home" if edge > 0 else "away"
        else:
            line = g["tl"]
            if line is None:
                continue
            edge = b["total"] - line
            side = "over" if edge > 0 else "under"
        if edge == 0:
            continue
        o = grade(market, side, line, g["hs"], g["as"])
        out["all"][o] += 1
        if abs(edge) >= thr:
            out["edge"][o] += 1
    return out


def top2(preds, by, price_shift=0.0):
    """Two most likely moneyline sides per regular-season Sunday slate, paid at the archive price.

    price_shift worsens every price by that many cents of American odds (e.g. 10 turns -150 into -160)."""
    slates = {}
    for b in preds:
        g = b["g"]
        if g["game_type"] != "REG" or g["weekday"] != "Sunday" or g["hml"] is None or g["aml"] is None:
            continue
        pm = novig(g["hml"], g["aml"])[0]
        ph = pm if by == "market" else b["p_home"]
        side = "home" if ph >= 0.5 else "away"
        prob = ph if side == "home" else 1 - ph
        price = g["hml"] if side == "home" else g["aml"]
        slates.setdefault((g["season"], g["week"]), []).append((prob, g["game_id"], side, price, g))
    out = {"slates": 0, "bets": 0, "W": 0, "L": 0, "P": 0, "profit": 0.0, "both": 0}
    for k in sorted(slates):
        cand = sorted(slates[k], key=lambda c: (-c[0], c[1]))[:2]
        if len(cand) < 2:
            continue
        out["slates"] += 1
        wins = 0
        for prob, gid, side, price, g in cand:
            pr = worsen_american(price, price_shift)
            o = grade("moneyline", side, None, g["hs"], g["as"])
            out["bets"] += 1
            out[o] += 1
            out["profit"] += payout(o, pr)
            wins += o == "W"
        out["both"] += wins == 2
    return out


def worsen_american(a, cents):
    """Move an American price `cents` worse for the bettor, crossing the +/-100 gap correctly."""
    if not cents:
        return a
    # work on the 'cents' scale where -100 and +100 are the same point
    x = a + 100.0 if a < 0 else a - 100.0  # -150 -> -50, +120 -> +20
    x -= cents
    return x - 100.0 if x < 0 else x + 100.0


# ---------------------------------------------------------------- multiple-testing null

def family_null(variant_bets, sims=2000, seed=20261114):
    """Distribution of the best variant's ROI when every cover outcome is a fair coin.

    variant_bets: dict name -> list of (game_id, market, side). One coin per (game, market)
    says whether home (spread) or over (total) covers, so overlapping variants share outcomes
    and opposite sides get opposite outcomes. Pushes are treated as decided coin flips."""
    rng = random.Random(seed)
    keys = sorted({(gid, mk) for v in variant_bets.values() for gid, mk, _ in v})
    best = []
    win_pay = 100.0 / 110.0
    for _ in range(sims):
        flip = {k: rng.random() < 0.5 for k in keys}
        m = -1e9
        for name, gl in variant_bets.items():
            if not gl:
                continue
            w = sum(1 for gid, mk, side in gl if flip[(gid, mk)] == (side in ("home", "over")))
            roi = (w * win_pay - (len(gl) - w)) / len(gl)
            m = max(m, roi)
        best.append(m)
    best.sort()
    return best
