"""Quantitative research engine."""

from .backtest import BacktestConfig, run_backtest
from .metrics import performance_metrics
from .protocols import Candidate, evaluate_candidates, walk_forward
from .strategies import StrategySpec, build_directions

__all__ = [
    "BacktestConfig",
    "Candidate",
    "StrategySpec",
    "build_directions",
    "evaluate_candidates",
    "performance_metrics",
    "run_backtest",
    "walk_forward",
]
