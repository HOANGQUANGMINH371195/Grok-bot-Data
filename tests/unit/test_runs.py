import pytest
from vda_platform.runtime import FenceError, RunLedger, RunState


def test_lease_fence_rejects_stale_worker_after_requeue() -> None:
    ledger = RunLedger()
    ledger.create("run-1", "w", "c", "bot")
    first = ledger.lease("run-1", "worker-a")
    ledger.transition("run-1", "worker-a", first.fence, RunState.RUNNING)
    waiting = ledger.wait("run-1", "worker-a", first.fence, "tool")
    second = ledger.lease("run-1", "worker-b")
    assert second.fence > waiting.fence
    with pytest.raises(FenceError):
        ledger.checkpoint("run-1", "worker-a", first.fence, {"step": "stale"})


def test_checkpoint_revision_and_terminal_transition() -> None:
    ledger = RunLedger()
    ledger.create("run-1", "w", "c", "bot")
    leased = ledger.lease("run-1", "worker-a")
    running = ledger.transition("run-1", "worker-a", leased.fence, RunState.RUNNING)
    checkpoint = ledger.checkpoint("run-1", "worker-a", running.fence, {"cursor": 1})
    assert checkpoint.checkpoint_revision == 1
    done = ledger.transition("run-1", "worker-a", running.fence, RunState.COMPLETED)
    assert done.state is RunState.COMPLETED
