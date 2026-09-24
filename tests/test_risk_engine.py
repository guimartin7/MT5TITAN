from mt5titan.domain import Decision, DecisionAction, MarketSnapshot
from mt5titan.risk import RiskEngine, RiskLimits, RiskState


def snapshot():
    return MarketSnapshot("WINV26", "M5", 1, 140000.0, 140005.0)


def decision(confidence=0.8):
    return Decision("d1", "WINV26", DecisionAction.BUY, confidence, 0.7)


def test_allows_clean_decision():
    engine = RiskEngine(RiskLimits(max_spread=10, min_confidence=0.5))
    result = engine.evaluate(decision(), snapshot(), RiskState())
    assert result.allowed
    assert not result.reasons


def test_kill_switch_is_sovereign():
    result = RiskEngine().evaluate(decision(), snapshot(), RiskState(kill_switch=True))
    assert not result.allowed
    assert "kill_switch_active" in result.reasons


def test_combines_multiple_blockers():
    engine = RiskEngine(RiskLimits(max_daily_loss_pct=1, max_entries_per_day=3))
    state = RiskState(daily_return_pct=-1.5, entries_today=3, feed_healthy=False)
    result = engine.evaluate(decision(), snapshot(), state)
    assert not result.allowed
    assert set(result.reasons) >= {"daily_loss_limit", "daily_entry_limit", "feed_unhealthy"}
