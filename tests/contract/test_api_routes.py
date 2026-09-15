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
