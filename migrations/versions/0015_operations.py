"""Use case: Adds revocable platform staff and private customer support workflows.

What it does: Preserves prior data and constrains ticket ownership, timelines and operator audit.
"""

from alembic import op
from sqlalchemy import (
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

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "feedback_support_owner", "feedback", ["workspace_id", "actor_id", "id"]
    )
    op.create_unique_constraint("jobs_support_owner", "jobs", ["workspace_id", "owner_id", "id"])
    op.create_table(
        "staff_grants",
        Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
        Column("role", String(10), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        Column("revoked_at", DateTime(timezone=True), nullable=True),
        CheckConstraint("role IN ('admin','support')", name="staff_role"),
    )
    op.create_table(
        "staff_audit",
        Column("id", Uuid, primary_key=True),
        Column("actor_id", Uuid, ForeignKey("users.id"), nullable=True),
        Column("action", String(64), nullable=False),
        Column("origin", String(20), nullable=False),
        Column("outcome", String(10), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=True),
        Column("resource_id", Uuid, nullable=True),
        CheckConstraint("origin IN ('api','operator_cli')", name="staff_audit_origin"),
        CheckConstraint("outcome IN ('success','denied')", name="staff_audit_outcome"),
    )
    op.create_table(
        "support_tickets",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
        Column("requester_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("subject", String(120), nullable=False),
        Column("description", String(4000), nullable=False),
        Column("feature", String(40), nullable=False),
        Column("category", String(40), nullable=False),
        Column("status", String(24), nullable=False),
        Column("priority", String(10), nullable=False),
        Column("version", Integer, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        Column("assignee_id", Uuid, ForeignKey("staff_grants.user_id"), nullable=True),
        Column("feedback_id", Uuid, nullable=True),
        Column("job_id", Uuid, nullable=True),
        Column("resolved_at", DateTime(timezone=True), nullable=True),
        UniqueConstraint("workspace_id", "id", name="support_ticket_tenant"),
        ForeignKeyConstraint(
            ["workspace_id", "requester_id", "feedback_id"],
            ["feedback.workspace_id", "feedback.actor_id", "feedback.id"],
            name="support_feedback_owner",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "requester_id", "job_id"],
            ["jobs.workspace_id", "jobs.owner_id", "jobs.id"],
            name="support_job_owner",
        ),
        CheckConstraint(
            "status IN ('open','triaged','in_progress','waiting_on_customer',"
            "'escalated','resolved')",
            name="support_status",
        ),
        CheckConstraint("priority IN ('normal','high')", name="support_priority"),
        CheckConstraint("version BETWEEN 1 AND 200", name="support_version"),
        CheckConstraint(
            "(status = 'resolved') = (resolved_at IS NOT NULL)", name="support_resolved"
        ),
    )
    op.create_table(
        "support_events",
        Column("id", Uuid, primary_key=True),
        Column("workspace_id", Uuid, nullable=False),
        Column("ticket_id", Uuid, nullable=False),
        Column("sequence", Integer, nullable=False),
        Column("actor_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("actor_role", String(10), nullable=False),
        Column("kind", String(15), nullable=False),
        Column("body", String(4000), nullable=False),
        Column("status", String(24), nullable=False),
        Column("priority", String(10), nullable=False),
        Column("assignee_id", Uuid, ForeignKey("staff_grants.user_id"), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        ForeignKeyConstraint(
            ["workspace_id", "ticket_id"],
            ["support_tickets.workspace_id", "support_tickets.id"],
            name="support_event_tenant",
        ),
        UniqueConstraint("workspace_id", "ticket_id", "sequence", name="support_event_sequence"),
        CheckConstraint("sequence BETWEEN 1 AND 200", name="support_event_bound"),
        CheckConstraint("actor_role IN ('requester','staff')", name="support_event_role"),
        CheckConstraint(
            "kind IN ('created','message','updated','reopened')", name="support_event_kind"
        ),
    )
    op.create_index("staff_audit_time", "staff_audit", ["created_at", "id"])
    op.create_index(
        "support_requester_time",
        "support_tickets",
        ["workspace_id", "requester_id", "created_at", "id"],
    )
    op.create_index("support_queue_time", "support_tickets", ["status", "created_at", "id"])


def downgrade() -> None:
    op.drop_table("support_events")
    op.drop_table("support_tickets")
    op.drop_table("staff_audit")
    op.drop_table("staff_grants")
    op.drop_constraint("jobs_support_owner", "jobs", type_="unique")
    op.drop_constraint("feedback_support_owner", "feedback", type_="unique")
