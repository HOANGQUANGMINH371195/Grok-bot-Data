from pathlib import Path

from alembic import op

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute((Path(__file__).with_suffix(".sql")).read_text())


def downgrade() -> None:
    raise RuntimeError("R1 migrations are forward-only")
