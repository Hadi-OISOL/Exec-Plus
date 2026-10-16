"""Use case: Retains private exact multi-company worksheets.

What it does: Adds immutable source-backed records without changing prior data;
downgrade refuses while any worksheet remains.
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consolidation_runs",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("owner_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("request", sa.JSON, nullable=False),
        sa.Column("evidence", sa.JSON, nullable=False),
        sa.Column("result", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "consolidation_private_history",
        "consolidation_runs",
        ["organization_id", "owner_id", "created_at"],
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM consolidation_runs LIMIT 1")).first():
        raise RuntimeError("Keep saved company worksheets; downgrade would erase private evidence.")
    op.drop_index("consolidation_private_history", table_name="consolidation_runs")
    op.drop_table("consolidation_runs")
