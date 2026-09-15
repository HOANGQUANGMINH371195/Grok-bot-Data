import pytest
from vda_api.application import LocalApiError, LocalApplication


def test_local_application_preserves_message_ack_and_membership_visibility() -> None:
    application = LocalApplication()
    application.create_conversation("w", "room", "human-1", ["human-1", "human-2"])
    ack = application.send("room", "human-1", "client-1", "hello")
    assert ack.message.sequence == 1
    assert [message.body for message in application.read("room", "human-2")] == ["hello"]


def test_local_application_rejects_unknown_conversation_and_nonmember() -> None:
    application = LocalApplication()
    with pytest.raises(LocalApiError, match="not found"):
        application.send("missing", "human-1", "client-1", "hello")
    application.create_conversation("w", "room", "human-1", ["human-1"])
    with pytest.raises(PermissionError):
        application.send("room", "human-2", "client-1", "hello")
