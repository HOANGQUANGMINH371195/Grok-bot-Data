from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from vda_platform.jobs import (
    JobOutcome,
    PostgresControlWorker,
    PostgresRuntimeRepository,
    RetryableJobError,
)

pytest.importorskip("psycopg")

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_postgres_worker_recovery_before_and_after_commit() -> None:
    url = os.environ.get("VDA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("VDA_TEST_DATABASE_URL is required for PostgreSQL integration")
    engine = create_engine(url, pool_pre_ping=True)
    workspace_id = f"worker-it-{uuid4().hex}"

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
    success_task = f"task-{uuid4().hex}"
    success_run = f"run-{uuid4().hex}"
    repository.create_task(
        workspace_id=workspace_id,
        task_id=success_task,
        kind="profile",
        payload={},
        idempotency_key=success_task,
        now=NOW,
    )
    repository.create_run(
        workspace_id=workspace_id,
        run_id=success_run,
        task_id=success_task,
        now=NOW,
    )

    def worker_lost(_: object) -> None:
        raise RuntimeError("worker lost after commit")

    worker = PostgresControlWorker(
        repository,
        workspace_id=workspace_id,
        worker_id="worker-a",
        handler=lambda _: JobOutcome("artifact:success"),
        after_commit=worker_lost,
    )
    with pytest.raises(RuntimeError, match="worker lost"):
        worker.run_once(now=NOW)
    assert repository.claim_run(
        workspace_id=workspace_id,
        worker_id="worker-b",
        now=NOW + timedelta(seconds=1),
    ) is None

    retry_task = f"task-{uuid4().hex}"
    retry_run = f"run-{uuid4().hex}"
    repository.create_task(
        workspace_id=workspace_id,
        task_id=retry_task,
        kind="profile",
        payload={},
        idempotency_key=retry_task,
        now=NOW,
    )
    repository.create_run(
        workspace_id=workspace_id,
        run_id=retry_run,
        task_id=retry_task,
        now=NOW,
    )

    def retry_handler(_: object) -> JobOutcome:
        raise RetryableJobError("provider timeout")

    retry_worker = PostgresControlWorker(
        repository,
        workspace_id=workspace_id,
        worker_id="worker-c",
        handler=retry_handler,
    )
    retry = retry_worker.run_once(now=NOW)
    assert retry is not None
    assert retry.state.value == "queued"

    recovered_worker = PostgresControlWorker(
        repository,
        workspace_id=workspace_id,
        worker_id="worker-d",
        handler=lambda _: JobOutcome("artifact:retry-success"),
    )
    recovered = recovered_worker.run_once(now=NOW + timedelta(seconds=1))
    assert recovered is not None
    assert recovered.state.value == "completed"
    assert recovered.fence == retry.fence + 1
    engine.dispose()
