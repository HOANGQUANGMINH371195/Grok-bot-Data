from __future__ import annotations

from typing import Literal

from vda_platform.runtime.model import ModelResponse, ToolCall


class ProviderError(RuntimeError):
    """Provider failure used to exercise retry/recovery paths."""


FailureMode = Literal["timeout", "rate_limit", "malformed_tool_call"]


class FakeModelProvider:
    """Scriptable, deterministic provider; never reads credentials or calls the network."""

    def __init__(self, responses: tuple[ModelResponse, ...] = ()) -> None:
        self._responses = list(responses)
        self.calls = 0

    def enqueue(self, response: ModelResponse) -> None:
        self._responses.append(response)

    def fail_once(self, mode: FailureMode) -> None:
        self._responses.append(ModelResponse(text="", tool_calls=(ToolCall(f"__{mode}__", {}),)))

    def complete(self, *, context: tuple[str, ...], tool_ids: tuple[str, ...]) -> ModelResponse:
        self.calls += 1
        if not self._responses:
            return ModelResponse(text="I need more verified evidence to answer.")
        response = self._responses.pop(0)
        if response.tool_calls and response.tool_calls[0].tool_id == "__timeout__":
            raise ProviderError("provider_timeout")
        if response.tool_calls and response.tool_calls[0].tool_id == "__rate_limit__":
            raise ProviderError("provider_rate_limit")
        if response.tool_calls and response.tool_calls[0].tool_id == "__malformed_tool_call__":
            raise ProviderError("provider_malformed_tool_call")
        if any(call.tool_id not in tool_ids for call in response.tool_calls):
            raise ProviderError("provider_requested_unavailable_tool")
        del context  # Context is supplied to make tests explicit; fake never logs it.
        return response
