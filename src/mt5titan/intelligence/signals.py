"""Translate research strategies into normalized Signals."""
from mt5titan.domain import DecisionAction, Signal
from mt5titan.research.strategies import StrategySpec, build_directions


def strategy_signal(bars, spec: StrategySpec, *, source: str | None = None) -> Signal:
    directions = build_directions(bars, spec)
    direction = int(directions[-1])
    action = (
        DecisionAction.BUY
        if direction > 0
        else DecisionAction.SELL
        if direction < 0
        else DecisionAction.HOLD
    )

    score = float(direction)
    confidence = 0.65 if direction else 0.30
    return Signal(
        source=source or spec.name,
        action=action,
        confidence=confidence,
        score=score,
        reasons=(f"STRATEGY:{spec.name}",),
    )
