"""Typed contracts shared between research, risk and execution layers."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MarketRegime(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    EVENT = "EVENT"
    UNCERTAIN = "UNCERTAIN"


class DecisionAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    timeframe: str
    timestamp: int
    bid: float
    ask: float
    regime: MarketRegime = MarketRegime.UNCERTAIN
    features: dict[str, float | int | str | bool | None] = field(default_factory=dict)

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    def validate(self) -> None:
        if not self.symbol:
            raise ValueError("symbol is required")
        if self.timestamp <= 0:
            raise ValueError("timestamp must be positive")
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError("bid/ask must be positive")
        if self.ask < self.bid:
            raise ValueError("ask cannot be below bid")


@dataclass(frozen=True)
class Signal:
    source: str
    action: DecisionAction
    confidence: float
    score: float
    reasons: tuple[str, ...] = ()

    def validate(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not -1.0 <= self.score <= 1.0:
            raise ValueError("score must be between -1 and 1")


@dataclass(frozen=True)
class Decision:
    decision_id: str
    symbol: str
    action: DecisionAction
    confidence: float
    score: float
    contributors: dict[str, float] = field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.decision_id:
            raise ValueError("decision_id is required")
        if not self.symbol:
            raise ValueError("symbol is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not -1.0 <= self.score <= 1.0:
            raise ValueError("score must be between -1 and 1")


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()
    risk_fraction: float | None = None
