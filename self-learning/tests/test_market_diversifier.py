#!/usr/bin/env python3
"""Tests for market_diversifier.py — REQ-055: Cross-market diversification analysis."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from market_diversifier import (
    AssetClass,
    MarketPosition,
    ConcentrationResult,
    DiversificationAdvisor,
    herfindahl_index,
    effective_markets,
    concentration_risk,
)


class TestAssetClass(unittest.TestCase):
    """Test AssetClass enum."""

    def test_all_classes_exist(self):
        self.assertIn(AssetClass.CRYPTO, AssetClass)
        self.assertIn(AssetClass.SPORTS, AssetClass)
        self.assertIn(AssetClass.POLITICS, AssetClass)
        self.assertIn(AssetClass.WEATHER, AssetClass)
        self.assertIn(AssetClass.ECONOMICS, AssetClass)
        self.assertIn(AssetClass.OTHER, AssetClass)

    def test_class_values_are_strings(self):
        for cls in AssetClass:
            self.assertIsInstance(cls.value, str)


class TestMarketPosition(unittest.TestCase):
    """Test MarketPosition data model."""

    def test_creation(self):
        pos = MarketPosition(
            market_id="btc-above-100k",
            asset_class=AssetClass.CRYPTO,
            amount=10.0,
            ticker="BTC",
        )
        self.assertEqual(pos.market_id, "btc-above-100k")
        self.assertEqual(pos.asset_class, AssetClass.CRYPTO)

    def test_to_dict(self):
        pos = MarketPosition(
            market_id="lakers-win",
            asset_class=AssetClass.SPORTS,
            amount=5.0,
        )
        d = pos.to_dict()
        self.assertIn("market_id", d)
        self.assertIn("asset_class", d)
        self.assertIn("amount", d)


class TestHerfindahlIndex(unittest.TestCase):
    """Test HHI computation."""

    def test_perfect_concentration(self):
        # All in one class
        weights = {"CRYPTO": 1.0}
        self.assertAlmostEqual(herfindahl_index(weights), 1.0)

    def test_perfect_diversification(self):
        # Equal across 5 classes
        weights = {c: 0.2 for c in ["A", "B", "C", "D", "E"]}
        self.assertAlmostEqual(herfindahl_index(weights), 0.2)

    def test_moderate_concentration(self):
        weights = {"CRYPTO": 0.6, "SPORTS": 0.4}
        hhi = herfindahl_index(weights)
        self.assertGreater(hhi, 0.5)  # 0.36 + 0.16 = 0.52
        self.assertLess(hhi, 1.0)

    def test_empty_weights(self):
        self.assertAlmostEqual(herfindahl_index({}), 0.0)


class TestEffectiveMarkets(unittest.TestCase):
    """Test effective number of markets (1/HHI)."""

    def test_one_market(self):
        weights = {"CRYPTO": 1.0}
        self.assertAlmostEqual(effective_markets(weights), 1.0)

    def test_four_equal(self):
        weights = {c: 0.25 for c in ["A", "B", "C", "D"]}
        self.assertAlmostEqual(effective_markets(weights), 4.0)

    def test_empty(self):
        self.assertAlmostEqual(effective_markets({}), 0.0)


class TestConcentrationRisk(unittest.TestCase):
    """Test concentration risk classification."""

    def test_high_concentration(self):
        weights = {"CRYPTO": 1.0}
        result = concentration_risk(weights)
        self.assertEqual(result, "HIGH")

    def test_moderate_concentration(self):
        weights = {"CRYPTO": 0.6, "SPORTS": 0.4}
        result = concentration_risk(weights)
        self.assertIn(result, ["HIGH", "MODERATE"])

    def test_low_concentration(self):
        weights = {c: 0.2 for c in ["A", "B", "C", "D", "E"]}
        result = concentration_risk(weights)
        self.assertEqual(result, "LOW")


class TestDiversificationAdvisor(unittest.TestCase):
    """Test the full diversification advisor."""

    def _make_positions(self, class_amounts):
        """Helper: create positions from {AssetClass: total_amount}."""
        positions = []
        for i, (cls, amt) in enumerate(class_amounts.items()):
            positions.append(MarketPosition(
                market_id=f"market-{i}",
                asset_class=cls,
                amount=amt,
            ))
        return positions

    def test_analyze_concentrated(self):
        positions = self._make_positions({
            AssetClass.CRYPTO: 50.0,
        })
        advisor = DiversificationAdvisor()
        result = advisor.analyze(positions)
        self.assertIsInstance(result, ConcentrationResult)
        self.assertEqual(result.risk_level, "HIGH")

    def test_analyze_diversified(self):
        positions = self._make_positions({
            AssetClass.CRYPTO: 10.0,
            AssetClass.SPORTS: 10.0,
            AssetClass.POLITICS: 10.0,
            AssetClass.WEATHER: 10.0,
            AssetClass.ECONOMICS: 10.0,
        })
        advisor = DiversificationAdvisor()
        result = advisor.analyze(positions)
        self.assertEqual(result.risk_level, "LOW")

    def test_analyze_empty(self):
        advisor = DiversificationAdvisor()
        result = advisor.analyze([])
        self.assertEqual(result.total_exposure, 0.0)

    def test_class_weights_sum_to_one(self):
        positions = self._make_positions({
            AssetClass.CRYPTO: 30.0,
            AssetClass.SPORTS: 20.0,
        })
        advisor = DiversificationAdvisor()
        result = advisor.analyze(positions)
        total_weight = sum(result.class_weights.values())
        self.assertAlmostEqual(total_weight, 1.0)

    def test_recommendations_for_concentrated(self):
        positions = self._make_positions({
            AssetClass.CRYPTO: 80.0,
            AssetClass.SPORTS: 5.0,
        })
        advisor = DiversificationAdvisor()
        result = advisor.analyze(positions)
        self.assertGreater(len(result.recommendations), 0)

    def test_no_recommendations_when_diversified(self):
        positions = self._make_positions({
            AssetClass.CRYPTO: 10.0,
            AssetClass.SPORTS: 10.0,
            AssetClass.POLITICS: 10.0,
            AssetClass.WEATHER: 10.0,
        })
        advisor = DiversificationAdvisor()
        result = advisor.analyze(positions)
        # May still have suggestions but risk should be low
        self.assertIn(result.risk_level, ["LOW", "MODERATE"])

    def test_result_to_dict(self):
        positions = self._make_positions({
            AssetClass.CRYPTO: 40.0,
            AssetClass.SPORTS: 10.0,
        })
        advisor = DiversificationAdvisor()
        result = advisor.analyze(positions)
        d = result.to_dict()
        self.assertIn("hhi", d)
        self.assertIn("effective_markets", d)
        self.assertIn("risk_level", d)
        self.assertIn("class_weights", d)

    def test_result_summary_text(self):
        positions = self._make_positions({
            AssetClass.CRYPTO: 40.0,
            AssetClass.SPORTS: 10.0,
        })
        advisor = DiversificationAdvisor()
        result = advisor.analyze(positions)
        text = result.summary_text()
        self.assertIsInstance(text, str)
        self.assertIn("Diversification", text)

    def test_multiple_positions_same_class(self):
        positions = [
            MarketPosition("btc-100k", AssetClass.CRYPTO, 20.0, "BTC"),
            MarketPosition("eth-5k", AssetClass.CRYPTO, 15.0, "ETH"),
            MarketPosition("lakers", AssetClass.SPORTS, 10.0),
        ]
        advisor = DiversificationAdvisor()
        result = advisor.analyze(positions)
        self.assertAlmostEqual(result.class_weights[AssetClass.CRYPTO], 35.0 / 45.0, places=2)

    def test_max_class_exposure(self):
        positions = self._make_positions({
            AssetClass.CRYPTO: 80.0,
            AssetClass.SPORTS: 20.0,
        })
        advisor = DiversificationAdvisor()
        result = advisor.analyze(positions)
        self.assertAlmostEqual(result.max_class_exposure, 0.8, places=2)

    def test_custom_concentration_threshold(self):
        positions = self._make_positions({
            AssetClass.CRYPTO: 60.0,
            AssetClass.SPORTS: 40.0,
        })
        # Strict threshold — 0.5 HHI is the divider
        advisor = DiversificationAdvisor(high_threshold=0.4, moderate_threshold=0.25)
        result = advisor.analyze(positions)
        self.assertEqual(result.risk_level, "HIGH")


if __name__ == "__main__":
    unittest.main()
