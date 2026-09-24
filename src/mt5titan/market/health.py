"""Feed-health validation independent from MetaTrader imports."""
from dataclasses import dataclass
from time import time


@dataclass(frozen=True)
class FeedHealth:
    healthy: bool
    status: str
    age_seconds: float | None
    bid: float | None = None
    ask: float | None = None
    spread: float | None = None
    estimated_server_shift_hours: float | None = None


def assess_feed(
    tick_timestamp: int | float | None,
    bid: float | None,
    ask: float | None,
    *,
    now_timestamp: int | float | None = None,
    max_age_seconds: float = 120.0,
) -> FeedHealth:
    if tick_timestamp is None or bid is None or ask is None:
        return FeedHealth(False, "MISSING_TICK", None)

    bid = float(bid)
    ask = float(ask)
    if bid <= 0 or ask <= 0 or ask < bid:
        return FeedHealth(False, "INVALID_QUOTE", None, bid, ask, ask - bid)

    now_value = float(time() if now_timestamp is None else now_timestamp)
    raw_offset = float(tick_timestamp) - now_value
    server_shift = round(raw_offset / 3600) * 3600
    normalized_age = now_value - (float(tick_timestamp) - server_shift)

    status = "OK" if abs(normalized_age) <= max_age_seconds else "STALE_OR_FUTURE_TICK"
    return FeedHealth(
        healthy=status == "OK",
        status=status,
        age_seconds=round(normalized_age, 1),
        bid=bid,
        ask=ask,
        spread=ask - bid,
        estimated_server_shift_hours=server_shift / 3600,
    )
