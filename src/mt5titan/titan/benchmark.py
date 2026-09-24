"""Compare deterministic quant signals against quant + AI committee."""
from dataclasses import dataclass

from mt5titan.domain import DecisionAction, Signal
from mt5titan.research.backtest import BacktestConfig, run_backtest
from mt5titan.research.metrics import performance_metrics
from mt5titan.research.strategies import StrategySpec, build_directions

from .committee import AICommittee
from .models import AgentOpinion


@dataclass(frozen=True)
class PromotionPolicy:
    min_expectancy_delta: float = 0.0
    min_profit_factor_delta: float = 0.0
    max_drawdown_increase_pct_points: float = 0.0
    require_non_negative_return_delta: bool = True


def _committee_direction(committee: AICommittee, opinions: list[AgentOpinion]) -> int:
    signal = committee.aggregate(opinions)
    if signal.action == DecisionAction.BUY:
        return 1
    if signal.action == DecisionAction.SELL:
        return -1
    return 0


def combine_quant_and_ai(
    quant_direction: int,
    committee_direction: int,
) -> int:
    """Conservative fusion: AI may confirm or veto, but cannot invent a trade alone."""
    if quant_direction == 0:
        return 0
    if committee_direction == 0:
        return 0
    if committee_direction != quant_direction:
        return 0
    return quant_direction


def fused_directions(
    quant_directions: list[int],
    replay: dict[int, list[AgentOpinion]],
    committee: AICommittee | None = None,
) -> list[int]:
    committee = committee or AICommittee()
    result = []
    for index, quant_direction in enumerate(quant_directions):
        opinions = replay.get(index)
        if not opinions:
            result.append(0)
            continue
        ai_direction = _committee_direction(committee, opinions)
        result.append(combine_quant_and_ai(int(quant_direction), ai_direction))
    return result


def _run_direction_backtest(bars, directions, config: BacktestConfig) -> dict:
    if len(bars) != len(directions):
        raise ValueError("bars and directions length mismatch")
    equity = config.initial_equity
    equity_curve = [equity]
    trades = []
    position = 0
    entry_price = None
    entry_equity = None
    entry_time = None
    period_returns = []

    def bar_value(bar, key, default=0.0):
        try:
            return bar[key]
        except (KeyError, IndexError, TypeError, ValueError):
            return default

    def price(index, direction, entering):
        mid = float(bars[index]["open"])
        spread = float(bar_value(bars[index], "spread", 0.0)) * config.point if config.use_bar_spread else 0.0
        buying = (direction == 1 and entering) or (direction == -1 and not entering)
        quoted = mid + spread / 2 if buying else mid - spread / 2
        fee = config.cost_bps_per_side / 10_000.0
        return quoted * (1.0 + fee if buying else 1.0 - fee)

    def close(index):
        nonlocal equity, position, entry_price, entry_equity, entry_time
        if position == 0:
            return
        exit_price = price(index, position, False)
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
        target = int(directions[index - 1])
        if target != position:
            if position != 0:
                close(index)
            if target != 0:
                position = target
                entry_price = price(index, position, True)
                entry_equity = equity
                entry_time = int(bars[index]["time"])

        previous = equity_curve[-1]
        marked = equity
        if position != 0 and entry_price:
            close_px = float(bars[index]["close"])
            open_return = (close_px - entry_price) / entry_price * position
            marked = entry_equity * (1.0 + open_return)
        equity_curve.append(marked)
        period_returns.append(marked / previous - 1.0 if previous else 0.0)

    if position != 0:
        close(len(bars) - 1)
        equity_curve[-1] = equity

    return {
        "metrics": performance_metrics(
            config.initial_equity,
            equity,
            trades,
            equity_curve,
            period_returns=period_returns,
            periods_per_year=config.periods_per_year,
        ),
        "trade_log": trades,
        "equity_curve": equity_curve,
    }


def compare_quant_vs_ai(
    bars,
    strategy: StrategySpec,
    replay: dict[int, list[AgentOpinion]],
    *,
    config: BacktestConfig | None = None,
    committee: AICommittee | None = None,
    policy: PromotionPolicy | None = None,
) -> dict:
    config = config or BacktestConfig()
    policy = policy or PromotionPolicy()
    quant = run_backtest(bars, strategy, config)
    quant_directions = build_directions(bars, strategy)
    fused = fused_directions(quant_directions, replay, committee)
    hybrid = _run_direction_backtest(bars, fused, config)

    qm = quant["metrics"]
    hm = hybrid["metrics"]

    return_delta = float(hm["return_pct"]) - float(qm["return_pct"])
    expectancy_delta = float(hm["expectancy"]) - float(qm["expectancy"])

    def pf(value):
        if value == "infinite":
            return float("inf")
        return 0.0 if value is None else float(value)

    profit_factor_delta = pf(hm["profit_factor"]) - pf(qm["profit_factor"])
    drawdown_increase = float(hm["max_drawdown_pct"]) - float(qm["max_drawdown_pct"])

    checks = {
        "return_not_worse": return_delta >= 0 if policy.require_non_negative_return_delta else True,
        "expectancy_improved": expectancy_delta >= policy.min_expectancy_delta,
        "profit_factor_improved": profit_factor_delta >= policy.min_profit_factor_delta,
        "drawdown_not_worse": drawdown_increase <= policy.max_drawdown_increase_pct_points,
    }
    failed = [name for name, passed in checks.items() if not passed]

    return {
        "quant": qm,
        "quant_plus_ai": hm,
        "deltas": {
            "return_pct_points": round(return_delta, 4),
            "expectancy": round(expectancy_delta, 6),
            "profit_factor": (
                "infinite"
                if profit_factor_delta == float("inf")
                else round(profit_factor_delta, 4)
            ),
            "max_drawdown_pct_points": round(drawdown_increase, 4),
        },
        "promotion": {
            "verdict": "PROMOTE_AI_EXPERIMENT" if not failed else "REJECT_AI_EXPERIMENT",
            "checks": checks,
            "failed_checks": failed,
        },
        "approved_for_orders": False,
        "warning": "Promotion only advances research. It never authorizes Demo or real execution.",
    }
