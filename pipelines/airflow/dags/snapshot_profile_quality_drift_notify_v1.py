from __future__ import annotations

from dataclasses import dataclass


class DagContractError(ValueError):
    """A schedule request is outside the trusted R1 template."""


@dataclass(frozen=True)
class DagTask:
    task_id: str
    operator: str
    retry_safe_key: str


@dataclass(frozen=True)
class TrustedDag:
    dag_id: str
    version: str
    schedule: str
    catchup: bool
    max_active_runs: int
    tasks: tuple[DagTask, ...]
    xcom_max_bytes: int = 16 * 1024
    max_backfill_intervals: int = 31


TASKS = (
    DagTask("import_source", "CoreImportOperator", "pipeline_run_id:import_source"),
    DagTask("profile", "CoreProfileOperator", "pipeline_run_id:profile"),
    DagTask("quality", "CoreQualityOperator", "pipeline_run_id:quality"),
    DagTask("drift", "CoreDriftOperator", "pipeline_run_id:drift"),
    DagTask("notify", "CoreNotifyOperator", "pipeline_run_id:notify"),
)


def build_snapshot_dag(*, schedule: str) -> TrustedDag:
    if not schedule or len(schedule) > 128:
        raise DagContractError("schedule must be an explicit bounded cron expression")
    return TrustedDag(
        "snapshot_profile_quality_drift_notify",
        "v1",
        schedule,
        catchup=False,
        max_active_runs=1,
        tasks=TASKS,
    )
