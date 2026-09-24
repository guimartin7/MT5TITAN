"""Translate research strategies into strength-aware normalized Signals."""
from mt5titan.domain import DecisionAction, Signal
from mt5titan.research.indicators import relative_strength_index, simple_moving_average
from mt5titan.research.strategies import StrategySpec, build_directions


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _average_range_pct(bars, window: int = 20) -> float:
    sample = bars[-window:]
    values = []
    for bar in sample:
        close = float(bar["close"])
        if close > 0:
            values.append((float(bar["high"]) - float(bar["low"])) / close * 100.0)
    return sum(values) / len(values) if values else 0.0


def _signal_strength(bars, spec: StrategySpec, direction: int) -> tuple[float, tuple[str, ...]]:
    if not direction:
        return 0.0, (f"STRATEGY:{spec.name}", "NO_ACTIVE_DIRECTION")

    p = dict(spec.parameters)
    closes = [float(bar["close"]) for bar in bars]
    latest = closes[-1]
    average_range_pct = max(_average_range_pct(bars), 0.0001)

    if spec.name == "sma_trend":
        fast = int(p.get("fast", 20))
        slow = int(p.get("slow", 50))
        fast_value = simple_moving_average(closes, fast)[-1]
        slow_value = simple_moving_average(closes, slow)[-1]
        if fast_value is None or slow_value is None or not slow_value:
            return 0.0, (f"STRATEGY:{spec.name}", "WARMUP")
        gap_pct = abs(float(fast_value) / float(slow_value) - 1.0) * 100.0
        strength = _clamp(gap_pct / (average_range_pct * 1.5))
        return strength, (
            f"STRATEGY:{spec.name}",
            f"SMA_GAP_PCT:{gap_pct:.4f}",
            f"AVG_RANGE_PCT:{average_range_pct:.4f}",
        )

    if spec.name == "momentum_breakout":
        window = int(p.get("window", 40))
        previous = bars[-1 - window:-1]
        if len(previous) < window:
            return 0.0, (f"STRATEGY:{spec.name}", "WARMUP")
        upper = max(float(bar["high"]) for bar in previous)
        lower = min(float(bar["low"]) for bar in previous)
        distance = latest - upper if direction > 0 else lower - latest
        distance_pct = max(0.0, distance / latest * 100.0) if latest else 0.0
        # A persisted breakout can sit back near its boundary; retain a modest floor.
        strength = _clamp(0.25 + distance_pct / average_range_pct)
        return strength, (
            f"STRATEGY:{spec.name}",
            f"BREAKOUT_DISTANCE_PCT:{distance_pct:.4f}",
            f"AVG_RANGE_PCT:{average_range_pct:.4f}",
        )

    if spec.name == "rsi_mean_reversion":
        window = int(p.get("window", 14))
        rsi = relative_strength_index(closes, window)[-1]
        if rsi is None:
            return 0.0, (f"STRATEGY:{spec.name}", "WARMUP")
        distance_from_mid = abs(float(rsi) - 50.0) / 50.0
        strength = _clamp(distance_from_mid)
        return strength, (
            f"STRATEGY:{spec.name}",
            f"RSI:{float(rsi):.2f}",
        )

    return 0.5, (f"STRATEGY:{spec.name}", "DEFAULT_STRENGTH")


def strategy_signal(bars, spec: StrategySpec, *, source: str | None = None) -> Signal:
    directions = build_directions(bars, spec)
    direction = int(directions[-1])
    action = (
        DecisionAction.BUY
        if direction > 0
        else DecisionAction.SELL
        if direction < 0
        else DecisionAction.HOLD
    )

    strength, reasons = _signal_strength(bars, spec, direction)
    if direction:
        confidence = round(0.50 + 0.40 * strength, 4)
        score = round(float(direction) * (0.25 + 0.75 * strength), 4)
    else:
        confidence = 0.25
        score = 0.0

    return Signal(
        source=source or spec.name,
        action=action,
        confidence=confidence,
        score=score,
        reasons=reasons,
    )
