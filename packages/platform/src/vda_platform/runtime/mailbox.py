from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


class MailboxError(ValueError):
    """Invalid peer message or handoff."""


MailboxKind = Literal["request", "question", "status", "fyi", "result"]


@dataclass(frozen=True)
class MailboxMessage:
    message_id: str
    correlation_id: str
    conversation_id: str
    source_bot_id: str
    target_bot_id: str
    kind: MailboxKind
    body: str


@dataclass(frozen=True)
class Handoff:
    stage_id: str
    conversation_id: str
    owner_bot_id: str
    hop_count: int
    terminal_source: str | None = None


class Mailbox:
    def __init__(self, conversation_id: str, members: set[str], max_hops: int = 6) -> None:
        self.conversation_id = conversation_id
        self.members = set(members)
        self.max_hops = max_hops
        self._messages: dict[tuple[str, str], MailboxMessage] = {}
        self._handoffs: dict[str, Handoff] = {}

    @property
    def messages(self) -> tuple[MailboxMessage, ...]:
        return tuple(self._messages.values())

    def send(
        self,
        *,
        correlation_id: str,
        source_bot_id: str,
        target_bot_id: str,
        kind: MailboxKind,
        body: str,
    ) -> MailboxMessage:
        if source_bot_id == target_bot_id:
            raise MailboxError("bot cannot message itself")
        if source_bot_id not in self.members or target_bot_id not in self.members:
            raise MailboxError("peer is not an active member")
        if not body:
            raise MailboxError("mailbox body is required")
        key = (correlation_id, target_bot_id)
        existing = self._messages.get(key)
        if existing is not None:
            if existing.body != body or existing.source_bot_id != source_bot_id:
                raise MailboxError("correlation already has a different message")
            return existing
        message = MailboxMessage(
            f"{correlation_id}:{target_bot_id}",
            correlation_id,
            self.conversation_id,
            source_bot_id,
            target_bot_id,
            kind,
            body,
        )
        self._messages[key] = message
        return message

    def create_handoff(self, stage_id: str, owner_bot_id: str) -> Handoff:
        if owner_bot_id not in self.members:
            raise MailboxError("handoff owner is not a member")
        if stage_id in self._handoffs:
            raise MailboxError("stage already exists")
        handoff = Handoff(stage_id, self.conversation_id, owner_bot_id, 0)
        self._handoffs[stage_id] = handoff
        return handoff

    def handoff(
        self, stage_id: str, source_bot_id: str, target_bot_id: str, expected_hop: int
    ) -> Handoff:
        current = self._handoffs.get(stage_id)
        if (
            current is None
            or current.owner_bot_id != source_bot_id
            or current.hop_count != expected_hop
        ):
            raise MailboxError("handoff compare-and-set failed")
        if target_bot_id not in self.members or target_bot_id == source_bot_id:
            raise MailboxError("invalid handoff target")
        if current.terminal_source == target_bot_id:
            raise MailboxError("handoff bounce detected")
        next_hop = current.hop_count + 1
        if next_hop > self.max_hops:
            raise MailboxError("handoff hop limit exceeded")
        updated = replace(
            current, owner_bot_id=target_bot_id, hop_count=next_hop, terminal_source=source_bot_id
        )
        self._handoffs[stage_id] = updated
        return updated
