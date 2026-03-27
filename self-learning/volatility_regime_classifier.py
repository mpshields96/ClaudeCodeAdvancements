"""volatility_regime_classifier.py — Market regime detection from bet outcomes.

Classifies current market conditions into LOW/NORMAL/HIGH volatility
regimes based on recent bet outcome distribution. Informs adaptive
strategy parameters (tighter stops in high vol, wider in low vol).

Completes the Kalshi analytical toolkit:
- loss_reduction_simulator: what avg_loss to target
- wr_cliff_analyzer: how close to the danger zone
- edge_decay_detector: is the edge changing
- bankroll_growth_planner: trajectory projection
- strategy_allocator: capital allocation
- volatility_regime_classifier: adaptive parameter selection (THIS)

Usage:
    from volatility_regime_classifier import VolatilityRegimeClassifier

    classifier = VolatilityRegimeClassifier()
    result = classifier.classify(pnl_values)
    print(result.regime)  # Regime.LOW, Regime.NORMAL, Regime.HIGH
    params = classifier.recommend_params(result.regime)
"""
import math
import statistics
from dataclasses import dataclass
from enum import Enum


class Regime(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass
class RegimeClassification:
    """Result of regime classification."""

    regime: Regime
    volatility: float  # std dev of P&L outcomes
    vol_percentile: float  # where current vol falls in historical context (0-1)
    loss_frequency: float  # fraction of bets that are losses
    avg_loss_magnitude: float  # average size of losses (positive number)
    confidence: float  # 0-1, how confident in the classification
    message: str

    def summary(self) -> str:
        return (
            f"Regime: {self.regime.value.upper()} | "
            f"Vol: {self.volatility:.2f} (p{self.vol_percentile:.0%}) | "
            f"Loss freq: {self.loss_frequency:.1%} | "
            f"Avg loss: ${self.avg_loss_magnitude:.2f} | "
            f"Confidence: {self.confidence:.0%}"
        )

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "volatility": round(self.volatility, 4),
            "vol_percentile": round(self.vol_percentile, 4),
            "loss_frequency": round(self.loss_frequency, 4),
            "avg_loss_magnitude": round(self.avg_loss_magnitude, 2),
            "confidence": round(self.confidence, 4),
            "message": self.message,
        }


@dataclass
class OutcomeWindow:
    """Statistics for a window of bet outcomes."""

    n_bets: int
    volatility: float
    mean_pnl: float
    loss_frequency: float
    avg_loss_magnitude: float
    max_loss: float

    @classmethod
    def from_pnl_values(cls, pnls: list[float]) -> "OutcomeWindow":
        if not pnls:
            return cls(0, 0.0, 0.0, 0.0, 0.0, 0.0)

        losses = [p for p in pnls if p <= 0]
        return cls(
            n_bets=len(pnls),
            volatility=statistics.stdev(pnls) if len(pnls) >= 2 else 0.0,
            mean_pnl=statistics.mean(pnls),
            loss_frequency=len(losses) / len(pnls),
            avg_loss_magnitude=abs(statistics.mean(losses)) if losses else 0.0,
            max_loss=abs(min(pnls)),
        )

    def to_dict(self) -> dict:
        return {
            "n_bets": self.n_bets,
            "volatility": round(self.volatility, 4),
            "mean_pnl": round(self.mean_pnl, 4),
            "loss_frequency": round(self.loss_frequency, 4),
            "avg_loss_magnitude": round(self.avg_loss_magnitude, 2),
            "max_loss": round(self.max_loss, 2),
        }


class VolatilityRegimeClassifier:
    """Classifies market regime from recent bet outcomes."""

    # Default thresholds (calibrated to sniper strategy)
    LOW_VOL_PERCENTILE = 0.25
    HIGH_VOL_PERCENTILE = 0.75
    MIN_BETS_FOR_CONFIDENCE = 30

    def __init__(self, window_size: int = 50):
        self.window_size = window_size

    def classify(self, pnl_values: list[float]) -> RegimeClassification:
        """Classify current regime from P&L values."""
        if len(pnl_values) < 3:
            return RegimeClassification(
                regime=Regime.NORMAL,
                volatility=0.0,
                vol_percentile=0.50,
                loss_frequency=0.0,
                avg_loss_magnitude=0.0,
                confidence=0.1,
                message="Insufficient data for regime classification",
            )

        window = OutcomeWindow.from_pnl_values(pnl_values)

        # Compute rolling volatilities for percentile ranking
        rolling_vols = self._rolling_volatilities(pnl_values)
        current_vol = window.volatility

        # Percentile of current vol within rolling history
        if rolling_vols:
            below = sum(1 for v in rolling_vols if v <= current_vol)
            vol_percentile = below / len(rolling_vols)
        else:
            vol_percentile = 0.50

        # Classify based on volatility percentile + loss frequency
        # Zero volatility is always LOW (no variance = no risk)
        if current_vol == 0.0 or (vol_percentile <= self.LOW_VOL_PERCENTILE and window.loss_frequency < 0.05):
            regime = Regime.LOW
            message = (
                f"Low volatility: vol p{vol_percentile:.0%},"
                f" loss freq {window.loss_frequency:.1%}"
            )
        elif vol_percentile >= self.HIGH_VOL_PERCENTILE or window.loss_frequency > 0.12:
            regime = Regime.HIGH
            message = (
                f"High volatility: vol p{vol_percentile:.0%},"
                f" loss freq {window.loss_frequency:.1%}"
            )
        else:
            regime = Regime.NORMAL
            message = (
                f"Normal volatility: vol p{vol_percentile:.0%},"
                f" loss freq {window.loss_frequency:.1%}"
            )

        # Confidence scales with sample size
        confidence = min(1.0, len(pnl_values) / self.MIN_BETS_FOR_CONFIDENCE)

        return RegimeClassification(
            regime=regime,
            volatility=current_vol,
            vol_percentile=vol_percentile,
            loss_frequency=window.loss_frequency,
            avg_loss_magnitude=window.avg_loss_magnitude,
            confidence=confidence,
            message=message,
        )

    def _rolling_volatilities(self, pnl_values: list[float]) -> list[float]:
        """Compute rolling volatilities for percentile context."""
        if len(pnl_values) < self.window_size:
            return []
        vols = []
        for i in range(0, len(pnl_values) - self.window_size + 1, self.window_size // 2):
            chunk = pnl_values[i : i + self.window_size]
            if len(chunk) >= 2:
                vols.append(statistics.stdev(chunk))
        return vols

    def rolling_classify(self, pnl_values: list[float]) -> list[RegimeClassification]:
        """Classify regimes over rolling windows."""
        results = []
        step = self.window_size // 2
        for i in range(0, len(pnl_values) - self.window_size + 1, step):
            chunk = pnl_values[i : i + self.window_size]
            result = self.classify(chunk)
            results.append(result)
        return results

    def recommend_params(self, regime: Regime) -> dict:
        """Recommend strategy parameters for a given regime."""
        params = {
            Regime.LOW: {
                "max_loss": 10.0,
                "volume_adjustment": 1.0,
                "entry_threshold": 0.90,
                "rationale": (
                    "Low vol: wider stops OK (fewer false exits),"
                    " normal volume, standard entry threshold"
                ),
            },
            Regime.NORMAL: {
                "max_loss": 8.0,
                "volume_adjustment": 1.0,
                "entry_threshold": 0.91,
                "rationale": (
                    "Normal vol: moderate stops ($8 cap),"
                    " normal volume, slightly tighter entries"
                ),
            },
            Regime.HIGH: {
                "max_loss": 6.0,
                "volume_adjustment": 0.75,
                "entry_threshold": 0.93,
                "rationale": (
                    "High vol: tight stops ($6 cap), reduced volume (75%),"
                    " only highest-confidence entries (93c+)"
                ),
            },
        }
        return params[regime]

    def full_report(self, pnl_values: list[float]) -> dict:
        """Complete regime analysis report."""
        current = self.classify(pnl_values)
        window = OutcomeWindow.from_pnl_values(pnl_values)
        recommendations = self.recommend_params(current.regime)
        rolling = self.rolling_classify(pnl_values)

        regime_counts = {r.value: 0 for r in Regime}
        for r in rolling:
            regime_counts[r.regime.value] += 1

        return {
            "current_regime": current.to_dict(),
            "recommendations": recommendations,
            "window_stats": window.to_dict(),
            "rolling_regime_distribution": regime_counts,
            "n_outcomes": len(pnl_values),
        }
