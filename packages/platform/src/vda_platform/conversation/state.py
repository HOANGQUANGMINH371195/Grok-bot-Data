from __future__ import annotations

from dataclasses import dataclass


class MembershipError(PermissionError):
    """The actor has no active interval in this conversation."""


class IdempotencyConflict(ValueError):
    """A client reused an idempotency key with different content."""


@dataclass(frozen=True)
class MemberInterval:
    principal_id: str
    joined_at_seq: int
    left_at_seq: int | None = None

    @property
    def active(self) -> bool:
        return self.left_at_seq is None


@dataclass(frozen=True)
class Message:
    message_id: str
    conversation_id: str
    sender_id: str
    sequence: int
    client_message_id: str
    body: str
    policy_generation: int


class ConversationState:
    """A deterministic aggregate used by DB repositories and offline state-machine tests."""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        self._members: dict[str, list[MemberInterval]] = {}
        self._messages: list[Message] = []
        self._idempotency: dict[tuple[str, str], Message] = {}
        self.policy_generation = 0
        self.event_sequence = 0

    @property
    def messages(self) -> tuple[Message, ...]:
        return tuple(self._messages)

    def add_member(self, principal_id: str) -> MemberInterval:
        if self._active_interval(principal_id) is not None:
            raise MembershipError("principal already active")
        self.policy_generation += 1
        interval = MemberInterval(principal_id, len(self._messages) + 1)
        self._members.setdefault(principal_id, []).append(interval)
        return interval

    def remove_member(self, principal_id: str) -> None:
        intervals = self._members.get(principal_id, [])
        active = self._active_interval(principal_id)
        if active is None:
            raise MembershipError("principal is not active")
        intervals[-1] = MemberInterval(
            active.principal_id, active.joined_at_seq, len(self._messages) + 1
        )
        self.policy_generation += 1

    def visible_messages(self, principal_id: str) -> tuple[Message, ...]:
        intervals = self._members.get(principal_id, [])
        visible_from = max((interval.joined_at_seq for interval in intervals), default=None)
        if visible_from is None:
            raise MembershipError("principal is not a member")
        return tuple(message for message in self._messages if message.sequence >= visible_from)

    def append_message(self, sender_id: str, client_message_id: str, body: str) -> Message:
        if self._active_interval(sender_id) is None:
            raise MembershipError("sender is not an active member")
        if not client_message_id or not body:
            raise ValueError("client_message_id and body are required")
        key = (sender_id, client_message_id)
        previous = self._idempotency.get(key)
        if previous is not None:
            if previous.body != body:
                raise IdempotencyConflict("same client_message_id has different payload")
            return previous
        sequence = len(self._messages) + 1
        message = Message(
            message_id=f"{self.conversation_id}:{sequence}",
            conversation_id=self.conversation_id,
            sender_id=sender_id,
            sequence=sequence,
            client_message_id=client_message_id,
            body=body,
            policy_generation=self.policy_generation,
        )
        self._messages.append(message)
        self._idempotency[key] = message
        self.event_sequence += 1
        return message

    def _active_interval(self, principal_id: str) -> MemberInterval | None:
        intervals = self._members.get(principal_id, [])
        return next((interval for interval in reversed(intervals) if interval.active), None)
