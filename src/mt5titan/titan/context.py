"""Build the exact, auditable context sent to model agents."""
from dataclasses import asdict

from mt5titan.intelligence.features import FeatureSet
from mt5titan.intelligence.regime import RegimeAssessment
from mt5titan.intelligence.score import MarketScore

from .models import AgentContext


def build_agent_context(
    *,
    symbol: str,
    timeframe: str,
    timestamp: int,
    features: FeatureSet,
    regime: RegimeAssessment,
    market_score: MarketScore,
    strategy_signals: dict[str, float],
    event_risk: dict | None = None,
    portfolio: dict | None = None,
) -> AgentContext:
    if timestamp <= 0:
        raise ValueError("timestamp must be positive")
    return AgentContext(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        regime=regime.regime.value,
        market_score=market_score.total,
        features=asdict(features),
        strategy_signals={str(k): float(v) for k, v in strategy_signals.items()},
        event_risk=dict(event_risk or {}),
        portfolio=dict(portfolio or {}),
    )
