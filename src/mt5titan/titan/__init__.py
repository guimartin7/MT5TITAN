"""Provider-agnostic Titan intelligence agents."""

from .agents import MacroAgent, NewsAgent, TechnicalAgent
from .benchmark import PromotionPolicy, compare_quant_vs_ai
from .committee import AICommittee, CommitteePolicy
from .models import AgentContext, AgentOpinion, AgentVerdict
from .provider import ModelProvider
from .replay import OpinionReplayStore

__all__ = [
    "AICommittee",
    "AgentContext",
    "AgentOpinion",
    "AgentVerdict",
    "CommitteePolicy",
    "MacroAgent",
    "ModelProvider",
    "NewsAgent",
    "OpinionReplayStore",
    "PromotionPolicy",
    "TechnicalAgent",
    "compare_quant_vs_ai",
]
