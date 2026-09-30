"""Use case: Defines the current PostgreSQL control-plane schema.

What it does: Enforces tenant ownership, references, uniqueness, and seat bounds.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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
    UniqueConstraint,
    Uuid,
)

metadata = MetaData()
users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("display_name", String(100), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
workspaces = Table(
    "workspaces",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", String(100), nullable=False),
    Column("seat_limit", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("seat_limit >= 3 AND seat_limit <= 50", name="seat_limit_bounds"),
)
memberships = Table(
    "memberships",
    metadata,
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), primary_key=True),
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("role", String(10), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("role IN ('owner', 'admin', 'member')", name="membership_role"),
    Index("memberships_user", "user_id"),
)
invitations = Table(
    "invitations",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("email", String(254), nullable=False),
    Column("role", String(10), nullable=False),
    Column("status", String(12), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("invited_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("role IN ('admin', 'member')", name="invitation_role"),
    CheckConstraint(
        "status IN ('pending', 'accepted', 'revoked', 'expired')", name="invitation_status"
    ),
    Index("invitations_workspace", "workspace_id", "status"),
)
datasets = Table(
    "datasets",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workspace_id", "id"),
)
uploads = Table(
    "uploads",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("sample_id", String(40), nullable=True),
    Column("filename", String(255), nullable=False),
    Column("content_type", String(100), nullable=False),
    Column("size", Integer, nullable=False),
    Column("storage_key", String(255), nullable=False, unique=True),
    Column("checksum", String(64), nullable=False),
    Column("status", String(12), nullable=False),
    Column("format", String(5), nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("column_count", Integer, nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]),
    CheckConstraint("size > 0 AND size <= 20971520", name="upload_size_bounds"),
    CheckConstraint("status = 'stored'", name="upload_status"),
    Index("uploads_workspace_dataset", "workspace_id", "dataset_id"),
)
audit_events = Table(
    "audit_events",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("actor_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("action", String(50), nullable=False),
    Column("resource_type", String(30), nullable=False),
    Column("resource_id", Uuid, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("audit_workspace_time", "workspace_id", "created_at"),
)

revisions = Table(
    "revisions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("upload_id", Uuid, nullable=False),
    Column("parent_id", Uuid, nullable=True),
    Column("algorithm", String(40), nullable=False),
    Column("source_checksum", String(64), nullable=False),
    Column("output_checksum", String(64), nullable=False),
    Column("recipe", JSON, nullable=False),
    Column("profile", JSON, nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workspace_id", "dataset_id", "upload_id", "id"),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id"],
        ["uploads.workspace_id", "uploads.dataset_id", "uploads.id"],
    ),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id", "parent_id"],
        ["revisions.workspace_id", "revisions.dataset_id", "revisions.upload_id", "revisions.id"],
    ),
    Index("revisions_upload", "workspace_id", "dataset_id", "upload_id"),
)
uploads.append_constraint(
    UniqueConstraint("workspace_id", "dataset_id", "id", name="uploads_tenant_id")
)
revision_heads = Table(
    "revision_heads",
    metadata,
    Column("workspace_id", Uuid, primary_key=True),
    Column("dataset_id", Uuid, primary_key=True),
    Column("upload_id", Uuid, primary_key=True),
    Column("revision_id", Uuid, nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id", "revision_id"],
        ["revisions.workspace_id", "revisions.dataset_id", "revisions.upload_id", "revisions.id"],
    ),
)

understandings = Table(
    "understandings",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("upload_id", Uuid, nullable=False),
    Column("revision_id", Uuid, nullable=False),
    Column("version", Integer, nullable=False),
    Column("state", String(20), nullable=False),
    Column("definition", JSON, nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workspace_id", "dataset_id", "version"),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id", "revision_id"],
        ["revisions.workspace_id", "revisions.dataset_id", "revisions.upload_id", "revisions.id"],
    ),
    CheckConstraint(
        "state IN ('inferred', 'confirmed', 'rejected', 'needs_review')", name="understanding_state"
    ),
    CheckConstraint("version > 0", name="understanding_version"),
)

data_preferences = Table(
    "data_preferences",
    metadata,
    Column("workspace_id", Uuid, primary_key=True),
    Column("dataset_id", Uuid, primary_key=True),
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("domain_hint", String(20), nullable=False),
    Column("goal", String(500), nullable=False),
    ForeignKeyConstraint(["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]),
)
usage_events = Table(
    "usage_events",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("actor_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("kind", String(40), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("resource_id", Uuid, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "kind IN ('upload', 'storage_bytes', 'seat_added', 'seat_removed', "
        "'seat_limit', 'profile', 'cleaning', 'restore', 'sample')",
        name="usage_kind",
    ),
    CheckConstraint("quantity >= 0", name="usage_quantity"),
    Index("usage_workspace_time", "workspace_id", "created_at"),
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
    Column("model_route", String(200), nullable=True),
    Column("receipt", JSON, nullable=False, server_default="{}"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]),
    Index("query_executions_workspace_dataset", "workspace_id", "dataset_id"),
    Index("query_executions_workspace_time", "workspace_id", "created_at"),
)
saved_items = Table(
    "saved_items",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("upload_id", Uuid, nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("kind", String(20), nullable=False),
    Column("name", String(100), nullable=False),
    Column("description", String(500), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("shared", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id"],
        ["uploads.workspace_id", "uploads.dataset_id", "uploads.id"],
    ),
    CheckConstraint(
        "kind IN ('question', 'prompt', 'dashboard', 'analysis')", name="saved_item_kind"
    ),
    Index("saved_items_workspace_upload", "workspace_id", "dataset_id", "upload_id"),
    UniqueConstraint("workspace_id", "id"),
    Index("saved_items_owner", "workspace_id", "owner_id"),
)
threads = Table(
    "threads",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("upload_id", Uuid, nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id"],
        ["uploads.workspace_id", "uploads.dataset_id", "uploads.id"],
    ),
    Index("threads_workspace_owner", "workspace_id", "owner_id"),
)
thread_turns = Table(
    "thread_turns",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("thread_id", Uuid, ForeignKey("threads.id"), nullable=False),
    Column("question", String(500), nullable=False),
    Column("kind", String(20), nullable=False),
    Column("query_id", Uuid, ForeignKey("query_executions.id"), nullable=True),
    Column("message", String(1000), nullable=True),
    Column("model_route", String(200), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("request_id", Uuid, nullable=True),
    Column("status", String(20), nullable=False, server_default="complete"),
    Column("evidence", JSON, nullable=False, server_default="{}"),
    UniqueConstraint("thread_id", "request_id", name="thread_request"),
    CheckConstraint("status IN ('running', 'complete', 'partial', 'failed')", name="thread_status"),
    CheckConstraint(
        "kind IN ('numerical', 'rows', 'overview', 'textual', 'mixed', 'ambiguous', 'unsupported')",
        name="thread_turn_kind",
    ),
    Index("thread_turns_thread_time", "thread_id", "created_at"),
)
join_paths = Table(
    "join_paths",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("left_dataset_id", Uuid, nullable=False),
    Column("left_column", String(100), nullable=False),
    Column("right_dataset_id", Uuid, nullable=False),
    Column("right_column", String(100), nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workspace_id", "left_dataset_id", "right_dataset_id", name="join_paths_pair"),
    Index("join_paths_workspace", "workspace_id"),
)

feedback = Table(
    "feedback",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("actor_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("feature", String(40), nullable=False),
    Column("rating", Integer, nullable=False),
    Column("category", String(40), nullable=False),
    Column("release", String(40), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("rating BETWEEN 1 AND 5", name="feedback_rating"),
    Index("feedback_workspace", "workspace_id"),
)

documents = Table(
    "documents",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("checksum", String(64), nullable=False),
    Column("size", Integer, nullable=False),
    Column("shared", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workspace_id", "id"),
    ForeignKeyConstraint(["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]),
    Index("documents_workspace_dataset", "workspace_id", "dataset_id"),
)

document_chunks = Table(
    "document_chunks",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("document_id", Uuid, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("start", Integer, nullable=False),
    Column("end", Integer, nullable=False),
    Column("checksum", String(64), nullable=False),
    Column("algorithm", String(40), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "document_id"],
        ["documents.workspace_id", "documents.id"],
        ondelete="CASCADE",
    ),
    UniqueConstraint("workspace_id", "document_id", "ordinal"),
)

report_schedules = Table(
    "report_schedules",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("item_id", Uuid, nullable=False),
    Column("interval_hours", Integer, nullable=False),
    Column("next_due", DateTime(timezone=True), nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "item_id"],
        ["saved_items.workspace_id", "saved_items.id"],
        ondelete="CASCADE",
    ),
    UniqueConstraint("workspace_id", "id"),
    CheckConstraint("interval_hours BETWEEN 1 AND 8760", name="report_interval"),
    Index("reports_due", "enabled", "next_due"),
)

report_deliveries = Table(
    "report_deliveries",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("schedule_id", Uuid, nullable=False),
    Column("due_at", DateTime(timezone=True), nullable=False),
    Column("status", String(40), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "schedule_id"],
        ["report_schedules.workspace_id", "report_schedules.id"],
        ondelete="CASCADE",
    ),
    UniqueConstraint("workspace_id", "schedule_id", "due_at"),
)

understandings.append_constraint(
    UniqueConstraint("workspace_id", "dataset_id", "id", name="understanding_tenant_id")
)
uploads.append_constraint(UniqueConstraint("workspace_id", "id", name="upload_workspace_id"))
organizations = Table(
    "organizations",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
departments = Table(
    "departments",
    metadata,
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), primary_key=True),
    Column("organization_id", Uuid, ForeignKey("organizations.id"), nullable=False),
    Column("name", String(100), nullable=False),
)
studies = Table(
    "studies",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("shared", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]),
    UniqueConstraint("workspace_id", "id"),
)
study_versions = Table(
    "study_versions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("study_id", Uuid, nullable=False),
    Column("number", Integer, nullable=False),
    Column("upload_id", Uuid, nullable=False),
    ForeignKeyConstraint(["workspace_id", "upload_id"], ["uploads.workspace_id", "uploads.id"]),
    Column("parent_id", Uuid, nullable=True),
    Column("question", String(500), nullable=False),
    Column("method", JSON, nullable=False),
    Column("evidence", JSON, nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(["workspace_id", "study_id"], ["studies.workspace_id", "studies.id"]),
    UniqueConstraint("workspace_id", "study_id", "id"),
    ForeignKeyConstraint(
        ["workspace_id", "study_id", "parent_id"],
        ["study_versions.workspace_id", "study_versions.study_id", "study_versions.id"],
    ),
    UniqueConstraint("workspace_id", "study_id", "number"),
    CheckConstraint("number BETWEEN 1 AND 50", name="study_version_limit"),
)
study_boards = Table(
    "study_boards",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("shared", Boolean, nullable=False),
    Column("version", Integer, nullable=False),
    Column("pins", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("json_array_length(pins) <= 6", name="six_board_pins"),
    UniqueConstraint("workspace_id", "id"),
)
view_dismissals = Table(
    "view_dismissals",
    metadata,
    Column("workspace_id", Uuid, primary_key=True),
    Column("dataset_id", Uuid, primary_key=True),
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("understanding_id", Uuid, primary_key=True),
    Column("dismissed", JSON, nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "understanding_id"],
        ["understandings.workspace_id", "understandings.dataset_id", "understandings.id"],
    ),
)

refresh_feeds = Table(
    "refresh_feeds",
    metadata,
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
    ForeignKeyConstraint(["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]),
    CheckConstraint(
        "interval_hours BETWEEN 1 AND 8760 AND freshness_hours BETWEEN 1 AND 8760",
        name="refresh_intervals",
    ),
    CheckConstraint("version >= 1", name="refresh_version"),
    Index("refresh_due", "enabled", "next_due"),
)

refresh_candidates = Table(
    "refresh_candidates",
    metadata,
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

monitors = Table(
    "monitors",
    metadata,
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

observations = Table(
    "observations",
    metadata,
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
    ForeignKeyConstraint(["workspace_id", "monitor_id"], ["monitors.workspace_id", "monitors.id"]),
    UniqueConstraint("workspace_id", "monitor_id", "source_version"),
    Index("observation_jobs", "status", "created_at"),
)

alert_rules = Table(
    "alert_rules",
    metadata,
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
    ForeignKeyConstraint(["workspace_id", "monitor_id"], ["monitors.workspace_id", "monitors.id"]),
    CheckConstraint("cooldown_minutes BETWEEN 1 AND 10080", name="alert_cooldown"),
)

alert_events = Table(
    "alert_events",
    metadata,
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
