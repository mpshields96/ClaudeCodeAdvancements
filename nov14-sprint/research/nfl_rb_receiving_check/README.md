# Running-back receiving yards > 22.5, registered forecast check

Source code and the frozen protocol only (`protocol.md`, frozen before the sample was fetched). The nflverse tables, manifest and `results.json` stay local (`private/` and `results.json` are ignored).

1. `python3 -I fetch_public.py` downloads public nflverse snap-count, weekly player stat and player ID tables into `private/` with SHA-256 provenance.
2. `python3 -I check_rbs.py > results.json` compares five fixed probabilities (pooled base rate, last 5, last 10, role-shrunk last 10, role group) by Brier score and log loss with week-block intervals.

Diagnostic only. No prices, ROI, sizing or new picks are produced, and it never changes an existing selection.
