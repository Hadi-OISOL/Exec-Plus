"""Use case: Defines tenant, query, execution, lineage, and answer value objects.

What it does: Enforces the data required for authorized and verifiable analytics.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TypeAlias
from uuid import UUID

Scalar: TypeAlias = str | int | float | Decimal | bool | date | datetime | None
NumericScalar: TypeAlias = int | float | Decimal


class QuestionKind(str, Enum):
    NUMERICAL = "numerical"
    ROWS = "rows"
    OVERVIEW = "overview"
    TEXTUAL = "textual"
    MIXED = "mixed"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


class ModelTier(str, Enum):
    SMALL = "small"
    LARGE = "large"


@dataclass(frozen=True, slots=True)
class WorkspaceScope:
    workspace_id: UUID
    actor_id: UUID
    roles: frozenset[str]
    allowed_dataset_ids: frozenset[UUID]

    def permits_dataset(self, dataset_id: UUID) -> bool:
        return dataset_id in self.allowed_dataset_ids


@dataclass(frozen=True, slots=True)
class QueryPlan:
    query_id: UUID
    workspace_id: UUID
    dataset_id: UUID
    question: str
    sql: str
    params: tuple[Scalar, ...] = ()


@dataclass(frozen=True, slots=True)
class QueryResult:
    query_id: UUID
    columns: tuple[str, ...]
    rows: tuple[tuple[Scalar, ...], ...]
    records_analyzed: int
    matched_records: int | None = None


@dataclass(frozen=True, slots=True)
class CalculationLineage:
    query_id: UUID
    workspace_id: UUID
    dataset_id: UUID
    dataset_name: str
    records_analyzed: int
    metric: str
    aggregation: str
    grouping: tuple[str, ...]
    filters: tuple[str, ...]
    sql: str
    model_route: str | None = None
    receipt: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VerifiedMetricAnswer:
    label: str
    value: NumericScalar
    lineage: CalculationLineage


@dataclass(frozen=True, slots=True)
class QueryExecution:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    actor_id: UUID
    dataset_name: str
    metric: str
    aggregation: str
    grouping: tuple[str, ...]
    filters: tuple[str, ...]
    sql: str
    records_analyzed: int
    created_at: datetime
    model_route: str | None = None
    receipt: dict[str, object] = field(default_factory=dict)

    def lineage(self) -> CalculationLineage:
        return CalculationLineage(
            query_id=self.id,
            workspace_id=self.workspace_id,
            dataset_id=self.dataset_id,
            dataset_name=self.dataset_name,
            records_analyzed=self.records_analyzed,
            metric=self.metric,
            aggregation=self.aggregation,
            grouping=self.grouping,
            filters=self.filters,
            sql=self.sql,
            model_route=self.model_route,
            receipt=self.receipt,
        )
