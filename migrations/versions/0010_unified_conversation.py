"""Use case: Retains private, retry-safe conversation steps and evidence references.

What it does: Adds durable turn states without changing historical query receipts.
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("thread_turns", sa.Column("request_id", sa.Uuid(), nullable=True))
    op.add_column(
        "thread_turns",
        sa.Column("status", sa.String(20), nullable=False, server_default="complete"),
    )
    op.add_column(
        "thread_turns",
        sa.Column("evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_unique_constraint("thread_request", "thread_turns", ["thread_id", "request_id"])
    op.create_check_constraint(
        "thread_status", "thread_turns", "status IN ('running', 'complete', 'partial', 'failed')"
    )
    op.drop_constraint("thread_turn_kind", "thread_turns", type_="check")
    op.create_check_constraint(
        "thread_turn_kind",
        "thread_turns",
        "kind IN ('numerical', 'rows', 'overview', 'textual', 'mixed', 'ambiguous', 'unsupported')",
    )


def downgrade() -> None:
    op.execute("UPDATE thread_turns SET kind = 'textual' WHERE kind = 'mixed'")
    op.drop_constraint("thread_turn_kind", "thread_turns", type_="check")
    op.create_check_constraint(
        "thread_turn_kind",
        "thread_turns",
        "kind IN ('numerical', 'rows', 'overview', 'textual', 'ambiguous', 'unsupported')",
    )
    op.drop_constraint("thread_status", "thread_turns", type_="check")
    op.drop_constraint("thread_request", "thread_turns", type_="unique")
    for column in ("evidence", "status", "request_id"):
        op.drop_column("thread_turns", column)
