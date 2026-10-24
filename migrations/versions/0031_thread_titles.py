"""Use case: Lets owners rename and hide their private chats.

What it does: Adds nullable title and hidden time to threads; additive, older images ignore them.
"""

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("threads", sa.Column("title", sa.String(120), nullable=True))
    op.add_column("threads", sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    kept = op.get_bind().execute(
        sa.text("SELECT 1 FROM threads WHERE title IS NOT NULL OR hidden_at IS NOT NULL LIMIT 1")
    )
    if kept.first() is not None:
        raise RuntimeError("Chat names or hidden chats exist; refusing to discard them.")
    op.drop_column("threads", "hidden_at")
    op.drop_column("threads", "title")
