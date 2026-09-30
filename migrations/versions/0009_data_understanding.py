"""Use case: Retains immutable business meanings and private analysis preferences.

What it does: Adds tenant-bound definition history without rewriting upload profiles or receipts.
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "understandings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "dataset_id", "version"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "dataset_id", "upload_id", "revision_id"],
            [
                "revisions.workspace_id",
                "revisions.dataset_id",
                "revisions.upload_id",
                "revisions.id",
            ],
        ),
        sa.CheckConstraint(
            "state IN ('inferred', 'confirmed', 'rejected', 'needs_review')",
            name="understanding_state",
        ),
        sa.CheckConstraint("version > 0", name="understanding_version"),
    )
    op.create_table(
        "data_preferences",
        sa.Column("workspace_id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("domain_hint", sa.String(20), nullable=False),
        sa.Column("goal", sa.String(500), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]
        ),
    )


def downgrade() -> None:
    op.drop_table("data_preferences")
    op.drop_table("understandings")
