# TV bot lane: handoff to the parent

Written 2026-11-15T09:48:35Z by the TV bot lane (Claude, session `local_<session>`).
For the current Claude parent, sprint-coord (`local_<session>`), and
the top session (`local_<session>`).

**State: the lane's assignment is finished and closed. This chat is idle.** No successor is
needed. If work resumes later, read this file, then the first section of `STATUS.md`.
The window that covers this work ends at 11:23:32Z on 2026-11-15. A new chat does not restart it.

## What Matthew can use now

- `START_TONIGHT.md`: the steps, written for the phone. Current version 09:43Z.
- `RESULT.html`: the result page. Open it on the Mac.
- The commands, run by him in the Mac's Terminal from the project folder:
  - `/usr/bin/python3 -I nov14-sprint/tvbot/bot/run.py replay --fresh` (test on made-up bars)
  - `/usr/bin/python3 -I nov14-sprint/tvbot/bot/run.py gate --config nov14-sprint/tvbot/config/smaller_size.json`
  - `/usr/bin/python3 -I nov14-sprint/tvbot/bot/run.py paper --fresh --config nov14-sprint/tvbot/config/smaller_size.json`
- With no real data connected, `paper` prints `NO REAL SOURCE IS SET UP` and stops. That is the
  intended state today.

## What it is

A paper-only bot in two separate parts: a TradingView chart indicator for Matthew's eyes
(`pine/emax_alerts.pine`), and an offline runner that reads one local file. Nothing from
TradingView goes into the runner; such input is refused. There is no broker connection.

## Verified (UTC, 2026-11-15)

- 09:47:27Z: 101 unit tests, OK.
- 09:42Z to 09:43Z, after the last code change: `replay --fresh --expect` exit 0, ledger MATCH
  34 rows, net +227.88 on made-up bars; `adverse` 28 of 28; `sweep` +270.30, +227.88, +185.47,
  +100.63, -69.03 at 0, 1, 2, 4 and 8 times the cost settings; `paper` exit 2 with no source;
  `gate --show` nothing recorded; `check_review.py` PASS 15 of 15.
- `gate/` and `real/` do not exist. The Pine file is unchanged (sha256 begins `a04cdd266f21096b`).
- Independent reviews on record: Codex accepted the local paper demo and its refusal controls
  and did not accept real hourly SPY operation (`nov14-sprint/codex/NOV15_ACCEPTANCE.md`). The
  advisor's second pass scored 18 PASS, 0 FAIL, 4 NOT YET (`nov14-sprint/advisor/PASS2_TRADING.md`).
- The three changes made after those reviews (cost table on the page, shorter-file refusal, the
  page note for a refused later file) are covered by this lane's tests only. No reviewer has
  checked them yet.

## Sent and asked

- The 09:43Z `START_TONIGHT.md` was sent to Matthew's device at about 09:49Z (the advisor's C4).
- One review ask was queued to Codex at 09:49:47Z for the three changes above and a phone-width
  look at the page. Receipt: `receipts/TO_CODEX_review_ask_20261115T094947Z.txt`. It is queued,
  not confirmed read, and this chat is not polling for it. A reply would arrive as a file under
  `nov14-sprint/codex/` or as a chat message.

## Not verified

- The cost table and the new page note were not looked at in a browser or at phone width. A text
  check shows the new table inside the page's side-scroll wrapper, like the other four.
- No real file has been run. +227.88 on one synthetic sample is not evidence of an edge.
- No person has run `gate` or `paper` in Terminal.

## Open, and whose it is

- **Matthew or a vendor:** a data source cleared for hourly SPY (advisor item B2), then a first
  real file (B5). Codex's verdict is that no source in the sprint evidence is cleared
  (`nov14-sprint/codex/NOV15_SOURCE_VERDICT.md`).
- **Matthew:** the gate decision. Nobody else may record it.
- **The advisor's file** `nov14-sprint/advisor/ACCEPTANCE_RUBRIC.md`: its draft short version
  for the phone still says to sign up for Twelve Data Basic and shows `paper` without `--fresh`.
  `START_TONIGHT.md` is the current text.
- Optional hardening, only worth doing once a source is cleared: durable bar numbering, and a
  check for a bar missing in the middle of a day. Details in `STATUS.md`, "Known limits".

## Next runnable step

For Matthew: steps 1 to 4 of `START_TONIGHT.md` section (a). For a later owner: nothing to build
until a source is cleared.

## Rules that carry forward

- Paper only. No orders, accounts, keys, purchases, paid data, installs, schedules or pushes.
- Never write `gate/paper_gate.json` and never create `real/`. Both are Matthew's steps.
- TradingView values never go into the runner or the ledger. Do not edit `pine/emax_alerts.pine`.
- Do not run `run.py holdout`.

## Commit

The lane is committed locally and not pushed. The first commit is `4945e65` (09:49:02Z, 119 files,
this lane's paths only). A small second commit holds this file's last edits and one receipt.
`git log --oneline -- nov14-sprint/tvbot` lists them. A third commit, `90c95ba` (09:54Z), changes
`STATUS.md` only: it points at the research lane's Twelve Data addendum (header auth is
documented by the vendor and was not run; no source is cleared). A last small commit holds
this paragraph.
Left out on purpose: `locks/` (runtime lock files), `self-learning/` (a stray from an old hook)
and `bot/__pycache__/`. `START_TONIGHT.md` section (b) and the last line of `STATUS.md` carry the
coordinator's 06:40Z edits, and `pine/README.md` lines 3 and 32 carry the coordinator's earlier
note of Codex's compile check.
