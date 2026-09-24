from mt5titan.intelligence.opportunity import build_trade_recommendation


def report(action="BUY", risk_allowed=True, ai=False):
    return {
        "timeframe": "M5",
        "reference_price": 100.0,
        "features": {"average_range_pct": 0.5},
        "market_score": {"total": 80.0},
        "regime": {"value": "TRENDING", "confidence": 0.8},
        "decision": {
            "action": action,
            "confidence": 0.75,
            "score": 0.7 if action == "BUY" else -0.7 if action == "SELL" else 0.0,
        },
        "risk": {"allowed": risk_allowed, "reasons": [] if risk_allowed else ["blocked"]},
        "ai": (
            {"enabled": True, "committee": {"action": action}}
            if ai
            else {"enabled": False}
        ),
    }


def test_buy_recommendation_has_entry_zone_and_invalidation():
    rec = build_trade_recommendation(report("BUY"))
    assert rec.action == "BUY"
    assert rec.opportunity_score > 0
    assert rec.entry_zone_low < rec.entry_price < rec.entry_zone_high
    assert rec.invalidation_price < rec.entry_price
    assert rec.horizon == "10-30 min"


def test_sell_invalidation_is_above_entry():
    rec = build_trade_recommendation(report("SELL"))
    assert rec.invalidation_price > rec.entry_price


def test_hold_and_blocked_are_penalized():
    good = build_trade_recommendation(report("BUY", True))
    hold = build_trade_recommendation(report("HOLD", True))
    blocked = build_trade_recommendation(report("BUY", False))
    assert hold.opportunity_score < good.opportunity_score
    assert blocked.opportunity_score < good.opportunity_score
