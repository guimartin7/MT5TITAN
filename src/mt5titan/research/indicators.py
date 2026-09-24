"""Small deterministic indicator library."""


def simple_moving_average(values: list[float], window: int) -> list[float | None]:
    if window < 1:
        raise ValueError("window must be positive")
    result: list[float | None] = [None] * len(values)
    running = 0.0
    for index, value in enumerate(values):
        running += float(value)
        if index >= window:
            running -= float(values[index - window])
        if index >= window - 1:
            result[index] = running / window
    return result


def relative_strength_index(values: list[float], window: int = 14) -> list[float | None]:
    if window < 2:
        raise ValueError("RSI window must be at least 2")
    result: list[float | None] = [None] * len(values)
    gains = [max(0.0, values[i] - values[i - 1]) for i in range(1, len(values))]
    losses = [max(0.0, values[i - 1] - values[i]) for i in range(1, len(values))]
    for index in range(window, len(values)):
        gain = sum(gains[index - window:index]) / window
        loss = sum(losses[index - window:index]) / window
        if loss == 0:
            result[index] = 100.0
        else:
            result[index] = 100.0 - 100.0 / (1.0 + gain / loss)
    return result
