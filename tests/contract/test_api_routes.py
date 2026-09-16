import hashlib

from fastapi.testclient import TestClient
from vda_api.main import app


def test_local_demo_routes_are_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("VDA_LOCAL_DEMO", raising=False)
    response = TestClient(app).post(
        "/v1/local/workspaces/w/conversations",
        headers={"X-Principal-Id": "human"},
        json={"conversation_id": "disabled-room", "member_ids": ["human"]},
    )
    assert response.status_code == 404


def test_local_demo_routes_require_principal_and_round_trip_messages(monkeypatch) -> None:
    monkeypatch.setenv("VDA_LOCAL_DEMO", "true")
    client = TestClient(app)
    conversation_id = "route-room-contract"
    created = client.post(
        "/v1/local/workspaces/w/conversations",
        headers={"X-Principal-Id": "human"},
        json={"conversation_id": conversation_id, "member_ids": ["human", "bot"]},
    )
    assert created.status_code == 201
    missing_identity = client.post(
        f"/v1/local/conversations/{conversation_id}/messages",
        json={"client_message_id": "c1", "body": "hello"},
    )
    assert missing_identity.status_code == 401
    sent = client.post(
        f"/v1/local/conversations/{conversation_id}/messages",
        headers={"X-Principal-Id": "human"},
        json={"client_message_id": "c1", "body": "hello"},
    )
    assert sent.status_code == 201
    read = client.get(
        f"/v1/local/conversations/{conversation_id}/messages",
        headers={"X-Principal-Id": "bot"},
    )
    assert read.status_code == 200
    assert read.json()["messages"][0]["body"] == "hello"


def test_local_bot_turn_is_guarded_and_returns_durable_message(monkeypatch) -> None:
    monkeypatch.setenv("VDA_LOCAL_DEMO", "true")
    client = TestClient(app)
    conversation_id = "route-bot-contract"
    created = client.post(
        "/v1/local/workspaces/w/conversations",
        headers={"X-Principal-Id": "human"},
        json={"conversation_id": conversation_id, "member_ids": ["human", "bot-1"]},
    )
    assert created.status_code == 201
    turn = client.post(
        f"/v1/local/conversations/{conversation_id}/bot-turn",
        headers={"X-Principal-Id": "human"},
        json={"bot_id": "bot-1", "turn_id": "turn-route-1"},
    )
    assert turn.status_code == 201
    assert turn.json()["status"] == "ok"
    assert turn.json()["message_id"]


def test_local_events_support_cursor_reconnect(monkeypatch) -> None:
    monkeypatch.setenv("VDA_LOCAL_DEMO", "true")
    client = TestClient(app)
    conversation_id = "route-events-contract"
    created = client.post(
        "/v1/local/workspaces/w/conversations",
        headers={"X-Principal-Id": "human-events"},
        json={"conversation_id": conversation_id, "member_ids": ["human-events"]},
    )
    assert created.status_code == 201
    sent = client.post(
        f"/v1/local/conversations/{conversation_id}/messages",
        headers={"X-Principal-Id": "human-events"},
        json={"client_message_id": "event-1", "body": "one"},
    )
    assert sent.status_code == 201
    first = client.get(
        f"/v1/local/conversations/{conversation_id}/events?after_seq=0",
        headers={"X-Principal-Id": "human-events"},
    )
    assert first.status_code == 200
    cursor = first.json()["high_watermark"]
    client.post(
        f"/v1/local/conversations/{conversation_id}/messages",
        headers={"X-Principal-Id": "human-events"},
        json={"client_message_id": "event-2", "body": "two"},
    )
    replay = client.get(
        f"/v1/local/conversations/{conversation_id}/events?after_seq={cursor}",
        headers={"X-Principal-Id": "human-events"},
    )
    assert [event["event_sequence"] for event in replay.json()["events"]] == [2]


def test_local_dataset_profile_is_hash_pinned_and_does_not_return_raw_pii(monkeypatch) -> None:
    monkeypatch.setenv("VDA_LOCAL_DEMO", "true")
    client = TestClient(app)
    headers = {"X-Principal-Id": "dataset-owner"}
    workspace_id = "dataset-workspace-contract"
    dataset_id = "sales-profile-contract"
    created = client.post(
        f"/v1/local/workspaces/{workspace_id}/datasets",
        headers=headers,
        json={"dataset_id": dataset_id},
    )
    assert created.status_code == 201

    payload = b"amount,email\n10.5,alice@example.com\n,not-an-email\n"
    artifact = client.post(
        f"/v1/local/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/retryable-upload",
        headers={
            **headers,
            "X-File-Name": "sales.csv",
            "X-Content-SHA256": hashlib.sha256(payload).hexdigest(),
            "Content-Type": "text/csv",
        },
        content=payload,
    )
    assert artifact.status_code == 201
    assert artifact.json()["dataset_id"] == dataset_id
    repeated = client.post(
        f"/v1/local/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/retryable-upload",
        headers={
            **headers,
            "X-File-Name": "sales.csv",
            "X-Content-SHA256": hashlib.sha256(payload).hexdigest(),
            "Content-Type": "text/csv",
        },
        content=payload,
    )
    assert repeated.status_code == 201
    assert repeated.json()["artifact_id"] == artifact.json()["artifact_id"]

    profile = client.post(
        f"/v1/local/workspaces/{workspace_id}/datasets/{dataset_id}/profiles",
        headers=headers,
        json={"artifact_id": artifact.json()["artifact_id"]},
    )
    assert profile.status_code == 201
    body = profile.json()
    assert body["status"] == "completed"
    assert body["evidence"]["approved"] is False
    assert body["source_sha256"] == hashlib.sha256(payload).hexdigest()
    assert body["columns"][1]["pii_signal_counts"]["email"] == 1
    assert "alice@example.com" not in profile.text
    assert "top_values" not in profile.text

    mismatched_hash = client.post(
        f"/v1/local/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/bad-hash",
        headers={
            **headers,
            "X-File-Name": "sales.csv",
            "X-Content-SHA256": "0" * 64,
            "Content-Type": "text/csv",
        },
        content=payload,
    )
    assert mismatched_hash.status_code == 422
    wrong_actor = client.post(
        f"/v1/local/workspaces/{workspace_id}/datasets/{dataset_id}/profiles",
        headers={"X-Principal-Id": "intruder"},
        json={"artifact_id": artifact.json()["artifact_id"]},
    )
    assert wrong_actor.status_code == 404
