"""Higher-timeframe confirmation that never creates a trade direction."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TimeframeConfirmation:
    base_timeframe: str
    higher_timeframe: str
    base_action: str
    higher_action: str
    higher_confidence: float
    status: str
    score: float
    adjustment_pct: float

    def to_dict(self) -> dict:
        return asdict(self)


def build_timeframe_confirmation(
    *,
    base_report: dict,
    higher_report: dict,
) -> TimeframeConfirmation:
    base_action = str(base_report["decision"]["action"])
    higher_action = str(higher_report["decision"]["action"])
    higher_confidence = float(higher_report["decision"]["confidence"])

    if base_action == "HOLD" or higher_action == "HOLD":
        status = "NEUTRAL"
        score = 0.0
        adjustment = 0.0
    elif base_action == higher_action:
        status = "ALIGNED"
        score = higher_confidence
        adjustment = min(10.0, 4.0 + higher_confidence * 6.0)
    else:
        status = "CONFLICT"
        score = -higher_confidence
        adjustment = -min(15.0, 7.0 + higher_confidence * 8.0)

    return TimeframeConfirmation(
        base_timeframe=str(base_report["timeframe"]),
        higher_timeframe=str(higher_report["timeframe"]),
        base_action=base_action,
        higher_action=higher_action,
        higher_confidence=round(higher_confidence, 4),
        status=status,
        score=round(score, 4),
        adjustment_pct=round(adjustment, 2),
    )
