"""Current review eligibility, retaining the separately issued November 15 decision policy."""
import hashlib
import json
from collections import Counter

import issued_selection_decisions_20261115 as issued
import selection_markets as markets

# Canonical JSON digest of the immutable 07:08:57Z release. An edited review uses today's rule.
ISSUED_REVIEW = "f3ac4630844dd937f37f4070aae930849cdf6724e75de660284e37d1fa539271"
CURRENT_POLICY = ("Up to two distinct contracts per Chicago window. Same-game selections share game risk. "
                  "Formal calls must agree on direction for each event, period, market and subject.")


def apply_overlay(overlay, candidates, input_sha, capture_time, first_kick, run_utc):
    issued.validate_overlay(overlay, input_sha, first_kick, run_utc)
    payload = json.dumps(overlay, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    if hashlib.sha256(payload).hexdigest() == ISSUED_REVIEW:
        return issued.apply_overlay(overlay, candidates, input_sha, capture_time, first_kick, run_utc)
    if markets.instant(overlay["decided_utc"]) < markets.instant(capture_time):
        raise ValueError("Review decision predates its bound price capture")
    # Keep the issued price, ID, timing, sources and rationale checks for every single contract.
    # Stage updates until the whole proposed review passes the current per-window limit.
    originals = {c["id"]: c for c in candidates}
    draft = {key:dict(c) for key,c in originals.items()}
    selected = []
    seen_ids = set()
    directions = {}
    per_window = Counter()
    for item in overlay["calls"]:
        cid, = issued.apply_overlay(dict(overlay, calls=[item]), draft.values(), input_sha, capture_time, first_kick, run_utc)
        c = draft[cid]
        window = c["window"]
        market = (c["event_id"], c["period"], c["provider_market"], c["subject"])
        direction = c["outcome"]
        if cid in seen_ids or directions.setdefault(market, direction) != direction or per_window[window] >= 2:
            raise ValueError("Duplicate, opposing, or excess review call: " + cid)
        seen_ids.add(cid)
        selected.append(cid)
        per_window[window] += 1
    for cid in selected:
        c = draft[cid]
        related = [other for other in selected if other != cid and draft[other]["event_id"] == c["event_id"]]
        c.update(review_policy=CURRENT_POLICY, same_game_contract_ids=related)
        originals[cid].update(c)
    return selected


def __getattr__(name):
    return getattr(issued, name)
