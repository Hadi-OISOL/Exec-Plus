"""Use case: Defines opt-in, deny-first access to dataset rows and columns.

What it does: Validates immutable grants, projects authorized cells and binds evidence
to the exact policy revision and audience without executing user-supplied expressions.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from execplus.domain.errors import UnsupportedQuestionError
from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import TableData
from execplus.domain.semantics import DatasetView, normalize_filter_value

ACCESS_KEYS = frozenset(
    {"access_policy_id", "access_policy_version", "access_actor_id", "access_restricted"}
)
OPERATORS = frozenset({"eq", "ne", "lt", "lte", "gt", "gte"})


@dataclass(frozen=True)
class DatasetAccessPolicy:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    version: int
    enabled: bool
    grants: list[dict[str, Any]]
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True)
class ScopedUploadMetadata:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    filename: str
    content_type: str
    status: str
    format: str
    row_count: int
    column_count: int
    created_by: UUID
    created_at: datetime
    sample_id: str | None = None
    size: None = None
    checksum: None = None
    access_limited: bool = True


@dataclass(frozen=True)
class DatasetAccess:
    actor_id: UUID
    policy: DatasetAccessPolicy | None = None
    columns: tuple[str, ...] | None = None
    conditions: tuple[dict[str, Any], ...] = ()

    @property
    def restricted(self) -> bool:
        return self.columns is not None or bool(self.conditions)

    def reference(self) -> dict[str, str]:
        if self.policy is None:
            return {}
        return {
            "access_policy_id": str(self.policy.id),
            "access_policy_version": str(self.policy.version),
            "access_actor_id": str(self.actor_id),
            "access_restricted": "true" if self.restricted else "false",
        }

    def require_full(self) -> None:
        if self.restricted:
            raise IngestionError(
                "access_restricted", "This action requires access to the complete dataset.", 403
            )


def denied() -> IngestionError:
    return IngestionError("not_found", "The requested dataset or result is unavailable.", 404)


def access_for(
    policy: DatasetAccessPolicy | None, actor_id: UUID, membership_created_at: str
) -> DatasetAccess:
    if policy is None or not policy.enabled:
        return DatasetAccess(actor_id, policy)
    grant = next((item for item in policy.grants if item.get("user_id") == str(actor_id)), None)
    if grant is None or grant.get("membership_created_at") != membership_created_at:
        raise denied()
    return DatasetAccess(
        actor_id,
        policy,
        tuple(grant["columns"]) if grant["columns"] is not None else None,
        tuple(grant["conditions"]),
    )


def validate_grants(raw: Any, view: DatasetView, members: set[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) > 50:
        raise IngestionError("access_invalid", "Choose at most fifty member grants.", 422)
    result = []
    seen = set()
    for grant in raw:
        if not isinstance(grant, dict) or set(grant) != {"user_id", "columns", "conditions"}:
            raise IngestionError("access_invalid", "Use the supported grant fields.", 422)
        user_id, columns, conditions = grant["user_id"], grant["columns"], grant["conditions"]
        if not isinstance(user_id, str) or user_id not in members or user_id in seen:
            raise IngestionError("access_invalid", "Choose each current member at most once.", 422)
        seen.add(user_id)
        if columns is not None and (
            not isinstance(columns, list)
            or not 1 <= len(columns) <= 1000
            or not all(isinstance(name, str) and view.column(name) for name in columns)
            or len(set(columns)) != len(columns)
        ):
            raise IngestionError(
                "access_invalid", "Choose existing visible columns or all columns.", 422
            )
        if not isinstance(conditions, list) or len(conditions) > 12:
            raise IngestionError("access_invalid", "Choose at most twelve row conditions.", 422)
        normalized = []
        for condition in conditions:
            if not isinstance(condition, dict) or set(condition) != {"column", "operator", "value"}:
                raise IngestionError(
                    "access_invalid", "Use a column, operator and typed value.", 422
                )
            name, operator, value = condition["column"], condition["operator"], condition["value"]
            column = view.column(name) if isinstance(name, str) else None
            if column is None or not isinstance(operator, str) or operator not in OPERATORS:
                raise IngestionError(
                    "access_invalid", "Choose an existing field and supported condition.", 422
                )
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise IngestionError(
                    "access_invalid",
                    "Use a nonempty condition value up to two hundred characters.",
                    422,
                )
            if column.type not in {"integer", "decimal", "date", "boolean", "text"}:
                raise IngestionError(
                    "access_invalid", "This field has no supported condition type.", 422
                )
            try:
                if column.type == "boolean":
                    if value not in {"true", "false"}:
                        raise UnsupportedQuestionError("Invalid boolean")
                    normalize_filter_value(column, value == "true")
                else:
                    normalize_filter_value(column, value)
            except UnsupportedQuestionError:
                raise IngestionError(
                    "access_invalid", "The condition value does not match the field type.", 422
                ) from None
            normalized.append(dict(column=name, operator=operator, value=value, type=column.type))
        result.append(dict(user_id=user_id, columns=columns, conditions=normalized))
    return result


def _matches(raw: str, condition: dict[str, Any]) -> bool:
    if not raw.strip():
        return False
    actual: Any
    expected: Any
    try:
        if condition["type"] in {"integer", "decimal"}:
            actual, expected = Decimal(raw), Decimal(condition["value"])
            if not actual.is_finite() or not expected.is_finite():
                return False
        elif condition["type"] == "date":
            actual = date.fromisoformat(raw)
            expected = date.fromisoformat(condition["value"])
        elif condition["type"] == "boolean":
            if raw.strip().lower() not in {"true", "false"}:
                return False
            actual, expected = raw.strip().lower(), condition["value"].strip().lower()
        else:
            actual, expected = raw, condition["value"]
        return bool(
            {
                "eq": lambda: actual == expected,
                "ne": lambda: actual != expected,
                "lt": lambda: actual < expected,
                "lte": lambda: actual <= expected,
                "gt": lambda: actual > expected,
                "gte": lambda: actual >= expected,
            }[condition["operator"]]()
        )
    except (ValueError, InvalidOperation, TypeError):
        return False


def project_table(table: TableData, view: DatasetView, access: DatasetAccess) -> TableData:
    if not access.restricted:
        return table
    visible = set(table.headers if access.columns is None else access.columns)
    if not visible <= set(table.headers):
        raise denied()
    for condition in access.conditions:
        column = view.column(condition["column"])
        if column is None or column.type != condition["type"]:
            raise denied()
    indices = tuple(index for index, name in enumerate(table.headers) if name in visible)
    filters = tuple((table.headers.index(item["column"]), item) for item in access.conditions)
    return TableData(
        tuple(table.headers[index] for index in indices),
        tuple(
            tuple(row[index] for index in indices)
            for row in table.rows
            if all(_matches(row[index], condition) for index, condition in filters)
        ),
    )
