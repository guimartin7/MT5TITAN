"""Transparent market-quality score."""
from dataclasses import dataclass

from mt5titan.domain import MarketRegime

from .features import FeatureSet
from .regime import RegimeAssessment


@dataclass(frozen=True)
class MarketScore:
    total: float
    trend: float
    momentum: float
    volatility: float
    liquidity: float
    reasons: tuple[str, ...]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_market(features: FeatureSet, regime: RegimeAssessment) -> MarketScore:
    trend = _clamp(abs(features.trend_gap_pct) * 250.0)
    momentum = _clamp(abs(features.momentum_pct) * 100.0)

    if regime.regime == MarketRegime.HIGH_VOLATILITY:
        volatility = 25.0
    elif regime.regime == MarketRegime.LOW_VOLATILITY:
        volatility = 45.0
    else:
        volatility = _clamp(100.0 - abs(features.realized_volatility_pct - 0.35) * 120.0)

    liquidity = 70.0
    reasons: list[str] = []
    if features.volume_ratio is not None:
        liquidity = _clamp(50.0 + (features.volume_ratio - 1.0) * 50.0)
    if features.spread_points is not None:
        liquidity = _clamp(liquidity - max(0.0, features.spread_points - 1.0) * 5.0)

    if regime.regime == MarketRegime.TRENDING:
        reasons.append("TREND_REGIME")
    elif regime.regime == MarketRegime.RANGING:
        reasons.append("RANGE_REGIME")
    elif regime.regime in {MarketRegime.HIGH_VOLATILITY, MarketRegime.LOW_VOLATILITY}:
        reasons.append("VOLATILITY_REGIME")

    total = (
        trend * 0.30
        + momentum * 0.25
        + volatility * 0.25
        + liquidity * 0.20
    )
    return MarketScore(
        total=round(_clamp(total), 2),
        trend=round(trend, 2),
        momentum=round(momentum, 2),
        volatility=round(volatility, 2),
        liquidity=round(liquidity, 2),
        reasons=tuple(reasons),
    )
