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


def test_local_application_reconnects_from_event_cursor() -> None:
    application = LocalApplication()
    application.create_conversation("w", "events-room", "human-1", ["human-1"])
    application.send("events-room", "human-1", "c1", "first")
    first, watermark = application.read_events("events-room", "human-1", 0)
    assert len(first) == 1
    application.send("events-room", "human-1", "c2", "second")
    replay, new_watermark = application.read_events("events-room", "human-1", watermark)
    assert [event.payload["message_id"] for event in replay] == ["events-room:2"]
    assert new_watermark > watermark


def test_local_application_profiles_only_immutable_actor_visible_artifacts() -> None:
    application = LocalApplication()
    application.create_dataset("workspace-a", "sales", "owner")
    payload = b"amount,email\n10.5,alice@example.com\n,not-an-email\n"
    artifact = application.upload_dataset(
        "workspace-a", "sales", "owner", "upload-1", "sales.csv", payload
    )
    retry = application.upload_dataset(
        "workspace-a", "sales", "owner", "upload-1", "sales.csv", payload
    )
    assert retry == artifact

    profile = application.profile_dataset("workspace-a", "sales", "owner", artifact.artifact_id)
    assert profile.artifact_id == artifact.artifact_id
    assert profile.evidence.approved is False
    email = next(column for column in profile.columns if column.name == "email")
    assert email.pii_signal_counts["email"] == 1
    assert "alice@example.com" not in repr(profile)
    assert (
        application.profile_dataset("workspace-a", "sales", "owner", artifact.artifact_id)
        == profile
    )

    application.create_dataset("workspace-b", "sales", "other")
    with pytest.raises(LocalApiError, match="not available"):
        application.profile_dataset("workspace-b", "sales", "other", artifact.artifact_id)
    with pytest.raises(PermissionError, match="not visible"):
        application.upload_dataset(
            "workspace-a", "sales", "intruder", "upload-2", "sales.csv", payload
        )
