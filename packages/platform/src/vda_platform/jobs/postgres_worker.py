from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from .repository import PostgresRuntimeRepository, RunLease
from .worker import JobOutcome, RetryableJobError, WaitingJob

RuntimeRunHandler = Callable[[RunLease], JobOutcome]
AfterCommitHook = Callable[[RunLease], None]


class PostgresControlWorker:
    """One bounded control-worker iteration over the durable runtime repository."""

    def __init__(
        self,
        repository: PostgresRuntimeRepository,
        *,
        workspace_id: str,
        worker_id: str,
        handler: RuntimeRunHandler,
        lease_seconds: int | None = None,
        after_commit: AfterCommitHook | None = None,
    ) -> None:
        if not workspace_id or not worker_id:
            raise ValueError("workspace_id and worker_id are required")
        self._repository = repository
        self._workspace_id = workspace_id
        self._worker_id = worker_id
        self._handler = handler
        self._lease_seconds = lease_seconds
        self._after_commit = after_commit

    def run_once(self, *, now: datetime | None = None) -> RunLease | None:
        lease = self._repository.claim_run(
            workspace_id=self._workspace_id,
            worker_id=self._worker_id,
            now=now,
            lease_seconds=self._lease_seconds,
        )
        if lease is None:
            return None
        running = self._repository.start_run(lease, now=now)
        try:
            outcome = self._handler(running)
        except WaitingJob as exc:
            return self._repository.wait(running, exc.reason, now=now)
        except RetryableJobError as exc:
            return self._repository.fail(
                running,
                _error_code(exc),
                retryable=True,
                now=now,
            )
        except Exception as exc:
            return self._repository.fail(
                running,
                _error_code(exc),
                retryable=False,
                now=now,
            )
        completed = self._repository.complete(running, outcome.result_ref, now=now)
        if self._after_commit is not None:
            self._after_commit(completed)
        return completed


def _error_code(error: Exception) -> str:
    name = error.__class__.__name__.lower()
    return name if name.isidentifier() else "runtime_run_failed"
