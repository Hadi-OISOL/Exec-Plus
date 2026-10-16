"""Use case: Retains explicit model prices, allowances and provider attempt evidence.

What it does: Adds isolated accounting records and refuses downgrade while any
configuration or usage evidence remains, without changing existing source data.
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_prices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider", sa.String(160), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "model", "created_at", name="usage_price_version"),
    )
    op.create_table(
        "usage_policies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("workspace_id", "version", name="usage_policy_version"),
        sa.UniqueConstraint("workspace_id", "id", name="usage_policy_workspace"),
        sa.CheckConstraint("version > 0 AND ends_at > starts_at", name="usage_policy_window"),
    )
    op.create_table(
        "usage_attempts",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(160), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=True),
        sa.Column("price_id", sa.Uuid(), sa.ForeignKey("usage_prices.id"), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("held_exposure", sa.Numeric(40, 18), nullable=False),
        sa.Column("cost", sa.Numeric(40, 18), nullable=True),
        sa.Column("outcome", sa.String(24), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("cost_basis", sa.String(32), nullable=True),
        sa.Column("evidence_ref", sa.String(160), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "policy_id"],
            ["usage_policies.workspace_id", "usage_policies.id"],
            name="usage_attempt_policy_workspace",
        ),
        sa.CheckConstraint(
            "state IN ('reserved','started','settled','unknown','released')",
            name="usage_attempt_state",
        ),
        sa.CheckConstraint(
            "version > 0 AND held_exposure >= 0 AND (cost IS NULL OR cost >= 0)",
            name="usage_attempt_amounts",
        ),
        sa.CheckConstraint(
            "operation IN ('conversation','data_reading','document_answer','summary')",
            name="usage_attempt_operation",
        ),
    )
    op.create_index("usage_attempt_window", "usage_attempts", ["workspace_id", "created_at"])
    op.create_index("usage_attempt_active", "usage_attempts", ["workspace_id", "state"])
    op.create_table(
        "model_usage_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "attempt_id"],
            ["usage_attempts.workspace_id", "usage_attempts.id"],
            name="usage_event_attempt_workspace",
        ),
        sa.UniqueConstraint("workspace_id", "attempt_id", "sequence", name="usage_event_sequence"),
        sa.CheckConstraint("sequence > 0", name="usage_event_sequence_positive"),
    )


def downgrade() -> None:
    for name in ("model_usage_events", "usage_attempts", "usage_policies", "usage_prices"):
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {name}")).scalar_one():
            raise RuntimeError(
                "Preserve all model usage and allowance evidence before downgrading."
            )
    for name in ("model_usage_events", "usage_attempts", "usage_policies", "usage_prices"):
        op.drop_table(name)
