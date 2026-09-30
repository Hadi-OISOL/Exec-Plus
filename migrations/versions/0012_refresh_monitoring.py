"""Use case: Adds durable staged refresh, observation jobs and private KPI alerts.

What it does: Preserves all existing snapshots and adds tenant-constrained Phase 4B metadata.
"""

from alembic import op
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_feeds",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
        Column("dataset_id", Uuid, nullable=False),
        Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("version", Integer, nullable=False),
        Column("source", JSON, nullable=False),
        Column("interval_hours", Integer, nullable=False),
        Column("freshness_hours", Integer, nullable=False),
        Column("enabled", Boolean, nullable=False),
        Column("next_due", DateTime(timezone=True), nullable=False),
        Column("last_checked_at", DateTime(timezone=True), nullable=True),
        Column("state", String(40), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("workspace_id", "dataset_id"),
        ForeignKeyConstraint(
            ["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]
        ),
        CheckConstraint(
            "interval_hours BETWEEN 1 AND 8760 AND freshness_hours BETWEEN 1 AND 8760",
            name="refresh_intervals",
        ),
        CheckConstraint("version >= 1", name="refresh_version"),
    )
    op.create_index("refresh_due", "refresh_feeds", ["enabled", "next_due"])
    op.create_table(
        "refresh_candidates",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
        Column("feed_id", Uuid, nullable=False),
        Column("request_id", Uuid, nullable=False),
        Column("signature", String(64), nullable=False),
        Column("base_version", Integer, nullable=False),
        Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
        Column("status", String(40), nullable=False),
        Column("details", JSON, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(
            ["workspace_id", "feed_id"], ["refresh_feeds.workspace_id", "refresh_feeds.id"]
        ),
        UniqueConstraint("workspace_id", "feed_id", "request_id"),
    )
    op.create_table(
        "monitors",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
        Column("feed_id", Uuid, nullable=False),
        Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("name", String(100), nullable=False),
        Column("method", JSON, nullable=False),
        Column("relevance", Integer, nullable=False),
        Column("enabled", Boolean, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(
            ["workspace_id", "feed_id"], ["refresh_feeds.workspace_id", "refresh_feeds.id"]
        ),
        CheckConstraint("relevance BETWEEN 1 AND 5", name="monitor_relevance"),
    )
    op.create_table(
        "observations",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
        Column("monitor_id", Uuid, nullable=False),
        Column("source_version", Integer, nullable=False),
        Column("source", JSON, nullable=False),
        Column("status", String(40), nullable=False),
        Column("attempts", Integer, nullable=False),
        Column("claimed_at", DateTime(timezone=True), nullable=True),
        Column("claim_id", Uuid, nullable=True),
        Column("evidence", JSON, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(
            ["workspace_id", "monitor_id"], ["monitors.workspace_id", "monitors.id"]
        ),
        UniqueConstraint("workspace_id", "monitor_id", "source_version"),
    )
    op.create_index("observation_jobs", "observations", ["status", "created_at"])
    op.create_table(
        "alert_rules",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
        Column("monitor_id", Uuid, nullable=False),
        Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("operator", String(5), nullable=False),
        Column("threshold", String(100), nullable=False),
        Column("cooldown_minutes", Integer, nullable=False),
        Column("enabled", Boolean, nullable=False),
        Column("last_delivered_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(
            ["workspace_id", "monitor_id"], ["monitors.workspace_id", "monitors.id"]
        ),
        CheckConstraint("cooldown_minutes BETWEEN 1 AND 10080", name="alert_cooldown"),
    )
    op.create_table(
        "alert_events",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
        Column("rule_id", Uuid, nullable=False),
        Column("observation_id", Uuid, nullable=False),
        Column("status", String(40), nullable=False),
        Column("read_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        UniqueConstraint("workspace_id", "id"),
        ForeignKeyConstraint(
            ["workspace_id", "rule_id"], ["alert_rules.workspace_id", "alert_rules.id"]
        ),
        ForeignKeyConstraint(
            ["workspace_id", "observation_id"], ["observations.workspace_id", "observations.id"]
        ),
        UniqueConstraint("workspace_id", "rule_id", "observation_id"),
    )


def downgrade() -> None:
    for name in (
        "alert_events",
        "alert_rules",
        "observations",
        "monitors",
        "refresh_candidates",
        "refresh_feeds",
    ):
        op.drop_table(name)
