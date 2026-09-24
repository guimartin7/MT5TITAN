"""Instrument profiles populated from broker metadata."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class InstrumentProfile:
    symbol: str
    description: str
    tick_size: float
    tick_value: float
    volume_min: float
    volume_step: float
    expiration_time: int = 0
    market: str = "UNKNOWN"

    @property
    def value_per_point(self) -> float:
        return self.tick_value / self.tick_size

    def to_dict(self) -> dict:
        return {**asdict(self), "value_per_point": self.value_per_point}


def load_b3_profile(api, symbol: str) -> InstrumentProfile:
    account = api.account_info()
    if account is None or account.trade_mode != api.ACCOUNT_TRADE_MODE_DEMO:
        raise RuntimeError("B3 profile requires a Demo account")
    if "ClearInvestimentos-DEMO" not in str(account.server):
        raise RuntimeError("unsupported B3 server")

    info = api.symbol_info(symbol)
    if info is None or not symbol.upper().startswith(("WIN", "WDO")):
        raise ValueError("unsupported B3 instrument")

    values = (
        info.trade_tick_size,
        info.trade_tick_value,
        info.volume_min,
        info.volume_step,
    )
    if any(float(value) <= 0 for value in values):
        raise ValueError("invalid instrument metadata")

    return InstrumentProfile(
        symbol=symbol,
        description=str(info.description),
        tick_size=float(info.trade_tick_size),
        tick_value=float(info.trade_tick_value),
        volume_min=float(info.volume_min),
        volume_step=float(info.volume_step),
        expiration_time=int(getattr(info, "expiration_time", 0) or 0),
        market="B3",
    )


def futures_pnl(
    entry: float,
    exit_price: float,
    direction: int,
    contracts: float,
    profile: InstrumentProfile,
) -> float:
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    return (exit_price - entry) * direction * contracts * profile.value_per_point
