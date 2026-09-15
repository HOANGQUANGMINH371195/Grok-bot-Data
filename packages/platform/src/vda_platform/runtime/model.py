from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ToolCall:
    tool_id: str
    payload: dict[str, object]


@dataclass(frozen=True)
class ModelResponse:
    text: str
    tool_calls: tuple[ToolCall, ...] = ()
    provider: str = "fake"
    model: str = "fake-grounded-v1"
    usage_input_tokens: int = 0
    usage_output_tokens: int = 0


class ModelProvider(Protocol):
    def complete(self, *, context: tuple[str, ...], tool_ids: tuple[str, ...]) -> ModelResponse: ...
