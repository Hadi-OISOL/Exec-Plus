"""Use case: Builds governed evidence queries for registered decision-analysis methods.

What it does: Validates confirmed units, population filters and bounded complete result projections.
"""

from typing import Any
from uuid import UUID, uuid4

from execplus.domain.decision_analysis import METHODS, fail
from execplus.domain.large_allocation import is_large_allocation
from execplus.domain.large_allocation_queries import large_allocation_plan
from execplus.domain.models import QueryPlan, WorkspaceScope
from execplus.domain.multivariate_anomalies import is_multivariate
from execplus.domain.multivariate_queries import multivariate_plan
from execplus.domain.profiling import TableData
from execplus.domain.scenarios import METHOD as SCENARIO_METHOD
from execplus.domain.semantics import (
    DatasetView,
    MetricFilter,
    build_where,
    quote_identifier,
    validate_read_only,
)
from execplus.domain.source_scenarios import is_source_scenario, source_scenario_plan
from execplus.domain.studies import count_plan, method_request, validated_method
from execplus.domain.understanding import governed_request, preferred_aggregation


def analysis_plan(
    scope: WorkspaceScope, did: UUID, view: DatasetView, table: TableData, raw: dict[str, Any]
) -> tuple[QueryPlan, dict[str, str]]:
    kind = raw["kind"]
    if is_multivariate(raw):
        return multivariate_plan(scope, did, view, table, raw)
    if is_large_allocation(raw):
        return large_allocation_plan(scope, did, view, table, raw)
    if kind == "scenario_comparison" and is_source_scenario(raw):
        return source_scenario_plan(scope, did, view, table, raw)
    if kind not in {**METHODS, "scenario_comparison": SCENARIO_METHOD}:
        fail("unsupported_analysis", "Choose a registered analysis method.")
    names = (
        [raw["metric"]]
        if kind in {"robust_distribution", "scenario_comparison"}
        else [raw["cost_column"], raw["benefit_column"]]
    )
    if kind == "bounded_allocation" and raw.get("resource_column"):
        names.append(raw["resource_column"])
    units = {}
    clauses: list[MetricFilter] = []
    for name in names:
        method = validated_method(
            dict(
                kind="metric",
                column=name,
                aggregation=raw["aggregation"]
                if kind == "scenario_comparison"
                else preferred_aggregation(view, name).value,
                filters=raw["filters"],
                group_by=[],
                order=[],
            ),
            view,
        )
        request = governed_request(view, table, method_request(method))
        clauses.extend(request.filters)
        meaning = next(item for item in (view.definition or {})["columns"] if item["name"] == name)
        unit = meaning["currency"] or meaning["unit"]
        if not unit or meaning["unit_column"]:
            fail("fixed_unit_required", "Confirm a fixed unit for every analysis measure.")
        units[name] = unit
    combined = tuple(dict.fromkeys(clauses))
    if len(combined) > 20:
        fail("analysis_filter_limit", "Use at most 20 total governed filters.")
    where, parameters = build_where(view, combined)
    if kind == "scenario_comparison":
        if raw["aggregation"] not in {"sum", "avg"}:
            fail("invalid_scenario", "Scenarios support eligible sums and averages only.")
        metric = quote_identifier(raw["metric"])
        sql = f'SELECT {raw["aggregation"].upper()}({metric}) AS "__baseline" FROM "dataset"'
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " LIMIT 1"
    elif kind == "robust_distribution":
        metric = quote_identifier(raw["metric"])
        fields = metric
        if raw.get("segment_column"):
            segment = raw["segment_column"]
            meaning = next(
                (c for c in (view.definition or {}).get("columns", []) if c["name"] == segment),
                None,
            )
            if (
                not meaning
                or meaning["role"] not in {"dimension", "identifier"}
                or segment == raw["metric"]
            ):
                fail("invalid_segment", "Choose a separate confirmed group or identifier column.")
            fields = f"{quote_identifier(segment)}, {metric}"
        sql = f'SELECT {fields}, COUNT(?) AS "__frequency" FROM "dataset"'
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" GROUP BY {fields} ORDER BY {fields} LIMIT 1001"
        parameters = [1, *parameters]
    else:
        entity = raw["entity_column"]
        meaning = next(
            (item for item in (view.definition or {}).get("columns", []) if item["name"] == entity),
            None,
        )
        if not meaning or meaning["role"] not in {"identifier", "dimension"}:
            fail(
                "candidate_identity_required",
                "Choose a confirmed candidate identifier or category.",
            )
        if len(set([entity, *names])) != len(names) + 1:
            fail(
                "distinct_columns_required",
                "Candidate, cost, benefit and resource columns must differ.",
            )
        fields = ", ".join(quote_identifier(name) for name in [entity, *names])
        sql = f'SELECT {fields} FROM "dataset"'
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {quote_identifier(entity)} LIMIT 21"
    validate_read_only(sql)
    return QueryPlan(
        uuid4(), scope.workspace_id, did, "Registered decision analysis", sql, tuple(parameters)
    ), units


def scenario_coverage_plans(
    scope: WorkspaceScope, did: UUID, view: DatasetView, table: TableData, raw: dict[str, Any]
) -> list[QueryPlan]:
    method = validated_method(
        dict(
            kind="metric",
            column=raw["metric"],
            aggregation=raw["aggregation"],
            filters=raw["filters"],
            group_by=[],
            order=[],
        ),
        view,
    )
    request = governed_request(view, table, method_request(method))
    return [
        count_plan(scope, did, view, request, present_only=True),
        count_plan(scope, did, view, request, present_only=False),
    ]
