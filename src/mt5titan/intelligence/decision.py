"""Deterministic decision engine used before AI agents exist."""
from dataclasses import dataclass
import hashlib

from mt5titan.domain import Decision, DecisionAction, MarketRegime, Signal

from .regime import RegimeAssessment
from .score import MarketScore


@dataclass(frozen=True)
class DecisionPolicy:
    minimum_market_score: float = 45.0
    minimum_absolute_signal: float = 0.20
    minimum_confidence: float = 0.55


class DecisionEngine:
    def __init__(self, policy: DecisionPolicy | None = None):
        self.policy = policy or DecisionPolicy()

    def decide(
        self,
        *,
        symbol: str,
        timestamp: int,
        signals: list[Signal],
        regime: RegimeAssessment,
        market_score: MarketScore,
    ) -> Decision:
        if not signals:
            return self._hold(symbol, timestamp, "NO_SIGNALS", {}, 0.0)

        contributors: dict[str, float] = {}
        weighted = 0.0
        weight_sum = 0.0

        for signal in signals:
            signal.validate()
            regime_weight = self._regime_weight(signal.source, regime.regime)
            weight = max(0.01, signal.confidence * regime_weight)
            contributors[signal.source] = round(signal.score, 4)
            weighted += signal.score * weight
            weight_sum += weight

        score = weighted / weight_sum if weight_sum else 0.0
        confidence = min(1.0, sum(s.confidence for s in signals) / len(signals))

        if market_score.total < self.policy.minimum_market_score:
            return self._hold(symbol, timestamp, "MARKET_SCORE_TOO_LOW", contributors, score)
        if abs(score) < self.policy.minimum_absolute_signal:
            return self._hold(symbol, timestamp, "SIGNAL_TOO_WEAK", contributors, score)
        if confidence < self.policy.minimum_confidence:
            return self._hold(symbol, timestamp, "CONFIDENCE_TOO_LOW", contributors, score)

        action = DecisionAction.BUY if score > 0 else DecisionAction.SELL
        identifier = self._decision_id(symbol, timestamp, action.value)
        return Decision(
            decision_id=identifier,
            symbol=symbol,
            action=action,
            confidence=round(confidence, 4),
            score=round(score, 4),
            contributors=contributors,
            reason_codes=("DETERMINISTIC_ENSEMBLE", regime.regime.value),
            metadata={"market_score": market_score.total, "regime_confidence": regime.confidence},
        )

    @staticmethod
    def _regime_weight(source: str, regime: MarketRegime) -> float:
        source = source.lower()
        if regime == MarketRegime.TRENDING:
            return 1.25 if any(token in source for token in ("trend", "momentum", "breakout")) else 0.80
        if regime == MarketRegime.RANGING:
            return 1.25 if any(token in source for token in ("mean", "reversion", "rsi")) else 0.75
        if regime == MarketRegime.HIGH_VOLATILITY:
            return 0.60
        if regime == MarketRegime.LOW_VOLATILITY:
            return 0.75
        return 0.85

    def _hold(self, symbol, timestamp, reason, contributors, score) -> Decision:
        return Decision(
            decision_id=self._decision_id(symbol, timestamp, "HOLD"),
            symbol=symbol,
            action=DecisionAction.HOLD,
            confidence=0.0,
            score=round(score, 4),
            contributors=contributors,
            reason_codes=(reason,),
        )

    @staticmethod
    def _decision_id(symbol: str, timestamp: int, action: str) -> str:
        raw = f"{symbol}:{timestamp}:{action}".encode()
        return hashlib.sha256(raw).hexdigest()[:20]
