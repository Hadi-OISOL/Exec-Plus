"""Use case: Stores explicit personal context independently of any selected dataset.

What it does: Adds membership-bound private memory without rewriting saved source evidence.
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column("workspace_id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(300), nullable=False),
        sa.Column("focus", sa.String(500), nullable=False),
        sa.Column("explanation_style", sa.String(20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "user_id"],
            ["memberships.workspace_id", "memberships.user_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("version > 0", name="agent_memory_version"),
        sa.CheckConstraint(
            "explanation_style IN ('concise', 'step_by_step')", name="agent_memory_style"
        ),
    )


def downgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM agent_memories")).scalar_one()
    if count:
        raise RuntimeError(
            "Preserve personal memory and its deletion revisions before downgrading; "
            "no data is deleted automatically."
        )
    op.drop_table("agent_memories")
