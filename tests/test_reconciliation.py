from mt5titan.execution.reconciliation import MANAGED_MAGIC, compare_expected, summarize_broker_state


def test_clean_account_allows_new_entry():
    snapshot = summarize_broker_state([], [])
    assert snapshot["status"] == "CLEAN"
    assert snapshot["safe_for_new_entry"]


def test_manual_position_blocks_new_entry():
    snapshot = summarize_broker_state([{"magic": 0, "volume": 1}], [])
    assert snapshot["status"] == "CONFLICT"
    assert "foreign_or_manual_position" in snapshot["conflict_reasons"]


def test_expected_position_requires_stop():
    snapshot = summarize_broker_state([{"magic": MANAGED_MAGIC, "volume": 1, "type": 0, "sl": 0}], [])
    result = compare_expected(snapshot, {"volume": 1, "type": 0})
    assert not result["matches"]
    assert "broker_position_without_stop" in result["reasons"]
