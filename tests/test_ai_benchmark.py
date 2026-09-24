from mt5titan.research import BacktestConfig, StrategySpec
from mt5titan.titan.benchmark import compare_quant_vs_ai
from mt5titan.titan.models import AgentOpinion, AgentVerdict


def bars(count=300):
    rows = []
    price = 100.0
    for i in range(count):
        open_price = price
        price += 0.2 if (i // 100) % 2 == 0 else -0.15
        rows.append({
            "time": i + 1,
            "open": open_price,
            "high": max(open_price, price) + 0.1,
            "low": min(open_price, price) - 0.1,
            "close": price,
            "spread": 0,
        })
    return rows


def buy_opinion():
    return [
        AgentOpinion("technical", AgentVerdict.BUY, 0.9, 0.8),
        AgentOpinion("news", AgentVerdict.BUY, 0.8, 0.5),
        AgentOpinion("macro", AgentVerdict.BUY, 0.8, 0.4),
    ]


def sell_opinion():
    return [
        AgentOpinion("technical", AgentVerdict.SELL, 0.9, -0.8),
        AgentOpinion("news", AgentVerdict.SELL, 0.8, -0.5),
        AgentOpinion("macro", AgentVerdict.SELL, 0.8, -0.4),
    ]


def test_ai_cannot_create_trade_when_quant_is_flat():
    data = bars()
    strategy = StrategySpec("sma_trend", {"fast": 5, "slow": 20})
    replay = {i: buy_opinion() for i in range(len(data))}
    report = compare_quant_vs_ai(
        data,
        strategy,
        replay,
        config=BacktestConfig(cost_bps_per_side=0, use_bar_spread=False),
    )
    assert report["approved_for_orders"] is False


def test_conflicting_ai_can_veto_quant_trade():
    data = bars()
    strategy = StrategySpec("sma_trend", {"fast": 5, "slow": 20})
    replay = {i: sell_opinion() for i in range(len(data))}
    report = compare_quant_vs_ai(
        data,
        strategy,
        replay,
        config=BacktestConfig(cost_bps_per_side=0, use_bar_spread=False),
    )
    assert report["quant_plus_ai"]["trades"] <= report["quant"]["trades"]
