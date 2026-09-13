"""Use case: Adds persistence for saved items, conversation threads, and join paths.

What it does: Backs saved questions/prompts/dashboards, multi-turn threads with
structured references, and declared cross-dataset join paths.
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
    Index,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    Uuid,
)

revision = "0005"
down_revision = "0004"
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
Table("query_executions", metadata, Column("id", Uuid, primary_key=True))

saved_items = Table(
    "saved_items",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("upload_id", Uuid, nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("kind", String(20), nullable=False),
    Column("name", String(100), nullable=False),
    Column("description", String(500), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("shared", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id"],
        ["uploads.workspace_id", "uploads.dataset_id", "uploads.id"],
    ),
    CheckConstraint("kind IN ('question', 'prompt', 'dashboard')", name="saved_item_kind"),
    Index("saved_items_workspace_upload", "workspace_id", "dataset_id", "upload_id"),
    Index("saved_items_owner", "workspace_id", "owner_id"),
)
threads = Table(
    "threads",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("upload_id", Uuid, nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id"],
        ["uploads.workspace_id", "uploads.dataset_id", "uploads.id"],
    ),
    Index("threads_workspace_owner", "workspace_id", "owner_id"),
)
thread_turns = Table(
    "thread_turns",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("thread_id", Uuid, ForeignKey("threads.id"), nullable=False),
    Column("question", String(500), nullable=False),
    Column("kind", String(20), nullable=False),
    Column("query_id", Uuid, ForeignKey("query_executions.id"), nullable=True),
    Column("message", String(1000), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "kind IN ('numerical', 'textual', 'ambiguous', 'unsupported')", name="thread_turn_kind"
    ),
    Index("thread_turns_thread_time", "thread_id", "created_at"),
)
join_paths = Table(
    "join_paths",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("left_dataset_id", Uuid, nullable=False),
    Column("left_column", String(100), nullable=False),
    Column("right_dataset_id", Uuid, nullable=False),
    Column("right_column", String(100), nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workspace_id", "left_dataset_id", "right_dataset_id", name="join_paths_pair"),
    Index("join_paths_workspace", "workspace_id"),
)


def upgrade() -> None:
    metadata.create_all(
        op.get_bind(), tables=[saved_items, threads, thread_turns, join_paths], checkfirst=False
    )


def downgrade() -> None:
    metadata.drop_all(
        op.get_bind(), tables=[join_paths, thread_turns, threads, saved_items], checkfirst=False
    )
