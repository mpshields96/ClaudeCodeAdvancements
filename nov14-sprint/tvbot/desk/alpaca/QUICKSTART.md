# SPY paper desk

**Start with the worksheet.** Double-click **Open SPY Paper Desk.command** in the extracted folder. In the source checkout, use **desk/Open Alpaca Paper Desk.command**. A local rehearsal opens in your browser. Its test values apply to synthetic fills. Your personal worksheet starts blank.

1. Open **Setup (limits)** and enter your whole shares per entry, maximum order dollars, estimated loss per trade, total SPY exposure and daily loss ceiling.
2. Enter a price and stop distance in the sizing calculator. Adjust the assumed costs, exposure already in use and day loss to see how much capacity remains. The share suggestion is read-only. Save your draft, review the changes and approve the exact values you want. An open desk keeps its loaded limits for that session.
3. When you are ready for the first authenticated test, store your own Alpaca **paper** keys using the setup guide in **desk/alpaca/SETUP.md**. Double-click **After You Approve/Check Paper Connection.command**. This checks account eligibility, SPY, the venue clock and the latest free IEX bid and ask. A working connection can still report a closed market or a stale quote.
4. **After You Approve/Open Connected Paper Desk.command** opens a separate paper session. The adapter and daily arm are distinct controls. Use **Check for new closed bar** to request data and act on a fresh signal. The first request also loads prior bars for strategy warm-up. Check the source, session, open orders and Stop status in the desk.

In a source checkout, the after-approval commands are under **desk/after-approval**.

5. **After You Approve/Run Timed Paper Session.command** is a separate, optional timed run of that same paper desk. You start it, and it stops by itself. It checks for a new closed bar on a timer (default 60 minutes, every 60 seconds; for example `--minutes 30 --every 60 --at-end leave`). Each line shows the account mode, the data time, and whether the result was a strategy call or a data/timing pass. At the end it reconciles with the broker and reports flat or exposed; by default it presses Stop & Close only when the broker position matches the desk. It refuses a live or non-paper desk, a second runner and a second desk process. It never presses Enable or Arm and installs no schedule, so orders still need your own manual controls. It reports a fill only when Alpaca confirms it. A record of each run is saved under the paper state folder in **runner**.

The connected strategy can open long SPY positions with whole-share, day-limit buy orders. The limit price bounds the entry dollars. A stop estimates loss at its trigger, and the market can move past it. This is a manually checked desk. A fill or change at Alpaca can precede its appearance in the desk. Before walking away from exposure, inspect the broker-confirmed position, working exits and Stop result.

## Review a decision

- **Decision lab** records the challenger alongside the active strategy and cash on the same completed bars. Reveal later outcomes and verify the recorded inputs. The challenger stays in shadow.
- **SPY historical study** lets you call up 24 decisions from November 10–13, 2026. Choose the one- or two-share research case and reveal the next window. These research sizes do not set a trading limit. The historical brief and study files are in **desk/research/spy_november_2026**.
- **Session review** includes filled trades, a selected pass, costs and limits. Select a week and use its report button to generate the printable review. Fill-price results and the cost sensitivity use only closed round trips. Your actual account fee schedule is separate.

The free feed covers IEX. Alpaca's simulator may price fills using a different market view. The historical study uses a separate licensed sample. The build was exercised with synthetic venue responses and public historical data. The first account-authenticated test is yours after limits approval.

[Alpaca market data](https://docs.alpaca.markets/us/docs/about-market-data-api) · [Paper execution](https://docs.alpaca.markets/us/docs/paper-trading)
