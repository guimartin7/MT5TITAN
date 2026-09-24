from mt5titan.execution.journal import create_intent, empty_journal, transition
from mt5titan.execution.recovery import recover_journal


def broker(status="CLEAN", positions=(), orders=(), deals=()):
    return {
        "status": status,
        "safe_for_new_entry": status == "CLEAN",
        "positions": list(positions),
        "orders": list(orders),
        "recent_deals": list(deals),
    }


def test_sent_without_evidence_becomes_unknown():
    journal = empty_journal()
    item, _ = create_intent(journal, "WINV26", 123, 1)
    transition(item, "PREFLIGHT_APPROVED")
    transition(item, "SENT")
    report = recover_journal(journal, broker(), "2026-09-23")
    assert item["status"] == "UNKNOWN"
    assert not report["safe_to_continue"]


def test_sent_with_protected_position_confirms():
    journal = empty_journal()
    item, _ = create_intent(journal, "WINV26", 123, 1)
    transition(item, "PREFLIGHT_APPROVED")
    transition(item, "SENT")
    snapshot = broker("MANAGED_EXPOSURE", positions=({"magic": 26090301, "sl": 99900},))
    recover_journal(journal, snapshot, "2026-09-23")
    assert item["status"] == "CONFIRMED"
