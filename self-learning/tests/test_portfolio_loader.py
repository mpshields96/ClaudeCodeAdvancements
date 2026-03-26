#!/usr/bin/env python3
"""Tests for portfolio_loader.py — MT-37 Phase 3.

Parses user holdings from CSV/JSON/dict into a normalized Holdings model.
Supports brokerage-style exports (ticker, shares, cost basis).
"""

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import portfolio_loader as pl


class TestHolding(unittest.TestCase):
    """Test individual Holding dataclass."""

    def test_create_holding(self):
        h = pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0)
        self.assertEqual(h.ticker, "AAPL")
        self.assertEqual(h.shares, 10.0)
        self.assertEqual(h.cost_basis, 150.0)

    def test_market_value(self):
        h = pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0, current_price=175.0)
        self.assertAlmostEqual(h.market_value(), 1750.0)

    def test_market_value_no_price(self):
        h = pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0)
        self.assertIsNone(h.market_value())

    def test_unrealized_gain(self):
        h = pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0, current_price=175.0)
        self.assertAlmostEqual(h.unrealized_gain(), 250.0)

    def test_unrealized_gain_loss(self):
        h = pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0, current_price=130.0)
        self.assertAlmostEqual(h.unrealized_gain(), -200.0)

    def test_unrealized_gain_no_price(self):
        h = pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0)
        self.assertIsNone(h.unrealized_gain())

    def test_weight_in_portfolio(self):
        h = pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0, current_price=100.0)
        self.assertAlmostEqual(h.weight(total_value=5000.0), 0.20)

    def test_weight_zero_total(self):
        h = pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0, current_price=100.0)
        self.assertEqual(h.weight(total_value=0.0), 0.0)

    def test_ticker_normalized_uppercase(self):
        h = pl.Holding(ticker="aapl", shares=10.0, cost_basis=150.0)
        self.assertEqual(h.ticker, "AAPL")

    def test_to_dict(self):
        h = pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0)
        d = h.to_dict()
        self.assertEqual(d["ticker"], "AAPL")
        self.assertEqual(d["shares"], 10.0)
        self.assertEqual(d["cost_basis"], 150.0)


class TestPortfolio(unittest.TestCase):
    """Test Portfolio container."""

    def test_create_empty(self):
        p = pl.Portfolio()
        self.assertEqual(len(p.holdings), 0)

    def test_add_holding(self):
        p = pl.Portfolio()
        p.add(pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0))
        self.assertEqual(len(p.holdings), 1)

    def test_total_cost_basis(self):
        p = pl.Portfolio()
        p.add(pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0))
        p.add(pl.Holding(ticker="GOOG", shares=5.0, cost_basis=100.0))
        self.assertAlmostEqual(p.total_cost_basis(), 2000.0)  # 10*150 + 5*100

    def test_total_market_value(self):
        p = pl.Portfolio()
        p.add(pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0, current_price=175.0))
        p.add(pl.Holding(ticker="GOOG", shares=5.0, cost_basis=100.0, current_price=120.0))
        self.assertAlmostEqual(p.total_market_value(), 2350.0)  # 10*175 + 5*120

    def test_total_market_value_partial_prices(self):
        """If some holdings lack prices, return None."""
        p = pl.Portfolio()
        p.add(pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0, current_price=175.0))
        p.add(pl.Holding(ticker="GOOG", shares=5.0, cost_basis=100.0))  # no price
        self.assertIsNone(p.total_market_value())

    def test_tickers(self):
        p = pl.Portfolio()
        p.add(pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0))
        p.add(pl.Holding(ticker="GOOG", shares=5.0, cost_basis=100.0))
        self.assertEqual(p.tickers(), ["AAPL", "GOOG"])

    def test_get_holding(self):
        p = pl.Portfolio()
        p.add(pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0))
        h = p.get("AAPL")
        self.assertIsNotNone(h)
        self.assertEqual(h.shares, 10.0)

    def test_get_holding_not_found(self):
        p = pl.Portfolio()
        self.assertIsNone(p.get("AAPL"))

    def test_get_case_insensitive(self):
        p = pl.Portfolio()
        p.add(pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0))
        h = p.get("aapl")
        self.assertIsNotNone(h)

    def test_to_dict(self):
        p = pl.Portfolio()
        p.add(pl.Holding(ticker="AAPL", shares=10.0, cost_basis=150.0))
        d = p.to_dict()
        self.assertEqual(len(d["holdings"]), 1)
        self.assertEqual(d["holdings"][0]["ticker"], "AAPL")


class TestLoadCSV(unittest.TestCase):
    """Test CSV loading."""

    def _write_csv(self, rows, headers=None):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
        writer = csv.writer(f)
        if headers:
            writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        f.close()
        return f.name

    def test_basic_csv(self):
        path = self._write_csv(
            [["AAPL", "10", "150.0"], ["GOOG", "5", "100.0"]],
            headers=["ticker", "shares", "cost_basis"],
        )
        try:
            p = pl.load_csv(path)
            self.assertEqual(len(p.holdings), 2)
            self.assertEqual(p.holdings[0].ticker, "AAPL")
            self.assertAlmostEqual(p.holdings[0].shares, 10.0)
        finally:
            os.unlink(path)

    def test_csv_with_extra_columns(self):
        path = self._write_csv(
            [["AAPL", "10", "150.0", "Technology", "Large Cap"]],
            headers=["ticker", "shares", "cost_basis", "sector", "cap"],
        )
        try:
            p = pl.load_csv(path)
            self.assertEqual(len(p.holdings), 1)
        finally:
            os.unlink(path)

    def test_csv_alternate_headers(self):
        """Support common brokerage export header variations."""
        path = self._write_csv(
            [["AAPL", "10", "150.0"]],
            headers=["Symbol", "Quantity", "Cost Basis"],
        )
        try:
            p = pl.load_csv(path)
            self.assertEqual(len(p.holdings), 1)
            self.assertEqual(p.holdings[0].ticker, "AAPL")
        finally:
            os.unlink(path)

    def test_csv_with_dollar_signs(self):
        path = self._write_csv(
            [["AAPL", "10", "$150.00"]],
            headers=["ticker", "shares", "cost_basis"],
        )
        try:
            p = pl.load_csv(path)
            self.assertAlmostEqual(p.holdings[0].cost_basis, 150.0)
        finally:
            os.unlink(path)

    def test_csv_with_commas_in_numbers(self):
        path = self._write_csv(
            [["AAPL", "1,000", "$1,500.00"]],
            headers=["ticker", "shares", "cost_basis"],
        )
        try:
            p = pl.load_csv(path)
            self.assertAlmostEqual(p.holdings[0].shares, 1000.0)
            self.assertAlmostEqual(p.holdings[0].cost_basis, 1500.0)
        finally:
            os.unlink(path)

    def test_empty_csv(self):
        path = self._write_csv([], headers=["ticker", "shares", "cost_basis"])
        try:
            p = pl.load_csv(path)
            self.assertEqual(len(p.holdings), 0)
        finally:
            os.unlink(path)

    def test_csv_skip_blank_rows(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        f.write("ticker,shares,cost_basis\nAAPL,10,150\n\n\nGOOG,5,100\n")
        f.close()
        try:
            p = pl.load_csv(f.name)
            self.assertEqual(len(p.holdings), 2)
        finally:
            os.unlink(f.name)

    def test_csv_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            pl.load_csv("/nonexistent/file.csv")


class TestLoadJSON(unittest.TestCase):
    """Test JSON loading."""

    def _write_json(self, data):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, f)
        f.close()
        return f.name

    def test_basic_json_list(self):
        path = self._write_json([
            {"ticker": "AAPL", "shares": 10, "cost_basis": 150.0},
            {"ticker": "GOOG", "shares": 5, "cost_basis": 100.0},
        ])
        try:
            p = pl.load_json(path)
            self.assertEqual(len(p.holdings), 2)
        finally:
            os.unlink(path)

    def test_json_with_holdings_key(self):
        path = self._write_json({
            "holdings": [
                {"ticker": "AAPL", "shares": 10, "cost_basis": 150.0},
            ]
        })
        try:
            p = pl.load_json(path)
            self.assertEqual(len(p.holdings), 1)
        finally:
            os.unlink(path)

    def test_json_with_current_price(self):
        path = self._write_json([
            {"ticker": "AAPL", "shares": 10, "cost_basis": 150.0, "current_price": 175.0},
        ])
        try:
            p = pl.load_json(path)
            self.assertAlmostEqual(p.holdings[0].current_price, 175.0)
        finally:
            os.unlink(path)

    def test_empty_json(self):
        path = self._write_json([])
        try:
            p = pl.load_json(path)
            self.assertEqual(len(p.holdings), 0)
        finally:
            os.unlink(path)


class TestLoadFromDict(unittest.TestCase):
    """Test loading from Python dicts."""

    def test_from_dict_list(self):
        data = [
            {"ticker": "AAPL", "shares": 10, "cost_basis": 150.0},
            {"ticker": "GOOG", "shares": 5, "cost_basis": 100.0},
        ]
        p = pl.load_from_dicts(data)
        self.assertEqual(len(p.holdings), 2)

    def test_from_dict_missing_optional(self):
        data = [{"ticker": "AAPL", "shares": 10}]
        p = pl.load_from_dicts(data)
        self.assertEqual(p.holdings[0].cost_basis, 0.0)


class TestAutoDetect(unittest.TestCase):
    """Test auto-detection of file format."""

    def test_detect_csv(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        f.write("ticker,shares,cost_basis\nAAPL,10,150\n")
        f.close()
        try:
            p = pl.load(f.name)
            self.assertEqual(len(p.holdings), 1)
        finally:
            os.unlink(f.name)

    def test_detect_json(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump([{"ticker": "AAPL", "shares": 10, "cost_basis": 150}], f)
        f.close()
        try:
            p = pl.load(f.name)
            self.assertEqual(len(p.holdings), 1)
        finally:
            os.unlink(f.name)

    def test_unsupported_format(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".xlsx", delete=False)
        f.write("not real xlsx")
        f.close()
        try:
            with self.assertRaises(ValueError):
                pl.load(f.name)
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
