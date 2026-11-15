# Recording a ticket and its sportsbook return

In the Sunday desk, open the card and choose **Record a ticket I already placed**. Enter the sportsbook, exact line, price offered, price accepted, stake, and actual placement time. The desktop form takes Chicago local time. The journal keeps the original call and the reported ticket on their own terms.

Open **After the games** to enter the amount the book actually returned on that particular ticket. Enter the **gross return, including any stake returned**. A $10 ticket that lost and returned nothing has a $0 gross return and a −$10 net. A full $10 refund has a $10 gross return and $0 net. A $9.50 cashout on $10 has a −$0.50 net. An unconfirmed ticket stays pending. The public box score can produce a separate estimate before the sportsbook settles.

Select the matching book and ticket when you have several tickets on one game. A correction appends a new entry with a note. The journal preserves the prior entry and counts only the latest confirmed return for that ticket.

## Journal interface

`record_ticket(journal, contract_id, book, accepted_price, stake, now, placed_utc=..., offered_price=...)` returns a ticket with its `ticket_id`. The placement time must include its timezone and precede kickoff. A later reporting time is allowed. Exact resubmissions are refused under the journal lock. Older tickets remain readable with their original timestamps and hashes.

`record_settlement(journal, ticket_id, gross_return, outcome, now, *, confirmed=True, prior_sha=None, note="", by="matthew")` accepts the ticket's stable ID. Use the currency or units of the recorded stake. Outcomes are `win`, `loss`, `push`, `void`, `refund`, `cashout`, `adjustment`, and `other`. A first entry uses no prior hash. A correction requires the current settlement hash and a note. The function raises `JournalError` for invalid input, stale corrections, and unconfirmed returns.

The equivalent command is `python3 -IB journal.py settlement TICKET_ID --gross-return 9.50 --outcome cashout --confirmed`. The command prints the settlement hash. Use `--prior-sha HASH --note REASON` to amend it. Use `grade` to read the current ticket IDs and settlement revisions.

`evaluate(State(journal))["tickets"]` supplies one row per ticket, including its ID, accepted price, `accepted_in_band`, original football grade, estimated gross, the latest `settlement` (or null), and `actual_net` (or null). Under `score.confirmed_ticket_returns`, each stake unit has confirmed and pending counts, confirmed stake, gross return, and net return. All cash amounts are self-reported from the operator. The archive excludes personal tickets and settlements.
