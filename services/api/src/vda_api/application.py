from __future__ import annotations

from dataclasses import dataclass

from vda_platform.conversation import ConversationOutbox, ConversationState, MessageAck


class LocalApiError(ValueError):
    """Local demo command failed its workspace or membership contract."""


@dataclass
class LocalConversation:
    workspace_id: str
    owner_id: str
    outbox: ConversationOutbox


class LocalApplication:
    """Contract harness for the local demo; production uses DB-backed repositories."""

    def __init__(self) -> None:
        self._conversations: dict[str, LocalConversation] = {}

    def create_conversation(
        self, workspace_id: str, conversation_id: str, owner_id: str, members: list[str]
    ) -> LocalConversation:
        if conversation_id in self._conversations:
            raise LocalApiError("conversation already exists")
        if owner_id not in members:
            raise LocalApiError("owner must be a member")
        state = ConversationState(conversation_id)
        for member_id in dict.fromkeys(members):
            state.add_member(member_id)
        conversation = LocalConversation(
            workspace_id, owner_id, ConversationOutbox(workspace_id, state)
        )
        self._conversations[conversation_id] = conversation
        return conversation

    def get(self, conversation_id: str) -> LocalConversation:
        try:
            return self._conversations[conversation_id]
        except KeyError as exc:
            raise LocalApiError("conversation not found") from exc

    def send(
        self, conversation_id: str, actor_id: str, client_message_id: str, body: str
    ) -> MessageAck:
        conversation = self.get(conversation_id)
        return conversation.outbox.append_human_message(actor_id, client_message_id, body)

    def read(self, conversation_id: str, actor_id: str):
        conversation = self.get(conversation_id)
        return conversation.outbox.conversation.visible_messages(actor_id)
