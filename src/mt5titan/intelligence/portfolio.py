"""Portfolio exposure and correlation controls."""
from dataclasses import dataclass
from math import sqrt
from statistics import mean


def _returns(values: list[float]) -> list[float]:
    output = []
    for i in range(1, len(values)):
        previous = float(values[i - 1])
        current = float(values[i])
        output.append(current / previous - 1.0 if previous else 0.0)
    return output


def pearson_correlation(a: list[float], b: list[float]) -> float | None:
    size = min(len(a), len(b))
    if size < 3:
        return None
    a = a[-size:]
    b = b[-size:]
    ma, mb = mean(a), mean(b)
    da = [x - ma for x in a]
    db = [y - mb for y in b]
    denom = sqrt(sum(x * x for x in da) * sum(y * y for y in db))
    if denom == 0:
        return None
    return sum(x * y for x, y in zip(da, db)) / denom


def close_correlation(series_a: list[float], series_b: list[float]) -> float | None:
    return pearson_correlation(_returns(series_a), _returns(series_b))


@dataclass(frozen=True)
class ExposurePolicy:
    max_open_positions: int = 3
    max_same_direction_correlated: int = 2
    correlation_threshold: float = 0.80


def evaluate_portfolio_exposure(
    *,
    candidate_symbol: str,
    candidate_direction: int,
    open_positions: list[dict],
    correlations: dict[tuple[str, str], float | None],
    policy: ExposurePolicy | None = None,
) -> dict:
    policy = policy or ExposurePolicy()
    blockers: list[str] = []

    if candidate_direction not in (-1, 1):
        raise ValueError("candidate_direction must be -1 or 1")

    if len(open_positions) >= policy.max_open_positions:
        blockers.append("max_open_positions")

    correlated_same_direction = 0
    for position in open_positions:
        symbol = str(position.get("symbol", ""))
        direction = int(position.get("direction", 0) or 0)
        key = (candidate_symbol, symbol)
        reverse = (symbol, candidate_symbol)
        correlation = correlations.get(key, correlations.get(reverse))
        if (
            correlation is not None
            and abs(float(correlation)) >= policy.correlation_threshold
            and direction == candidate_direction
        ):
            correlated_same_direction += 1

    if correlated_same_direction >= policy.max_same_direction_correlated:
        blockers.append("correlated_directional_exposure")

    return {
        "allowed": not blockers,
        "blockers": blockers,
        "open_positions": len(open_positions),
        "correlated_same_direction": correlated_same_direction,
        "policy": {
            "max_open_positions": policy.max_open_positions,
            "max_same_direction_correlated": policy.max_same_direction_correlated,
            "correlation_threshold": policy.correlation_threshold,
        },
    }
