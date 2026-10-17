"""Use case: Adds local password accounts and private resumable setup.

What it does: Preserves prior identity/evidence rows and refuses destructive downgrades.
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "local_accounts",
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "account_events",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("reason", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("account_events_private", "account_events", ["user_id", "created_at"])
    op.create_table(
        "account_rate_windows",
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("used", sa.Integer, nullable=False),
        sa.CheckConstraint("used BETWEEN 1 AND 60", name="account_auth_rate_bounds"),
    )
    op.create_table(
        "invitation_identity_approvals",
        sa.Column(
            "invitation_id",
            sa.Uuid,
            sa.ForeignKey("invitations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("local_accounts.user_id"), nullable=False),
        sa.Column("approved_by", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "onboarding_progress",
        sa.Column("workspace_id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, primary_key=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("active_step", sa.String(20), nullable=False),
        sa.Column("skipped_steps", sa.JSON, nullable=False),
        sa.Column("paused", sa.Boolean, nullable=False),
        sa.Column("finished", sa.Boolean, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "user_id"],
            ["memberships.workspace_id", "memberships.user_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("version > 0", name="onboarding_progress_version"),
        sa.CheckConstraint(
            "active_step IN ('setup', 'data', 'quality', 'meaning', 'analysis', "
            "'dashboard', 'recommendations', 'team')",
            name="onboarding_progress_step",
        ),
    )


def downgrade() -> None:
    for table in (
        "local_accounts",
        "account_events",
        "invitation_identity_approvals",
        "onboarding_progress",
    ):
        if op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError(
                "Keep local accounts, security history and private guide progress; "
                "downgrade would erase retained records."
            )
    op.drop_table("onboarding_progress")
    op.drop_table("invitation_identity_approvals")
    op.drop_table("account_rate_windows")
    op.drop_index("account_events_private", table_name="account_events")
    op.drop_table("account_events")
    op.drop_table("local_accounts")
