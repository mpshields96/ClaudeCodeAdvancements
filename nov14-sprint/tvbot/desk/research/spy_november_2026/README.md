# November 2026 SPY signal study

The frozen shadow rule and moving-average crossover were compared with cash across 24 same-session windows on November 10–13. Each window used only earlier completed hourly bars. The historical source contained 3,900 valid regular-session minutes across November 2–13. The first six sessions supplied initial history. The displayed results describe hypothetical executions over a single subsequent bar.

Open the [interactive replay](../../ui/spy_study.html) or [one-page decision brief](decision_brief.pdf). The static replay opens directly from disk, with no credentials or server. The clickable windows show the estimated move, threshold and volatility before revealing the later outcome. The two-share scenario illustrates the effect of spreading the same assumed minimum commission across two shares.

## Reproduce the numbers

Use the exact November SPY ZIP identified in [the aggregate results](results.json). The free download periodically changes to a newer sample. This program validates the source checksum and covers only the dated research extract. Run from the repository's tvbot directory, replacing SAMPLE.zip with your copy of the vendor archive.

    python3 -IB desk/research/spy_november_2026/evaluate.py desk SAMPLE.zip --reference-shares 1 --out /tmp/spy-one-share.json
    python3 -IB desk/research/spy_november_2026/evaluate.py desk SAMPLE.zip --reference-shares 2 --out /tmp/spy-two-share.json

FirstRate provides [free samples](https://firstratedata.com/free-intraday-data) under its [data license](https://firstratedata.com/about/license). The release contains derived results and code. Raw market data stays with its holder.
