"""Local OHLC resampling to avoid extra external market-data calls."""
from __future__ import annotations


_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "H1": 3600,
}


def next_higher_timeframe(timeframe: str) -> str | None:
    return {
        "M1": "M5",
        "M5": "M15",
        "M15": "H1",
        "H1": None,
    }.get(timeframe.upper())


def resample_candles(candles: list[dict], target_timeframe: str) -> list[dict]:
    target = target_timeframe.upper()
    if target not in _SECONDS:
        raise ValueError(f"unsupported target timeframe: {target_timeframe}")
    if not candles:
        return []

    target_seconds = _SECONDS[target]
    buckets: dict[int, list[dict]] = {}
    for candle in sorted(candles, key=lambda row: int(row["time"])):
        timestamp = int(candle["time"])
        bucket = timestamp // target_seconds * target_seconds
        buckets.setdefault(bucket, []).append(candle)

    rows = []
    for timestamp, group in sorted(buckets.items()):
        rows.append({
            "time": timestamp,
            "open": float(group[0]["open"]),
            "high": max(float(row["high"]) for row in group),
            "low": min(float(row["low"]) for row in group),
            "close": float(group[-1]["close"]),
            "spread": float(group[-1].get("spread", 0.0)),
            "tick_volume": sum(float(row.get("tick_volume", 0.0)) for row in group),
        })
    return rows
