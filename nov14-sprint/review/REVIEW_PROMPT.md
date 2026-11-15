# Review prompt for a frozen TV decision packet

This is the exact text sent to a fresh Claude reviewer. `{FOLDER}` is replaced with a folder that holds only the packet file and its `bars_through_signal_bar.jsonl`. Nothing else goes to the reviewer: no later bars, fill, profit, or any other model's opinion.

---

You are an independent reviewer of one paper-trading decision. It is a research exercise on synthetic data. Nothing you say can place, authorize or change an order.

The folder {FOLDER} holds exactly two files: a decision packet (`PKT-*.json`) and the closed bars up to the decision (`bars_through_signal_bar.jsonl`). Read only those two files. Do not open, list or search any other file or folder. If you compute anything, use `/usr/bin/python3 -I` and read only those two files.

Check the packet on its own terms:
1. Recompute every item in `frozen.arithmetic_to_check` from the bars and inputs, and say whether each packet value matches.
2. Does the action follow from the rule as written (`frozen.rule`) and the inputs at the decision?
3. Do the timing fields agree with each other and with the fill rule in `frozen.forward_plan`?
4. Do the proposed order and the risk limits agree?
5. What information would you need, and is missing, to be confident?

Reply with one JSON object only, following `expected_challenge_schema` in the packet. Copy `packet_id` from the packet. Set `live_or_recorded` to `live`, `reviewed_utc` to the current UTC time from `date -u +%Y-%m-%dT%H:%M:%SZ`, `authority` to the exact text the schema gives, and `reviewer_model` to the model name you believe you are. After the JSON, on separate lines, list every file you opened and every command you ran.
