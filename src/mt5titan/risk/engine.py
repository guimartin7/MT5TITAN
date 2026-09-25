"""Central risk gate.

This module never sends orders. It only decides whether a new exposure is allowed.
"""
from dataclasses import dataclass

from mt5titan.domain import Decision, DecisionAction, MarketSnapshot, RiskDecision


@dataclass(frozen=True)
class RiskLimits:
    max_daily_loss_pct: float = 1.0
    max_drawdown_pct: float = 2.0
    max_entries_per_day: int = 5
    max_open_trades: int = 3
    max_stake_pct: float = 10.0
    max_spread: float | None = None
    min_confidence: float = 0.0


@dataclass
class RiskState:
    daily_return_pct: float = 0.0
    drawdown_pct: float = 0.0
    entries_today: int = 0
    open_trades: int = 0
    stake_pct_of_balance: float = 0.0
    kill_switch: bool = False
    feed_healthy: bool = True
    conflicting_exposure: bool = False


class RiskEngine:
    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()

    def evaluate(self, decision: Decision, snapshot: MarketSnapshot, state: RiskState) -> RiskDecision:
        decision.validate()
        snapshot.validate()

        if decision.action == DecisionAction.HOLD:
            return RiskDecision(False, ("no_new_exposure_for_hold",))

        reasons: list[str] = []

        if state.kill_switch:
            reasons.append("kill_switch_active")
        if not state.feed_healthy:
            reasons.append("feed_unhealthy")
        if state.conflicting_exposure:
            reasons.append("conflicting_exposure")
        if state.daily_return_pct <= -self.limits.max_daily_loss_pct:
            reasons.append("daily_loss_limit")
        if state.drawdown_pct <= -self.limits.max_drawdown_pct:
            reasons.append("drawdown_limit")
        if state.entries_today >= self.limits.max_entries_per_day:
            reasons.append("daily_entry_limit")
        if state.open_trades >= self.limits.max_open_trades:
            reasons.append("max_open_trades")
        if state.stake_pct_of_balance > self.limits.max_stake_pct:
            reasons.append("stake_above_limit")
        if decision.confidence < self.limits.min_confidence:
            reasons.append("confidence_below_minimum")
        if self.limits.max_spread is not None and snapshot.spread > self.limits.max_spread:
            reasons.append("spread_above_limit")

        return RiskDecision(allowed=not reasons, reasons=tuple(dict.fromkeys(reasons)))
