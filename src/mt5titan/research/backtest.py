"""Shared directional backtest engine.

Signals are generated from candle N and executed only at candle N+1 open.
"""
from dataclasses import dataclass

from .metrics import performance_metrics
from .strategies import StrategySpec, build_directions


@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: float = 10_000.0
    cost_bps_per_side: float = 2.0
    point: float = 0.0
    use_bar_spread: bool = True
    periods_per_year: float | None = None


def _bar_value(bar, key, default=0.0):
    try:
        return bar[key]
    except (KeyError, IndexError, TypeError, ValueError):
        return default


def _execution_price(bar, direction: int, entering: bool, config: BacktestConfig) -> float:
    mid = float(bar["open"])
    spread = float(_bar_value(bar, "spread", 0.0)) * config.point if config.use_bar_spread else 0.0
    buying = (direction == 1 and entering) or (direction == -1 and not entering)
    quoted = mid + spread / 2 if buying else mid - spread / 2
    fee = config.cost_bps_per_side / 10_000.0
    return quoted * (1.0 + fee if buying else 1.0 - fee)


def run_backtest(bars, strategy: StrategySpec, config: BacktestConfig | None = None) -> dict:
    config = config or BacktestConfig()
    if config.initial_equity <= 0 or config.cost_bps_per_side < 0:
        raise ValueError("invalid backtest configuration")
    if len(bars) < 5:
        raise ValueError("insufficient history")

    desired = build_directions(bars, strategy)
    equity = config.initial_equity
    equity_curve = [equity]
    period_returns: list[float] = []
    trades: list[dict] = []
    position = 0
    entry_price = None
    entry_equity = None
    entry_time = None

    def close_trade(index: int):
        nonlocal equity, position, entry_price, entry_equity, entry_time
        if position == 0:
            return
        exit_price = _execution_price(bars[index], position, False, config)
        raw_return = (exit_price - entry_price) / entry_price * position
        pnl = entry_equity * raw_return
        equity = entry_equity + pnl
        trades.append({
            "direction": position,
            "entry_time": int(entry_time),
            "exit_time": int(bars[index]["time"]),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "return_pct": raw_return * 100.0,
        })
        position = 0
        entry_price = entry_equity = entry_time = None

    for index in range(1, len(bars)):
        target = int(desired[index - 1])
        if target != position:
            if position != 0:
                close_trade(index)
            if target != 0:
                position = target
                entry_price = _execution_price(bars[index], position, True, config)
                entry_equity = equity
                entry_time = int(bars[index]["time"])

        previous_equity = equity_curve[-1]
        marked = equity
        if position != 0 and entry_price:
            close = float(bars[index]["close"])
            open_return = (close - entry_price) / entry_price * position
            marked = entry_equity * (1.0 + open_return)
        equity_curve.append(marked)
        period_returns.append(marked / previous_equity - 1.0 if previous_equity else 0.0)

    if position != 0:
        close_trade(len(bars) - 1)
        equity_curve[-1] = equity

    metrics = performance_metrics(
        config.initial_equity,
        equity,
        trades,
        equity_curve,
        period_returns=period_returns,
        periods_per_year=config.periods_per_year,
    )
    return {
        "strategy": strategy.name,
        "parameters": dict(strategy.parameters),
        "config": {
            "initial_equity": config.initial_equity,
            "cost_bps_per_side": config.cost_bps_per_side,
            "point": config.point,
            "use_bar_spread": config.use_bar_spread,
            "periods_per_year": config.periods_per_year,
        },
        "metrics": metrics,
        "trade_log": trades,
        "equity_curve": equity_curve,
    }
