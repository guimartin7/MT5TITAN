"""Persistent paper broker for the web application."""
from datetime import datetime, timezone

from mt5titan.storage import SQLiteStore


class PaperTradingBroker:
    name = "paper"
    execution_enabled = True

    def __init__(self, initial_balance: float = 10_000.0, store: SQLiteStore | None = None):
        self.store = store or SQLiteStore()
        self.initial_balance = float(initial_balance)
        current = self.store.get_state_float("paper_balance", self.initial_balance)
        self.store.set_state("paper_balance", current)

    @property
    def balance(self) -> float:
        return self.store.get_state_float("paper_balance", self.initial_balance)

    def _set_balance(self, value: float) -> None:
        self.store.set_state("paper_balance", round(value, 10))

    def status(self) -> dict:
        snapshot = self.store.paper_snapshot()
        return {
            "broker": self.name,
            "connected": True,
            "execution_enabled": True,
            "balance": round(self.balance, 2),
            "open_trades": len(snapshot["open_trades"]),
        }

    def place_order(self, *, symbol: str, side: str, stake: float, price: float) -> dict:
        side = side.upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if stake <= 0:
            raise ValueError("stake must be positive")
        if price <= 0:
            raise ValueError("price must be positive")
        if stake > self.balance:
            raise ValueError("insufficient paper balance")

        now = datetime.now(timezone.utc).isoformat()
        trade = self.store.create_paper_trade(
            symbol=symbol,
            side=side,
            stake=float(stake),
            entry_price=float(price),
            created_at_utc=now,
        )
        self._set_balance(self.balance - float(stake))
        return trade

    def settle(self, *, trade_id: int, exit_price: float, payout_ratio: float = 0.82) -> dict:
        if exit_price <= 0:
            raise ValueError("exit_price must be positive")

        trade = self.store.get_paper_trade(trade_id)
        if trade["status"] != "OPEN":
            raise ValueError("trade already settled")

        won = exit_price > trade["entry_price"] if trade["side"] == "BUY" else exit_price < trade["entry_price"]
        returned = trade["stake"] * (1.0 + payout_ratio) if won else 0.0
        pnl = returned - trade["stake"]
        self._set_balance(self.balance + returned)

        return self.store.settle_paper_trade(
            trade_id=trade_id,
            exit_price=float(exit_price),
            payout_ratio=float(payout_ratio),
            won=won,
            pnl=round(pnl, 2),
            settled_at_utc=datetime.now(timezone.utc).isoformat(),
        )

    def reset(self, balance: float | None = None) -> dict:
        value = self.initial_balance if balance is None else float(balance)
        if value <= 0:
            raise ValueError("balance must be positive")
        self._set_balance(value)
        return self.snapshot()

    def snapshot(self) -> dict:
        snapshot = self.store.paper_snapshot()
        return {
            "balance": round(self.balance, 2),
            **snapshot,
        }
