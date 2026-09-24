"""Generate model opinions and persist them for later replay."""
from dataclasses import dataclass

from .agents import MacroAgent, NewsAgent, TechnicalAgent
from .models import AgentContext, AgentOpinion
from .provider import ModelProvider
from .replay import OpinionReplayStore


@dataclass(frozen=True)
class ExperimentResult:
    key: str
    opinions: tuple[AgentOpinion, ...]


class TitanExperiment:
    def __init__(self, provider: ModelProvider, replay_store: OpinionReplayStore):
        self.provider = provider
        self.replay_store = replay_store
        self.agents = (
            TechnicalAgent(provider),
            NewsAgent(provider),
            MacroAgent(provider),
        )

    def run_context(
        self,
        *,
        key: str,
        context: AgentContext,
        metadata: dict | None = None,
    ) -> ExperimentResult:
        if not key:
            raise ValueError("replay key is required")

        opinions = tuple(agent.evaluate(context) for agent in self.agents)
        self.replay_store.append(
            key=key,
            opinions=list(opinions),
            metadata={
                "symbol": context.symbol,
                "timeframe": context.timeframe,
                "timestamp": context.timestamp,
                **dict(metadata or {}),
            },
        )
        return ExperimentResult(key=key, opinions=opinions)
