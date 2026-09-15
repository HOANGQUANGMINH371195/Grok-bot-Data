from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class RunState(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    HANDED_OFF = "handed_off"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InvalidRunTransition(ValueError):
    """A state transition violates the run contract."""


class FenceError(RuntimeError):
    """A stale worker attempted a durable write."""


@dataclass(frozen=True)
class Run:
    run_id: str
    workspace_id: str
    conversation_id: str
    bot_id: str
    state: RunState = RunState.QUEUED
    lease_owner: str | None = None
    fence: int = 0
    checkpoint_revision: int = 0
    checkpoint: dict[str, object] | None = None
    wait_reason: str | None = None
    error_code: str | None = None


_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.QUEUED: frozenset({RunState.LEASED, RunState.CANCELLED}),
    RunState.LEASED: frozenset({RunState.RUNNING, RunState.QUEUED, RunState.CANCELLED}),
    RunState.RUNNING: frozenset(
        {
            RunState.WAITING,
            RunState.COMPLETED,
            RunState.HANDED_OFF,
            RunState.FAILED,
            RunState.CANCELLED,
        }
    ),
    RunState.WAITING: frozenset({RunState.LEASED, RunState.CANCELLED, RunState.FAILED}),
    RunState.COMPLETED: frozenset(),
    RunState.HANDED_OFF: frozenset(),
    RunState.FAILED: frozenset(),
    RunState.CANCELLED: frozenset(),
}


class RunLedger:
    """In-memory aggregate mirroring the DB lease/fence protocol."""

    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}

    def create(self, run_id: str, workspace_id: str, conversation_id: str, bot_id: str) -> Run:
        if run_id in self._runs:
            raise ValueError("run already exists")
        run = Run(run_id, workspace_id, conversation_id, bot_id)
        self._runs[run_id] = run
        return run

    def get(self, run_id: str) -> Run:
        return self._runs[run_id]

    def lease(self, run_id: str, worker_id: str) -> Run:
        run = self.get(run_id)
        self._transition(run, RunState.LEASED)
        leased = replace(run, state=RunState.LEASED, lease_owner=worker_id, fence=run.fence + 1)
        self._runs[run_id] = leased
        return leased

    def transition(
        self,
        run_id: str,
        worker_id: str,
        fence: int,
        state: RunState,
        *,
        error_code: str | None = None,
    ) -> Run:
        run = self._guard(run_id, worker_id, fence)
        self._transition(run, state)
        updated = replace(run, state=state, error_code=error_code)
        if state != RunState.WAITING:
            updated = replace(updated, wait_reason=None)
        self._runs[run_id] = updated
        return updated

    def wait(self, run_id: str, worker_id: str, fence: int, reason: str) -> Run:
        if reason not in {"input", "approval", "children", "tool", "peer"}:
            raise ValueError("invalid wait reason")
        run = self._guard(run_id, worker_id, fence)
        self._transition(run, RunState.WAITING)
        updated = replace(run, state=RunState.WAITING, wait_reason=reason, lease_owner=None)
        self._runs[run_id] = updated
        return updated

    def checkpoint(self, run_id: str, worker_id: str, fence: int, data: dict[str, object]) -> Run:
        run = self._guard(run_id, worker_id, fence)
        if run.state not in {RunState.LEASED, RunState.RUNNING}:
            raise InvalidRunTransition("checkpoint requires leased or running run")
        updated = replace(
            run, checkpoint_revision=run.checkpoint_revision + 1, checkpoint=dict(data)
        )
        self._runs[run_id] = updated
        return updated

    def _guard(self, run_id: str, worker_id: str, fence: int) -> Run:
        run = self.get(run_id)
        if run.lease_owner != worker_id or run.fence != fence:
            raise FenceError("stale or non-owner worker")
        return run

    @staticmethod
    def _transition(run: Run, target: RunState) -> None:
        if target not in _TRANSITIONS[run.state]:
            raise InvalidRunTransition(f"{run.state} -> {target} is not allowed")
