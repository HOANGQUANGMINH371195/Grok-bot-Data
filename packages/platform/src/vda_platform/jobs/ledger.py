from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from vda_platform.runtime.runs import FenceError


class JobError(ValueError):
    """A job command violates idempotency, state, or admission rules."""


class JobState(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Job:
    job_id: str
    workspace_id: str
    kind: str
    payload: dict[str, object]
    idempotency_key: str
    state: JobState = JobState.QUEUED
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    fence: int = 0
    attempts: int = 0
    checkpoint_revision: int = 0
    checkpoint: dict[str, object] | None = None
    wait_reason: str | None = None
    error_code: str | None = None
    result_ref: str | None = None


class JobLedger:
    """In-memory job ledger with the same lease/fence semantics as the DB port."""

    def __init__(self, *, default_lease_seconds: int = 60) -> None:
        if default_lease_seconds <= 0:
            raise ValueError("default lease must be positive")
        self._default_lease = timedelta(seconds=default_lease_seconds)
        self._jobs: dict[str, Job] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._created: dict[str, datetime] = {}

    def enqueue(
        self,
        *,
        job_id: str,
        workspace_id: str,
        kind: str,
        payload: dict[str, object],
        idempotency_key: str,
        now: datetime | None = None,
    ) -> Job:
        if not job_id or not workspace_id or not kind or not idempotency_key:
            raise JobError("job identity and idempotency key are required")
        if not _json_safe(payload):
            raise JobError("job payload must be JSON-safe")
        timestamp = _utc(now or datetime.now(UTC))
        key = (workspace_id, idempotency_key)
        existing_id = self._idempotency.get(key)
        if existing_id is not None:
            existing = self._jobs[existing_id]
            if existing.payload != payload or existing.kind != kind:
                raise JobError("idempotency key was reused with different job input")
            return existing
        if job_id in self._jobs:
            raise JobError("job_id already exists")
        job = Job(job_id, workspace_id, kind, dict(payload), idempotency_key)
        self._jobs[job_id] = job
        self._idempotency[key] = job_id
        self._created[job_id] = timestamp
        return job

    def get(self, job_id: str) -> Job:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise JobError("job not found") from exc

    def claim(
        self,
        worker_id: str,
        *,
        now: datetime | None = None,
        limit: int = 1,
        lease_seconds: int | None = None,
    ) -> tuple[Job, ...]:
        if not worker_id or limit < 1:
            raise JobError("worker_id and positive claim limit are required")
        timestamp = _utc(now or datetime.now(UTC))
        lease = (
            timedelta(seconds=lease_seconds)
            if lease_seconds is not None
            else self._default_lease
        )
        if lease <= timedelta(0):
            raise JobError("lease must be positive")
        candidates = sorted(
            (
                job
                for job in self._jobs.values()
                if job.state is JobState.QUEUED
                or (
                    job.state in {JobState.LEASED, JobState.RUNNING}
                    and job.lease_expires_at is not None
                    and job.lease_expires_at <= timestamp
                )
            ),
            key=lambda job: self._created[job.job_id],
        )[:limit]
        claimed: list[Job] = []
        for job in candidates:
            updated = replace(
                job,
                state=JobState.LEASED,
                lease_owner=worker_id,
                lease_expires_at=timestamp + lease,
                fence=job.fence + 1,
                attempts=job.attempts + 1,
                wait_reason=None,
            )
            self._jobs[job.job_id] = updated
            claimed.append(updated)
        return tuple(claimed)

    def start(self, job_id: str, worker_id: str, fence: int) -> Job:
        job = self._guard(job_id, worker_id, fence)
        if job.state is not JobState.LEASED:
            raise JobError("only a leased job can start")
        updated = replace(job, state=JobState.RUNNING)
        self._jobs[job_id] = updated
        return updated

    def heartbeat(
        self, job_id: str, worker_id: str, fence: int, *, now: datetime | None = None
    ) -> Job:
        job = self._guard(job_id, worker_id, fence)
        if job.state not in {JobState.LEASED, JobState.RUNNING}:
            raise JobError("only an active job can heartbeat")
        timestamp = _utc(now or datetime.now(UTC))
        updated = replace(job, lease_expires_at=timestamp + self._default_lease)
        self._jobs[job_id] = updated
        return updated

    def checkpoint(
        self, job_id: str, worker_id: str, fence: int, data: dict[str, object]
    ) -> Job:
        job = self._guard(job_id, worker_id, fence)
        if job.state not in {JobState.LEASED, JobState.RUNNING}:
            raise JobError("only an active job can checkpoint")
        if not _json_safe(data):
            raise JobError("checkpoint must be JSON-safe")
        updated = replace(
            job,
            checkpoint_revision=job.checkpoint_revision + 1,
            checkpoint=dict(data),
        )
        self._jobs[job_id] = updated
        return updated

    def wait(self, job_id: str, worker_id: str, fence: int, reason: str) -> Job:
        if reason not in {"input", "approval", "children", "tool", "peer"}:
            raise JobError("invalid wait reason")
        job = self._guard(job_id, worker_id, fence)
        if job.state not in {JobState.LEASED, JobState.RUNNING}:
            raise JobError("only an active job can wait")
        updated = replace(
            job,
            state=JobState.WAITING,
            lease_owner=None,
            lease_expires_at=None,
            wait_reason=reason,
        )
        self._jobs[job_id] = updated
        return updated

    def resume(self, job_id: str, *, now: datetime | None = None) -> Job:
        job = self.get(job_id)
        if job.state is not JobState.WAITING:
            raise JobError("only a waiting job can resume")
        updated = replace(
            job,
            state=JobState.QUEUED,
            lease_owner=None,
            lease_expires_at=None,
            wait_reason=None,
            error_code=None,
        )
        self._jobs[job_id] = updated
        del now  # DB time/backoff belongs to the persistent adapter.
        return updated

    def complete(self, job_id: str, worker_id: str, fence: int, result_ref: str) -> Job:
        if not result_ref:
            raise JobError("result_ref is required")
        job = self._guard(job_id, worker_id, fence)
        if job.state not in {JobState.LEASED, JobState.RUNNING}:
            raise JobError("only an active job can complete")
        updated = replace(
            job,
            state=JobState.COMPLETED,
            lease_owner=None,
            lease_expires_at=None,
            result_ref=result_ref,
        )
        self._jobs[job_id] = updated
        return updated

    def fail(
        self,
        job_id: str,
        worker_id: str,
        fence: int,
        error_code: str,
        *,
        retryable: bool,
        now: datetime | None = None,
    ) -> Job:
        if not error_code:
            raise JobError("error_code is required")
        job = self._guard(job_id, worker_id, fence)
        if job.state not in {JobState.LEASED, JobState.RUNNING}:
            raise JobError("only an active job can fail")
        updated = replace(
            job,
            state=JobState.QUEUED if retryable else JobState.FAILED,
            lease_owner=None,
            lease_expires_at=None,
            error_code=error_code,
        )
        self._jobs[job_id] = updated
        del now  # Backoff scheduling is owned by the persistent queue adapter.
        return updated

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job.state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}:
            return job
        updated = replace(job, state=JobState.CANCELLED, lease_owner=None, lease_expires_at=None)
        self._jobs[job_id] = updated
        return updated

    def _guard(self, job_id: str, worker_id: str, fence: int) -> Job:
        job = self.get(job_id)
        if job.lease_owner != worker_id or job.fence != fence:
            raise FenceError("stale or non-owner worker")
        return job


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _json_safe(value: object) -> bool:
    try:
        json.dumps(value, separators=(",", ":"))
    except (TypeError, ValueError):
        return False
    return True
