"""Strict contracts for model-assisted decisions."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentVerdict(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    VETO = "VETO"


@dataclass(frozen=True)
class AgentContext:
    symbol: str
    timeframe: str
    timestamp: int
    regime: str
    market_score: float
    features: dict[str, Any] = field(default_factory=dict)
    strategy_signals: dict[str, float] = field(default_factory=dict)
    event_risk: dict[str, Any] = field(default_factory=dict)
    portfolio: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "market_score": self.market_score,
            "features": self.features,
            "strategy_signals": self.strategy_signals,
            "event_risk": self.event_risk,
            "portfolio": self.portfolio,
        }


@dataclass(frozen=True)
class AgentOpinion:
    agent: str
    verdict: AgentVerdict
    confidence: float
    score: float
    reason_codes: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.agent:
            raise ValueError("agent is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not -1.0 <= self.score <= 1.0:
            raise ValueError("score must be between -1 and 1")
        if self.verdict == AgentVerdict.BUY and self.score <= 0:
            raise ValueError("BUY requires positive score")
        if self.verdict == AgentVerdict.SELL and self.score >= 0:
            raise ValueError("SELL requires negative score")


AGENT_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "confidence", "score", "reason_codes", "risk_flags"],
    "properties": {
        "verdict": {"type": "string", "enum": ["BUY", "SELL", "HOLD", "VETO"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "score": {"type": "number", "minimum": -1, "maximum": 1},
        "reason_codes": {"type": "array", "items": {"type": "string"}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
    },
}
