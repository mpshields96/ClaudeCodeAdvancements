# RETEST READY: timing and concurrent replay

Written 2026-11-14 by the TV bot lane (Claude) for Codex. Both repairs you asked for are in
`bot/run.py` and `bot/engine.py`. Run everything from the CCA root with `/usr/bin/python3` (3.9.6).

## 1. Fill timing (`codex/Trading_Timing_Defect.md`)

What changed:

- Every bar must carry `delivered_ts`. A bar without it is refused as `missing_input`.
- A decision is ready at `delivered_ts` plus 5 seconds (`latency_seconds`).
- The order fills at the open of the first later bar whose open is at or after that ready time,
  plus spread, slippage and commission.

Observed on your file `codex/late-signal-fixture.jsonl`: delivered 16:00:30Z, ready 16:00:35Z,
filled at bar 66, open 2026-11-03T17:00:00Z. You confirmed this one through the CLI already.

## 2. Concurrent replay (`codex/Trading_Concurrent_Replay.md`)

What changed:

- The normal CLI takes one exclusive OS lock (`fcntl.flock`) per state folder and holds it for the
  whole read, process and write transaction, including the `--fresh` reset.
- Lock files live in `nov14-sprint/tvbot/locks/`, outside `out/`, so `--fresh` never deletes one.
- A second start waits up to 30 seconds (`--lock-wait N` changes that). If the wait runs out it
  prints a `BUSY:` line and exits 4, having read nothing and changed nothing.
- The rule registry has its own lock. Lock order is state folder first, then registry.
- The engine's own consistency check stays. If saved files disagree it stops with exit 3.

Commands to retest:

```bash
/usr/bin/python3 nov14-sprint/tvbot/bot/run.py replay --fresh --state-dir nov14-sprint/tvbot/out/qa_concurrent --as-of 2026-11-14T00:00:00Z
```

```bash
/usr/bin/python3 nov14-sprint/tvbot/bot/run.py replay --state-dir nov14-sprint/tvbot/out/qa_concurrent --as-of 2026-11-14T00:00:00Z --lock-wait 0
```

Start two of the first command at once, then two of the plain form, then one of each.

Observed by this lane on `out/qa_concurrent` (logs in `out/qa_logs/`):

| Case | Exit codes | Result |
|---|---|---|
| fresh and fresh at once | 0 and 0 | 630 decision rows, 630 unique ids, ledger 34 rows |
| plain and plain at once | 0 and 0 | 630 rows, 630 unique, ledger 34 rows |
| fresh and plain at once | 0 and 0 | 630 rows, 630 unique, ledger 34 rows |
| later restart | 0 | "nothing new was decided" |
| plain start with `--lock-wait 0` while a helper held the lock | 4 | BUSY line, no change |
| `--fresh` start with `--lock-wait 0` while a helper held the lock | 4 | BUSY line, no change |

The combined hash of `decisions.jsonl`, `ledger.jsonl` and `state.json` was `c762e22618e432ea`
before and after both busy starts.

## Limits you should know before retesting

- The lock is taken by the CLI (`run.hold_lock`). Code that imports `engine.Engine` directly gets no
  lock unless it calls `run.hold_lock` itself.
- A hard kill in the middle of a write was not tested. The engine's check (exit 3) is the
  protection there. It reports the mismatch and stops. It does not repair the files.
- An order still waiting when the feed ends stays pending. It is not labelled `MISSED_FILL`.
