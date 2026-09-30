"""Use case: Stores record and dataset-guide conversation turns without losing prior history.

What it does: Extends the turn-kind constraint and records the composed model route.
"""

from alembic import op
from sqlalchemy import Column, String

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("thread_turn_kind", "thread_turns", type_="check")
    op.create_check_constraint(
        "thread_turn_kind",
        "thread_turns",
        "kind IN ('numerical', 'rows', 'overview', 'textual', 'ambiguous', 'unsupported')",
    )
    op.add_column("thread_turns", Column("model_route", String(200), nullable=True))


def downgrade() -> None:
    op.execute("UPDATE thread_turns SET kind = 'textual' WHERE kind = 'overview'")
    op.execute("UPDATE thread_turns SET kind = 'numerical' WHERE kind = 'rows'")
    op.drop_column("thread_turns", "model_route")
    op.drop_constraint("thread_turn_kind", "thread_turns", type_="check")
    op.create_check_constraint(
        "thread_turn_kind",
        "thread_turns",
        "kind IN ('numerical', 'textual', 'ambiguous', 'unsupported')",
    )
