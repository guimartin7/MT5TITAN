"""Market-data sources independent from the execution broker."""
from __future__ import annotations

from dataclasses import dataclass

from mt5titan.storage import SQLiteStore


@dataclass(frozen=True)
class MarketDataBatch:
    source: str
    symbol: str
    timeframe: str
    candles: list[dict]


class DemoMarketDataProvider:
    name = "demo"

    def candles(self, *, symbol: str, timeframe: str, count: int = 140) -> MarketDataBatch:
        count = max(30, min(int(count), 1000))
        seconds = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600}.get(timeframe, 300)
        seed = sum(ord(ch) for ch in symbol.upper()) % 25
        price = 90.0 + seed
        rows = []

        for index in range(count):
            cycle = (index // 35) % 3
            drift = (
                0.22
                if cycle == 0
                else -0.16
                if cycle == 1
                else (0.04 if index % 2 == 0 else -0.04)
            )
            open_price = price
            price = max(10.0, price + drift)
            rows.append({
                "time": 1_700_000_000 + index * seconds,
                "open": round(open_price, 5),
                "high": round(max(open_price, price) + 0.08, 5),
                "low": round(min(open_price, price) - 0.08, 5),
                "close": round(price, 5),
                "spread": 0.01,
                "tick_volume": 100 + index,
            })

        return MarketDataBatch(self.name, symbol, timeframe, rows)


class StoredMarketDataProvider:
    name = "stored"

    def __init__(self, store: SQLiteStore):
        self.store = store

    def candles(self, *, symbol: str, timeframe: str, count: int = 140) -> MarketDataBatch:
        rows = self.store.load_market_candles(symbol=symbol, timeframe=timeframe, limit=count)
        if len(rows) < 30:
            raise ValueError("stored market data requires at least 30 candles")
        return MarketDataBatch(self.name, symbol, timeframe, rows)
