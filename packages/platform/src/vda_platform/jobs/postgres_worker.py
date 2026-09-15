from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import Event, Thread

from .repository import PostgresRuntimeRepository, RunLease
from .worker import JobOutcome, RetryableJobError, WaitingJob

RuntimeRunHandler = Callable[[RunLease], JobOutcome]
AfterCommitHook = Callable[[RunLease], None]
WorkerErrorHook = Callable[[Exception], None]


class _LeaseHeartbeat:
    def __init__(
        self,
        repository: PostgresRuntimeRepository,
        lease: RunLease,
        interval_seconds: float,
    ) -> None:
        self._repository = repository
        self._lease = lease
        self._interval = interval_seconds
        self._stop = Event()
        self.error: Exception | None = None
        self._thread: Thread | None = None

    def __enter__(self) -> _LeaseHeartbeat:
        self._thread = Thread(target=self._run, name="runtime-lease-heartbeat", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self._interval * 2))

    def _run(self) -> None:
        lease = self._lease
        while not self._stop.wait(self._interval):
            try:
                lease = self._repository.heartbeat(lease)
            except Exception as exc:  # worker supervisor observes this as a failed lease
                self.error = exc
                self._stop.set()
                return


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
        heartbeat_interval_seconds: float | None = None,
        after_commit: AfterCommitHook | None = None,
    ) -> None:
        if not workspace_id or not worker_id:
            raise ValueError("workspace_id and worker_id are required")
        self._repository = repository
        self._workspace_id = workspace_id
        self._worker_id = worker_id
        self._handler = handler
        self._lease_seconds = lease_seconds
        effective_lease = lease_seconds if lease_seconds is not None else repository.lease_seconds
        self._heartbeat_interval = (
            heartbeat_interval_seconds
            if heartbeat_interval_seconds is not None
            else min(15.0, max(0.1, effective_lease / 3))
        )
        if self._heartbeat_interval <= 0:
            raise ValueError("heartbeat interval must be positive")
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
        handler_error: Exception | None = None
        outcome: JobOutcome | None = None
        with _LeaseHeartbeat(self._repository, running, self._heartbeat_interval) as heartbeat:
            try:
                outcome = self._handler(running)
            except Exception as exc:
                handler_error = exc
        if heartbeat.error is not None and handler_error is None:
            raise heartbeat.error
        if isinstance(handler_error, WaitingJob):
            return self._repository.wait(running, handler_error.reason, now=now)
        if isinstance(handler_error, RetryableJobError):
            return self._repository.fail(
                running,
                _error_code(handler_error),
                retryable=True,
                now=now,
            )
        if handler_error is not None:
            return self._repository.fail(
                running,
                _error_code(handler_error),
                retryable=False,
                now=now,
            )
        assert outcome is not None
        completed = self._repository.complete(running, outcome.result_ref, now=now)
        if self._after_commit is not None:
            self._after_commit(completed)
        return completed

    def run_forever(
        self,
        *,
        stop_event: Event,
        poll_interval_seconds: float = 1.0,
        on_error: WorkerErrorHook | None = None,
    ) -> int:
        """Poll until shutdown without retaining a DB transaction between runs."""
        if poll_interval_seconds <= 0:
            raise ValueError("poll interval must be positive")
        processed = 0
        while not stop_event.is_set():
            try:
                result = self.run_once()
            except Exception as exc:
                if on_error is None:
                    raise
                on_error(exc)
                result = None
            if result is not None:
                processed += 1
            if result is None:
                stop_event.wait(poll_interval_seconds)
        return processed


def _error_code(error: Exception) -> str:
    name = error.__class__.__name__.lower()
    return name if name.isidentifier() else "runtime_run_failed"
