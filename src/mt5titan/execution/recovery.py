"""Conservative recovery for uncertain execution outcomes."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .journal import journal_readiness, transition
from .reconciliation import MANAGED_MAGIC

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def _local_date(iso_timestamp: str) -> str:
    instant = datetime.fromisoformat(iso_timestamp)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(SAO_PAULO).date().isoformat()


def recover_sent_intent(item: dict, snapshot: dict) -> dict:
    if item["status"] not in {"SENT", "UNKNOWN"}:
        return {"resolved": True, "status": item["status"]}

    managed_positions = [
        row for row in snapshot.get("positions", []) if row.get("magic") == MANAGED_MAGIC
    ]
    managed_orders = [
        row for row in snapshot.get("orders", []) if row.get("magic") == MANAGED_MAGIC
    ]
    managed_deals = [
        row for row in snapshot.get("recent_deals", []) if row.get("magic") == MANAGED_MAGIC
    ]
    protected_positions = [row for row in managed_positions if row.get("sl")]

    if protected_positions:
        transition(item, "CONFIRMED")
        return {"resolved": True, "status": "CONFIRMED"}

    if managed_positions:
        if item["status"] == "SENT":
            transition(item, "UNKNOWN", comment="broker position found without confirmed stop")
        return {
            "resolved": False,
            "status": "UNKNOWN",
            "action": "BLOCK_UNPROTECTED_POSITION",
        }

    if managed_orders or managed_deals:
        if item["status"] == "SENT":
            transition(item, "UNKNOWN", comment="partial broker evidence")
        return {
            "resolved": False,
            "status": "UNKNOWN",
            "action": "BLOCK_AND_RECONCILE_PARTIAL_EVIDENCE",
        }

    if item["status"] == "SENT":
        transition(item, "UNKNOWN", comment="no broker evidence found")
    return {
        "resolved": False,
        "status": "UNKNOWN",
        "action": "BLOCK_AND_REQUIRE_MANUAL_REVIEW",
    }


def recover_journal(journal: dict, snapshot: dict, today: str) -> dict:
    actions = []
    for item in journal["intents"]:
        if item["status"] in {"SENT", "UNKNOWN"}:
            before = item["status"]
            result = recover_sent_intent(item, snapshot)
            actions.append({"id": item["id"], "before": before, "after": item["status"], **result})
        elif item["status"] in {"CREATED", "PREFLIGHT_APPROVED"}:
            if _local_date(item["created_at_utc"]) != today:
                if snapshot.get("status") == "CLEAN":
                    before = item["status"]
                    transition(item, "CANCELLED", comment="expired intent without broker exposure")
                    actions.append({"id": item["id"], "before": before, "after": "CANCELLED", "resolved": True})
                else:
                    actions.append({
                        "id": item["id"],
                        "before": item["status"],
                        "after": item["status"],
                        "resolved": False,
                        "action": "BLOCK_EXPIRED_INTENT_WITH_BROKER_EXPOSURE",
                    })

    readiness = journal_readiness(journal)
    return {
        "actions": actions,
        "journal_readiness": readiness,
        "safe_to_continue": bool(snapshot.get("safe_for_new_entry")) and readiness["ready"],
    }
