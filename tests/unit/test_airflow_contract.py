import pytest
from snapshot_profile_quality_drift_notify_v1 import DagContractError, build_snapshot_dag


def test_trusted_dag_has_fixed_tasks_and_safe_runtime_limits() -> None:
    dag = build_snapshot_dag(schedule="0 2 * * *")
    assert dag.dag_id == "snapshot_profile_quality_drift_notify"
    assert dag.version == "v1"
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert [task.task_id for task in dag.tasks] == [
        "import_source",
        "profile",
        "quality",
        "drift",
        "notify",
    ]
    assert all("pipeline_run_id:" in task.retry_safe_key for task in dag.tasks)


def test_dag_rejects_unbounded_schedule_input() -> None:
    with pytest.raises(DagContractError, match="schedule"):
        build_snapshot_dag(schedule="")
