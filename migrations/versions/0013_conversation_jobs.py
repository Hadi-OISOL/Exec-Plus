"""Use case: Adds durable private conversation work without replacing legacy turns.

What it does: Stores bounded leases, attempts and activity with tenant-constrained references.
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

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("threads_tenant_id", "threads", ["workspace_id", "id"])
    op.create_unique_constraint("thread_turns_thread_id", "thread_turns", ["thread_id", "id"])
    op.create_table(
        "jobs",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
        Column("thread_id", Uuid, nullable=False),
        Column("turn_id", Uuid, nullable=False),
        Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("request_id", Uuid, nullable=False),
        Column("payload_hash", String(64), nullable=False),
        Column("status", String(20), nullable=False),
        Column("priority", Integer, nullable=False),
        Column("attempts", Integer, nullable=False),
        Column("max_attempts", Integer, nullable=False),
        Column("budget", JSON, nullable=False),
        Column("sources", JSON, nullable=False),
        Column("plan", JSON, nullable=False),
        Column("result_refs", JSON, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        Column("expires_at", DateTime(timezone=True), nullable=False),
        Column("lease_id", Uuid, nullable=True),
        Column("lease_expires_at", DateTime(timezone=True), nullable=True),
        Column("cancel_requested", Boolean, nullable=False),
        Column("failure_code", String(40), nullable=True),
        Column("current_stage", String(40), nullable=True),
        Column("event_sequence", Integer, nullable=False),
        UniqueConstraint("workspace_id", "id", name="jobs_tenant_id"),
        UniqueConstraint("thread_id", "turn_id", "id", name="jobs_thread_id"),
        UniqueConstraint("workspace_id", "thread_id", "request_id", name="jobs_request"),
        UniqueConstraint("turn_id", name="jobs_one_turn"),
        ForeignKeyConstraint(["workspace_id", "thread_id"], ["threads.workspace_id", "threads.id"]),
        ForeignKeyConstraint(
            ["thread_id", "turn_id"], ["thread_turns.thread_id", "thread_turns.id"]
        ),
        CheckConstraint(
            "status IN ('queued','claimed','running','cancelling',"
            "'succeeded','failed','cancelled','expired')",
            name="job_state",
        ),
        CheckConstraint(
            "attempts >= 0 AND attempts <= max_attempts AND max_attempts BETWEEN 1 AND 3",
            name="job_attempt_bounds",
        ),
        CheckConstraint(
            "priority BETWEEN 0 AND 10 AND event_sequence BETWEEN 0 AND 200",
            name="job_priority_events",
        ),
    )
    op.create_table(
        "job_attempts",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, nullable=False),
        Column("job_id", Uuid, nullable=False),
        Column("number", Integer, nullable=False),
        Column("status", String(20), nullable=False),
        Column("started_at", DateTime(timezone=True), nullable=False),
        Column("heartbeat_at", DateTime(timezone=True), nullable=False),
        Column("lease_expires_at", DateTime(timezone=True), nullable=False),
        Column("finished_at", DateTime(timezone=True), nullable=True),
        Column("failure_code", String(40), nullable=True),
        ForeignKeyConstraint(["workspace_id", "job_id"], ["jobs.workspace_id", "jobs.id"]),
        UniqueConstraint("workspace_id", "job_id", "number", name="job_attempt_number"),
        CheckConstraint("number BETWEEN 1 AND 3", name="job_attempt_number_bounds"),
    )
    op.create_table(
        "job_events",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, nullable=False),
        Column("job_id", Uuid, nullable=False),
        Column("sequence", Integer, nullable=False),
        Column("stage", String(40), nullable=False),
        Column("status", String(20), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        ForeignKeyConstraint(["workspace_id", "job_id"], ["jobs.workspace_id", "jobs.id"]),
        UniqueConstraint("workspace_id", "job_id", "sequence", name="job_event_sequence"),
        CheckConstraint("sequence BETWEEN 1 AND 200", name="job_event_bounds"),
        CheckConstraint(
            "stage IN ('queued','authorizing','checking_source','planning',"
            "'validating_plan','executing_query','retrieving_documents',"
            "'verifying_evidence','finished')",
            name="job_event_stage",
        ),
        CheckConstraint(
            "status IN ('started','completed','failed','cancelled')", name="job_event_status"
        ),
    )
    op.add_column("thread_turns", Column("job_id", Uuid, nullable=True))
    op.create_foreign_key(
        "thread_turn_job",
        "thread_turns",
        "jobs",
        ["thread_id", "id", "job_id"],
        ["thread_id", "turn_id", "id"],
    )
    op.create_index("jobs_due", "jobs", ["status", "priority", "created_at"])
    op.create_index("jobs_leases", "jobs", ["status", "lease_expires_at"])


def downgrade() -> None:
    op.drop_constraint("thread_turn_job", "thread_turns", type_="foreignkey")
    op.drop_column("thread_turns", "job_id")
    for table in ("job_events", "job_attempts", "jobs"):
        op.drop_table(table)
    op.drop_constraint("thread_turns_thread_id", "thread_turns", type_="unique")
    op.drop_constraint("threads_tenant_id", "threads", type_="unique")
