from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from vda_platform.jobs import PostgresRuntimeRepository, RuntimeRepositoryError
from vda_platform.runtime import FenceError, RunState

pytest.importorskip("psycopg")

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_postgres_runtime_claim_fence_checkpoint_and_effect_idempotency() -> None:
    url = os.environ.get("VDA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("VDA_TEST_DATABASE_URL is required for PostgreSQL integration")
    engine = create_engine(url, pool_pre_ping=True)
    workspace_id = f"runtime-it-{uuid4().hex}"
    task_id = f"task-{uuid4().hex}"
    run_id = f"run-{uuid4().hex}"

    with engine.begin() as connection:
        connection.execute(
            text("SELECT set_config('app.workspace_id', :workspace_id, true)"),
            {"workspace_id": workspace_id},
        )
        connection.execute(
            text("INSERT INTO workspaces (id) VALUES (:workspace_id)"),
            {"workspace_id": workspace_id},
        )

    repository = PostgresRuntimeRepository(engine, default_lease_seconds=10)
    assert repository.create_task(
        workspace_id=workspace_id,
        task_id=task_id,
        kind="profile",
        payload={"dataset": "d1"},
        idempotency_key="profile-1",
        now=NOW,
    ) == task_id
    assert repository.create_task(
        workspace_id=workspace_id,
        task_id="different-task-id",
        kind="profile",
        payload={"dataset": "d1"},
        idempotency_key="profile-1",
        now=NOW,
    ) == task_id
    repository.create_run(
        workspace_id=workspace_id,
        run_id=run_id,
        task_id=task_id,
        now=NOW,
    )

    first = repository.claim_run(workspace_id=workspace_id, worker_id="worker-a", now=NOW)
    assert first is not None
    assert first.state is RunState.LEASED
    running = repository.start_run(first, now=NOW)
    checkpointed = repository.checkpoint(running, {"page": 2}, now=NOW)
    assert checkpointed.checkpoint_revision == 1
    assert checkpointed.checkpoint == {"page": 2}
    waiting = repository.wait(checkpointed, "approval", now=NOW)
    assert waiting.state is RunState.WAITING
    repository.resume_run(workspace_id=workspace_id, run_id=run_id, now=NOW)
    execution = repository.record_tool_execution(
        workspace_id=workspace_id,
        run_id=run_id,
        attempt_id=first.attempt_id,
        operation_key="profile:page:2",
        tool_id="profile.start",
        tool_version="v1",
        effect_class="compute",
        input_payload={"page": 2},
        state="succeeded",
        output={"rows": 3},
    )
    duplicate = repository.record_tool_execution(
        workspace_id=workspace_id,
        run_id=run_id,
        attempt_id=first.attempt_id,
        operation_key="profile:page:2",
        tool_id="profile.start",
        tool_version="v1",
        effect_class="compute",
        input_payload={"page": 2},
        state="succeeded",
        output={"rows": 3},
    )
    assert duplicate.execution_id == execution.execution_id
    assert duplicate.output == {"rows": 3}
    with pytest.raises(RuntimeRepositoryError, match="different input"):
        repository.record_tool_execution(
            workspace_id=workspace_id,
            run_id=run_id,
            attempt_id=first.attempt_id,
            operation_key="profile:page:2",
            tool_id="profile.start",
            tool_version="v1",
            effect_class="compute",
            input_payload={"page": 99},
            state="succeeded",
            output={"rows": 99},
        )
    effect = repository.reserve_effect(
        workspace_id=workspace_id,
        run_id=run_id,
        attempt_id=first.attempt_id,
        operation_key="profile:page:2:effect",
    )
    assert repository.reserve_effect(
        workspace_id=workspace_id,
        run_id=run_id,
        attempt_id=first.attempt_id,
        operation_key="profile:page:2:effect",
    ).effect_id == effect.effect_id
    with pytest.raises(RuntimeRepositoryError, match="unknown-state"):
        repository.reconcile_effect(
            workspace_id=workspace_id,
            operation_key="profile:page:2:effect",
            result_ref="artifact:unverified",
        )
    unknown = repository.mark_effect_unknown(
        workspace_id=workspace_id,
        operation_key="profile:page:2:effect",
    )
    assert unknown.state == "unknown"
    reconciled = repository.reconcile_effect(
        workspace_id=workspace_id,
        operation_key="profile:page:2:effect",
        result_ref="artifact:verified",
    )
    assert reconciled.state == "reconciled"
    assert repository.mark_effect_unknown(
        workspace_id=workspace_id,
        operation_key="profile:page:2:effect",
    ).state == "reconciled"
    assert repository.reconcile_effect(
        workspace_id=workspace_id,
        operation_key="profile:page:2:effect",
        result_ref="artifact:verified",
    ) == reconciled
    with pytest.raises(RuntimeRepositoryError, match="unknown-state"):
        repository.reconcile_effect(
            workspace_id=workspace_id,
            operation_key="profile:page:2:effect",
            result_ref="artifact:different",
        )

    recovered = repository.claim_run(
        workspace_id=workspace_id,
        worker_id="worker-b",
        now=NOW + timedelta(seconds=11),
    )
    assert recovered is not None
    assert recovered.fence == first.fence + 1
    with pytest.raises(FenceError, match="stale"):
        repository.heartbeat(running, now=NOW + timedelta(seconds=11))
    repository.complete(recovered, "artifact:profile:1", now=NOW + timedelta(seconds=11))
    assert repository.claim_run(
        workspace_id=workspace_id,
        worker_id="worker-c",
        now=NOW + timedelta(seconds=12),
    ) is None
    engine.dispose()
