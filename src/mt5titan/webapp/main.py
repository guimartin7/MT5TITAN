"""Functional web application for MT5TITAN."""
from __future__ import annotations

from pathlib import Path
from typing import Literal
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from mt5titan.brokers import AvalonBrokerAdapter, PaperTradingBroker
from mt5titan.domain import DecisionAction
from mt5titan.intelligence import DecisionEngine, build_features, detect_regime, score_market
from mt5titan.intelligence.signals import strategy_signal
from mt5titan.research import StrategySpec
from mt5titan.risk import RiskEngine, RiskLimits, RiskState
from mt5titan.storage import SQLiteStore


app = FastAPI(title="MT5TITAN", version="0.3.0")
store = SQLiteStore()
paper = PaperTradingBroker(store=store)
avalon = AvalonBrokerAdapter()


class Candle(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    spread: float = 0.0
    tick_volume: float = 0.0


class AnalyzeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = "M5"
    candles: list[Candle] = Field(min_length=30)


class PaperOrderRequest(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    stake: float = Field(gt=0)
    price: float = Field(gt=0)


class PaperSettleRequest(BaseModel):
    trade_id: int
    exit_price: float = Field(gt=0)
    payout_ratio: float = Field(default=0.82, ge=0, le=2)


def _specs():
    return (
        StrategySpec("sma_trend", {"fast": 9, "slow": 21}),
        StrategySpec("momentum_breakout", {"window": 20}),
        StrategySpec("rsi_mean_reversion", {"window": 14, "lower": 30, "upper": 70, "exit": 50}),
    )


def _analyze(payload: AnalyzeRequest) -> dict:
    bars = [c.model_dump() for c in payload.candles]
    features = build_features(bars)
    regime = detect_regime(features)
    market = score_market(features, regime)
    signals = [strategy_signal(bars, spec, source=spec.name) for spec in _specs()]

    last = bars[-1]
    from mt5titan.domain import MarketSnapshot
    snapshot = MarketSnapshot(
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        timestamp=int(last["time"]),
        bid=float(last["close"]),
        ask=float(last["close"]) + float(last.get("spread", 0.0)),
        regime=regime.regime,
        features=features.to_dict(),
    )

    decision = DecisionEngine().decide(
        symbol=payload.symbol,
        timestamp=snapshot.timestamp,
        signals=signals,
        regime=regime,
        market_score=market,
    )
    risk = RiskEngine(
        RiskLimits(min_confidence=0.55)
    ).evaluate(decision, snapshot, RiskState())

    return {
        "symbol": payload.symbol,
        "timeframe": payload.timeframe,
        "features": features.to_dict(),
        "regime": {
            "value": regime.regime.value,
            "confidence": regime.confidence,
            "reasons": list(regime.reasons),
        },
        "market_score": {
            "total": market.total,
            "trend": market.trend,
            "momentum": market.momentum,
            "volatility": market.volatility,
            "liquidity": market.liquidity,
        },
        "signals": [
            {
                "source": s.source,
                "action": s.action.value,
                "confidence": s.confidence,
                "score": s.score,
                "reasons": list(s.reasons),
            }
            for s in signals
        ],
        "decision": {
            "id": decision.decision_id,
            "action": decision.action.value,
            "confidence": decision.confidence,
            "score": decision.score,
            "reasons": list(decision.reason_codes),
        },
        "risk": {
            "allowed": risk.allowed,
            "reasons": list(risk.reasons),
        },
        "execution": {
            "live_enabled": False,
            "paper_enabled": True,
        },
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.3.0", "persistence": "sqlite"}


@app.get("/api/brokers")
def broker_status():
    return {"paper": paper.status(), "avalon": avalon.status()}


@app.post("/api/analyze")
def analyze(payload: AnalyzeRequest):
    try:
        report = _analyze(payload)
        analysis_id = store.save_analysis(report, datetime.now(timezone.utc).isoformat())
        report["analysis_id"] = analysis_id
        return report
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/analyses")
def analyses(limit: int = 50):
    return {"items": store.recent_analyses(limit)}


@app.get("/api/paper")
def paper_status():
    return paper.snapshot()


@app.post("/api/paper/reset")
def paper_reset():
    return paper.reset()


@app.post("/api/paper/order")
def paper_order(payload: PaperOrderRequest):
    try:
        return paper.place_order(**payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/paper/settle")
def paper_settle(payload: PaperSettleRequest):
    try:
        return paper.settle(**payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/demo/candles")
def demo_candles(count: int = 120):
    count = max(30, min(count, 500))
    price = 100.0
    rows = []
    for index in range(count):
        cycle = (index // 35) % 3
        drift = 0.22 if cycle == 0 else -0.16 if cycle == 1 else (0.04 if index % 2 == 0 else -0.04)
        open_price = price
        price = max(10.0, price + drift)
        rows.append({
            "time": 1_700_000_000 + index * 300,
            "open": round(open_price, 4),
            "high": round(max(open_price, price) + 0.08, 4),
            "low": round(min(open_price, price) - 0.08, 4),
            "close": round(price, 4),
            "spread": 0.01,
            "tick_volume": 100 + index,
        })
    return {"symbol": "DEMO", "timeframe": "M5", "candles": rows}


@app.get("/", response_class=HTMLResponse)
def index():
    path = Path(__file__).parent / "static" / "index.html"
    return path.read_text(encoding="utf-8")


def run():
    import uvicorn
    uvicorn.run("mt5titan.webapp.main:app", host="127.0.0.1", port=8000, reload=False)
