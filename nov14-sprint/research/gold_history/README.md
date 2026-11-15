# Gold swing-break basket, falsification test

Source code only. The protocol (`PREREGISTRATION.md`) was frozen before any price rows were read. The HistData XAU/USD M1 bid files, downloaded HTML, quote and fill rows and every output stay in the local `private/` folder and the ignored `*.csv`/`*.json`/`*.html` files.

Rerun order, from this folder:

1. `python3 -I fetch.py 2021 2022 2023` (public HistData XAU/USD M1 bid download form, no login; files, URL, bytes and SHA-256 into `private/`)
2. `python3 -I fetch_year_quotes.py` (the twelve published XAU/USD tick archives, once, in sequence)
3. `python3 -I replay.py` (the preregistered experiment: predeclared modes and cost cases)
4. `python3 -I quote_check.py` (frozen supplementary January replay with actual bid and ask)
5. `python3 -I quote_year.py` (2023 quote series on the identical eligible sessions)
6. `python3 -I causal_stress.py` (future-availability check with chronological waits for actual quotes)
7. `python3 -I check_results.py` (cross-check of net cash, per-session returns and end positions)

Optional: `python3 -I gold_intraday_check.py .` marks the frozen 2023 simulation at every quoted tick (collateral hurdle is a sensitivity, not a broker margin schedule).

Simulated research. No broker, account or order. File hashes for the nine protocol files were checked against the author's publisher note before this copy.
