# Automated paper session (`paper_runner.py --auto`)

This runs on the Alpaca **paper** desk only. It uses simulated money, places no live orders, and installs no schedule. You start it once, and it ends by itself.

## The one-line commands

`<desk>` is the desk folder, the one that contains `alpaca_session.py`.

Automated paper run (a launcher outside this folder should call exactly this):

```
/bin/zsh "<desk>/after-approval/Start Automated Paper Session.command" --no-browser
```

This is the same as `/usr/bin/python3 -IB "<desk>/alpaca/paper_runner.py" --auto --minutes 120 --every 30 --no-browser`. Options you add later win. For example, `--minutes 60` gives a 60-minute run, up to the runner's 400-minute maximum.

Monitor-only run (never presses Enable or Arm, same as before):

```
/bin/zsh "<desk>/after-approval/Run Timed Paper Session.command" --no-browser
```

Without `--auto` the runner works exactly as before. Its defaults are 60 minutes and a check every 60 seconds.

## What `--auto` does, in order

1. It runs the same refusals as monitor-only. It needs the approved limits worksheet, holds one runner lock, refuses any live desk or any other paper desk process, and requires the desk to identify as `alpaca-paper` with a real broker, this state folder and `alpaca_paper.json`.
2. It runs the checked reconcile, and refuses on a mismatched position, an outside order or a reconcile that is not clean.
3. Every 30 seconds it runs one desk check (the Check button). The desk covers between-bar fills and protective stops inside each check.
4. It waits until three things hold on the same check: the strategy warm-up is `ready`, the desk preflight shows the regular session open (`calendar` and `venue clock` ok), and every other preflight row is ok except "adapter enabled". It never presses on a desk that is already armed.
   - On a fractional desk, the rows "SPY fractionable" and "non-margin cash" only pass after a connection check. If those two are the **only** failing rows, the runner presses the desk's **connection check** once per run (`POST /api/alpaca/connection_check {}`). At Alpaca that check is GET-only (account, clock and the SPY asset) and sends no order. If the rows still fail afterwards, the rest of the run is monitor-only. While any other row fails, it does not press the check and keeps waiting.
5. Right before pressing it runs the paper-identity check, confirms the desk can bound Arm (see "Arm expiry" below), and runs the checked reconcile again. Then it presses **Enable** (`POST /api/alpaca/enable {"confirm": true}`), only if the adapter is off, and **Arm** (`POST /api/arm {"expires_utc": <run end>}`). It presses each at most once per run.
6. It reads back the expiry the desk actually set. If that expiry is later than the run end, or can't be read, the runner presses **Stop & Close** at once and ends the run, so its arm never outlasts the run. This is a backstop; the capability check in step 5 should mean it never fires.
7. At the deadline (or Ctrl-C) it does the usual clean end. It presses Stop & Close when the desk owns paper exposure, runs the checked reconcile, and records **FLAT**, **EXPOSED** or **UNRESOLVED** (exit 0, 7 or 8). The run record in `state-alpaca-paper/runner/` has an `auto` section. That section shows when Enable and Arm were pressed, the requested and actual expiry, any stop trigger and any switch to monitor-only.

## When it stops (and never enables or arms again)

On any of these it stops checking and goes to the clean end:

- a desk Stop, such as the operator's Stop & Close
- a risk latch: `DAILY_LOSS_STOP`, today's `day_stop`, or a Stop whose reason names a loss or risk
- an unresolved or unknown order: `UNRESOLVED_SUBMIT`, an ambiguous recovery, or a blocking alarm such as `UNKNOWN_STATUS` or `ORDER_MISSING`
- a foreign order or position: `FOREIGN_ORDER`, `FOREIGN_POSITION`, `POSITION_MISMATCH`, an outside order in the reconcile, or a broker position the desk doesn't match
- a lost connection: one failed check, a non-200 check, `BROKER_DISCONNECTED` or `BROKER_UNREACHABLE`
- the adapter being disabled after the runner enabled it
- a desk that no longer identifies as this paper desk

If the arm lapses or is removed any other way, the rest of the run is monitor-only. Each check line shows `AUTO: MONITOR-ONLY ... never re-arms`, and the record says so too.

The runner can't reach Clear Stop, Play, Schedule, Disable, Pause or Resume in either mode.

## Arm expiry

An automated arm must not outlast the run. The runner presses Enable and Arm only on a desk whose `/api/health` reports `"arm_bounded_expiry": true`. This desk reports it: `/api/arm` honours a body `expires_utc` and can only shorten the arm with it.

Every arm, automated or from the UI's Arm button, ends at the wind-down at the latest. The wind-down is `WIND_DOWN_S` (15 minutes) before the regular close. The close is the desk calendar's, early closes included, or the venue clock's next close when that is earlier. A requested expiry later than the wind-down is capped to it. An earlier one is kept. An expiry that is in the past or can't be parsed is refused. Inside the wind-down no arm is taken (`ARM_WIND_DOWN`), so no new entry starts there. The arm's bounds show in the session state as `arm_bounds`.

When the arm ends, the desk's own Stop & Close sends the reduce-only close while the venue still takes it, then reconciles until the broker confirms flat or an explicit UNRESOLVED handoff.

On an older desk without the flag, `--auto` says so in the first line, presses nothing, and runs as monitor-only to the deadline with the usual clean end. No Stop gets latched.
