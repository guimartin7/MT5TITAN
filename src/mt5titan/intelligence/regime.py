"""Deterministic market-regime detector."""
from dataclasses import dataclass

from mt5titan.domain import MarketRegime

from .features import FeatureSet


@dataclass(frozen=True)
class RegimeAssessment:
    regime: MarketRegime
    confidence: float
    reasons: tuple[str, ...]


def detect_regime(features: FeatureSet) -> RegimeAssessment:
    reasons: list[str] = []
    gap = abs(features.trend_gap_pct)
    vol = features.realized_volatility_pct
    momentum = abs(features.momentum_pct)

    if vol >= 1.20 or features.average_range_pct >= 1.50:
        reasons.append("VOLATILITY_EXTREME")
        return RegimeAssessment(MarketRegime.HIGH_VOLATILITY, 0.85, tuple(reasons))

    if vol <= 0.05 and features.average_range_pct <= 0.10:
        reasons.append("VOLATILITY_COMPRESSED")
        return RegimeAssessment(MarketRegime.LOW_VOLATILITY, 0.80, tuple(reasons))

    if gap >= 0.15 and momentum >= 0.20:
        reasons.extend(("MA_SEPARATION", "MOMENTUM_CONFIRMATION"))
        confidence = min(0.95, 0.60 + gap + momentum / 4.0)
        return RegimeAssessment(MarketRegime.TRENDING, confidence, tuple(reasons))

    if gap <= 0.08 and 35.0 <= features.rsi <= 65.0:
        reasons.extend(("MA_COMPRESSION", "RSI_NEUTRAL"))
        return RegimeAssessment(MarketRegime.RANGING, 0.72, tuple(reasons))

    reasons.append("MIXED_SIGNALS")
    return RegimeAssessment(MarketRegime.UNCERTAIN, 0.45, tuple(reasons))
