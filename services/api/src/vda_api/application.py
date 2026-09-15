from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vda_adapters.fake_model import FakeModelProvider
from vda_platform.conversation import ConversationOutbox, ConversationState, MessageAck
from vda_platform.runtime import BotRuntime, BotTurn
from vda_platform.tools import ToolRegistry


class LocalApiError(ValueError):
    """Local demo command failed its workspace or membership contract."""


@dataclass
class LocalConversation:
    workspace_id: str
    owner_id: str
    outbox: ConversationOutbox
    bot_templates: dict[str, str]


class LocalApplication:
    """Contract harness for the local demo; production uses DB-backed repositories."""

    def __init__(self) -> None:
        self._conversations: dict[str, LocalConversation] = {}
        root = Path(__file__).resolve().parents[4]
        self._tool_registry = ToolRegistry.from_contract_root(root)

    def create_conversation(
        self,
        workspace_id: str,
        conversation_id: str,
        owner_id: str,
        members: list[str],
        bot_templates: dict[str, str] | None = None,
    ) -> LocalConversation:
        if conversation_id in self._conversations:
            raise LocalApiError("conversation already exists")
        if owner_id not in members:
            raise LocalApiError("owner must be a member")
        state = ConversationState(conversation_id)
        for member_id in dict.fromkeys(members):
            state.add_member(member_id)
        templates = dict(bot_templates or {})
        for member_id in members:
            if member_id.startswith("bot"):
                templates.setdefault(member_id, "DataAssistant")
        unknown = set(templates.values()) - {
            "DataAssistant", "DataSteward", "DataAnalyst", "ReportWriter"
        }
        if unknown:
            raise LocalApiError("unknown bot template")
        conversation = LocalConversation(
            workspace_id, owner_id, ConversationOutbox(workspace_id, state), templates
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

    def run_bot_turn(
        self, conversation_id: str, actor_id: str, bot_id: str, turn_id: str
    ) -> tuple[BotTurn, MessageAck | None]:
        conversation = self.get(conversation_id)
        if not conversation.outbox.conversation.is_active_member(actor_id):
            raise PermissionError("actor is not an active member")
        template = conversation.bot_templates.get(bot_id)
        if template is None or not conversation.outbox.conversation.is_active_member(bot_id):
            raise PermissionError("bot is not an active member")
        provider = FakeModelProvider()
        runtime = BotRuntime(provider, self._tool_registry)
        history = tuple(message.body for message in conversation.outbox.conversation.messages)
        result = runtime.execute(
            actor_id=actor_id,
            bot_id=bot_id,
            bot_template=template,
            workspace_id=conversation.workspace_id,
            conversation_id=conversation_id,
            fence=1,
            idempotency_key=turn_id,
            system="Answer only with verified evidence and ask for missing approvals.",
            history=history,
        )
        if result.status.value != "ok" or not result.text:
            return result, None
        ack = conversation.outbox.append_bot_message(bot_id, f"{turn_id}:response", result.text)
        return result, ack
