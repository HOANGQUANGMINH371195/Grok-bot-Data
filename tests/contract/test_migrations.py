import importlib.util
from pathlib import Path


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
    assert core.revision == "0001_core"
    assert core.down_revision is None
    assert messaging.revision == "0002_messaging"
    assert messaging.down_revision == core.revision
    assert identity.revision == "0003_identity"
    assert identity.down_revision == messaging.revision
    assert (root / "database/migrations/versions/0001_core.sql").exists()
    assert (root / "database/migrations/versions/0002_messaging.sql").exists()
    identity_sql = (root / "database/migrations/versions/0003_identity.sql").read_text()
    assert "workspace_memberships_one_active" in identity_sql
    assert "FORCE ROW LEVEL SECURITY" in identity_sql
    assert "CHECK (NOT can_write OR can_read)" in identity_sql
