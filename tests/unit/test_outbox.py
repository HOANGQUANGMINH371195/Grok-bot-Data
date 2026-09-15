import pytest

from vda_platform.conversation import ConversationOutbox, ConversationState


def test_human_ack_survives_bot_quota_rejection_and_outbox_is_deduplicated() -> None:
    state = ConversationState("room-1")
    state.add_member("human-1")
    outbox = ConversationOutbox("workspace-1", state)
    first = outbox.append_human_message("human-1", "client-1", "hello")
    assert first.bot_dispatch == "rejected_quota"
    duplicate = outbox.append_human_message("human-1", "client-1", "hello")
    assert duplicate.message.message_id == first.message.message_id
    assert len(outbox.events) == 1
    assert len(state.messages) == 1


def test_bot_dispatch_consumes_quota_without_changing_human_message_commit() -> None:
    state = ConversationState("room-1")
    state.add_member("human-1")
    outbox = ConversationOutbox("workspace-1", state)
    outbox.set_bot_quota(1)
    ack = outbox.append_human_message("human-1", "client-1", "@bot profile")
    assert ack.bot_dispatch == "queued"
    assert ack.event.event_sequence == 1


def test_idempotent_retry_after_later_message_reuses_original_event_and_outcome() -> None:
    state = ConversationState("room-2")
    state.add_member("human-1")
    outbox = ConversationOutbox("workspace-1", state)
    outbox.set_bot_quota(1)
    first = outbox.append_human_message("human-1", "client-1", "first")
    outbox.append_human_message("human-1", "client-2", "second")

    retry = outbox.append_human_message("human-1", "client-1", "first")
    assert retry.message.message_id == first.message.message_id
    assert retry.event.event_id == first.event.event_id
    assert retry.bot_dispatch == "queued"
    assert len(outbox.events) == 2


def test_inactive_member_cannot_read_after_leave_or_send() -> None:
    state = ConversationState("room-3")
    state.add_member("human-1")
    outbox = ConversationOutbox("workspace-1", state)
    outbox.append_human_message("human-1", "client-1", "before leave")
    state.remove_member("human-1")

    with pytest.raises(PermissionError, match="active member"):
        state.visible_messages("human-1")
    with pytest.raises(PermissionError, match="active member"):
        outbox.append_human_message("human-1", "client-2", "after leave")
