"""Market-data sources independent from the execution broker."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from urllib.parse import urlencode
from urllib.request import urlopen

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



class TwelveDataMarketDataProvider:
    """Official Twelve Data REST market-data adapter."""

    name = "twelve"

    def __init__(self, api_key: str | None = None, opener=None):
        self.api_key = api_key or os.getenv("TWELVE_DATA_API_KEY")
        self._opener = opener or urlopen

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        raw = symbol.strip().upper()
        if "/" in raw or ":" in raw:
            return raw
        if len(raw) == 6 and raw.isalpha():
            return f"{raw[:3]}/{raw[3:]}"
        return raw

    @staticmethod
    def _interval(timeframe: str) -> str:
        mapping = {
            "M1": "1min",
            "M5": "5min",
            "M15": "15min",
            "H1": "1h",
        }
        try:
            return mapping[timeframe.upper()]
        except KeyError as error:
            raise ValueError(f"unsupported Twelve Data timeframe: {timeframe}") from error

    @staticmethod
    def _timestamp(value: str) -> int:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())

    def candles(self, *, symbol: str, timeframe: str, count: int = 140) -> MarketDataBatch:
        if not self.api_key:
            raise RuntimeError("TWELVE_DATA_API_KEY is required for real market data")

        count = max(30, min(int(count), 5000))
        normalized = self.normalize_symbol(symbol)
        query = urlencode({
            "symbol": normalized,
            "interval": self._interval(timeframe),
            "outputsize": count,
            "timezone": "UTC",
            "order": "ASC",
            "format": "JSON",
            "apikey": self.api_key,
        })
        url = f"https://api.twelvedata.com/time_series?{query}"

        try:
            with self._opener(url, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise RuntimeError(f"Twelve Data request failed: {error}") from error

        if payload.get("status") == "error":
            message = payload.get("message") or payload.get("code") or "unknown error"
            raise RuntimeError(f"Twelve Data error: {message}")

        values = payload.get("values")
        if not isinstance(values, list) or len(values) < 30:
            raise ValueError("Twelve Data returned fewer than 30 candles")

        rows = []
        for item in values:
            rows.append({
                "time": self._timestamp(str(item["datetime"])),
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "spread": 0.0,
                "tick_volume": float(item.get("volume") or 0.0),
            })

        rows.sort(key=lambda row: row["time"])
        return MarketDataBatch(self.name, symbol.strip().upper(), timeframe.upper(), rows)
