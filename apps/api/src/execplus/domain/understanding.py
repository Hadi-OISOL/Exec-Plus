"""Use case: Defines versioned, reviewable business meaning for retained data.

What it does: Infers bounded suggestions and validates human definitions without changing sources.
"""

import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.ingestion import IngestionError
from execplus.domain.profiling import TableData
from execplus.domain.semantics import (
    AggregationKind,
    DatasetView,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    build_where,
    dataset_view,
)

DOMAINS = (
    "auto",
    "sales",
    "finance",
    "inventory",
    "hr",
    "marketing",
    "operations",
    "research",
    "other",
)
STATES = ("inferred", "confirmed", "rejected", "needs_review")
ROLES = ("metric", "dimension", "identifier", "ordinal", "ignored")
GRAINS = (
    "unknown",
    "record",
    "order",
    "order_item",
    "customer",
    "inventory_snapshot",
    "survey_response",
    "other",
)
TAGS = frozenset(
    {
        "revenue",
        "sales",
        "cost",
        "amount",
        "quantity",
        "stock",
        "price",
        "headcount",
        "salary",
        "tenure",
        "turnover",
        "hires",
    }
)


@dataclass(frozen=True)
class Understanding:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    upload_id: UUID
    revision_id: UUID
    version: int
    state: str
    definition: dict[str, Any]
    created_by: UUID
    created_at: datetime


@dataclass(frozen=True)
class DataPreference:
    workspace_id: UUID
    dataset_id: UUID
    user_id: UUID
    domain_hint: str
    goal: str


def _choice(value: Any, choices: tuple[str, ...] | frozenset[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise IngestionError("invalid_definition", "Choose a supported definition value.", 422)
    return value


def _text(value: Any, limit: int) -> str:
    if not isinstance(value, str) or len(value) > limit or "\x00" in value:
        raise IngestionError("invalid_definition", "Definition text is invalid or too long.", 422)
    return value.strip()


def infer_definition(profile: dict[str, Any], domain_hint: str = "auto") -> dict[str, Any]:
    view = dataset_view(profile)
    tags = set().union(*(column.tags for column in view.columns))
    detected = (
        "sales"
        if tags & {"sales", "revenue", "price"}
        else "inventory"
        if tags & {"stock", "quantity"}
        else "hr"
        if tags & {"salary", "headcount"}
        else "other"
    )
    columns: list[dict[str, Any]] = []
    for column in view.columns:
        ordinal = bool(set(re.findall(r"[a-z]+", column.name.lower())) & {"rating", "likert"})
        role = (
            "identifier" if "identifier" in column.tags else "ordinal" if ordinal else column.role
        )
        columns.append(
            dict(
                name=column.name,
                role=role,
                meaning="",
                unit="",
                currency="",
                unit_column="",
                date_meaning="",
                timezone="",
                missing_policy="exclude",
                tags=sorted(column.tags & TAGS),
            )
        )
    order_key = next(
        (entry for entry in profile["columns"] if entry["name"].lower() in {"order_id", "orderid"}),
        None,
    )
    grain = "unknown"
    if order_key and order_key["missing"] == 0:
        grain = "order" if order_key["distinct_count"] == profile["row_count"] else "order_item"
    return dict(
        domain=detected if domain_hint == "auto" else domain_hint,
        description=(
            f"{profile['row_count']} rows and {len(columns)} columns. Review the suggested meaning."
        ),
        grain=grain,
        sensitivity="internal",
        update_mode="snapshot",
        columns=columns,
        metrics=[],
        relationships=[],
    )


def validate_definition(
    raw: dict[str, Any], table: TableData, profile: dict[str, Any], state: str
) -> dict[str, Any]:
    _choice(state, STATES)
    expected = {
        "domain",
        "description",
        "grain",
        "sensitivity",
        "update_mode",
        "columns",
        "metrics",
        "relationships",
    }
    if set(raw) != expected:
        raise IngestionError("invalid_definition", "Use the supplied definition fields.", 422)
    value: dict[str, Any] = dict(
        domain=_choice(raw["domain"], DOMAINS),
        description=_text(raw["description"], 500),
        grain=_choice(raw["grain"], GRAINS),
        sensitivity=_choice(raw["sensitivity"], ("internal", "confidential", "restricted")),
        update_mode=_choice(raw["update_mode"], ("snapshot", "append", "replace")),
        columns=[],
        metrics=[],
        relationships=[],
    )
    source = {entry["name"]: entry for entry in profile["columns"]}
    if not isinstance(raw["columns"], list) or len(raw["columns"]) != len(source):
        raise IngestionError(
            "invalid_definition", "Describe every source column exactly once.", 422
        )
    seen = set()
    column_fields = {
        "name",
        "role",
        "meaning",
        "unit",
        "currency",
        "unit_column",
        "date_meaning",
        "timezone",
        "missing_policy",
        "tags",
    }
    columns: list[dict[str, Any]] = []
    for entry in raw["columns"]:
        if not isinstance(entry, dict) or set(entry) != column_fields:
            raise IngestionError("invalid_definition", "Invalid column definition fields.", 422)
        name = _text(entry["name"], 200)
        if name not in source or name in seen:
            raise IngestionError("invalid_definition", "Use each source column exactly once.", 422)
        seen.add(name)
        role = _choice(entry["role"], ROLES)
        if role == "metric" and source[name]["type"] not in {"integer", "decimal"}:
            raise IngestionError("invalid_definition", "Only numeric columns can be metrics.", 422)
        currency = _text(entry["currency"], 3).upper()
        if currency and not re.fullmatch("[A-Z]{3}", currency):
            raise IngestionError("invalid_definition", "Use a three-letter currency code.", 422)
        unit_column = _text(entry["unit_column"], 200)
        if unit_column and (
            unit_column not in source or source[unit_column]["role"] != "dimension"
        ):
            raise IngestionError(
                "invalid_definition", "Choose a category column for per-row units.", 422
            )
        zone = _text(entry["timezone"], 80)
        if zone:
            try:
                ZoneInfo(zone)
            except (ZoneInfoNotFoundError, ValueError):
                raise IngestionError(
                    "invalid_definition", "Choose a recognized time zone.", 422
                ) from None
        tags = entry["tags"]
        if (
            not isinstance(tags, list)
            or len(tags) > len(TAGS)
            or any(not isinstance(tag, str) or tag not in TAGS for tag in tags)
        ):
            raise IngestionError("invalid_definition", "Choose supported semantic tags.", 422)
        columns.append(
            dict(
                name=name,
                role=role,
                meaning=_text(entry["meaning"], 200),
                unit=_text(entry["unit"], 40),
                currency=currency,
                unit_column=unit_column,
                date_meaning=_text(entry["date_meaning"], 100),
                timezone=zone,
                missing_policy=_choice(entry["missing_policy"], ("exclude", "needs_review")),
                tags=sorted(set(tags)),
            )
        )
    value["columns"] = columns
    if state == "confirmed" and value["grain"] == "unknown":
        raise IngestionError("invalid_definition", "Confirm what one row represents.", 422)
    if not isinstance(raw["metrics"], list) or len(raw["metrics"]) > 24:
        raise IngestionError("invalid_definition", "Use up to 24 metric definitions.", 422)
    view = apply_definition(dataset_view(profile), value)
    metrics: list[dict[str, Any]] = []
    for metric in raw["metrics"]:
        if not isinstance(metric, dict) or set(metric) != {
            "name",
            "column",
            "aggregation",
            "filters",
        }:
            raise IngestionError("invalid_definition", "Invalid metric definition fields.", 422)
        name = _text(metric["name"], 80)
        column = _text(metric["column"], 200)
        aggregation = _choice(metric["aggregation"], tuple(item.value for item in AggregationKind))
        if (
            not name
            or column not in view.metrics
            or any(
                item["name"].casefold() == name.casefold() or item["column"] == column
                for item in metrics
            )
        ):
            raise IngestionError(
                "invalid_definition",
                "Metric names and columns must be distinct and supported.",
                422,
            )
        filters = metric["filters"]
        if not isinstance(filters, list) or len(filters) > 20:
            raise IngestionError("invalid_definition", "Use up to 20 metric filters.", 422)
        clean_filters = []
        for clause in filters:
            if not isinstance(clause, dict) or set(clause) != {"column", "operator", "value"}:
                raise IngestionError("invalid_definition", "Invalid metric filter fields.", 422)
            filter_column = _text(clause["column"], 200)
            operator = _choice(clause["operator"], tuple(item.value for item in FilterOperator))
            if (
                type(clause["value"]) not in {str, int, float, bool}
                or len(str(clause["value"])) > 200
            ):
                raise IngestionError("invalid_definition", "Invalid metric filter value.", 422)
            normalized = MetricFilter(filter_column, FilterOperator(operator), clause["value"])
            build_where(view, (normalized,))
            clean_filters.append(
                dict(column=filter_column, operator=operator, value=clause["value"])
            )
        metrics.append(
            dict(name=name, column=column, aggregation=aggregation, filters=clean_filters)
        )
    value["metrics"] = metrics
    relationships = raw["relationships"]
    if not isinstance(relationships, list) or len(relationships) > 24:
        raise IngestionError("invalid_definition", "Review at most 24 relationships.", 422)
    seen_paths: set[str] = set()
    for relationship in relationships:
        if not isinstance(relationship, dict) or set(relationship) != {
            "join_path_id",
            "state",
            "cardinality",
        }:
            raise IngestionError("invalid_definition", "Invalid relationship fields.", 422)
        try:
            path_id = str(UUID(relationship["join_path_id"]))
        except (ValueError, TypeError, AttributeError) as error:
            raise IngestionError(
                "invalid_definition", "Invalid relationship identifier.", 422
            ) from error
        if path_id in seen_paths:
            raise IngestionError("invalid_definition", "Review each relationship once.", 422)
        seen_paths.add(path_id)
        value["relationships"].append(
            dict(
                join_path_id=path_id,
                state=_choice(relationship["state"], STATES),
                cardinality=_choice(relationship["cardinality"], ("many_to_one", "one_to_one")),
            )
        )
    if value["grain"] == "order" and state == "confirmed":
        order_columns = [
            item["name"] for item in columns if item["name"].lower() in {"order_id", "orderid"}
        ]
        if any(
            source[name]["missing"] or source[name]["distinct_count"] != len(table.rows)
            for name in order_columns
        ):
            raise IngestionError(
                "invalid_definition",
                "Repeated or missing order identifiers cannot establish one row per order.",
                422,
            )
    return value


def apply_definition(view: DatasetView, definition: dict[str, Any]) -> DatasetView:
    mappings = {item["name"]: item for item in definition["columns"]}
    columns = tuple(
        replace(
            column,
            role="dimension"
            if mappings[column.name]["role"] in {"identifier", "ordinal"}
            else mappings[column.name]["role"],
            tags=frozenset(mappings[column.name]["tags"])
            | (
                frozenset({"identifier"})
                if mappings[column.name]["role"] == "identifier"
                else frozenset()
            ),
        )
        for column in view.columns
    )
    return replace(
        view,
        columns=columns,
        metrics=frozenset(column.name for column in columns if column.role == "metric"),
        dimensions=frozenset(column.name for column in columns if column.role == "dimension"),
        definition=definition,
    )


def questions(definition: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    result = []
    if definition["grain"] == "unknown":
        result.append("What does one row represent?")
    elif definition["grain"] == "order_item":
        result.append("Order identifiers repeat. Is each row an order item?")
    for column in definition["columns"]:
        source = next(item for item in profile["columns"] if item["name"] == column["name"])
        if column["role"] == "metric" and not (
            column["unit"] or column["currency"] or column["unit_column"]
        ):
            result.append(f"What unit does {column['name']} measure?")
        if source["invalid_dates"]:
            result.append(
                f"Review the invalid or ambiguous dates in {column['name']} under Prepare data."
            )
    return result[:12]


def governed_request(view: DatasetView, table: TableData, request: MetricRequest) -> MetricRequest:
    definition = view.definition
    if definition:
        for metric in definition["metrics"]:
            if metric["column"] == request.metric:
                if request.aggregation.value != metric["aggregation"]:
                    raise ClarificationRequiredError(
                        "This metric has a confirmed aggregation. "
                        "Review its definition before changing the calculation."
                    )
                defaults = tuple(
                    MetricFilter(item["column"], FilterOperator(item["operator"]), item["value"])
                    for item in metric["filters"]
                )
                request = replace(
                    request, filters=tuple(dict.fromkeys((*defaults, *request.filters)))
                )
        column = next(
            (item for item in definition["columns"] if item["name"] == request.metric), None
        )
        if column and column["missing_policy"] == "needs_review":
            index = table.headers.index(request.metric)
            if any(not row[index].strip() for row in table.rows):
                raise ClarificationRequiredError(
                    "Review the missing-value policy before calculating this metric."
                )
    unit_columns = {
        column.name
        for column in view.columns
        if column.name.lower() in {"currency", "currency_code", "unit", "units", "uom"}
    }
    if definition:
        unit_columns |= {
            entry["unit_column"]
            for entry in definition["columns"]
            if entry["name"] == request.metric and entry["unit_column"]
        }
    if request.aggregation != AggregationKind.COUNT:
        for name in unit_columns:
            index = table.headers.index(name)
            values = {row[index].strip().casefold() for row in table.rows}
            constrained = any(
                item.column == name and item.operator in {FilterOperator.EQ, FilterOperator.IEQ}
                for item in request.filters
            )
            if (
                (len(values) > 1 or "" in values)
                and name not in request.group_by
                and not constrained
            ):
                raise ClarificationRequiredError(
                    f"Group or filter by {name} before combining values "
                    "with different or missing units."
                )
    return request


def preferred_aggregation(view: DatasetView, metric: str) -> AggregationKind:
    for entry in (view.definition or {}).get("metrics", []):
        if entry["column"] == metric:
            return AggregationKind(entry["aggregation"])
    return AggregationKind.SUM
