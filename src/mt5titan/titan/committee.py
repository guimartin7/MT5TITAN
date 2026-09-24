"""Aggregate validated agent opinions without granting execution authority."""
from dataclasses import dataclass

from mt5titan.domain import DecisionAction, Signal

from .models import AgentOpinion, AgentVerdict


@dataclass(frozen=True)
class CommitteePolicy:
    technical_weight: float = 0.45
    news_weight: float = 0.25
    macro_weight: float = 0.30
    minimum_absolute_score: float = 0.20
    veto_is_absolute: bool = True


class AICommittee:
    def __init__(self, policy: CommitteePolicy | None = None):
        self.policy = policy or CommitteePolicy()

    def aggregate(self, opinions: list[AgentOpinion]) -> Signal:
        if not opinions:
            return Signal("ai_committee", DecisionAction.HOLD, 0.0, 0.0, ("NO_AGENT_OPINIONS",))

        for opinion in opinions:
            opinion.validate()

        vetoes = [op for op in opinions if op.verdict == AgentVerdict.VETO]
        if vetoes and self.policy.veto_is_absolute:
            reasons = tuple(
                code
                for opinion in vetoes
                for code in (opinion.risk_flags or opinion.reason_codes or ("AGENT_VETO",))
            )
            return Signal("ai_committee", DecisionAction.HOLD, 1.0, 0.0, reasons)

        weights = {
            "technical": self.policy.technical_weight,
            "news": self.policy.news_weight,
            "macro": self.policy.macro_weight,
        }
        weighted = 0.0
        total_weight = 0.0
        confidences = []

        for opinion in opinions:
            base_weight = weights.get(opinion.agent, 0.15)
            effective = base_weight * opinion.confidence
            weighted += opinion.score * effective
            total_weight += effective
            confidences.append(opinion.confidence)

        score = weighted / total_weight if total_weight else 0.0
        confidence = sum(confidences) / len(confidences) if confidences else 0.0

        if abs(score) < self.policy.minimum_absolute_score:
            action = DecisionAction.HOLD
        else:
            action = DecisionAction.BUY if score > 0 else DecisionAction.SELL

        reasons = tuple(
            f"{op.agent}:{op.verdict.value}"
            for op in opinions
        )
        return Signal(
            source="ai_committee",
            action=action,
            confidence=round(confidence, 4),
            score=round(score, 4),
            reasons=reasons,
        )
