import pytest
from vda_platform.conversation import ConversationState, IdempotencyConflict, MembershipError


def test_message_idempotency_returns_same_message_and_rejects_payload_reuse() -> None:
    state = ConversationState("room-1")
    state.add_member("human-1")
    first = state.append_message("human-1", "client-1", "hello")
    assert state.append_message("human-1", "client-1", "hello") == first
    with pytest.raises(IdempotencyConflict):
        state.append_message("human-1", "client-1", "tampered")
    assert len(state.messages) == 1
    assert state.event_sequence == 1


def test_rejoin_starts_new_visibility_interval() -> None:
    state = ConversationState("room-1")
    state.add_member("human-1")
    state.append_message("human-1", "c1", "before leave")
    state.remove_member("human-1")
    state.add_member("human-1")
    state.append_message("human-1", "c2", "after rejoin")
    assert [message.body for message in state.visible_messages("human-1")] == ["after rejoin"]


def test_non_member_cannot_send_or_read() -> None:
    state = ConversationState("room-1")
    with pytest.raises(MembershipError):
        state.append_message("human-1", "c1", "no")
    with pytest.raises(MembershipError):
        state.visible_messages("human-1")
