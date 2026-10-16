"""Use case: Adds scoped read-only keys, private embeds and signed webhook metadata.

What it does: Keeps secrets hashed and delivery work idempotent while preserving
all existing tables; downgrade refuses while integration configuration remains.
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_keys",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid,
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("membership_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("dataset_ids", sa.JSON, nullable=False),
        sa.Column("operations", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("rate_limit", sa.Integer, nullable=False),
        sa.CheckConstraint("rate_limit BETWEEN 1 AND 60", name="integration_key_rate"),
        sa.CheckConstraint("expires_at > created_at", name="integration_key_expiry"),
        sa.Index("integration_keys_actor", "workspace_id", "user_id"),
    )
    op.create_table(
        "integration_request_windows",
        sa.Column(
            "key_id",
            sa.Uuid,
            sa.ForeignKey("integration_keys.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("used", sa.Integer, nullable=False),
        sa.CheckConstraint("used BETWEEN 1 AND 60", name="integration_request_count"),
    )
    op.create_table(
        "embed_grants",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid,
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("membership_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "board_id",
            sa.Uuid,
            sa.ForeignKey("study_boards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("board_version", sa.Integer, nullable=False),
        sa.Column("host_origin", sa.String(300), nullable=False),
        sa.Column("bootstrap_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("session_hash", sa.String(64), unique=True),
        sa.Column("session_expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "board_version > 0 AND expires_at > created_at", name="embed_grant_bounds"
        ),
        sa.CheckConstraint(
            "(session_hash IS NULL) = (session_expires_at IS NULL)", name="embed_session_pair"
        ),
        sa.Index("embed_grants_actor", "workspace_id", "user_id"),
    )
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid,
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("membership_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dataset_ids", sa.JSON, nullable=False),
        sa.Column("event_types", sa.JSON, nullable=False),
        sa.Column("destination", sa.String(2000), nullable=False),
        sa.Column("signing_version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("signing_version > 0", name="webhook_signing_version"),
        sa.Index("webhook_subscriptions_actor", "workspace_id", "user_id"),
    )
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "subscription_id",
            sa.Uuid,
            sa.ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.Uuid, nullable=False),
        sa.Column(
            "dataset_id", sa.Uuid, sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_status", sa.Integer),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("lease_id", sa.Uuid),
        sa.UniqueConstraint(
            "subscription_id", "kind", "resource_id", name="webhook_event_identity"
        ),
        sa.CheckConstraint(
            "kind IN ('job.succeeded','job.failed','refresh.accepted')", name="webhook_event_kind"
        ),
        sa.CheckConstraint(
            "status IN ('pending','sending','delivered','failed','cancelled')",
            name="webhook_delivery_state",
        ),
        sa.CheckConstraint("attempts BETWEEN 0 AND 6", name="webhook_attempt_bound"),
        sa.CheckConstraint(
            "last_status IS NULL OR last_status BETWEEN 100 AND 599", name="webhook_http_status"
        ),
        sa.Index("webhook_deliveries_due", "status", "next_attempt_at"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    for name in ("integration_keys", "embed_grants", "webhook_subscriptions", "webhook_deliveries"):
        if connection.execute(sa.text("SELECT 1 FROM " + name + " LIMIT 1")).first():
            raise RuntimeError(
                "Preserve integration credentials, grants and delivery evidence before downgrade."
            )
    for name in (
        "webhook_deliveries",
        "webhook_subscriptions",
        "embed_grants",
        "integration_request_windows",
        "integration_keys",
    ):
        op.drop_table(name)
