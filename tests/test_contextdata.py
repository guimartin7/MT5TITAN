import json

from mt5titan.contextdata.providers import FredMacroProvider, GdeltNewsProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_gdelt_context_extracts_headlines_and_impact():
    payload = {
        "articles": [
            {
                "title": "Federal Reserve interest rate decision moves markets",
                "domain": "example.com",
                "sourcecountry": "United States",
                "seendate": "20260924T120000Z",
                "url": "https://example.com/a",
            },
            {
                "title": "Bitcoin market update",
                "domain": "example.org",
                "sourcecountry": "United States",
                "seendate": "20260924T121000Z",
                "url": "https://example.org/b",
            },
        ]
    }
    provider = GdeltNewsProvider(
        opener=lambda *args, **kwargs: FakeResponse(payload)
    )
    context = provider.context(symbol="BTCUSD")
    assert context["available"] is True
    assert context["article_count"] == 2
    assert context["high_impact_hits"] >= 1
    assert context["risk_level"] in {"MEDIUM", "HIGH"}


def test_fred_context_is_optional_without_key():
    provider = FredMacroProvider(api_key=None)
    provider.api_key = None
    context = provider.context()
    assert context["available"] is False
    assert context["reason"] == "FRED_API_KEY_NOT_CONFIGURED"


def test_fred_context_parses_series():
    payload = {
        "observations": [
            {"date": "2026-09-24", "value": "4.25"},
            {"date": "2026-09-23", "value": "4.20"},
        ]
    }
    provider = FredMacroProvider(
        api_key="test",
        opener=lambda *args, **kwargs: FakeResponse(payload),
    )
    context = provider.context()
    assert context["available"] is True
    assert context["series"]["fed_funds"]["value"] == 4.25
    assert context["series"]["fed_funds"]["change"] == 0.05
