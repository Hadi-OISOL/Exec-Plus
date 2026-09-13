"""Use case: Records which model route, if any, produced a query's structured plan.

What it does: Adds a nullable model_route column so NL-routed queries are traceable.
"""

from alembic import op
from sqlalchemy import Column, MetaData, String, Table, Uuid

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None
metadata = MetaData()
query_executions = Table(
    "query_executions",
    metadata,
    Column("id", Uuid, primary_key=True),
)


def upgrade() -> None:
    op.add_column("query_executions", Column("model_route", String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("query_executions", "model_route")
