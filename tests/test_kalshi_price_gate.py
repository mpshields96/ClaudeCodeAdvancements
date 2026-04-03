#!/usr/bin/env python3
"""Tests for kalshi_price_gate.py."""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kalshi_price_gate import evaluate_market, format_eval, list_board, main, normalize_yes_price


class TestKalshiPriceGate(unittest.TestCase):
    def test_normalize_yes_price_accepts_cents(self):
        self.assertEqual(normalize_yes_price(61), 61)

    def test_normalize_yes_price_accepts_dollars(self):
        self.assertEqual(normalize_yes_price(0.58), 58)

    def test_list_board_contains_three_markets(self):
        board = list_board()
        self.assertEqual(len(board), 3)
        self.assertEqual(board[0].key, "hawks-magic")

    def test_evaluate_market_bet_when_below_ceiling(self):
        result = evaluate_market("rockets-bucks", 61)
        self.assertEqual(result["verdict"], "bet")
        self.assertEqual(result["margin_cents"], 1)

    def test_evaluate_market_pass_when_above_ceiling(self):
        result = evaluate_market("pacers-bulls", 59)
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["margin_cents"], -2)

    def test_format_eval_mentions_ceiling(self):
        text = format_eval(evaluate_market("hawks-magic", 58))
        self.assertIn("BET", text)
        self.assertIn("ceiling", text)

    def test_main_json_emits_structured_payload(self):
        with patch("sys.stdout.write") as mock_write:
            exit_code = main(["eval", "--market", "hawks-magic", "--yes", "0.58", "--json"])

        self.assertEqual(exit_code, 0)
        payload = "".join(call.args[0] for call in mock_write.call_args_list)
        data = json.loads(payload)
        self.assertEqual(data["market"], "hawks-magic")
        self.assertEqual(data["quoted_yes_cents"], 58)
        self.assertEqual(data["verdict"], "bet")


if __name__ == "__main__":
    unittest.main()
