"""SQLite persistence for analyses and paper trading."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteStore:
    def __init__(self, path: str | Path = "data/mt5titan.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS paper_trades (
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

                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at_utc TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    score REAL NOT NULL,
                    regime TEXT NOT NULL,
                    market_score REAL NOT NULL,
                    risk_allowed INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def get_state_float(self, key: str, default: float) -> float:
        with self.connect() as db:
            row = db.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
        return default if row is None else float(row["value"])

    def set_state(self, key: str, value: str | float | int) -> None:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO app_state(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, str(value)),
            )

    def create_paper_trade(
        self, *, symbol: str, side: str, stake: float, entry_price: float, created_at_utc: str
    ) -> dict:
        with self.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO paper_trades(symbol, side, stake, entry_price, created_at_utc)
                VALUES (?, ?, ?, ?, ?)
                """,
                (symbol, side, stake, entry_price, created_at_utc),
            )
            trade_id = int(cursor.lastrowid)
        return self.get_paper_trade(trade_id)

    def get_paper_trade(self, trade_id: int) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM paper_trades WHERE trade_id = ?", (trade_id,)).fetchone()
        if row is None:
            raise ValueError("trade not found")
        return dict(row)

    def settle_paper_trade(
        self,
        *,
        trade_id: int,
        exit_price: float,
        payout_ratio: float,
        won: bool,
        pnl: float,
        settled_at_utc: str,
    ) -> dict:
        with self.connect() as db:
            db.execute(
                """
                UPDATE paper_trades
                SET status='SETTLED', exit_price=?, payout_ratio=?, won=?, pnl=?, settled_at_utc=?
                WHERE trade_id=? AND status='OPEN'
                """,
                (exit_price, payout_ratio, int(won), pnl, settled_at_utc, trade_id),
            )
        return self.get_paper_trade(trade_id)

    def paper_snapshot(self) -> dict:
        with self.connect() as db:
            open_rows = db.execute(
                "SELECT * FROM paper_trades WHERE status='OPEN' ORDER BY trade_id DESC"
            ).fetchall()
            history_rows = db.execute(
                "SELECT * FROM paper_trades WHERE status='SETTLED' ORDER BY trade_id DESC LIMIT 100"
            ).fetchall()
        return {
            "open_trades": [dict(row) for row in open_rows],
            "history": [dict(row) for row in history_rows],
        }

    def save_analysis(self, report: dict, created_at_utc: str) -> int:
        decision = report["decision"]
        with self.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO analyses(
                    created_at_utc, symbol, timeframe, decision_id, action, confidence,
                    score, regime, market_score, risk_allowed, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at_utc,
                    report["symbol"],
                    report["timeframe"],
                    decision["id"],
                    decision["action"],
                    decision["confidence"],
                    decision["score"],
                    report["regime"]["value"],
                    report["market_score"]["total"],
                    int(report["risk"]["allowed"]),
                    json.dumps(report, ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def recent_analyses(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT id, created_at_utc, symbol, timeframe, decision_id, action,
                       confidence, score, regime, market_score, risk_allowed
                FROM analyses
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
