"""Tests for fill_rate_simulator.py (REQ-042).

Maker sniper fill rate simulation — models probability of limit order fills
at various offsets, expiry windows, and spread conditions.
"""
import json
import os
import random
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fill_rate_simulator import (
    FillRateResult,
    FillRateSimulator,
    MarketSnapshot,
    ParameterSweep,
    SpreadModel,
)


class TestMarketSnapshot(unittest.TestCase):
    """MarketSnapshot data class."""

    def test_basic_creation(self):
        snap = MarketSnapshot(ask_cents=94, bid_cents=92, price_cents=93, seconds_to_expiry=600)
        self.assertEqual(snap.ask_cents, 94)
        self.assertEqual(snap.bid_cents, 92)
        self.assertEqual(snap.spread_cents, 2)
        self.assertEqual(snap.seconds_to_expiry, 600)

    def test_spread_computed(self):
        snap = MarketSnapshot(ask_cents=95, bid_cents=90, price_cents=92, seconds_to_expiry=300)
        self.assertEqual(snap.spread_cents, 5)

    def test_zero_spread(self):
        snap = MarketSnapshot(ask_cents=94, bid_cents=94, price_cents=94, seconds_to_expiry=300)
        self.assertEqual(snap.spread_cents, 0)

    def test_maker_price_at_offset(self):
        snap = MarketSnapshot(ask_cents=94, bid_cents=92, price_cents=93, seconds_to_expiry=300)
        self.assertEqual(snap.maker_price(offset_cents=1), 93)
        self.assertEqual(snap.maker_price(offset_cents=2), 92)

    def test_maker_price_cannot_go_below_bid(self):
        snap = MarketSnapshot(ask_cents=92, bid_cents=91, price_cents=91, seconds_to_expiry=300)
        # offset=2 would put maker at 90, below bid 91 — should clamp to bid
        self.assertEqual(snap.maker_price(offset_cents=2), 91)

    def test_fill_possible_with_enough_spread(self):
        snap = MarketSnapshot(ask_cents=94, bid_cents=91, price_cents=92, seconds_to_expiry=300)
        self.assertTrue(snap.fill_possible(offset_cents=1, min_spread_cents=2))

    def test_fill_not_possible_narrow_spread(self):
        snap = MarketSnapshot(ask_cents=93, bid_cents=92, price_cents=92, seconds_to_expiry=300)
        self.assertFalse(snap.fill_possible(offset_cents=1, min_spread_cents=2))


class TestSpreadModel(unittest.TestCase):
    """SpreadModel — empirical or parametric spread distributions."""

    def test_parametric_spread(self):
        model = SpreadModel.parametric(mean_spread=3.0, std_spread=1.0)
        self.assertEqual(model.mean_spread, 3.0)
        self.assertEqual(model.std_spread, 1.0)

    def test_sample_spread_positive(self):
        random.seed(42)
        model = SpreadModel.parametric(mean_spread=3.0, std_spread=1.0)
        spreads = [model.sample_spread() for _ in range(100)]
        self.assertTrue(all(s >= 1 for s in spreads))  # floor at 1c
        self.assertTrue(1.5 < sum(spreads) / len(spreads) < 5.0)

    def test_from_empirical(self):
        spreads = [2, 3, 3, 4, 2, 5, 3, 2, 4, 3]
        model = SpreadModel.from_empirical(spreads)
        self.assertAlmostEqual(model.mean_spread, 3.1, places=1)
        self.assertGreater(model.std_spread, 0)

    def test_empirical_empty_fallback(self):
        model = SpreadModel.from_empirical([])
        self.assertEqual(model.mean_spread, 3.0)  # default fallback

    def test_sample_is_integer(self):
        random.seed(42)
        model = SpreadModel.parametric(mean_spread=3.0, std_spread=1.0)
        s = model.sample_spread()
        self.assertIsInstance(s, int)


class TestFillRateSimulator(unittest.TestCase):
    """Core fill rate Monte Carlo simulation."""

    def test_basic_simulation(self):
        random.seed(42)
        sim = FillRateSimulator(
            spread_model=SpreadModel.parametric(mean_spread=3.0, std_spread=1.0),
            price_vol_per_second=0.01,  # 1% price vol per second (high for testing)
        )
        result = sim.simulate(
            base_price_cents=93,
            offset_cents=1,
            expiry_seconds=300,
            min_spread_cents=2,
            n_simulations=1000,
        )
        self.assertIsInstance(result, FillRateResult)
        self.assertGreaterEqual(result.fill_rate, 0.0)
        self.assertLessEqual(result.fill_rate, 1.0)
        self.assertEqual(result.n_simulations, 1000)

    def test_zero_offset_high_fill_rate(self):
        """Offset 0 = taker. Should have ~100% fill rate (always fills instantly)."""
        random.seed(42)
        sim = FillRateSimulator(
            spread_model=SpreadModel.parametric(mean_spread=3.0, std_spread=1.0),
            price_vol_per_second=0.01,
        )
        result = sim.simulate(
            base_price_cents=93,
            offset_cents=0,
            expiry_seconds=300,
            min_spread_cents=0,
            n_simulations=500,
        )
        # 0 offset = at ask, should fill immediately if spread >= 0
        self.assertGreater(result.fill_rate, 0.9)

    def test_large_offset_low_fill_rate(self):
        """Large offset + short expiry = low fill rate."""
        random.seed(42)
        sim = FillRateSimulator(
            spread_model=SpreadModel.parametric(mean_spread=3.0, std_spread=1.0),
            price_vol_per_second=0.002,  # low vol
        )
        result = sim.simulate(
            base_price_cents=93,
            offset_cents=5,
            expiry_seconds=30,
            min_spread_cents=2,
            n_simulations=500,
        )
        self.assertLess(result.fill_rate, 0.5)

    def test_result_has_mean_time_to_fill(self):
        random.seed(42)
        sim = FillRateSimulator(
            spread_model=SpreadModel.parametric(mean_spread=3.0, std_spread=1.0),
            price_vol_per_second=0.01,
        )
        result = sim.simulate(
            base_price_cents=93, offset_cents=1, expiry_seconds=300,
            min_spread_cents=2, n_simulations=500,
        )
        if result.n_filled > 0:
            self.assertGreater(result.mean_time_to_fill, 0)
            self.assertLessEqual(result.mean_time_to_fill, 300)

    def test_result_has_effective_edge(self):
        random.seed(42)
        sim = FillRateSimulator(
            spread_model=SpreadModel.parametric(mean_spread=3.0, std_spread=1.0),
            price_vol_per_second=0.01,
        )
        result = sim.simulate(
            base_price_cents=93, offset_cents=1, expiry_seconds=300,
            min_spread_cents=2, n_simulations=500,
        )
        # Effective edge = offset * fill_rate (expected price improvement)
        self.assertIsNotNone(result.effective_edge_cents)

    def test_narrow_spread_reduces_eligible(self):
        """With high min_spread, many snapshots become ineligible."""
        random.seed(42)
        sim = FillRateSimulator(
            spread_model=SpreadModel.parametric(mean_spread=2.0, std_spread=0.5),
            price_vol_per_second=0.01,
        )
        result = sim.simulate(
            base_price_cents=93, offset_cents=1, expiry_seconds=300,
            min_spread_cents=4,  # high threshold
            n_simulations=500,
        )
        # Many should be skipped due to narrow spread
        self.assertGreater(result.n_skipped_narrow_spread, 0)

    def test_simulation_deterministic_with_seed(self):
        """Same seed = same result."""
        spread = SpreadModel.parametric(mean_spread=3.0, std_spread=1.0)
        random.seed(99)
        r1 = FillRateSimulator(spread, 0.01).simulate(93, 1, 300, 2, 200)
        random.seed(99)
        r2 = FillRateSimulator(spread, 0.01).simulate(93, 1, 300, 2, 200)
        self.assertEqual(r1.fill_rate, r2.fill_rate)


class TestFillRateResult(unittest.TestCase):
    """FillRateResult data class."""

    def test_summary_string(self):
        result = FillRateResult(
            fill_rate=0.52, n_simulations=1000, n_filled=520,
            n_skipped_narrow_spread=50,
            mean_time_to_fill=145.3, median_time_to_fill=120.0,
            effective_edge_cents=0.52,
            offset_cents=1, expiry_seconds=300, base_price_cents=93,
        )
        s = result.summary()
        self.assertIn("52.0%", s)
        self.assertIn("1000", s)
        self.assertIn("145.3", s)

    def test_to_dict(self):
        result = FillRateResult(
            fill_rate=0.5, n_simulations=100, n_filled=50,
            n_skipped_narrow_spread=10,
            mean_time_to_fill=100.0, median_time_to_fill=90.0,
            effective_edge_cents=0.5,
            offset_cents=1, expiry_seconds=300, base_price_cents=93,
        )
        d = result.to_dict()
        self.assertEqual(d["fill_rate"], 0.5)
        self.assertEqual(d["n_filled"], 50)
        self.assertIn("effective_edge_cents", d)

    def test_json_serializable(self):
        result = FillRateResult(
            fill_rate=0.5, n_simulations=100, n_filled=50,
            n_skipped_narrow_spread=5,
            mean_time_to_fill=100.0, median_time_to_fill=90.0,
            effective_edge_cents=0.5,
            offset_cents=1, expiry_seconds=300, base_price_cents=93,
        )
        s = json.dumps(result.to_dict())
        self.assertIn("fill_rate", s)


class TestParameterSweep(unittest.TestCase):
    """ParameterSweep — sweep across offsets and expiry windows."""

    def test_sweep_basic(self):
        random.seed(42)
        sim = FillRateSimulator(
            spread_model=SpreadModel.parametric(mean_spread=3.0, std_spread=1.0),
            price_vol_per_second=0.01,
        )
        sweep = ParameterSweep(sim)
        results = sweep.run(
            base_price_cents=93,
            offsets=[1, 2],
            expiries=[60, 300],
            min_spread_cents=2,
            n_simulations=100,
        )
        self.assertEqual(len(results), 4)  # 2 offsets * 2 expiries
        # Each result should be a FillRateResult
        for r in results:
            self.assertIsInstance(r, FillRateResult)

    def test_sweep_monotonicity_offset(self):
        """Higher offset should generally mean lower fill rate."""
        random.seed(42)
        sim = FillRateSimulator(
            spread_model=SpreadModel.parametric(mean_spread=4.0, std_spread=1.0),
            price_vol_per_second=0.005,
        )
        sweep = ParameterSweep(sim)
        results = sweep.run(
            base_price_cents=93,
            offsets=[1, 2, 3],
            expiries=[300],
            min_spread_cents=2,
            n_simulations=500,
        )
        rates = [r.fill_rate for r in results]
        # Offset 1 should have higher fill rate than offset 3
        self.assertGreaterEqual(rates[0], rates[2])

    def test_sweep_monotonicity_expiry(self):
        """Longer expiry should generally mean higher fill rate."""
        random.seed(42)
        sim = FillRateSimulator(
            spread_model=SpreadModel.parametric(mean_spread=3.0, std_spread=1.0),
            price_vol_per_second=0.005,
        )
        sweep = ParameterSweep(sim)
        results = sweep.run(
            base_price_cents=93,
            offsets=[1],
            expiries=[30, 120, 300],
            min_spread_cents=2,
            n_simulations=500,
        )
        rates = [r.fill_rate for r in results]
        # 300s should have higher fill rate than 30s
        self.assertGreaterEqual(rates[2], rates[0])

    def test_sweep_to_table(self):
        random.seed(42)
        sim = FillRateSimulator(
            spread_model=SpreadModel.parametric(mean_spread=3.0, std_spread=1.0),
            price_vol_per_second=0.01,
        )
        sweep = ParameterSweep(sim)
        results = sweep.run(93, [1, 2], [60, 300], 2, 100)
        table = sweep.to_table(results)
        self.assertIn("offset", table.lower())
        self.assertIn("expiry", table.lower())
        self.assertIn("%", table)


class TestFromDB(unittest.TestCase):
    """Calibrate simulator from polybot.db trade history."""

    def _make_test_db(self):
        """Create a minimal test DB with expiry_sniper trades."""
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "polybot.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,
                action TEXT NOT NULL,
                price_cents INTEGER NOT NULL,
                count INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                strategy TEXT DEFAULT 'btc_lag',
                is_paper INTEGER NOT NULL DEFAULT 0,
                result TEXT,
                pnl_cents INTEGER,
                signal_price_cents INTEGER,
                close_price_cents INTEGER
            )
        """)
        # Insert 50 expiry_sniper trades at various prices
        import time
        base_ts = time.time() - 86400 * 7  # 7 days ago
        for i in range(50):
            price = random.choice([90, 91, 92, 93, 94])
            result = random.choice(["yes", "yes", "yes", "yes", "no"])  # ~80% WR
            pnl = (100 - price) if result == "yes" else -price
            conn.execute(
                "INSERT INTO trades (timestamp, ticker, side, action, price_cents, count, cost_usd, strategy, is_paper, result, pnl_cents) VALUES (?, ?, ?, ?, ?, 1, ?, 'expiry_sniper_v1', 0, ?, ?)",
                (base_ts + i * 600, f"KXBTC15M-{i}", "yes", "buy", price, price / 100.0, result, pnl),
            )
        conn.commit()
        conn.close()
        return db_path

    def test_from_db_creates_simulator(self):
        random.seed(42)
        db_path = self._make_test_db()
        try:
            sim = FillRateSimulator.from_db(db_path)
            self.assertIsInstance(sim, FillRateSimulator)
            self.assertGreater(sim.spread_model.mean_spread, 0)
        finally:
            os.unlink(db_path)

    def test_from_db_runs_simulation(self):
        random.seed(42)
        db_path = self._make_test_db()
        try:
            sim = FillRateSimulator.from_db(db_path)
            result = sim.simulate(93, 1, 300, 2, 200)
            self.assertIsInstance(result, FillRateResult)
            self.assertGreaterEqual(result.fill_rate, 0.0)
        finally:
            os.unlink(db_path)

    def test_from_db_missing_db(self):
        with self.assertRaises(FileNotFoundError):
            FillRateSimulator.from_db("/nonexistent/path.db")

    def test_from_db_empty_trades(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "polybot.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE trades (
                id INTEGER PRIMARY KEY, timestamp REAL, ticker TEXT, side TEXT,
                action TEXT, price_cents INTEGER, count INTEGER, cost_usd REAL,
                strategy TEXT, is_paper INTEGER, result TEXT, pnl_cents INTEGER
            )
        """)
        conn.commit()
        conn.close()
        try:
            sim = FillRateSimulator.from_db(db_path)
            self.assertIsInstance(sim, FillRateSimulator)
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
