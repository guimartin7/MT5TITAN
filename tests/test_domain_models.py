import pytest

from mt5titan.domain import DecisionAction, MarketRegime, MarketSnapshot, Signal


def test_market_snapshot_validates_quote():
    snapshot = MarketSnapshot("WINV26", "M5", 1, 140000.0, 140005.0, MarketRegime.TRENDING)
    snapshot.validate()
    assert snapshot.spread == 5.0


def test_market_snapshot_rejects_inverted_quote():
    snapshot = MarketSnapshot("WINV26", "M5", 1, 10, 9)
    with pytest.raises(ValueError):
        snapshot.validate()


def test_signal_validation():
    Signal("quant", DecisionAction.BUY, 0.75, 0.6).validate()
