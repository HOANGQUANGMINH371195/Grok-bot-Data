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
