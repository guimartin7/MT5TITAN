from pathlib import Path

from mt5titan.titan import AgentContext, OpinionReplayStore
from mt5titan.titan.experiment import TitanExperiment


class FakeProvider:
    def structured_decision(self, *, agent_name, system_instruction, context, schema):
        if agent_name == "news":
            return {
                "verdict": "HOLD",
                "confidence": 0.7,
                "score": 0.0,
                "reason_codes": ["NO_NEWS_EDGE"],
                "risk_flags": [],
            }
        return {
            "verdict": "BUY",
            "confidence": 0.8,
            "score": 0.6,
            "reason_codes": ["CONFIRM"],
            "risk_flags": [],
        }


def test_experiment_persists_all_agent_opinions(tmp_path: Path):
    path = tmp_path / "replay.jsonl"
    store = OpinionReplayStore(path)
    experiment = TitanExperiment(FakeProvider(), store)
    context = AgentContext(
        symbol="WINV26",
        timeframe="M5",
        timestamp=123,
        regime="TRENDING",
        market_score=70.0,
        features={},
        strategy_signals={"trend": 1.0},
    )
    result = experiment.run_context(key="WINV26:M5:123", context=context)

    assert len(result.opinions) == 3
    loaded = store.load()
    assert "WINV26:M5:123" in loaded
    assert len(loaded["WINV26:M5:123"]["opinions"]) == 3
