"""Use case: Adds opt-in dataset row and column policies without changing existing access.

What it does: Retains append-only policy revisions and refuses destructive downgrade.
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dataset_access_policies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("grants", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]
        ),
        sa.UniqueConstraint("workspace_id", "dataset_id", "version"),
        sa.CheckConstraint("version > 0", name="dataset_access_version"),
    )


def downgrade() -> None:
    count = (
        op.get_bind().execute(sa.text("SELECT COUNT(*) FROM dataset_access_policies")).scalar_one()
    )
    if count:
        raise RuntimeError(
            "Preserve all dataset access policies before downgrading; "
            "no policy is deleted automatically."
        )
    op.drop_table("dataset_access_policies")
