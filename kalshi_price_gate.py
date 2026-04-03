#!/usr/bin/env python3
"""kalshi_price_gate.py - evaluate quoted Kalshi prices against approved ceilings.

Usage:
    python3 kalshi_price_gate.py list
    python3 kalshi_price_gate.py eval --market rockets-bucks --yes 61
    python3 kalshi_price_gate.py eval --market hawks-magic --yes 0.58 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MarketGate:
    key: str
    label: str
    max_yes_cents: int
    note: str


APRIL_4_2026_BOARD: dict[str, MarketGate] = {
    "rockets-bucks": MarketGate(
        key="rockets-bucks",
        label="Rockets over Bucks",
        max_yes_cents=62,
        note="Best April 4 lean; only take if the market has not already priced Houston too richly.",
    ),
    "hawks-magic": MarketGate(
        key="hawks-magic",
        label="Hawks over Magic",
        max_yes_cents=59,
        note="Atlanta form lean; pass if the streak premium is already fully priced.",
    ),
    "pacers-bulls": MarketGate(
        key="pacers-bulls",
        label="Pacers over Bulls",
        max_yes_cents=57,
        note="Weakest of the three; price discipline matters more than team preference.",
    ),
}


def normalize_yes_price(value: float) -> int:
    """Accept dollars or cents and normalize to integer cents."""
    if value <= 1.0:
        value *= 100.0
    return int(round(value))


def list_board(board: dict[str, MarketGate] = APRIL_4_2026_BOARD) -> list[MarketGate]:
    return [board[key] for key in sorted(board)]


def evaluate_market(
    market_key: str,
    yes_price: float,
    board: dict[str, MarketGate] = APRIL_4_2026_BOARD,
) -> dict[str, object]:
    if market_key not in board:
        raise KeyError(market_key)

    gate = board[market_key]
    quoted_yes_cents = normalize_yes_price(yes_price)
    verdict = "bet" if quoted_yes_cents <= gate.max_yes_cents else "pass"
    margin_cents = gate.max_yes_cents - quoted_yes_cents

    return {
        "market": gate.key,
        "label": gate.label,
        "quoted_yes_cents": quoted_yes_cents,
        "max_yes_cents": gate.max_yes_cents,
        "verdict": verdict,
        "margin_cents": margin_cents,
        "note": gate.note,
    }


def format_list(markets: list[MarketGate]) -> str:
    lines = ["APRIL 4 PRICE GATE BOARD:"]
    for market in markets:
        lines.append(f"- {market.key}: {market.label} | max YES {market.max_yes_cents}c")
        lines.append(f"  {market.note}")
    return "\n".join(lines) + "\n"


def format_eval(result: dict[str, object]) -> str:
    verdict = str(result["verdict"]).upper()
    margin = int(result["margin_cents"])
    if margin >= 0:
        price_line = f"{result['quoted_yes_cents']}c <= {result['max_yes_cents']}c ceiling"
    else:
        price_line = f"{result['quoted_yes_cents']}c > {result['max_yes_cents']}c ceiling"
    return (
        f"{verdict}: {result['label']}\n"
        f"{price_line}\n"
        f"Margin: {margin:+d}c\n"
        f"Note: {result['note']}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate quoted Kalshi YES prices against approved ceilings.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List the approved board and price ceilings.")

    eval_parser = subparsers.add_parser("eval", help="Evaluate a quoted YES price.")
    eval_parser.add_argument("--market", required=True, choices=sorted(APRIL_4_2026_BOARD))
    eval_parser.add_argument("--yes", required=True, type=float, help="Quoted YES price in cents or dollars.")
    eval_parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")

    args = parser.parse_args(argv)

    if args.command == "list":
        sys.stdout.write(format_list(list_board()))
        return 0

    result = evaluate_market(args.market, args.yes)
    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_eval(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
