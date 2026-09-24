from pathlib import Path

from mt5titan.brokers.paper import PaperTradingBroker
from mt5titan.storage import SQLiteStore


def test_paper_balance_and_trade_survive_restart(tmp_path: Path):
    path = tmp_path / "app.db"
    store = SQLiteStore(path)
    broker = PaperTradingBroker(store=store)
    trade = broker.place_order(symbol="EURUSD", side="BUY", stake=100, price=1.1)

    restarted = PaperTradingBroker(store=SQLiteStore(path))
    snapshot = restarted.snapshot()

    assert snapshot["balance"] == 9900.0
    assert snapshot["open_trades"][0]["trade_id"] == trade["trade_id"]


def test_settlement_is_persisted(tmp_path: Path):
    path = tmp_path / "app.db"
    broker = PaperTradingBroker(store=SQLiteStore(path))
    trade = broker.place_order(symbol="DEMO", side="BUY", stake=100, price=100)
    result = broker.settle(trade_id=trade["trade_id"], exit_price=101, payout_ratio=0.82)

    restarted = PaperTradingBroker(store=SQLiteStore(path))
    snapshot = restarted.snapshot()

    assert result["won"] == 1
    assert snapshot["balance"] == 10082.0
    assert not snapshot["open_trades"]
    assert snapshot["history"][0]["pnl"] == 82.0


def test_analysis_history_survives_restart(tmp_path: Path):
    path = tmp_path / "app.db"
    store = SQLiteStore(path)
    report = {
        "symbol": "DEMO",
        "timeframe": "M5",
        "regime": {"value": "TRENDING"},
        "market_score": {"total": 72.5},
        "decision": {
            "id": "abc",
            "action": "BUY",
            "confidence": 0.8,
            "score": 0.6,
        },
        "risk": {"allowed": True},
    }

    identifier = store.save_analysis(report, "2026-09-24T00:00:00+00:00")
    recent = SQLiteStore(path).recent_analyses()

    assert recent[0]["id"] == identifier
    assert recent[0]["action"] == "BUY"
    assert recent[0]["regime"] == "TRENDING"
