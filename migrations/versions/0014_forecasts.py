"""Use case: Retains private basic forecasts and later actual comparisons.

What it does: Adds immutable evidence tables with owner and complete source identity constraints.
"""

from alembic import op
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
)

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "understandings_source_identity",
        "understandings",
        ["workspace_id", "dataset_id", "upload_id", "revision_id", "id"],
    )
    op.create_table(
        "forecast_runs",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, nullable=False),
        Column("dataset_id", Uuid, nullable=False),
        Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("name", String(100), nullable=False),
        Column("upload_id", Uuid, nullable=False),
        Column("revision_id", Uuid, nullable=False),
        Column("understanding_id", Uuid, nullable=False),
        Column("method", String(40), nullable=False),
        Column("method_version", String(40), nullable=False),
        Column("request", JSON, nullable=False),
        Column("evidence", JSON, nullable=False),
        Column("result", JSON, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        UniqueConstraint(
            "workspace_id", "dataset_id", "owner_id", "id", name="forecast_run_owner_identity"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "dataset_id", "upload_id", "revision_id"],
            [
                "revisions.workspace_id",
                "revisions.dataset_id",
                "revisions.upload_id",
                "revisions.id",
            ],
            name="forecast_run_revision",
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
            name="forecast_run_understanding",
        ),
    )
    op.create_table(
        "forecast_comparisons",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, nullable=False),
        Column("dataset_id", Uuid, nullable=False),
        Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("forecast_id", Uuid, nullable=False),
        Column("upload_id", Uuid, nullable=False),
        Column("revision_id", Uuid, nullable=False),
        Column("understanding_id", Uuid, nullable=False),
        Column("evidence", JSON, nullable=False),
        Column("result", JSON, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        ForeignKeyConstraint(
            ["workspace_id", "dataset_id", "owner_id", "forecast_id"],
            [
                "forecast_runs.workspace_id",
                "forecast_runs.dataset_id",
                "forecast_runs.owner_id",
                "forecast_runs.id",
            ],
            name="forecast_comparison_run",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "dataset_id", "upload_id", "revision_id"],
            [
                "revisions.workspace_id",
                "revisions.dataset_id",
                "revisions.upload_id",
                "revisions.id",
            ],
            name="forecast_comparison_revision",
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
            name="forecast_comparison_understanding",
        ),
    )
    op.create_index(
        "forecast_runs_owner",
        "forecast_runs",
        ["workspace_id", "dataset_id", "owner_id", "created_at"],
    )
    op.create_index(
        "forecast_comparisons_owner",
        "forecast_comparisons",
        ["workspace_id", "forecast_id", "owner_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("forecast_comparisons")
    op.drop_table("forecast_runs")
    op.drop_constraint("understandings_source_identity", "understandings", type_="unique")
