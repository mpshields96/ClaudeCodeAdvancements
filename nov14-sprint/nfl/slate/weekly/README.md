# weekly/: dated weekly screen, review intake and published card

Paper and advisory only. Standard library only, Python 3.9. No network, no keys, no refresh. Owner: the nfl-slate-data worker. Full interface: `API.md` (API id `weekly/1`).

## What it does

1. `screen DATE`: reads `../weekly_inputs/DATE/{schedule.json,odds.json,captures/}` and lists every game and every contract the capture quotes, with fresh in-band prices per book. Market-only. No picks.
2. `review submit DATE`: takes one immutable, hash-chained review (per window: 0 to 2 calls, or an explicit no-play, with a thesis, counterevidence, a condition and a price floor) pinned to one capture. Two calls may share a game when they are different contracts (for example a side and the total); the same contract twice is refused `DUPLICATE_CONTRACT`, opposite directions on the same event, period, market and subject (at any threshold, for example Over 45.5 with Under 47.5) `OPPOSITE_DIRECTION`, and a third call in a window `WINDOW_LIMIT`. Append-only. A window you don't name stays unreviewed. `author_kind` (`human`, `claude`, `codex`, `other`) is recorded as `unspecified` if left out, never assumed human.
3. `annotate submit DATE`: an independent red-team note in its own hash-chained file. It is not a review, counts toward no limit and changes no call. `author_kind` is required and never defaulted; `stance` is `concern`, `supports` or `info`; scope is optional (window and/or contract id).
4. `publish DATE`: writes `published/DATE/Sunday_Card.json` (what `pdf_export/brief.py` reads), `Card.json` (adds the annotations), `CURRENT.json` and a write-once `history/` pair. A published call that shares a game with another published call carries a `shared_event` "Correlated" note.
5. `card DATE`: re-hashes and returns the current published card.

## Run it

```
cd nov14-sprint/nfl/slate
R="/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I weekly/weekly_api.py"
$R dates
$R screen 2026-11-22 --window early --band-only
$R review submit 2026-11-22 --payload review.json
$R review verify 2026-11-22
$R annotate submit 2026-11-22 --payload note.json
$R annotate list 2026-11-22
$R publish 2026-11-22
$R card 2026-11-22
```

`--inputs DIR` and `--work DIR` point it at scratch folders (reviews go to `<work>/reviews/DATE/`, annotations to `<work>/annotations/DATE/`, cards to `<work>/published/DATE/`). Exit 0 ok, 1 refused (JSON with `code`), 2 usage.

## Tests

```
cd nov14-sprint/nfl/slate
/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I weekly/test_weekly_api.py
```

73 tests, all passing (last run 2026-11-15 09:44Z). The tests copy the real 2026-11-22 inputs into a temp folder and never write to `weekly/reviews/`, `weekly/annotations/` or `weekly/published/`; they also check that the frozen Nov 15 slate and picker files keep their hashes. They compare contract ids with the engine's `selection_markets.key_for` when it can be imported, and check published cards with `pdf_export/brief.py`'s own `validate_card`, `initial_quote` and `check_capture` (extracted from the source, because pypdf and reportlab aren't installed for this interpreter).

## What it does not do

No network or odds refresh (the front door owns that). No weekly journal and no ticket ledger (`journal.py --data weekly/journals/DATE` belongs to the web owner). No PDF. No engine, picks, stake or availability claim: Louisiana availability and fills stay `unknown`. Nothing from Nov 15 is carried into another date.

## Files

- `weekly_api.py`: the code.
- `API.md`: interface, payload, refusal codes, file shapes.
- `test_weekly_api.py`: unit tests.
- `reviews/DATE/reviews.jsonl`, `annotations/DATE/annotations.jsonl`, `published/DATE/...`: created at runtime; empty until a real review is submitted. (`published/2026-11-22/scouting/` holds a PDF this code did not write; it is not part of this API and is not committed with it.)
