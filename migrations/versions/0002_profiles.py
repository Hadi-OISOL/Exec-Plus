"""Use case: Adds tenant-scoped profiling history and usage metadata.

What it does: Preserves existing uploads while adding immutable revisions and active pointers.
"""

from alembic import op
from sqlalchemy import (
    JSON,
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

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
metadata = MetaData()
Table("users", metadata, Column("id", Uuid, primary_key=True))
Table("workspaces", metadata, Column("id", Uuid, primary_key=True))
Table(
    "uploads",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid),
    Column("dataset_id", Uuid),
)

revisions = Table(
    "revisions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("upload_id", Uuid, nullable=False),
    Column("parent_id", Uuid, nullable=True),
    Column("algorithm", String(40), nullable=False),
    Column("source_checksum", String(64), nullable=False),
    Column("output_checksum", String(64), nullable=False),
    Column("recipe", JSON, nullable=False),
    Column("profile", JSON, nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workspace_id", "dataset_id", "upload_id", "id"),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id"],
        ["uploads.workspace_id", "uploads.dataset_id", "uploads.id"],
    ),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id", "parent_id"],
        ["revisions.workspace_id", "revisions.dataset_id", "revisions.upload_id", "revisions.id"],
    ),
    Index("revisions_upload", "workspace_id", "dataset_id", "upload_id"),
)

revision_heads = Table(
    "revision_heads",
    metadata,
    Column("workspace_id", Uuid, primary_key=True),
    Column("dataset_id", Uuid, primary_key=True),
    Column("upload_id", Uuid, primary_key=True),
    Column("revision_id", Uuid, nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id", "revision_id"],
        ["revisions.workspace_id", "revisions.dataset_id", "revisions.upload_id", "revisions.id"],
    ),
)
usage_events = Table(
    "usage_events",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("actor_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("kind", String(40), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("resource_id", Uuid, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "kind IN ('upload', 'storage_bytes', 'seat_added', 'seat_removed', "
        "'seat_limit', 'profile', 'cleaning', 'restore', 'sample')",
        name="usage_kind",
    ),
    CheckConstraint("quantity >= 0", name="usage_quantity"),
    Index("usage_workspace_time", "workspace_id", "created_at"),
)


def upgrade() -> None:
    op.add_column("uploads", Column("sample_id", String(40), nullable=True))
    op.create_unique_constraint(
        "uploads_tenant_id", "uploads", ["workspace_id", "dataset_id", "id"]
    )
    metadata.create_all(
        op.get_bind(), tables=[revisions, revision_heads, usage_events], checkfirst=False
    )


def downgrade() -> None:
    op.drop_column("uploads", "sample_id")
    metadata.drop_all(
        op.get_bind(), tables=[revision_heads, usage_events, revisions], checkfirst=False
    )
    op.drop_constraint("uploads_tenant_id", "uploads", type_="unique")
