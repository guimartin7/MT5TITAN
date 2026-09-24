"""Persistent and idempotent execution journal."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ACTIVE_STATES = {"CREATED", "PREFLIGHT_APPROVED", "SENT", "UNKNOWN"}
FINAL_STATES = {"CONFIRMED", "REJECTED", "CANCELLED"}


def intent_id(symbol: str, candle_time: int, direction: int) -> str:
    raw = f"{symbol}:{int(candle_time)}:{int(direction)}".encode()
    return hashlib.sha256(raw).hexdigest()[:20]


def empty_journal() -> dict:
    return {"mode": "DEMO_EXECUTION_JOURNAL", "version": 1, "intents": []}


def validate_journal(journal: dict) -> None:
    if journal.get("mode") != "DEMO_EXECUTION_JOURNAL" or journal.get("version") != 1:
        raise ValueError("invalid execution journal")
    identifiers = [item.get("id") for item in journal.get("intents", [])]
    if None in identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate or invalid execution intent")
    allowed = ACTIVE_STATES | FINAL_STATES
    if any(item.get("status") not in allowed for item in journal["intents"]):
        raise ValueError("unknown execution state")


def load_journal(path: Path) -> dict:
    if not path.exists():
        return empty_journal()
    journal = json.loads(path.read_text(encoding="utf-8"))
    validate_journal(journal)
    return journal


def save_journal(path: Path, journal: dict) -> None:
    validate_journal(journal)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(journal, indent=2), encoding="utf-8")
    temporary.replace(path)


def create_intent(journal: dict, symbol: str, candle_time: int, direction: int, volume: float = 1) -> tuple[dict, bool]:
    validate_journal(journal)
    identifier = intent_id(symbol, candle_time, direction)
    existing = next((item for item in journal["intents"] if item["id"] == identifier), None)
    if existing:
        return existing, False
    if volume <= 0 or direction not in (-1, 1):
        raise ValueError("invalid execution intent")
    if any(item["status"] in ACTIVE_STATES for item in journal["intents"]):
        raise RuntimeError("another execution intent is active")

    item = {
        "id": identifier,
        "symbol": symbol,
        "candle_time": int(candle_time),
        "direction": int(direction),
        "volume": float(volume),
        "status": "CREATED",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "broker_order": None,
        "broker_deal": None,
    }
    journal["intents"].append(item)
    return item, True


def transition(item: dict, target: str, **evidence) -> dict:
    transitions = {
        "CREATED": {"PREFLIGHT_APPROVED", "REJECTED", "CANCELLED"},
        "PREFLIGHT_APPROVED": {"SENT", "REJECTED", "CANCELLED"},
        "SENT": {"CONFIRMED", "REJECTED", "UNKNOWN"},
        "UNKNOWN": {"CONFIRMED", "REJECTED"},
    }
    current = item["status"]
    if target not in transitions.get(current, set()):
        raise ValueError(f"invalid transition: {current} -> {target}")
    item["status"] = target
    item["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    for key in ("broker_order", "broker_deal", "retcode", "comment"):
        if key in evidence:
            item[key] = evidence[key]
    return item


def journal_readiness(journal: dict) -> dict:
    active = [item for item in journal["intents"] if item["status"] in ACTIVE_STATES]
    unknown = [item for item in active if item["status"] == "UNKNOWN"]
    return {
        "ready": not active,
        "active_intents": len(active),
        "unknown_intents": len(unknown),
        "blockers": (
            ["unknown_execution_outcome"]
            if unknown
            else ["active_execution_intent"]
            if active
            else []
        ),
    }
