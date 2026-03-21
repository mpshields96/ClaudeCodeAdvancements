#!/usr/bin/env python3
"""
Tests for calibration_bias.py — MT-26 Phase 1: Calibration Bias Exploiter

Tests calibration curve computation, bias detection, mispricing zone identification,
and bias-adjusted probability estimation.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calibration_bias import (
    CalibrationBias,
    CalibrationResult,
    MispricingZone,
    BiasDirection,
)


class TestBiasDirection(unittest.TestCase):
    """BiasDirection enum values."""

    def test_enum_values(self):
        self.assertEqual(BiasDirection.OVERCONFIDENT.value, "overconfident")
        self.assertEqual(BiasDirection.UNDERCONFIDENT.value, "underconfident")
        self.assertEqual(BiasDirection.MIXED.value, "mixed")
        self.assertEqual(BiasDirection.NONE.value, "none")


class TestCalibrationResult(unittest.TestCase):
    """CalibrationResult dataclass."""

    def test_creation(self):
        result = CalibrationResult(
            domain="crypto",
            bias_direction=BiasDirection.OVERCONFIDENT,
            mean_bias=0.05,
            max_bias=0.12,
            n_contracts=500,
            calibration_curve=[],
            mispricing_zones=[],
        )
        self.assertEqual(result.domain, "crypto")
        self.assertEqual(result.bias_direction, BiasDirection.OVERCONFIDENT)
        self.assertEqual(result.n_contracts, 500)

    def test_to_dict(self):
        result = CalibrationResult(
            domain="crypto",
            bias_direction=BiasDirection.OVERCONFIDENT,
            mean_bias=0.05,
            max_bias=0.12,
            n_contracts=500,
            calibration_curve=[{"bin_center": 0.5, "actual_freq": 0.45, "count": 100}],
            mispricing_zones=[],
        )
        d = result.to_dict()
        self.assertEqual(d["domain"], "crypto")
        self.assertEqual(d["bias_direction"], "overconfident")
        self.assertIsInstance(d["calibration_curve"], list)


class TestMispricingZone(unittest.TestCase):
    """MispricingZone dataclass."""

    def test_creation(self):
        zone = MispricingZone(
            price_range=(0.05, 0.15),
            bias=0.08,
            direction=BiasDirection.OVERCONFIDENT,
            confidence=0.92,
            n_samples=200,
            exploitable=True,
        )
        self.assertEqual(zone.price_range, (0.05, 0.15))
        self.assertTrue(zone.exploitable)

    def test_to_dict(self):
        zone = MispricingZone(
            price_range=(0.05, 0.15),
            bias=0.08,
            direction=BiasDirection.OVERCONFIDENT,
            confidence=0.92,
            n_samples=200,
            exploitable=True,
        )
        d = zone.to_dict()
        self.assertEqual(d["price_range"], [0.05, 0.15])
        self.assertEqual(d["direction"], "overconfident")


class TestCalibrationBiasInit(unittest.TestCase):
    """Initialization and configuration."""

    def test_default_init(self):
        cb = CalibrationBias()
        self.assertEqual(cb.n_bins, 10)
        self.assertEqual(cb.min_samples_per_bin, 20)

    def test_custom_bins(self):
        cb = CalibrationBias(n_bins=20, min_samples_per_bin=50)
        self.assertEqual(cb.n_bins, 20)
        self.assertEqual(cb.min_samples_per_bin, 50)

    def test_invalid_bins(self):
        with self.assertRaises(ValueError):
            CalibrationBias(n_bins=0)
        with self.assertRaises(ValueError):
            CalibrationBias(n_bins=-5)

    def test_invalid_min_samples(self):
        with self.assertRaises(ValueError):
            CalibrationBias(min_samples_per_bin=0)


class TestAddContract(unittest.TestCase):
    """Adding historical contract data."""

    def setUp(self):
        self.cb = CalibrationBias()

    def test_add_single(self):
        self.cb.add_contract(market_price=0.65, outcome=1, domain="crypto")
        self.assertEqual(len(self.cb.contracts), 1)

    def test_add_multiple(self):
        for i in range(100):
            self.cb.add_contract(
                market_price=i / 100, outcome=1 if i > 50 else 0, domain="crypto"
            )
        self.assertEqual(len(self.cb.contracts), 100)

    def test_add_batch(self):
        contracts = [
            {"market_price": 0.65, "outcome": 1, "domain": "crypto"},
            {"market_price": 0.30, "outcome": 0, "domain": "crypto"},
            {"market_price": 0.80, "outcome": 1, "domain": "political"},
        ]
        self.cb.add_batch(contracts)
        self.assertEqual(len(self.cb.contracts), 3)

    def test_invalid_price_too_high(self):
        with self.assertRaises(ValueError):
            self.cb.add_contract(market_price=1.5, outcome=1, domain="crypto")

    def test_invalid_price_negative(self):
        with self.assertRaises(ValueError):
            self.cb.add_contract(market_price=-0.1, outcome=1, domain="crypto")

    def test_invalid_outcome(self):
        with self.assertRaises(ValueError):
            self.cb.add_contract(market_price=0.5, outcome=2, domain="crypto")

    def test_edge_prices(self):
        # 0.0 and 1.0 should be accepted
        self.cb.add_contract(market_price=0.0, outcome=0, domain="crypto")
        self.cb.add_contract(market_price=1.0, outcome=1, domain="crypto")
        self.assertEqual(len(self.cb.contracts), 2)

    def test_domain_preserved(self):
        self.cb.add_contract(market_price=0.5, outcome=1, domain="weather")
        self.assertEqual(self.cb.contracts[0]["domain"], "weather")


class TestCalibrationCurve(unittest.TestCase):
    """Computing calibration curves."""

    def setUp(self):
        self.cb = CalibrationBias(n_bins=5, min_samples_per_bin=5)

    def _add_perfectly_calibrated(self, n=500):
        """Add contracts where outcome frequency matches market price."""
        import random
        random.seed(42)
        for _ in range(n):
            p = random.random()
            outcome = 1 if random.random() < p else 0
            self.cb.add_contract(market_price=p, outcome=outcome, domain="crypto")

    def _add_overconfident(self, n=500):
        """Add contracts where market price overestimates outcome probability."""
        import random
        random.seed(42)
        for _ in range(n):
            p = random.uniform(0.5, 0.95)
            # Actual outcome rate is lower than market price (overconfident)
            actual_p = p - 0.15
            outcome = 1 if random.random() < actual_p else 0
            self.cb.add_contract(market_price=p, outcome=outcome, domain="crypto")

    def test_curve_length_matches_bins(self):
        self._add_perfectly_calibrated()
        curve = self.cb.compute_calibration_curve(domain="crypto")
        # May have fewer bins if some bins have too few samples
        self.assertLessEqual(len(curve), 5)
        self.assertGreater(len(curve), 0)

    def test_curve_entry_fields(self):
        self._add_perfectly_calibrated()
        curve = self.cb.compute_calibration_curve(domain="crypto")
        entry = curve[0]
        self.assertIn("bin_center", entry)
        self.assertIn("mean_predicted", entry)
        self.assertIn("actual_freq", entry)
        self.assertIn("count", entry)
        self.assertIn("bias", entry)

    def test_perfectly_calibrated_low_bias(self):
        self._add_perfectly_calibrated(n=2000)
        curve = self.cb.compute_calibration_curve(domain="crypto")
        # Mean absolute bias should be small for well-calibrated data
        biases = [abs(e["bias"]) for e in curve]
        mean_bias = sum(biases) / len(biases)
        self.assertLess(mean_bias, 0.08)

    def test_overconfident_positive_bias(self):
        self._add_overconfident(n=2000)
        curve = self.cb.compute_calibration_curve(domain="crypto")
        # Bias should be positive (predicted > actual) for overconfident
        positive_bias_count = sum(1 for e in curve if e["bias"] > 0)
        self.assertGreater(positive_bias_count, len(curve) // 2)

    def test_empty_domain_returns_empty(self):
        self._add_perfectly_calibrated()
        curve = self.cb.compute_calibration_curve(domain="sports")
        self.assertEqual(len(curve), 0)

    def test_all_domains_combined(self):
        self._add_perfectly_calibrated()
        # domain=None should use all contracts
        curve = self.cb.compute_calibration_curve(domain=None)
        self.assertGreater(len(curve), 0)


class TestAnalyze(unittest.TestCase):
    """Full analysis: bias direction, mispricing zones."""

    def setUp(self):
        self.cb = CalibrationBias(n_bins=5, min_samples_per_bin=10)

    def _add_overconfident_data(self, domain="crypto", n=1000):
        import random
        random.seed(42)
        for _ in range(n):
            p = random.uniform(0.3, 0.95)
            actual_p = max(0, p - 0.12)
            outcome = 1 if random.random() < actual_p else 0
            self.cb.add_contract(market_price=p, outcome=outcome, domain=domain)

    def _add_underconfident_data(self, domain="political", n=1000):
        import random
        random.seed(123)
        for _ in range(n):
            p = random.uniform(0.05, 0.70)
            actual_p = min(1, p + 0.10)
            outcome = 1 if random.random() < actual_p else 0
            self.cb.add_contract(market_price=p, outcome=outcome, domain=domain)

    def test_overconfident_detection(self):
        self._add_overconfident_data()
        result = self.cb.analyze(domain="crypto")
        self.assertIsInstance(result, CalibrationResult)
        self.assertEqual(result.bias_direction, BiasDirection.OVERCONFIDENT)
        self.assertGreater(result.mean_bias, 0)

    def test_underconfident_detection(self):
        self._add_underconfident_data()
        result = self.cb.analyze(domain="political")
        self.assertEqual(result.bias_direction, BiasDirection.UNDERCONFIDENT)
        self.assertLess(result.mean_bias, 0)

    def test_n_contracts_reported(self):
        self._add_overconfident_data(n=500)
        result = self.cb.analyze(domain="crypto")
        self.assertEqual(result.n_contracts, 500)

    def test_insufficient_data(self):
        # Only 5 contracts — below min_samples_per_bin threshold
        for i in range(5):
            self.cb.add_contract(market_price=0.5, outcome=i % 2, domain="crypto")
        result = self.cb.analyze(domain="crypto")
        self.assertEqual(result.bias_direction, BiasDirection.NONE)

    def test_multi_domain_analysis(self):
        self._add_overconfident_data(domain="crypto")
        self._add_underconfident_data(domain="political")
        crypto = self.cb.analyze(domain="crypto")
        political = self.cb.analyze(domain="political")
        # Different domains should show different bias directions
        self.assertNotEqual(crypto.bias_direction, political.bias_direction)

    def test_result_has_calibration_curve(self):
        self._add_overconfident_data()
        result = self.cb.analyze(domain="crypto")
        self.assertIsInstance(result.calibration_curve, list)
        self.assertGreater(len(result.calibration_curve), 0)


class TestMispricingZones(unittest.TestCase):
    """Finding exploitable mispricing zones."""

    def setUp(self):
        self.cb = CalibrationBias(n_bins=10, min_samples_per_bin=10)

    def _add_biased_extremes(self, n=2000):
        """Add data with strong bias at price extremes (FLB pattern)."""
        import random
        random.seed(42)
        for _ in range(n):
            p = random.random()
            if p < 0.15:
                # Low-priced contracts: market overestimates (lose 60%+ per Makers & Takers)
                actual_p = p * 0.4
            elif p > 0.85:
                # High-priced contracts: slight underconfidence
                actual_p = min(1.0, p + 0.03)
            else:
                # Middle: roughly calibrated
                actual_p = p + random.uniform(-0.02, 0.02)
            actual_p = max(0, min(1, actual_p))
            outcome = 1 if random.random() < actual_p else 0
            self.cb.add_contract(market_price=p, outcome=outcome, domain="crypto")

    def test_finds_mispricing_zones(self):
        self._add_biased_extremes()
        result = self.cb.analyze(domain="crypto")
        # Should find at least 1 exploitable zone at low prices
        self.assertGreater(len(result.mispricing_zones), 0)

    def test_zone_has_correct_fields(self):
        self._add_biased_extremes()
        result = self.cb.analyze(domain="crypto")
        if result.mispricing_zones:
            zone = result.mispricing_zones[0]
            self.assertIsInstance(zone, MispricingZone)
            self.assertIsInstance(zone.price_range, tuple)
            self.assertEqual(len(zone.price_range), 2)
            self.assertIsInstance(zone.exploitable, bool)

    def test_exploitable_requires_min_bias(self):
        self._add_biased_extremes()
        result = self.cb.analyze(domain="crypto")
        for zone in result.mispricing_zones:
            if zone.exploitable:
                self.assertGreater(abs(zone.bias), 0.03)

    def test_zone_confidence(self):
        self._add_biased_extremes()
        result = self.cb.analyze(domain="crypto")
        for zone in result.mispricing_zones:
            self.assertGreaterEqual(zone.confidence, 0)
            self.assertLessEqual(zone.confidence, 1)


class TestAdjustProbability(unittest.TestCase):
    """Bias-adjusted probability estimation."""

    def setUp(self):
        self.cb = CalibrationBias(n_bins=5, min_samples_per_bin=10)
        import random
        random.seed(42)
        # Add overconfident data so there's a known bias
        for _ in range(1000):
            p = random.uniform(0.2, 0.9)
            actual_p = max(0, p - 0.10)
            outcome = 1 if random.random() < actual_p else 0
            self.cb.add_contract(market_price=p, outcome=outcome, domain="crypto")
        self.cb.analyze(domain="crypto")

    def test_adjust_returns_float(self):
        adjusted = self.cb.adjust_probability(0.60, domain="crypto")
        self.assertIsInstance(adjusted, float)

    def test_adjusted_in_valid_range(self):
        for price in [0.1, 0.3, 0.5, 0.7, 0.9]:
            adjusted = self.cb.adjust_probability(price, domain="crypto")
            self.assertGreaterEqual(adjusted, 0.0)
            self.assertLessEqual(adjusted, 1.0)

    def test_overconfident_adjusts_down(self):
        # For overconfident market, adjusted should be <= market price
        adjusted = self.cb.adjust_probability(0.70, domain="crypto")
        self.assertLessEqual(adjusted, 0.70)

    def test_unknown_domain_returns_original(self):
        adjusted = self.cb.adjust_probability(0.60, domain="sports")
        self.assertEqual(adjusted, 0.60)

    def test_no_analysis_returns_original(self):
        cb2 = CalibrationBias()
        adjusted = cb2.adjust_probability(0.60, domain="crypto")
        self.assertEqual(adjusted, 0.60)


class TestSaveLoad(unittest.TestCase):
    """Persistence of calibration data."""

    def setUp(self):
        self.cb = CalibrationBias(n_bins=5, min_samples_per_bin=10)
        import random
        random.seed(42)
        for _ in range(500):
            p = random.uniform(0.1, 0.9)
            outcome = 1 if random.random() < p else 0
            self.cb.add_contract(market_price=p, outcome=outcome, domain="crypto")
        self.cb.analyze(domain="crypto")

    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.cb.save(path)
            self.assertTrue(os.path.exists(path))

            cb2 = CalibrationBias.load(path)
            self.assertEqual(len(cb2.contracts), 500)
        finally:
            os.unlink(path)

    def test_save_creates_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.cb.save(path)
            with open(path) as f:
                data = json.load(f)
            self.assertIn("contracts", data)
            self.assertIn("n_bins", data)
        finally:
            os.unlink(path)

    def test_load_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            CalibrationBias.load("/tmp/nonexistent_calib.json")


class TestCLI(unittest.TestCase):
    """CLI interface for standalone usage."""

    def test_analyze_output_json(self):
        import subprocess
        # Create a temp file with contract data
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            contracts = [
                {"market_price": 0.6, "outcome": 1, "domain": "crypto"},
                {"market_price": 0.7, "outcome": 0, "domain": "crypto"},
            ] * 50  # 100 contracts
            json.dump(contracts, f)
            path = f.name
        try:
            result = subprocess.run(
                [sys.executable, "-m", "calibration_bias", "analyze", path, "--domain", "crypto"],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            self.assertEqual(result.returncode, 0)
            output = json.loads(result.stdout)
            self.assertIn("domain", output)
            self.assertIn("bias_direction", output)
        finally:
            os.unlink(path)

    def test_adjust_output(self):
        import subprocess
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            contracts = [
                {"market_price": 0.6, "outcome": 1, "domain": "crypto"},
                {"market_price": 0.7, "outcome": 0, "domain": "crypto"},
            ] * 50
            json.dump(contracts, f)
            path = f.name
        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "calibration_bias",
                    "adjust", path,
                    "--domain", "crypto",
                    "--price", "0.65",
                ],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            self.assertEqual(result.returncode, 0)
            output = json.loads(result.stdout)
            self.assertIn("market_price", output)
            self.assertIn("adjusted_price", output)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
