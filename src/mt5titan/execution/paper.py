"""Broker-independent paper execution engine."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from mt5titan.domain import Decision, DecisionAction, MarketSnapshot, RiskDecision


@dataclass
class PaperPosition:
    symbol: str
    direction: int
    units: float
    entry_price: float
    opened_at: int


@dataclass
class PaperAccount:
    cash: float = 10_000.0
    equity: float = 10_000.0
    position: PaperPosition | None = None
    trades: list[dict] = field(default_factory=list)
    entries_today: int = 0


class PaperBroker:
    def __init__(self, account: PaperAccount | None = None, cost_bps: float = 0.0):
        if cost_bps < 0:
            raise ValueError("cost_bps cannot be negative")
        self.account = account or PaperAccount()
        self.cost_bps = cost_bps

    def mark_to_market(self, snapshot: MarketSnapshot) -> float:
        snapshot.validate()
        position = self.account.position
        if position is None:
            self.account.equity = self.account.cash
            return self.account.equity

        mark = snapshot.bid if position.direction == 1 else snapshot.ask
        pnl = (mark - position.entry_price) * position.direction * position.units
        self.account.equity = self.account.cash + pnl
        return self.account.equity

    def execute(
        self,
        decision: Decision,
        risk: RiskDecision,
        snapshot: MarketSnapshot,
        *,
        units: float = 1.0,
    ) -> dict:
        decision.validate()
        snapshot.validate()
        if not risk.allowed:
            return {"action": "RISK_BLOCK", "reasons": list(risk.reasons)}

        if units <= 0:
            raise ValueError("units must be positive")

        current = self.account.position

        if decision.action == DecisionAction.HOLD:
            self.mark_to_market(snapshot)
            return {"action": "HOLD"}

        direction = 1 if decision.action == DecisionAction.BUY else -1

        if current is not None:
            if current.direction == direction:
                self.mark_to_market(snapshot)
                return {"action": "ALREADY_POSITIONED"}
            closed = self.close(snapshot)
            return {"action": "CLOSE_OPPOSITE", "closed": closed}

        fee = self.cost_bps / 10_000
        raw_price = snapshot.ask if direction == 1 else snapshot.bid
        price = raw_price * (1 + fee if direction == 1 else 1 - fee)
        self.account.position = PaperPosition(
            symbol=snapshot.symbol,
            direction=direction,
            units=units,
            entry_price=price,
            opened_at=snapshot.timestamp,
        )
        self.account.entries_today += 1
        self.mark_to_market(snapshot)
        event = {
            "action": "PAPER_BUY" if direction == 1 else "PAPER_SELL",
            "decision_id": decision.decision_id,
            "symbol": snapshot.symbol,
            "price": price,
            "units": units,
            "timestamp": snapshot.timestamp,
        }
        self.account.trades.append(event)
        return event

    def close(self, snapshot: MarketSnapshot) -> dict:
        position = self.account.position
        if position is None:
            return {"action": "NO_POSITION"}

        fee = self.cost_bps / 10_000
        raw_price = snapshot.bid if position.direction == 1 else snapshot.ask
        exit_price = raw_price * (1 - fee if position.direction == 1 else 1 + fee)
        pnl = (exit_price - position.entry_price) * position.direction * position.units
        self.account.cash += pnl
        self.account.position = None
        self.account.equity = self.account.cash

        event = {
            "action": "PAPER_CLOSE",
            "symbol": position.symbol,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "closed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        self.account.trades.append(event)
        return event
