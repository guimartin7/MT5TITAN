from mt5titan.domain import DecisionAction, MarketRegime, Signal
from mt5titan.intelligence import DecisionEngine, build_features, detect_regime, score_market


def trending_bars(count=80):
    rows = []
    price = 100.0
    for i in range(count):
        open_price = price
        price += 0.35
        rows.append({
            "time": i + 1,
            "open": open_price,
            "high": price + 0.1,
            "low": open_price - 0.1,
            "close": price,
            "spread": 1,
            "tick_volume": 100 + i,
        })
    return rows


def ranging_bars(count=80):
    rows = []
    for i in range(count):
        close = 100.0 + (0.2 if i % 2 == 0 else -0.2)
        rows.append({
            "time": i + 1,
            "open": 100.0,
            "high": 100.3,
            "low": 99.7,
            "close": close,
            "spread": 1,
            "tick_volume": 100,
        })
    return rows


def test_feature_pipeline_uses_closed_bars():
    features = build_features(trending_bars())
    assert features.sma_fast > features.sma_slow
    assert features.momentum_pct > 0


def test_trending_regime_is_detected():
    features = build_features(trending_bars())
    regime = detect_regime(features)
    assert regime.regime == MarketRegime.TRENDING


def test_ranging_market_is_not_misclassified_as_strong_trend():
    features = build_features(ranging_bars())
    regime = detect_regime(features)
    assert regime.regime in {MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY, MarketRegime.UNCERTAIN}


def test_decision_engine_respects_market_score_gate():
    features = build_features(trending_bars())
    regime = detect_regime(features)
    market = score_market(features, regime)
    signals = [
        Signal("trend", DecisionAction.BUY, 0.8, 0.8),
        Signal("momentum", DecisionAction.BUY, 0.7, 0.6),
    ]
    decision = DecisionEngine().decide(
        symbol="WINV26",
        timestamp=123,
        signals=signals,
        regime=regime,
        market_score=market,
    )
    assert decision.action == DecisionAction.BUY
    assert decision.decision_id


def test_high_volatility_reduces_regime_weight_but_does_not_bypass_gates():
    signals = [Signal("trend", DecisionAction.BUY, 0.9, 0.8)]
    class R:
        regime = MarketRegime.HIGH_VOLATILITY
        confidence = 0.9
    class M:
        total = 20.0
    decision = DecisionEngine().decide(
        symbol="WINV26", timestamp=1, signals=signals, regime=R(), market_score=M()
    )
    assert decision.action == DecisionAction.HOLD
    assert "MARKET_SCORE_TOO_LOW" in decision.reason_codes
