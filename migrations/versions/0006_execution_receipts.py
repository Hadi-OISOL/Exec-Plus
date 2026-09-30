"""Use case: Preserves replayable execution receipts without rewriting historical records.

What it does: Adds exact snapshot and result evidence to future analytical executions.
"""

from alembic import op
from sqlalchemy import JSON, Column, text

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("saved_item_kind", "saved_items", type_="check")
    op.create_check_constraint(
        "saved_item_kind", "saved_items", "kind IN ('question', 'prompt', 'dashboard', 'analysis')"
    )
    op.add_column("query_executions", Column("receipt", JSON, nullable=False, server_default="{}"))


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(text("SELECT COUNT(*) FROM saved_items WHERE kind = 'analysis'"))
        .scalar()
    ):
        raise RuntimeError("Export and remove saved analyses before downgrading below 0006")
    op.drop_constraint("saved_item_kind", "saved_items", type_="check")
    op.create_check_constraint(
        "saved_item_kind", "saved_items", "kind IN ('question', 'prompt', 'dashboard')"
    )
    op.drop_column("query_executions", "receipt")
