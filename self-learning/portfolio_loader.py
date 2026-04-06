#!/usr/bin/env python3
"""portfolio_loader.py — MT-37 Phase 3: Portfolio holdings parser.

Parses user holdings from CSV, JSON, or Python dicts into a normalized
Portfolio model. Supports common brokerage export formats.

Usage:
    from portfolio_loader import load, Portfolio, Holding

    # Auto-detect format
    portfolio = load("holdings.csv")
    portfolio = load("holdings.json")

    # Or from Python dicts
    portfolio = load_from_dicts([
        {"ticker": "AAPL", "shares": 10, "cost_basis": 150.0},
    ])

    # Access holdings
    for h in portfolio.holdings:
        print(f"{h.ticker}: {h.shares} shares @ ${h.cost_basis}")

CLI:
    python3 portfolio_loader.py holdings.csv
    python3 portfolio_loader.py holdings.json --json
"""
from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass, field


# Common header aliases for brokerage exports
TICKER_ALIASES = {"ticker", "symbol", "stock", "name", "security"}
SHARES_ALIASES = {"shares", "quantity", "qty", "units", "amount"}
COST_BASIS_ALIASES = {"cost_basis", "cost basis", "costbasis", "avg_cost", "average cost", "price"}
CURRENT_PRICE_ALIASES = {"current_price", "current price", "market_price", "market price", "last_price", "last"}


def _clean_number(val: str) -> float:
    """Parse a number string, stripping $, commas, whitespace."""
    if not val or not str(val).strip():
        return 0.0
    s = str(val).strip().replace("$", "").replace(",", "")
    return float(s)


def _find_column(headers: list[str], aliases: set[str]) -> int | None:
    """Find column index matching any alias (case-insensitive)."""
    for i, h in enumerate(headers):
        if h.strip().lower() in aliases:
            return i
    return None


@dataclass
class Holding:
    """A single portfolio holding."""

    ticker: str
    shares: float
    cost_basis: float = 0.0
    current_price: float | None = None

    def __post_init__(self):
        self.ticker = self.ticker.upper().strip()

    def market_value(self) -> float | None:
        """Current market value (shares * current_price)."""
        if self.current_price is None:
            return None
        return self.shares * self.current_price

    def unrealized_gain(self) -> float | None:
        """Unrealized P&L (market_value - cost_basis * shares)."""
        mv = self.market_value()
        if mv is None:
            return None
        return mv - (self.cost_basis * self.shares)

    def weight(self, total_value: float) -> float:
        """Weight in portfolio (0.0-1.0)."""
        if total_value == 0.0:
            return 0.0
        mv = self.market_value()
        if mv is None:
            return 0.0
        return mv / total_value

    def to_dict(self) -> dict:
        """Serialize to dict."""
        d = {"ticker": self.ticker, "shares": self.shares, "cost_basis": self.cost_basis}
        if self.current_price is not None:
            d["current_price"] = self.current_price
        return d


@dataclass
class Portfolio:
    """Container for portfolio holdings."""

    holdings: list[Holding] = field(default_factory=list)

    def add(self, holding: Holding):
        """Add a holding."""
        self.holdings.append(holding)

    def total_cost_basis(self) -> float:
        """Sum of (shares * cost_basis) across all holdings."""
        return sum(h.shares * h.cost_basis for h in self.holdings)

    def total_market_value(self) -> float | None:
        """Sum of market values. None if any holding lacks a price."""
        values = [h.market_value() for h in self.holdings]
        if any(v is None for v in values):
            return None
        return sum(values)

    def tickers(self) -> list[str]:
        """Sorted list of ticker symbols."""
        return sorted(h.ticker for h in self.holdings)

    def get(self, ticker: str) -> Holding | None:
        """Get holding by ticker (case-insensitive)."""
        t = ticker.upper().strip()
        for h in self.holdings:
            if h.ticker == t:
                return h
        return None

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {"holdings": [h.to_dict() for h in self.holdings]}


def load_csv(path: str) -> Portfolio:
    """Load portfolio from CSV file.

    Supports common brokerage header variations (ticker/symbol, shares/quantity, etc.).
    Strips dollar signs and commas from numeric fields.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV file not found: {path}")

    portfolio = Portfolio()

    with open(path, newline="") as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        if headers is None:
            return portfolio

        # Map columns
        ticker_col = _find_column(headers, TICKER_ALIASES)
        shares_col = _find_column(headers, SHARES_ALIASES)
        cost_col = _find_column(headers, COST_BASIS_ALIASES)
        price_col = _find_column(headers, CURRENT_PRICE_ALIASES)

        if ticker_col is None or shares_col is None:
            return portfolio

        for row in reader:
            if not row or not any(cell.strip() for cell in row):
                continue

            ticker = row[ticker_col].strip()
            if not ticker:
                continue

            shares = _clean_number(row[shares_col]) if shares_col < len(row) else 0.0
            cost_basis = _clean_number(row[cost_col]) if cost_col is not None and cost_col < len(row) else 0.0
            current_price = None
            if price_col is not None and price_col < len(row):
                try:
                    current_price = _clean_number(row[price_col])
                except (ValueError, IndexError):
                    pass

            portfolio.add(Holding(
                ticker=ticker,
                shares=shares,
                cost_basis=cost_basis,
                current_price=current_price,
            ))

    return portfolio


def load_json(path: str) -> Portfolio:
    """Load portfolio from JSON file.

    Supports both list-of-dicts and {"holdings": [...]} formats.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"JSON file not found: {path}")

    with open(path) as f:
        data = json.load(f)

    if isinstance(data, dict) and "holdings" in data:
        data = data["holdings"]

    if not isinstance(data, list):
        return Portfolio()

    return load_from_dicts(data)


def load_from_dicts(data: list[dict]) -> Portfolio:
    """Load portfolio from a list of dicts."""
    portfolio = Portfolio()
    for item in data:
        portfolio.add(Holding(
            ticker=item.get("ticker", item.get("symbol", "")),
            shares=float(item.get("shares", item.get("quantity", 0))),
            cost_basis=float(item.get("cost_basis", item.get("cost basis", 0))),
            current_price=item.get("current_price", item.get("current price")),
        ))
    return portfolio


def load(path: str) -> Portfolio:
    """Auto-detect file format and load portfolio."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return load_csv(path)
    elif ext == ".json":
        return load_json(path)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Use .csv or .json")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 portfolio_loader.py <file.csv|file.json> [--json]")
        sys.exit(1)

    filepath = sys.argv[1]
    output_json = "--json" in sys.argv

    try:
        p = load(filepath)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if output_json:
        print(json.dumps(p.to_dict(), indent=2))
    else:
        print(f"Portfolio: {len(p.holdings)} holdings")
        print(f"Total cost basis: ${p.total_cost_basis():,.2f}")
        tmv = p.total_market_value()
        if tmv is not None:
            print(f"Total market value: ${tmv:,.2f}")
        for h in p.holdings:
            print(f"  {h.ticker}: {h.shares} shares @ ${h.cost_basis:.2f}")
