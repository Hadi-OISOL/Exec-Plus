"""Use case: Defines the current PostgreSQL control-plane schema.

What it does: Enforces tenant ownership, references, uniqueness, and seat bounds.
"""

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
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
google_connections = Table(
    "google_connections",
    metadata,
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("google_email", String(254), nullable=False),
    Column("scope", Text, nullable=False),
    Column("refresh_token_encrypted", Text, nullable=False),
    Column("version", Uuid, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
connector_connections = Table(
    "connector_connections",
    metadata,
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("provider", String(40), primary_key=True),
    Column("display_name", String(200), nullable=False),
    Column("sealed_credentials", Text, nullable=False),
    Column("version", Uuid, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
# Provider subjects are independent self-service principals, never email aliases of operators.
external_identities = Table(
    "external_identities",
    metadata,
    Column("provider", String(40), primary_key=True),
    Column("subject", String(255), primary_key=True),
    Column("user_id", Uuid, ForeignKey("users.id"), nullable=False, unique=True),
    Column("disabled_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
oauth_attempts = Table(
    "oauth_attempts",
    metadata,
    Column("state_hash", String(64), primary_key=True),
    Column("browser_hash", String(64), nullable=False),
    Column("provider", String(40), nullable=False),
    Column("purpose", String(12), nullable=False),
    Column("user_id", Uuid, ForeignKey("users.id")),
    Column("session_hash", String(64)),
    Column("connection_version", Uuid),
    Column("sealed_payload", Text, nullable=False),
    Column("status", String(12), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("handoff_hash", String(64), unique=True),
    Column("handoff_expires_at", DateTime(timezone=True)),
    Column("error_code", String(80)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("purpose IN ('signin', 'connect')", name="oauth_attempt_purpose"),
    CheckConstraint(
        "status IN ('pending', 'claimed', 'complete', 'consumed', 'revoked')",
        name="oauth_attempt_status",
    ),
    Index("oauth_attempt_actor", "user_id", "provider"),
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
agent_memories = Table(
    "agent_memories",
    metadata,
    Column("workspace_id", Uuid, primary_key=True),
    Column("user_id", Uuid, primary_key=True),
    Column("version", Integer, nullable=False),
    Column("role", String(300), nullable=False),
    Column("focus", String(500), nullable=False),
    Column("explanation_style", String(20), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "user_id"],
        ["memberships.workspace_id", "memberships.user_id"],
        ondelete="CASCADE",
    ),
    CheckConstraint("version > 0", name="agent_memory_version"),
    CheckConstraint("explanation_style IN ('concise', 'step_by_step')", name="agent_memory_style"),
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
local_accounts = Table(
    "local_accounts",
    metadata,
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("password_hash", String(256), nullable=False),
    Column("password_changed_at", DateTime(timezone=True), nullable=False),
    Column("disabled_at", DateTime(timezone=True)),
)
account_events = Table(
    "account_events",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Uuid, ForeignKey("users.id")),
    Column("action", String(40), nullable=False),
    Column("reason", String(80), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("account_events_private", "user_id", "created_at"),
)
account_rate_windows = Table(
    "account_rate_windows",
    metadata,
    Column("key_hash", String(64), primary_key=True),
    Column("window_start", DateTime(timezone=True), primary_key=True),
    Column("used", Integer, nullable=False),
    CheckConstraint("used BETWEEN 1 AND 60", name="account_auth_rate_bounds"),
)
invitation_identity_approvals = Table(
    "invitation_identity_approvals",
    metadata,
    Column(
        "invitation_id", Uuid, ForeignKey("invitations.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("user_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("approved_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("approved_at", DateTime(timezone=True), nullable=False),
)
onboarding_progress = Table(
    "onboarding_progress",
    metadata,
    Column("workspace_id", Uuid, primary_key=True),
    Column("user_id", Uuid, primary_key=True),
    Column("version", Integer, nullable=False),
    Column("active_step", String(20), nullable=False),
    Column("skipped_steps", JSON, nullable=False),
    Column("paused", Boolean, nullable=False),
    Column("finished", Boolean, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "user_id"],
        ["memberships.workspace_id", "memberships.user_id"],
        ondelete="CASCADE",
    ),
    CheckConstraint("version > 0", name="onboarding_progress_version"),
    CheckConstraint(
        "active_step IN ('setup', 'data', 'quality', 'meaning', 'analysis', "
        "'dashboard', 'recommendations', 'team')",
        name="onboarding_progress_step",
    ),
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
dataset_access_policies = Table(
    "dataset_access_policies",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("version", Integer, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("grants", JSON, nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]),
    UniqueConstraint("workspace_id", "dataset_id", "version"),
    CheckConstraint("version > 0", name="dataset_access_version"),
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
    UniqueConstraint(
        "workspace_id",
        "dataset_id",
        "upload_id",
        "revision_id",
        "id",
        name="understandings_source_identity",
    ),
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
    Column("job_id", Uuid, nullable=True),
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

threads.append_constraint(UniqueConstraint("workspace_id", "id", name="threads_tenant_id"))
thread_turns.append_constraint(UniqueConstraint("thread_id", "id", name="thread_turns_thread_id"))
jobs = Table(
    "jobs",
    metadata,
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
    ForeignKeyConstraint(["thread_id", "turn_id"], ["thread_turns.thread_id", "thread_turns.id"]),
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
        "priority BETWEEN 0 AND 10 AND event_sequence BETWEEN 0 AND 200", name="job_priority_events"
    ),
)
job_attempts = Table(
    "job_attempts",
    metadata,
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
job_events = Table(
    "job_events",
    metadata,
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

thread_turns.append_constraint(
    ForeignKeyConstraint(
        ["thread_id", "id", "job_id"],
        ["jobs.thread_id", "jobs.turn_id", "jobs.id"],
        name="thread_turn_job",
        use_alter=True,
    )
)
Index("jobs_due", jobs.c.status, jobs.c.priority, jobs.c.created_at)
Index("jobs_leases", jobs.c.status, jobs.c.lease_expires_at)

forecast_runs = Table(
    "forecast_runs",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("upload_id", Uuid, nullable=False),
    Column("revision_id", Uuid, nullable=False),
    Column("understanding_id", Uuid, nullable=False),
    Column("method", String(40), nullable=False),
    Column("method_version", String(40), nullable=False),
    Column("request", JSON, nullable=False),
    Column("evidence", JSON, nullable=False),
    Column("result", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "workspace_id", "dataset_id", "owner_id", "id", name="forecast_run_owner_identity"
    ),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id", "revision_id"],
        ["revisions.workspace_id", "revisions.dataset_id", "revisions.upload_id", "revisions.id"],
        name="forecast_run_revision",
    ),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id", "revision_id", "understanding_id"],
        [
            "understandings.workspace_id",
            "understandings.dataset_id",
            "understandings.upload_id",
            "understandings.revision_id",
            "understandings.id",
        ],
        name="forecast_run_understanding",
    ),
    Index("forecast_runs_owner", "workspace_id", "dataset_id", "owner_id", "created_at"),
)
forecast_comparisons = Table(
    "forecast_comparisons",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("forecast_id", Uuid, nullable=False),
    Column("upload_id", Uuid, nullable=False),
    Column("revision_id", Uuid, nullable=False),
    Column("understanding_id", Uuid, nullable=False),
    Column("evidence", JSON, nullable=False),
    Column("result", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "owner_id", "forecast_id"],
        [
            "forecast_runs.workspace_id",
            "forecast_runs.dataset_id",
            "forecast_runs.owner_id",
            "forecast_runs.id",
        ],
        name="forecast_comparison_run",
    ),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id", "revision_id"],
        ["revisions.workspace_id", "revisions.dataset_id", "revisions.upload_id", "revisions.id"],
        name="forecast_comparison_revision",
    ),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id", "revision_id", "understanding_id"],
        [
            "understandings.workspace_id",
            "understandings.dataset_id",
            "understandings.upload_id",
            "understandings.revision_id",
            "understandings.id",
        ],
        name="forecast_comparison_understanding",
    ),
    Index("forecast_comparisons_owner", "workspace_id", "forecast_id", "owner_id", "created_at"),
)

feedback.append_constraint(
    UniqueConstraint("workspace_id", "actor_id", "id", name="feedback_support_owner")
)
jobs.append_constraint(
    UniqueConstraint("workspace_id", "owner_id", "id", name="jobs_support_owner")
)

staff_grants = Table(
    "staff_grants",
    metadata,
    Column("user_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("role", String(10), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("role IN ('admin','support')", name="staff_role"),
)
staff_audit = Table(
    "staff_audit",
    metadata,
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
    Index("staff_audit_time", "created_at", "id"),
)
support_tickets = Table(
    "support_tickets",
    metadata,
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
        "status IN ('open','triaged','in_progress','waiting_on_customer','escalated','resolved')",
        name="support_status",
    ),
    CheckConstraint("priority IN ('normal','high')", name="support_priority"),
    CheckConstraint("version BETWEEN 1 AND 200", name="support_version"),
    CheckConstraint("(status = 'resolved') = (resolved_at IS NOT NULL)", name="support_resolved"),
    Index("support_requester_time", "workspace_id", "requester_id", "created_at", "id"),
    Index("support_queue_time", "status", "created_at", "id"),
)
support_events = Table(
    "support_events",
    metadata,
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

analysis_runs = Table(
    "analysis_runs",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("upload_id", Uuid, nullable=False),
    Column("revision_id", Uuid, nullable=False),
    Column("understanding_id", Uuid, nullable=False),
    Column("name", String(100), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("method_version", String(40), nullable=False),
    Column("request", JSON, nullable=False),
    Column("evidence", JSON, nullable=False),
    Column("result", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workspace_id", "owner_id", "id", name="analysis_run_owner"),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id", "revision_id"],
        ["revisions.workspace_id", "revisions.dataset_id", "revisions.upload_id", "revisions.id"],
        name="analysis_revision",
    ),
    ForeignKeyConstraint(
        ["workspace_id", "dataset_id", "upload_id", "revision_id", "understanding_id"],
        [
            "understandings.workspace_id",
            "understandings.dataset_id",
            "understandings.upload_id",
            "understandings.revision_id",
            "understandings.id",
        ],
        name="analysis_understanding",
    ),
    CheckConstraint(
        "kind IN ('robust_distribution','bounded_allocation','scenario_comparison')",
        name="analysis_kind",
    ),
    Index("analysis_owner_time", "workspace_id", "dataset_id", "owner_id", "created_at"),
)
analysis_reviews = Table(
    "analysis_reviews",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("run_id", Uuid, nullable=False),
    Column("owner_id", Uuid, nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("target", String(32), nullable=False),
    Column("status", String(24), nullable=False),
    Column("note", String(1000), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "owner_id", "run_id"],
        ["analysis_runs.workspace_id", "analysis_runs.owner_id", "analysis_runs.id"],
        name="analysis_review_owner",
    ),
    UniqueConstraint("workspace_id", "run_id", "sequence", name="analysis_review_sequence"),
    CheckConstraint("sequence BETWEEN 1 AND 200", name="analysis_review_limit"),
    CheckConstraint(
        "status IN ('pending','approved','rejected','expected',"
        "'investigate','data_issue','dismissed')",
        name="analysis_review_status",
    ),
)

request_metric_batches = Table(
    "request_metric_batches",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("request_metric_batch_retention", "created_at"),
)
request_metrics = Table(
    "request_metrics",
    metadata,
    Column("minute", DateTime(timezone=True), primary_key=True),
    Column("category", String(16), primary_key=True),
    Column("requests", BigInteger, nullable=False),
    Column("rejected", BigInteger, nullable=False),
    Column("failed", BigInteger, nullable=False),
    Column("response_start_ms", BigInteger, nullable=False),
    Column("maximum_response_start_ms", BigInteger, nullable=False),
    CheckConstraint(
        "category IN ('ingestion','exports','analysis','queue','other')",
        name="request_metric_category",
    ),
    CheckConstraint(
        "requests > 0 AND rejected >= 0 AND failed >= 0 AND rejected + failed <= requests "
        "AND response_start_ms >= maximum_response_start_ms AND maximum_response_start_ms >= 0",
        name="request_metric_counts",
    ),
)
incident_alert_policies = Table(
    "incident_alert_policies",
    metadata,
    Column("category", String(16), primary_key=True),
    Column("version", BigInteger, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("window_minutes", Integer, nullable=False),
    Column("minimum_requests", Integer, nullable=False),
    Column("minimum_failures", Integer, nullable=False),
    Column("failure_basis_points", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("updated_by", Uuid, ForeignKey("users.id"), nullable=False),
    CheckConstraint(
        "category IN ('ingestion','exports','analysis','queue','other')",
        name="incident_alert_category",
    ),
    CheckConstraint(
        "version > 0 AND window_minutes BETWEEN 1 AND 60 "
        "AND minimum_requests BETWEEN 1 AND 1000000 AND minimum_failures BETWEEN 1 AND 1000000 "
        "AND failure_basis_points BETWEEN 0 AND 10000",
        name="incident_alert_bounds",
    ),
)

incidents = Table(
    "incidents",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("code", String(40), nullable=False, unique=True),
    Column("component", String(20), nullable=False),
    Column("severity", String(12), nullable=False),
    Column("status", String(16), nullable=False),
    Column("version", BigInteger, nullable=False),
    Column("occurrences", BigInteger, nullable=False),
    Column("first_seen", DateTime(timezone=True), nullable=False),
    Column("last_seen", DateTime(timezone=True), nullable=False),
    Column("acknowledged_at", DateTime(timezone=True), nullable=True),
    Column("resolved_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("status IN ('open','acknowledged','resolved')", name="incident_status"),
    CheckConstraint("severity IN ('warning','error')", name="incident_severity"),
    CheckConstraint("version > 0 AND occurrences > 0", name="incident_counts"),
    CheckConstraint(
        "component IN ('api','jobs','refresh','reports','collector')", name="incident_component"
    ),
    CheckConstraint(
        "code IN ('http_failed','job_failed','job_timeout','job_interrupted','job_expired',"
        "'refresh_failed','report_failed','queue_overflow','collector_recovered','retention_capacity',"
        "'ingestion_failed','export_failed','queue_failed')",
        name="incident_code",
    ),
)
incident_occurrences = Table(
    "incident_occurrences",
    metadata,
    Column("source_kind", String(16), primary_key=True),
    Column("source_id", Uuid, primary_key=True),
    Column("occurred_at", DateTime(timezone=True), primary_key=True),
    Column("code", String(40), nullable=True),
    CheckConstraint(
        "source_kind IN ('http','job','refresh','report','collector')", name="incident_source_kind"
    ),
    Index("incident_occurrence_retention", "occurred_at"),
    Index("incident_occurrence_code", "code", "occurred_at"),
)
Index(
    "incident_failed_jobs",
    jobs.c.updated_at,
    jobs.c.id,
    postgresql_where=jobs.c.status.in_(("failed", "expired")),
)
Index(
    "incident_failed_reports",
    report_deliveries.c.created_at,
    report_deliveries.c.id,
    postgresql_where=report_deliveries.c.status == "failed",
)
Index(
    "incident_failed_refresh",
    audit_events.c.created_at,
    audit_events.c.id,
    postgresql_where=audit_events.c.action == "refresh.activation_failed",
)

usage_prices = Table(
    "usage_prices",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("provider", String(160), nullable=False),
    Column("model", String(160), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("definition", JSON, nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("provider", "model", "created_at", name="usage_price_version"),
)
usage_policies = Table(
    "usage_policies",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("ends_at", DateTime(timezone=True), nullable=False),
    Column("definition", JSON, nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    UniqueConstraint("workspace_id", "version", name="usage_policy_version"),
    UniqueConstraint("workspace_id", "id", name="usage_policy_workspace"),
    CheckConstraint("version > 0 AND ends_at > starts_at", name="usage_policy_window"),
)
usage_attempts = Table(
    "usage_attempts",
    metadata,
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), primary_key=True),
    Column("id", Uuid, primary_key=True),
    Column("actor_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("operation_id", Uuid, nullable=False),
    Column("operation", String(24), nullable=False),
    Column("provider", String(160), nullable=False),
    Column("model", String(160), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("policy_id", Uuid, nullable=True),
    Column("price_id", Uuid, ForeignKey("usage_prices.id"), nullable=True),
    Column("currency", String(3), nullable=True),
    Column("state", String(16), nullable=False),
    Column("version", Integer, nullable=False),
    Column("held_exposure", Numeric(40, 18), nullable=False),
    Column("cost", Numeric(40, 18), nullable=True),
    Column("outcome", String(24), nullable=True),
    Column("usage", JSON, nullable=False),
    Column("cost_basis", String(32), nullable=True),
    Column("evidence_ref", String(160), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    ForeignKeyConstraint(
        ["workspace_id", "policy_id"],
        ["usage_policies.workspace_id", "usage_policies.id"],
        name="usage_attempt_policy_workspace",
    ),
    CheckConstraint(
        "state IN ('reserved','started','settled','unknown','released')", name="usage_attempt_state"
    ),
    CheckConstraint(
        "version > 0 AND held_exposure >= 0 AND (cost IS NULL OR cost >= 0)",
        name="usage_attempt_amounts",
    ),
    CheckConstraint(
        "operation IN ('conversation','data_reading','document_answer','summary')",
        name="usage_attempt_operation",
    ),
    Index("usage_attempt_window", "workspace_id", "created_at"),
    Index("usage_attempt_active", "workspace_id", "state"),
)
model_usage_events = Table(
    "model_usage_events",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("attempt_id", Uuid, nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("actor_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("snapshot", JSON, nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "attempt_id"],
        ["usage_attempts.workspace_id", "usage_attempts.id"],
        name="usage_event_attempt_workspace",
    ),
    UniqueConstraint("workspace_id", "attempt_id", "sequence", name="usage_event_sequence"),
    CheckConstraint("sequence > 0", name="usage_event_sequence_positive"),
)

integration_keys = Table(
    "integration_keys",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("membership_created_at", DateTime(timezone=True), nullable=False),
    Column("name", String(100), nullable=False),
    Column("token_hash", String(64), unique=True, nullable=False),
    Column("dataset_ids", JSON, nullable=False),
    Column("operations", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    Column("last_used_at", DateTime(timezone=True)),
    Column("rate_limit", Integer, nullable=False),
    CheckConstraint("rate_limit BETWEEN 1 AND 60", name="integration_key_rate"),
    CheckConstraint("expires_at > created_at", name="integration_key_expiry"),
    Index("integration_keys_actor", "workspace_id", "user_id"),
)
integration_request_windows = Table(
    "integration_request_windows",
    metadata,
    Column("key_id", Uuid, ForeignKey("integration_keys.id", ondelete="CASCADE"), primary_key=True),
    Column("window_start", DateTime(timezone=True), primary_key=True),
    Column("used", Integer, nullable=False),
    CheckConstraint("used BETWEEN 1 AND 60", name="integration_request_count"),
)
embed_grants = Table(
    "embed_grants",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("membership_created_at", DateTime(timezone=True), nullable=False),
    Column("board_id", Uuid, ForeignKey("study_boards.id", ondelete="CASCADE"), nullable=False),
    Column("board_version", Integer, nullable=False),
    Column("host_origin", String(300), nullable=False),
    Column("bootstrap_hash", String(64), unique=True, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("consumed_at", DateTime(timezone=True)),
    Column("session_hash", String(64), unique=True),
    Column("session_expires_at", DateTime(timezone=True)),
    Column("revoked_at", DateTime(timezone=True)),
    CheckConstraint("board_version > 0 AND expires_at > created_at", name="embed_grant_bounds"),
    CheckConstraint(
        "(session_hash IS NULL) = (session_expires_at IS NULL)", name="embed_session_pair"
    ),
    Index("embed_grants_actor", "workspace_id", "user_id"),
)
webhook_subscriptions = Table(
    "webhook_subscriptions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("membership_created_at", DateTime(timezone=True), nullable=False),
    Column("dataset_ids", JSON, nullable=False),
    Column("event_types", JSON, nullable=False),
    Column("destination", String(2000), nullable=False),
    Column("signing_version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    CheckConstraint("signing_version > 0", name="webhook_signing_version"),
    Index("webhook_subscriptions_actor", "workspace_id", "user_id"),
)
webhook_deliveries = Table(
    "webhook_deliveries",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "subscription_id",
        Uuid,
        ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("kind", String(32), nullable=False),
    Column("resource_id", Uuid, nullable=False),
    Column("dataset_id", Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("status", String(20), nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("next_attempt_at", DateTime(timezone=True), nullable=False),
    Column("last_status", Integer),
    Column("last_attempt_at", DateTime(timezone=True)),
    Column("lease_until", DateTime(timezone=True)),
    Column("lease_id", Uuid),
    UniqueConstraint("subscription_id", "kind", "resource_id", name="webhook_event_identity"),
    CheckConstraint(
        "kind IN ('job.succeeded','job.failed','refresh.accepted')", name="webhook_event_kind"
    ),
    CheckConstraint(
        "status IN ('pending','sending','delivered','failed','cancelled')",
        name="webhook_delivery_state",
    ),
    CheckConstraint("attempts BETWEEN 0 AND 6", name="webhook_attempt_bound"),
    CheckConstraint(
        "last_status IS NULL OR last_status BETWEEN 100 AND 599", name="webhook_http_status"
    ),
    Index("webhook_deliveries_due", "status", "next_attempt_at"),
)

registered_sources = Table(
    "registered_sources",
    metadata,
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), primary_key=True),
    Column("id", Uuid, primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("configuration", JSON, nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("version > 0", name="registered_source_version"),
)
source_imports = Table(
    "source_imports",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, nullable=False),
    Column("actor_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("membership_created_at", DateTime(timezone=True), nullable=False),
    Column("request_id", Uuid, nullable=False),
    Column("source_id", Uuid, nullable=False),
    Column("source_version", Integer, nullable=False),
    Column("dataset_id", Uuid, nullable=False),
    Column("selection", JSON, nullable=False),
    Column("access_reference", JSON, nullable=False),
    Column("status", String(12), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    Column("upload_id", Uuid),
    Column("candidate_id", Uuid),
    Column("snapshot", JSON),
    Column("failure_code", String(40)),
    ForeignKeyConstraint(
        ["workspace_id", "source_id", "source_version"],
        ["registered_sources.workspace_id", "registered_sources.id", "registered_sources.version"],
    ),
    ForeignKeyConstraint(["workspace_id", "dataset_id"], ["datasets.workspace_id", "datasets.id"]),
    ForeignKeyConstraint(["workspace_id", "upload_id"], ["uploads.workspace_id", "uploads.id"]),
    ForeignKeyConstraint(
        ["workspace_id", "candidate_id"],
        ["refresh_candidates.workspace_id", "refresh_candidates.id"],
    ),
    UniqueConstraint("workspace_id", "actor_id", "request_id"),
    CheckConstraint(
        "status IN ('extracting','imported','staged','failed')", name="source_import_status"
    ),
    CheckConstraint(
        "(status = 'extracting') = (completed_at IS NULL)", name="source_import_completion"
    ),
    CheckConstraint(
        "completed_at IS NULL OR completed_at >= created_at", name="source_import_order"
    ),
    Index("source_import_history", "workspace_id", "actor_id", "dataset_id", "created_at"),
)

consolidation_runs = Table(
    "consolidation_runs",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("organization_id", Uuid, ForeignKey("organizations.id"), nullable=False),
    Column("owner_id", Uuid, ForeignKey("users.id"), nullable=False),
    Column("name", String(100), nullable=False),
    Column("request", JSON, nullable=False),
    Column("evidence", JSON, nullable=False),
    Column("result", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("consolidation_private_history", "organization_id", "owner_id", "created_at"),
)

plan_catalog = Table(
    "plan_catalog",
    metadata,
    Column("key", String(40), primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("name", String(100), nullable=False),
    Column("limits", JSON, nullable=False),
    Column("created_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("version > 0", name="plan_catalog_version"),
)
workspace_plans = Table(
    "workspace_plans",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("plan_key", String(40), nullable=False),
    Column("plan_version", Integer, nullable=False),
    Column("limits", JSON, nullable=False),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("ends_at", DateTime(timezone=True), nullable=False),
    Column("assigned_by", Uuid, ForeignKey("users.id"), nullable=False),
    Column("basis", String(24), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workspace_id", "version", name="workspace_plan_version"),
    UniqueConstraint("workspace_id", "id", name="workspace_plan_scope"),
    CheckConstraint("version > 0 AND ends_at > starts_at", name="workspace_plan_period"),
    CheckConstraint("basis IN ('native_default','administrator')", name="workspace_plan_basis"),
)
plan_admissions = Table(
    "plan_admissions",
    metadata,
    Column("workspace_id", Uuid, ForeignKey("workspaces.id"), primary_key=True),
    Column("actor_id", Uuid, ForeignKey("users.id"), primary_key=True),
    Column("kind", String(24), primary_key=True),
    Column("request_id", Uuid, primary_key=True),
    Column("input_hash", String(64), nullable=False),
    Column("assignment_id", Uuid),
    Column("quantity", BigInteger, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["workspace_id", "assignment_id"], ["workspace_plans.workspace_id", "workspace_plans.id"]
    ),
    CheckConstraint("quantity > 0", name="plan_admission_quantity"),
    CheckConstraint(
        "kind IN ('processing','exports','forecasts','model_attempts')", name="plan_admission_kind"
    ),
    Index("plan_admission_window", "workspace_id", "kind", "created_at"),
)
