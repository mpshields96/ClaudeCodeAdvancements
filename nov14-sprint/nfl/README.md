# NFL research sources (paper research only)

Code and the frozen pre-registration only. No datasets, odds rows, forecasts, results or reports are published. Nothing here places a bet or reads an account, and no paper result implies a real edge.

| Folder | What it is | Run (from the repo root) |
|---|---|---|
| `walkforward/` | Pre-registered walk-forward model vs listed market prices. `PREREGISTRATION.json` was frozen before the first test run. | `/usr/bin/python3 -I nov14-sprint/nfl/walkforward/wf.py`, tests `test_wf.py` |
| `adversarial/` | Independent replay, adversarial checks and accepted-price stress. Imports no walk-forward code. | `run_adversarial.py`, `audit_walkforward.py`, tests `test_adv.py` |

Inputs you supply locally (not published): the public nflverse `games.csv` at `nov14-sprint/nfl/data/raw/games.csv`. `wf.py` refuses to run unless its SHA-256 matches the value in `PREREGISTRATION.json`. `run_adversarial.py` also reads the local slate lane outputs (`slate/`, `real/`), which stay private; without them it cannot run. Tests that need `games.csv` skip or fail with a clear message when it is absent.
