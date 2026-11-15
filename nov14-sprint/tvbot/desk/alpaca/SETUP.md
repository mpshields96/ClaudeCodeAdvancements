# Alpaca paper desk: setup guide for Matthew

This guide takes you from nothing to your first manual **paper** session for SPY on Alpaca's free IEX
data. You do every step that involves your account, your keys or your limits. The agents built the
tools and never touched any of those.

**What has and hasn't happened (as of 2026-11-15).** No authenticated call to Alpaca has ever been
made from this desk. No agent has opened a connection to any Alpaca host, read a key, or looked in
your Keychain. Everything was built and tested against a local mock with made-up ids and bars. The
first real request is yours, in step 7, after you approve your own limits.

Commands below run from the desk folder, `nov14-sprint/tvbot/desk` inside the repository. From the
repository root (the folder that contains `nov14-sprint/`), run `cd nov14-sprint/tvbot/desk` first.
Every path below (`launch.py`, `alpaca/...`, `state/...`) is relative to that desk folder.

---

## 1. Make the paper account and paper keys (Alpaca website, you)

1. Sign in at alpaca.markets and switch the dashboard to your **Paper** account.
2. Generate an API key pair there. Alpaca shows the secret once, so keep the page open until step 2.
3. Check the key id. Paper key ids usually start with `PK`; live-money ones usually start with `AK`.
   Alpaca calls this prefix a hint, not a guarantee
   ([Alpaca key security guide](https://alpaca.markets/learn/api-key-security-best-practices-for-alpaca-builders)).
   The same guide calls the host the real boundary, and a paper key sent to the live host is refused
   with a 401. The desk only ever talks to the fixed paper host `paper-api.alpaca.markets`. As a second
   guard it refuses any key id that starts with `AK`. If your key id starts with `AK`, you made it on the
   live account: go back and make the pair on the Paper account.

## 2. Store the keys in your macOS Keychain (Terminal, you)

Type these two commands yourself. The `-w` at the end, with nothing after it, makes macOS **prompt**
for the value, so the key never lands in your shell history. Paste the value at each prompt (it asks
twice, and nothing shows while you type).

```bash
security add-generic-password -s alpaca-paper -a key-id -w
```

```bash
security add-generic-password -s alpaca-paper -a secret-key -w
```

- First prompt: paste the **key id**. Second command: paste the **secret key**.
- Replacing keys later? Add `-U` before `-w` to update the existing item.
- The names matter: service `alpaca-paper`, accounts `key-id` and `secret-key`.
- Don't put keys in any file in this folder, in `.zshrc`, or in a chat.

## 3. If the desk says "not found or access was denied"

That message names the item it looked for. It means one of these:

- The item doesn't exist or is spelled differently. List what's stored (this shows names, not the
  secret):

  ```bash
  security find-generic-password -s alpaca-paper -a key-id
  ```

  If it prints "could not be found", repeat step 2 with the exact names.
- You clicked **Deny** on the Keychain prompt. The first time a real session reads the item, macOS may
  ask whether `security` can use it. Choose **Allow** (or **Always Allow** to skip the prompt next time).
- The value has a space or line break in it. Re-store it with `-U` (step 2).

**Alternative: environment variables.** The desk also accepts `APCA_API_KEY_ID` and
`APCA_API_SECRET_KEY` set in the one Terminal window that starts the desk. They vanish when the window
closes. Keychain is the recommended route because env vars are easier to leak (screenshots, `env`
dumps, a stray `export` saved in a file). The same paper-key check applies.

## 4. Write your limits (desk Setup panel, or a file; you)

Five numbers, all yours. No agent picks, suggests or fills them, and there are no defaults.

| Field | What it means |
|---|---|
| `fixed_shares` | Whole shares per entry. Required. No default, no formula. |
| `max_loss_per_trade` | Dollars you accept losing on one trade if the stop is hit. |
| `daily_loss` | Dollars of realized loss in a day after which new entries stop. |
| `per_trade_notional` | Largest dollar value of one order (shares x price). |
| `gross_exposure` | Largest dollar value of everything open plus everything working, together. |

**In the desk (easiest).** Open the **Setup** panel. Type your numbers into the draft and press
**Save draft**. A half-filled draft is fine while you think. Under it, **Check effects** shows, at a
reference price and stop distance you choose:

- the notional and the dollars you make or lose per $1 SPY move;
- the estimated loss at the stop, with fees and slippage **labeled as assumed**;
- remaining room under each cap, and the worst case if every working order fills;
- a plain pass or fail line for each cap, with the reason.

Read-only alternatives ("at most N shares keeps a $X stop under your per-trade loss") and one
**TEST EXAMPLE** preset are shown beside the draft. They never change your draft unless you click
**Copy into draft**, and copying never approves anything.

**As a file (alternative).** Copy `alpaca/limits.template.json` somewhere of yours, replace each `null`
with your number, and save it. The desk refuses the template itself and refuses any copy until you
approve it in step 5.

## 5. Approve your limits (you)

Approval is the only thing that makes limits real. The desk decides that from how the limits got
there (your local approval, recorded in the file), never from what the numbers happen to be. So your
numbers can match the test example and still count, as long as you approved them.

**In the Setup panel:** press **Review and approve**. The desk shows every change from your last
approved limits (old to new). Type `APPROVE PAPER LIMITS` exactly, give a short reason, and confirm.

**Or in Terminal:**

```bash
/usr/bin/python3 -IB alpaca/sizing.py approve --state-dir state --from-file /path/to/your_limits.json
```

It prints the old-to-new changes and asks for the same phrase and a reason. `show` instead of
`approve` prints the current worksheet.

Either way the desk writes `state/limits_approved.json` with `provenance: "operator-approved"`, the
time, your reason, the change list and a fingerprint (hash) of that whole record. If any part of
that file is edited by hand afterwards (a number, the time, the reason, the change list), the
fingerprint stops matching and the real paper path refuses it.

Approval is tied to what you reviewed. If the draft or your approved limits change after you
open **Review and approve** (another tab, another window, a Terminal approval), the approval is
refused and you're asked to reload and check again. Cap checks use exact decimal arithmetic, so
a stop-out of $1.0014 counts as over a $1.00 cap, and share counts always round down. To
change limits, save a new draft and approve again. To withdraw approval, delete that one file.

## 6. Rehearse in mock mode (no keys, no network)

Double-click **Open Alpaca Paper Desk.command** in Finder (the coordinator's INTEGRATION.md has the
final details), or run:

```bash
/usr/bin/python3 -IB launch.py --broker alpaca-paper --transport mock
```

Mock mode talks only to an in-process fake Alpaca with made-up ids and bars. It never reads your keys.
It works with a draft: the banner then says **DRAFT LIMITS (not approved)**. Things to try:

- The banner at the top shows the mode (`alpaca-mock`), the evidence label, the data label, whether
  the adapter is enabled, and where the limits came from.
- **Enable** asks you to confirm. **Disable** asks for a reason. The adapter always starts disabled.
- **Check for new bars** is the only way bars advance. There is no Play button and no timer in
  Alpaca modes: when you're not clicking, nothing happens.
- Partial fills, orders the desk isn't sure about, and reconcile alarms show plainly in the orders
  area, each with its evidence label.
- **Stop** closes the session and disables the adapter. A restart shows it disabled again.

## 7. Your first manual paper session (you, when you're ready)

This is the first time anything sends your keys to Alpaca, and it goes only to the paper host.

**First, the readiness check.** It refuses to touch any credential until your approved limits load.
Then it makes four read-only GET requests to the paper host and submits no order:

```bash
/usr/bin/python3 -IB alpaca/readiness.py --state-dir state --limits state/limits_approved.json
```

(`alpaca/readiness.py` is Codex's checker. Use the state folder and limits file you approved.)
If it passes, start the session:

```bash
/usr/bin/python3 -IB launch.py --broker alpaca-paper --transport https --limits state/limits_approved.json
```

(Flag names follow the build contract; check INTEGRATION.md for the coordinator's final command.)

- The desk refuses to start the real path if the limits file is missing, still a draft, the template,
  a test example, edited after approval, or has any blank, zero or negative value, or no whole
  `fixed_shares`. Each refusal says which.
- It starts **disabled**. Press **Enable** and confirm. Keys are read from Keychain only when a request
  is actually sent.
- Each **Check for new bars** asks Alpaca's free IEX feed for the latest closed SPY bar. SPY only.
  No paid data route exists in the code.
- **Stop** works at any time, even while disabled, and turns the adapter off.
- Nothing runs in the background. Close the window and the desk does nothing until you open it again.

## What is not tested yet

Everything above was exercised only against the local mock. These are unknown until your step 7:

- Alpaca's real responses, error texts and rate limits, and whether your account and keys work.
- How real partial fills, cancels and late fills arrive and time out.
- The exact Keychain prompt macOS shows the first time.
- Real IEX bar timing and gaps, and how the trading calendar handles a holiday or early close.

## Undo and clean-up

- Turn off trading: **Disable** in the desk, or **Stop**.
- Withdraw limit approval: delete `state/limits_approved.json`.
- Remove your keys from Keychain:

  ```bash
  security delete-generic-password -s alpaca-paper -a key-id
  ```

  ```bash
  security delete-generic-password -s alpaca-paper -a secret-key
  ```

- Revoke the keys themselves on the Alpaca paper dashboard.
