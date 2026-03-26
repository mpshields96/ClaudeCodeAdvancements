#!/usr/bin/env python3
"""
Tests for strategy_health_scorer.py — Statistical strategy health assessment.

Run: python3 self-learning/tests/test_strategy_health_scorer.py
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_trades(strategy, n, win_pct=0.6, pnl_per_win=1.50, pnl_per_loss=-1.00,
                 unsettled_pct=0.0):
    """Generate synthetic trade data with wins/losses interleaved.

    Uses deterministic pattern: trade i is a win if (i * n_wins) // n_settled
    changes — this spreads wins evenly across the sequence.
    """
    trades = []
    n_unsettled = int(n * unsettled_pct)
    n_settled = n - n_unsettled
    n_wins = int(n_settled * win_pct)

    # Build settled results with even distribution
    settled_results = []
    for i in range(n_settled):
        # Bresenham-style distribution: win at evenly spaced intervals
        if n_wins > 0 and (i * n_wins % n_settled) < n_wins:
            settled_results.append("yes")
        else:
            settled_results.append("no")

    settled_idx = 0
    for i in range(n):
        if i < n_unsettled:
            result = None
            pnl = 0
        else:
            result = settled_results[settled_idx]
            pnl = pnl_per_win if result == "yes" else pnl_per_loss
            settled_idx += 1
        trades.append({
            "strategy": strategy,
            "result": result,
            "side": "yes",
            "pnl_usd": pnl,
            "timestamp": 1000 + i * 3600,
            "price_cents": 60,
            "cost_usd": 1.50,
            "market_id": f"MKT-{i % 5}",
            "contracts": 1,
        })
    return trades


def _make_streak_trades(strategy, wins_before, losses, wins_after):
    """Create trades with a specific loss streak pattern."""
    trades = []
    idx = 0
    for _ in range(wins_before):
        trades.append({"strategy": strategy, "result": "yes", "side": "yes", "pnl_usd": 1.50,
                        "timestamp": 1000 + idx * 3600})
        idx += 1
    for _ in range(losses):
        trades.append({"strategy": strategy, "result": "no", "side": "yes", "pnl_usd": -1.00,
                        "timestamp": 1000 + idx * 3600})
        idx += 1
    for _ in range(wins_after):
        trades.append({"strategy": strategy, "result": "yes", "side": "yes", "pnl_usd": 1.50,
                        "timestamp": 1000 + idx * 3600})
        idx += 1
    return trades


class TestScoreStrategy(unittest.TestCase):
    """Test individual strategy scoring."""

    def test_insufficient_data_below_min_sample(self):
        from strategy_health_scorer import score_strategy
        trades = _make_trades("test", 10)
        v = score_strategy("test", trades)
        self.assertEqual(v.verdict, "INSUFFICIENT_DATA")

    def test_healthy_profitable_strategy(self):
        from strategy_health_scorer import score_strategy
        trades = _make_trades("sniper", 50, win_pct=0.7, pnl_per_win=2.50, pnl_per_loss=-1.00)
        v = score_strategy("sniper", trades)
        self.assertEqual(v.verdict, "HEALTHY")
        self.assertGreater(v.pnl_usd, 0)

    def test_kill_deep_losses(self):
        from strategy_health_scorer import score_strategy
        trades = _make_trades("loser", 40, win_pct=0.2, pnl_per_win=1.00, pnl_per_loss=-2.00)
        v = score_strategy("loser", trades)
        self.assertEqual(v.verdict, "KILL")
        self.assertLess(v.pnl_usd, -30)

    def test_pause_long_loss_streak(self):
        from strategy_health_scorer import score_strategy
        # 10 wins, then 10 losses (streak=10), then 10 wins = 30 settled
        trades = _make_streak_trades("streaky", 10, 10, 10)
        v = score_strategy("streaky", trades)
        self.assertIn(v.verdict, ("PAUSE", "KILL"))
        self.assertGreaterEqual(v.max_loss_streak, 8)

    def test_monitor_declining_win_rate(self):
        from strategy_health_scorer import score_strategy
        # First 30 trades: 80% WR, last 20: 30% WR
        good = _make_trades("drifter", 30, win_pct=0.8, pnl_per_win=1.50, pnl_per_loss=-1.00)
        bad = _make_trades("drifter", 20, win_pct=0.3, pnl_per_win=1.50, pnl_per_loss=-1.00)
        # Override timestamps so bad trades come after good
        for i, t in enumerate(bad):
            t["timestamp"] = 2000000 + i * 3600
        all_trades = good + bad
        v = score_strategy("drifter", all_trades)
        # Should flag as at least MONITOR
        self.assertIn(v.verdict, ("MONITOR", "PAUSE", "KILL"))

    def test_handles_unsettled_trades(self):
        from strategy_health_scorer import score_strategy
        trades = _make_trades("partial", 40, win_pct=0.6, unsettled_pct=0.5)
        v = score_strategy("partial", trades)
        # Only 20 settled, >= MIN_SAMPLE_SIZE
        self.assertEqual(v.settled_trades, 20)
        self.assertEqual(v.total_trades, 40)

    def test_win_rate_computed_on_settled_only(self):
        from strategy_health_scorer import score_strategy
        trades = _make_trades("mixed", 30, win_pct=0.6, unsettled_pct=0.1)
        v = score_strategy("mixed", trades)
        # Win rate should not count unsettled as losses
        self.assertGreater(v.win_rate, 0)

    def test_zero_trades_returns_insufficient(self):
        from strategy_health_scorer import score_strategy
        v = score_strategy("empty", [])
        self.assertEqual(v.verdict, "INSUFFICIENT_DATA")
        self.assertEqual(v.total_trades, 0)


class TestComputeLossStreak(unittest.TestCase):
    """Test loss streak computation."""

    def test_no_losses(self):
        from strategy_health_scorer import _compute_loss_streak
        self.assertEqual(_compute_loss_streak([True, True, True]), 0)

    def test_all_losses(self):
        from strategy_health_scorer import _compute_loss_streak
        self.assertEqual(_compute_loss_streak([False, False, False]), 3)

    def test_mixed_pattern(self):
        from strategy_health_scorer import _compute_loss_streak
        outcomes = [True, False, False, False, True, False, False]
        self.assertEqual(_compute_loss_streak(outcomes), 3)

    def test_empty_list(self):
        from strategy_health_scorer import _compute_loss_streak
        self.assertEqual(_compute_loss_streak([]), 0)

    def test_single_loss(self):
        from strategy_health_scorer import _compute_loss_streak
        self.assertEqual(_compute_loss_streak([False]), 1)


class TestComputeRecentWinRate(unittest.TestCase):
    """Test recent win rate sliding window."""

    def test_returns_none_below_window(self):
        from strategy_health_scorer import _compute_recent_win_rate
        self.assertIsNone(_compute_recent_win_rate([True] * 10, window=20))

    def test_computes_last_n(self):
        from strategy_health_scorer import _compute_recent_win_rate
        outcomes = [True] * 30 + [False] * 20  # Last 20 are all losses
        wr = _compute_recent_win_rate(outcomes, window=20)
        self.assertEqual(wr, 0.0)

    def test_all_wins_recent(self):
        from strategy_health_scorer import _compute_recent_win_rate
        outcomes = [False] * 10 + [True] * 20
        wr = _compute_recent_win_rate(outcomes, window=20)
        self.assertEqual(wr, 1.0)


class TestScoreStrategies(unittest.TestCase):
    """Test multi-strategy scoring."""

    def test_scores_all_strategies(self):
        from strategy_health_scorer import score_strategies
        trades = (_make_trades("a", 30, win_pct=0.7) +
                  _make_trades("b", 30, win_pct=0.3, pnl_per_loss=-2.00))
        verdicts = score_strategies(trades)
        names = [v.strategy for v in verdicts]
        self.assertIn("a", names)
        self.assertIn("b", names)

    def test_sorted_by_severity(self):
        from strategy_health_scorer import score_strategies
        trades = (_make_trades("healthy", 50, win_pct=0.7, pnl_per_win=2.00) +
                  _make_trades("killer", 50, win_pct=0.1, pnl_per_win=1.00, pnl_per_loss=-2.00))
        verdicts = score_strategies(trades)
        # KILL should come before HEALTHY
        severity_order = {"KILL": 0, "PAUSE": 1, "MONITOR": 2, "HEALTHY": 3, "INSUFFICIENT_DATA": 4}
        severities = [severity_order.get(v.verdict, 5) for v in verdicts]
        self.assertEqual(severities, sorted(severities))

    def test_empty_trades(self):
        from strategy_health_scorer import score_strategies
        verdicts = score_strategies([])
        self.assertEqual(len(verdicts), 0)

    def test_single_strategy(self):
        from strategy_health_scorer import score_strategies
        trades = _make_trades("solo", 30, win_pct=0.6)
        verdicts = score_strategies(trades)
        self.assertEqual(len(verdicts), 1)
        self.assertEqual(verdicts[0].strategy, "solo")


class TestFormatHealthReport(unittest.TestCase):
    """Test markdown report formatting."""

    def test_produces_markdown_table(self):
        from strategy_health_scorer import score_strategies, format_health_report
        trades = _make_trades("test", 30, win_pct=0.6)
        verdicts = score_strategies(trades)
        report = format_health_report(verdicts)
        self.assertIn("Strategy Health Report", report)
        self.assertIn("test", report)
        self.assertIn("|", report)

    def test_includes_summary(self):
        from strategy_health_scorer import score_strategies, format_health_report
        trades = (_make_trades("good", 50, win_pct=0.7, pnl_per_win=2.00) +
                  _make_trades("bad", 50, win_pct=0.1, pnl_per_loss=-2.00))
        verdicts = score_strategies(trades)
        report = format_health_report(verdicts)
        self.assertIn("Summary", report)

    def test_empty_verdicts(self):
        from strategy_health_scorer import format_health_report
        report = format_health_report([])
        self.assertIn("Strategy Health Report", report)


class TestRealDBCompatibility(unittest.TestCase):
    """Test against real Kalshi schema format."""

    def test_kalshi_schema_trades(self):
        from strategy_health_scorer import score_strategies
        # Simulate real Kalshi data format
        trades = []
        for i in range(50):
            result = "yes" if i % 2 == 0 else "no"
            trades.append({
                "strategy": "expiry_sniper_v1",
                "result": result,
                "pnl_usd": 1.50 if result == "yes" else -1.00,
                "timestamp": 1000 + i * 3600,
                "price_cents": 60,
                "cost_usd": 1.50,
                "market_id": f"TICKER-{i}",
                "contracts": 2,
            })
        verdicts = score_strategies(trades)
        self.assertEqual(len(verdicts), 1)
        self.assertEqual(verdicts[0].strategy, "expiry_sniper_v1")
        self.assertIn(verdicts[0].verdict, ("HEALTHY", "MONITOR", "PAUSE", "KILL"))


if __name__ == "__main__":
    unittest.main()
