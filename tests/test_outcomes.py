from pathlib import Path

from mt5titan.storage import SQLiteStore


def analysis_report():
    return {
        "symbol": "DEMO",
        "timeframe": "M5",
        "source": "demo",
        "reference_price": 100.0,
        "regime": {"value": "TRENDING"},
        "market_score": {"total": 80.0},
        "decision": {
            "id": "decision-1",
            "action": "BUY",
            "confidence": 0.8,
            "score": 0.7,
        },
        "risk": {"allowed": True},
        "ai": {
            "enabled": True,
            "committee": {
                "action": "BUY",
                "confidence": 0.75,
                "score": 0.5,
                "reasons": [],
            },
            "agents": [
                {
                    "agent": "technical",
                    "verdict": "BUY",
                    "confidence": 0.8,
                    "score": 0.7,
                    "reason_codes": [],
                    "risk_flags": [],
                },
                {
                    "agent": "news",
                    "verdict": "HOLD",
                    "confidence": 0.6,
                    "score": 0.0,
                    "reason_codes": [],
                    "risk_flags": [],
                },
                {
                    "agent": "macro",
                    "verdict": "SELL",
                    "confidence": 0.7,
                    "score": -0.4,
                    "reason_codes": [],
                    "risk_flags": [],
                },
            ],
        },
    }


def test_outcome_statistics_track_regime_and_agents(tmp_path: Path):
    store = SQLiteStore(tmp_path / "outcomes.db")
    analysis_id = store.save_analysis(analysis_report(), "2026-09-24T00:00:00+00:00")

    store.save_outcome(
        analysis_id=analysis_id,
        evaluated_at_utc="2026-09-24T01:00:00+00:00",
        entry_price=100.0,
        exit_price=102.0,
        action="BUY",
        result="WIN",
        market_direction="BUY",
        directional_return_pct=2.0,
    )

    stats = store.outcome_statistics()

    assert stats["wins"] == 1
    assert stats["win_rate_pct"] == 100.0
    assert stats["by_regime"]["TRENDING"]["win_rate_pct"] == 100.0
    assert stats["agents"]["technical"]["accuracy_pct"] == 100.0
    assert stats["agents"]["macro"]["accuracy_pct"] == 0.0
    assert stats["agents"]["committee"]["accuracy_pct"] == 100.0
    assert "news" not in stats["agents"]


def test_outcome_upsert_is_idempotent(tmp_path: Path):
    store = SQLiteStore(tmp_path / "outcomes.db")
    analysis_id = store.save_analysis(analysis_report(), "2026-09-24T00:00:00+00:00")

    first = store.save_outcome(
        analysis_id=analysis_id,
        evaluated_at_utc="2026-09-24T01:00:00+00:00",
        entry_price=100.0,
        exit_price=99.0,
        action="BUY",
        result="LOSS",
        market_direction="SELL",
        directional_return_pct=-1.0,
    )
    second = store.save_outcome(
        analysis_id=analysis_id,
        evaluated_at_utc="2026-09-24T02:00:00+00:00",
        entry_price=100.0,
        exit_price=102.0,
        action="BUY",
        result="WIN",
        market_direction="BUY",
        directional_return_pct=2.0,
    )

    assert first["result"] == "LOSS"
    assert second["result"] == "WIN"
    assert len(store.recent_outcomes()) == 1
