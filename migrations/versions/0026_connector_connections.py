"""Use case: Stores each user's encrypted connection to an external data platform.

What it does: Adds one sealed-credentials row per user and provider and keeps every existing record.
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connector_connections",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("provider", sa.String(40), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("sealed_credentials", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM connector_connections")).scalar_one():
        raise RuntimeError(
            "Disconnect data platforms before downgrading; no data is deleted automatically."
        )
    op.drop_table("connector_connections")
