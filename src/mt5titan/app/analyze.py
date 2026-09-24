"""End-to-end MT5TITAN analysis runner.

Connects to MT5 Demo, reads closed candles, builds intelligence context, optionally
calls the configured AI provider, evaluates the deterministic Decision Engine and
Risk Engine, persists an audit report, and NEVER sends an order.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from mt5titan.adapters import MT5Adapter
from mt5titan.domain import DecisionAction
from mt5titan.intelligence import DecisionEngine, build_features, detect_regime, score_market
from mt5titan.intelligence.signals import strategy_signal
from mt5titan.research import StrategySpec
from mt5titan.risk import RiskEngine, RiskLimits, RiskState
from mt5titan.titan import AICommittee, OpinionReplayStore, TitanExperiment, build_agent_context
from mt5titan.titan.providers import OpenAIProvider


TIMEFRAMES = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "H1": "TIMEFRAME_H1",
}


def _strategy_specs() -> tuple[StrategySpec, ...]:
    return (
        StrategySpec("sma_trend", {"fast": 9, "slow": 21}),
        StrategySpec("momentum_breakout", {"window": 20}),
        StrategySpec("rsi_mean_reversion", {"window": 14, "lower": 30, "upper": 70, "exit": 50}),
    )


def _serialize_decision(decision) -> dict:
    return {
        "decision_id": decision.decision_id,
        "symbol": decision.symbol,
        "action": decision.action.value,
        "confidence": decision.confidence,
        "score": decision.score,
        "contributors": decision.contributors,
        "reason_codes": list(decision.reason_codes),
        "metadata": decision.metadata,
    }


def run_analysis(
    api,
    *,
    terminal_path: str,
    symbol: str,
    timeframe_name: str,
    bars_count: int,
    use_ai: bool,
    output_dir: Path,
    replay_dir: Path,
) -> dict:
    adapter = MT5Adapter(api, terminal_path)
    adapter.connect()
    try:
        adapter.require_demo()
        timeframe = getattr(api, TIMEFRAMES[timeframe_name])
        bars = adapter.closed_bars(symbol, timeframe, bars_count)
        snapshot, feed_health = adapter.market_snapshot(symbol, timeframe_name)

        features = build_features(bars)
        regime = detect_regime(features)
        market = score_market(features, regime)

        quant_signals = [
            strategy_signal(bars, spec, source=spec.name)
            for spec in _strategy_specs()
        ]

        event_risk = {"blocked": False, "caution": False, "relevant_events": []}
        portfolio = {"allowed": True, "blockers": [], "open_positions": 0}

        ai_signal = None
        replay_path = replay_dir / f"{symbol}-{timeframe_name}-opinions.jsonl"

        if use_ai:
            context = build_agent_context(
                symbol=symbol,
                timeframe=timeframe_name,
                timestamp=snapshot.timestamp,
                features=features,
                regime=regime,
                market_score=market,
                strategy_signals={signal.source: signal.score for signal in quant_signals},
                event_risk=event_risk,
                portfolio=portfolio,
            )
            provider = OpenAIProvider()
            experiment = TitanExperiment(provider, OpinionReplayStore(replay_path))
            key = f"{symbol}:{timeframe_name}:{snapshot.timestamp}"
            result = experiment.run_context(key=key, context=context)
            ai_signal = AICommittee().aggregate(list(result.opinions))

        all_signals = list(quant_signals)
        if ai_signal is not None:
            all_signals.append(ai_signal)

        decision = DecisionEngine().decide(
            symbol=symbol,
            timestamp=snapshot.timestamp,
            signals=all_signals,
            regime=regime,
            market_score=market,
        )

        risk_state = RiskState(
            feed_healthy=bool(feed_health["healthy"]),
            kill_switch=False,
            conflicting_exposure=not bool(portfolio["allowed"]),
        )
        risk = RiskEngine(
            RiskLimits(
                max_daily_loss_pct=1.0,
                max_drawdown_pct=2.0,
                max_entries_per_day=5,
                min_confidence=0.55,
            )
        ).evaluate(decision, snapshot, risk_state)

        report = {
            "mode": "ANALYSIS_ONLY_NO_ORDER_SEND",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "timeframe": timeframe_name,
            "bars": len(bars),
            "snapshot": {
                "timestamp": snapshot.timestamp,
                "bid": snapshot.bid,
                "ask": snapshot.ask,
                "spread": snapshot.spread,
            },
            "feed_health": feed_health,
            "features": features.to_dict(),
            "regime": {
                "value": regime.regime.value,
                "confidence": regime.confidence,
                "reasons": list(regime.reasons),
            },
            "market_score": asdict(market),
            "quant_signals": [
                {
                    "source": signal.source,
                    "action": signal.action.value,
                    "confidence": signal.confidence,
                    "score": signal.score,
                    "reasons": list(signal.reasons),
                }
                for signal in quant_signals
            ],
            "ai_signal": None if ai_signal is None else {
                "action": ai_signal.action.value,
                "confidence": ai_signal.confidence,
                "score": ai_signal.score,
                "reasons": list(ai_signal.reasons),
            },
            "decision": _serialize_decision(decision),
            "risk": {
                "allowed": risk.allowed,
                "reasons": list(risk.reasons),
                "risk_fraction": risk.risk_fraction,
            },
            "execution": {
                "enabled": False,
                "order_send_called": False,
                "note": "This runner intentionally has no execution gateway.",
            },
            "replay_path": str(replay_path) if use_ai else None,
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_path = output_dir / f"analysis-{symbol}-{timeframe_name}-{stamp}.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report
    finally:
        adapter.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal", default=r"C:\Program Files\MetaTrader 5\terminal64.exe")
    parser.add_argument("--symbol", default="WINV26")
    parser.add_argument("--timeframe", choices=tuple(TIMEFRAMES), default="M5")
    parser.add_argument("--bars", type=int, default=250)
    parser.add_argument("--ai", action="store_true", help="Enable configured OpenAI agents.")
    parser.add_argument("--reports", default="reports")
    parser.add_argument("--replays", default="replays")
    args = parser.parse_args()

    if args.bars < 80:
        parser.error("--bars must be at least 80")

    import MetaTrader5 as mt5

    try:
        report = run_analysis(
            mt5,
            terminal_path=args.terminal,
            symbol=args.symbol,
            timeframe_name=args.timeframe,
            bars_count=args.bars,
            use_ai=args.ai,
            output_dir=Path(args.reports),
            replay_dir=Path(args.replays),
        )
    except Exception as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}, ensure_ascii=False, indent=2))
        return 1

    printable = dict(report)
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
