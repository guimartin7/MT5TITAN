"""Economic-calendar contracts and event risk classification.

Providers are adapters. This module contains no network access.
"""
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class EconomicEvent:
    event_id: str
    currency: str
    title: str
    scheduled_at_utc: datetime
    impact: str

    def validate(self) -> None:
        if self.impact not in {"LOW", "MEDIUM", "HIGH"}:
            raise ValueError("impact must be LOW, MEDIUM or HIGH")
        if self.scheduled_at_utc.tzinfo is None:
            raise ValueError("scheduled_at_utc must be timezone-aware")


@dataclass(frozen=True)
class EventRiskPolicy:
    high_impact_block_before_minutes: int = 30
    high_impact_block_after_minutes: int = 15
    medium_impact_caution_before_minutes: int = 15


def classify_event_risk(
    events: list[EconomicEvent],
    *,
    currencies: set[str],
    now: datetime | None = None,
    policy: EventRiskPolicy | None = None,
) -> dict:
    policy = policy or EventRiskPolicy()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    relevant = []
    blocked = False
    caution = False

    for event in events:
        event.validate()
        if event.currency.upper() not in {c.upper() for c in currencies}:
            continue
        minutes = (event.scheduled_at_utc - now).total_seconds() / 60.0
        row = {
            "event_id": event.event_id,
            "currency": event.currency,
            "title": event.title,
            "impact": event.impact,
            "minutes_from_now": round(minutes, 1),
        }

        if event.impact == "HIGH":
            if -policy.high_impact_block_after_minutes <= minutes <= policy.high_impact_block_before_minutes:
                blocked = True
                row["risk"] = "BLOCK"
            else:
                row["risk"] = "NORMAL"
        elif event.impact == "MEDIUM" and 0 <= minutes <= policy.medium_impact_caution_before_minutes:
            caution = True
            row["risk"] = "CAUTION"
        else:
            row["risk"] = "NORMAL"

        relevant.append(row)

    relevant.sort(key=lambda row: abs(row["minutes_from_now"]))
    return {
        "blocked": blocked,
        "caution": caution,
        "relevant_events": relevant,
        "reason": "HIGH_IMPACT_EVENT_NEAR" if blocked else "MEDIUM_IMPACT_EVENT_NEAR" if caution else None,
    }
