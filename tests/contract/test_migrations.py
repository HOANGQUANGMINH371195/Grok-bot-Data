import importlib.util
from pathlib import Path

from vda_platform.storage import Base


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alembic_revision_chain_is_linear_and_sql_backed() -> None:
    root = Path(__file__).parents[2]
    core = _load("migration_0001", root / "database/migrations/versions/0001_core.py")
    messaging = _load("migration_0002", root / "database/migrations/versions/0002_messaging.py")
    identity = _load("migration_0003", root / "database/migrations/versions/0003_identity.py")
    runtime = _load("migration_0004", root / "database/migrations/versions/0004_runtime.py")
    tenant_fks = _load(
        "migration_0005", root / "database/migrations/versions/0005_runtime_tenant_fks.py"
    )
    run_events = _load(
        "migration_0006", root / "database/migrations/versions/0006_run_events.py"
    )
    assert core.revision == "0001_core"
    assert core.down_revision is None
    assert messaging.revision == "0002_messaging"
    assert messaging.down_revision == core.revision
    assert identity.revision == "0003_identity"
    assert identity.down_revision == messaging.revision
    assert runtime.revision == "0004_runtime"
    assert runtime.down_revision == identity.revision
    assert tenant_fks.revision == "0005_runtime_tenant_fks"
    assert tenant_fks.down_revision == runtime.revision
    assert run_events.revision == "0006_run_events"
    assert run_events.down_revision == tenant_fks.revision
    assert (root / "database/migrations/versions/0001_core.sql").exists()
    assert (root / "database/migrations/versions/0002_messaging.sql").exists()
    identity_sql = (root / "database/migrations/versions/0003_identity.sql").read_text()
    assert "workspace_memberships_one_active" in identity_sql
    assert "FORCE ROW LEVEL SECURITY" in identity_sql
    assert "CHECK (NOT can_write OR can_read)" in identity_sql
    runtime_sql = (root / "database/migrations/versions/0004_runtime.sql").read_text()
    assert "FOR UPDATE SKIP LOCKED" in runtime_sql
    assert "runs_claim_idx" in runtime_sql
    assert "UNIQUE (workspace_id, operation_key)" in runtime_sql
    assert "FORCE ROW LEVEL SECURITY" in runtime_sql
    assert {
        "tasks",
        "runs",
        "attempts",
        "tool_executions",
        "effects",
        "run_events",
    } <= set(Base.metadata.tables)
    tenant_fk_sql = (root / "database/migrations/versions/0005_runtime_tenant_fks.sql").read_text()
    for constraint in (
        "runs_workspace_task_fk",
        "attempts_workspace_run_fk",
        "tool_executions_workspace_attempt_fk",
        "effects_workspace_attempt_fk",
    ):
        assert constraint in tenant_fk_sql
    run_events_sql = (root / "database/migrations/versions/0006_run_events.sql").read_text()
    assert "run_events_workspace_run_fk" in run_events_sql
    assert "FORCE ROW LEVEL SECURITY" in run_events_sql
