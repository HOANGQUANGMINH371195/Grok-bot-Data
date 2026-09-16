import os
import re

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from vda_data.ingestion import ArtifactVersion, SourceRegistryError

from .application import LocalApiError, LocalApplication, LocalProfile

app = FastAPI(title="VDaAgent API", version="0.1.0")
local = LocalApplication()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Principal-Id", "X-File-Name", "X-Content-SHA256"],
    max_age=600,
)


class _RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateConversationRequest(_RequestModel):
    conversation_id: str = Field(min_length=1, max_length=256)
    member_ids: list[str] = Field(min_length=1, max_length=32)
    bot_templates: dict[str, str] = Field(default_factory=dict, max_length=16)


class SendMessageRequest(_RequestModel):
    client_message_id: str = Field(min_length=1, max_length=256)
    body: str = Field(min_length=1, max_length=12000)


class BotTurnRequest(_RequestModel):
    bot_id: str = Field(min_length=1, max_length=256)
    turn_id: str = Field(min_length=1, max_length=256)


class CreateDatasetRequest(_RequestModel):
    dataset_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ProfileDatasetRequest(_RequestModel):
    artifact_id: str = Field(min_length=1, max_length=256)


def _local_demo_enabled() -> bool:
    return os.getenv("VDA_LOCAL_DEMO", "false").lower() == "true"


def _principal(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=401, detail="X-Principal-Id is required for local demo")
    return value


def _local_demo_guard() -> None:
    if not _local_demo_enabled():
        raise HTTPException(status_code=404, detail="local demo is disabled")


def _local_resource_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="local dataset or artifact is not available")


def _filename(value: str | None) -> str:
    if (
        not value
        or len(value) > 255
        or "/" in value
        or "\\" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise HTTPException(status_code=422, detail="X-File-Name is invalid")
    return value


def _expected_sha256(value: str | None) -> str | None:
    if value is None:
        return None
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        raise HTTPException(status_code=422, detail="X-Content-SHA256 must be lowercase SHA-256")
    return value


async def _read_bounded_upload(request: Request, max_bytes: int) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Content-Length is invalid") from exc
        if declared_size < 0:
            raise HTTPException(status_code=400, detail="Content-Length is invalid")
        if declared_size > max_bytes:
            raise HTTPException(status_code=413, detail="upload exceeds max_file_bytes")
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > max_bytes:
            raise HTTPException(status_code=413, detail="upload exceeds max_file_bytes")
        payload.extend(chunk)
    return bytes(payload)


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
    _local_demo_guard()
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
    _local_demo_guard()
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
    _local_demo_guard()
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


@app.get("/v1/local/conversations/{conversation_id}/events")
def read_local_events(
    conversation_id: str,
    after_seq: int = Query(default=0, ge=0),
    x_principal_id: str | None = Header(default=None),
) -> dict[str, object]:
    _local_demo_guard()
    principal_id = _principal(x_principal_id)
    try:
        events, high_watermark = local.read_events(conversation_id, principal_id, after_seq)
    except (LocalApiError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "high_watermark": high_watermark,
        "events": [
            {
                "event_id": event.event_id,
                "event_sequence": event.event_sequence,
                "event_type": event.event_type,
                "payload": event.payload,
            }
            for event in events
        ],
    }


@app.post("/v1/local/conversations/{conversation_id}/bot-turn", status_code=201)
def run_local_bot_turn(
    conversation_id: str,
    request: BotTurnRequest,
    x_principal_id: str | None = Header(default=None),
) -> dict[str, object]:
    _local_demo_guard()
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


@app.post("/v1/local/workspaces/{workspace_id}/datasets", status_code=201)
def create_local_dataset(
    workspace_id: str,
    request: CreateDatasetRequest,
    x_principal_id: str | None = Header(default=None),
) -> dict[str, str]:
    _local_demo_guard()
    principal_id = _principal(x_principal_id)
    try:
        dataset = local.create_dataset(workspace_id, request.dataset_id, principal_id)
    except PermissionError as exc:
        raise _local_resource_not_found() from exc
    except LocalApiError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"dataset_id": dataset.dataset_id, "workspace_id": dataset.workspace_id}


@app.post(
    "/v1/local/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}",
    status_code=201,
)
async def upload_local_dataset(
    workspace_id: str,
    dataset_id: str,
    upload_id: str,
    request: Request,
    x_principal_id: str | None = Header(default=None),
    x_file_name: str | None = Header(default=None),
    x_content_sha256: str | None = Header(default=None),
) -> dict[str, object]:
    _local_demo_guard()
    principal_id = _principal(x_principal_id)
    filename = _filename(x_file_name)
    expected_sha256 = _expected_sha256(x_content_sha256)
    payload = await _read_bounded_upload(request, local.max_upload_bytes)
    try:
        artifact = local.upload_dataset(
            workspace_id,
            dataset_id,
            principal_id,
            upload_id,
            filename,
            payload,
            expected_sha256=expected_sha256,
        )
    except (LocalApiError, PermissionError) as exc:
        raise _local_resource_not_found() from exc
    except SourceRegistryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _artifact_response(dataset_id, artifact)


@app.post("/v1/local/workspaces/{workspace_id}/datasets/{dataset_id}/profiles", status_code=201)
def profile_local_dataset(
    workspace_id: str,
    dataset_id: str,
    request: ProfileDatasetRequest,
    x_principal_id: str | None = Header(default=None),
) -> dict[str, object]:
    _local_demo_guard()
    principal_id = _principal(x_principal_id)
    try:
        profile = local.profile_dataset(workspace_id, dataset_id, principal_id, request.artifact_id)
    except (LocalApiError, PermissionError, SourceRegistryError) as exc:
        raise _local_resource_not_found() from exc
    return _profile_response(profile)


def _artifact_response(dataset_id: str, artifact: ArtifactVersion) -> dict[str, object]:
    return {
        "artifact_id": artifact.artifact_id,
        "dataset_id": dataset_id,
        "workspace_id": artifact.workspace_id,
        "source_sha256": artifact.source_sha256,
        "object_version_id": artifact.object_version_id,
        "size_bytes": artifact.size_bytes,
        "format": artifact.format,
        "headers": list(artifact.headers),
        "row_count": artifact.row_count,
        "status": artifact.status.value,
    }


def _profile_response(profile: LocalProfile) -> dict[str, object]:
    return {
        "profile_id": profile.profile_id,
        "dataset_id": profile.dataset_id,
        "workspace_id": profile.workspace_id,
        "artifact_id": profile.artifact_id,
        "source_sha256": profile.source_sha256,
        "row_count": profile.row_count,
        "column_count": profile.column_count,
        "method_version": profile.method_version,
        "status": "completed",
        "evidence": {
            "evidence_id": profile.evidence.evidence_id,
            "source_version": profile.evidence.source_version,
            "method_version": profile.evidence.method_version,
            "cell_refs": list(profile.evidence.cell_refs),
            "limitations": list(profile.evidence.limitations),
            "approved": profile.evidence.approved,
        },
        "columns": [
            {
                "name": column.name,
                "physical_type": column.physical_type,
                "non_null_count": column.non_null_count,
                "null_count": column.null_count,
                "null_rate": column.null_rate,
                "distinct_non_null_count": column.distinct_non_null_count,
                "pii_signal_counts": column.pii_signal_counts,
            }
            for column in profile.columns
        ],
    }
