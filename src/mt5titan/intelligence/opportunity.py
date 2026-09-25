"""Opportunity scoring and human-readable trade recommendation."""
from dataclasses import dataclass, asdict

from mt5titan.domain import MarketRegime


@dataclass(frozen=True)
class TradeRecommendation:
    action: str
    opportunity_score: float
    risk_level: str
    entry_price: float
    entry_zone_low: float
    entry_zone_high: float
    invalidation_price: float | None
    horizon: str
    context_risk: str
    context_penalty_pct: float
    timeframe_status: str
    timeframe_adjustment_pct: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        result = asdict(self)
        result["reasons"] = list(self.reasons)
        return result


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _horizon(timeframe: str) -> str:
    return {
        "M1": "3-8 min",
        "M5": "10-30 min",
        "M15": "30-90 min",
        "H1": "2-6 h",
    }.get(timeframe.upper(), "context-dependent")


def build_trade_recommendation(report: dict) -> TradeRecommendation:
    action = str(report["decision"]["action"])
    decision_score = abs(float(report["decision"]["score"])) * 100.0
    confidence = float(report["decision"]["confidence"]) * 100.0
    market_score = float(report["market_score"]["total"])
    regime_confidence = float(report["regime"]["confidence"]) * 100.0
    risk_allowed = bool(report["risk"]["allowed"])

    total = (
        market_score * 0.35
        + decision_score * 0.30
        + confidence * 0.25
        + regime_confidence * 0.10
    )

    external = report.get("external_context") or {}
    news = external.get("news") or {}
    macro = external.get("macro") or {}
    context_penalty = 0.0
    context_risk = "LOW"

    news_risk = str(news.get("risk_level") or "").upper()
    if news.get("available") and news_risk == "HIGH":
        context_penalty += 20.0
        context_risk = "HIGH"
    elif news.get("available") and news_risk == "MEDIUM":
        context_penalty += 8.0
        context_risk = "MEDIUM"

    vix = (macro.get("series") or {}).get("vix") or {}
    if vix.get("available"):
        try:
            vix_value = float(vix["value"])
        except (KeyError, TypeError, ValueError):
            vix_value = 0.0
        if vix_value >= 30.0:
            context_penalty += 12.0
            context_risk = "HIGH"
        elif vix_value >= 20.0:
            context_penalty += 5.0
            if context_risk == "LOW":
                context_risk = "MEDIUM"

    context_penalty = min(context_penalty, 30.0)
    total *= 1.0 - context_penalty / 100.0

    timeframe = report.get("timeframe_confirmation") or {}
    timeframe_status = str(timeframe.get("status") or "NOT_EVALUATED")
    try:
        timeframe_adjustment = float(timeframe.get("adjustment_pct") or 0.0)
    except (TypeError, ValueError):
        timeframe_adjustment = 0.0
    timeframe_adjustment = max(-15.0, min(10.0, timeframe_adjustment))
    total *= 1.0 + timeframe_adjustment / 100.0

    if action == "HOLD":
        total *= 0.35
    if not risk_allowed:
        total *= 0.25

    regime = str(report["regime"]["value"])
    if context_risk == "HIGH" or regime in {
        MarketRegime.HIGH_VOLATILITY.value,
        MarketRegime.UNCERTAIN.value,
        MarketRegime.EVENT.value,
    }:
        risk_level = "HIGH"
    elif market_score >= 75 and confidence >= 65:
        risk_level = "LOW"
    else:
        risk_level = "MEDIUM"

    entry = float(report["reference_price"])
    average_range_pct = max(0.01, float(report["features"]["average_range_pct"]))
    range_value = entry * average_range_pct / 100.0
    zone_half_width = range_value * 0.20

    if action == "BUY":
        invalidation = entry - range_value * 0.90
    elif action == "SELL":
        invalidation = entry + range_value * 0.90
    else:
        invalidation = None

    reasons = [
        f"REGIME:{regime}",
        f"MARKET_SCORE:{market_score:.2f}",
        f"DECISION_CONFIDENCE:{confidence:.1f}",
    ]
    if context_penalty:
        reasons.append(f"CONTEXT_RISK:{context_risk}")
        reasons.append(f"CONTEXT_PENALTY_PCT:{context_penalty:.1f}")
    if timeframe_status != "NOT_EVALUATED":
        reasons.append(f"MTF:{timeframe_status}")
        reasons.append(f"MTF_ADJUSTMENT_PCT:{timeframe_adjustment:.1f}")
    if report.get("ai", {}).get("enabled"):
        committee = report["ai"].get("committee", {})
        reasons.append(f"AI_COMMITTEE:{committee.get('action', 'HOLD')}")
    if not risk_allowed:
        reasons.extend(f"RISK_BLOCK:{reason}" for reason in report["risk"]["reasons"])

    return TradeRecommendation(
        action=action,
        opportunity_score=round(_clamp(total), 2),
        risk_level=risk_level,
        entry_price=round(entry, 6),
        entry_zone_low=round(entry - zone_half_width, 6),
        entry_zone_high=round(entry + zone_half_width, 6),
        invalidation_price=None if invalidation is None else round(invalidation, 6),
        horizon=_horizon(str(report["timeframe"])),
        context_risk=context_risk,
        context_penalty_pct=round(context_penalty, 2),
        timeframe_status=timeframe_status,
        timeframe_adjustment_pct=round(timeframe_adjustment, 2),
        reasons=tuple(reasons),
    )
