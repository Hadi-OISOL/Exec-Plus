"""Use case: Projects complete authorized records for explicit multivariate cohorts.

What it does: Requires matching measure populations, confirmed identifiers, text
groups and fixed units, and retains a cap-plus-one refusal instead of truncation.
"""

from typing import Any
from uuid import UUID, uuid4

from execplus.domain.decision_analysis import fail
from execplus.domain.models import QueryPlan, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import DatasetView, build_where, quote_identifier, validate_read_only
from execplus.domain.studies import method_request, validated_method
from execplus.domain.understanding import governed_request, preferred_aggregation


def multivariate_plan(
    scope: WorkspaceScope, did: UUID, view: DatasetView, table: TableData, raw: dict[str, Any]
) -> tuple[QueryPlan, dict[str, str]]:
    metrics = raw["metrics"]
    names = [raw["identifier_column"], raw["cohort_column"], *metrics]
    if not 2 <= len(metrics) <= 4 or len(set(names)) != len(names):
        fail(
            "multivariate_columns", "Choose a separate identifier, group and two to four measures."
        )
    meanings = {c["name"]: c for c in (view.definition or {}).get("columns", [])}
    identifier, cohort = meanings.get(names[0]), meanings.get(names[1])
    if (
        not identifier
        or identifier["role"] != "identifier"
        or not cohort
        or cohort["role"] != "dimension"
    ):
        fail("multivariate_roles", "Confirm a record identifier and a separate group field first.")
    units, populations = {}, []
    for metric in metrics:
        method = validated_method(
            dict(
                kind="metric",
                column=metric,
                aggregation=preferred_aggregation(view, metric).value,
                filters=raw["filters"],
                group_by=[],
                order=[],
            ),
            view,
        )
        request = governed_request(view, table, method_request(method))
        populations.append(frozenset(request.filters))
        meaning = meanings[metric]
        unit = meaning["currency"] or meaning["unit"]
        if not unit or meaning["unit_column"]:
            fail("fixed_unit_required", "Confirm one fixed unit for every selected measure.")
        units[metric] = unit
    if any(population != populations[0] for population in populations[1:]):
        fail(
            "multivariate_population", "All measures must use the same confirmed required filters."
        )
    if raw["reference_label"] == raw["comparison_label"]:
        fail("multivariate_cohorts", "Choose different reference and comparison groups.")
    where, parameters = build_where(view, tuple(sorted(populations[0], key=repr)))
    group = quote_identifier(names[1])
    where.append(f"{group} IN (?, ?)")
    parameters.extend([raw["reference_label"], raw["comparison_label"]])
    fields = ", ".join(map(quote_identifier, names))
    sql = f'SELECT {fields} FROM "dataset" WHERE ' + " AND ".join(where)
    sql += f" ORDER BY {quote_identifier(names[0])} LIMIT 1001"
    validate_read_only(sql)
    return QueryPlan(
        uuid4(), scope.workspace_id, did, "Private multivariate evidence", sql, tuple(parameters)
    ), units
