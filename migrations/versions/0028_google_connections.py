"""Use case: Stores each user's Google connection so sheet imports can run without a new consent.

What it does: Adds one encrypted refresh-token row per user and leaves every existing record intact.
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "invitation_identity_approvals_user_id_fkey",
        "invitation_identity_approvals",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "invitation_identity_approvals_user_id_fkey",
        "invitation_identity_approvals",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_table(
        "google_connections",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("google_email", sa.String(254), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("version", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "external_identities",
        sa.Column("provider", sa.String(40), primary_key=True),
        sa.Column("subject", sa.String(255), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "oauth_attempts",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("browser_hash", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("purpose", sa.String(12), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("session_hash", sa.String(64)),
        sa.Column("connection_version", sa.Uuid()),
        sa.Column("sealed_payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("handoff_hash", sa.String(64), unique=True),
        sa.Column("handoff_expires_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("purpose IN ('signin', 'connect')", name="oauth_attempt_purpose"),
        sa.CheckConstraint(
            "status IN ('pending', 'claimed', 'complete', 'consumed', 'revoked')",
            name="oauth_attempt_status",
        ),
    )
    op.create_index("oauth_attempt_actor", "oauth_attempts", ["user_id", "provider"])


def downgrade() -> None:
    if any(
        op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        for table in ("google_connections", "external_identities", "oauth_attempts")
    ):
        raise RuntimeError(
            "Disconnect Google accounts before downgrading; no data is deleted automatically."
        )
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM invitation_identity_approvals a LEFT JOIN local_accounts l "
                "ON l.user_id=a.user_id WHERE l.user_id IS NULL LIMIT 1"
            )
        )
        .first()
    ):
        raise RuntimeError("Keep external account identity approvals before downgrading.")
    op.drop_constraint(
        "invitation_identity_approvals_user_id_fkey",
        "invitation_identity_approvals",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "invitation_identity_approvals_user_id_fkey",
        "invitation_identity_approvals",
        "local_accounts",
        ["user_id"],
        ["user_id"],
    )
    op.drop_table("oauth_attempts")
    op.drop_table("external_identities")
    op.drop_table("google_connections")
