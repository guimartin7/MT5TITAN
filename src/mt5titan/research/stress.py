"""Fixed stress scenarios for costs and spread assumptions."""
from dataclasses import dataclass

from .backtest import BacktestConfig, run_backtest
from .strategies import StrategySpec


@dataclass(frozen=True)
class StressScenario:
    name: str
    cost_bps_per_side: float
    spread_multiplier: float = 1.0


DEFAULT_SCENARIOS = (
    StressScenario("baseline", 2.0, 1.0),
    StressScenario("adverse", 4.0, 1.5),
    StressScenario("severe", 6.0, 2.0),
)


def _scaled_bars(bars, multiplier: float):
    if multiplier <= 0:
        raise ValueError("spread multiplier must be positive")
    rows = []
    for bar in bars:
        row = dict(bar)
        try:
            row["spread"] = float(row.get("spread", 0.0)) * multiplier
        except (TypeError, ValueError):
            row["spread"] = 0.0
        rows.append(row)
    return rows


def run_stress_test(
    bars,
    strategy: StrategySpec,
    *,
    base_config: BacktestConfig | None = None,
    scenarios=DEFAULT_SCENARIOS,
) -> dict:
    base = base_config or BacktestConfig()
    results = []
    for scenario in scenarios:
        config = BacktestConfig(
            initial_equity=base.initial_equity,
            cost_bps_per_side=scenario.cost_bps_per_side,
            point=base.point,
            use_bar_spread=base.use_bar_spread,
            periods_per_year=base.periods_per_year,
        )
        report = run_backtest(_scaled_bars(bars, scenario.spread_multiplier), strategy, config)
        results.append({
            "name": scenario.name,
            "cost_bps_per_side": scenario.cost_bps_per_side,
            "spread_multiplier": scenario.spread_multiplier,
            "metrics": report["metrics"],
        })

    robust = all(item["metrics"]["return_pct"] > 0 for item in results)
    return {
        "mode": "FIXED_STRESS_TEST",
        "strategy": strategy.name,
        "scenarios": results,
        "positive_return_all_scenarios": robust,
        "warning": "Stress scenarios are fixed and must not be tuned after viewing results.",
    }
