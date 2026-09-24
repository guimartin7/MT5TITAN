from datetime import datetime, timedelta, timezone

from mt5titan.intelligence.calendar import EconomicEvent, classify_event_risk
from mt5titan.intelligence.portfolio import close_correlation, evaluate_portfolio_exposure


def test_close_correlation_detects_similar_series():
    a = [100, 101, 102, 103, 104, 105]
    b = [200, 202, 204, 206, 208, 210]
    value = close_correlation(a, b)
    assert value is not None
    assert value > 0.99


def test_correlated_same_direction_can_block():
    result = evaluate_portfolio_exposure(
        candidate_symbol="WIN",
        candidate_direction=1,
        open_positions=[
            {"symbol": "IND", "direction": 1},
            {"symbol": "IBOV", "direction": 1},
        ],
        correlations={
            ("WIN", "IND"): 0.9,
            ("WIN", "IBOV"): 0.85,
        },
    )
    assert not result["allowed"]
    assert "correlated_directional_exposure" in result["blockers"]


def test_high_impact_event_blocks_near_window():
    now = datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc)
    event = EconomicEvent(
        "fed-1",
        "USD",
        "Fed decision",
        now + timedelta(minutes=20),
        "HIGH",
    )
    risk = classify_event_risk([event], currencies={"USD"}, now=now)
    assert risk["blocked"]
    assert risk["reason"] == "HIGH_IMPACT_EVENT_NEAR"


def test_unrelated_currency_is_ignored():
    now = datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc)
    event = EconomicEvent(
        "ecb-1",
        "EUR",
        "ECB",
        now + timedelta(minutes=5),
        "HIGH",
    )
    risk = classify_event_risk([event], currencies={"USD"}, now=now)
    assert not risk["blocked"]
    assert risk["relevant_events"] == []
