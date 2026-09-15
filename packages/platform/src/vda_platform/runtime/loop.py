from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from vda_platform.memory import (
    BuiltContext,
    ContextBudget,
    ContextOverflow,
    MemoryRecord,
    build_context,
)
from vda_platform.tools import ToolContext, ToolDenied, ToolRegistry, ToolValidationError


class ModelToolCall(Protocol):
    tool_id: str
    payload: dict[str, object]


class ModelResponse(Protocol):
    text: str
    tool_calls: tuple[ModelToolCall, ...]
    provider: str
    model: str


class ModelProvider(Protocol):
    def complete(self, *, context: tuple[str, ...], tool_ids: tuple[str, ...]) -> ModelResponse: ...


class TurnStatus(StrEnum):
    OK = "ok"
    NEEDS_INPUT = "needs_input"
    DENIED = "denied"
    FAILED = "failed"


@dataclass(frozen=True)
class ToolResult:
    tool_id: str
    status: TurnStatus
    data: Any = None
    error: str | None = None


@dataclass(frozen=True)
class BotTurn:
    status: TurnStatus
    text: str
    provider: str
    model: str
    context: BuiltContext | None
    tool_results: tuple[ToolResult, ...] = ()
    error_code: str | None = None


class BotRuntime:
    """One bounded bot turn over the shared provider/tool/context contracts."""

    def __init__(
        self,
        provider: ModelProvider,
        registry: ToolRegistry,
        *,
        max_tool_calls: int = 3,
        max_output_chars: int = 16_000,
    ) -> None:
        if max_tool_calls < 1 or max_output_chars < 1:
            raise ValueError("runtime caps must be positive")
        self._provider = provider
        self._registry = registry
        self._max_tool_calls = max_tool_calls
        self._max_output_chars = max_output_chars

    def execute(
        self,
        *,
        actor_id: str,
        bot_id: str,
        bot_template: str,
        workspace_id: str,
        conversation_id: str,
        grant_version: int = 1,
        policy_generation: int = 1,
        fence: int,
        idempotency_key: str,
        system: str,
        history: tuple[str, ...],
        memories: tuple[MemoryRecord, ...] = (),
        results: tuple[str, ...] = (),
        budget: ContextBudget | None = None,
        handlers: dict[str, Callable[[ToolContext, dict[str, Any]], Any]] | None = None,
    ) -> BotTurn:
        allowed = self._registry.allowed_tools(bot_template)
        try:
            context = build_context(
                conversation_id=conversation_id,
                bot_id=bot_id,
                system=system,
                tool_descriptions=allowed,
                history=history,
                memories=memories,
                results=results,
                budget=budget,
            )
        except ContextOverflow:
            return BotTurn(
                TurnStatus.NEEDS_INPUT,
                "",
                "unknown",
                "unknown",
                None,
                error_code="context_budget_exceeded",
            )

        try:
            response = self._provider.complete(
                context=tuple(item.content for item in context.items), tool_ids=allowed
            )
        except Exception as exc:  # provider adapters normalize public errors; never expose detail
            return BotTurn(
                TurnStatus.FAILED,
                "",
                "unknown",
                "unknown",
                context,
                error_code=_safe_error_code(exc),
            )
        if len(response.text) > self._max_output_chars:
            return BotTurn(
                TurnStatus.FAILED,
                "",
                response.provider,
                response.model,
                context,
                error_code="model_output_limit",
            )
        if len(response.tool_calls) > self._max_tool_calls:
            return BotTurn(
                TurnStatus.FAILED,
                response.text,
                response.provider,
                response.model,
                context,
                error_code="tool_call_limit",
            )

        tool_results: list[ToolResult] = []
        for index, call in enumerate(response.tool_calls):
            handler = (handlers or {}).get(call.tool_id)
            if handler is None:
                tool_results.append(
                    ToolResult(call.tool_id, TurnStatus.DENIED, error="handler_unavailable")
                )
                continue
            tool_context = ToolContext(
                actor_id,
                bot_template,
                workspace_id,
                conversation_id,
                grant_version,
                policy_generation,
                fence,
                f"{idempotency_key}:{index}",
            )
            try:
                data = self._registry.invoke(call.tool_id, tool_context, call.payload, handler)
            except ToolDenied:
                tool_results.append(
                    ToolResult(call.tool_id, TurnStatus.DENIED, error="tool_denied")
                )
            except ToolValidationError:
                tool_results.append(
                    ToolResult(call.tool_id, TurnStatus.FAILED, error="tool_input_invalid")
                )
            except Exception as exc:  # handler detail must not reach model/UI
                tool_results.append(
                    ToolResult(call.tool_id, TurnStatus.FAILED, error=_safe_error_code(exc))
                )
            else:
                tool_results.append(ToolResult(call.tool_id, TurnStatus.OK, data=data))
        status = TurnStatus.OK
        if any(result.status is TurnStatus.DENIED for result in tool_results):
            status = TurnStatus.DENIED
        elif any(result.status is TurnStatus.FAILED for result in tool_results):
            status = TurnStatus.FAILED
        return BotTurn(
            status, response.text, response.provider, response.model, context, tuple(tool_results)
        )


def _safe_error_code(error: Exception) -> str:
    name = error.__class__.__name__.lower()
    return name if name.isidentifier() else "provider_error"
