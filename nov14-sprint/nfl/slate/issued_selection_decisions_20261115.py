"""Pregame evaluation and reviewed selections. This module never fetches a price."""
from math import erf, sqrt
from urllib.parse import urlsplit

import selection_markets as markets


def model_probability(c, game, test):
    if c["period"] != "full_game":
        return None
    model, side = game["model"], c["side"]
    if c["market"] == "moneyline":
        p = model["p_home_win"]
        return p if side == "home" else 1 - p
    if c["market"] == "spread":
        margin = model["margin_home"] if side == "home" else -model["margin_home"]
        return (1 + erf((margin + c["line"]) / (test["sd_margin"] * sqrt(2)))) / 2
    if c["market"] == "total":
        p = (1 + erf((model["total"] - c["line"]) / (test["sd_total"] * sqrt(2)))) / 2
        return p if side == "over" else 1 - p
    return None


def historical_movement(c, prior_rows, g):
    eid = g.get("espn_event_id") or g["event_id"]
    key = markets.key_for(eid, c["provider_market"], c["subject"], c["outcome"], c["line"])
    old = prior_rows.get(key, {}).get("quotes", {})
    comparisons = []
    for bk in sorted(c["quotes"]):
        before = old.get(bk)
        after = c["quotes"][bk]
        if before and markets.instant(before["observed_utc"]) < markets.instant(after["observed_utc"]):
            comparisons.append({"book": bk, "earliest_observed_price": before["price"],
                                "earliest_observed_utc": before["observed_utc"], "earliest_source_url": before["source_url"],
                                "latest_observed_price": after["price"], "latest_observed_utc": after["observed_utc"],
                                "latest_source_url": after["source_url"], "is_opener": False, "is_closing_line": False})
    return comparisons


def screen_reason(c):
    if not c["in_price_band"]:
        return "All observed prices are outside the personal price band."
    if c["two_sided_books"] == 0:
        return "No same-book two-sided quote at this exact line."
    if c["peer_count"] < 2:
        return "Fewer than two other books priced both sides of this exact line."
    if c["model_estimate"] is None:
        return "No independently benchmarked full-game forecast applies to this contract."
    if min(c["hit_likelihood"], c["model_estimate"]) <= 0.5:
        return "The market and football model do not both favor this side."
    return None


def evaluate(candidates, games, test, historical):
    for c in candidates:
        markets.price_candidate(c)
        g = games[c["event_id"]]
        c.update(game=g["game"], kickoff_utc=g["kickoff_utc"], window=g["window"],
                 model_estimate=model_probability(c, g, test), selected=False,
                 price_observations=historical_movement(c, historical, g))
        c["screen_exclusion"] = screen_reason(c)
    def rank_key(c):
        scorable = c["in_price_band"] and c["hit_likelihood"] is not None
        return (not scorable, -(c["hit_likelihood"] or 0.0), c["id"])

    candidates.sort(key=rank_key)
    for i, c in enumerate(candidates, 1):
        c["rank"] = i if c["in_price_band"] and c["hit_likelihood"] is not None else None
    screens, controls = {}, {}
    for window in markets.WINDOWS:
        available = [c for c in candidates if c["window"] == window]
        approved = next((c for c in available if c["screen_exclusion"] is None), None)
        screens[window] = approved["id"] if approved else None
        controls[window] = next((c["id"] for c in available if c["provider_market"] == "h2h"
                                 and c["in_price_band"] and c["hit_likelihood"] is not None
                                 and c["hit_likelihood"] > 0.5), None)
    return screens, controls


def validate_overlay(overlay, input_sha, first_kick, run_utc):
    if overlay.get("capture_sha256") != input_sha:
        raise ValueError("Review file was made for another capture")
    if not isinstance(overlay.get("author"), str) or not overlay["author"].strip():
        raise ValueError("Review file needs an author")
    decided = markets.instant(overlay.get("decided_utc"))
    if decided >= markets.instant(first_kick) or decided > markets.instant(run_utc):
        raise ValueError("Review must be recorded by the run and before the first kickoff")
    if not isinstance(overlay.get("calls"), list):
        raise ValueError("Review calls must be an array; an empty array records a pass")
    notes = overlay.get("window_notes", {})
    if not isinstance(notes, dict) or any(k not in markets.WINDOWS or not isinstance(v, str) for k,v in notes.items()):
        raise ValueError("Review window_notes must use early/late/night with text reasons")


def apply_overlay(overlay, candidates, input_sha, capture_time, first_kick, run_utc):
    validate_overlay(overlay, input_sha, first_kick, run_utc)
    if markets.instant(overlay["decided_utc"]) < markets.instant(capture_time):
        raise ValueError("Review decision predates its bound price capture")
    by_id = {c["id"]: c for c in candidates}
    calls, taken, used_events = [], set(), set()
    counts = {w: 0 for w in markets.WINDOWS}
    for r in overlay["calls"]:
        if not isinstance(r, dict):
            raise ValueError("Review call must be an object")
        for k in ("event_id", "market", "subject", "side", "point", "minimum_price", "rationale", "risk"):
            if k not in r:
                raise ValueError("Review call missing " + k)
        if type(r["market"]) is not str or r["market"] not in markets.MARKETS:
            raise ValueError("Unknown market in review")
        point = r["point"]
        if point is not None and (type(point) not in (int, float) or markets.line_number(point) is None):
            raise ValueError("Review point must be a finite number or null")
        cid = markets.key_for(r["event_id"], r["market"], r["subject"], r["side"], point)
        c = by_id.get(cid)
        if c is None:
            raise ValueError("Review contract missing in the exact capture: " + cid)
        floor = r["minimum_price"]
        if type(floor) is not int or not 100 <= abs(floor) <= 200:
            raise ValueError("Review price floor outside personal bounds")
        if not c["in_price_band"] or markets.decimal_odds(c["price"]) < markets.decimal_odds(floor):
            raise ValueError("Review floor unavailable inside the price band: " + cid)
        if c["two_sided_books"] == 0:
            raise ValueError("Cannot evaluate a reviewed call without a two-sided exact market")
        if any(not isinstance(r[k], str) or not r[k].strip() for k in ("rationale", "risk")):
            raise ValueError("Review needs a pregame rationale and contrary case for " + cid)
        urls = r.get("sources", [])
        if not isinstance(urls, list) or any(not isinstance(u,str) or urlsplit(u).scheme not in ("http","https") for u in urls):
            raise ValueError("Review sources must be a list of public links")
        # Both sides of ±3 represent one spread. Different players/thresholds remain distinct.
        signed = -point if c["market"] == "spread" and c["side"] == "away" else point
        prop = (c["event_id"], c["provider_market"], c["subject"], signed)
        if prop in taken or counts[c["window"]] == 2:
            raise ValueError("Duplicate, opposing, or excess review call: " + cid)
        if c["event_id"] in used_events:
            raise ValueError("Release calls must come from different games within a window")
        used_events.add(c["event_id"])
        taken.add(prop)
        counts[c["window"]] += 1
        c.update(minimum_price=floor, rationale=r["rationale"], risk=r["risk"], review_sources=urls, condition=r.get("condition"))
        calls.append(cid)
    return calls


def selection_call(c):
    s = c["source"]
    return {"id": c["id"], "event_id": c["event_id"], "window": c["window"],
            "kickoff": c["kickoff_utc"], "label": c["label"], "game": c["game"],
            "market": c["provider_market"], "period": c["period"], "subject": c["subject"],
            "side": c["outcome"], "point": c["line"], "minimum_price": c["minimum_price"],
            "book": s["book"], "price": c["price"], "observed_utc": s["observed_utc"],
            "provider_updated_utc": s["provider_updated_utc"], "source_url": s["source_url"], "sportsbook": s["title"],
            "break_even": c["break_even"], "market_probability": c["hit_likelihood"],
            "all_book_median_no_vig": c["consensus_including_offer"],
            "probability_basis": c["likelihood_basis"], "other_two_sided_books": c["peer_count"],
            "model_estimate": c["model_estimate"], "market_gap_pp": c["market_gap_pp"],
            "reference_return_per_unit_decided": c["return_per_unit_at_likelihood"],
            "estimated_edge": None, "rationale": c["rationale"], "risk": c["risk"],
            "sources": c.get("review_sources", []), "condition": c.get("condition"), "ticket_status": "no ticket",
            "local_availability_verified": False, "price_observations": c["price_observations"],
            "quoted_books": {k: q["price"] for k,q in c["quotes"].items()}}
