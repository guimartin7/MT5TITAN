"""In-memory paper broker for the web application."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class PaperTrade:
    trade_id: int
    symbol: str
    side: str
    stake: float
    entry_price: float
    created_at_utc: str


@dataclass
class PaperState:
    balance: float = 10_000.0
    open_trades: list[PaperTrade] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)


class PaperTradingBroker:
    name = "paper"
    execution_enabled = True

    def __init__(self, initial_balance: float = 10_000.0):
        self.state = PaperState(balance=float(initial_balance))
        self._next_id = 1

    def status(self) -> dict:
        return {
            "broker": self.name,
            "connected": True,
            "execution_enabled": True,
            "balance": round(self.state.balance, 2),
            "open_trades": len(self.state.open_trades),
        }

    def place_order(self, *, symbol: str, side: str, stake: float, price: float) -> dict:
        side = side.upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if stake <= 0:
            raise ValueError("stake must be positive")
        if price <= 0:
            raise ValueError("price must be positive")
        if stake > self.state.balance:
            raise ValueError("insufficient paper balance")

        trade = PaperTrade(
            trade_id=self._next_id,
            symbol=symbol,
            side=side,
            stake=float(stake),
            entry_price=float(price),
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        self._next_id += 1
        self.state.balance -= stake
        self.state.open_trades.append(trade)
        return asdict(trade)

    def settle(self, *, trade_id: int, exit_price: float, payout_ratio: float = 0.82) -> dict:
        if exit_price <= 0:
            raise ValueError("exit_price must be positive")
        trade = next((t for t in self.state.open_trades if t.trade_id == trade_id), None)
        if trade is None:
            raise ValueError("trade not found")

        won = exit_price > trade.entry_price if trade.side == "BUY" else exit_price < trade.entry_price
        returned = trade.stake * (1.0 + payout_ratio) if won else 0.0
        pnl = returned - trade.stake
        self.state.balance += returned
        self.state.open_trades.remove(trade)

        result = {
            **asdict(trade),
            "exit_price": float(exit_price),
            "won": won,
            "payout_ratio": payout_ratio,
            "pnl": round(pnl, 2),
            "settled_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        self.state.history.append(result)
        return result

    def snapshot(self) -> dict:
        return {
            "balance": round(self.state.balance, 2),
            "open_trades": [asdict(t) for t in self.state.open_trades],
            "history": list(self.state.history),
        }
