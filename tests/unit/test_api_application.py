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


def test_local_application_runs_guarded_fake_bot_turn_and_commits_bot_message() -> None:
    application = LocalApplication()
    application.create_conversation("w", "bot-room", "human-1", ["human-1", "bot-1"])
    result, ack = application.run_bot_turn("bot-room", "human-1", "bot-1", "turn-1")
    assert result.status.value == "ok"
    assert ack is not None
    assert ack.message.sender_id == "bot-1"
    assert "verified evidence" in ack.message.body
    assert [message.sender_id for message in application.read("bot-room", "human-1")] == ["bot-1"]


def test_local_application_rejects_bot_turn_from_nonmember() -> None:
    application = LocalApplication()
    application.create_conversation("w", "bot-room-2", "human-1", ["human-1", "bot-1"])
    with pytest.raises(PermissionError, match="active member"):
        application.run_bot_turn("bot-room-2", "human-2", "bot-1", "turn-1")
