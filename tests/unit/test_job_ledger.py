from datetime import UTC, datetime, timedelta

import pytest
from vda_platform.jobs import JobError, JobLedger, JobState
from vda_platform.runtime import FenceError

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_enqueue_is_idempotent_and_rejects_different_payload() -> None:
    ledger = JobLedger()
    first = ledger.enqueue(
        job_id="job-1",
        workspace_id="w",
        kind="profile",
        payload={"dataset": "d1"},
        idempotency_key="idem-1",
        now=NOW,
    )
    assert ledger.enqueue(
        job_id="different-id",
        workspace_id="w",
        kind="profile",
        payload={"dataset": "d1"},
        idempotency_key="idem-1",
        now=NOW,
    ) == first
    with pytest.raises(JobError, match="different job input"):
        ledger.enqueue(
            job_id="job-2",
            workspace_id="w",
            kind="profile",
            payload={"dataset": "d2"},
            idempotency_key="idem-1",
            now=NOW,
        )


def test_lease_expiry_increments_fence_and_blocks_stale_worker_commit() -> None:
    ledger = JobLedger(default_lease_seconds=10)
    ledger.enqueue(
        job_id="job-1", workspace_id="w", kind="compute", payload={}, idempotency_key="i", now=NOW
    )
    first = ledger.claim("worker-a", now=NOW)[0]
    assert first.state is JobState.LEASED
    ledger.start(first.job_id, "worker-a", first.fence)
    recovered = ledger.claim("worker-b", now=NOW + timedelta(seconds=11))[0]
    assert recovered.fence == first.fence + 1
    with pytest.raises(FenceError, match="stale"):
        ledger.complete(first.job_id, "worker-a", first.fence, "artifact:old")
    done = ledger.complete(recovered.job_id, "worker-b", recovered.fence, "artifact:new")
    assert done.state is JobState.COMPLETED


def test_checkpoint_wait_resume_and_retryable_failure_are_recoverable() -> None:
    ledger = JobLedger()
    ledger.enqueue(
        job_id="job-1", workspace_id="w", kind="export", payload={}, idempotency_key="i", now=NOW
    )
    leased = ledger.claim("worker-a", now=NOW)[0]
    checkpointed = ledger.checkpoint(leased.job_id, "worker-a", leased.fence, {"page": 2})
    waiting = ledger.wait(checkpointed.job_id, "worker-a", leased.fence, "approval")
    assert waiting.checkpoint_revision == 1
    resumed = ledger.resume(waiting.job_id, now=NOW + timedelta(seconds=1))
    retried = ledger.claim("worker-b", now=NOW + timedelta(seconds=1))[0]
    failed = ledger.fail(
        retried.job_id,
        "worker-b",
        retried.fence,
        "provider_timeout",
        retryable=True,
        now=NOW,
    )
    assert resumed.state is JobState.QUEUED
    assert failed.state is JobState.QUEUED
    assert failed.error_code == "provider_timeout"


def test_invalid_payload_or_terminal_transition_is_fail_closed() -> None:
    ledger = JobLedger()
    with pytest.raises(JobError, match="JSON-safe"):
        ledger.enqueue(
            job_id="job-1",
            workspace_id="w",
            kind="x",
            payload={"bad": object()},
            idempotency_key="i",
        )
    ledger.enqueue(job_id="job-2", workspace_id="w", kind="x", payload={}, idempotency_key="i-2")
    claimed = ledger.claim("worker")[0]
    done = ledger.complete(claimed.job_id, "worker", claimed.fence, "artifact:1")
    with pytest.raises(FenceError, match="stale"):
        ledger.complete(done.job_id, "worker", done.fence, "artifact:2")
