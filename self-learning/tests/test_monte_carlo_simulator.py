"""Tests for Monte Carlo bankroll simulator (REQ-040).

Tests the simulation engine, bet distribution extraction, ruin/target probability,
and synthetic bet generation. Uses synthetic data — no DB dependency.
"""
import json
import math
import os
import random
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monte_carlo_simulator import (
    BetDistribution,
    MonteCarloSimulator,
    SimulationResult,
    SyntheticBetGenerator,
)


class TestBetDistribution(unittest.TestCase):
    """Test BetDistribution — parameterize from historical bet outcomes."""

    def test_from_outcomes_basic(self):
        """Create distribution from a list of pnl values."""
        outcomes = [0.90, 0.90, 0.90, 0.90, -10.0]  # 4 wins, 1 loss
        dist = BetDistribution.from_outcomes(outcomes)
        self.assertEqual(dist.total_bets, 5)
        self.assertAlmostEqual(dist.win_rate, 0.8, places=2)
        self.assertAlmostEqual(dist.avg_win, 0.90, places=2)
        self.assertAlmostEqual(dist.avg_loss, -10.0, places=2)

    def test_from_outcomes_all_wins(self):
        dist = BetDistribution.from_outcomes([0.50, 0.60, 0.70])
        self.assertAlmostEqual(dist.win_rate, 1.0)
        self.assertAlmostEqual(dist.avg_win, 0.60, places=2)
        self.assertEqual(dist.avg_loss, 0.0)

    def test_from_outcomes_all_losses(self):
        dist = BetDistribution.from_outcomes([-5.0, -10.0])
        self.assertAlmostEqual(dist.win_rate, 0.0)
        self.assertEqual(dist.avg_win, 0.0)
        self.assertAlmostEqual(dist.avg_loss, -7.5, places=2)

    def test_from_outcomes_empty(self):
        dist = BetDistribution.from_outcomes([])
        self.assertEqual(dist.total_bets, 0)
        self.assertAlmostEqual(dist.win_rate, 0.0)

    def test_from_params(self):
        """Create distribution from explicit parameters."""
        dist = BetDistribution(
            win_rate=0.957,
            avg_win=0.90,
            avg_loss=-10.0,
            total_bets=964,
            daily_volume=30,
        )
        self.assertAlmostEqual(dist.win_rate, 0.957)
        self.assertEqual(dist.daily_volume, 30)

    def test_expected_value(self):
        """EV = win_rate * avg_win + (1 - win_rate) * avg_loss."""
        dist = BetDistribution(
            win_rate=0.957,
            avg_win=0.90,
            avg_loss=-10.0,
            total_bets=964,
        )
        ev = dist.expected_value()
        expected = 0.957 * 0.90 + 0.043 * (-10.0)
        self.assertAlmostEqual(ev, expected, places=4)

    def test_expected_value_positive(self):
        """Sniper strategy should have positive EV."""
        dist = BetDistribution(
            win_rate=0.957,
            avg_win=0.90,
            avg_loss=-10.0,
            total_bets=964,
        )
        self.assertGreater(dist.expected_value(), 0)

    def test_variance(self):
        """Variance of single bet outcome."""
        dist = BetDistribution(
            win_rate=0.957,
            avg_win=0.90,
            avg_loss=-10.0,
            total_bets=964,
        )
        var = dist.variance()
        self.assertGreater(var, 0)

    def test_sample_single(self):
        """Sample a single bet outcome."""
        dist = BetDistribution(
            win_rate=0.957,
            avg_win=0.90,
            avg_loss=-10.0,
            total_bets=964,
        )
        random.seed(42)
        outcome = dist.sample()
        self.assertIn(outcome, [dist.avg_win, dist.avg_loss])

    def test_sample_distribution(self):
        """Over many samples, win rate should converge to parameterized rate."""
        dist = BetDistribution(win_rate=0.80, avg_win=1.0, avg_loss=-5.0)
        random.seed(123)
        samples = [dist.sample() for _ in range(10000)]
        win_count = sum(1 for s in samples if s > 0)
        empirical_wr = win_count / len(samples)
        self.assertAlmostEqual(empirical_wr, 0.80, delta=0.02)

    def test_from_outcomes_sets_win_loss_distributions(self):
        """From outcomes should capture win/loss value distributions."""
        outcomes = [0.50, 0.60, 0.70, 0.80, -5.0, -10.0]
        dist = BetDistribution.from_outcomes(outcomes)
        self.assertEqual(len(dist.win_values), 4)
        self.assertEqual(len(dist.loss_values), 2)

    def test_sample_empirical(self):
        """When win/loss values are available, sample from empirical distribution."""
        outcomes = [0.50, 0.60, 0.70, 0.80, -5.0, -10.0]
        dist = BetDistribution.from_outcomes(outcomes)
        random.seed(42)
        samples = [dist.sample_empirical() for _ in range(1000)]
        # All samples should be from our actual outcome values
        valid_values = set(outcomes)
        for s in samples:
            self.assertIn(s, valid_values)

    def test_kelly_fraction(self):
        """Kelly criterion calculation."""
        dist = BetDistribution(
            win_rate=0.957,
            avg_win=0.90,
            avg_loss=-10.0,
        )
        kelly = dist.kelly_fraction()
        # Kelly = p/a - q/b where a=avg_loss, b=avg_win
        # For high WR + asymmetric payoff, should be small positive
        self.assertGreater(kelly, 0)
        self.assertLess(kelly, 1)  # Fractional

    def test_with_loss_cap_basic(self):
        """with_loss_cap caps all loss values at the specified maximum."""
        outcomes = [0.90, 0.90, 0.90, 0.90, -19.0, -25.0]
        dist = BetDistribution.from_outcomes(outcomes)
        self.assertAlmostEqual(dist.avg_loss, -22.0, places=1)

        capped = dist.with_loss_cap(7.50)
        # All losses should be capped at -7.50
        self.assertAlmostEqual(capped.avg_loss, -7.50, places=2)
        for v in capped.loss_values:
            self.assertGreaterEqual(v, -7.50)

    def test_with_loss_cap_preserves_wins(self):
        """Capping losses does not change win values."""
        outcomes = [0.90, 0.80, 1.10, -19.0, -5.0]
        dist = BetDistribution.from_outcomes(outcomes)
        capped = dist.with_loss_cap(7.50)
        self.assertEqual(capped.win_values, dist.win_values)
        self.assertAlmostEqual(capped.win_rate, dist.win_rate)

    def test_with_loss_cap_no_change_if_within(self):
        """If all losses are already within cap, nothing changes."""
        outcomes = [0.90, 0.90, -5.0, -3.0]
        dist = BetDistribution.from_outcomes(outcomes)
        capped = dist.with_loss_cap(7.50)
        self.assertEqual(capped.loss_values, dist.loss_values)
        self.assertAlmostEqual(capped.avg_loss, dist.avg_loss)

    def test_with_loss_cap_recalculates_ev(self):
        """Capped distribution has higher EV than uncapped."""
        outcomes = [0.90] * 19 + [-19.0]  # 95% WR, large loss
        dist = BetDistribution.from_outcomes(outcomes)
        capped = dist.with_loss_cap(7.50)
        self.assertGreater(capped.expected_value(), dist.expected_value())

    def test_with_loss_cap_empty_losses(self):
        """Capping with no losses is a no-op."""
        dist = BetDistribution.from_outcomes([0.90, 0.80])
        capped = dist.with_loss_cap(7.50)
        self.assertEqual(len(capped.loss_values), 0)

    def test_with_loss_cap_preserves_metadata(self):
        """Capping preserves total_bets, daily_volume."""
        dist = BetDistribution.from_outcomes([0.90, -20.0], daily_volume=25)
        capped = dist.with_loss_cap(7.50)
        self.assertEqual(capped.total_bets, dist.total_bets)
        self.assertEqual(capped.daily_volume, 25)


class TestSimulationResult(unittest.TestCase):
    """Test SimulationResult data container."""

    def test_basic_construction(self):
        result = SimulationResult(
            n_simulations=4,
            n_days=30,
            starting_bankroll=100.0,
            target_bankroll=125.0,
            final_bankrolls=[110.0, 120.0, 130.0, 0.0],
            ruin_count=1,
            target_count=1,
        )
        self.assertAlmostEqual(result.ruin_probability, 0.25)
        self.assertAlmostEqual(result.target_probability, 0.25)
        self.assertAlmostEqual(result.median_bankroll, 115.0)

    def test_percentiles(self):
        bankrolls = list(range(1, 101))  # 1 to 100
        result = SimulationResult(
            n_simulations=100,
            n_days=30,
            starting_bankroll=50.0,
            target_bankroll=75.0,
            final_bankrolls=bankrolls,
            ruin_count=0,
            target_count=26,
        )
        p5, p50, p95 = result.percentiles(5), result.percentiles(50), result.percentiles(95)
        self.assertLess(p5, p50)
        self.assertLess(p50, p95)

    def test_expected_daily_pnl(self):
        result = SimulationResult(
            n_simulations=2,
            n_days=30,
            starting_bankroll=100.0,
            target_bankroll=125.0,
            final_bankrolls=[130.0, 110.0],
            ruin_count=0,
            target_count=1,
        )
        # Average final = 120, started at 100, over 30 days = 0.667/day
        self.assertAlmostEqual(result.expected_daily_pnl(), (20.0 / 30.0), places=2)

    def test_to_dict(self):
        result = SimulationResult(
            n_simulations=100,
            n_days=30,
            starting_bankroll=100.0,
            target_bankroll=125.0,
            final_bankrolls=[110.0] * 100,
            ruin_count=5,
            target_count=20,
        )
        d = result.to_dict()
        self.assertIn("ruin_probability", d)
        self.assertIn("target_probability", d)
        self.assertIn("median_bankroll", d)
        self.assertIn("percentile_5", d)
        self.assertIn("percentile_95", d)
        self.assertEqual(d["n_simulations"], 100)


class TestMonteCarloSimulator(unittest.TestCase):
    """Test the Monte Carlo simulation engine."""

    def setUp(self):
        self.dist = BetDistribution(
            win_rate=0.957,
            avg_win=0.90,
            avg_loss=-10.0,
            total_bets=964,
            daily_volume=30,
        )

    def test_single_path(self):
        """Simulate a single bankroll path."""
        sim = MonteCarloSimulator(self.dist)
        random.seed(42)
        path = sim.simulate_path(
            starting_bankroll=100.0,
            n_days=30,
        )
        self.assertEqual(len(path), 31)  # day 0 + 30 days
        self.assertAlmostEqual(path[0], 100.0)

    def test_path_with_ruin(self):
        """Path should stop at 0 when bankroll hits zero."""
        bad_dist = BetDistribution(
            win_rate=0.10,
            avg_win=1.0,
            avg_loss=-10.0,
            daily_volume=30,
        )
        sim = MonteCarloSimulator(bad_dist)
        random.seed(42)
        path = sim.simulate_path(starting_bankroll=50.0, n_days=100)
        # With 10% WR and -10 loss, should hit ruin
        self.assertEqual(path[-1], 0.0)

    def test_run_simulation(self):
        """Run full MC simulation with multiple paths."""
        sim = MonteCarloSimulator(self.dist)
        result = sim.run(
            starting_bankroll=100.0,
            target_bankroll=125.0,
            n_days=30,
            n_simulations=500,
            seed=42,
        )
        self.assertIsInstance(result, SimulationResult)
        self.assertEqual(result.n_simulations, 500)
        self.assertEqual(len(result.final_bankrolls), 500)

    def test_high_wr_reaches_target(self):
        """With 95.7% WR sniper, should reach 125 target from 100 most of the time."""
        sim = MonteCarloSimulator(self.dist)
        result = sim.run(
            starting_bankroll=100.0,
            target_bankroll=125.0,
            n_days=60,
            n_simulations=1000,
            seed=42,
        )
        # With positive EV strategy, majority should reach target in 60 days
        self.assertGreater(result.target_probability, 0.5)

    def test_ruin_probability_low_for_good_strategy(self):
        """Sniper strategy should have low ruin probability."""
        sim = MonteCarloSimulator(self.dist)
        result = sim.run(
            starting_bankroll=100.0,
            target_bankroll=125.0,
            n_days=30,
            n_simulations=1000,
            seed=42,
        )
        self.assertLess(result.ruin_probability, 0.10)

    def test_ruin_probability_high_for_bad_strategy(self):
        """Losing strategy should have high ruin probability."""
        bad_dist = BetDistribution(
            win_rate=0.50,
            avg_win=0.90,
            avg_loss=-10.0,
            daily_volume=30,
        )
        sim = MonteCarloSimulator(bad_dist)
        result = sim.run(
            starting_bankroll=100.0,
            target_bankroll=200.0,
            n_days=30,
            n_simulations=500,
            seed=42,
        )
        self.assertGreater(result.ruin_probability, 0.5)

    def test_bankroll_floor_zero(self):
        """No bankroll should go below zero."""
        sim = MonteCarloSimulator(self.dist)
        result = sim.run(
            starting_bankroll=100.0,
            target_bankroll=200.0,
            n_days=30,
            n_simulations=500,
            seed=42,
        )
        for b in result.final_bankrolls:
            self.assertGreaterEqual(b, 0.0)

    def test_custom_daily_volume(self):
        """Override daily volume for scenario analysis."""
        dist_low = BetDistribution(
            win_rate=0.957,
            avg_win=0.90,
            avg_loss=-10.0,
            daily_volume=10,
        )
        dist_high = BetDistribution(
            win_rate=0.957,
            avg_win=0.90,
            avg_loss=-10.0,
            daily_volume=50,
        )
        sim_low = MonteCarloSimulator(dist_low)
        sim_high = MonteCarloSimulator(dist_high)
        result_low = sim_low.run(100.0, 125.0, 30, 500, seed=42)
        result_high = sim_high.run(100.0, 125.0, 30, 500, seed=42)
        # Higher volume = faster growth (positive EV) = more likely to hit target
        self.assertGreater(result_high.target_probability, result_low.target_probability)

    def test_scenario_analysis(self):
        """Run multiple scenarios and compare."""
        sim = MonteCarloSimulator(self.dist)
        scenarios = sim.scenario_analysis(
            starting_bankroll=100.0,
            target_bankroll=125.0,
            n_days_options=[30, 60, 90],
            n_simulations=200,
            seed=42,
        )
        self.assertEqual(len(scenarios), 3)
        # Longer time horizons = higher target probability
        probs = [s.target_probability for s in scenarios]
        self.assertLessEqual(probs[0], probs[1])
        self.assertLessEqual(probs[1], probs[2])

    def test_ruin_threshold(self):
        """Custom ruin threshold (e.g., bankroll drops below $5)."""
        sim = MonteCarloSimulator(self.dist)
        result = sim.run(
            starting_bankroll=100.0,
            target_bankroll=125.0,
            n_days=30,
            n_simulations=500,
            seed=42,
            ruin_threshold=5.0,
        )
        # Ruin = bankroll < 5, not just 0
        self.assertIsNotNone(result.ruin_count)


class TestSyntheticBetGenerator(unittest.TestCase):
    """Test synthetic bet generation from historical patterns."""

    def test_from_trade_data(self):
        """Generate synthetic bets from trade summary data."""
        trade_data = [
            {"pnl_usd": 0.90, "strategy": "expiry_sniper"},
            {"pnl_usd": 0.85, "strategy": "expiry_sniper"},
            {"pnl_usd": -10.0, "strategy": "expiry_sniper"},
            {"pnl_usd": 0.60, "strategy": "daily_sniper"},
            {"pnl_usd": -8.0, "strategy": "daily_sniper"},
        ]
        gen = SyntheticBetGenerator.from_trade_data(trade_data)
        self.assertEqual(len(gen.strategies), 2)
        self.assertIn("expiry_sniper", gen.strategies)

    def test_generate_day(self):
        """Generate one day of synthetic bets."""
        trade_data = [
            {"pnl_usd": 0.90, "strategy": "expiry_sniper"},
            {"pnl_usd": 0.85, "strategy": "expiry_sniper"},
            {"pnl_usd": -10.0, "strategy": "expiry_sniper"},
        ]
        gen = SyntheticBetGenerator.from_trade_data(trade_data, daily_volume=10)
        random.seed(42)
        day_bets = gen.generate_day()
        self.assertEqual(len(day_bets), 10)
        for bet in day_bets:
            self.assertIn("pnl", bet)
            self.assertIn("strategy", bet)

    def test_generate_sequence(self):
        """Generate N days of synthetic bets."""
        trade_data = [{"pnl_usd": p, "strategy": "s1"} for p in [0.9] * 19 + [-10.0]]
        gen = SyntheticBetGenerator.from_trade_data(trade_data, daily_volume=5)
        random.seed(42)
        sequence = gen.generate_sequence(n_days=7)
        self.assertEqual(len(sequence), 7)
        for day in sequence:
            self.assertEqual(len(day), 5)

    def test_multi_strategy(self):
        """Multi-strategy generator respects volume proportions."""
        trade_data = (
            [{"pnl_usd": 0.90, "strategy": "sniper"}] * 30
            + [{"pnl_usd": 0.60, "strategy": "daily"}] * 10
        )
        gen = SyntheticBetGenerator.from_trade_data(trade_data, daily_volume=40)
        random.seed(42)
        day = gen.generate_day()
        sniper_count = sum(1 for b in day if b["strategy"] == "sniper")
        # Should roughly maintain 75/25 ratio
        self.assertGreater(sniper_count, 15)
        self.assertLess(sniper_count, 40)

    def test_bootstrap_from_outcomes(self):
        """Bootstrap resampling from actual outcome distribution."""
        outcomes = [0.90, 0.85, 0.80, 0.95, -10.0, -9.50]
        gen = SyntheticBetGenerator.from_outcomes(outcomes, daily_volume=20)
        random.seed(42)
        day = gen.generate_day()
        self.assertEqual(len(day), 20)
        valid = set(outcomes)
        for bet in day:
            self.assertIn(bet["pnl"], valid)


class TestSimulatorCLI(unittest.TestCase):
    """Test CLI output and JSON export."""

    def setUp(self):
        self.dist = BetDistribution(
            win_rate=0.957,
            avg_win=0.90,
            avg_loss=-10.0,
            daily_volume=30,
        )

    def test_result_to_json(self):
        """SimulationResult should serialize to JSON."""
        sim = MonteCarloSimulator(self.dist)
        result = sim.run(100.0, 125.0, 30, 100, seed=42)
        json_str = json.dumps(result.to_dict())
        parsed = json.loads(json_str)
        self.assertIn("ruin_probability", parsed)

    def test_result_summary_string(self):
        """Human-readable summary."""
        sim = MonteCarloSimulator(self.dist)
        result = sim.run(100.0, 125.0, 30, 100, seed=42)
        summary = result.summary()
        self.assertIn("Ruin", summary)
        self.assertIn("Target", summary)
        self.assertIn("Median", summary)

    def test_sensitivity_analysis(self):
        """Run sensitivity across win rate range."""
        sim = MonteCarloSimulator(self.dist)
        results = sim.sensitivity_analysis(
            starting_bankroll=100.0,
            target_bankroll=125.0,
            n_days=30,
            n_simulations=100,
            win_rate_range=(0.90, 0.98),
            steps=5,
            seed=42,
        )
        self.assertEqual(len(results), 5)
        # Higher WR = higher target probability
        probs = [r["target_probability"] for r in results]
        # General trend should be increasing (allow some MC noise)
        self.assertGreater(probs[-1], probs[0])


class TestFromDB(unittest.TestCase):
    """Test BetDistribution.from_db with synthetic SQLite DB."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_polybot.db")
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE trades (
                id INTEGER PRIMARY KEY,
                strategy TEXT,
                is_paper INTEGER,
                result TEXT,
                pnl_cents INTEGER,
                timestamp INTEGER,
                side TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE bankroll_history (
                id INTEGER PRIMARY KEY,
                timestamp INTEGER,
                balance_usd REAL,
                source TEXT
            )
        """)
        # Insert 20 sniper trades: 19 wins (90c each), 1 loss (-1000c)
        import time
        base_ts = int(time.time()) - 86400 * 5
        for i in range(19):
            conn.execute(
                "INSERT INTO trades (strategy, is_paper, result, pnl_cents, timestamp, side) VALUES (?,?,?,?,?,?)",
                ("expiry_sniper_v1", 0, "win", 90, base_ts + i * 3600, "yes"),
            )
        conn.execute(
            "INSERT INTO trades (strategy, is_paper, result, pnl_cents, timestamp, side) VALUES (?,?,?,?,?,?)",
            ("expiry_sniper_v1", 0, "loss", -1000, base_ts + 20 * 3600, "yes"),
        )
        # Insert bankroll
        conn.execute(
            "INSERT INTO bankroll_history (timestamp, balance_usd, source) VALUES (?,?,?)",
            (base_ts + 21 * 3600, 125.50, "api"),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        os.remove(self.db_path)
        os.rmdir(self.tmpdir)

    def test_from_db_basic(self):
        dist = BetDistribution.from_db(db_path=self.db_path)
        self.assertEqual(dist.total_bets, 20)
        self.assertAlmostEqual(dist.win_rate, 0.95, places=2)
        self.assertAlmostEqual(dist.avg_win, 0.90, places=2)
        self.assertAlmostEqual(dist.avg_loss, -10.0, places=2)

    def test_from_db_captures_bankroll(self):
        dist = BetDistribution.from_db(db_path=self.db_path)
        self.assertAlmostEqual(dist._current_bankroll, 125.50)

    def test_from_db_strategy_filter(self):
        dist = BetDistribution.from_db(db_path=self.db_path, strategy="expiry_sniper_v1")
        self.assertEqual(dist.total_bets, 20)

    def test_from_db_nonexistent_strategy(self):
        dist = BetDistribution.from_db(db_path=self.db_path, strategy="nonexistent")
        self.assertEqual(dist.total_bets, 0)

    def test_from_db_daily_volume_estimated(self):
        dist = BetDistribution.from_db(db_path=self.db_path)
        self.assertGreater(dist.daily_volume, 0)

    def test_from_db_daily_volume_override(self):
        dist = BetDistribution.from_db(db_path=self.db_path, daily_volume=50)
        self.assertEqual(dist.daily_volume, 50)

    def test_from_db_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            BetDistribution.from_db(db_path="/nonexistent/path.db")

    def test_from_db_has_empirical_values(self):
        dist = BetDistribution.from_db(db_path=self.db_path)
        self.assertEqual(len(dist.win_values), 19)
        self.assertEqual(len(dist.loss_values), 1)

    def test_from_db_simulation_works(self):
        """End-to-end: DB -> distribution -> simulation."""
        dist = BetDistribution.from_db(db_path=self.db_path)
        sim = MonteCarloSimulator(dist)
        result = sim.run(125.0, 250.0, 30, 100, seed=42)
        self.assertEqual(result.n_simulations, 100)
        self.assertGreater(result.target_probability, 0)


class TestEdgeCases(unittest.TestCase):
    """Edge cases and boundary conditions."""

    def test_zero_bankroll(self):
        """Starting at zero = instant ruin."""
        dist = BetDistribution(win_rate=0.95, avg_win=1.0, avg_loss=-5.0, daily_volume=10)
        sim = MonteCarloSimulator(dist)
        result = sim.run(0.0, 100.0, 30, 100, seed=42)
        self.assertAlmostEqual(result.ruin_probability, 1.0)

    def test_already_at_target(self):
        """Starting at target = 100% target probability."""
        dist = BetDistribution(win_rate=0.95, avg_win=1.0, avg_loss=-5.0, daily_volume=10)
        sim = MonteCarloSimulator(dist)
        result = sim.run(125.0, 125.0, 30, 100, seed=42)
        self.assertAlmostEqual(result.target_probability, 1.0)

    def test_one_day_simulation(self):
        dist = BetDistribution(win_rate=0.95, avg_win=1.0, avg_loss=-5.0, daily_volume=10)
        sim = MonteCarloSimulator(dist)
        result = sim.run(100.0, 200.0, 1, 100, seed=42)
        self.assertEqual(result.n_days, 1)

    def test_single_simulation(self):
        dist = BetDistribution(win_rate=0.95, avg_win=1.0, avg_loss=-5.0, daily_volume=10)
        sim = MonteCarloSimulator(dist)
        result = sim.run(100.0, 200.0, 30, 1, seed=42)
        self.assertEqual(result.n_simulations, 1)
        self.assertEqual(len(result.final_bankrolls), 1)

    def test_deterministic_with_seed(self):
        """Same seed = same results."""
        dist = BetDistribution(win_rate=0.957, avg_win=0.90, avg_loss=-10.0, daily_volume=30)
        sim = MonteCarloSimulator(dist)
        r1 = sim.run(100.0, 125.0, 30, 100, seed=42)
        r2 = sim.run(100.0, 125.0, 30, 100, seed=42)
        self.assertEqual(r1.final_bankrolls, r2.final_bankrolls)

    def test_daily_volume_zero(self):
        """Zero daily volume = bankroll unchanged."""
        dist = BetDistribution(win_rate=0.95, avg_win=1.0, avg_loss=-5.0, daily_volume=0)
        sim = MonteCarloSimulator(dist)
        result = sim.run(100.0, 200.0, 30, 50, seed=42)
        for b in result.final_bankrolls:
            self.assertAlmostEqual(b, 100.0)


if __name__ == "__main__":
    unittest.main()
