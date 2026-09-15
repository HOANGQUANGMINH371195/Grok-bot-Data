import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .application import LocalApiError, LocalApplication

app = FastAPI(title="VDaAgent API", version="0.1.0")
local = LocalApplication()


class CreateConversationRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=256)
    member_ids: list[str] = Field(min_length=1, max_length=32)
    bot_templates: dict[str, str] = Field(default_factory=dict, max_length=16)


class SendMessageRequest(BaseModel):
    client_message_id: str = Field(min_length=1, max_length=256)
    body: str = Field(min_length=1, max_length=12000)


class BotTurnRequest(BaseModel):
    bot_id: str = Field(min_length=1, max_length=256)
    turn_id: str = Field(min_length=1, max_length=256)


def _local_demo_enabled() -> bool:
    return os.getenv("VDA_LOCAL_DEMO", "false").lower() == "true"


def _principal(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=401, detail="X-Principal-Id is required for local demo")
    return value


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
def readyz() -> dict[str, str]:
    if _local_demo_enabled():
        return {"status": "ready", "mode": "local_demo"}
    return {"status": "not_ready", "reason": "M1 dependencies are not configured"}


@app.post("/v1/local/workspaces/{workspace_id}/conversations", status_code=201)
def create_local_conversation(
    workspace_id: str,
    request: CreateConversationRequest,
    x_principal_id: str | None = Header(default=None),
) -> dict[str, object]:
    if not _local_demo_enabled():
        raise HTTPException(status_code=404, detail="local demo is disabled")
    principal_id = _principal(x_principal_id)
    try:
        conversation = local.create_conversation(
            workspace_id,
            request.conversation_id,
            principal_id,
            request.member_ids,
            request.bot_templates,
        )
    except LocalApiError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"conversation_id": request.conversation_id, "workspace_id": conversation.workspace_id}


@app.post("/v1/local/conversations/{conversation_id}/messages", status_code=201)
def send_local_message(
    conversation_id: str,
    request: SendMessageRequest,
    x_principal_id: str | None = Header(default=None),
) -> dict[str, object]:
    if not _local_demo_enabled():
        raise HTTPException(status_code=404, detail="local demo is disabled")
    principal_id = _principal(x_principal_id)
    try:
        ack = local.send(conversation_id, principal_id, request.client_message_id, request.body)
    except (LocalApiError, PermissionError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "message_id": ack.message.message_id,
        "sequence": ack.message.sequence,
        "bot_dispatch": ack.bot_dispatch,
        "event_id": ack.event.event_id,
    }


@app.get("/v1/local/conversations/{conversation_id}/messages")
def read_local_messages(
    conversation_id: str,
    x_principal_id: str | None = Header(default=None),
) -> dict[str, object]:
    if not _local_demo_enabled():
        raise HTTPException(status_code=404, detail="local demo is disabled")
    principal_id = _principal(x_principal_id)
    try:
        messages = local.read(conversation_id, principal_id)
    except (LocalApiError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "messages": [
            {
                "message_id": message.message_id,
                "sender_id": message.sender_id,
                "sequence": message.sequence,
                "body": message.body,
            }
            for message in messages
        ]
    }


@app.post("/v1/local/conversations/{conversation_id}/bot-turn", status_code=201)
def run_local_bot_turn(
    conversation_id: str,
    request: BotTurnRequest,
    x_principal_id: str | None = Header(default=None),
) -> dict[str, object]:
    if not _local_demo_enabled():
        raise HTTPException(status_code=404, detail="local demo is disabled")
    principal_id = _principal(x_principal_id)
    try:
        result, ack = local.run_bot_turn(
            conversation_id, principal_id, request.bot_id, request.turn_id
        )
    except (LocalApiError, PermissionError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {
        "status": result.status.value,
        "provider": result.provider,
        "model": result.model,
        "error_code": result.error_code,
        "message_id": ack.message.message_id if ack else None,
        "sequence": ack.message.sequence if ack else None,
        "text": result.text,
    }
