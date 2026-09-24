from pathlib import Path

from mt5titan.marketdata import DemoMarketDataProvider, StoredMarketDataProvider
from mt5titan.storage import SQLiteStore


def candles(count=40):
    rows = []
    price = 100.0
    for index in range(count):
        open_price = price
        price += 0.1
        rows.append({
            "time": 1_700_000_000 + index * 300,
            "open": open_price,
            "high": price + 0.05,
            "low": open_price - 0.05,
            "close": price,
            "spread": 0.01,
            "tick_volume": 100 + index,
        })
    return rows


def test_demo_market_data_is_deterministic():
    provider = DemoMarketDataProvider()
    first = provider.candles(symbol="EURUSD", timeframe="M5", count=40)
    second = provider.candles(symbol="EURUSD", timeframe="M5", count=40)
    assert first.candles == second.candles
    assert len(first.candles) == 40


def test_imported_market_data_survives_restart(tmp_path: Path):
    path = tmp_path / "market.db"
    store = SQLiteStore(path)
    store.replace_market_candles(symbol="EURUSD", timeframe="M5", candles=candles())

    restarted = SQLiteStore(path)
    batch = StoredMarketDataProvider(restarted).candles(
        symbol="EURUSD", timeframe="M5", count=35
    )

    assert batch.source == "stored"
    assert len(batch.candles) == 35
    assert batch.candles[-1]["time"] > batch.candles[0]["time"]


def test_watchlist_is_persistent(tmp_path: Path):
    path = tmp_path / "watch.db"
    store = SQLiteStore(path)
    store.add_watchlist(symbol="eurusd", timeframe="m5", source="stored")

    restarted = SQLiteStore(path)
    assert restarted.list_watchlist() == [
        {"symbol": "EURUSD", "timeframe": "M5", "source": "stored"}
    ]

    restarted.remove_watchlist(symbol="EURUSD", timeframe="M5", source="stored")
    assert restarted.list_watchlist() == []
