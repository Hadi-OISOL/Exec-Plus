"""Use case: Stores each person's optional onboarding answers once, independent of workspaces.

What it does: Adds the additive user_profiles table; older images ignore it and downgrade
refuses while answers exist.
"""

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("preferred_name", sa.String(120), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("skipped_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="user_profile_version"),
    )


def downgrade() -> None:
    kept = op.get_bind().execute(sa.text("SELECT 1 FROM user_profiles LIMIT 1"))
    if kept.first() is not None:
        raise RuntimeError("User profiles exist; refusing to discard them.")
    op.drop_table("user_profiles")
