"""Performance metrics with explicit assumptions."""
from math import sqrt
from statistics import mean, pstdev


def _max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    worst = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, equity / peak - 1.0)
    return worst * 100.0


def performance_metrics(
    initial_equity: float,
    final_equity: float,
    trades: list[dict],
    equity_curve: list[float],
    *,
    period_returns: list[float] | None = None,
    periods_per_year: float | None = None,
) -> dict:
    pnls = [float(t["pnl"]) for t in trades]
    returns = [float(t["return_pct"]) / 100.0 for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    expectancy = mean(pnls) if pnls else 0.0
    payoff = (mean(wins) / abs(mean(losses))) if wins and losses else None
    profit_factor = gross_profit / gross_loss if gross_loss else (None if not gross_profit else float("inf"))

    max_consecutive_losses = current = 0
    for pnl in pnls:
        current = current + 1 if pnl < 0 else 0
        max_consecutive_losses = max(max_consecutive_losses, current)

    max_dd = abs(_max_drawdown(equity_curve))
    total_return_pct = (final_equity / initial_equity - 1.0) * 100.0
    calmar = total_return_pct / max_dd if max_dd > 0 else None

    sharpe = sortino = None
    series = list(period_returns or [])
    if periods_per_year and len(series) >= 2:
        deviation = pstdev(series)
        if deviation > 0:
            sharpe = mean(series) / deviation * sqrt(periods_per_year)
        downside = [min(0.0, value) for value in series]
        downside_dev = sqrt(sum(v * v for v in downside) / len(downside))
        if downside_dev > 0:
            sortino = mean(series) / downside_dev * sqrt(periods_per_year)

    return {
        "initial_equity": round(initial_equity, 2),
        "final_equity": round(final_equity, 2),
        "return_pct": round(total_return_pct, 4),
        "trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
        "expectancy": round(expectancy, 6),
        "profit_factor": None if profit_factor is None else ("infinite" if profit_factor == float("inf") else round(profit_factor, 4)),
        "payoff_ratio": None if payoff is None else round(payoff, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "max_consecutive_losses": max_consecutive_losses,
        "sharpe": None if sharpe is None else round(sharpe, 4),
        "sortino": None if sortino is None else round(sortino, 4),
        "calmar": None if calmar is None else round(calmar, 4),
        "metric_note": "Sharpe/Sortino are annualized only when periods_per_year is provided.",
    }
