import sqlite3
from pathlib import Path

from mt5titan.brokers.paper import PaperTradingBroker
from mt5titan.storage import SQLiteStore


def test_old_paper_schema_is_migrated(tmp_path: Path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE paper_trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                stake REAL NOT NULL,
                entry_price REAL NOT NULL,
                created_at_utc TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                exit_price REAL,
                payout_ratio REAL,
                won INTEGER,
                pnl REAL,
                settled_at_utc TEXT
            );
            """
        )

    store = SQLiteStore(path)
    with store.connect() as db:
        columns = {
            row["name"]
            for row in db.execute("PRAGMA table_info(paper_trades)").fetchall()
        }

    assert "analysis_id" in columns


def test_analysis_id_survives_paper_restart(tmp_path: Path):
    path = tmp_path / "audit.db"
    broker = PaperTradingBroker(store=SQLiteStore(path))
    trade = broker.place_order(
        symbol="EURUSD",
        side="BUY",
        stake=100,
        price=1.1,
        analysis_id=42,
    )

    restarted = PaperTradingBroker(store=SQLiteStore(path))
    snapshot = restarted.snapshot()

    assert trade["analysis_id"] == 42
    assert snapshot["open_trades"][0]["analysis_id"] == 42
    assert snapshot["balance"] == 9900.0


def test_paper_reset_clears_trades_and_restores_balance(tmp_path: Path):
    broker = PaperTradingBroker(store=SQLiteStore(tmp_path / "reset.db"))
    broker.place_order(
        symbol="BTCUSD",
        side="BUY",
        stake=100,
        price=100,
        analysis_id=1,
    )

    snapshot = broker.reset()

    assert snapshot["balance"] == 10000.0
    assert snapshot["open_trades"] == []
    assert snapshot["history"] == []


def test_risk_snapshot_tracks_daily_loss_and_open_exposure(tmp_path: Path):
    store = SQLiteStore(tmp_path / "risk.db")
    broker = PaperTradingBroker(store=store)
    first = broker.place_order(
        symbol="EURUSD",
        side="BUY",
        stake=100,
        price=1.1,
        analysis_id=1,
    )
    broker.settle(
        trade_id=first["trade_id"],
        exit_price=1.0,
        payout_ratio=0.82,
    )
    broker.place_order(
        symbol="GBPUSD",
        side="SELL",
        stake=50,
        price=1.3,
        analysis_id=2,
    )

    snapshot = store.paper_risk_snapshot(
        initial_balance=10000.0,
        symbol="GBPUSD",
    )

    assert snapshot["daily_return_pct"] == -1.0
    assert snapshot["drawdown_pct"] == -1.0
    assert snapshot["entries_today"] == 2
    assert snapshot["open_trades"] == 1
    assert snapshot["conflicting_exposure"] is True
