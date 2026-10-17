"""Use case: Adds fixed-category request counts and local operational alert thresholds.

What it does: Retains incident history, gives new occurrences opaque correlation
references, and refuses to discard collected metrics or administrator settings.
"""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

OLD_CODES = (
    "'http_failed','job_failed','job_timeout','job_interrupted','job_expired',"
    "'refresh_failed','report_failed','queue_overflow','collector_recovered','retention_capacity'"
)
NEW_CODES = "'ingestion_failed','export_failed','queue_failed'"
CATEGORIES = "category IN ('ingestion','exports','analysis','queue','other')"


def upgrade() -> None:
    op.create_table(
        "request_metric_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("request_metric_batch_retention", "request_metric_batches", ["created_at"])
    op.create_table(
        "request_metrics",
        sa.Column("minute", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("category", sa.String(16), primary_key=True),
        *(
            sa.Column(name, sa.BigInteger(), nullable=False)
            for name in (
                "requests",
                "rejected",
                "failed",
                "response_start_ms",
                "maximum_response_start_ms",
            )
        ),
        sa.CheckConstraint(CATEGORIES, name="request_metric_category"),
        sa.CheckConstraint(
            "requests > 0 AND rejected >= 0 AND failed >= 0 AND rejected + failed <= requests "
            "AND response_start_ms >= maximum_response_start_ms AND maximum_response_start_ms >= 0",
            name="request_metric_counts",
        ),
    )
    op.create_table(
        "incident_alert_policies",
        sa.Column("category", sa.String(16), primary_key=True),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *(
            sa.Column(name, sa.Integer(), nullable=False)
            for name in (
                "window_minutes",
                "minimum_requests",
                "minimum_failures",
                "failure_basis_points",
            )
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint(CATEGORIES, name="incident_alert_category"),
        sa.CheckConstraint(
            "version > 0 AND window_minutes BETWEEN 1 AND 60 "
            "AND minimum_requests BETWEEN 1 AND 1000000 AND minimum_failures BETWEEN 1 AND 1000000 "
            "AND failure_basis_points BETWEEN 0 AND 10000",
            name="incident_alert_bounds",
        ),
    )
    op.add_column("incident_occurrences", sa.Column("code", sa.String(40), nullable=True))
    op.create_index("incident_occurrence_code", "incident_occurrences", ["code", "occurred_at"])
    op.drop_constraint("incident_code", "incidents", type_="check")
    op.create_check_constraint("incident_code", "incidents", f"code IN ({OLD_CODES},{NEW_CODES})")


def downgrade() -> None:
    retained = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT (SELECT COUNT(*) FROM request_metrics) + "
                "(SELECT COUNT(*) FROM request_metric_batches) + "
                "(SELECT COUNT(*) FROM incident_alert_policies) + "
                "(SELECT COUNT(*) FROM incident_occurrences WHERE code IS NOT NULL) + "
                f"(SELECT COUNT(*) FROM incidents WHERE code IN ({NEW_CODES}))"
            )
        )
        .scalar_one()
    )
    if retained:
        raise RuntimeError(
            "Preserve operational metrics and correlation evidence before downgrading."
        )
    op.drop_constraint("incident_code", "incidents", type_="check")
    op.create_check_constraint("incident_code", "incidents", f"code IN ({OLD_CODES})")
    op.drop_index("incident_occurrence_code", table_name="incident_occurrences")
    op.drop_column("incident_occurrences", "code")
    op.drop_table("incident_alert_policies")
    op.drop_table("request_metrics")
    op.drop_index("request_metric_batch_retention", table_name="request_metric_batches")
    op.drop_table("request_metric_batches")
