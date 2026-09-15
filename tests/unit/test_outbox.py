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
