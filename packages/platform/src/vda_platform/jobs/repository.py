from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, Engine, text

from vda_platform.runtime.runs import FenceError, RunState

from .ledger import JobError


class RuntimeRepositoryError(JobError):
    """A durable runtime command violates its state or idempotency contract."""


@dataclass(frozen=True)
class RunLease:
    run_id: str
    task_id: str
    workspace_id: str
    state: RunState
    worker_id: str
    fence: int
    attempt_id: str
    attempt_number: int
    lease_expires_at: datetime | None
    checkpoint_revision: int
    checkpoint: dict[str, object] | None


@dataclass(frozen=True)
class ToolExecutionRecord:
    execution_id: str
    operation_key: str
    state: str
    output: dict[str, object] | None


@dataclass(frozen=True)
class EffectRecord:
    effect_id: str
    operation_key: str
    state: str
    result_ref: str | None


class PostgresRuntimeRepository:
    """Transactional runtime repository for the 0004_runtime schema.

    Every public mutation scopes the connection with ``SET LOCAL`` semantics before
    touching tenant rows. Claims commit the lease and attempt immediately, so no
    transaction is held while a worker calls a model or tool.
    """

    def __init__(self, engine: Engine, *, default_lease_seconds: int = 60) -> None:
        if default_lease_seconds <= 0:
            raise ValueError("default lease must be positive")
        self._engine = engine
        self._default_lease_seconds = default_lease_seconds

    @property
    def lease_seconds(self) -> int:
        return self._default_lease_seconds

    def create_task(
        self,
        *,
        workspace_id: str,
        task_id: str,
        kind: str,
        payload: Mapping[str, object],
        idempotency_key: str,
        root_task_id: str | None = None,
        parent_task_id: str | None = None,
        now: datetime | None = None,
    ) -> str:
        self._required(workspace_id, task_id, kind, idempotency_key)
        payload_json = _json_payload(payload)
        timestamp = _utc(now or datetime.now(UTC))
        with self._engine.begin() as connection:
            _scope(connection, workspace_id)
            existing = connection.execute(
                text(
                    """
                    SELECT id, kind, payload_json
                    FROM tasks
                    WHERE workspace_id = :workspace_id AND idempotency_key = :idempotency_key
                    """
                ),
                {"workspace_id": workspace_id, "idempotency_key": idempotency_key},
            ).mappings().first()
            if existing is not None:
                if existing["kind"] != kind or existing["payload_json"] != payload:
                    raise RuntimeRepositoryError(
                        "idempotency key was reused with different job input"
                    )
                return str(existing["id"])
            try:
                connection.execute(
                    text(
                        """
                        INSERT INTO tasks
                          (id, workspace_id, kind, idempotency_key, payload_json,
                           root_task_id, parent_task_id, created_at)
                        VALUES
                          (:id, :workspace_id, :kind, :idempotency_key,
                           CAST(:payload_json AS jsonb), :root_task_id,
                           :parent_task_id, :created_at)
                        """
                    ),
                    {
                        "id": task_id,
                        "workspace_id": workspace_id,
                        "kind": kind,
                        "idempotency_key": idempotency_key,
                        "payload_json": payload_json,
                        "root_task_id": root_task_id or task_id,
                        "parent_task_id": parent_task_id,
                        "created_at": timestamp,
                    },
                )
            except Exception as exc:
                raise RuntimeRepositoryError("task insert failed") from exc
        return task_id

    def create_run(
        self,
        *,
        workspace_id: str,
        run_id: str,
        task_id: str,
        conversation_id: str | None = None,
        bot_id: str | None = None,
        now: datetime | None = None,
        supersedes_run_id: str | None = None,
    ) -> str:
        self._required(workspace_id, run_id, task_id)
        timestamp = _utc(now or datetime.now(UTC))
        with self._engine.begin() as connection:
            _scope(connection, workspace_id)
            try:
                connection.execute(
                    text(
                        """
                        INSERT INTO runs
                          (id, workspace_id, task_id, conversation_id, bot_id,
                           state, created_at, updated_at, supersedes_run_id)
                        VALUES
                          (:id, :workspace_id, :task_id, :conversation_id, :bot_id,
                           'queued', :created_at, :updated_at, :supersedes_run_id)
                        """
                    ),
                    {
                        "id": run_id,
                        "workspace_id": workspace_id,
                        "task_id": task_id,
                        "conversation_id": conversation_id,
                        "bot_id": bot_id,
                        "created_at": timestamp,
                        "updated_at": timestamp,
                        "supersedes_run_id": supersedes_run_id,
                    },
                )
            except Exception as exc:
                raise RuntimeRepositoryError("run insert failed") from exc
        return run_id

    def claim_run(
        self,
        *,
        workspace_id: str,
        worker_id: str,
        now: datetime | None = None,
        lease_seconds: int | None = None,
    ) -> RunLease | None:
        self._required(workspace_id, worker_id)
        timestamp = _utc(now or datetime.now(UTC))
        seconds = lease_seconds if lease_seconds is not None else self._default_lease_seconds
        if seconds <= 0:
            raise RuntimeRepositoryError("lease must be positive")
        with self._engine.begin() as connection:
            _scope(connection, workspace_id)
            row = connection.execute(
                text(
                    """
                    SELECT id, task_id, workspace_id, fence, checkpoint_revision, checkpoint_json
                    FROM runs
                    WHERE workspace_id = :workspace_id
                      AND (
                        state = 'queued'
                        OR (state IN ('leased', 'running')
                            AND lease_expires_at IS NOT NULL
                            AND lease_expires_at <= :now)
                      )
                    ORDER BY created_at, id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """
                ),
                {"workspace_id": workspace_id, "now": timestamp},
            ).mappings().first()
            if row is None:
                return None
            fence = int(row["fence"]) + 1
            attempt_number = int(
                connection.execute(
                    text(
                        "SELECT COALESCE(MAX(attempt_number), 0) + 1 "
                        "FROM attempts WHERE run_id = :run_id"
                    ),
                    {"run_id": row["id"]},
                ).scalar_one()
            )
            attempt_id = f"attempt-{uuid.uuid4().hex}"
            lease_expires_at = timestamp + timedelta(seconds=seconds)
            connection.execute(
                text(
                    """
                    UPDATE runs
                    SET state = 'leased', lease_owner = :worker_id,
                        lease_expires_at = :lease_expires_at, fence = :fence,
                        updated_at = :updated_at
                    WHERE id = :run_id AND workspace_id = :workspace_id
                    """
                ),
                {
                    "worker_id": worker_id,
                    "lease_expires_at": lease_expires_at,
                    "fence": fence,
                    "updated_at": timestamp,
                    "run_id": row["id"],
                    "workspace_id": workspace_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO attempts
                      (id, workspace_id, run_id, attempt_number, worker_id, fence,
                       state, started_at)
                    VALUES
                      (:id, :workspace_id, :run_id, :attempt_number, :worker_id,
                       :fence, 'leased', :started_at)
                    """
                ),
                {
                    "id": attempt_id,
                    "workspace_id": workspace_id,
                    "run_id": row["id"],
                    "attempt_number": attempt_number,
                    "worker_id": worker_id,
                    "fence": fence,
                    "started_at": timestamp,
                },
            )
            return RunLease(
                str(row["id"]),
                str(row["task_id"]),
                workspace_id,
                RunState.LEASED,
                worker_id,
                fence,
                attempt_id,
                attempt_number,
                lease_expires_at,
                int(row["checkpoint_revision"]),
                _json_object(row["checkpoint_json"]),
            )

    def start_run(self, lease: RunLease, *, now: datetime | None = None) -> RunLease:
        return self._transition(lease, RunState.RUNNING, now=now)

    def wait(
        self,
        lease: RunLease,
        reason: str,
        *,
        now: datetime | None = None,
    ) -> RunLease:
        if reason not in {"input", "approval", "children", "tool", "peer"}:
            raise RuntimeRepositoryError("invalid wait reason")
        return self._transition(lease, RunState.WAITING, wait_reason=reason, now=now)

    def heartbeat(self, lease: RunLease, *, now: datetime | None = None) -> RunLease:
        timestamp = _utc(now or datetime.now(UTC))
        expiry = timestamp + timedelta(seconds=self._default_lease_seconds)
        with self._engine.begin() as connection:
            _scope(connection, lease.workspace_id)
            result = connection.execute(
                text(
                    """
                    UPDATE runs
                    SET lease_expires_at = :lease_expires_at, updated_at = :updated_at
                    WHERE id = :run_id AND workspace_id = :workspace_id
                      AND lease_owner = :worker_id AND fence = :fence
                      AND state IN ('leased', 'running')
                    """
                ),
                {
                    "lease_expires_at": expiry,
                    "updated_at": timestamp,
                    "run_id": lease.run_id,
                    "workspace_id": lease.workspace_id,
                    "worker_id": lease.worker_id,
                    "fence": lease.fence,
                },
            )
            if result.rowcount != 1:
                raise FenceError("stale or non-owner worker")
        return RunLease(**{**lease.__dict__, "lease_expires_at": expiry})

    def resume_run(
        self,
        *,
        workspace_id: str,
        run_id: str,
        now: datetime | None = None,
    ) -> None:
        """Wake a waiting run without holding a worker lease or transaction."""
        self._required(workspace_id, run_id)
        timestamp = _utc(now or datetime.now(UTC))
        with self._engine.begin() as connection:
            _scope(connection, workspace_id)
            result = connection.execute(
                text(
                    """
                    UPDATE runs
                    SET state = 'queued', lease_owner = NULL, lease_expires_at = NULL,
                        wait_reason = NULL, error_code = NULL, updated_at = :updated_at
                    WHERE id = :run_id AND workspace_id = :workspace_id
                      AND state = 'waiting'
                    """
                ),
                {
                    "updated_at": timestamp,
                    "run_id": run_id,
                    "workspace_id": workspace_id,
                },
            )
            if result.rowcount != 1:
                raise RuntimeRepositoryError("run is not waiting or is not visible")

    def checkpoint(
        self,
        lease: RunLease,
        checkpoint: Mapping[str, object],
        *,
        now: datetime | None = None,
    ) -> RunLease:
        payload = _json_payload(checkpoint)
        timestamp = _utc(now or datetime.now(UTC))
        with self._engine.begin() as connection:
            _scope(connection, lease.workspace_id)
            row = connection.execute(
                text(
                    """
                    UPDATE runs
                    SET checkpoint_revision = checkpoint_revision + 1,
                        checkpoint_json = CAST(:checkpoint_json AS jsonb),
                        updated_at = :updated_at
                    WHERE id = :run_id AND workspace_id = :workspace_id
                      AND lease_owner = :worker_id AND fence = :fence
                      AND state IN ('leased', 'running')
                    RETURNING checkpoint_revision
                    """
                ),
                {
                    "checkpoint_json": payload,
                    "updated_at": timestamp,
                    "run_id": lease.run_id,
                    "workspace_id": lease.workspace_id,
                    "worker_id": lease.worker_id,
                    "fence": lease.fence,
                },
            ).mappings().first()
            if row is None:
                raise FenceError("stale or non-owner worker")
            revision = int(row["checkpoint_revision"])
        return RunLease(
            **{
                **lease.__dict__,
                "checkpoint_revision": revision,
                "checkpoint": dict(checkpoint),
            }
        )

    def complete(
        self, lease: RunLease, result_ref: str, *, now: datetime | None = None
    ) -> RunLease:
        if not result_ref:
            raise RuntimeRepositoryError("result_ref is required")
        return self._transition(lease, RunState.COMPLETED, result_ref=result_ref, now=now)

    def fail(
        self,
        lease: RunLease,
        error_code: str,
        *,
        retryable: bool,
        now: datetime | None = None,
    ) -> RunLease:
        if not error_code:
            raise RuntimeRepositoryError("error_code is required")
        return self._transition(
            lease,
            RunState.QUEUED if retryable else RunState.FAILED,
            error_code=error_code,
            now=now,
        )

    def record_tool_execution(
        self,
        *,
        workspace_id: str,
        run_id: str,
        attempt_id: str,
        operation_key: str,
        tool_id: str,
        tool_version: str,
        effect_class: str,
        input_payload: Mapping[str, object],
        state: str = "started",
        output: Mapping[str, object] | None = None,
    ) -> ToolExecutionRecord:
        self._required(workspace_id, run_id, attempt_id, operation_key, tool_id, tool_version)
        if effect_class not in {"read", "compute", "write", "external"}:
            raise RuntimeRepositoryError("invalid effect class")
        if state not in {"started", "succeeded", "failed", "unknown"}:
            raise RuntimeRepositoryError("invalid tool execution state")
        with self._engine.begin() as connection:
            _scope(connection, workspace_id)
            payload = _json_payload(input_payload)
            output_json = None if output is None else _json_payload(output)
            connection.execute(
                text(
                    """
                    INSERT INTO tool_executions
                      (id, workspace_id, run_id, attempt_id, operation_key, tool_id,
                       tool_version, effect_class, state, input_json, output_json)
                    VALUES
                      (:id, :workspace_id, :run_id, :attempt_id, :operation_key,
                       :tool_id, :tool_version, :effect_class, :state,
                       CAST(:input_json AS jsonb), CAST(:output_json AS jsonb))
                    ON CONFLICT (workspace_id, operation_key) DO NOTHING
                    """
                ),
                {
                    "id": f"tool-{uuid.uuid4().hex}",
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "attempt_id": attempt_id,
                    "operation_key": operation_key,
                    "tool_id": tool_id,
                    "tool_version": tool_version,
                    "effect_class": effect_class,
                    "state": state,
                    "input_json": payload,
                    "output_json": output_json,
                },
            )
            row = connection.execute(
                text(
                    "SELECT id, run_id, attempt_id, tool_id, tool_version, effect_class, "
                    "operation_key, state, input_json, output_json FROM tool_executions "
                    "WHERE workspace_id = :workspace_id AND operation_key = :operation_key"
                ),
                {"workspace_id": workspace_id, "operation_key": operation_key},
            ).mappings().one()
            if (
                row["run_id"] != run_id
                or row["attempt_id"] != attempt_id
                or row["tool_id"] != tool_id
                or row["tool_version"] != tool_version
                or row["effect_class"] != effect_class
                or row["input_json"] != dict(input_payload)
            ):
                raise RuntimeRepositoryError("tool operation key was reused with different input")
            return ToolExecutionRecord(
                str(row["id"]),
                str(row["operation_key"]),
                str(row["state"]),
                _json_object(row["output_json"]),
            )

    def reserve_effect(
        self,
        *,
        workspace_id: str,
        run_id: str,
        attempt_id: str,
        operation_key: str,
        effect_id: str | None = None,
    ) -> EffectRecord:
        self._required(workspace_id, run_id, attempt_id, operation_key)
        with self._engine.begin() as connection:
            _scope(connection, workspace_id)
            connection.execute(
                text(
                    """
                    INSERT INTO effects
                      (id, workspace_id, run_id, attempt_id, operation_key, state)
                    VALUES
                      (:id, :workspace_id, :run_id, :attempt_id, :operation_key, 'reserved')
                    ON CONFLICT (workspace_id, operation_key) DO NOTHING
                    """
                ),
                {
                    "id": effect_id or f"effect-{uuid.uuid4().hex}",
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "attempt_id": attempt_id,
                    "operation_key": operation_key,
                },
            )
            row = connection.execute(
                text(
                    "SELECT id, run_id, attempt_id, operation_key, state, result_ref FROM effects "
                    "WHERE workspace_id = :workspace_id AND operation_key = :operation_key"
                ),
                {"workspace_id": workspace_id, "operation_key": operation_key},
            ).mappings().one()
            if row["run_id"] != run_id or row["attempt_id"] != attempt_id:
                raise RuntimeRepositoryError("effect operation key was reused by another attempt")
            return EffectRecord(
                str(row["id"]), str(row["operation_key"]), str(row["state"]), row["result_ref"]
            )

    def _transition(
        self,
        lease: RunLease,
        state: RunState,
        *,
        result_ref: str | None = None,
        error_code: str | None = None,
        wait_reason: str | None = None,
        now: datetime | None = None,
    ) -> RunLease:
        if state not in {
            RunState.RUNNING,
            RunState.WAITING,
            RunState.COMPLETED,
            RunState.FAILED,
            RunState.QUEUED,
            RunState.CANCELLED,
        }:
            raise RuntimeRepositoryError("invalid run transition")
        timestamp = _utc(now or datetime.now(UTC))
        release_lease = state in {
            RunState.WAITING,
            RunState.COMPLETED,
            RunState.FAILED,
            RunState.QUEUED,
            RunState.CANCELLED,
        }
        lease_owner = None if release_lease else lease.worker_id
        stored_wait_reason = wait_reason if state is RunState.WAITING else None
        with self._engine.begin() as connection:
            _scope(connection, lease.workspace_id)
            result = connection.execute(
                text(
                    """
                    UPDATE runs
                    SET state = :state, lease_owner = :lease_owner,
                        lease_expires_at = CASE
                          WHEN :release_lease THEN NULL
                          ELSE lease_expires_at
                        END,
                        wait_reason = :wait_reason,
                        result_ref = COALESCE(:result_ref, result_ref),
                        error_code = :error_code, updated_at = :updated_at
                    WHERE id = :run_id AND workspace_id = :workspace_id
                      AND lease_owner = :worker_id AND fence = :fence
                    """
                ),
                {
                    "state": state.value,
                    "lease_owner": lease_owner,
                    "release_lease": release_lease,
                    "wait_reason": stored_wait_reason,
                    "result_ref": result_ref,
                    "error_code": error_code,
                    "updated_at": timestamp,
                    "run_id": lease.run_id,
                    "workspace_id": lease.workspace_id,
                    "worker_id": lease.worker_id,
                    "fence": lease.fence,
                },
            )
            if result.rowcount != 1:
                raise FenceError("stale or non-owner worker")
        return replace(
            lease,
            state=state,
            lease_expires_at=None if release_lease else lease.lease_expires_at,
        )

    @staticmethod
    def _required(*values: str) -> None:
        if any(not value for value in values):
            raise RuntimeRepositoryError("required runtime identity is missing")


def _scope(connection: Connection, workspace_id: str) -> None:
    connection.execute(
        text("SELECT set_config('app.workspace_id', :workspace_id, true)"),
        {"workspace_id": workspace_id},
    )


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _json_payload(value: Mapping[str, object]) -> str:
    try:
        return json.dumps(dict(value), separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeRepositoryError("runtime payload must be JSON-safe") from exc


def _json_object(value: Any) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, str):
        decoded = json.loads(value)
    elif isinstance(value, Mapping):
        decoded = dict(value)
    else:
        decoded = value
    if not isinstance(decoded, dict):
        raise RuntimeRepositoryError("runtime JSON value must be an object")
    return dict(decoded)
