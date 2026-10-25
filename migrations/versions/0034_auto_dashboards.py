"""Use case: Keeps each owner's automatic dataset dashboards as numbered versions.

What it does: Adds the additive auto_dashboards table; older images ignore it and downgrade
refuses while dashboards exist.
"""

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auto_dashboards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("shared", sa.Boolean(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "dataset_id", "upload_id"],
            ["uploads.workspace_id", "uploads.dataset_id", "uploads.id"],
            name="auto_dashboard_upload",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "dataset_id",
            "upload_id",
            "owner_id",
            "number",
            name="auto_dashboard_version",
        ),
        sa.CheckConstraint("number >= 1", name="auto_dashboard_number"),
    )
    op.create_index(
        "auto_dashboard_upload_time",
        "auto_dashboards",
        ["workspace_id", "dataset_id", "upload_id", "created_at"],
    )


def downgrade() -> None:
    kept = op.get_bind().execute(sa.text("SELECT 1 FROM auto_dashboards LIMIT 1"))
    if kept.first() is not None:
        raise RuntimeError("Automatic dashboards exist; refusing to discard them.")
    op.drop_index("auto_dashboard_upload_time", table_name="auto_dashboards")
    op.drop_table("auto_dashboards")
