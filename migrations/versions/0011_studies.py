"""Use case: Adds private study versions, bounded dashboards and organization grouping.

What it does: Preserves existing workspaces and historical evidence while adding Phase 4A metadata.
"""

from alembic import op
from sqlalchemy import (
    JSON,
    Boolean,
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

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "understanding_tenant_id", "understandings", ["workspace_id", "dataset_id", "id"]
    )
    op.create_unique_constraint("upload_workspace_id", "uploads", ["workspace_id", "id"])
    op.create_table(
        "organizations",
        Column("id", Uuid, primary_key=True),
        Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("name", String(100), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "departments",
        Column("workspace_id", Uuid, ForeignKey("workspaces.id"), primary_key=True),
        Column("organization_id", Uuid, ForeignKey("organizations.id"), nullable=False),
        Column("name", String(100), nullable=False),
    )
    op.create_table(
        "studies",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, nullable=False),
        Column("dataset_id", Uuid, nullable=False),
        Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("name", String(100), nullable=False),
        Column("shared", Boolean, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        ForeignKeyConstraint(
            ["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]
        ),
        UniqueConstraint("workspace_id", "id"),
    )
    op.create_table(
        "study_versions",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, nullable=False),
        Column("study_id", Uuid, nullable=False),
        Column("number", Integer, nullable=False),
        Column("upload_id", Uuid, nullable=False),
        ForeignKeyConstraint(["workspace_id", "upload_id"], ["uploads.workspace_id", "uploads.id"]),
        Column("parent_id", Uuid, nullable=True),
        Column("question", String(500), nullable=False),
        Column("method", JSON, nullable=False),
        Column("evidence", JSON, nullable=False),
        Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        ForeignKeyConstraint(["workspace_id", "study_id"], ["studies.workspace_id", "studies.id"]),
        UniqueConstraint("workspace_id", "study_id", "id"),
        ForeignKeyConstraint(
            ["workspace_id", "study_id", "parent_id"],
            ["study_versions.workspace_id", "study_versions.study_id", "study_versions.id"],
        ),
        UniqueConstraint("workspace_id", "study_id", "number"),
        CheckConstraint("number BETWEEN 1 AND 50", name="study_version_limit"),
    )
    op.create_table(
        "study_boards",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
        Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("name", String(100), nullable=False),
        Column("shared", Boolean, nullable=False),
        Column("version", Integer, nullable=False),
        Column("pins", JSON, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        CheckConstraint("json_array_length(pins) <= 6", name="six_board_pins"),
        UniqueConstraint("workspace_id", "id"),
    )
    op.create_table(
        "view_dismissals",
        Column("workspace_id", Uuid, primary_key=True),
        Column("dataset_id", Uuid, primary_key=True),
        Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
        Column("understanding_id", Uuid, primary_key=True),
        Column("dismissed", JSON, nullable=False),
        ForeignKeyConstraint(
            ["workspace_id", "dataset_id", "understanding_id"],
            ["understandings.workspace_id", "understandings.dataset_id", "understandings.id"],
        ),
    )


def downgrade() -> None:
    for name in (
        "view_dismissals",
        "study_boards",
        "study_versions",
        "studies",
        "departments",
        "organizations",
    ):
        op.drop_table(name)
    op.drop_constraint("upload_workspace_id", "uploads", type_="unique")
    op.drop_constraint("understanding_tenant_id", "understandings", type_="unique")
