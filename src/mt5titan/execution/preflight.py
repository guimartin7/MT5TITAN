"""Demo order preflight.

This module may call order_check, but never order_send.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from mt5titan.market import assess_feed
from mt5titan.market.instruments import load_b3_profile

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class PreflightConfig:
    symbol: str = "WINV26"
    volume: float = 1.0
    stop_points: float = 100.0
    target_points: float = 200.0
    direction: int = 1
    deviation_points: int = 10
    magic: int = 26090301


def round_to_tick(price: float, tick_size: float) -> float:
    return round(price / tick_size) * tick_size


def validate_context(api, config: PreflightConfig) -> None:
    terminal, account = api.terminal_info(), api.account_info()
    if terminal is None or account is None or not terminal.connected:
        raise RuntimeError("terminal or account disconnected")
    if account.trade_mode != api.ACCOUNT_TRADE_MODE_DEMO:
        raise RuntimeError("preflight refused outside Demo")
    if account.server != "ClearInvestimentos-DEMO":
        raise RuntimeError("unsupported server")
    if account.margin_mode != api.ACCOUNT_MARGIN_MODE_RETAIL_NETTING:
        raise RuntimeError("Netting account required")
    if config.symbol != "WINV26" or config.volume != 1:
        raise RuntimeError("initial execution scope is one WINV26 contract")
    if config.direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")

    positions = api.positions_get(symbol=config.symbol)
    orders = api.orders_get(symbol=config.symbol)
    if positions is None or orders is None:
        raise RuntimeError(f"could not query exposure: {api.last_error()}")
    if positions or orders:
        raise RuntimeError("existing exposure blocks a new entry")
    if not terminal.trade_allowed or terminal.tradeapi_disabled:
        raise RuntimeError("terminal automation is disabled")
    if not account.trade_allowed or not account.trade_expert:
        raise RuntimeError("account automation is disabled")


def build_request(api, config: PreflightConfig) -> tuple[dict, dict]:
    profile = load_b3_profile(api, config.symbol)
    tick = api.symbol_info_tick(config.symbol)
    if tick is None:
        raise RuntimeError("quote unavailable")

    feed = assess_feed(tick.time, tick.bid, tick.ask)
    if not feed.healthy:
        raise RuntimeError(f"feed refused: {feed.status}")

    buying = config.direction == 1
    price = float(tick.ask if buying else tick.bid)
    stop = price - config.stop_points if buying else price + config.stop_points
    target = price + config.target_points if buying else price - config.target_points

    request = {
        "action": api.TRADE_ACTION_DEAL,
        "symbol": config.symbol,
        "volume": config.volume,
        "type": api.ORDER_TYPE_BUY if buying else api.ORDER_TYPE_SELL,
        "price": round_to_tick(price, profile.tick_size),
        "sl": round_to_tick(stop, profile.tick_size),
        "tp": round_to_tick(target, profile.tick_size),
        "deviation": config.deviation_points,
        "magic": config.magic,
        "comment": "mt5titan-demo-preflight",
        "type_time": api.ORDER_TIME_DAY,
        "type_filling": api.ORDER_FILLING_IOC,
    }
    return request, feed.__dict__


def run_preflight(api, config: PreflightConfig) -> dict:
    validate_context(api, config)
    request, feed = build_request(api, config)
    margin = api.order_calc_margin(
        request["type"], request["symbol"], request["volume"], request["price"]
    )
    if margin is None:
        raise RuntimeError(f"margin calculation failed: {api.last_error()}")

    result = api.order_check(request)
    if result is None:
        raise RuntimeError(f"order_check failed: {api.last_error()}")

    return {
        "mode": "DEMO_PREFLIGHT_ONLY",
        "would_send_order": False,
        "server": "ClearInvestimentos-DEMO",
        "request": request,
        "estimated_margin": float(margin),
        "feed_health": feed,
        "check_retcode": int(result.retcode),
        "check_comment": result.comment,
        "check_approved": int(result.retcode) == 0,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }
