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
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
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
                    analysis_id INTEGER,
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

                CREATE TABLE IF NOT EXISTS decision_outcomes (
                    analysis_id INTEGER PRIMARY KEY,
                    evaluated_at_utc TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    action TEXT NOT NULL,
                    result TEXT NOT NULL,
                    market_direction TEXT NOT NULL,
                    directional_return_pct REAL NOT NULL,
                    FOREIGN KEY(analysis_id) REFERENCES analyses(id)
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
            self._migrate_schema(db)

    def _migrate_schema(self, db) -> None:
        columns = {
            row["name"]
            for row in db.execute("PRAGMA table_info(paper_trades)").fetchall()
        }
        if "analysis_id" not in columns:
            db.execute("ALTER TABLE paper_trades ADD COLUMN analysis_id INTEGER")

        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_paper_trades_analysis_id "
            "ON paper_trades(analysis_id)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_paper_trades_status "
            "ON paper_trades(status)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_created_at "
            "ON analyses(created_at_utc)"
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

    def open_paper_trade_atomic(
        self,
        *,
        analysis_id: int | None,
        symbol: str,
        side: str,
        stake: float,
        entry_price: float,
        created_at_utc: str,
        initial_balance: float,
    ) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = db.execute(
                "SELECT value FROM app_state WHERE key='paper_balance'"
            ).fetchone()
            balance = initial_balance if state is None else float(state["value"])
            if stake > balance:
                raise ValueError("insufficient paper balance")

            cursor = db.execute(
                """
                INSERT INTO paper_trades(
                    analysis_id, symbol, side, stake, entry_price, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    symbol,
                    side,
                    float(stake),
                    float(entry_price),
                    created_at_utc,
                ),
            )
            new_balance = balance - float(stake)
            db.execute(
                """
                INSERT INTO app_state(key, value) VALUES ('paper_balance', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(round(new_balance, 10)),),
            )
            trade_id = int(cursor.lastrowid)
        return self.get_paper_trade(trade_id)

    def settle_paper_trade_atomic(
        self,
        *,
        trade_id: int,
        exit_price: float,
        payout_ratio: float,
        won: bool,
        returned: float,
        pnl: float,
        settled_at_utc: str,
        initial_balance: float,
    ) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            trade = db.execute(
                "SELECT * FROM paper_trades WHERE trade_id=?",
                (trade_id,),
            ).fetchone()
            if trade is None:
                raise ValueError("trade not found")
            if trade["status"] != "OPEN":
                raise ValueError("trade already settled")

            state = db.execute(
                "SELECT value FROM app_state WHERE key='paper_balance'"
            ).fetchone()
            balance = initial_balance if state is None else float(state["value"])
            new_balance = balance + float(returned)

            db.execute(
                """
                UPDATE paper_trades
                SET status='SETTLED', exit_price=?, payout_ratio=?, won=?, pnl=?,
                    settled_at_utc=?
                WHERE trade_id=? AND status='OPEN'
                """,
                (
                    float(exit_price),
                    float(payout_ratio),
                    int(won),
                    float(pnl),
                    settled_at_utc,
                    trade_id,
                ),
            )
            db.execute(
                """
                INSERT INTO app_state(key, value) VALUES ('paper_balance', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(round(new_balance, 10)),),
            )
        return self.get_paper_trade(trade_id)

    def reset_paper_account(self, *, balance: float) -> None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM paper_trades")
            db.execute(
                """
                INSERT INTO app_state(key, value) VALUES ('paper_balance', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(round(float(balance), 10)),),
            )

    def paper_risk_snapshot(
        self,
        *,
        initial_balance: float,
        symbol: str | None = None,
        day_utc: str | None = None,
    ) -> dict:
        from datetime import datetime, timezone

        day = day_utc or datetime.now(timezone.utc).date().isoformat()
        with self.connect() as db:
            open_rows = db.execute(
                "SELECT symbol FROM paper_trades WHERE status='OPEN'"
            ).fetchall()
            entries_today = int(
                db.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM paper_trades
                    WHERE substr(created_at_utc, 1, 10)=?
                    """,
                    (day,),
                ).fetchone()["total"]
            )
            settled = db.execute(
                """
                SELECT pnl, settled_at_utc
                FROM paper_trades
                WHERE status='SETTLED' AND pnl IS NOT NULL
                ORDER BY settled_at_utc, trade_id
                """
            ).fetchall()

        daily_pnl = sum(
            float(row["pnl"])
            for row in settled
            if str(row["settled_at_utc"] or "").startswith(day)
        )
        cumulative = 0.0
        peak = 0.0
        for row in settled:
            cumulative += float(row["pnl"])
            peak = max(peak, cumulative)

        drawdown_pct = (
            (cumulative - peak) / float(initial_balance) * 100.0
            if initial_balance > 0
            else 0.0
        )
        daily_return_pct = (
            daily_pnl / float(initial_balance) * 100.0
            if initial_balance > 0
            else 0.0
        )
        normalized_symbol = symbol.upper() if symbol else None
        same_symbol_open = (
            any(str(row["symbol"]).upper() == normalized_symbol for row in open_rows)
            if normalized_symbol
            else False
        )
        return {
            "daily_return_pct": round(daily_return_pct, 6),
            "drawdown_pct": round(drawdown_pct, 6),
            "entries_today": entries_today,
            "open_trades": len(open_rows),
            "conflicting_exposure": same_symbol_open,
        }

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


    def save_outcome(
        self,
        *,
        analysis_id: int,
        evaluated_at_utc: str,
        entry_price: float,
        exit_price: float,
        action: str,
        result: str,
        market_direction: str,
        directional_return_pct: float,
    ) -> dict:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO decision_outcomes(
                    analysis_id, evaluated_at_utc, entry_price, exit_price,
                    action, result, market_direction, directional_return_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(analysis_id) DO UPDATE SET
                    evaluated_at_utc=excluded.evaluated_at_utc,
                    entry_price=excluded.entry_price,
                    exit_price=excluded.exit_price,
                    action=excluded.action,
                    result=excluded.result,
                    market_direction=excluded.market_direction,
                    directional_return_pct=excluded.directional_return_pct
                """,
                (
                    analysis_id,
                    evaluated_at_utc,
                    entry_price,
                    exit_price,
                    action,
                    result,
                    market_direction,
                    directional_return_pct,
                ),
            )
        return self.get_outcome(analysis_id)

    def get_outcome(self, analysis_id: int) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM decision_outcomes WHERE analysis_id=?",
                (analysis_id,),
            ).fetchone()
        if row is None:
            raise ValueError("outcome not found")
        return dict(row)

    def recent_outcomes(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT o.*, a.symbol, a.timeframe, a.regime, a.confidence, a.market_score
                FROM decision_outcomes o
                JOIN analyses a ON a.id = o.analysis_id
                ORDER BY o.analysis_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def outcome_statistics(self) -> dict:
        outcomes = self.recent_outcomes(500)
        directional = [row for row in outcomes if row["action"] in {"BUY", "SELL"}]
        wins = sum(1 for row in directional if row["result"] == "WIN")
        losses = sum(1 for row in directional if row["result"] == "LOSS")
        flats = sum(1 for row in directional if row["result"] == "FLAT")

        by_regime: dict[str, dict] = {}
        for row in directional:
            bucket = by_regime.setdefault(
                row["regime"],
                {"trades": 0, "wins": 0, "losses": 0, "flats": 0},
            )
            bucket["trades"] += 1
            if row["result"] == "WIN":
                bucket["wins"] += 1
            elif row["result"] == "LOSS":
                bucket["losses"] += 1
            else:
                bucket["flats"] += 1

        for bucket in by_regime.values():
            resolved = bucket["wins"] + bucket["losses"]
            bucket["win_rate_pct"] = (
                round(bucket["wins"] / resolved * 100.0, 2) if resolved else None
            )

        agent_totals: dict[str, dict] = {}
        for row in directional:
            analysis = self.get_analysis(int(row["analysis_id"]))
            payload = analysis["payload"]
            ai = payload.get("ai") or {}
            actual = row["market_direction"]
            if actual not in {"BUY", "SELL"}:
                continue

            opinions = list(ai.get("agents") or [])
            committee = ai.get("committee")
            if committee:
                opinions.append({
                    "agent": "committee",
                    "verdict": committee.get("action"),
                })

            for opinion in opinions:
                agent = str(opinion.get("agent", "unknown"))
                verdict = str(opinion.get("verdict", "HOLD"))
                if verdict not in {"BUY", "SELL"}:
                    continue
                bucket = agent_totals.setdefault(agent, {"directional_calls": 0, "correct": 0})
                bucket["directional_calls"] += 1
                if verdict == actual:
                    bucket["correct"] += 1

        for bucket in agent_totals.values():
            bucket["accuracy_pct"] = round(
                bucket["correct"] / bucket["directional_calls"] * 100.0, 2
            ) if bucket["directional_calls"] else None

        resolved = wins + losses
        return {
            "evaluated": len(outcomes),
            "directional_trades": len(directional),
            "wins": wins,
            "losses": losses,
            "flats": flats,
            "win_rate_pct": round(wins / resolved * 100.0, 2) if resolved else None,
            "by_regime": by_regime,
            "agents": agent_totals,
        }
