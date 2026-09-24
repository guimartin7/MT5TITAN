from mt5titan.research import BacktestConfig, Candidate, StrategySpec, evaluate_candidates, run_backtest, walk_forward


def bars(count=400):
    rows = []
    price = 100.0
    for i in range(count):
        drift = 0.2 if (i // 80) % 2 == 0 else -0.15
        open_price = price
        price = max(10.0, price + drift)
        rows.append({
            "time": i + 1,
            "open": open_price,
            "high": max(open_price, price) + 0.1,
            "low": min(open_price, price) - 0.1,
            "close": price,
            "spread": 1,
        })
    return rows


def test_backtest_executes_after_signal_bar():
    report = run_backtest(
        bars(),
        StrategySpec("sma_trend", {"fast": 5, "slow": 20}),
        BacktestConfig(cost_bps_per_side=0, use_bar_spread=False),
    )
    assert report["metrics"]["trades"] > 0
    assert report["trade_log"][0]["entry_time"] > 20


def test_three_way_protocol_keeps_holdout_for_selected_candidate_only():
    candidates = [
        Candidate("fast", StrategySpec("sma_trend", {"fast": 5, "slow": 20})),
        Candidate("slow", StrategySpec("sma_trend", {"fast": 10, "slow": 30})),
    ]
    report = evaluate_candidates(bars(), candidates, BacktestConfig(cost_bps_per_side=0))
    assert report["development_bars"] == 240
    assert report["validation_bars"] == 80
    assert report["holdout_bars"] == 80
    assert report["selected_candidate"] in {"fast", "slow"}


def test_walk_forward_builds_multiple_test_windows():
    report = walk_forward(
        bars(500),
        StrategySpec("momentum_breakout", {"window": 10}),
        train_size=200,
        test_size=50,
        step_size=50,
        config=BacktestConfig(cost_bps_per_side=0),
    )
    assert report["window_count"] >= 5
