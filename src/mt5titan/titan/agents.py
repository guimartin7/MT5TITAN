"""Specialized model-assisted agents."""
from dataclasses import dataclass

from .models import AGENT_RESPONSE_SCHEMA, AgentContext, AgentOpinion, AgentVerdict
from .provider import ModelProvider


def _parse(agent_name: str, payload: dict) -> AgentOpinion:
    opinion = AgentOpinion(
        agent=agent_name,
        verdict=AgentVerdict(str(payload["verdict"])),
        confidence=float(payload["confidence"]),
        score=float(payload["score"]),
        reason_codes=tuple(str(x) for x in payload.get("reason_codes", [])),
        risk_flags=tuple(str(x) for x in payload.get("risk_flags", [])),
    )
    opinion.validate()
    return opinion


@dataclass
class BaseAgent:
    provider: ModelProvider
    name: str
    instruction: str

    def evaluate(self, context: AgentContext) -> AgentOpinion:
        payload = self.provider.structured_decision(
            agent_name=self.name,
            system_instruction=self.instruction,
            context=context,
            schema=AGENT_RESPONSE_SCHEMA,
        )
        if not isinstance(payload, dict):
            raise ValueError(f"{self.name} provider returned non-object response")
        return _parse(self.name, payload)


class TechnicalAgent(BaseAgent):
    def __init__(self, provider: ModelProvider):
        super().__init__(
            provider,
            "technical",
            (
                "Evaluate only the supplied technical features, regime and strategy "
                "signals. Do not infer missing prices or news. Prefer HOLD under "
                "conflicting evidence. Return only the structured decision."
            ),
        )


class NewsAgent(BaseAgent):
    def __init__(self, provider: ModelProvider):
        super().__init__(
            provider,
            "news",
            (
                "Evaluate only supplied news/event-risk information. Never fabricate "
                "headlines or events. Use VETO when supplied high-impact event risk "
                "makes a new trade inappropriate. Return only structured output."
            ),
        )


class MacroAgent(BaseAgent):
    def __init__(self, provider: ModelProvider):
        super().__init__(
            provider,
            "macro",
            (
                "Evaluate only supplied macro_context, event-risk and portfolio context. "
                "Do not invent economic data or assume causality from a single series. "
                "Prefer HOLD when evidence is incomplete and VETO for explicit portfolio "
                "or event-risk conflicts."
            ),
        )
