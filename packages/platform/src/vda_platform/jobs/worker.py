from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from .ledger import Job, JobLedger


class RetryableJobError(RuntimeError):
    """The current attempt failed but the job may be claimed again."""


class WaitingJob(RuntimeError):
    """The job needs an external wake-up and must release its lease."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class JobOutcome:
    result_ref: str


JobHandler = Callable[[Job], JobOutcome]


class ControlWorker:
    """Small worker port that makes lease ownership and commit ordering explicit."""

    def __init__(self, ledger: JobLedger, worker_id: str, handler: JobHandler) -> None:
        if not worker_id:
            raise ValueError("worker_id is required")
        self._ledger = ledger
        self._worker_id = worker_id
        self._handler = handler

    def run_once(self, *, now: datetime | None = None) -> tuple[Job, ...]:
        claimed = self._ledger.claim(self._worker_id, now=now)
        outcomes: list[Job] = []
        for leased in claimed:
            running = self._ledger.start(leased.job_id, self._worker_id, leased.fence)
            try:
                outcome = self._handler(running)
            except WaitingJob as exc:
                outcomes.append(
                    self._ledger.wait(running.job_id, self._worker_id, running.fence, exc.reason)
                )
            except RetryableJobError as exc:
                outcomes.append(
                    self._ledger.fail(
                        running.job_id,
                        self._worker_id,
                        running.fence,
                        _error_code(exc),
                        retryable=True,
                        now=now,
                    )
                )
            except Exception as exc:
                outcomes.append(
                    self._ledger.fail(
                        running.job_id,
                        self._worker_id,
                        running.fence,
                        _error_code(exc),
                        retryable=False,
                        now=now,
                    )
                )
            else:
                outcomes.append(
                    self._ledger.complete(
                        running.job_id, self._worker_id, running.fence, outcome.result_ref
                    )
                )
        return tuple(outcomes)


def _error_code(error: Exception) -> str:
    name = error.__class__.__name__.lower()
    return name if name.isidentifier() else "job_failed"
