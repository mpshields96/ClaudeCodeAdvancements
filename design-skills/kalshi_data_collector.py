"""Kalshi financial data collector for MT-33 Strategic Intelligence Report.

Reads polybot.db (READ-ONLY) and extracts trade statistics, strategy breakdowns,
daily P&L, bankroll history, and chart-ready data structures.

Usage:
    from kalshi_data_collector import KalshiDataCollector
    collector = KalshiDataCollector()  # uses default DB path
    data = collector.collect_all()     # full report data

Safety:
    - All DB access is read-only (no writes, no schema changes)
    - Never exposes credentials, API keys, or wallet addresses
    - Graceful degradation if DB is missing or empty
"""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_PATH = os.path.expanduser(
    "~/Projects/polymarket-bot/data/polybot.db"
)


class KalshiDataCollector:
    """Read-only collector for Kalshi bot trading data."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def is_available(self):
        """Check if the DB exists and has tables."""
        if not os.path.exists(self.db_path):
            return False
        if os.path.getsize(self.db_path) == 0:
            return False
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='trades'"
            )
            has_trades = cur.fetchone() is not None
            conn.close()
            return has_trades
        except Exception:
            return False

    def _connect(self):
        """Open read-only connection."""
        return sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)

    # ── Summary stats ────────────────────────────────────────────────────

    def get_trade_summary(self):
        """Overall trade statistics (live trades only for key metrics)."""
        if not self.is_available():
            return self._empty_summary()

        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_paper = 0 THEN 1 ELSE 0 END) as live,
                    SUM(CASE WHEN is_paper = 1 THEN 1 ELSE 0 END) as paper,
                    SUM(CASE WHEN is_paper = 0 AND result IS NOT NULL THEN 1 ELSE 0 END) as settled,
                    SUM(CASE WHEN is_paper = 0 AND result IS NULL THEN 1 ELSE 0 END) as unsettled,
                    SUM(CASE WHEN is_paper = 0 AND pnl_cents > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN is_paper = 0 AND pnl_cents <= 0 AND result IS NOT NULL THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN is_paper = 0 AND pnl_cents IS NOT NULL THEN pnl_cents ELSE 0 END) as total_pnl
                FROM trades
            """).fetchone()

            settled = row["settled"] or 0
            wins = row["wins"] or 0
            win_rate = round(100.0 * wins / settled, 1) if settled > 0 else None

            # Date range
            dates = conn.execute("""
                SELECT MIN(datetime(timestamp, 'unixepoch')) as first_dt,
                       MAX(datetime(timestamp, 'unixepoch')) as last_dt
                FROM trades WHERE is_paper = 0
            """).fetchone()

            return {
                "total_live_trades": row["live"] or 0,
                "total_paper_trades": row["paper"] or 0,
                "settled_trades": settled,
                "unsettled_trades": row["unsettled"] or 0,
                "wins": wins,
                "losses": row["losses"] or 0,
                "total_pnl_usd": (row["total_pnl"] or 0) / 100.0,
                "win_rate_pct": win_rate,
                "first_trade_date": dates["first_dt"] or "",
                "last_trade_date": dates["last_dt"] or "",
            }
        finally:
            conn.close()

    def _empty_summary(self):
        return {
            "total_live_trades": 0,
            "total_paper_trades": 0,
            "settled_trades": 0,
            "unsettled_trades": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl_usd": 0.0,
            "win_rate_pct": None,
            "first_trade_date": "",
            "last_trade_date": "",
        }

    # ── Strategy breakdown ───────────────────────────────────────────────

    def get_strategy_breakdown(self):
        """Per-strategy stats for live trades, sorted by total P&L descending."""
        if not self.is_available():
            return []

        conn = self._connect()
        try:
            rows = conn.execute("""
                SELECT
                    strategy,
                    COUNT(*) as trade_count,
                    SUM(CASE WHEN pnl_cents > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl_cents <= 0 AND result IS NOT NULL THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN result IS NOT NULL THEN 1 ELSE 0 END) as settled,
                    SUM(CASE WHEN pnl_cents IS NOT NULL THEN pnl_cents ELSE 0 END) as total_pnl,
                    AVG(CASE WHEN pnl_cents IS NOT NULL THEN pnl_cents END) as avg_pnl
                FROM trades
                WHERE is_paper = 0
                GROUP BY strategy
                ORDER BY total_pnl DESC
            """).fetchall()

            result = []
            for r in rows:
                settled = r[4] or 0
                wins = r[2] or 0
                result.append({
                    "strategy": r[0],
                    "trade_count": r[1],
                    "wins": wins,
                    "losses": r[3] or 0,
                    "win_rate_pct": round(100.0 * wins / settled, 1) if settled > 0 else 0.0,
                    "total_pnl_usd": (r[5] or 0) / 100.0,
                    "avg_pnl_usd": round((r[6] or 0) / 100.0, 2),
                })
            return result
        finally:
            conn.close()

    # ── Daily P&L ────────────────────────────────────────────────────────

    def get_daily_pnl(self):
        """Daily P&L aggregation from trades (since daily_pnl table is empty)."""
        if not self.is_available():
            return []

        conn = self._connect()
        try:
            rows = conn.execute("""
                SELECT
                    date(timestamp, 'unixepoch') as trade_date,
                    SUM(pnl_cents) as day_pnl,
                    COUNT(*) as trade_count,
                    SUM(CASE WHEN pnl_cents > 0 THEN 1 ELSE 0 END) as wins
                FROM trades
                WHERE is_paper = 0 AND pnl_cents IS NOT NULL
                GROUP BY trade_date
                ORDER BY trade_date
            """).fetchall()

            result = []
            cumulative = 0.0
            for r in rows:
                day_pnl = (r[1] or 0) / 100.0
                cumulative += day_pnl
                result.append({
                    "date": r[0],
                    "pnl_usd": day_pnl,
                    "cumulative_pnl_usd": round(cumulative, 2),
                    "trade_count": r[2],
                    "wins": r[3] or 0,
                })
            return result
        finally:
            conn.close()

    # ── Bankroll history ─────────────────────────────────────────────────

    def get_bankroll_history(self, max_points=200):
        """Bankroll timeline, downsampled to max_points for chart rendering."""
        if not self.is_available():
            return []

        conn = self._connect()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM bankroll_history WHERE source = 'api'"
            ).fetchone()[0]

            if total == 0:
                return []

            # Downsample by taking every Nth row
            step = max(1, total // max_points)
            rows = conn.execute(f"""
                SELECT timestamp, balance_usd
                FROM bankroll_history
                WHERE source = 'api' AND (rowid % {step} = 0 OR rowid = 1)
                ORDER BY timestamp
                LIMIT {max_points}
            """).fetchall()

            return [
                {
                    "timestamp": r[0],
                    "datetime": datetime.fromtimestamp(r[0], tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "balance_usd": r[1],
                }
                for r in rows
            ]
        finally:
            conn.close()

    # ── Chart-ready data ─────────────────────────────────────────────────

    def chart_cumulative_pnl(self):
        """LineChart data: cumulative P&L over time."""
        daily = self.get_daily_pnl()
        return {
            "labels": [d["date"] for d in daily],
            "values": [d["cumulative_pnl_usd"] for d in daily],
        }

    def chart_strategy_winrate(self):
        """HorizontalBarChart data: win rate by strategy."""
        strategies = self.get_strategy_breakdown()
        return {
            "labels": [s["strategy"] for s in strategies],
            "values": [s["win_rate_pct"] for s in strategies],
        }

    def chart_daily_pnl_values(self):
        """HistogramChart data: raw daily PnL values for distribution."""
        daily = self.get_daily_pnl()
        return {
            "values": [d["pnl_usd"] for d in daily],
        }

    def chart_strategy_pnl_distribution(self):
        """BoxPlot data: PnL distribution per strategy."""
        if not self.is_available():
            return {"categories": [], "data_series": []}

        conn = self._connect()
        try:
            # Get distinct strategies with settled trades
            strategies = conn.execute("""
                SELECT DISTINCT strategy FROM trades
                WHERE is_paper = 0 AND pnl_cents IS NOT NULL
                ORDER BY strategy
            """).fetchall()

            categories = []
            data_series = []
            for (strategy,) in strategies:
                values = conn.execute("""
                    SELECT pnl_cents / 100.0 FROM trades
                    WHERE is_paper = 0 AND pnl_cents IS NOT NULL AND strategy = ?
                """, (strategy,)).fetchall()
                categories.append(strategy)
                data_series.append([v[0] for v in values])

            return {"categories": categories, "data_series": data_series}
        finally:
            conn.close()

    def chart_winrate_vs_profit(self):
        """ScatterPlot data: win rate (x) vs avg profit (y) per strategy."""
        strategies = self.get_strategy_breakdown()
        points = []
        for s in strategies:
            if s["win_rate_pct"] is not None:
                points.append({
                    "x": s["win_rate_pct"],
                    "y": s["avg_pnl_usd"],
                    "label": s["strategy"],
                })
        return {
            "series": [{"name": "Strategies", "data": points}],
        }

    def chart_trade_volume(self):
        """DonutChart data: trade count share by strategy."""
        strategies = self.get_strategy_breakdown()
        return {
            "labels": [s["strategy"] for s in strategies],
            "values": [s["trade_count"] for s in strategies],
        }

    def chart_bankroll_timeline(self):
        """AreaChart data: bankroll balance over time."""
        history = self.get_bankroll_history(max_points=100)
        return {
            "labels": [h["datetime"] for h in history],
            "values": [h["balance_usd"] for h in history],
        }

    def chart_edge_forest(self):
        """ForestPlot data: per-asset/price alpha with Wilson CI.

        Groups sniper trades by ticker prefix (asset) + price_cents bucket.
        Computes win rate alpha vs break-even, with Wilson score CI.
        """
        if not self.is_available():
            return {"studies": []}

        conn = self._connect()
        try:
            # Extract asset from ticker (e.g. KXBTCD-26MAR10-T22 -> BTC)
            rows = conn.execute("""
                SELECT
                    CASE
                        WHEN ticker LIKE 'KXBTC%' THEN 'BTC'
                        WHEN ticker LIKE 'KXETH%' THEN 'ETH'
                        WHEN ticker LIKE 'KXSOL%' THEN 'SOL'
                        WHEN ticker LIKE 'KXXRP%' THEN 'XRP'
                        ELSE SUBSTR(ticker, 3, 3)
                    END as asset,
                    price_cents as price,
                    COUNT(*) as n,
                    SUM(CASE WHEN pnl_cents > 0 THEN 1 ELSE 0 END) as wins
                FROM trades
                WHERE is_paper = 0 AND pnl_cents IS NOT NULL
                  AND strategy = 'sniper'
                  AND price_cents IS NOT NULL
                GROUP BY asset, price_cents
                HAVING COUNT(*) >= 10
                ORDER BY asset, price_cents
            """).fetchall()

            studies = []
            import math
            z = 1.96  # 95% CI
            for asset, price_c, n, wins in rows:
                price = price_c / 100.0
                wr = wins / n
                be = price  # break-even = contract price
                alpha = wr - be

                # Wilson score interval for win rate
                denom = 1 + z * z / n
                center = (wr + z * z / (2 * n)) / denom
                margin = z * math.sqrt((wr * (1 - wr) + z * z / (4 * n)) / n) / denom
                ci_lower = center - margin - be
                ci_upper = center + margin - be

                label = f"{asset} {price_c}c"
                studies.append({
                    "label": label,
                    "estimate": round(alpha, 4),
                    "ci_lower": round(ci_lower, 4),
                    "ci_upper": round(ci_upper, 4),
                })

            return {"studies": studies}
        except Exception:
            return {"studies": []}
        finally:
            conn.close()

    def chart_price_candles(self):
        """CandlestickChart data: daily OHLC of sniper contract prices.

        Aggregates sniper bet prices into daily candles showing price range.
        Uses price_cents column and datetime(created_at, 'unixepoch') for grouping.
        """
        if not self.is_available():
            return {"candles": []}

        conn = self._connect()
        try:
            rows = conn.execute("""
                SELECT
                    DATE(created_at, 'unixepoch') as day,
                    MIN(price_cents) as low,
                    MAX(price_cents) as high,
                    (SELECT price_cents FROM trades t2
                     WHERE t2.is_paper = 0 AND t2.strategy = 'sniper'
                       AND t2.price_cents IS NOT NULL
                       AND DATE(t2.created_at, 'unixepoch') = DATE(t1.created_at, 'unixepoch')
                     ORDER BY t2.created_at ASC LIMIT 1) as open_p,
                    (SELECT price_cents FROM trades t2
                     WHERE t2.is_paper = 0 AND t2.strategy = 'sniper'
                       AND t2.price_cents IS NOT NULL
                       AND DATE(t2.created_at, 'unixepoch') = DATE(t1.created_at, 'unixepoch')
                     ORDER BY t2.created_at DESC LIMIT 1) as close_p
                FROM trades t1
                WHERE is_paper = 0 AND strategy = 'sniper'
                  AND price_cents IS NOT NULL AND created_at IS NOT NULL
                GROUP BY DATE(created_at, 'unixepoch')
                HAVING COUNT(*) >= 3
                ORDER BY day DESC
                LIMIT 30
            """).fetchall()

            candles = []
            for day, low, high, open_p, close_p in reversed(rows):
                if all(v is not None for v in (low, high, open_p, close_p)):
                    candles.append({
                        "label": day[-5:] if day else "",  # MM-DD
                        "open": open_p / 100.0,
                        "high": high / 100.0,
                        "low": low / 100.0,
                        "close": close_p / 100.0,
                    })

            return {"title": "Sniper Contract Prices (Daily)", "candles": candles}
        except Exception:
            return {"candles": []}
        finally:
            conn.close()

    # ── Aggregator ───────────────────────────────────────────────────────

    def collect_all(self):
        """Collect all financial data for report integration.

        Returns a JSON-serializable dict with all analytics and chart data.
        If DB is unavailable, returns empty structures with available=False.
        """
        available = self.is_available()
        return {
            "available": available,
            "db_path": self.db_path,
            "summary": self.get_trade_summary(),
            "strategies": self.get_strategy_breakdown(),
            "daily_pnl": self.get_daily_pnl(),
            "bankroll": self.get_bankroll_history(),
            "charts": {
                "cumulative_pnl": self.chart_cumulative_pnl(),
                "strategy_winrate": self.chart_strategy_winrate(),
                "daily_pnl_histogram": self.chart_daily_pnl_values(),
                "strategy_pnl_distribution": self.chart_strategy_pnl_distribution(),
                "winrate_vs_profit": self.chart_winrate_vs_profit(),
                "trade_volume": self.chart_trade_volume(),
                "bankroll_timeline": self.chart_bankroll_timeline(),
                "edge_forest": self.chart_edge_forest(),
                "price_candles": self.chart_price_candles(),
            },
        }
