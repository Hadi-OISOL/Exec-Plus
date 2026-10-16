"""Use case: Adds bounded redacted internal incident monitoring.

What it does: Preserves existing control-plane records, indexes durable failures
and refuses downgrade while incident evidence remains.
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("component", sa.String(20), nullable=False),
        sa.Column("severity", sa.String(12), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("occurrences", sa.BigInteger(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('open','acknowledged','resolved')", name="incident_status"),
        sa.CheckConstraint("severity IN ('warning','error')", name="incident_severity"),
        sa.CheckConstraint("version > 0 AND occurrences > 0", name="incident_counts"),
        sa.CheckConstraint(
            "component IN ('api','jobs','refresh','reports','collector')", name="incident_component"
        ),
        sa.CheckConstraint(
            "code IN ('http_failed','job_failed','job_timeout','job_interrupted','job_expired',"
            "'refresh_failed','report_failed','queue_overflow','collector_recovered',"
            "'retention_capacity')",
            name="incident_code",
        ),
    )
    op.create_table(
        "incident_occurrences",
        sa.Column("source_kind", sa.String(16), primary_key=True),
        sa.Column("source_id", sa.Uuid(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), primary_key=True),
        sa.CheckConstraint(
            "source_kind IN ('http','job','refresh','report','collector')",
            name="incident_source_kind",
        ),
    )
    op.create_index("incident_occurrence_retention", "incident_occurrences", ["occurred_at"])
    op.create_index(
        "incident_failed_jobs",
        "jobs",
        ["updated_at", "id"],
        postgresql_where=sa.text("status IN ('failed','expired')"),
    )
    op.create_index(
        "incident_failed_reports",
        "report_deliveries",
        ["created_at", "id"],
        postgresql_where=sa.text("status = 'failed'"),
    )
    op.create_index(
        "incident_failed_refresh",
        "audit_events",
        ["created_at", "id"],
        postgresql_where=sa.text("action = 'refresh.activation_failed'"),
    )


def downgrade() -> None:
    count = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT (SELECT COUNT(*) FROM incidents) "
                "+ (SELECT COUNT(*) FROM incident_occurrences)"
            )
        )
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            "Preserve internal incident evidence before downgrading; "
            "no incident is deleted automatically."
        )
    op.drop_index("incident_failed_refresh", table_name="audit_events")
    op.drop_index("incident_failed_reports", table_name="report_deliveries")
    op.drop_index("incident_failed_jobs", table_name="jobs")
    op.drop_index("incident_occurrence_retention", table_name="incident_occurrences")
    op.drop_table("incident_occurrences")
    op.drop_table("incidents")
