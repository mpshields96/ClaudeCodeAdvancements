# Four-way shadow comparison

Run the cash, EMA, trend challenger, and frozen one-bar reversal rules against the same recorded SPY paper-lab inputs. This offline utility never opens an account, loads an order manager, or places an order. It refuses to write inside the desk state directory. Records are hypothetical; engineering orders and broker fills are outside the inputs.

Provide the UTC time at which your protocol was actually recorded. Store that independent protocol before examining new outcomes. A command-line cutoff is not evidence that the protocol existed at that time. Keep source and run directories private.

From the desk directory, run the following with your own values:

```sh
python3 -IB research/shadow_compare.py --desk . --state-dir /path/to/paper-lab-state \
  --freeze-utc YYYY-MM-DDTHH:MM:SSZ --out-parent /path/to/private-runs
```

Run once soon after the signal bar closes, before the next outcome bar. Run again with new observations and add `--witness-dir /path/to/the/first/run` to distinguish a forecast actually saved before the outcome from a reconstruction. Each run gets a fresh directory. Only use earlier runs made against the same desk decision code and data source. The runner verifies hash chains, reproduces baseline choices, compares existing scores, and separates genuine IEX, synthetic and ineligible observations. A reconstruction can test a frozen rule; it is not an observed forward call. A local SHA is an integrity check rather than a third-party timestamp.

See each run’s `summary.json` for base/doubled cost results, sample size, long/short counts, excluded windows and evidence classes. The comparison does not change the live long-only pilot, its sizing, or its controls. No sample data, market history or private protocol is included.
