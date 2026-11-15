# weekly/ callable interface, v1 (implemented: `weekly/weekly_api.py`, API id `weekly/1`)

Written by the nfl-slate-data worker (Claude), first version 2026-11-15 07:41Z, rewritten for the working code at about 08:00Z, updated 2026-11-15 about 09:30Z for the 0-2-per-window rule and the red-team annotation API. Paper only, advisory only. This file describes what the code does today (61 unit tests pass). Where a rule is a choice I made, it says so in section 9.

## 1. What it is and who owns what

| Piece | Owner |
|---|---|
| Network, odds and schedule fetches, `sunday_intake.acquire(date)`, date picker, review forms, PDF, weekly journal (`journal.py --data weekly/journals/<date>`) | the front-door / release owner |
| `weekly/weekly_api.py`: screen, review intake, published card | this worker |
| Engine, `picker.py`, `selection_*.py`, freeze | Codex 7d2e |
| Nov 15 files (`slate_20261115.json`, `results/*`, `Sunday_Card.json` for Nov 15) | unchanged, never written here |

The code never calls the network, never reads a key and writes only under `weekly/reviews/`, `weekly/annotations/` and `weekly/published/`. It creates no ticket ledger and no `weekly/journals/`.

## 2. Calling it

Import: `sys.path.insert(0, ".../nov14-sprint/nfl/slate/weekly"); import weekly_api`. Every function returns a plain `dict` and raises `weekly_api.Refused(code, detail)`.

CLI (same results):

```
/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I weekly/weekly_api.py [--inputs DIR] [--work DIR] COMMAND
  dates
  screen DATE [--edition latest|<captured_utc>|<sha256>] [--window early|late|night] [--market KEY] [--band-only]
  review submit DATE --payload FILE|-      review list DATE      review verify DATE
  annotate submit DATE --payload FILE|-    annotate list DATE    annotate verify DATE
  publish DATE
  card DATE
```

- One JSON object on stdout. Exit 0 ok. Exit 1 refused, with `{"ok": false, "api": "weekly/1", "code": "...", "detail": "..."}` on stdout and `REFUSED CODE: detail` on stderr. Exit 2 is a usage error.
- `--inputs` (default `../weekly_inputs`) and `--work` (default this folder; reviews go to `<work>/reviews/`, annotations to `<work>/annotations/`, cards to `<work>/published/`) exist so tests and trials can run against a scratch folder.
- The server clock is the only clock. A client time in the payload (`client_utc`) is stored as `client_claimed_utc` and never used for a rule.
- Writes: lock file, temp file, `os.replace` (published files); fsync'd appends under `flock` (review rows).

## 3. Inputs (read-only)

For a date `D` (a Sunday on or after 2026-11-22):

```
weekly_inputs/D/schedule.json                          ESPN scoreboard + _source
weekly_inputs/D/odds.json                              latest edition
weekly_inputs/D/captures/<captured_utc, colons removed>.json   every edition
```

- Odds and schedule are joined on the set of both team display names plus the kickoff minute, never on home and away (a neutral-site game, such as MIN and SF, has arbitrary labels). A game that cannot be paired shows `missing` and a warning. It is never guessed.
- `event_id` is the odds feed's 32-hex id. `espn_event_id` is carried alongside.
- The capture lists whatever markets the front door fetched. **Main lines** (`h2h`, `spreads`, `totals`) come from `games[]`. If the capture also has `event_odds[]` (the detailed shape the Nov 15 capture has), every supported market key in it is read too: `team_totals`, `h2h_h1`, `spreads_h1`, `totals_h1`, `team_totals_h1`, `player_pass_yds`, `player_rush_yds`, `player_reception_yds`. Anything the capture lacks is listed under `markets_unavailable` and `missing` as **unavailable**, never invented. The real 2026-11-22 capture is main-only, so all eight are unavailable there.
- Windows (Central time hour of kickoff): `early` before 14:00, `late` before 18:00, `night` otherwise. Labels: "Morning / noon", "Afternoon", "Sunday night". A Sunday-night game that kicks off after 00:00Z is still Sunday in Chicago.

## 4. `dates()`

```json
{"ok": true, "api": "weekly/1", "rule": "...", "dates": [{
  "date": "2026-11-22", "week": 11, "games": 11, "state": "ready", "editions": 1,
  "latest_edition_utc": "2026-11-15T07:34:18Z", "latest_sha256": "<64 hex>", "first_kickoff_utc": "2026-11-22T18:00:00Z",
  "windows": {"early": 7, "late": 3, "night": 1},
  "review_state": {"early": "unreviewed", "late": "unreviewed", "night": "unreviewed"}, "published": false}]}
```

`state` is `ready`, `partly_started` or `all_started`. A date with no inputs isn't listed, and `screen` for it refuses `NO_INPUTS`.

## 5. `screen(date, edition="latest", window=None, market=None, band_only=False)`

Market-only. No model, no football judgment, no picks. It carries `"provisional": true` and `"engine": null`. Never refreshes anything.

```json
{"ok": true, "api": "weekly/1", "kind": "screen", "date": "2026-11-22", "week": 11, "generated_utc": "...",
 "provisional": true, "engine": null,
 "edition": {"captured_utc": "...", "sha256": "<of the capture file bytes>", "path": "<abs path>", "is_latest": true, "age_seconds": 1100},
 "inputs": {"schedule": {"sha256": "...", "events": 11, "observed_utc": "..."},
            "odds": {"books_requested": [...], "books_present": ["betrivers","draftkings","fanduel"], "books_missing": ["betmgm","espnbet"],
                     "markets_present": ["h2h","spreads","totals"], "markets_unavailable": ["team_totals", "..."], "credits_remaining": 415}},
 "windows": [{"name": "early", "label": "Morning / noon", "first_kickoff_utc": "...", "max_calls": 2, "state": "open", "games": [<game>]}],
 "warnings": ["2 of 5 requested books have no quotes in this edition: betmgm, espnbet"],
 "missing": ["unavailable in this capture: team_totals, ... (main lines only)"],
 "evidence_labels": "price=known, no_vig=derived, judgment=estimated, fill/personal price/Louisiana availability=unknown"}
```

`<game>`: `event_id`, `espn_event_id`, `away`/`home` (`name`, `abbr`), `kickoff_utc`, `kickoff_ct`, `window`, `state` (`scheduled`, `started`), `neutral_site`, `venue`, `books` (`key`, `provider_updated_utc`), `lines` (best fresh moneyline, most-quoted spread and total point, each with its `basis`), `contracts[]`, `markets_unavailable`, `missing`.

`<contract>` is the unit a review points at:

```json
{"id": "403a8870...:full_game:spreads::Arizona%20Cardinals:14", "event_id": "403a8870...", "period": "full_game",
 "market": "spreads", "subject": "", "side": "Arizona Cardinals", "point": 14.0, "label": "Arizona Cardinals +14.0 (ARI at KC)",
 "quotes": [{"book": "betrivers", "price": -110, "updated_utc": "...", "age_seconds_at_capture": 49.0, "fresh": true, "in_band": true}],
 "best": {"book": "betrivers", "price": -110, "updated_utc": "...", "in_band": true},
 "best_in_band": {"...": "..."}, "no_vig": {"median": 0.5, "books": 2, "label": "derived"},
 "reviewable": true, "why_not": null}
```

- `id` is exactly `selection_markets.key_for(event_id, market, subject, side, line)`: `":".join(quote(str(bit), safe="") for bit in [event_id, period, market, subject, side, format(line, ".15g") or "-"])`. A unit test compares it with the real function.
- Team markets (`h2h`, `spreads`) have an empty `subject` and the team name as `side`. `totals` has an empty `subject` and `Over`/`Under`. `team_totals*` and props have the team or player in `subject` and `Over`/`Under`.
- `fresh` means the book's own `last_update` was no more than 30 minutes before the capture. `in_band` means American price -200 to +200 (absolute value 100 to 200). Only a **fresh, in-band** quote can back a call. `reviewable` is true when a fresh in-band quote exists and the game has not started. `why_not` says which condition failed.
- `no_vig.median` is the median fair probability over books that quote both sides (same market and point) fresh. It is **derived** arithmetic, never an edge. With one book `books` is 1.
- Games sort by kickoff then team name. Windows with no games are omitted.

## 6. Review intake (immutable)

`submit_review(date, payload)`. Append-only: a revision is a new row and the latest non-late row per window wins. Nothing is edited or deleted.

```json
{"api": "weekly/1", "date": "2026-11-22", "author": "matthew", "author_kind": "human",
 "edition": {"captured_utc": "2026-11-15T07:34:18Z", "sha256": "<64 hex of the capture the reviewer looked at>"},
 "late": false, "client_utc": "optional, stored only",
 "windows": {"early": {"decision": "calls", "note": "optional"},
             "late": {"decision": "no_play", "note": "reason", "considered": "optional text"}},
 "calls": [{"event_id": "<32 hex>", "market": "spreads", "subject": "", "side": "Arizona Cardinals", "point": 14.0,
            "minimum_price": -115, "thesis": "...", "counterevidence": "...", "condition": "...", "sources": ["https://..."]}]}
```

- **Per window: 0, 1 or 2 calls**, including the one-game Sunday-night window. Two calls may be in the same game when they are **distinct contracts** (for example a side and the total). The same exact contract twice is refused `DUPLICATE_CONTRACT`; a third call in a window is refused `WINDOW_LIMIT`. `GAME_REPEATED` no longer exists. When calls share a game, the published call carries a `shared_event` note (section 7).
- **Opposite directions are declined.** Two calls that take opposite directions on the same event, the same period, the same market and the same subject are refused `OPPOSITE_DIRECTION`, **whatever the thresholds**: Warren Over 22.5 rushing yards with Warren Under 24.5, game Over 45.5 with game Under 47.5, home -3.5 with away +2.5, and the two moneylines. "Direction" is the call's `side` (Over/Under for totals, team totals and props; the team name for a moneyline or spread). The period is part of the market key, so a first-half total is a different market from the full-game total. The subject is the player or team (empty for a moneyline, spread or game total). Still allowed together: a different market (a moneyline and a spread, a side and a total), a different subject (two players, or the two teams' team totals), a different period (full-game Over with first-half Under), and the same direction at another line. This is the release decision for **formal picks only**; annotations and the personal notebook are not calls and are not affected. A revision that is refused leaves the previous active row and published card untouched. `publish` repeats the check, so a row written before the rule can't reach a card (refused `OPPOSITE_DIRECTION` with a "Resubmit" note).
- `author_kind` is optional on a review and is one of `human`, `claude`, `codex`, `other`. If it is left out, the row records `"unspecified"`. It is never defaulted to `human`, so a review row can't be mistaken for Matthew's own unless the submitter said so.
- Each named window is `calls` or `no_play`. A `calls` window needs at least one call in it. **A window that is not named is not reviewed.** Silence is never turned into a pass. The state is `unreviewed`, then `unreviewed_after_close` once its first kickoff has passed.
- `thesis`, `counterevidence` and `condition` are required text. `rationale` and `risk` are accepted as aliases for `thesis` and `counterevidence`. `sources` is optional (plain https links with no keys or tokens). The first one is published as the call's `source`.
- `edition` is required and pinned. It must be a real capture of that date and not dated in the future. A review made against an older edition is accepted and flagged `edition_is_latest: false`.
- A call needs a market in the supported list and a contract that exists in the pinned edition. The server stamps `observed_book`, `observed_price` and `book_updated_utc` from the best fresh quote that pays at least the floor, so the reviewer never types the observed price.

Refusal codes:

| Code | Refused when |
|---|---|
| `BAD_DATE` | not a Sunday on or after 2026-11-22 |
| `NO_INPUTS` | the date has no schedule, odds or captures |
| `BAD_PAYLOAD`, `BAD_WINDOW`, `BAD_DECISION`, `BAD_MARKET` | structurally wrong payload, unknown window name, decision not `calls`/`no_play`, unsupported market filter |
| `EDITION_UNKNOWN` | the pin is missing, doesn't match a capture file, or is dated in the future |
| `UNKNOWN_CONTRACT` | the market, event, side or line is not in the pinned capture (the detail says whether the market is unavailable in a main-only capture) |
| `INCOMPLETE_FIELD` | a required field is missing or empty, `minimum_price` isn't an integer, a link is not a plain https link |
| `PRICE_OUT_OF_BAND` | `minimum_price` outside -200..+200 |
| `FLOOR_ABOVE_QUOTE` | no fresh in-band quote in the pinned edition pays at least the floor |
| `WRONG_WINDOW` | a call's game belongs to a window the payload doesn't declare as `calls` |
| `DUPLICATE_CONTRACT` | the same exact contract (same contract id) appears twice in the payload. Two different contracts in one game are allowed |
| `OPPOSITE_DIRECTION` | two calls take opposite directions (`side` differs) on the same event, period, market and subject, at any threshold. The detail names both calls and lists what stays allowed. Checked after `DUPLICATE_CONTRACT` and before `WINDOW_LIMIT`, so a three-call payload with a clash is told to fix the clash first |
| `BAD_AUTHOR_KIND` | a review that sets `author_kind` to something other than `human`, `claude`, `codex`, `other` (for an annotation, a missing `author_kind` is also this code) |
| `WINDOW_LIMIT` | more than 2 calls in one window (a third call) |
| `DATE_LIMIT` | more than 6 calls for the date (counting windows not in this submission) |
| `AFTER_KICKOFF` | the clock is at or after a called game's kickoff, or after a window's first kickoff, and `late` is not true. With `"late": true` the row is recorded, flagged `late`, and excluded from the card and from the prospective claim. |
| `CHAIN_BROKEN` | `verify`, `publish` or `card` finds an altered row or file |

An identical resubmission (same window body and edition) writes nothing and returns `"duplicate": true`.

Storage: `weekly/reviews/<date>/reviews.jsonl`, one hash-chained row per window decision (`row_id`, `seq`, `received_utc`, `client_claimed_utc`, `window`, `decision`, `note`, `considered`, `author`, `author_kind`, `edition`, `edition_is_latest`, `late`, `calls`, `supersedes`, `payload_sha256`, `body_sha256`, `prev_sha256`, `sha256`). `verify(date)` returns `{rows, head_sha256}` or refuses `CHAIN_BROKEN`. `list_reviews(date)` returns every row, `window_states` and `chain_ok`.

`submit_review` returns `{"ok": true, "rows": [...], "duplicate": false, "window_states": {...}, "warnings": [...]}`.

## 6b. Independent red-team annotations

`annotate(date, payload)`. A separate, append-only, hash-chained file (`weekly/annotations/<date>/annotations.jsonl`). An annotation is **not a review**: it never counts toward a window's 2 calls, never changes or removes a call, and never makes a window "reviewed". Each row says `"kind": "red_team_annotation", "is_review": false, "changes_calls": false`.

```json
{"api": "weekly/1", "date": "2026-11-22", "author_kind": "claude", "author": "red-team-1",
 "stance": "concern", "text": "up to 4000 characters",
 "sources": ["https://..."], "scope": {"window": "early", "contract_id": "<id from screen>"},
 "edition": {"captured_utc": "...", "sha256": "<64 hex>"}}
```

- `author_kind` is **required** and is one of `human`, `claude`, `codex`, `other`. It is never defaulted, so a Claude note can't be recorded as a human one. `author` is a required label of at most 80 characters.
- `stance` is `concern`, `supports` or `info`. `text` is required. `sources` is optional (plain https links, no keys).
- `scope` is optional. It may hold `window` (`early`, `late`, `night`) and/or `contract_id` (must exist in the pinned or latest capture; if `window` is also given it must be that contract's window). With no scope the note applies to the date. `edition` is optional and defaults to the latest capture.
- Server clock only. `received_after_kickoff` is `true` when the note arrived at or after the first kickoff of whatever it is scoped to (the contract's game, the window's first game, or the date's first game). It is recorded and labelled, not refused.
- An identical note (same author, stance, text, sources, scope and capture) writes nothing and returns `"duplicate": true`.
- Refusals: `BAD_PAYLOAD`, `BAD_DATE`, `NO_INPUTS`, `BAD_AUTHOR_KIND`, `BAD_STANCE`, `BAD_SCOPE` (unknown scope key, unknown window, or a contract not in that window), `UNKNOWN_CONTRACT`, `EDITION_UNKNOWN`, `INCOMPLETE_FIELD` (missing `author`/`text`, bad link), `CHAIN_BROKEN` (on read of a tampered file).
- `annotate list DATE` returns `{rows, chain_ok, chain_problem}`. `annotate verify DATE` returns `{rows, head_sha256}` or refuses `CHAIN_BROKEN`.

## 7. `publish(date)` and the published files

Builds from the latest non-late row per window. Refuses `NOTHING_TO_PUBLISH` when no window has a decision and `MIXED_EDITIONS` when the calls windows pin different captures (resubmit them against one edition). Output, under `weekly/published/<date>/`:

```
Sunday_Card.json   the file pdf_export/brief.py reads (same review, brief-compatible)
Card.json          the fuller card: per-window states, calls with evidence, late rows, unreviewed windows
CURRENT.json       pointers and sha256s for the two files, the pinned capture and the review head hash
history/<UTC no colons>.<sha8>.Sunday_Card.json   write-once, one pair per publish that changed something
history/<UTC no colons>.<sha8>.Card.json
```

Publishing the same content twice is a no-op (`"unchanged": true`).

**Result keys:** `ok, api, date, unchanged, published_utc, output_path (= sunday_card_path), sunday_card_path, card_path, current_path, history_sunday_card_path, history_card_path, capture_path, capture_sha256, sunday_card_sha256, card_sha256, review_rows`.

**`Sunday_Card.json`:**

```json
{"slate_date": "2026-11-22", "issued_utc": "<received_utc of the latest included review row>",
 "earliest_snapshot": "<captured_utc of the pinned capture>", "snapshot_sha256": "<sha256 of that capture file>",
 "calls": [{"label": "...", "event_id": "...", "window": "Morning / noon", "kickoff": "2026-11-22T18:00:00Z", "game": "Arizona Cardinals at Kansas City Chiefs",
            "market": "spreads", "side": "Arizona Cardinals", "subject": "", "point": 14.0, "minimum_price": -115,
            "observed_book": "betrivers", "observed_price": -110, "book_updated_utc": "...",
            "condition": "...", "thesis": "...", "counterevidence": "...", "source": "https://... or empty",
            "decision": "Conditional pregame recommendation", "ticket": null,
            "shared_event": {"event_id": "...", "calls_in_event": 2, "note": "Correlated: 2 calls on this card are in the same game, ...",
                             "others": [{"label": "...", "id": "...", "market": "totals", "side": "Over", "point": 44.5, "relation": "different_markets"}]}}],
 "passes": [{"window": "Sunday night", "decision": "Pass", "reason": "...", "considered": "optional"}],
 "unreviewed_windows": ["Afternoon"], "excluded_started_before_issue": [],
 "source": {"producer": "weekly/weekly_api.py", "api": "weekly/1", "review_rows": ["..."], "review_head_sha256": "...", "paper_only": true}}
```

- **`shared_event`** appears only on an actual published call whose game holds another published call. It is arithmetic on the call fields: `calls_in_event`, the `others` with a `relation` (`different_markets`, `same_market_other_subject`, `same_market_other_line`; `opposite_sides_same_market` is still defined but no longer reachable, since opposite directions are refused at submit and again at publish) and a plain-English `note` that starts "Correlated: N calls on this card are in the same game, so one game result can decide more than one of them. They are not independent calls." It is not a probability and not a risk limit. brief.py's `validate_card` ignores the extra key (a unit test checks this).
- **`Card.json` adds** (annotations never reach `Sunday_Card.json`): `annotations` (the rows, shaped as in 6b, without internal hashes except `sha256`), `annotation_head_sha256`, `annotations_note`, per call `annotation_rows` (row ids scoped to that contract), per window `annotation_rows` (window-scoped notes with no contract) and `review_author_kind`, plus `summary.calls_sharing_an_event` and `summary.annotations`. A date-wide note (no scope) appears in `annotations` only. Adding a note changes `Card.json` and so writes a new history pair, but never changes `Sunday_Card.json` or any call.
- brief.py needs `issued_utc` earlier than every call's kickoff. A call whose game had already kicked off when the latest review landed is listed under `excluded_started_before_issue` (with its row id) and stays out of `calls`. It remains in `Card.json` and in the earlier history snapshot.
- A window that was never reviewed is in `unreviewed_windows`, not `passes`. Only an explicit `no_play` becomes a pass.
- Nothing from Nov 15 is carried in. A weekly card contains only that date's reviewed calls.
- The real brief.py functions `validate_card`, `initial_quote` and `check_capture` accept this file against the pinned capture (checked 07:55Z on a scratch publish, and by the unit tests). The optional `sunday_<date>_selections.json` and `_watchlist.json` files brief.py can read are **not** produced here; without them the PDF falls back to the card alone.

`current_card(date)` returns the `publish` keys plus `card` and `sunday_card` (parsed), after re-hashing both files against `CURRENT.json`. It refuses `NO_CARD` before the first publish and `CHAIN_BROKEN` if a file changed.

## 8. How this meets the other owners

- **Weekly journal.** I don't touch `journal.py` or create `weekly/journals/`. The web owner runs the existing journal CLI with `--data weekly/journals/<date>`. The fields it needs are in `CURRENT.json` (`capture_path`, `capture_sha256`) and in each call (`event_id`, `market`, `subject`, `side`, `point`, `minimum_price`, `label`, `observed_*`). I haven't run journal.py against the 2026-11-22 capture and make no claim that it accepts one.
- **Engine.** `sunday_card.load_frozen` refuses any date except 2026-11-15, so the weekly path doesn't use it. `contracts[].id` is already the engine's key, so Codex can join to it.
- **PDF.** `pdf_export/brief.py` takes `Sunday_Card.json` and the pinned capture file.

## 9. Choices and limits

- One decision per window per submission, 0 to 2 calls per window (distinct contracts; two in the same game are allowed and annotated as correlated, but never opposite directions on one event, period, market and subject), at most 6 per date, floor in the -200..+200 band and no higher than the best fresh quote in the pinned capture. The 0-2 rule, including the one-game Sunday night, is Matthew's (relayed to me on 2026-11-15 before 09:00Z); the other limits are the approved v0 interface values.
- The publish history files are write-once. If the same second and the same content hash already exist, publish skips it; if the name exists with different content it refuses `CHAIN_BROKEN` rather than overwrite.
- A quote older than 30 minutes at capture time can't back a call. That is stricter than the screen's display, which still shows it with `fresh: false`.
- No network, no keys, no refresh, no picks, no probabilities as edge, no stake advice. No claim that a price is fillable or available in Louisiana: `local_availability_verified` is `false` and stays false. Evidence labels: price `known`, no-vig `derived`, judgment `estimated`, fill and personal price and final inactives `unknown`.
- Not verified: journal.py against a non-Nov-15 capture, and the PDF end to end (pypdf and reportlab aren't installed for this interpreter, so brief.py's validators were run by extracting them from the source).

## Change log

- 2026-11-15 07:41Z: v0 contract draft.
- 2026-11-15 about 08:00Z: v1, rewritten for the implemented code (screen, review intake with hash-chained rows, publish of `Sunday_Card.json` and `Card.json`).
- 2026-11-15 about 09:30Z: still `weekly/1` (additive). Rule fix: 0-2 calls per window, same-game distinct contracts allowed, `GAME_REPEATED` removed, `DUPLICATE_CONTRACT` added, `shared_event` correlation note on published calls. New: independent red-team annotation API (6b), review `author_kind`, `Card.json` annotation fields. Code commit `be29e0a`; 61 tests.
- 2026-11-15 about 09:45Z: still `weekly/1` (additive refusal). Release decision for formal picks, relayed by the integrated release owner: opposite directions on the same event, period, market and subject are refused `OPPOSITE_DIRECTION` at any threshold (submit and publish); two distinct same-game selections with shared-game risk stay allowed. `opposite_sides_same_market` is no longer produced. 73 tests (12 new, one rewritten, two older third-call cases made robust to the rule).
