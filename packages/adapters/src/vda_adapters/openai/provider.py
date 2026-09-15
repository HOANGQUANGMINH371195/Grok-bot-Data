from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
from pydantic import SecretStr

from vda_adapters.fake_model import ModelResponse, ToolCall


class ProviderProtocolError(RuntimeError):
    """Provider response is malformed or requests an unavailable tool."""


@dataclass(frozen=True)
class OpenAIProvider:
    api_key: SecretStr
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 30.0

    async def complete(
        self,
        *,
        context: tuple[str, ...],
        tool_ids: tuple[str, ...],
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> ModelResponse:
        """Make one explicitly requested call; no hidden retries for unknown side effects."""
        messages = [{"role": "user", "content": text} for text in context]
        payload = {"model": self.model, "messages": messages, "temperature": 0}
        headers = {"Authorization": f"Bearer {self.api_key.get_secret_value()}"}
        async with httpx.AsyncClient(
            base_url=self.base_url.rstrip("/"),
            headers=headers,
            timeout=self.timeout_seconds,
            transport=transport,
        ) as client:
            response = await client.post("/chat/completions", json=payload)
        if response.status_code >= 400:
            raise ProviderProtocolError(f"openai_http_{response.status_code}")
        try:
            body = response.json()
            choice = body["choices"][0]["message"]
            text = choice.get("content") or ""
            calls = tuple(self._tool_call(call, tool_ids) for call in choice.get("tool_calls", []))
            usage = body.get("usage", {})
            return ModelResponse(
                text,
                calls,
                "openai",
                self.model,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderProtocolError("openai_malformed_response") from exc

    @staticmethod
    def _tool_call(call: dict[str, object], allowed: tuple[str, ...]) -> ToolCall:
        try:
            function = call["function"]
            assert isinstance(function, dict)
            tool_id = function["name"]
            raw_arguments = function.get("arguments", "{}")
            assert isinstance(tool_id, str) and isinstance(raw_arguments, str)
            payload = json.loads(raw_arguments)
            if not isinstance(payload, dict) or tool_id not in allowed:
                raise ProviderProtocolError("openai_unavailable_tool")
            return ToolCall(tool_id, payload)
        except (KeyError, TypeError, ValueError, AssertionError, json.JSONDecodeError) as exc:
            if isinstance(exc, ProviderProtocolError):
                raise
            raise ProviderProtocolError("openai_malformed_tool_call") from exc
