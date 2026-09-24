import pytest

from mt5titan.domain import DecisionAction
from mt5titan.titan import AICommittee, AgentContext, AgentOpinion, AgentVerdict, NewsAgent, TechnicalAgent


class FakeProvider:
    def __init__(self, responses):
        self.responses = responses

    def structured_decision(self, *, agent_name, system_instruction, context, schema):
        return self.responses[agent_name]


def context():
    return AgentContext(
        symbol="WINV26",
        timeframe="M5",
        timestamp=123,
        regime="TRENDING",
        market_score=72.0,
        features={"rsi": 58},
        strategy_signals={"trend": 0.8},
    )


def test_agent_parses_structured_response():
    provider = FakeProvider({
        "technical": {
            "verdict": "BUY",
            "confidence": 0.8,
            "score": 0.7,
            "reason_codes": ["TREND_CONFIRMATION"],
            "risk_flags": [],
        }
    })
    opinion = TechnicalAgent(provider).evaluate(context())
    assert opinion.verdict == AgentVerdict.BUY
    assert opinion.score == 0.7


def test_invalid_agent_score_is_rejected():
    provider = FakeProvider({
        "technical": {
            "verdict": "BUY",
            "confidence": 0.8,
            "score": -0.2,
            "reason_codes": [],
            "risk_flags": [],
        }
    })
    with pytest.raises(ValueError):
        TechnicalAgent(provider).evaluate(context())


def test_committee_combines_agents():
    opinions = [
        AgentOpinion("technical", AgentVerdict.BUY, 0.8, 0.8),
        AgentOpinion("news", AgentVerdict.HOLD, 0.6, 0.0),
        AgentOpinion("macro", AgentVerdict.BUY, 0.7, 0.4),
    ]
    signal = AICommittee().aggregate(opinions)
    assert signal.action == DecisionAction.BUY
    assert signal.score > 0


def test_news_veto_is_absolute():
    opinions = [
        AgentOpinion("technical", AgentVerdict.BUY, 0.95, 0.9),
        AgentOpinion(
            "news",
            AgentVerdict.VETO,
            0.9,
            0.0,
            risk_flags=("HIGH_IMPACT_EVENT_NEAR",),
        ),
    ]
    signal = AICommittee().aggregate(opinions)
    assert signal.action == DecisionAction.HOLD
    assert signal.confidence == 1.0
    assert "HIGH_IMPACT_EVENT_NEAR" in signal.reasons
