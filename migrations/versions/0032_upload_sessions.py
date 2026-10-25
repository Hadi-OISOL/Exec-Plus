"""Use case: Adds resumable chunked upload sessions and per-user storage quota overrides.

What it does: Creates two additive tables and lifts the 20 MiB upload row bound; downgrade
refuses while sessions, overrides or larger uploads exist.
"""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("dataset_id", sa.Uuid, nullable=True),
        sa.Column("created_by", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("chunk_size", sa.Integer, nullable=False),
        sa.Column("chunk_hashes", sa.JSON, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("upload_id", sa.Uuid, nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.String(300), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size_bytes > 0 AND chunk_size > 0", name="upload_session_sizes"),
        sa.CheckConstraint(
            "status IN ('open','processing','completed','failed','cancelled','expired')",
            name="upload_session_status",
        ),
    )
    op.create_index("upload_sessions_owner", "upload_sessions", ["created_by", "status"])
    op.create_index("upload_sessions_status", "upload_sessions", ["status", "expires_at"])
    op.create_table(
        "user_storage_quotas",
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("quota_bytes", sa.BigInteger, nullable=False),
        sa.Column("set_by", sa.Uuid, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quota_bytes >= 0", name="user_storage_quota_bounds"),
    )
    op.drop_constraint("upload_size_bounds", "uploads", type_="check")
    op.create_check_constraint("upload_size_bounds", "uploads", "size > 0")


def downgrade() -> None:
    bind = op.get_bind()
    for statement in (
        "SELECT 1 FROM upload_sessions LIMIT 1",
        "SELECT 1 FROM user_storage_quotas LIMIT 1",
        "SELECT 1 FROM uploads WHERE size > 20971520 LIMIT 1",
    ):
        if bind.execute(sa.text(statement)).first() is not None:
            raise RuntimeError(
                "Upload sessions, quota overrides or uploads above 20 MiB exist; "
                "refusing to discard them."
            )
    op.drop_constraint("upload_size_bounds", "uploads", type_="check")
    op.create_check_constraint("upload_size_bounds", "uploads", "size > 0 AND size <= 20971520")
    op.drop_table("user_storage_quotas")
    op.drop_index("upload_sessions_status", "upload_sessions")
    op.drop_index("upload_sessions_owner", "upload_sessions")
    op.drop_table("upload_sessions")
