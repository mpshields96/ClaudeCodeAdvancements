# MT-10 Phase 3A: Self-Learning Graduation to Kalshi Bot

## Design Document (CCA Session 58, 2026-03-19)

### Problem

CCA has a working self-learning system (journal.py, reflect.py, improver.py, trace_analyzer.py)
that detects patterns and generates improvement proposals for development sessions. The Kalshi
bot has no equivalent — it logs trades to SQLite but doesn't learn from outcomes systematically.

The research_outcomes.py tracker (S57) shows 46 CCA-to-Kalshi deliveries at 0% implementation
rate. The bot can't improve itself because there's no Observe-Detect-Hypothesize-Build loop.

### Architecture: What CCA Builds vs. What Kalshi Bot Uses

**CCA's role** (this project): Build the tools, generate proposals from trade data.
**Kalshi bot's role**: Execute trades, log results, consume proposals.
**Bridge**: File-based handoff (no cross-project writes from CCA).

```
CCA (read-only from Kalshi DB)          Kalshi Bot (reads CCA output)
┌──────────────────────┐                ┌──────────────────────┐
│ trade_reflector.py   │  reads DB →    │ kalshi_bot.db        │
│ (new: analyze trades)│  ←────────     │ trades table         │
│                      │                │ daily_pnl table      │
│ Outputs:             │  writes →      │                      │
│ trading_proposals/   │  ────────→     │ Reads proposals at   │
│   *.jsonl            │                │ session start        │
└──────────────────────┘                └──────────────────────┘
```

### Scope: What Phase 3A Delivers

1. **`trade_reflector.py`** — Reads Kalshi bot's SQLite DB (read-only), detects patterns
2. **Trading proposal format** — Structured JSONL for cross-chat consumption
3. **Trading domain schema** — Event types for journal.py (bet outcomes, strategy shifts)
4. **Safety gates** — No proposal auto-applies to live trading. All require Matthew review.

### Component 1: trade_reflector.py

Location: `self-learning/trade_reflector.py`

**Input:** Path to kalshi_bot.db (read-only)
**Output:** Structured analysis + proposals

Patterns to detect (from Kalshi bot's trades table):

| Pattern | Detection Method | Minimum Data |
|---------|-----------------|--------------|
| Strategy win rate drift | Wilson CI on last N vs. historical | N >= 20 trades |
| Time-of-day bias | Group by hour, chi-squared | N >= 50 trades |
| Streak detection | Runs test (Wald-Wolfowitz) | N >= 15 trades |
| Edge erosion | Rolling window edge_pct trend | N >= 30 trades |
| Sizing inefficiency | Compare actual sizing vs. Kelly optimal | N >= 20 trades |

**All pattern detectors require minimum sample sizes.** No proposals generated below threshold.
This enforces Matthew's standing directive: structural basis + math validation + 30+ data points.

```python
class TradeReflector:
    """Analyze Kalshi bot trade history and generate improvement proposals."""

    def __init__(self, db_path: str):
        """Open DB read-only."""

    def analyze(self) -> dict:
        """Run all detectors. Return structured report."""

    def win_rate_drift(self, strategy: str = None) -> dict:
        """Wilson CI comparison: last 20 vs. all-time."""

    def time_of_day_analysis(self) -> dict:
        """Group trades by hour, identify statistically significant biases."""

    def streak_analysis(self) -> dict:
        """Wald-Wolfowitz runs test for non-random streaks."""

    def edge_trend(self, window: int = 20) -> dict:
        """Rolling window edge_pct: rising, stable, or declining?"""

    def sizing_efficiency(self) -> dict:
        """Compare actual cost_usd vs. Kelly-optimal for each trade."""

    def generate_proposals(self) -> list[dict]:
        """Convert detected patterns into structured proposals."""
```

### Component 2: Trading Proposal Format

```json
{
    "proposal_id": "tp_20260319_abc123",
    "source": "trade_reflector",
    "pattern": "win_rate_drift",
    "strategy": "expiry_sniper",
    "severity": "warning",
    "evidence": {
        "recent_win_rate": 0.82,
        "historical_win_rate": 0.93,
        "wilson_ci_lower": 0.68,
        "sample_size_recent": 22,
        "sample_size_historical": 87,
        "p_value": 0.032
    },
    "recommendation": "Expiry sniper win rate dropped from 93% to 82% (last 22 trades). Wilson CI lower bound 68% overlaps historical. Monitor 10 more trades before adjusting.",
    "action_type": "monitor",
    "auto_applicable": false,
    "created_at": "2026-03-19T17:00:00Z"
}
```

**action_type values:**
- `monitor` — No code change, just watch (most common)
- `parameter_adjust` — Suggests a config.yaml change (e.g., threshold)
- `strategy_pause` — Suggests disabling a strategy temporarily
- `investigation` — Needs deeper analysis (triggers research request to CCA)

**auto_applicable is ALWAYS false for trading.** No proposal auto-applies.
improver.py already classifies trading as HIGH risk. This extends that principle.

### Component 3: Trading Domain Journal Events

Extend journal.py event_type vocabulary for trading:

| event_type | When | Fields |
|------------|------|--------|
| `trade_batch_analyzed` | After running trade_reflector | trades_count, patterns_found, proposals_generated |
| `proposal_created` | New trading proposal | proposal_id, pattern, strategy, severity |
| `proposal_outcome` | Proposal acted on or expired | proposal_id, action_taken, profit_delta_cents |

These integrate into the existing journal.jsonl format — no schema changes needed.

### Safety Requirements (Non-Negotiable)

1. **Read-only DB access** — trade_reflector.py opens kalshi_bot.db with `?mode=ro`
2. **No credential access** — Never read .env, API keys, or auth tokens
3. **No trade execution** — This module OBSERVES, never ACTS
4. **Minimum sample sizes** — Every statistical test requires N >= documented threshold
5. **p-value gating** — No proposal generated unless p < 0.10 (lenient) with explicit p-value
6. **All proposals logged** — Both to trading_proposals.jsonl AND journal.jsonl
7. **No auto-apply** — `auto_applicable` is hardcoded False for all trading proposals

### File Layout

```
self-learning/
├── trade_reflector.py          # NEW: Kalshi trade pattern analysis
├── trading_proposals.jsonl     # NEW: Proposal store (append-only)
└── tests/
    └── test_trade_reflector.py # NEW: Tests (target: 40+)
```

### Build Order (TDD)

1. `TradeReflector.__init__` — open DB read-only, verify schema
2. `win_rate_drift()` — Wilson CI, minimum N=20
3. `edge_trend()` — rolling window
4. `time_of_day_analysis()` — hourly grouping + chi-squared
5. `streak_analysis()` — runs test
6. `sizing_efficiency()` — Kelly comparison
7. `generate_proposals()` — orchestrator
8. CLI entry point

### Success Criteria

- [ ] trade_reflector.py reads kalshi_bot.db (read-only) and produces proposals
- [ ] All statistical tests have documented minimum sample sizes
- [ ] All proposals include p-values or confidence intervals
- [ ] No proposal has auto_applicable=True
- [ ] 40+ tests passing
- [ ] Generates at least 1 meaningful proposal from Matthew's real trade history
- [ ] Journal integration: events logged for each analysis run

### Dependencies

- Python stdlib only (sqlite3, statistics, math)
- CCA's journal.py (for event logging)
- Read access to /Users/matthewshields/Projects/polymarket-bot/kalshi_bot.db

### What This Does NOT Do

- Does not modify the Kalshi bot's code
- Does not access Kalshi API or any external service
- Does not auto-adjust trading parameters
- Does not read credentials or financial account data
- Does not write to the polymarket-bot directory
