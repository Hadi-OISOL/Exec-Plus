"""Use case: Persists activation, document metadata, and report delivery state.

What it does: Adds tenant-bound records without placing document passages in PostgreSQL.
"""

from alembic import op
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    Uuid,
)

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

metadata = MetaData()
feedback = Table(
    "feedback",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("actor_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("feature", String(40), nullable=False),
    Column("rating", Integer, nullable=False),
    Column("category", String(40), nullable=False),
    Column("release", String(40), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("rating BETWEEN 1 AND 5", name="feedback_rating"),
    Index("feedback_workspace", "workspace_id"),
)

documents = Table(
    "documents",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("checksum", String(64), nullable=False),
    Column("size", Integer, nullable=False),
    Column("shared", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workspace_id", "id"),
    ForeignKeyConstraint(["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]),
    Index("documents_workspace_dataset", "workspace_id", "dataset_id"),
)

document_chunks = Table(
    "document_chunks",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("document_id", Uuid, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("start", Integer, nullable=False),
    Column("end", Integer, nullable=False),
    Column("checksum", String(64), nullable=False),
    Column("algorithm", String(40), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "document_id"],
        ["documents.workspace_id", "documents.id"],
        ondelete="CASCADE",
    ),
    UniqueConstraint("workspace_id", "document_id", "ordinal"),
)

report_schedules = Table(
    "report_schedules",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("item_id", Uuid, nullable=False),
    Column("interval_hours", Integer, nullable=False),
    Column("next_due", DateTime(timezone=True), nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "item_id"],
        ["saved_items.workspace_id", "saved_items.id"],
        ondelete="CASCADE",
    ),
    UniqueConstraint("workspace_id", "id"),
    CheckConstraint("interval_hours BETWEEN 1 AND 8760", name="report_interval"),
    Index("reports_due", "enabled", "next_due"),
)

report_deliveries = Table(
    "report_deliveries",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("schedule_id", Uuid, nullable=False),
    Column("due_at", DateTime(timezone=True), nullable=False),
    Column("status", String(40), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "schedule_id"],
        ["report_schedules.workspace_id", "report_schedules.id"],
        ondelete="CASCADE",
    ),
    UniqueConstraint("workspace_id", "schedule_id", "due_at"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for name in ("users", "workspaces", "datasets", "saved_items"):
        Table(name, metadata, autoload_with=bind, extend_existing=True)
    op.create_unique_constraint(
        "saved_items_workspace_id_id_key", "saved_items", ["workspace_id", "id"]
    )
    for table in (feedback, documents, document_chunks, report_schedules, report_deliveries):
        table.create(bind)


def downgrade() -> None:
    for name in (
        "report_deliveries",
        "report_schedules",
        "document_chunks",
        "documents",
        "feedback",
    ):
        op.drop_table(name)
    op.drop_constraint("saved_items_workspace_id_id_key", "saved_items", type_="unique")
