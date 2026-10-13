"""Use case: Adds immutable scenario comparisons to existing private analysis storage.

What it does: Extends the kind constraint while preserving all analysis and review records.
"""

from alembic import op
from sqlalchemy import text

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("analysis_kind", "analysis_runs", type_="check")
    op.create_check_constraint(
        "analysis_kind",
        "analysis_runs",
        "kind IN ('robust_distribution','bounded_allocation','scenario_comparison')",
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(text("SELECT COUNT(*) FROM analysis_runs WHERE kind='scenario_comparison'"))
        .scalar_one()
    ):
        raise RuntimeError(
            "Preserve scenario comparisons before downgrading; no data is deleted automatically."
        )
    op.drop_constraint("analysis_kind", "analysis_runs", type_="check")
    op.create_check_constraint(
        "analysis_kind", "analysis_runs", "kind IN ('robust_distribution','bounded_allocation')"
    )
