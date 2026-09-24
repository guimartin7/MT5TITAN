from mt5titan.research.backtest import BacktestConfig, run_backtest
from mt5titan.research.baselines import buy_and_hold, compare_to_baselines, no_trade
from mt5titan.research.stress import run_stress_test
from mt5titan.research.strategies import StrategySpec


def bars(count=250):
    rows = []
    price = 100.0
    for i in range(count):
        open_price = price
        price += 0.15
        rows.append({
            "time": i + 1,
            "open": open_price,
            "high": price + 0.1,
            "low": open_price - 0.1,
            "close": price,
            "spread": 1,
        })
    return rows


def test_no_trade_is_zero_return():
    baseline = no_trade(5000)
    assert baseline.return_pct == 0
    assert baseline.final_equity == 5000


def test_buy_hold_is_reproducible():
    first = buy_and_hold(bars(), cost_bps_per_side=0, use_bar_spread=False)
    second = buy_and_hold(bars(), cost_bps_per_side=0, use_bar_spread=False)
    assert first == second
    assert first.return_pct > 0


def test_stress_has_fixed_scenarios():
    report = run_stress_test(
        bars(),
        StrategySpec("sma_trend", {"fast": 5, "slow": 20}),
        base_config=BacktestConfig(point=0.01),
    )
    assert [row["name"] for row in report["scenarios"]] == ["baseline", "adverse", "severe"]


def test_strategy_can_be_compared_to_baselines():
    data = bars()
    report = run_backtest(
        data,
        StrategySpec("sma_trend", {"fast": 5, "slow": 20}),
        BacktestConfig(cost_bps_per_side=0, use_bar_spread=False),
    )
    comparison = compare_to_baselines(
        data,
        report["metrics"],
        cost_bps_per_side=0,
        use_bar_spread=False,
    )
    assert "alpha_vs_buy_hold_pct_points" in comparison
