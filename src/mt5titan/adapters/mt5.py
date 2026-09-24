"""Thin MetaTrader 5 adapter.

The rest of MT5TITAN should depend on this interface instead of importing
MetaTrader5 directly.
"""
from dataclasses import asdict
from typing import Any

from mt5titan.domain import MarketSnapshot
from mt5titan.market import assess_feed


class MT5Adapter:
    def __init__(self, api: Any, terminal_path: str):
        self.api = api
        self.terminal_path = terminal_path
        self.connected = False

    def connect(self) -> None:
        if not self.api.initialize(self.terminal_path, timeout=15000):
            raise RuntimeError(f"MT5 connection failed: {self.api.last_error()}")
        self.connected = True

    def close(self) -> None:
        if self.connected:
            self.api.shutdown()
            self.connected = False

    def require_demo(self) -> Any:
        account = self.api.account_info()
        if account is None or account.trade_mode != self.api.ACCOUNT_TRADE_MODE_DEMO:
            raise RuntimeError("operation allowed only in Demo account")
        return account

    def select_symbol(self, symbol: str) -> None:
        if not self.api.symbol_select(symbol, True):
            raise RuntimeError(f"symbol unavailable: {symbol}")

    def closed_bars(self, symbol: str, timeframe: int, count: int):
        self.require_demo()
        self.select_symbol(symbol)
        bars = self.api.copy_rates_from_pos(symbol, timeframe, 1, count)
        if bars is None or len(bars) == 0:
            raise RuntimeError(f"no closed bars returned for {symbol}")
        return bars

    def market_snapshot(self, symbol: str, timeframe_name: str) -> tuple[MarketSnapshot, dict]:
        self.require_demo()
        self.select_symbol(symbol)
        tick = self.api.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"tick unavailable for {symbol}")
        health = assess_feed(tick.time, tick.bid, tick.ask)
        snapshot = MarketSnapshot(
            symbol=symbol,
            timeframe=timeframe_name,
            timestamp=int(tick.time),
            bid=float(tick.bid),
            ask=float(tick.ask),
            features={"feed_status": health.status},
        )
        snapshot.validate()
        return snapshot, asdict(health)
