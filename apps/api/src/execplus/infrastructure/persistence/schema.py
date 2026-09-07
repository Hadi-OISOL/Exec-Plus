"""Use case: Defines the current PostgreSQL control-plane schema.

What it does: Enforces tenant ownership, references, uniqueness, and seat bounds.
"""

from sqlalchemy import (
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

metadata = MetaData()
users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("display_name", String(100), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
workspaces = Table(
    "workspaces",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", String(100), nullable=False),
    Column("seat_limit", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("seat_limit >= 3 AND seat_limit <= 50", name="seat_limit_bounds"),
)
memberships = Table(
    "memberships",
    metadata,
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), primary_key=True),
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("role", String(10), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("role IN ('owner', 'admin', 'member')", name="membership_role"),
    Index("memberships_user", "user_id"),
)
invitations = Table(
    "invitations",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("email", String(254), nullable=False),
    Column("role", String(10), nullable=False),
    Column("status", String(12), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("invited_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("role IN ('admin', 'member')", name="invitation_role"),
    CheckConstraint(
        "status IN ('pending', 'accepted', 'revoked', 'expired')", name="invitation_status"
    ),
    Index("invitations_workspace", "workspace_id", "status"),
)
datasets = Table(
    "datasets",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workspace_id", "id"),
)
uploads = Table(
    "uploads",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("filename", String(255), nullable=False),
    Column("content_type", String(100), nullable=False),
    Column("size", Integer, nullable=False),
    Column("storage_key", String(255), nullable=False, unique=True),
    Column("checksum", String(64), nullable=False),
    Column("status", String(12), nullable=False),
    Column("format", String(5), nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("column_count", Integer, nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]),
    CheckConstraint("size > 0 AND size <= 20971520", name="upload_size_bounds"),
    CheckConstraint("status = 'stored'", name="upload_status"),
    Index("uploads_workspace_dataset", "workspace_id", "dataset_id"),
)
audit_events = Table(
    "audit_events",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("actor_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("action", String(50), nullable=False),
    Column("resource_type", String(30), nullable=False),
    Column("resource_id", Uuid, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("audit_workspace_time", "workspace_id", "created_at"),
)
