from datetime import UTC, datetime

from vda_platform.jobs import (
    ControlWorker,
    JobLedger,
    JobOutcome,
    RetryableJobError,
    WaitingJob,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _enqueue(ledger: JobLedger, job_id: str) -> None:
    ledger.enqueue(
        job_id=job_id,
        workspace_id="w",
        kind="profile",
        payload={},
        idempotency_key=job_id,
        now=NOW,
    )


def test_worker_commits_success_and_releases_lease() -> None:
    ledger = JobLedger()
    _enqueue(ledger, "job-1")
    worker = ControlWorker(ledger, "worker-a", lambda job: JobOutcome(f"artifact:{job.job_id}"))

    [done] = worker.run_once(now=NOW)

    assert done.state.value == "completed"
    assert done.result_ref == "artifact:job-1"
    assert done.lease_owner is None


def test_worker_retry_wait_and_terminal_error_are_visible() -> None:
    ledgers = [JobLedger() for _ in range(3)]
    for index, ledger in enumerate(ledgers, start=1):
        _enqueue(ledger, f"job-{index}")

    def retry_handler(_: object) -> JobOutcome:
        raise RetryableJobError()

    def wait_handler(_: object) -> JobOutcome:
        raise WaitingJob("approval")

    def fail_handler(_: object) -> JobOutcome:
        raise ValueError("bad")

    retry = ControlWorker(ledgers[0], "worker", retry_handler)
    wait = ControlWorker(ledgers[1], "worker", wait_handler)
    fail = ControlWorker(ledgers[2], "worker", fail_handler)

    assert retry.run_once(now=NOW)[0].state.value == "queued"
    assert wait.run_once(now=NOW)[0].state.value == "waiting"
    assert fail.run_once(now=NOW)[0].state.value == "failed"


def test_handler_crash_before_commit_leaves_retryable_job() -> None:
    ledger = JobLedger()
    _enqueue(ledger, "job-1")

    def crash(_: object) -> JobOutcome:
        raise RetryableJobError("provider timeout")

    worker = ControlWorker(ledger, "worker-a", crash)
    [retry] = worker.run_once(now=NOW)

    assert retry.state.value == "queued"
    assert retry.error_code == "retryablejoberror"
    [reclaimed] = ledger.claim("worker-b", now=NOW)
    assert reclaimed.fence == retry.fence + 1


def test_completed_outcome_survives_worker_loss_after_commit() -> None:
    ledger = JobLedger()
    _enqueue(ledger, "job-1")
    worker = ControlWorker(ledger, "worker-a", lambda _: JobOutcome("artifact:committed"))

    [done] = worker.run_once(now=NOW)

    assert done.state.value == "completed"
    assert ledger.claim("worker-b", now=NOW) == ()
