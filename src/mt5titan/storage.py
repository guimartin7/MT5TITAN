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

                CREATE TABLE IF NOT EXISTS watchlist (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    source TEXT NOT NULL,
                    PRIMARY KEY(symbol, timeframe, source)
                );

                CREATE TABLE IF NOT EXISTS market_candles (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    time INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    spread REAL NOT NULL DEFAULT 0,
                    tick_volume REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY(symbol, timeframe, time)
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

    def get_analysis(self, analysis_id: int) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute(
                """
                SELECT id, created_at_utc, symbol, timeframe, decision_id, action,
                       confidence, score, regime, market_score, risk_allowed, payload_json
                FROM analyses
                WHERE id = ?
                """,
                (analysis_id,),
            ).fetchone()
        if row is None:
            raise ValueError("analysis not found")
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

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


    def add_watchlist(self, *, symbol: str, timeframe: str, source: str) -> dict:
        symbol = symbol.strip().upper()
        timeframe = timeframe.strip().upper()
        source = source.strip().lower()
        if not symbol:
            raise ValueError("symbol is required")
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO watchlist(symbol, timeframe, source) VALUES (?, ?, ?)",
                (symbol, timeframe, source),
            )
        return {"symbol": symbol, "timeframe": timeframe, "source": source}

    def remove_watchlist(self, *, symbol: str, timeframe: str, source: str) -> None:
        with self.connect() as db:
            db.execute(
                "DELETE FROM watchlist WHERE symbol=? AND timeframe=? AND source=?",
                (symbol.upper(), timeframe.upper(), source.lower()),
            )

    def list_watchlist(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT symbol, timeframe, source FROM watchlist ORDER BY symbol, timeframe"
            ).fetchall()
        return [dict(row) for row in rows]

    def replace_market_candles(self, *, symbol: str, timeframe: str, candles: list[dict]) -> int:
        symbol = symbol.strip().upper()
        timeframe = timeframe.strip().upper()
        if len(candles) < 30:
            raise ValueError("at least 30 candles are required")
        with self.connect() as db:
            db.execute(
                "DELETE FROM market_candles WHERE symbol=? AND timeframe=?",
                (symbol, timeframe),
            )
            db.executemany(
                """
                INSERT INTO market_candles(
                    symbol, timeframe, time, open, high, low, close, spread, tick_volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        symbol,
                        timeframe,
                        int(candle["time"]),
                        float(candle["open"]),
                        float(candle["high"]),
                        float(candle["low"]),
                        float(candle["close"]),
                        float(candle.get("spread", 0.0)),
                        float(candle.get("tick_volume", 0.0)),
                    )
                    for candle in candles
                ],
            )
        return len(candles)

    def load_market_candles(self, *, symbol: str, timeframe: str, limit: int = 140) -> list[dict]:
        limit = max(30, min(int(limit), 5000))
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT time, open, high, low, close, spread, tick_volume
                FROM market_candles
                WHERE symbol=? AND timeframe=?
                ORDER BY time DESC
                LIMIT ?
                """,
                (symbol.upper(), timeframe.upper(), limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]
