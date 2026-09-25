from mt5titan.intelligence.multitimeframe import build_timeframe_confirmation
from mt5titan.marketdata.resample import next_higher_timeframe, resample_candles


def candles(count=180, step=60):
    rows = []
    price = 100.0
    for index in range(count):
        open_price = price
        price += 0.1
        rows.append({
            "time": 1_700_000_000 + index * step,
            "open": open_price,
            "high": price + 0.05,
            "low": open_price - 0.05,
            "close": price,
            "spread": 0.01,
            "tick_volume": 100,
        })
    return rows


def report(timeframe, action, confidence):
    return {
        "timeframe": timeframe,
        "decision": {
            "action": action,
            "confidence": confidence,
        },
    }


def test_resample_m1_to_m5():
    rows = resample_candles(candles(), "M5")
    assert len(rows) >= 30
    assert rows[0]["time"] < rows[-1]["time"]
    assert rows[-1]["high"] >= rows[-1]["close"]
    assert rows[-1]["low"] <= rows[-1]["open"]


def test_next_higher_timeframe_mapping():
    assert next_higher_timeframe("M1") == "M5"
    assert next_higher_timeframe("M5") == "M15"
    assert next_higher_timeframe("M15") == "H1"
    assert next_higher_timeframe("H1") is None


def test_aligned_higher_timeframe_boosts_score():
    result = build_timeframe_confirmation(
        base_report=report("M5", "BUY", 0.7),
        higher_report=report("M15", "BUY", 0.8),
    )
    assert result.status == "ALIGNED"
    assert result.adjustment_pct > 0


def test_conflicting_higher_timeframe_penalizes_score():
    result = build_timeframe_confirmation(
        base_report=report("M5", "BUY", 0.7),
        higher_report=report("M15", "SELL", 0.8),
    )
    assert result.status == "CONFLICT"
    assert result.adjustment_pct < 0
