"""Use case: Defines reproducible studies and bounded adaptive workspace views.

What it does: Selects supported components and validates descriptive study methods.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from execplus.domain.errors import UnsupportedQuestionError
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryPlan, WorkspaceScope
from execplus.domain.semantics import (
    AggregationKind,
    DatasetView,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    build_where,
    quote_identifier,
    validate_read_only,
)
from execplus.domain.understanding import preferred_aggregation


@dataclass(frozen=True)
class Organization:
    id: UUID
    owner_id: UUID
    name: str
    created_at: datetime


@dataclass(frozen=True)
class Department:
    workspace_id: UUID
    organization_id: UUID
    name: str


@dataclass(frozen=True)
class Study:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    owner_id: UUID
    name: str
    shared: bool
    created_at: datetime


@dataclass(frozen=True)
class StudyVersion:
    id: UUID
    workspace_id: UUID
    study_id: UUID
    number: int
    upload_id: UUID
    parent_id: UUID | None
    question: str
    method: dict[str, Any]
    evidence: dict[str, Any]
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True)
class StudyBoard:
    id: UUID
    workspace_id: UUID
    owner_id: UUID
    name: str
    shared: bool
    version: int
    pins: list[str]
    created_at: datetime


@dataclass(frozen=True)
class ViewDismissals:
    workspace_id: UUID
    dataset_id: UUID
    user_id: UUID
    understanding_id: UUID
    dismissed: list[str]


def validated_method(raw: dict[str, Any], view: DatasetView) -> dict[str, Any]:
    if set(raw) - {"kind", "column", "aggregation", "group_by", "filters", "order"}:
        raise IngestionError("invalid_method", "Unsupported study method fields.", 422)
    kind = raw.get("kind")
    column = raw.get("column")
    groups = raw.get("group_by", [])
    order = raw.get("order", [])
    filters = raw.get("filters", [])
    if (
        not isinstance(kind, str)
        or kind not in {"metric", "distribution", "missingness"}
        or not isinstance(column, str)
    ):
        raise IngestionError("invalid_method", "Choose a supported descriptive method.", 422)
    definition = view.definition
    meaning = next(
        (item for item in (definition or {}).get("columns", []) if item["name"] == column), None
    )
    if not definition or meaning is None or meaning["role"] in {"ignored", "identifier"}:
        raise UnsupportedQuestionError("Choose a confirmed measure or category, not an identifier")
    if (
        not isinstance(groups, list)
        or len(groups) > 1
        or any(not isinstance(name, str) or name not in view.dimensions for name in groups)
        or column in groups
    ):
        raise IngestionError("invalid_method", "Choose at most one different category.", 422)
    for group in groups:
        group_meaning = next(item for item in definition["columns"] if item["name"] == group)
        if group_meaning["role"] in {"identifier", "ignored"}:
            raise UnsupportedQuestionError("Identifiers cannot define descriptive groups")
    if (
        not isinstance(order, list)
        or len(order) > 30
        or any(not isinstance(value, str) or not value or len(value) > 200 for value in order)
        or len(set(order)) != len(order)
        or (order and kind != "distribution")
    ):
        raise IngestionError("invalid_method", "Use up to 30 distinct ordered categories.", 422)
    if kind == "distribution":
        if column not in view.dimensions:
            raise UnsupportedQuestionError("Distribution requires a confirmed category")
        if meaning["role"] == "ordinal" and not order:
            raise IngestionError(
                "category_order_required", "Declare the response order first.", 422
            )
    aggregation = raw.get("aggregation", "count")
    if not isinstance(aggregation, str) or aggregation not in {
        item.value for item in AggregationKind
    }:
        raise IngestionError("invalid_method", "Unsupported aggregation.", 422)
    if kind == "metric" and column not in view.metrics:
        raise UnsupportedQuestionError("This column is not a confirmed numeric measure")
    if kind == "metric" and not (meaning["unit"] or meaning["currency"] or meaning["unit_column"]):
        raise IngestionError(
            "unit_required", "Confirm this measure's unit before running a study.", 422
        )
    if kind != "metric" and aggregation != "count":
        raise IngestionError("invalid_method", "Descriptive counts require count aggregation.", 422)
    if not isinstance(filters, list) or len(filters) > 20:
        raise IngestionError("invalid_method", "Use at most 20 filters.", 422)
    for clause in filters:
        if (
            not isinstance(clause, dict)
            or set(clause) != {"column", "operator", "value"}
            or not isinstance(clause["column"], str)
            or not isinstance(clause["operator"], str)
            or clause["operator"] not in {item.value for item in FilterOperator}
            or type(clause["value"]) not in {str, int, float, bool}
            or len(str(clause["value"])) > 200
        ):
            raise IngestionError("invalid_method", "Invalid study filter.", 422)
    method = dict(
        kind=kind,
        column=column,
        aggregation=aggregation,
        group_by=groups,
        filters=filters,
        order=order,
    )
    build_where(view, method_request(method).filters)
    return method


def method_request(method: dict[str, Any]) -> MetricRequest:
    return MetricRequest(
        method["column"],
        AggregationKind(method["aggregation"]),
        tuple(method["group_by"]),
        tuple(
            MetricFilter(item["column"], FilterOperator(item["operator"]), item["value"])
            for item in method["filters"]
        ),
    )


def count_plan(
    scope: WorkspaceScope,
    dataset_id: UUID,
    view: DatasetView,
    request: MetricRequest,
    *,
    present_only: bool,
    distribution: bool = False,
) -> QueryPlan:
    column = quote_identifier(request.metric)
    groups = (*request.group_by, request.metric) if distribution else request.group_by
    select = [quote_identifier(name) for name in groups]
    select.append(f'COUNT({column if present_only else "?"}) AS "__value"')
    clauses, parameters = build_where(view, request.filters)
    sql = f'SELECT {", ".join(select)} FROM "dataset"'
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    if groups:
        names = ", ".join(quote_identifier(name) for name in groups)
        sql += f" GROUP BY {names} ORDER BY {names}"
    sql += " LIMIT 1001"
    validate_read_only(sql)
    return QueryPlan(
        uuid4(),
        scope.workspace_id,
        dataset_id,
        "Descriptive sample count",
        sql,
        tuple(parameters) if present_only else (1, *parameters),
    )


def recommendations(view: DatasetView, goal: str) -> list[dict[str, Any]]:
    definition = view.definition
    if not definition:
        return []
    words = set(re.findall(r"[a-z0-9]+", goal.lower()))
    domain_tags = {
        "sales": {"sales", "revenue", "price"},
        "finance": {"revenue", "cost", "amount"},
        "inventory": {"stock", "quantity", "price"},
        "operations": {"quantity", "cost"},
        "research": set(),
    }.get(definition["domain"], set())
    columns = {item["name"]: item for item in definition["columns"]}
    groups = [
        column.name
        for column in view.columns
        if column.name in view.dimensions and columns[column.name]["role"] == "dimension"
    ]
    dates = [name for name in groups if (column := view.column(name)) and column.type == "date"]
    categories = [name for name in groups if name not in dates]
    choices: list[dict[str, Any]] = []
    for column in view.columns:
        meaning = columns[column.name]
        if meaning["role"] in {"ignored", "identifier"}:
            continue
        overlap = words & set(
            re.findall(
                r"[a-z0-9]+", " ".join([column.name, meaning["meaning"], *meaning["tags"]]).lower()
            )
        )
        reason = f"Confirmed {definition['domain']} {meaning['role']}: {column.name}."
        if overlap:
            reason += " Matches your private goal."
        methods: list[tuple[str, dict[str, Any], str]] = []
        base = dict(column=column.name, filters=[], group_by=[], order=[])
        if meaning["role"] == "metric":
            if not (meaning["unit"] or meaning["currency"] or meaning["unit_column"]):
                continue
            aggregation = preferred_aggregation(view, column.name).value
            method = dict(base, kind="metric", aggregation=aggregation)
            methods.append(("card", method, f"What is the {aggregation} of {column.name}?"))
            for component, dimensions in (("line", dates), ("bar", categories)):
                if dimensions:
                    group = next(
                        (name for name in dimensions if name.lower() in words), dimensions[0]
                    )
                    methods.append(
                        (
                            component,
                            dict(method, group_by=[group]),
                            f"How does {column.name} vary by {group}?",
                        )
                    )
        elif meaning["role"] == "dimension" and column.type != "date":
            methods.append(
                (
                    "distribution",
                    dict(base, kind="distribution", aggregation="count"),
                    f"How are records distributed across {column.name}?",
                )
            )
        methods.append(
            (
                "table",
                dict(base, kind="missingness", aggregation="count"),
                f"How many {column.name} values are missing?",
            )
        )
        for component, method, question in methods:
            identity = hashlib.sha256(json.dumps(method, sort_keys=True).encode()).hexdigest()[:20]
            choices.append(
                dict(
                    id=identity,
                    component=component,
                    method=method,
                    question=question,
                    reason=reason,
                    rank=len(overlap) * 20
                    + len(set(meaning["tags"]) & domain_tags) * 5
                    + (
                        5
                        if definition["domain"] == "research"
                        and component in {"distribution", "table"}
                        else 0
                    )
                    + (component != "table"),
                )
            )
    return sorted(choices, key=lambda item: (-item["rank"], item["id"]))[:12]
