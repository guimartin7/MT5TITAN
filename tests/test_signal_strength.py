from mt5titan.intelligence.signals import strategy_signal
from mt5titan.research import StrategySpec


def trending_bars(step: float, count: int = 80):
    price = 100.0
    rows = []
    for index in range(count):
        open_price = price
        price += step
        rows.append({
            "time": 1_700_000_000 + index * 300,
            "open": open_price,
            "high": max(open_price, price) + abs(step) * 0.2 + 0.01,
            "low": min(open_price, price) - abs(step) * 0.2 - 0.01,
            "close": price,
            "spread": 0.01,
            "tick_volume": 100 + index,
        })
    return rows


def test_sma_confidence_changes_with_signal_strength():
    spec = StrategySpec("sma_trend", {"fast": 9, "slow": 21})
    weak = strategy_signal(trending_bars(0.03), spec)
    strong = strategy_signal(trending_bars(0.30), spec)

    assert weak.action.value == "BUY"
    assert strong.action.value == "BUY"
    assert 0.50 <= weak.confidence <= 0.90
    assert 0.50 <= strong.confidence <= 0.90
    assert strong.score >= weak.score


def test_hold_signal_has_low_confidence():
    bars = trending_bars(0.0)
    spec = StrategySpec("momentum_breakout", {"window": 20})
    signal = strategy_signal(bars, spec)
    assert signal.action.value == "HOLD"
    assert signal.confidence == 0.25
    assert signal.score == 0.0
