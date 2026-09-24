"""Simple baselines used to judge whether complexity adds value."""
from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineResult:
    name: str
    return_pct: float
    final_equity: float


def no_trade(initial_equity: float = 10_000.0) -> BaselineResult:
    if initial_equity <= 0:
        raise ValueError("initial_equity must be positive")
    return BaselineResult("no_trade", 0.0, initial_equity)


def buy_and_hold(
    bars,
    *,
    initial_equity: float = 10_000.0,
    cost_bps_per_side: float = 2.0,
    point: float = 0.0,
    use_bar_spread: bool = True,
) -> BaselineResult:
    if len(bars) < 2:
        raise ValueError("at least two bars are required")
    fee = cost_bps_per_side / 10_000.0

    first = bars[0]
    last = bars[-1]
    first_spread = float(first.get("spread", 0.0)) * point if use_bar_spread else 0.0
    last_spread = float(last.get("spread", 0.0)) * point if use_bar_spread else 0.0

    entry = (float(first["open"]) + first_spread / 2.0) * (1.0 + fee)
    exit_price = (float(last["close"]) - last_spread / 2.0) * (1.0 - fee)
    final_equity = initial_equity / entry * exit_price
    return BaselineResult(
        "buy_and_hold",
        (final_equity / initial_equity - 1.0) * 100.0,
        final_equity,
    )


def compare_to_baselines(
    bars,
    strategy_metrics: dict,
    *,
    initial_equity: float = 10_000.0,
    cost_bps_per_side: float = 2.0,
    point: float = 0.0,
    use_bar_spread: bool = True,
) -> dict:
    hold = buy_and_hold(
        bars,
        initial_equity=initial_equity,
        cost_bps_per_side=cost_bps_per_side,
        point=point,
        use_bar_spread=use_bar_spread,
    )
    idle = no_trade(initial_equity)
    strategy_return = float(strategy_metrics["return_pct"])
    return {
        "strategy_return_pct": strategy_return,
        "buy_and_hold_return_pct": round(hold.return_pct, 4),
        "no_trade_return_pct": idle.return_pct,
        "alpha_vs_buy_hold_pct_points": round(strategy_return - hold.return_pct, 4),
        "alpha_vs_no_trade_pct_points": round(strategy_return, 4),
    }
