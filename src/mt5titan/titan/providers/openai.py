"""OpenAI Responses API adapter with strict Structured Outputs.

Secrets are never accepted in AgentContext. Authentication is delegated to the
official OpenAI SDK, which reads OPENAI_API_KEY from the environment.
"""
import json
import os
from typing import Any

from mt5titan.titan.models import AgentContext


class OpenAIProvider:
    def __init__(
        self,
        *,
        model: str | None = None,
        client: Any | None = None,
    ):
        self.model = model or os.getenv("OPENAI_MODEL")
        if not self.model:
            raise RuntimeError("OPENAI_MODEL is required")

        if client is None:
            try:
                from openai import OpenAI
            except ImportError as error:
                raise RuntimeError(
                    'OpenAI SDK is not installed. Install the "ai-openai" extra.'
                ) from error
            client = OpenAI()
        self.client = client

    def structured_decision(
        self,
        *,
        agent_name: str,
        system_instruction: str,
        context: AgentContext,
        schema: dict,
    ) -> dict:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system_instruction,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                context.to_payload(),
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        }
                    ],
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": f"{agent_name}_decision",
                    "strict": True,
                    "schema": schema,
                }
            },
        )

        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise RuntimeError("OpenAI response did not contain structured output text")

        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as error:
            raise RuntimeError("OpenAI structured output was not valid JSON") from error

        if not isinstance(payload, dict):
            raise RuntimeError("OpenAI structured output must be a JSON object")
        return payload
