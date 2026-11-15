"""Research strategies for the offline paper desk (worker C).

Paper and offline only. Every number these modules produce is simulated.
Entry point for the session runner: ``from strategies.registry import STRATEGIES``.
Each value is ``decide(bars_so_far, position, cfg) -> Decision``.
"""
