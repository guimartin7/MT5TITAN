from mt5titan.market import assess_feed


def test_server_clock_offset_is_normalized():
    now = 1_000_000
    tick = now + 3 * 3600 - 10
    health = assess_feed(tick, 100.0, 101.0, now_timestamp=now)
    assert health.healthy
    assert health.age_seconds == 10.0
    assert health.estimated_server_shift_hours == 3.0


def test_invalid_quote_is_blocked():
    health = assess_feed(1000, 101.0, 100.0, now_timestamp=1000)
    assert not health.healthy
    assert health.status == "INVALID_QUOTE"
