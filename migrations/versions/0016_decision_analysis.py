"""Use case: Retains private anomaly and allocation analyses with human review history.

What it does: Adds immutable evidence and owner-constrained reviews while preserving prior data.
"""

from alembic import op
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, nullable=False),
        Column("dataset_id", Uuid, nullable=False),
        Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("upload_id", Uuid, nullable=False),
        Column("revision_id", Uuid, nullable=False),
        Column("understanding_id", Uuid, nullable=False),
        Column("name", String(100), nullable=False),
        Column("kind", String(32), nullable=False),
        Column("method_version", String(40), nullable=False),
        Column("request", JSON, nullable=False),
        Column("evidence", JSON, nullable=False),
        Column("result", JSON, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        UniqueConstraint("workspace_id", "owner_id", "id", name="analysis_run_owner"),
        ForeignKeyConstraint(
            ["workspace_id", "dataset_id", "upload_id", "revision_id"],
            [
                "revisions.workspace_id",
                "revisions.dataset_id",
                "revisions.upload_id",
                "revisions.id",
            ],
            name="analysis_revision",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "dataset_id", "upload_id", "revision_id", "understanding_id"],
            [
                "understandings.workspace_id",
                "understandings.dataset_id",
                "understandings.upload_id",
                "understandings.revision_id",
                "understandings.id",
            ],
            name="analysis_understanding",
        ),
        CheckConstraint(
            "kind IN ('robust_distribution','bounded_allocation')", name="analysis_kind"
        ),
    )
    op.create_index(
        "analysis_owner_time",
        "analysis_runs",
        ["workspace_id", "dataset_id", "owner_id", "created_at"],
    )
    op.create_table(
        "analysis_reviews",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, nullable=False),
        Column("run_id", Uuid, nullable=False),
        Column("owner_id", Uuid, nullable=False),
        Column("sequence", Integer, nullable=False),
        Column("target", String(32), nullable=False),
        Column("status", String(24), nullable=False),
        Column("note", String(1000), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        ForeignKeyConstraint(
            ["workspace_id", "owner_id", "run_id"],
            ["analysis_runs.workspace_id", "analysis_runs.owner_id", "analysis_runs.id"],
            name="analysis_review_owner",
        ),
        UniqueConstraint("workspace_id", "run_id", "sequence", name="analysis_review_sequence"),
        CheckConstraint("sequence BETWEEN 1 AND 200", name="analysis_review_limit"),
        CheckConstraint(
            "status IN ('pending','approved','rejected','expected',"
            "'investigate','data_issue','dismissed')",
            name="analysis_review_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("analysis_reviews")
    op.drop_table("analysis_runs")
