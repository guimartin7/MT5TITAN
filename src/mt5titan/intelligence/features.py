"""Feature pipeline built only from closed candles."""
from dataclasses import dataclass, asdict
from statistics import pstdev

from mt5titan.research.indicators import relative_strength_index, simple_moving_average


@dataclass(frozen=True)
class FeatureSet:
    sma_fast: float
    sma_slow: float
    trend_gap_pct: float
    rsi: float
    momentum_pct: float
    realized_volatility_pct: float
    average_range_pct: float
    volume_ratio: float | None
    spread_points: float | None

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_volume(bar):
    for key in ("real_volume", "tick_volume", "volume"):
        try:
            value = float(bar[key])
            if value >= 0:
                return value
        except (KeyError, TypeError, ValueError):
            continue
    return None


def build_features(
    bars,
    *,
    fast_window: int = 9,
    slow_window: int = 21,
    rsi_window: int = 14,
    momentum_window: int = 10,
    volatility_window: int = 20,
) -> FeatureSet:
    minimum = max(slow_window, rsi_window + 1, momentum_window + 1, volatility_window + 1)
    if len(bars) < minimum:
        raise ValueError(f"at least {minimum} closed bars are required")

    closes = [float(bar["close"]) for bar in bars]
    highs = [float(bar["high"]) for bar in bars]
    lows = [float(bar["low"]) for bar in bars]

    fast = simple_moving_average(closes, fast_window)[-1]
    slow = simple_moving_average(closes, slow_window)[-1]
    rsi = relative_strength_index(closes, rsi_window)[-1]
    if fast is None or slow is None or rsi is None:
        raise ValueError("feature warmup incomplete")

    base = closes[-1]
    if base <= 0:
        raise ValueError("latest close must be positive")

    momentum_base = closes[-1 - momentum_window]
    momentum_pct = (base / momentum_base - 1.0) * 100.0 if momentum_base else 0.0

    returns = []
    for i in range(len(closes) - volatility_window, len(closes)):
        previous = closes[i - 1]
        returns.append(closes[i] / previous - 1.0 if previous else 0.0)
    realized_volatility_pct = pstdev(returns) * 100.0 if len(returns) >= 2 else 0.0

    ranges = [
        (highs[i] - lows[i]) / closes[i] * 100.0
        for i in range(len(closes) - volatility_window, len(closes))
        if closes[i] > 0
    ]
    average_range_pct = sum(ranges) / len(ranges) if ranges else 0.0

    recent_volumes = [_safe_volume(bar) for bar in bars[-volatility_window:]]
    clean_volumes = [v for v in recent_volumes if v is not None]
    latest_volume = _safe_volume(bars[-1])
    volume_ratio = None
    if latest_volume is not None and clean_volumes:
        average_volume = sum(clean_volumes) / len(clean_volumes)
        volume_ratio = latest_volume / average_volume if average_volume > 0 else None

    try:
        spread_points = float(bars[-1]["spread"])
    except (KeyError, TypeError, ValueError):
        spread_points = None

    return FeatureSet(
        sma_fast=float(fast),
        sma_slow=float(slow),
        trend_gap_pct=(float(fast) / float(slow) - 1.0) * 100.0 if slow else 0.0,
        rsi=float(rsi),
        momentum_pct=momentum_pct,
        realized_volatility_pct=realized_volatility_pct,
        average_range_pct=average_range_pct,
        volume_ratio=volume_ratio,
        spread_points=spread_points,
    )
