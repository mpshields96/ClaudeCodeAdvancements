# Start tonight: the TV paper bot

Written 2026-11-15 (UTC) by the TV bot lane (Claude) for Matthew.
Changed 05:33Z: the paper command now carries `--fresh`.
Changed 06:40Z: section (b) follows Codex's source verdict. No signup is
directed, and the key-in-URL fetch is removed.
Changed 09:43Z: the result page now shows what the same trades make at higher
costs, and a file shorter than the saved run is refused unless `--fresh` is used.
You can read this on your phone. The steps themselves happen on the Mac.

## The short version

- **Paper only.** The bot has no broker connection. It cannot place an order.
- **It is ready to run.** What is left tonight is yours: look at the result page,
  decide the gate. Real bars need a cleared data source, and none is cleared yet.
- **With no real data connected, the bot makes no signals.** It prints one message
  and stops. That is on purpose.
- **The only result so far is a test on made-up bars.** +227.88 on one synthetic
  sample is not evidence of an edge.
- **Nothing from TradingView goes into the bot.** The chart indicator
  (`pine/emax_alerts.pine`) is for your eyes only. A TradingView export is refused.

No step below has Claude or Codex entering a key, opening an account or placing
an order. Those are yours.

---

## (a) Run it tonight in paper mode

Use the Mac's own **Terminal** app, not a Claude chat. The gate refuses to record
a decision made from inside an assistant session.

**1. Open Terminal and go to the project folder.**

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements
```

**2. Run the test replay.** This uses made-up bars and is labelled TEST ONLY.
It should end with a net of +227.88 and rebuild the result page.

```bash
/usr/bin/python3 -I nov14-sprint/tvbot/bot/run.py replay --fresh
```

**3. Open the result page.**

```bash
open nov14-sprint/tvbot/RESULT.html
```

Read "Read this first" and the Risk section. At the default order size, one
stopped trade costs about 79.98, which is 80% of the 100 daily-loss limit.
A smaller size is ready: one stopped trade costs about 33.19, about a third.
I suggest the smaller size. The commands below use it.

The page also has a table named "Same trades, every cost multiplied". On the
test sample the same trades end at +100.63 with costs 4 times the settings and
at a loss of 69.03 with costs 8 times the settings. The costs are settings.
They were not measured from a market.

**4. Decide the gate.** It shows the rule, the settings and the risk, then asks
you to type one of two answers exactly: `APPROVE PAPER ONLY` or `PASS`.
Approving allows paper mode only. It never allows a real order.

```bash
/usr/bin/python3 -I nov14-sprint/tvbot/bot/run.py gate --config nov14-sprint/tvbot/config/smaller_size.json
```

**5. Run the paper bot.** Keep `--fresh` in the command every time. It clears
the saved paper run and rebuilds it from the file you have now.

```bash
/usr/bin/python3 -I nov14-sprint/tvbot/bot/run.py paper --fresh --config nov14-sprint/tvbot/config/smaller_size.json
```

What you will see:

- **No real source yet:** one message beginning `NO REAL SOURCE IS SET UP`, and
  nothing else. No bars read, no signal made. Do section (b) to change that.
- **Real source connected and gate approved:** a first line `REAL BARS, PAPER ONLY`,
  then what the bot decided on those bars. The result page gains a paper section.

To use the default size instead, leave `--config ...` off both commands. An
approval covers one rule and one set of settings, so use the same form for both.

**Tonight the market is closed.** With real bars connected, the bot runs over the
history in your file, up to Friday's close. It does not wait for new bars.
Nothing is scheduled, and nothing runs by itself.

**For new bars later:** get a fresh file from a cleared source (section (b)),
then run step 5 again **with `--fresh`**, exactly as written above.

Why `--fresh` matters: a newly fetched file does not line up with the run saved
from the old file, because the data service returns a sliding window of rows.
Without `--fresh` the bot prints one line beginning `REAL FILE DOES NOT LINE UP`,
reads nothing and changes nothing. With it, the whole file is decided again
from its first row. If the new file starts later than the old one, the earliest
trades in the history can differ from last time.

---

## (b) Connect a real feed (yours to do)

The bot reads one file on this Mac. It never sees a key and never calls a data
service. You fetch the file yourself.

### No real source is cleared yet

Codex reviewed the sources at 06:35Z (`nov14-sprint/codex/NOV15_SOURCE_VERDICT.md`).
Its verdict: no source in the sprint evidence clears the full hourly SPY workflow.

- **Twelve Data Basic is only a candidate for a private, local test.** Its plan
  card allows internal non-display testing and evaluation. It excludes display,
  external sharing and production use. The Basic retention period and hourly SPY
  availability are not established. Sending its bars to a hosted Claude or Codex
  reviewer would count as external sharing.
- **This page no longer tells you to sign up for it.** The fetch command that put
  a key in the web address has been removed.
- **Filling in `source.json` yourself adds no vendor rights.**

What would clear a source: an hourly SPY file you already hold under a licence
that covers computing on it locally, storing it and the outputs; or written
confirmation from a provider covering hourly SPY, retention, and any display or
external-model use you intend.

If you get such a file, put it in `nov14-sprint/tvbot/real/` with a `source.json`
beside it. The fields it needs are in `config/source_template_twelvedata.json`
(`terms_quote`, `approved_by`, `approved_utc`). Then run steps 4 and 5 of
section (a). Until then the bot stops at `NO REAL SOURCE IS SET UP`. That is the
intended state tonight.

### If the bot refuses the file

It prints one line that says why, and makes no signal. The common ones:

- **A bar "has not closed yet":** the last row is still forming. Delete the last
  line of the CSV, or get a fresh file after the hour ends.
- **A bar "opens before the previous bar closed":** the vendor's hourly bars do
  not line up the way the bot expects. Send that line to the chat. Do not edit
  prices to make it pass.
- **Semicolons in the header:** the file is not comma-separated. Get a
  comma-separated copy.
- **"REAL FILE DOES NOT LINE UP WITH THE SAVED PAPER RUN":** `--fresh` was left
  off after a new fetch. Run step 5 of section (a) as written, with `--fresh`.
- **"REAL FILE IS SHORTER THAN THE SAVED PAPER RUN":** `--fresh` was left off and
  the file has fewer rows than the run saved earlier. Same fix: step 5 of
  section (a) as written, with `--fresh`.

### Rules for any other source

- A file you downloaded yourself, from a source whose terms allow this use.
- Header exactly `ts,open,high,low,close,volume` (the first column may be named
  `datetime`). Times in UTC. Oldest row first. Closed bars only.
- `ts` is when the bar opened, like `2026-11-13T14:30:00Z`.
- At least 64 rows before the bot can make any signal.
- Never a TradingView export. It is refused on sight.
- Keep the file on this Mac. Do not share or publish it. The `real` folder is
  set to stay out of git.

### What is not built

- **No live connection.** The bot reads a saved file. A saved file has no arrival
  times, so each bar is treated as arriving when it closes. A decision is ready
  a few seconds later and fills at the open of the next bar after that.
- **No real file has been run yet.** Every check so far used made-up bars. The
  first real file may show something the tests did not.
- **No schedule.** Each run is you typing the command.
