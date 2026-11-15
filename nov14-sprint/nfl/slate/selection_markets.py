"""Read local odds captures and group quotes by the exact pregame proposition."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from math import isfinite
from statistics import median
from urllib.parse import quote
from zoneinfo import ZoneInfo

BOOKS = {"betmgm", "betrivers", "draftkings", "espnbet", "fanduel"}
MARKETS = {
    "h2h": ("moneyline", "full_game"), "spreads": ("spread", "full_game"),
    "totals": ("total", "full_game"), "team_totals": ("team_total", "full_game"),
    "h2h_h1": ("moneyline", "first_half"), "spreads_h1": ("spread", "first_half"),
    "totals_h1": ("total", "first_half"), "team_totals_h1": ("team_total", "first_half"),
    "player_pass_yds": ("prop", "full_game"), "player_rush_yds": ("prop", "full_game"),
    "player_reception_yds": ("prop", "full_game"),
}
NAMES = {"player_pass_yds": "passing yards", "player_rush_yds": "rushing yards",
         "player_reception_yds": "receiving yards"}
WINDOWS = {"early": "Morning / noon", "late": "Afternoon", "night": "Sunday night"}
CENTRAL = ZoneInfo("America/Chicago")
BASE_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/"


def instant(value):
    if not isinstance(value, str):
        raise ValueError("Missing timezone-aware timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp is missing its timezone: " + value)
    return parsed


def window(kick):
    hour = instant(kick).astimezone(CENTRAL).hour
    return "early" if hour < 14 else "late" if hour < 18 else "night"


def decimal_odds(price):
    return 1 + (price / 100 if price > 0 else 100 / abs(price))


def price_number(value):
    if isinstance(value, bool):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return int(num) if isfinite(num) and num.is_integer() and abs(num) >= 100 else None


def line_number(value):
    if value is None:
        return None
    num = float(str(value).lstrip("oOuU"))
    if not isfinite(num):
        raise ValueError("Nonfinite line")
    return 0.0 if num == 0 else num


def key_for(event_id, market, subject, side, line):
    period = MARKETS[market][1]
    bits = [event_id, period, market, subject, side, format(line, ".15g") if line is not None else "-"]
    return ":".join(quote(str(bit), safe="") for bit in bits)


def label_for(key, subject, side, point):
    kind, period = MARKETS[key]
    prefix = "First half · " if period == "first_half" else ""
    if kind == "moneyline":
        return prefix + side + " to win"
    if kind == "spread":
        return prefix + ("%s %+.1f" % (side, point))
    unit = NAMES.get(key, "team points" if kind == "team_total" else "game points")
    return prefix + ("%s %s %g %s" % (subject, side.lower(), point, unit)).strip()


def game_signature(away, home, kick):
    return away, home, instant(kick)


def normalized_events(doc, props=()):
    """Convert the established ESPN/normalized --lines shape, retaining book-specific sources."""
    rows = []
    for game in doc["games"]:
        teams = game["teams"]
        books = []
        event = {"id": str(game["event_id"]), "commence_time": game["kickoff_utc"],
                 "away_team": teams["away"], "home_team": teams["home"], "bookmakers": books}
        for ref in game.get("book_references", []):
            groups = defaultdict(list)
            for m in ref.get("markets", []):
                kind = {"moneyline": "h2h", "pointSpread": "spreads", "total": "totals"}.get(m.get("market"))
                if kind is None:
                    continue
                side = m["side"]
                outcome = {"name": teams.get(side, side.title()), "price": m.get("american_price"),
                           "point": line_number(m.get("line"))}
                groups[kind, m.get("market_updated_utc")].append(outcome)
            bk = ref.get("book_key") or str(ref.get("book", "")).lower().replace(" ", "")
            books.append({"key": bk, "title": ref.get("book"), "last_update": ref.get("book_updated_utc"),
                          "observed_utc": ref.get("observed_utc") or doc.get("capture_complete_utc"),
                          "source_url": game.get("source_url") or game.get("event_url"),
                          "markets": [{"key": k, "last_update": t, "outcomes": oo} for (k, t), oo in groups.items()]})
        for prop in props:
            if str(prop["event_id"]) != event["id"] or prop["market"] not in NAMES:
                continue
            books.append({"key": prop["book"].lower().replace(" ", ""), "title": prop["book"],
                          "observed_utc": prop["observed_utc"], "source_url": prop["source_url"],
                          "last_update": prop["book_update_utc"], "source_input": "props",
                          "markets": [{"key": prop["market"], "outcomes": [
                              {"name": s.title(), "point": prop["line"], "description": prop["player"],
                               "price": prop[s + "_price"]} for s in ("over", "under")]}]})
        rows.append(event)
    return rows


def schedule_from_capture(capture, reference, as_of):
    """Match archived event IDs, neutral sites and venues without importing their old prices."""
    archive = {game_signature(g["teams"]["away"], g["teams"]["home"], g["kickoff_utc"]): g
               for g in reference["games"]}
    if instant(capture["captured_utc"]) > instant(as_of):
        raise ValueError("Capture completion is after this run")
    games, identities, seen = [], {}, set()
    for event in capture["games"]:
        sig = game_signature(event["away_team"], event["home_team"], event["commence_time"])
        eid = event["id"]
        if sig in seen or eid in identities:
            raise ValueError("Duplicate game in capture")
        old = archive.get(sig)
        if old is None:
            raise ValueError("Cannot reconcile capture with the scheduled game: " + " at ".join(sig[:2]))
        if old.get("state") not in (None, "STATUS_SCHEDULED"):
            raise ValueError("Game was already underway in schedule reference")
        seen.add(sig)
        identities[eid] = sig
        g = {k: old.get(k) for k in ("name", "teams", "venue", "neutral_site", "event_url", "state")}
        g.update(event_id=eid, espn_event_id=str(old["event_id"]), kickoff_utc=event["commence_time"])
        games.append(g)
    for event in capture.get("event_odds", []):
        if identities.get(event["id"]) != game_signature(event["away_team"], event["home_team"], event["commence_time"]):
            raise ValueError("Event-market payload does not match base event")
    return {"games": games, "capture_complete_utc": capture["captured_utc"]}


def entries(capture, lines, props):
    if capture is None:
        for e in normalized_events(lines, props):
            yield e, None, None
        return
    observations = {o["endpoint"]: o["observed_utc"] for o in capture.get("observations", [])}
    for collection in ("games", "event_odds"):
        for e in capture.get(collection, []):
            endpoint = "odds" if collection == "games" else "events/%s/odds" % e["id"]
            # Missing per-request timing remains unknown, even when capture completion is known.
            yield e, observations.get(endpoint), BASE_URL + endpoint


def collect(capture, lines, props, schedule, run_utc):
    """Read every supported quoted side. Retain comparator books and diagnostics."""
    groups, stats, skipped = {}, Counter(), Counter()
    cutoff = instant(run_utc)
    for event, endpoint_time, url in entries(capture, lines, props):
        eid = event["id"]
        if eid not in schedule:
            continue
        kick = instant(event["commence_time"])
        for book in event["bookmakers"]:
            bk = book["key"]
            for m in book.get("markets", []):
                key = m["key"]
                stats[key] += len(m["outcomes"])
                if key not in MARKETS or bk not in BOOKS:
                    skipped["unsupported book or market"] += len(m["outcomes"])
                    continue
                kind, period = MARKETS[key]
                observed = endpoint_time if capture is not None else book.get("observed_utc")
                updated = m.get("last_update") or book.get("last_update")
                if observed is None or instant(observed) >= kick or instant(observed) > cutoff:
                    skipped["missing or invalid pregame retrieval time"] += len(m["outcomes"])
                    continue
                if capture and instant(observed) > instant(capture["captured_utc"]):
                    raise ValueError("Request timestamp is after capture completion")
                if updated and not timedelta(0) <= instant(observed) - instant(updated) <= timedelta(minutes=30):
                    skipped["provider time is future or over 30 minutes old at retrieval"] += len(m["outcomes"])
                    continue
                if capture is not None and not updated:
                    skipped["missing provider update time"] += len(m["outcomes"])
                    continue
                if kind == "moneyline" and any(o.get("name") not in (event["home_team"], event["away_team"]) for o in m["outcomes"]):
                    skipped["three-way moneyline has different tie settlement"] += len(m["outcomes"])
                    continue
                raw = {}
                for o in m["outcomes"]:
                    side, subject = o.get("name"), o.get("description") or ""
                    price = price_number(o.get("price"))
                    try:
                        point = line_number(o.get("point"))
                    except (TypeError, ValueError):
                        point = None
                    sides = (event["away_team"], event["home_team"]) if kind in ("spread", "moneyline") else ("Over", "Under")
                    if (price is None or side not in sides or (kind == "moneyline") != (point is None)
                            or ((kind in ("prop", "team_total")) != bool(subject))
                            or (kind == "team_total" and subject not in (event["away_team"], event["home_team"]))):
                        skipped["malformed outcome"] += 1
                        continue
                    item = (subject, side, point)
                    if item in raw and raw[item] != price:
                        raise ValueError("Conflicting duplicate outcome for one market update")
                    raw[item] = price
                for (subject, side, point), price in raw.items():
                    if kind in ("moneyline", "spread"):
                        opp = event["home_team"] if side == event["away_team"] else event["away_team"]
                        game_side = "away" if side == event["away_team"] else "home"
                    else:
                        opp = "Under" if side == "Over" else "Over"
                        game_side = side.lower()
                    other = raw.get((subject, opp, -point if kind == "spread" else point))
                    implied = 1 / decimal_odds(price)
                    fair = implied / (implied + 1 / decimal_odds(other)) if other is not None else None
                    cid = key_for(eid, key, subject, side, point)
                    if cid not in groups:
                        groups[cid] = {"id": cid, "event_id": eid, "provider_market": key, "period": period,
                                       "market": kind, "subject": subject, "outcome": side, "side": game_side,
                                       "line": point, "label": label_for(key, subject, side, point), "quotes": {}}
                    quotes = groups[cid]["quotes"]
                    q = {"book": bk, "title": book.get("title") or bk, "price": price, "opposite_price": other,
                         "market_no_vig": fair, "observed_utc": observed, "market_updated_utc": m.get("last_update"),
                         "book_updated_utc": book.get("last_update"), "provider_updated_utc": updated,
                         "source_url": url or book.get("source_url"), "input": book.get("source_input", "lines")}
                    prior = quotes.get(bk)
                    if prior and instant(prior["observed_utc"]) == instant(observed) and prior != q:
                        raise ValueError("Conflicting same-book quotes at the same retrieval time")
                    if not prior or instant(prior["observed_utc"]) <= instant(observed):
                        quotes[bk] = q
    return list(groups.values()), dict(stats), dict(skipped)


def price_candidate(c):
    qs = list(c["quotes"].values())
    eligible = [q for q in qs if abs(q["price"]) <= 200]
    # Keep out-of-band contracts in the research universe while excluding them from calls.
    best = min(eligible or qs, key=lambda q: (-decimal_odds(q["price"]), q["book"]))
    peers = [q["market_no_vig"] for q in qs if q["book"] != best["book"] and q["market_no_vig"] is not None]
    all_fairs = [q["market_no_vig"] for q in qs if q["market_no_vig"] is not None]
    fair = median(peers) if peers else best["market_no_vig"]
    implied = 1 / decimal_odds(best["price"])
    c.update(source=best, price=best["price"], opposite_price=best["opposite_price"], in_price_band=bool(eligible),
             peer_count=len(peers), two_sided_books=len(all_fairs), book_count=len(qs), break_even=implied,
             market_no_vig=fair, hit_likelihood=fair, consensus_including_offer=median(all_fairs) if all_fairs else None,
             likelihood_basis="other books at exact line" if peers else "offering book only" if fair is not None else "unknown",
             market_gap_pp=100*(fair-implied) if fair is not None else None,
             return_per_unit_at_likelihood=fair*decimal_odds(best["price"])-1 if fair is not None else None,
             push_possible=(c["market"] == "moneyline" or c["line"].is_integer()),
             estimated_edge=None, verified_ticket=False)
