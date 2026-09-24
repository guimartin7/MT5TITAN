"""Deterministic strategy signals used by research and paper trading."""
from dataclasses import dataclass, field

from .indicators import relative_strength_index, simple_moving_average


@dataclass(frozen=True)
class StrategySpec:
    name: str
    parameters: dict = field(default_factory=dict)


def build_directions(bars, spec: StrategySpec) -> list[int]:
    closes = [float(bar["close"]) for bar in bars]
    directions = [0] * len(bars)
    p = dict(spec.parameters)

    if spec.name == "sma_trend":
        fast = int(p.get("fast", 20))
        slow = int(p.get("slow", 50))
        min_gap = float(p.get("min_gap", 0.0))
        if not 1 <= fast < slow:
            raise ValueError("SMA requires 1 <= fast < slow")
        fast_ma = simple_moving_average(closes, fast)
        slow_ma = simple_moving_average(closes, slow)
        for i in range(slow - 1, len(bars)):
            gap = float(fast_ma[i]) - float(slow_ma[i])
            if abs(gap) >= min_gap and gap != 0:
                directions[i] = 1 if gap > 0 else -1
        return directions

    if spec.name == "momentum_breakout":
        window = int(p.get("window", 40))
        if window < 2:
            raise ValueError("breakout window must be at least 2")
        current = 0
        for i in range(window, len(bars)):
            previous = bars[i - window:i]
            upper = max(float(bar["high"]) for bar in previous)
            lower = min(float(bar["low"]) for bar in previous)
            if closes[i] > upper:
                current = 1
            elif closes[i] < lower:
                current = -1
            directions[i] = current
        return directions

    if spec.name == "rsi_mean_reversion":
        window = int(p.get("window", 14))
        lower = float(p.get("lower", 30))
        upper = float(p.get("upper", 70))
        exit_level = float(p.get("exit", 50))
        if not 0 < lower < exit_level < upper < 100:
            raise ValueError("invalid RSI levels")
        rsi = relative_strength_index(closes, window)
        current = 0
        for i in range(window, len(bars)):
            value = rsi[i]
            if value is None:
                continue
            if current == 0 and value < lower:
                current = 1
            elif current == 0 and value > upper:
                current = -1
            elif current == 1 and value >= exit_level:
                current = 0
            elif current == -1 and value <= exit_level:
                current = 0
            directions[i] = current
        return directions

    raise ValueError(f"unknown strategy: {spec.name}")
