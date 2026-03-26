#!/usr/bin/env python3
"""market_data.py — MT-37 Phase 4: Market data retrieval and analysis.

Computes returns, volatility, beta, factor exposures, and correlation matrices
from price data. Supports CSV and JSON input formats.

Usage:
    from market_data import analyze_ticker, PriceRecord

    # From in-memory prices
    prices = [PriceRecord(date=date(2026, 1, 1), close=100.0), ...]
    result = analyze_ticker("AAPL", prices=prices)
    print(result.summary())

    # From CSV file
    result = analyze_ticker("AAPL", csv_path="prices.csv")

    # Multiple tickers + correlation
    results = analyze_multiple(ticker_prices)
    corr = compute_correlation_matrix({t: r.returns for t, r in results.items()})

CLI:
    python3 market_data.py --ticker AAPL --csv prices.csv
    python3 market_data.py --ticker AAPL --csv prices.csv --json
"""

import csv
import json
import math
import os
import statistics
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class PriceRecord:
    """A single price observation."""
    date: date
    close: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[int] = None


@dataclass
class MacroData:
    """Macro-economic data snapshot."""
    risk_free_rate: float
    cape_ratio: float
    as_of: date

    def to_dict(self) -> dict:
        return {
            "risk_free_rate": self.risk_free_rate,
            "cape_ratio": self.cape_ratio,
            "as_of": self.as_of.isoformat(),
        }


@dataclass
class MarketDataResult:
    """Analysis result for a single ticker."""
    ticker: str
    prices: list[PriceRecord]
    returns: list[float]
    volatility: float
    factor_exposures: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "num_prices": len(self.prices),
            "num_returns": len(self.returns),
            "volatility": self.volatility,
            "factor_exposures": self.factor_exposures,
            "mean_return": statistics.mean(self.returns) if self.returns else 0.0,
        }

    def summary(self) -> str:
        lines = [
            f"{self.ticker}: {len(self.prices)} prices, {len(self.returns)} returns",
            f"  Volatility (ann.): {self.volatility:.4f}",
        ]
        if self.returns:
            lines.append(f"  Mean return: {statistics.mean(self.returns):.6f}")
        for k, v in self.factor_exposures.items():
            lines.append(f"  {k}: {v:.4f}")
        return "\n".join(lines)


# ── Return Calculation ───────────────────────────────────────────────────────

def compute_returns(prices: list[PriceRecord], method: str = "simple") -> list[float]:
    """Compute return series from price records.

    Args:
        prices: List of PriceRecord sorted by date.
        method: "simple" for (p1-p0)/p0, "log" for ln(p1/p0).

    Returns:
        List of returns (length = len(prices) - 1, minus any zero-price gaps).
    """
    if method not in ("simple", "log"):
        raise ValueError(f"Unknown return method: {method!r}. Use 'simple' or 'log'.")

    if len(prices) < 2:
        return []

    # Filter out zero/negative close prices
    valid = [p for p in prices if p.close > 0]
    if len(valid) < 2:
        return []

    returns = []
    for i in range(1, len(valid)):
        p0 = valid[i - 1].close
        p1 = valid[i].close
        if method == "simple":
            returns.append((p1 - p0) / p0)
        else:  # log
            returns.append(math.log(p1 / p0))
    return returns


# ── Volatility ───────────────────────────────────────────────────────────────

def compute_volatility(
    returns: list[float],
    annualize: bool = True,
    periods_per_year: int = 252,
) -> float:
    """Compute (optionally annualized) standard deviation of returns."""
    if len(returns) < 2:
        return 0.0
    vol = statistics.stdev(returns)
    if annualize:
        vol *= math.sqrt(periods_per_year)
    return vol


# ── Beta ─────────────────────────────────────────────────────────────────────

def compute_beta(
    asset_returns: list[float],
    market_returns: list[float],
) -> Optional[float]:
    """Compute market beta via OLS: Cov(asset, market) / Var(market).

    Returns None if inputs are empty. Raises ValueError if lengths differ.
    """
    if len(asset_returns) != len(market_returns):
        raise ValueError(
            f"Length mismatch: asset={len(asset_returns)}, market={len(market_returns)}"
        )
    if len(asset_returns) < 2:
        return None

    n = len(asset_returns)
    mean_a = sum(asset_returns) / n
    mean_m = sum(market_returns) / n

    cov = sum((a - mean_a) * (m - mean_m) for a, m in zip(asset_returns, market_returns)) / (n - 1)
    var_m = sum((m - mean_m) ** 2 for m in market_returns) / (n - 1)

    if var_m == 0:
        return 0.0
    return cov / var_m


# ── Factor Exposures ─────────────────────────────────────────────────────────

def estimate_factor_exposures(
    asset_returns: list[float],
    market_returns: list[float],
) -> dict[str, float]:
    """Estimate basic factor exposures for an asset.

    Returns dict with market_beta, volatility, and mean_return.
    Full Fama-French factor exposures require factor return series
    (SMB, HML, etc.) which are added in later phases.
    """
    beta = compute_beta(asset_returns, market_returns)
    vol = compute_volatility(asset_returns, annualize=True)
    mean_ret = statistics.mean(asset_returns) if asset_returns else 0.0

    return {
        "market_beta": float(beta) if beta is not None else 0.0,
        "volatility": vol,
        "mean_return": mean_ret,
    }


# ── Correlation Matrix ───────────────────────────────────────────────────────

def compute_correlation_matrix(returns: dict[str, list[float]]) -> dict[str, dict[str, float]]:
    """Compute pairwise correlation matrix for multiple return series.

    Args:
        returns: Dict mapping ticker -> list of returns (same length).

    Returns:
        Nested dict: corr[ticker_a][ticker_b] = correlation coefficient.
    """
    if not returns:
        return {}

    tickers = sorted(returns.keys())
    matrix: dict[str, dict[str, float]] = {t: {} for t in tickers}

    for i, t1 in enumerate(tickers):
        for j, t2 in enumerate(tickers):
            if i == j:
                matrix[t1][t2] = 1.0
            elif j > i:
                r1 = returns[t1]
                r2 = returns[t2]
                n = min(len(r1), len(r2))
                if n < 2:
                    matrix[t1][t2] = 0.0
                    matrix[t2][t1] = 0.0
                    continue

                mean1 = sum(r1[:n]) / n
                mean2 = sum(r2[:n]) / n

                cov = sum((r1[k] - mean1) * (r2[k] - mean2) for k in range(n)) / (n - 1)
                std1 = math.sqrt(sum((r1[k] - mean1) ** 2 for k in range(n)) / (n - 1))
                std2 = math.sqrt(sum((r2[k] - mean2) ** 2 for k in range(n)) / (n - 1))

                if std1 == 0 or std2 == 0:
                    corr = 0.0
                else:
                    corr = cov / (std1 * std2)
                matrix[t1][t2] = corr
                matrix[t2][t1] = corr

    return matrix


# ── CSV/JSON Parsing ─────────────────────────────────────────────────────────

# Column name aliases (case-insensitive)
_DATE_ALIASES = {"date", "timestamp", "time", "day"}
_CLOSE_ALIASES = {"close", "adj close", "adj_close", "adjusted close", "price", "last"}
_OPEN_ALIASES = {"open"}
_HIGH_ALIASES = {"high"}
_LOW_ALIASES = {"low"}
_VOLUME_ALIASES = {"volume", "vol"}


def _find_col(headers: list[str], aliases: set[str]) -> Optional[int]:
    for i, h in enumerate(headers):
        if h.strip().lower() in aliases:
            return i
    return None


def _clean_num(val: str) -> float:
    if not val or not str(val).strip():
        return 0.0
    return float(str(val).strip().replace("$", "").replace(",", ""))


def _parse_date(s: str) -> date:
    """Parse date string in common formats."""
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s!r}")


def parse_csv_prices(path: str) -> list[PriceRecord]:
    """Parse price data from a CSV file."""
    records = []
    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        raw_headers = next(reader, None)
        if not raw_headers:
            return []

        # Handle BOM
        raw_headers[0] = raw_headers[0].lstrip("\ufeff")
        headers = [h.strip().lower() for h in raw_headers]

        date_idx = _find_col(headers, _DATE_ALIASES)
        close_idx = _find_col(headers, _CLOSE_ALIASES)
        open_idx = _find_col(headers, _OPEN_ALIASES)
        high_idx = _find_col(headers, _HIGH_ALIASES)
        low_idx = _find_col(headers, _LOW_ALIASES)
        vol_idx = _find_col(headers, _VOLUME_ALIASES)

        if date_idx is None or close_idx is None:
            return []

        for row in reader:
            if not row or not row[date_idx].strip():
                continue
            try:
                d = _parse_date(row[date_idx])
                # Rejoin fields after close_idx that look like continuation of a
                # comma-separated number (e.g. "$1,234.56" split into "$1" + "234.56")
                close_raw = row[close_idx]
                k = close_idx + 1
                while k < len(row) and row[k].strip().replace(".", "").isdigit():
                    close_raw += "," + row[k]
                    k += 1
                close = _clean_num(close_raw)
                pr = PriceRecord(date=d, close=close)
                if open_idx is not None and open_idx < len(row):
                    pr.open = _clean_num(row[open_idx])
                if high_idx is not None and high_idx < len(row):
                    pr.high = _clean_num(row[high_idx])
                if low_idx is not None and low_idx < len(row):
                    pr.low = _clean_num(row[low_idx])
                if vol_idx is not None and vol_idx < len(row):
                    pr.volume = int(_clean_num(row[vol_idx]))
                records.append(pr)
            except (ValueError, IndexError):
                continue

    return sorted(records, key=lambda r: r.date)


def parse_json_prices(path: str) -> list[PriceRecord]:
    """Parse price data from a JSON file (array of objects)."""
    with open(path, "r") as f:
        data = json.load(f)

    if not isinstance(data, list):
        return []

    records = []
    for item in data:
        if not isinstance(item, dict):
            continue
        date_str = item.get("date", "")
        close = item.get("close")
        if not date_str or close is None:
            continue
        try:
            d = _parse_date(str(date_str))
            pr = PriceRecord(date=d, close=float(close))
            if "open" in item:
                pr.open = float(item["open"])
            if "high" in item:
                pr.high = float(item["high"])
            if "low" in item:
                pr.low = float(item["low"])
            if "volume" in item:
                pr.volume = int(item["volume"])
            records.append(pr)
        except (ValueError, TypeError):
            continue

    return sorted(records, key=lambda r: r.date)


# ── High-Level Analysis ─────────────────────────────────────────────────────

def analyze_ticker(
    ticker: str,
    prices: Optional[list[PriceRecord]] = None,
    csv_path: Optional[str] = None,
    json_path: Optional[str] = None,
    market_returns: Optional[list[float]] = None,
) -> MarketDataResult:
    """Analyze a single ticker: returns, volatility, factor exposures.

    Provide prices directly, or pass csv_path/json_path to load from file.
    """
    if prices is None:
        if csv_path:
            prices = parse_csv_prices(csv_path)
        elif json_path:
            prices = parse_json_prices(json_path)
        else:
            raise ValueError("Must provide prices, csv_path, or json_path")

    returns = compute_returns(prices, method="simple")
    vol = compute_volatility(returns, annualize=True)

    if market_returns and len(market_returns) >= 2:
        # Trim to matching length
        n = min(len(returns), len(market_returns))
        exposures = estimate_factor_exposures(returns[:n], market_returns[:n])
    else:
        exposures = {
            "volatility": vol,
            "mean_return": statistics.mean(returns) if returns else 0.0,
        }

    return MarketDataResult(
        ticker=ticker,
        prices=prices,
        returns=returns,
        volatility=vol,
        factor_exposures=exposures,
    )


def analyze_multiple(
    ticker_prices: dict[str, list[PriceRecord]],
    market_returns: Optional[list[float]] = None,
) -> dict[str, MarketDataResult]:
    """Analyze multiple tickers."""
    return {
        ticker: analyze_ticker(ticker, prices=prices, market_returns=market_returns)
        for ticker, prices in ticker_prices.items()
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def cli_main(args: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Market data analysis (MT-37 Phase 4)")
    parser.add_argument("--ticker", "-t", help="Ticker symbol")
    parser.add_argument("--csv", help="Path to CSV price file")
    parser.add_argument("--json-file", help="Path to JSON price file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    parsed = parser.parse_args(args)

    if not parsed.ticker or (not parsed.csv and not parsed.json_file):
        parser.print_help()
        return 1

    try:
        result = analyze_ticker(
            parsed.ticker,
            csv_path=parsed.csv,
            json_path=parsed.json_file,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if parsed.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.summary())
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
