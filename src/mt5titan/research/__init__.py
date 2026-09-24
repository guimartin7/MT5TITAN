"""Quantitative research engine."""

from .backtest import BacktestConfig, run_backtest
from .baselines import BaselineResult, buy_and_hold, compare_to_baselines, no_trade
from .metrics import performance_metrics
from .protocols import Candidate, evaluate_candidates, walk_forward
from .strategies import StrategySpec, build_directions
from .stress import DEFAULT_SCENARIOS, StressScenario, run_stress_test

__all__ = [
    "BacktestConfig",
    "BaselineResult",
    "Candidate",
    "DEFAULT_SCENARIOS",
    "StrategySpec",
    "StressScenario",
    "build_directions",
    "buy_and_hold",
    "compare_to_baselines",
    "evaluate_candidates",
    "no_trade",
    "performance_metrics",
    "run_backtest",
    "run_stress_test",
    "walk_forward",
]
