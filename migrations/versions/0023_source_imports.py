"""Use case: Retains operator source versions and idempotent import publications.

What it does: Adds tenant-bound source/import metadata without changing retained
files or meanings; downgrade refuses while source configuration or imports exist.
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registered_sources",
        sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("version", sa.Integer, primary_key=True),
        sa.Column("configuration", sa.JSON, nullable=False),
        sa.Column("created_by", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="registered_source_version"),
    )
    op.create_table(
        "source_imports",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("workspace_id", sa.Uuid, nullable=False),
        sa.Column("actor_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("membership_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.Uuid, nullable=False),
        sa.Column("source_id", sa.Uuid, nullable=False),
        sa.Column("source_version", sa.Integer, nullable=False),
        sa.Column("dataset_id", sa.Uuid, nullable=False),
        sa.Column("selection", sa.JSON, nullable=False),
        sa.Column("access_reference", sa.JSON, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("upload_id", sa.Uuid),
        sa.Column("candidate_id", sa.Uuid),
        sa.Column("snapshot", sa.JSON),
        sa.Column("failure_code", sa.String(40)),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_id", "source_version"],
            [
                "registered_sources.workspace_id",
                "registered_sources.id",
                "registered_sources.version",
            ],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "upload_id"], ["uploads.workspace_id", "uploads.id"]
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "candidate_id"],
            ["refresh_candidates.workspace_id", "refresh_candidates.id"],
        ),
        sa.UniqueConstraint("workspace_id", "actor_id", "request_id"),
        sa.CheckConstraint(
            "status IN ('extracting','imported','staged','failed')", name="source_import_status"
        ),
        sa.CheckConstraint(
            "(status = 'extracting') = (completed_at IS NULL)", name="source_import_completion"
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at", name="source_import_order"
        ),
        sa.Index("source_import_history", "workspace_id", "actor_id", "dataset_id", "created_at"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    for name in ("source_imports", "registered_sources"):
        if connection.execute(sa.text(f"SELECT 1 FROM {name} LIMIT 1")).first():
            raise RuntimeError("Preserve all source configurations and imports before downgrade")
    op.drop_table("source_imports")
    op.drop_table("registered_sources")
