"""Functional web application for MT5TITAN."""
from __future__ import annotations

from pathlib import Path
import os
from typing import Literal
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from mt5titan.brokers import AvalonBrokerAdapter, PaperTradingBroker
from mt5titan.domain import DecisionAction
from mt5titan.intelligence import DecisionEngine, build_features, build_trade_recommendation, detect_regime, score_market
from mt5titan.intelligence.signals import strategy_signal
from mt5titan.marketdata import DemoMarketDataProvider, StoredMarketDataProvider, TwelveDataMarketDataProvider
from mt5titan.research import StrategySpec
from mt5titan.risk import RiskEngine, RiskLimits, RiskState
from mt5titan.storage import SQLiteStore
from mt5titan.titan import AICommittee, OpinionReplayStore, TitanExperiment, build_agent_context
from mt5titan.titan.providers import OpenAIProvider


app = FastAPI(title="MT5TITAN", version="0.9.0")
store = SQLiteStore()
paper = PaperTradingBroker(store=store)
avalon = AvalonBrokerAdapter()
demo_market = DemoMarketDataProvider()
stored_market = StoredMarketDataProvider(store)
twelve_market = TwelveDataMarketDataProvider()


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
    source: str = "external"
    use_ai: bool = False
    candles: list[Candle] = Field(min_length=30)


class PaperOrderRequest(BaseModel):
    analysis_id: int
    symbol: str
    side: Literal["BUY", "SELL"]
    stake: float = Field(gt=0)
    price: float = Field(gt=0)


class WatchlistRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = "M5"
    source: Literal["demo", "stored", "twelve"] = "demo"


class MarketImportRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = "M5"
    candles: list[Candle] = Field(min_length=30)


class PaperSettleRequest(BaseModel):
    trade_id: int
    exit_price: float = Field(gt=0)
    payout_ratio: float = Field(default=0.82, ge=0, le=2)


class OutcomeRequest(BaseModel):
    analysis_id: int
    exit_price: float = Field(gt=0)
    entry_price: float | None = Field(default=None, gt=0)


class ScannerRequest(BaseModel):
    deep_ai: bool = False
    ai_top_n: int = Field(default=3, ge=1, le=5)
    candle_count: int = Field(default=140, ge=30, le=500)


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
    quant_signals = list(signals)
    ai_payload = None

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

    if payload.use_ai:
        if not os.getenv("OPENAI_API_KEY") or not os.getenv("OPENAI_MODEL"):
            raise RuntimeError(
                "AI mode requires OPENAI_API_KEY and OPENAI_MODEL in the environment"
            )

        context = build_agent_context(
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            timestamp=snapshot.timestamp,
            features=features,
            regime=regime,
            market_score=market,
            strategy_signals={signal.source: signal.score for signal in quant_signals},
            event_risk={"blocked": False, "caution": False, "relevant_events": []},
            portfolio={"allowed": True, "blockers": []},
        )
        try:
            provider = OpenAIProvider()
            replay_store = OpinionReplayStore(Path("replays") / "web-opinions.jsonl")
            experiment = TitanExperiment(provider, replay_store)
            experiment_result = experiment.run_context(
                key=f"{payload.symbol}:{payload.timeframe}:{snapshot.timestamp}",
                context=context,
                metadata={"source": payload.source},
            )
            ai_signal = AICommittee().aggregate(list(experiment_result.opinions))
            signals.append(ai_signal)
            ai_payload = {
                "enabled": True,
                "requested": True,
                "available": True,
                "committee": {
                    "action": ai_signal.action.value,
                    "confidence": ai_signal.confidence,
                    "score": ai_signal.score,
                    "reasons": list(ai_signal.reasons),
                },
                "agents": [
                    {
                        "agent": opinion.agent,
                        "verdict": opinion.verdict.value,
                        "confidence": opinion.confidence,
                        "score": opinion.score,
                        "reason_codes": list(opinion.reason_codes),
                        "risk_flags": list(opinion.risk_flags),
                    }
                    for opinion in experiment_result.opinions
                ],
            }
        except RuntimeError as error:
            message = str(error)
            lowered = message.lower()
            if "credit_balance_exhausted" in lowered or "insufficient_quota" in lowered:
                reason = "OPENAI_CREDITS_EXHAUSTED"
            elif "ratelimit" in lowered or "rate limit" in lowered:
                reason = "OPENAI_RATE_LIMIT"
            else:
                reason = "OPENAI_UNAVAILABLE"
            ai_payload = {
                "enabled": False,
                "requested": True,
                "available": False,
                "fallback": "quant_only",
                "reason": reason,
                "message": message[:500],
            }

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
        "source": payload.source,
        "market_timestamp": snapshot.timestamp,
        "reference_price": snapshot.bid,
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
        "ai": ai_payload or {
            "enabled": False,
            "requested": False,
            "available": False,
            "fallback": None,
        },
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
    ai_configured = bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL"))
    return {
        "status": "ok",
        "version": "0.9.0",
        "persistence": "sqlite",
        "ai": {
            "provider": "openai",
            "configured": ai_configured,
        },
        "market_data": {
            "twelve_configured": bool(os.getenv("TWELVE_DATA_API_KEY")),
        },
    }


@app.get("/api/diagnostics")
def diagnostics():
    ai_key = bool(os.getenv("OPENAI_API_KEY"))
    ai_model = bool(os.getenv("OPENAI_MODEL"))
    try:
        db_ok = store.list_watchlist() is not None
    except Exception:
        db_ok = False

    return {
        "app": {"status": "ok", "version": "0.8.0"},
        "database": {"status": "ok" if db_ok else "error"},
        "quant": {"status": "ok"},
        "ai": {
            "status": "configured" if ai_key and ai_model else "not_configured",
            "api_key_present": ai_key,
            "model_present": ai_model,
        },
        "market_data": {
            "twelve": {
                "status": "configured" if os.getenv("TWELVE_DATA_API_KEY") else "not_configured",
                "api_key_present": bool(os.getenv("TWELVE_DATA_API_KEY")),
            }
        },
        "avalon": avalon.status(),
    }


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
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/scanner")
def scan_opportunities(payload: ScannerRequest):
    watch_items = store.list_watchlist()
    if not watch_items:
        raise HTTPException(status_code=422, detail="watchlist is empty")

    if payload.deep_ai and (
        not os.getenv("OPENAI_API_KEY") or not os.getenv("OPENAI_MODEL")
    ):
        raise HTTPException(
            status_code=503,
            detail="Deep AI scan requires OPENAI_API_KEY and OPENAI_MODEL",
        )

    candidates = []
    skipped = []
    twelve_calls = 0
    twelve_limit = max(1, min(int(os.getenv("TWELVE_DATA_SCAN_LIMIT", "6")), 25))

    for item in watch_items[:25]:
        if item["source"] == "twelve":
            if twelve_calls >= twelve_limit:
                skipped.append({
                    "symbol": item["symbol"],
                    "timeframe": item["timeframe"],
                    "source": item["source"],
                    "reason": f"real-data scan budget reached ({twelve_limit})",
                })
                continue
            twelve_calls += 1
        try:
            provider = demo_market if item["source"] == "demo" else stored_market if item["source"] == "stored" else twelve_market
            batch = provider.candles(
                symbol=item["symbol"],
                timeframe=item["timeframe"],
                count=payload.candle_count,
            )
            request = AnalyzeRequest(
                symbol=batch.symbol,
                timeframe=batch.timeframe,
                source=batch.source,
                use_ai=False,
                candles=[Candle(**row) for row in batch.candles],
            )
            report = _analyze(request)
            recommendation = build_trade_recommendation(report)
            candidates.append({
                "symbol": batch.symbol,
                "timeframe": batch.timeframe,
                "source": batch.source,
                "deep_ai": False,
                "recommendation": recommendation.to_dict(),
                "decision": report["decision"],
                "regime": report["regime"],
                "market_score": report["market_score"],
                "risk": report["risk"],
                "_candles": batch.candles,
            })
        except (ValueError, RuntimeError) as error:
            skipped.append({
                "symbol": item["symbol"],
                "timeframe": item["timeframe"],
                "source": item["source"],
                "reason": str(error),
            })

    candidates.sort(
        key=lambda row: row["recommendation"]["opportunity_score"],
        reverse=True,
    )

    if payload.deep_ai:
        eligible = [
            row
            for row in candidates
            if row["recommendation"]["action"] != "HOLD" and row["risk"]["allowed"]
        ][: payload.ai_top_n]

        for candidate in eligible:
            request = AnalyzeRequest(
                symbol=candidate["symbol"],
                timeframe=candidate["timeframe"],
                source=candidate["source"],
                use_ai=True,
                candles=[Candle(**row) for row in candidate["_candles"]],
            )
            report = _analyze(request)
            recommendation = build_trade_recommendation(report)
            candidate.update({
                "deep_ai": True,
                "recommendation": recommendation.to_dict(),
                "decision": report["decision"],
                "regime": report["regime"],
                "market_score": report["market_score"],
                "risk": report["risk"],
                "ai": report["ai"],
            })

        candidates.sort(
            key=lambda row: row["recommendation"]["opportunity_score"],
            reverse=True,
        )

    for candidate in candidates:
        candidate.pop("_candles", None)

    return {
        "mode": "QUANT_PLUS_TOP_AI" if payload.deep_ai else "QUANT_SCAN",
        "watchlist_size": len(watch_items),
        "ranked": candidates,
        "skipped": skipped,
        "note": (
            "Scanner results are not persisted as decisions. "
            "Run a full analysis on a selected candidate to create an analysis_id."
        ),
    }


@app.get("/api/analyses")
def analyses(limit: int = 50):
    return {"items": store.recent_analyses(limit)}


@app.post("/api/outcomes")
def evaluate_outcome(payload: OutcomeRequest):
    try:
        analysis = store.get_analysis(payload.analysis_id)
        report = analysis["payload"]
        action = analysis["action"]
        entry_price = payload.entry_price or report.get("reference_price")
        if entry_price is None:
            raise ValueError("entry_price is required for analyses created before v0.6.0")

        entry_price = float(entry_price)
        exit_price = float(payload.exit_price)
        if exit_price > entry_price:
            market_direction = "BUY"
        elif exit_price < entry_price:
            market_direction = "SELL"
        else:
            market_direction = "FLAT"

        if action == "HOLD":
            result = "HOLD"
            directional_return_pct = 0.0
        else:
            if market_direction == "FLAT":
                result = "FLAT"
            else:
                result = "WIN" if action == market_direction else "LOSS"
            direction = 1.0 if action == "BUY" else -1.0
            directional_return_pct = (
                (exit_price - entry_price) / entry_price * direction * 100.0
            )

        return store.save_outcome(
            analysis_id=payload.analysis_id,
            evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
            entry_price=entry_price,
            exit_price=exit_price,
            action=action,
            result=result,
            market_direction=market_direction,
            directional_return_pct=round(directional_return_pct, 6),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/outcomes")
def outcomes(limit: int = 100):
    return {"items": store.recent_outcomes(limit)}


@app.get("/api/outcomes/stats")
def outcome_stats():
    return store.outcome_statistics()


@app.get("/api/paper")
def paper_status():
    return paper.snapshot()


@app.post("/api/paper/reset")
def paper_reset():
    return paper.reset()


@app.post("/api/paper/order")
def paper_order(payload: PaperOrderRequest):
    try:
        analysis = store.get_analysis(payload.analysis_id)
        if not bool(analysis["risk_allowed"]):
            raise ValueError("analysis was blocked by Risk Engine")
        if analysis["action"] == "HOLD":
            raise ValueError("HOLD analysis cannot open a trade")
        if analysis["action"] != payload.side:
            raise ValueError("paper side must match persisted analysis decision")
        if analysis["symbol"] != payload.symbol:
            raise ValueError("paper symbol must match persisted analysis")
        order = payload.model_dump(exclude={"analysis_id"})
        trade = paper.place_order(**order)
        trade["analysis_id"] = payload.analysis_id
        return trade
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/paper/settle")
def paper_settle(payload: PaperSettleRequest):
    try:
        return paper.settle(**payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/market/candles")
def market_candles(
    symbol: str = "DEMO",
    timeframe: str = "M5",
    source: Literal["demo", "stored", "twelve"] = "demo",
    count: int = 140,
):
    try:
        provider = demo_market if source == "demo" else stored_market if source == "stored" else twelve_market
        batch = provider.candles(
            symbol=symbol.strip().upper(),
            timeframe=timeframe.strip().upper(),
            count=count,
        )
        return {
            "source": batch.source,
            "symbol": batch.symbol,
            "timeframe": batch.timeframe,
            "candles": batch.candles,
        }
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/market/import")
def market_import(payload: MarketImportRequest):
    try:
        candles = [candle.model_dump() for candle in payload.candles]
        count = store.replace_market_candles(
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            candles=candles,
        )
        return {
            "source": "stored",
            "symbol": payload.symbol.upper(),
            "timeframe": payload.timeframe.upper(),
            "imported": count,
        }
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/watchlist")
def watchlist():
    return {"items": store.list_watchlist()}


@app.post("/api/watchlist/demo-seed")
def watchlist_demo_seed():
    items = [
        ("EURUSD", "M5"),
        ("GBPUSD", "M5"),
        ("USDJPY", "M5"),
        ("XAUUSD", "M5"),
        ("BTCUSD", "M5"),
    ]
    created = [
        store.add_watchlist(symbol=symbol, timeframe=timeframe, source="demo")
        for symbol, timeframe in items
    ]
    return {
        "items": created,
        "warning": "These symbols use synthetic demo candles, not live market data.",
    }


@app.post("/api/watchlist")
def watchlist_add(payload: WatchlistRequest):
    try:
        return store.add_watchlist(**payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/watchlist")
def watchlist_remove(symbol: str, timeframe: str = "M5", source: str = "demo"):
    store.remove_watchlist(symbol=symbol, timeframe=timeframe, source=source)
    return {"removed": True}


@app.get("/api/demo/candles")
def demo_candles(count: int = 120):
    batch = demo_market.candles(symbol="DEMO", timeframe="M5", count=count)
    return {"symbol": batch.symbol, "timeframe": batch.timeframe, "candles": batch.candles}


@app.get("/", response_class=HTMLResponse)
def index():
    path = Path(__file__).parent / "static" / "index.html"
    return path.read_text(encoding="utf-8")


def run():
    import uvicorn
    uvicorn.run("mt5titan.webapp.main:app", host="127.0.0.1", port=8000, reload=False)
