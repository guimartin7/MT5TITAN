import json

from mt5titan.marketdata.providers import TwelveDataMarketDataProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_twelve_data_normalizes_common_symbols():
    assert TwelveDataMarketDataProvider.normalize_symbol("EURUSD") == "EUR/USD"
    assert TwelveDataMarketDataProvider.normalize_symbol("BTCUSD") == "BTC/USD"
    assert TwelveDataMarketDataProvider.normalize_symbol("AAPL") == "AAPL"


def test_twelve_data_parses_time_series():
    values = []
    for index in range(40):
        values.append({
            "datetime": f"2026-09-24 12:{index:02d}:00",
            "open": "100",
            "high": "101",
            "low": "99",
            "close": str(100 + index / 100),
            "volume": "1000",
        })

    provider = TwelveDataMarketDataProvider(
        api_key="test",
        opener=lambda *args, **kwargs: FakeResponse({"status": "ok", "values": values}),
    )
    batch = provider.candles(symbol="EURUSD", timeframe="M1", count=40)

    assert batch.source == "twelve"
    assert batch.symbol == "EURUSD"
    assert len(batch.candles) == 40
    assert batch.candles[0]["time"] < batch.candles[-1]["time"]


def test_twelve_data_requires_key():
    provider = TwelveDataMarketDataProvider(api_key=None)
    provider.api_key = None
    try:
        provider.candles(symbol="EURUSD", timeframe="M5", count=40)
    except RuntimeError as error:
        assert "TWELVE_DATA_API_KEY" in str(error)
    else:
        raise AssertionError("expected RuntimeError")
