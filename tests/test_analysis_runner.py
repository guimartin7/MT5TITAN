from pathlib import Path
from types import SimpleNamespace

from mt5titan.app.analyze import run_analysis


class FakeAPI:
    ACCOUNT_TRADE_MODE_DEMO = 0
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 60

    def __init__(self):
        self.sent = False

    def initialize(self, terminal, timeout=15000):
        return True

    def shutdown(self):
        return None

    def last_error(self):
        return (0, "ok")

    def account_info(self):
        return SimpleNamespace(trade_mode=0)

    def symbol_select(self, symbol, enabled):
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time=10_000, bid=120.0, ask=121.0)

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        rows = []
        price = 100.0
        for i in range(count):
            open_price = price
            price += 0.2
            rows.append({
                "time": i + 1,
                "open": open_price,
                "high": price + 0.1,
                "low": open_price - 0.1,
                "close": price,
                "spread": 1,
                "tick_volume": 100 + i,
            })
        return rows

    def order_send(self, request):
        self.sent = True
        raise AssertionError("order_send must never be called")


def test_analysis_runner_never_sends_order(tmp_path: Path):
    api = FakeAPI()
    report = run_analysis(
        api,
        terminal_path="fake",
        symbol="WINV26",
        timeframe_name="M5",
        bars_count=100,
        use_ai=False,
        output_dir=tmp_path / "reports",
        replay_dir=tmp_path / "replays",
    )
    assert report["mode"] == "ANALYSIS_ONLY_NO_ORDER_SEND"
    assert report["execution"]["enabled"] is False
    assert report["execution"]["order_send_called"] is False
    assert api.sent is False
    assert Path(report["report_path"]).exists()
