"""Feed-health validation independent from MetaTrader 5 imports."""
from dataclasses import dataclass
from time import time


@dataclass(frozen=True)
class FeedHealth:
    healthy: bool
    status: str
    age_seconds: float | None


def assess_feed(
    tick_timestamp: int | float | None,
    bid: float | None,
    ask: float | None,
    *,
    now_timestamp: int | float | None = None,
    max_age_seconds: float = 120.0,
) -> FeedHealth:
    if tick_timestamp is None or bid is None or ask is None:
        return FeedHealth(False, "MISSING_FEED", None)
    if bid <= 0 or ask <= 0 or ask < bid:
        return FeedHealth(False, "INVALID_QUOTE", None)

    now_value = float(time() if now_timestamp is None else now_timestamp)
    age = max(0.0, now_value - float(tick_timestamp))
    if age > max_age_seconds:
        return FeedHealth(False, "STALE_FEED", age)
    return FeedHealth(True, "HEALTHY", age)
