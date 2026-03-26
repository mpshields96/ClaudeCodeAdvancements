#!/usr/bin/env python3
"""Tests for market_data.py — MT-37 Phase 4: Market data retrieval.

TDD: Tests written before implementation.

Covers:
- PriceRecord and MarketDataResult dataclasses
- Return calculation (simple and log)
- Volatility calculation (annualized)
- Factor exposure estimation (market beta, size, value, momentum)
- Macro data (risk-free rate, CAPE ratio)
- Data normalization and cleaning
- CLI interface
- Error handling for missing/bad data
"""

import json
import math
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPriceRecord(unittest.TestCase):
    """Test PriceRecord dataclass."""

    def test_basic_construction(self):
        from market_data import PriceRecord
        pr = PriceRecord(date=date(2026, 1, 15), close=150.0)
        self.assertEqual(pr.date, date(2026, 1, 15))
        self.assertAlmostEqual(pr.close, 150.0)

    def test_optional_fields_default_none(self):
        from market_data import PriceRecord
        pr = PriceRecord(date=date(2026, 1, 15), close=150.0)
        self.assertIsNone(pr.open)
        self.assertIsNone(pr.high)
        self.assertIsNone(pr.low)
        self.assertIsNone(pr.volume)

    def test_all_fields(self):
        from market_data import PriceRecord
        pr = PriceRecord(
            date=date(2026, 1, 15), close=150.0,
            open=148.0, high=152.0, low=147.0, volume=1_000_000,
        )
        self.assertAlmostEqual(pr.open, 148.0)
        self.assertAlmostEqual(pr.high, 152.0)
        self.assertAlmostEqual(pr.low, 147.0)
        self.assertEqual(pr.volume, 1_000_000)


class TestReturnCalculation(unittest.TestCase):
    """Test return series computation."""

    def test_simple_returns(self):
        from market_data import compute_returns, PriceRecord
        prices = [
            PriceRecord(date=date(2026, 1, 1), close=100.0),
            PriceRecord(date=date(2026, 1, 2), close=105.0),
            PriceRecord(date=date(2026, 1, 3), close=102.0),
        ]
        returns = compute_returns(prices, method="simple")
        self.assertEqual(len(returns), 2)
        self.assertAlmostEqual(returns[0], 0.05, places=6)
        self.assertAlmostEqual(returns[1], -0.0285714, places=4)

    def test_log_returns(self):
        from market_data import compute_returns, PriceRecord
        prices = [
            PriceRecord(date=date(2026, 1, 1), close=100.0),
            PriceRecord(date=date(2026, 1, 2), close=110.0),
        ]
        returns = compute_returns(prices, method="log")
        self.assertEqual(len(returns), 1)
        self.assertAlmostEqual(returns[0], math.log(110 / 100), places=8)

    def test_empty_prices_returns_empty(self):
        from market_data import compute_returns
        self.assertEqual(compute_returns([], method="simple"), [])

    def test_single_price_returns_empty(self):
        from market_data import compute_returns, PriceRecord
        prices = [PriceRecord(date=date(2026, 1, 1), close=100.0)]
        self.assertEqual(compute_returns(prices, method="simple"), [])

    def test_invalid_method_raises(self):
        from market_data import compute_returns, PriceRecord
        prices = [
            PriceRecord(date=date(2026, 1, 1), close=100.0),
            PriceRecord(date=date(2026, 1, 2), close=105.0),
        ]
        with self.assertRaises(ValueError):
            compute_returns(prices, method="exponential")

    def test_zero_price_skipped(self):
        from market_data import compute_returns, PriceRecord
        prices = [
            PriceRecord(date=date(2026, 1, 1), close=100.0),
            PriceRecord(date=date(2026, 1, 2), close=0.0),
            PriceRecord(date=date(2026, 1, 3), close=105.0),
        ]
        # zero-price records should be filtered out
        returns = compute_returns(prices, method="simple")
        # Only one valid return: 100 -> 105
        self.assertEqual(len(returns), 1)
        self.assertAlmostEqual(returns[0], 0.05, places=4)


class TestVolatility(unittest.TestCase):
    """Test annualized volatility calculation."""

    def test_volatility_basic(self):
        from market_data import compute_volatility
        # Known returns
        returns = [0.01, -0.02, 0.015, -0.005, 0.02]
        vol = compute_volatility(returns, annualize=False)
        self.assertGreater(vol, 0)

    def test_annualized_volatility(self):
        from market_data import compute_volatility
        returns = [0.01, -0.02, 0.015, -0.005, 0.02]
        vol_daily = compute_volatility(returns, annualize=False)
        vol_annual = compute_volatility(returns, annualize=True, periods_per_year=252)
        self.assertAlmostEqual(vol_annual, vol_daily * math.sqrt(252), places=6)

    def test_empty_returns_zero_vol(self):
        from market_data import compute_volatility
        self.assertAlmostEqual(compute_volatility([]), 0.0)

    def test_single_return_zero_vol(self):
        from market_data import compute_volatility
        self.assertAlmostEqual(compute_volatility([0.01]), 0.0)

    def test_constant_returns_zero_vol(self):
        from market_data import compute_volatility
        self.assertAlmostEqual(compute_volatility([0.01] * 10), 0.0)


class TestBeta(unittest.TestCase):
    """Test market beta calculation."""

    def test_perfect_correlation_beta_one(self):
        from market_data import compute_beta
        asset_returns = [0.01, 0.02, -0.01, 0.03, -0.02]
        market_returns = [0.01, 0.02, -0.01, 0.03, -0.02]
        beta = compute_beta(asset_returns, market_returns)
        self.assertAlmostEqual(beta, 1.0, places=4)

    def test_double_leverage_beta_two(self):
        from market_data import compute_beta
        market_returns = [0.01, 0.02, -0.01, 0.03, -0.02]
        asset_returns = [r * 2 for r in market_returns]
        beta = compute_beta(asset_returns, market_returns)
        self.assertAlmostEqual(beta, 2.0, places=4)

    def test_uncorrelated_beta_near_zero(self):
        from market_data import compute_beta
        asset_returns = [0.01, -0.01, 0.01, -0.01]
        market_returns = [0.01, 0.01, -0.01, -0.01]
        beta = compute_beta(asset_returns, market_returns)
        self.assertAlmostEqual(beta, 0.0, places=4)

    def test_empty_returns_beta_none(self):
        from market_data import compute_beta
        self.assertIsNone(compute_beta([], []))

    def test_mismatched_lengths_raises(self):
        from market_data import compute_beta
        with self.assertRaises(ValueError):
            compute_beta([0.01, 0.02], [0.01])


class TestFactorExposures(unittest.TestCase):
    """Test factor exposure estimation."""

    def test_returns_dict_with_expected_keys(self):
        from market_data import estimate_factor_exposures
        asset_returns = [0.01, 0.02, -0.01, 0.03, -0.02, 0.01, -0.005, 0.015, 0.02, -0.01]
        market_returns = [0.005, 0.015, -0.005, 0.02, -0.01, 0.008, -0.003, 0.01, 0.015, -0.005]
        result = estimate_factor_exposures(asset_returns, market_returns)
        self.assertIn("market_beta", result)
        self.assertIn("volatility", result)
        self.assertIn("mean_return", result)

    def test_factor_exposures_values_are_float(self):
        from market_data import estimate_factor_exposures
        asset_returns = [0.01, 0.02, -0.01, 0.03, -0.02]
        market_returns = [0.005, 0.015, -0.005, 0.02, -0.01]
        result = estimate_factor_exposures(asset_returns, market_returns)
        for key, val in result.items():
            self.assertIsInstance(val, float, f"{key} should be float")


class TestMarketDataResult(unittest.TestCase):
    """Test MarketDataResult container."""

    def test_construction(self):
        from market_data import MarketDataResult, PriceRecord
        prices = [PriceRecord(date=date(2026, 1, 1), close=100.0)]
        result = MarketDataResult(
            ticker="AAPL",
            prices=prices,
            returns=[],
            volatility=0.2,
            factor_exposures={"market_beta": 1.1},
        )
        self.assertEqual(result.ticker, "AAPL")
        self.assertAlmostEqual(result.volatility, 0.2)

    def test_to_dict(self):
        from market_data import MarketDataResult, PriceRecord
        result = MarketDataResult(
            ticker="AAPL",
            prices=[PriceRecord(date=date(2026, 1, 1), close=100.0)],
            returns=[0.05],
            volatility=0.2,
            factor_exposures={"market_beta": 1.1},
        )
        d = result.to_dict()
        self.assertEqual(d["ticker"], "AAPL")
        self.assertEqual(d["num_prices"], 1)
        self.assertAlmostEqual(d["volatility"], 0.2)
        self.assertIn("factor_exposures", d)

    def test_summary_string(self):
        from market_data import MarketDataResult, PriceRecord
        result = MarketDataResult(
            ticker="AAPL",
            prices=[PriceRecord(date=date(2026, 1, 1), close=100.0)],
            returns=[0.05],
            volatility=0.2,
            factor_exposures={"market_beta": 1.1},
        )
        s = result.summary()
        self.assertIn("AAPL", s)
        self.assertIn("0.2", s)


class TestMacroData(unittest.TestCase):
    """Test macro data retrieval (CAPE, risk-free rate)."""

    def test_risk_free_rate_structure(self):
        from market_data import MacroData
        md = MacroData(risk_free_rate=0.05, cape_ratio=30.5, as_of=date(2026, 3, 25))
        self.assertAlmostEqual(md.risk_free_rate, 0.05)
        self.assertAlmostEqual(md.cape_ratio, 30.5)
        self.assertEqual(md.as_of, date(2026, 3, 25))

    def test_macro_data_to_dict(self):
        from market_data import MacroData
        md = MacroData(risk_free_rate=0.05, cape_ratio=30.5, as_of=date(2026, 3, 25))
        d = md.to_dict()
        self.assertIn("risk_free_rate", d)
        self.assertIn("cape_ratio", d)


class TestParseCsvPrices(unittest.TestCase):
    """Test CSV price parsing."""

    def test_parse_basic_csv(self):
        from market_data import parse_csv_prices
        csv_content = "Date,Close\n2026-01-01,100.0\n2026-01-02,105.0\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()
            prices = parse_csv_prices(f.name)
        os.unlink(f.name)
        self.assertEqual(len(prices), 2)
        self.assertAlmostEqual(prices[0].close, 100.0)
        self.assertEqual(prices[0].date, date(2026, 1, 1))

    def test_parse_ohlcv_csv(self):
        from market_data import parse_csv_prices
        csv_content = "Date,Open,High,Low,Close,Volume\n2026-01-01,99,102,98,100,5000\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()
            prices = parse_csv_prices(f.name)
        os.unlink(f.name)
        self.assertEqual(len(prices), 1)
        self.assertAlmostEqual(prices[0].open, 99.0)
        self.assertAlmostEqual(prices[0].high, 102.0)
        self.assertAlmostEqual(prices[0].low, 98.0)
        self.assertEqual(prices[0].volume, 5000)

    def test_parse_handles_dollar_signs_and_commas(self):
        from market_data import parse_csv_prices
        csv_content = "Date,Close\n2026-01-01,$1,234.56\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()
            prices = parse_csv_prices(f.name)
        os.unlink(f.name)
        self.assertEqual(len(prices), 1)
        self.assertAlmostEqual(prices[0].close, 1234.56)

    def test_empty_csv_returns_empty(self):
        from market_data import parse_csv_prices
        csv_content = "Date,Close\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()
            prices = parse_csv_prices(f.name)
        os.unlink(f.name)
        self.assertEqual(len(prices), 0)


class TestParseJsonPrices(unittest.TestCase):
    """Test JSON price parsing."""

    def test_parse_json_array(self):
        from market_data import parse_json_prices
        data = [
            {"date": "2026-01-01", "close": 100.0},
            {"date": "2026-01-02", "close": 105.0},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            prices = parse_json_prices(f.name)
        os.unlink(f.name)
        self.assertEqual(len(prices), 2)

    def test_parse_json_with_ohlcv(self):
        from market_data import parse_json_prices
        data = [{"date": "2026-01-01", "open": 99, "high": 102, "low": 98, "close": 100, "volume": 5000}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            prices = parse_json_prices(f.name)
        os.unlink(f.name)
        self.assertEqual(len(prices), 1)
        self.assertAlmostEqual(prices[0].open, 99.0)


class TestAnalyzeTicker(unittest.TestCase):
    """Test the high-level analyze_ticker function."""

    def test_analyze_from_prices(self):
        from market_data import analyze_ticker, PriceRecord
        prices = [
            PriceRecord(date=date(2026, 1, d), close=100 + d)
            for d in range(1, 22)
        ]
        result = analyze_ticker("TEST", prices=prices)
        self.assertEqual(result.ticker, "TEST")
        self.assertEqual(len(result.returns), 20)
        self.assertGreater(result.volatility, 0)

    def test_analyze_from_csv(self):
        from market_data import analyze_ticker
        csv_content = "Date,Close\n"
        for d in range(1, 22):
            csv_content += f"2026-01-{d:02d},{100 + d}\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()
            result = analyze_ticker("TEST", csv_path=f.name)
        os.unlink(f.name)
        self.assertEqual(result.ticker, "TEST")
        self.assertEqual(len(result.returns), 20)

    def test_analyze_no_data_raises(self):
        from market_data import analyze_ticker
        with self.assertRaises(ValueError):
            analyze_ticker("TEST")


class TestMultiTickerAnalysis(unittest.TestCase):
    """Test analyzing multiple tickers."""

    def test_analyze_multiple(self):
        from market_data import analyze_multiple, PriceRecord
        ticker_prices = {
            "AAPL": [PriceRecord(date=date(2026, 1, d), close=100 + d) for d in range(1, 12)],
            "GOOG": [PriceRecord(date=date(2026, 1, d), close=200 + d * 2) for d in range(1, 12)],
        }
        results = analyze_multiple(ticker_prices)
        self.assertEqual(len(results), 2)
        self.assertIn("AAPL", results)
        self.assertIn("GOOG", results)


class TestCLI(unittest.TestCase):
    """Test CLI mode."""

    def test_cli_with_csv(self):
        from market_data import cli_main
        csv_content = "Date,Close\n"
        for d in range(1, 22):
            csv_content += f"2026-01-{d:02d},{100 + d}\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()
            with patch("sys.stdout"):
                result = cli_main(["--ticker", "TEST", "--csv", f.name])
        os.unlink(f.name)
        self.assertEqual(result, 0)

    def test_cli_json_output(self):
        from market_data import cli_main
        csv_content = "Date,Close\n"
        for d in range(1, 22):
            csv_content += f"2026-01-{d:02d},{100 + d}\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()
            import io
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                cli_main(["--ticker", "TEST", "--csv", f.name, "--json"])
        os.unlink(f.name)
        output = buf.getvalue()
        parsed = json.loads(output)
        self.assertEqual(parsed["ticker"], "TEST")

    def test_cli_no_args_returns_error(self):
        from market_data import cli_main
        result = cli_main([])
        self.assertNotEqual(result, 0)


class TestCorrelationMatrix(unittest.TestCase):
    """Test correlation matrix computation."""

    def test_two_ticker_correlation(self):
        from market_data import compute_correlation_matrix
        returns = {
            "A": [0.01, 0.02, -0.01, 0.03],
            "B": [0.01, 0.02, -0.01, 0.03],
        }
        corr = compute_correlation_matrix(returns)
        self.assertAlmostEqual(corr["A"]["A"], 1.0, places=4)
        self.assertAlmostEqual(corr["A"]["B"], 1.0, places=4)

    def test_uncorrelated_tickers(self):
        from market_data import compute_correlation_matrix
        returns = {
            "A": [0.01, -0.01, 0.01, -0.01],
            "B": [0.01, 0.01, -0.01, -0.01],
        }
        corr = compute_correlation_matrix(returns)
        self.assertAlmostEqual(corr["A"]["B"], 0.0, places=4)

    def test_empty_returns_empty_matrix(self):
        from market_data import compute_correlation_matrix
        self.assertEqual(compute_correlation_matrix({}), {})


if __name__ == "__main__":
    unittest.main()
