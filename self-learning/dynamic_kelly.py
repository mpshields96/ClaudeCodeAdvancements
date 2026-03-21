#!/usr/bin/env python3
"""
dynamic_kelly.py — MT-26 Tier 2: Dynamic Kelly with Bayesian Updating

Replaces static Kelly fraction with time-decaying Kelly that updates as
new price data arrives during a betting window (e.g., 15-min crypto direction).

Key concepts from papers:
- arXiv:2602.09982: Kelly bets as time-updating probabilistic forecasts
- arXiv:2502.16859: Kelly for stochastic binary Markovian games with p > q edge
- MDPI Mathematics 12(11):1725: Capital growth under dynamic market conditions

Features:
1. Classic Kelly fraction: f* = (p*b - q) / b where b = (1/market_price - 1)
2. Bayesian belief updating: update prior probability with new observations
3. Time decay: reduce Kelly fraction as expiry approaches (less time to be right)
4. Fractional Kelly: configurable multiplier (0.5 = half-Kelly, safer)

Usage:
    from dynamic_kelly import DynamicKelly

    dk = DynamicKelly(bankroll_cents=10000, max_fraction=0.15)

    # Static bet sizing
    sizing = dk.compute_bet_sizing(true_prob=0.65, market_price=0.50)

    # With time decay
    sizing = dk.compute_bet_sizing(
        true_prob=0.65, market_price=0.50,
        minutes_remaining=5, total_window=15
    )

    # Bayesian update from new observation
    state = dk.update_belief(prior_prob=0.60, new_observation=0.65)
    sizing = dk.compute_bet_sizing(
        true_prob=state.posterior_prob, market_price=0.50
    )

Zero external dependencies. Stdlib only.
"""

import json
import math
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class BeliefState:
    """Current belief state after Bayesian updating."""
    prior_prob: float
    posterior_prob: float
    n_updates: int
    confidence: float  # 0-1, increases with more confirming observations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prior_prob": round(self.prior_prob, 4),
            "posterior_prob": round(self.posterior_prob, 4),
            "n_updates": self.n_updates,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class BetSizing:
    """Computed bet sizing recommendation."""
    kelly_fraction: float      # Fraction of bankroll to bet (0-1)
    bet_amount_cents: int      # Actual amount in cents
    edge: float                # true_prob - market_price
    market_price: float
    true_prob: float
    confidence: float          # Overall confidence in the sizing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kelly_fraction": round(self.kelly_fraction, 4),
            "bet_amount_cents": self.bet_amount_cents,
            "edge": round(self.edge, 4),
            "market_price": round(self.market_price, 4),
            "true_prob": round(self.true_prob, 4),
            "confidence": round(self.confidence, 4),
        }


class DynamicKelly:
    """
    Dynamic Kelly criterion with Bayesian updating and time decay.

    Computes optimal bet sizing that adjusts in real-time as new
    price data arrives and as expiry approaches.
    """

    # Minimum edge to consider betting
    MIN_EDGE = 0.0
    # Clamp for logit to avoid infinities
    LOGIT_CLAMP = 0.001

    def __init__(
        self,
        bankroll_cents: int = 50000,
        max_fraction: float = 0.25,
        kelly_multiplier: float = 1.0,
        min_bet_cents: int = 100,
    ):
        if bankroll_cents <= 0:
            raise ValueError(f"bankroll_cents must be > 0, got {bankroll_cents}")
        if not 0 < max_fraction <= 1.0:
            raise ValueError(f"max_fraction must be in (0, 1], got {max_fraction}")
        if kelly_multiplier <= 0:
            raise ValueError(f"kelly_multiplier must be > 0, got {kelly_multiplier}")

        self.bankroll_cents = bankroll_cents
        self.max_fraction = max_fraction
        self.kelly_multiplier = kelly_multiplier
        self.min_bet_cents = min_bet_cents

    def _clamp_prob(self, p: float) -> float:
        """Clamp probability to avoid log(0)."""
        return max(self.LOGIT_CLAMP, min(1 - self.LOGIT_CLAMP, p))

    def _logit(self, p: float) -> float:
        """Log-odds transform: logit(p) = log(p / (1-p))."""
        p = self._clamp_prob(p)
        return math.log(p / (1 - p))

    def _sigmoid(self, x: float) -> float:
        """Inverse logit: sigmoid(x) = 1 / (1 + exp(-x))."""
        if x > 500:
            return 1 - self.LOGIT_CLAMP
        if x < -500:
            return self.LOGIT_CLAMP
        return 1 / (1 + math.exp(-x))

    def kelly_fraction(
        self, true_prob: float, market_price: float
    ) -> float:
        """
        Compute Kelly fraction for a binary outcome bet.

        For a binary bet at market_price p_m with true probability p:
        - Payout odds b = (1/p_m) - 1  (e.g., p_m=0.50 -> b=1.0, even odds)
        - Kelly fraction f* = (p*b - (1-p)) / b
        - Simplified: f* = p - (1-p)/(b) = p - (1-p)*p_m/(1-p_m)

        Returns 0 if no positive edge exists.
        """
        if true_prob <= market_price:
            return 0.0

        # Avoid division by zero at extreme prices
        if market_price >= 1.0 or market_price <= 0.0:
            return 0.0

        # Payout odds: what you get per dollar risked if you win
        b = (1.0 / market_price) - 1.0

        if b <= 0:
            return 0.0

        # Kelly formula: f* = (p*b - q) / b where q = 1-p
        q = 1 - true_prob
        f = (true_prob * b - q) / b

        # Apply multiplier (fractional Kelly)
        f *= self.kelly_multiplier

        # Cap at max_fraction
        f = max(0, min(self.max_fraction, f))

        return round(f, 6)

    def update_belief(
        self,
        prior_prob: float,
        new_observation: float,
        observation_weight: float = 1.0,
    ) -> BeliefState:
        """
        Bayesian update of belief given a new price observation.

        Uses logit-space updating (per arXiv:2601.18815):
        - Convert prior and observation to logit space
        - Update: logit(posterior) = logit(prior) + weight * (logit(obs) - logit(prior))
        - Convert back to probability space

        This is more numerically stable than raw Bayes and handles
        the prediction market setting where observations are prices.
        """
        prior_logit = self._logit(prior_prob)
        obs_logit = self._logit(new_observation)

        # Weighted average in logit space
        # Weight controls how much we trust the new observation
        effective_weight = max(0, min(1, observation_weight)) * 0.5
        posterior_logit = prior_logit + effective_weight * (obs_logit - prior_logit)
        posterior_prob = self._sigmoid(posterior_logit)

        # Confidence based on agreement between prior and observation
        agreement = 1 - abs(prior_prob - new_observation)
        confidence = min(1.0, agreement)

        return BeliefState(
            prior_prob=round(prior_prob, 4),
            posterior_prob=round(posterior_prob, 4),
            n_updates=1,
            confidence=round(confidence, 4),
        )

    def time_decay_factor(
        self,
        minutes_remaining: float,
        total_window: float,
    ) -> float:
        """
        Time decay factor for Kelly fraction.

        As expiry approaches, reduce position size because:
        1. Less time for the market to move in your favor
        2. Higher variance in short-term outcomes
        3. Liquidity typically decreases near expiry

        Uses sqrt decay: factor = sqrt(remaining / total)
        This is more aggressive than linear but less than exponential,
        reflecting that early minutes are worth more than late ones.
        """
        if total_window <= 0:
            return 0.0
        if minutes_remaining <= 0:
            return 0.1  # Minimal floor, don't go to zero

        ratio = min(1.0, minutes_remaining / total_window)
        return math.sqrt(ratio)

    def compute_bet_sizing(
        self,
        true_prob: float,
        market_price: float,
        minutes_remaining: Optional[float] = None,
        total_window: float = 15.0,
    ) -> BetSizing:
        """
        Compute full bet sizing with optional time decay.

        Args:
            true_prob: Estimated true probability of the event
            market_price: Current market price (implied probability)
            minutes_remaining: Minutes until contract expiry (None = no decay)
            total_window: Total betting window in minutes (default 15)

        Returns:
            BetSizing with kelly_fraction, bet_amount, edge, and confidence
        """
        edge = true_prob - market_price
        f = self.kelly_fraction(true_prob, market_price)

        # Apply time decay if applicable
        if minutes_remaining is not None:
            decay = self.time_decay_factor(minutes_remaining, total_window)
            f *= decay

        # Compute bet amount
        bet_cents = int(f * self.bankroll_cents)
        bet_cents = max(0, min(bet_cents, self.bankroll_cents))

        # If below minimum bet, don't bet
        if 0 < bet_cents < self.min_bet_cents:
            bet_cents = 0
            f = 0

        # Confidence: higher with more edge and more time remaining
        edge_conf = min(1.0, abs(edge) / 0.20)  # Saturates at 20% edge
        time_conf = 1.0
        if minutes_remaining is not None:
            time_conf = min(1.0, minutes_remaining / total_window)
        confidence = (edge_conf + time_conf) / 2

        return BetSizing(
            kelly_fraction=round(f, 6),
            bet_amount_cents=bet_cents,
            edge=round(edge, 4),
            market_price=round(market_price, 4),
            true_prob=round(true_prob, 4),
            confidence=round(confidence, 4),
        )


def main():
    """CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(description="Dynamic Kelly Bet Sizing")
    sub = parser.add_subparsers(dest="command")

    # size
    size_p = sub.add_parser("size", help="Compute bet sizing")
    size_p.add_argument("--prob", type=float, required=True, help="True probability")
    size_p.add_argument("--price", type=float, required=True, help="Market price")
    size_p.add_argument("--bankroll", type=int, default=50000, help="Bankroll (cents)")
    size_p.add_argument("--remaining", type=float, help="Minutes remaining")
    size_p.add_argument("--window", type=float, default=15, help="Total window (min)")
    size_p.add_argument("--multiplier", type=float, default=1.0, help="Kelly multiplier")

    # update
    update_p = sub.add_parser("update", help="Bayesian belief update")
    update_p.add_argument("--prior", type=float, required=True, help="Prior probability")
    update_p.add_argument("--observation", type=float, required=True, help="New observation")
    update_p.add_argument("--weight", type=float, default=1.0, help="Observation weight")

    args = parser.parse_args()

    if args.command == "size":
        dk = DynamicKelly(
            bankroll_cents=args.bankroll,
            kelly_multiplier=args.multiplier,
        )
        sizing = dk.compute_bet_sizing(
            true_prob=args.prob,
            market_price=args.price,
            minutes_remaining=args.remaining,
            total_window=args.window,
        )
        print(json.dumps(sizing.to_dict(), indent=2))

    elif args.command == "update":
        dk = DynamicKelly()
        state = dk.update_belief(
            prior_prob=args.prior,
            new_observation=args.observation,
            observation_weight=args.weight,
        )
        print(json.dumps(state.to_dict(), indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
