"""Conversation invariants independent of persistence and transport."""

from .outbox import ConversationOutbox, MessageAck, OutboxEvent
from .state import (
    ConversationState,
    IdempotencyConflict,
    MembershipError,
    Message,
)

__all__ = [
    "ConversationOutbox",
    "ConversationState",
    "IdempotencyConflict",
    "MembershipError",
    "Message",
    "MessageAck",
    "OutboxEvent",
]
