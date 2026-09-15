"""Conversation invariants independent of persistence and transport."""

from .state import (
    ConversationState,
    IdempotencyConflict,
    MembershipError,
    Message,
)

__all__ = ["ConversationState", "IdempotencyConflict", "MembershipError", "Message"]
