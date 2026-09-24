"""Minimal provider protocol.

Concrete OpenAI/Anthropic/Gemini adapters can implement this without leaking
provider-specific code into trading logic.
"""
from typing import Protocol

from .models import AgentContext


class ModelProvider(Protocol):
    def structured_decision(
        self,
        *,
        agent_name: str,
        system_instruction: str,
        context: AgentContext,
        schema: dict,
    ) -> dict:
        """Return a JSON-compatible object that conforms to schema."""
        ...
