from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


class ContextOverflow(ValueError):
    """The mandatory context cannot fit the configured budget."""


Audience = Literal["conversation", "workspace", "private"]


@dataclass(frozen=True)
class ContextBudget:
    system: int = 2_000
    tools: int = 4_000
    history: int = 8_000
    memory: int = 4_000
    results: int = 4_000
    output: int = 2_000
    margin: int = 2_000

    @property
    def total(self) -> int:
        return (
            self.system
            + self.tools
            + self.history
            + self.memory
            + self.results
            + self.output
            + self.margin
        )


@dataclass(frozen=True)
class MemoryRecord:
    record_id: str
    conversation_id: str
    owner_bot_id: str
    content: str
    revision: int
    audience: Audience = "conversation"
    source_refs: tuple[str, ...] = ()
    generation: int = 0


@dataclass(frozen=True)
class ContextItem:
    kind: str
    content: str
    source_ref: str | None = None


@dataclass(frozen=True)
class BuiltContext:
    items: tuple[ContextItem, ...]
    used_tokens: int
    budget: ContextBudget
    summary_generation: int
    memory_revisions: tuple[int, ...]


def estimate_tokens(text: str) -> int:
    """Conservative deterministic estimator; provider tokenizer is a later adapter concern."""
    return max(1, (len(text.encode("utf-8")) + 3) // 4)


def build_context(
    *,
    conversation_id: str,
    bot_id: str,
    system: str,
    tool_descriptions: tuple[str, ...],
    history: tuple[str, ...],
    memories: tuple[MemoryRecord, ...],
    results: tuple[str, ...],
    budget: ContextBudget | None = None,
    summary_generation: int = 0,
) -> BuiltContext:
    budget = budget or ContextBudget()
    items: list[ContextItem] = [ContextItem("system", system)]
    items.extend(ContextItem("tools", value) for value in tool_descriptions)
    items.extend(ContextItem("history", value) for value in history)
    # Private memory is only valid for its exact conversation; workspace memory must still
    # be owned by the acting bot. A record from another conversation is never a cache hit.
    visible = [
        record
        for record in memories
        if record.owner_bot_id == bot_id
        and (record.conversation_id == conversation_id or record.audience == "workspace")
        and (record.audience != "private" or record.conversation_id == conversation_id)
    ]
    items.extend(ContextItem("memory", record.content, record.record_id) for record in visible)
    items.extend(ContextItem("result", value) for value in results)

    totals = {
        kind: sum(estimate_tokens(item.content) for item in items if item.kind == kind)
        for kind in ("system", "tools", "history", "memory", "result")
    }
    limits = {
        "system": budget.system,
        "tools": budget.tools,
        "history": budget.history,
        "memory": budget.memory,
        "result": budget.results,
    }
    over = [kind for kind, value in totals.items() if value > limits[kind]]
    if over:
        raise ContextOverflow(f"mandatory context exceeds {','.join(over)} budget component")
    used = sum(totals.values())
    available = budget.total - budget.output - budget.margin
    if used > available:
        raise ContextOverflow(
            "mandatory context exceeds total budget; summary or user narrowing required"
        )
    return BuiltContext(
        tuple(items),
        used,
        budget,
        summary_generation,
        tuple(record.revision for record in visible),
    )
