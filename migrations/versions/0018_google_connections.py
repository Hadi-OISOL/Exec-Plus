"""Use case: Stores each user's Google connection so sheet imports can run without a new consent.

What it does: Adds one encrypted refresh-token row per user and leaves every existing record intact.
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "google_connections",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("google_email", sa.String(254), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM google_connections")).scalar_one():
        raise RuntimeError(
            "Disconnect Google accounts before downgrading; no data is deleted automatically."
        )
    op.drop_table("google_connections")
