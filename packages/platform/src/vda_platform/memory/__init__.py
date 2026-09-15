"""Audience-scoped memory and bounded context construction."""

from .context import (
    BuiltContext,
    ContextBudget,
    ContextOverflow,
    MemoryRecord,
    build_context,
)

__all__ = ["BuiltContext", "ContextBudget", "ContextOverflow", "MemoryRecord", "build_context"]
