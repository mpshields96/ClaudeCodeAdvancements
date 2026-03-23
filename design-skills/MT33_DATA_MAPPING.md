# MT-33 Phase 1: Data Mapping — Strategic Intelligence Report

## DB Location

Primary: `~/Projects/polymarket-bot/data/polybot.db` (2.3 MB, 4,684 trades)
Secondary: `~/Projects/polymarket-bot/refs/kalshi-btc/kalshi_bot.db` (132 KB, legacy BTC)

Root-level `kalshi_bot.db`, `trading.db`, `trading_bot.db`, `polybot.db`, `polydb.db` are all 0 bytes.

---

## Primary DB Schema (data/polybot.db)

### Table: trades (4,684 rows)
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| timestamp | REAL | Unix epoch |
| ticker | TEXT | Market ticker (e.g., `aqc-cbb-e8-2026-04-06-pur`) |
| side | TEXT | `yes` or `no` |
| action | TEXT | `buy` or `sell` |
| price_cents | INTEGER | Limit price 1-99 |
| count | INTEGER | Number of contracts |
| cost_usd | REAL | Dollars spent |
| strategy | TEXT | Strategy name (21 distinct) |
| edge_pct | REAL | Estimated edge |
| win_prob | REAL | Model probability |
| is_paper | INTEGER | 1=paper, 0=live |
| result | TEXT | `yes` / `no` / NULL (unsettled) |
| pnl_cents | INTEGER | P&L after settlement |
| settled_at | REAL | Settlement timestamp |
| signal_price_cents | INTEGER | Signal entry price |
| exit_price_cents | INTEGER | Exit price |
| kalshi_fee_cents | INTEGER | Kalshi fees |
| gross_profit_cents | INTEGER | Gross before fees |
| signal_features | TEXT | JSON feature blob |

### Table: daily_pnl (0 rows — unused)
Empty. All P&L data lives in trades table.

### Table: bankroll_history (22,625 rows)
| Column | Type | Notes |
|--------|------|-------|
| timestamp | REAL | Unix epoch |
| balance_usd | REAL | Balance at snapshot |
| source | TEXT | `api` or `paper_simulation` |

### Table: kill_switch_events (0 rows)
No kill switch events recorded yet.

---

## Data Availability Summary

| Data Point | Source | Row Count | Status |
|------------|--------|-----------|--------|
| Trade history | trades | 4,684 | RICH |
| Strategy breakdown | trades.strategy | 21 strategies | RICH |
| Live vs paper | trades.is_paper | 1,197 live / 3,487 paper | RICH |
| Settled P&L | trades.pnl_cents | 1,858 settled | RICH |
| Bankroll timeline | bankroll_history | 22,625 | RICH |
| Daily P&L | daily_pnl | 0 | EMPTY (derive from trades) |
| Kill switch events | kill_switch_events | 0 | EMPTY |
| Self-learning journal | journal.jsonl | 854 entries | RICH |
| APF snapshots | ~/.cca-apf-snapshots.jsonl | ~30 entries | MODERATE |
| Principle registry | ~/.cca-principles.json | NOT FOUND | EMPTY |
| Research outcomes | ~/.cca-research-outcomes.jsonl | NOT FOUND | EMPTY |

---

## Strategy Performance (Live Trades Only)

| Strategy | Trades | Wins | Losses | Win Rate | Total PnL |
|----------|--------|------|--------|----------|-----------|
| expiry_sniper_v1 | 920 | 858 | 62 | 93.3% | +$369.00 |
| eth_orderbook_imbalance_v1 | 153 | 80 | 73 | 52.3% | +$198.48 |
| orderbook_imbalance_v1 | 127 | 68 | 59 | 53.5% | +$26.70 |
| btc_lag_v1 | 46 | 38 | 8 | 82.6% | +$15.63 |
| btc_lag | 1 | 1 | 0 | 100% | +$3.50 |
| sol_lag_v1 | 1 | 1 | 0 | 100% | +$4.77 |

Date range: 2026-01-30 to 2026-03-23 (53 days)

---

## Pillar 1: Kalshi Financial Analytics — Chart Mappings

### Chart 1: Cumulative P&L Line (LineChart)
```sql
SELECT date(timestamp, 'unixepoch') as d,
       SUM(pnl_cents) OVER (ORDER BY timestamp) / 100.0 as cum_pnl
FROM trades WHERE is_paper = 0 AND pnl_cents IS NOT NULL
ORDER BY timestamp;
```
Chart type: `LineChart` — x=date, y=cumulative P&L USD

### Chart 2: Win Rate by Strategy (HorizontalBarChart)
```sql
SELECT strategy,
       ROUND(100.0 * SUM(CASE WHEN pnl_cents > 0 THEN 1 ELSE 0 END) /
             COUNT(*), 1) as win_rate
FROM trades WHERE is_paper = 0 AND result IS NOT NULL
GROUP BY strategy ORDER BY win_rate DESC;
```
Chart type: `HorizontalBarChart` — y=strategy, x=win rate %

### Chart 3: Daily P&L Distribution (HistogramChart)
```sql
SELECT SUM(pnl_cents) / 100.0 as daily_pnl
FROM trades WHERE is_paper = 0 AND pnl_cents IS NOT NULL
GROUP BY date(timestamp, 'unixepoch');
```
Chart type: `HistogramChart` — raw daily PnL values, auto-binned

### Chart 4: Profit Distribution by Strategy (BoxPlot)
```sql
SELECT strategy, pnl_cents / 100.0 as pnl_usd
FROM trades WHERE is_paper = 0 AND pnl_cents IS NOT NULL;
```
Chart type: `BoxPlot` — one box per strategy showing PnL distribution

### Chart 5: Win Rate vs Avg Profit (ScatterPlot)
```sql
SELECT strategy,
       ROUND(100.0 * SUM(CASE WHEN pnl_cents > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as wr,
       ROUND(AVG(pnl_cents) / 100.0, 2) as avg_pnl
FROM trades WHERE is_paper = 0 AND result IS NOT NULL
GROUP BY strategy;
```
Chart type: `ScatterPlot` — x=win_rate, y=avg_profit, labels=strategy names

### Chart 6: Trade Volume by Strategy (DonutChart)
```sql
SELECT strategy, COUNT(*) as n
FROM trades WHERE is_paper = 0
GROUP BY strategy ORDER BY n DESC;
```
Chart type: `DonutChart` — share of trades by strategy

### Chart 7: Bankroll Over Time (AreaChart)
```sql
SELECT datetime(timestamp, 'unixepoch') as ts, balance_usd
FROM bankroll_history WHERE source = 'api'
ORDER BY timestamp;
```
Chart type: `AreaChart` — x=time, y=balance (gradient fill)

### Chart 8: Daily Trade Count (BarChart)
```sql
SELECT date(timestamp, 'unixepoch') as d, COUNT(*) as n
FROM trades WHERE is_paper = 0
GROUP BY d ORDER BY d;
```
Chart type: `BarChart` — x=date, y=trade count

---

## Pillar 2: Self-Learning Intelligence — Chart Mappings

### Chart 9: Journal Event Types (BarChart)
Source: `self-learning/journal.jsonl` — parse `type` field, count per type

### Chart 10: APF Trend (Sparkline)
Source: `~/.cca-apf-snapshots.jsonl` — parse `apf_score` per session

### Chart 11: Strategy Health (GaugeChart)
Source: `strategy_health_scorer.py` — run on trades data, get verdict

---

## Pillar 3-6: Deferred to Phase 2+

Research pipeline, market context, recommendations, and self-reference hook
require building data collectors first. Phase 1 focuses on Pillars 1-2 which
have available data NOW.

---

## Implementation Plan (Phase 2)

1. `kalshi_data_collector.py` — new file in design-skills/
   - Reads polybot.db (READ-ONLY) via Python sqlite3
   - Runs the SQL queries above
   - Returns structured dicts ready for chart_generator.py
   - NEVER exposes credentials, only aggregated metrics

2. Extend `report_generator.py` CCADataCollector
   - Import KalshiDataCollector
   - Add financial analytics to report data JSON
   - Graceful degradation: if DB not found, skip financial section

3. New Typst sections in cca-report.typ
   - Financial Analytics page(s)
   - Self-Learning Intelligence page

4. Wire chart_generator.py chart types to real data
   - Each chart call uses the SQL results from step 1
