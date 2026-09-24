"""Temporal validation protocols that protect against leakage."""
from dataclasses import dataclass

from .backtest import BacktestConfig, run_backtest
from .strategies import StrategySpec


@dataclass(frozen=True)
class Candidate:
    name: str
    strategy: StrategySpec


def _compact(report: dict) -> dict:
    return {
        "strategy": report["strategy"],
        "parameters": report["parameters"],
        "metrics": report["metrics"],
    }


def evaluate_candidates(
    bars,
    candidates: list[Candidate],
    config: BacktestConfig | None = None,
    *,
    development_ratio: float = 0.60,
    validation_ratio: float = 0.20,
) -> dict:
    if len(bars) < 300:
        raise ValueError("use at least 300 bars for three-way evaluation")
    if not candidates:
        raise ValueError("at least one candidate is required")
    if development_ratio <= 0 or validation_ratio <= 0 or development_ratio + validation_ratio >= 1:
        raise ValueError("invalid temporal split")

    first = int(len(bars) * development_ratio)
    second = int(len(bars) * (development_ratio + validation_ratio))
    development, validation, holdout = bars[:first], bars[first:second], bars[second:]

    rows = []
    for candidate in candidates:
        dev = run_backtest(development, candidate.strategy, config)
        val = run_backtest(validation, candidate.strategy, config)
        rows.append({
            "name": candidate.name,
            "strategy": candidate.strategy.name,
            "parameters": dict(candidate.strategy.parameters),
            "development": _compact(dev),
            "validation": _compact(val),
        })

    selected = max(rows, key=lambda row: row["validation"]["metrics"]["return_pct"])
    selected_spec = next(c.strategy for c in candidates if c.name == selected["name"])
    holdout_result = run_backtest(holdout, selected_spec, config)

    return {
        "protocol": "chronological development / validation / untouched holdout",
        "selection_rule": "highest net validation return; ties preserve candidate order",
        "development_bars": len(development),
        "validation_bars": len(validation),
        "holdout_bars": len(holdout),
        "candidates": rows,
        "selected_candidate": selected["name"],
        "holdout_result": _compact(holdout_result),
        "warning": "After this report, this holdout must not be used for parameter tuning.",
    }


def walk_forward(
    bars,
    strategy: StrategySpec,
    *,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
    config: BacktestConfig | None = None,
) -> dict:
    if train_size < 50 or test_size < 10:
        raise ValueError("walk-forward windows are too small")
    step = step_size or test_size
    if step < 1:
        raise ValueError("step_size must be positive")

    windows = []
    start = 0
    while start + train_size + test_size <= len(bars):
        train = bars[start:start + train_size]
        test = bars[start + train_size:start + train_size + test_size]
        train_result = run_backtest(train, strategy, config)
        test_result = run_backtest(test, strategy, config)
        windows.append({
            "start_index": start,
            "train_end_index": start + train_size - 1,
            "test_end_index": start + train_size + test_size - 1,
            "train": _compact(train_result),
            "test": _compact(test_result),
        })
        start += step

    if not windows:
        raise ValueError("not enough bars for one walk-forward window")

    profitable = sum(w["test"]["metrics"]["return_pct"] > 0 for w in windows)
    return {
        "windows": windows,
        "window_count": len(windows),
        "profitable_test_windows": profitable,
        "profitable_test_window_pct": round(profitable / len(windows) * 100, 2),
        "warning": "Walk-forward evaluates stability; it does not authorize execution.",
    }
