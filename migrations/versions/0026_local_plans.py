"""Use case: Retains local product allowances and idempotent admissions.

What it does: Adds price-free catalog/assignment versions and immutable usage
evidence, preserving all earlier product and model accounting records.
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_catalog",
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column("version", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("limits", sa.JSON, nullable=False),
        sa.Column("created_by", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="plan_catalog_version"),
    )
    op.create_table(
        "workspace_plans",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("plan_key", sa.String(40), nullable=False),
        sa.Column("plan_version", sa.Integer, nullable=False),
        sa.Column("limits", sa.JSON, nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_by", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("basis", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "version", name="workspace_plan_version"),
        sa.UniqueConstraint("workspace_id", "id", name="workspace_plan_scope"),
        sa.CheckConstraint("version > 0 AND ends_at > starts_at", name="workspace_plan_period"),
        sa.CheckConstraint(
            "basis IN ('native_default','administrator')", name="workspace_plan_basis"
        ),
    )
    op.create_table(
        "plan_admissions",
        sa.Column("workspace_id", sa.Uuid, sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("actor_id", sa.Uuid, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("kind", sa.String(24), primary_key=True),
        sa.Column("request_id", sa.Uuid, primary_key=True),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("assignment_id", sa.Uuid, nullable=True),
        sa.Column("quantity", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "assignment_id"],
            ["workspace_plans.workspace_id", "workspace_plans.id"],
        ),
        sa.CheckConstraint("quantity > 0", name="plan_admission_quantity"),
        sa.CheckConstraint(
            "kind IN ('processing','exports','forecasts','model_attempts')",
            name="plan_admission_kind",
        ),
    )
    op.create_index(
        "plan_admission_window", "plan_admissions", ["workspace_id", "kind", "created_at"]
    )


def downgrade() -> None:
    for name in ("plan_admissions", "workspace_plans", "plan_catalog"):
        if op.get_bind().execute(sa.text(f"SELECT 1 FROM {name} LIMIT 1")).first():
            raise RuntimeError(
                "Retain local allowance assignments and usage evidence before downgrade."
            )
    op.drop_index("plan_admission_window", table_name="plan_admissions")
    for name in ("plan_admissions", "workspace_plans", "plan_catalog"):
        op.drop_table(name)
