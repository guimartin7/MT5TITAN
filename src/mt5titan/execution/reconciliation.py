"""Pure reconciliation helpers."""
MANAGED_MAGIC = 26090301


def summarize_broker_state(positions: list[dict], orders: list[dict]) -> dict:
    managed_positions = [row for row in positions if row.get("magic") == MANAGED_MAGIC]
    foreign_positions = [row for row in positions if row.get("magic") != MANAGED_MAGIC]
    managed_orders = [row for row in orders if row.get("magic") == MANAGED_MAGIC]
    foreign_orders = [row for row in orders if row.get("magic") != MANAGED_MAGIC]

    reasons: list[str] = []
    if len(positions) > 1:
        reasons.append("multiple_positions_in_netting_account")
    if foreign_positions:
        reasons.append("foreign_or_manual_position")
    if foreign_orders:
        reasons.append("foreign_or_manual_order")
    if len(managed_positions) > 1:
        reasons.append("multiple_managed_positions")

    status = "CONFLICT" if reasons else ("MANAGED_EXPOSURE" if managed_positions or managed_orders else "CLEAN")
    return {
        "status": status,
        "safe_for_new_entry": status == "CLEAN",
        "conflict_reasons": reasons,
        "managed_position_count": len(managed_positions),
        "managed_order_count": len(managed_orders),
        "foreign_position_count": len(foreign_positions),
        "foreign_order_count": len(foreign_orders),
        "positions": positions,
        "orders": orders,
    }


def compare_expected(snapshot: dict, expected_position: dict | None = None) -> dict:
    reasons = list(snapshot.get("conflict_reasons", []))
    managed = [row for row in snapshot.get("positions", []) if row.get("magic") == MANAGED_MAGIC]

    if expected_position is None and managed:
        reasons.append("broker_has_position_but_local_state_is_flat")
    elif expected_position is not None and not managed:
        reasons.append("local_state_has_position_but_broker_is_flat")
    elif expected_position is not None and managed:
        actual = managed[0]
        if float(actual.get("volume", 0)) != float(expected_position["volume"]):
            reasons.append("position_volume_mismatch")
        if int(actual.get("type", -1)) != int(expected_position["type"]):
            reasons.append("position_direction_mismatch")
        if not actual.get("sl"):
            reasons.append("broker_position_without_stop")

    reasons = list(dict.fromkeys(reasons))
    return {"matches": not reasons, "reasons": reasons}
