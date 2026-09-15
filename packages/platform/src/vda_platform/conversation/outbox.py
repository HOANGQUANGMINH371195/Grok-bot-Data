from __future__ import annotations

from dataclasses import dataclass

from .state import ConversationState, Message


@dataclass(frozen=True)
class OutboxEvent:
    event_id: str
    event_type: str
    workspace_id: str
    conversation_id: str
    event_sequence: int
    payload: dict[str, object]


@dataclass(frozen=True)
class MessageAck:
    message: Message
    bot_dispatch: str
    event: OutboxEvent


class ConversationOutbox:
    """Atomic-in-memory analogue of message+event+outbox commit."""

    def __init__(self, workspace_id: str, conversation: ConversationState) -> None:
        self.workspace_id = workspace_id
        self.conversation = conversation
        self._events: list[OutboxEvent] = []
        self._bot_quota = 0

    @property
    def events(self) -> tuple[OutboxEvent, ...]:
        return tuple(self._events)

    def set_bot_quota(self, available: int) -> None:
        if available < 0:
            raise ValueError("quota cannot be negative")
        self._bot_quota = available

    def append_human_message(self, sender_id: str, client_message_id: str, body: str) -> MessageAck:
        message = self.conversation.append_message(sender_id, client_message_id, body)
        event = OutboxEvent(
            event_id=f"{self.workspace_id}:{self.conversation.conversation_id}:{self.conversation.event_sequence}",
            event_type="message.created",
            workspace_id=self.workspace_id,
            conversation_id=self.conversation.conversation_id,
            event_sequence=self.conversation.event_sequence,
            payload={"message_id": message.message_id, "sender_id": sender_id},
        )
        if not any(existing.event_id == event.event_id for existing in self._events):
            self._events.append(event)
        dispatch = "queued" if self._bot_quota > 0 else "rejected_quota"
        if dispatch == "queued":
            self._bot_quota -= 1
        return MessageAck(message, dispatch, event)
