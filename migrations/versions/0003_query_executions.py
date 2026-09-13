"""Use case: Persists reconstructable calculation lineage for every executed query.

What it does: Adds the query_executions table so answers can be traced after the fact.
"""

from alembic import op
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Uuid,
)

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None
metadata = MetaData()
Table("users", metadata, Column("id", Uuid, primary_key=True))
Table(
    "datasets",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid),
)

query_executions = Table(
    "query_executions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("actor_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("dataset_name", String(100), nullable=False),
    Column("metric", String(100), nullable=False),
    Column("aggregation", String(10), nullable=False),
    Column("grouping", JSON, nullable=False),
    Column("filters", JSON, nullable=False),
    Column("sql", Text, nullable=False),
    Column("records_analyzed", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]),
    Index("query_executions_workspace_dataset", "workspace_id", "dataset_id"),
    Index("query_executions_workspace_time", "workspace_id", "created_at"),
)


def upgrade() -> None:
    metadata.create_all(op.get_bind(), tables=[query_executions], checkfirst=False)


def downgrade() -> None:
    metadata.drop_all(op.get_bind(), tables=[query_executions], checkfirst=False)
