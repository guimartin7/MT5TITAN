import json
from types import SimpleNamespace

import pytest

from mt5titan.titan.models import AGENT_RESPONSE_SCHEMA, AgentContext
from mt5titan.titan.providers.openai import OpenAIProvider


class FakeResponses:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text):
        self.responses = FakeResponses(output_text)


def context():
    return AgentContext(
        symbol="WINV26",
        timeframe="M5",
        timestamp=123,
        regime="TRENDING",
        market_score=70.0,
        features={"rsi": 55.0},
        strategy_signals={"trend": 0.8},
    )


def test_openai_provider_uses_strict_json_schema():
    payload = {
        "verdict": "BUY",
        "confidence": 0.8,
        "score": 0.7,
        "reason_codes": ["TREND"],
        "risk_flags": [],
    }
    client = FakeClient(json.dumps(payload))
    provider = OpenAIProvider(model="test-model", client=client)

    result = provider.structured_decision(
        agent_name="technical",
        system_instruction="test",
        context=context(),
        schema=AGENT_RESPONSE_SCHEMA,
    )

    assert result == payload
    call = client.responses.calls[0]
    assert call["model"] == "test-model"
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True
    assert call["text"]["format"]["schema"] == AGENT_RESPONSE_SCHEMA


def test_provider_rejects_invalid_json_text():
    provider = OpenAIProvider(model="test-model", client=FakeClient("not json"))
    with pytest.raises(RuntimeError, match="valid JSON"):
        provider.structured_decision(
            agent_name="technical",
            system_instruction="test",
            context=context(),
            schema=AGENT_RESPONSE_SCHEMA,
        )


def test_model_must_be_configured(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_MODEL"):
        OpenAIProvider(client=FakeClient("{}"))
