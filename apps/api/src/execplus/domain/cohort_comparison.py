"""Compare a selected recorded category with other rows, without causal claims.

Reuses the governed pattern projection; calculations retain exact Decimal inputs.
"""

import json
from collections import Counter
from dataclasses import replace
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID

from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.guidance import DescriptionContext
from execplus.domain.models import QueryPlan, QueryResult, WorkspaceScope
from execplus.domain.patterns import (
    MAX_ROWS,
    MIN_GROUP,
    MIN_SUPPORT,
    encoded,
    invalid,
    mean,
    numerical,
    pattern_plan,
)
from execplus.domain.patterns import (
    REQUEST_VERSION as PATTERN_REQUEST_VERSION,
)
from execplus.domain.profiling import TableData
from execplus.domain.semantics import DatasetView, MetricRequest
from execplus.domain.understanding import governed_request, preferred_aggregation

VERSION = "cohort-comparison-v1"
REQUEST_VERSION = "cohort-comparison-request-v1"
EVIDENCE_VERSION = "cohort-comparison-evidence-v1"
MAX_METRICS = 12
MAX_CATEGORIES = 3


def cohort_request(
    context: DescriptionContext,
    table: TableData,
    target_column: str,
    target_value: str,
    selected: tuple[str, ...] = (),
) -> dict[str, Any]:
    if context.state != "confirmed" or not context.view.sources[0].get("understanding_id"):
        raise ClarificationRequiredError(
            "Confirm the saved field meanings before comparing groups."
        )
    view = context.view
    definitions = {item["name"]: item for item in (context.definition or {})["columns"]}
    profiles = {item["name"]: item for item in context.profile["columns"]}
    target = view.column(target_column)
    if (
        target is None
        or target_column not in view.dimensions
        or target.type != "text"
        or definitions[target_column]["role"] != "dimension"
        or not isinstance(target_value, str)
        or not 1 <= len(target_value) <= 200
        or "\x00" in target_value
    ):
        raise ClarificationRequiredError("Choose an existing text category and its recorded value.")
    if len(selected) > MAX_METRICS or len(set(selected)) != len(selected):
        invalid("Choose up to twelve different measures for this comparison.")
    if any(name not in view.metrics for name in selected):
        raise ClarificationRequiredError("Choose numerical measures from this file.")
    index = table.headers.index(target_column)
    if not any(row[index] == target_value for row in table.rows):
        raise ClarificationRequiredError(
            "That exact category value is not recorded in your accessible data. "
            "Choose its recorded label; I will not guess a readiness or success rule."
        )
    metrics: list[str] = []
    categories: list[str] = []
    exclusions: list[dict[str, str]] = []
    units: dict[str, str] = {}
    population = None
    for name, definition in definitions.items():
        if name == target_column:
            continue
        observed = profiles[name]
        reason = ""
        if definition["role"] in {"identifier", "ignored", "ordinal"}:
            reason = "Identifiers, ignored fields and ordinal codes are not comparison measures."
        elif name in view.metrics and (not selected or name in selected):
            unit = definition["currency"] or definition["unit"]
            if observed["type_conflicts"]:
                reason = "Review inconsistent numerical values first."
            elif not unit or definition["unit_column"]:
                reason = "Confirm one fixed unit before interpreting this measure."
            elif preferred_aggregation(view, name).value != "avg" and any(
                item["column"] == name for item in (context.definition or {}).get("metrics", [])
            ):
                reason = "Its saved calculation is not an average; no average is substituted."
            elif len(metrics) >= MAX_METRICS:
                reason = (
                    "The comparison covers at most twelve measures; select this one explicitly."
                )
            else:
                try:
                    governed = governed_request(
                        view, table, MetricRequest(name, preferred_aggregation(view, name))
                    )
                except ClarificationRequiredError as error:
                    reason = str(error)
                else:
                    filters = tuple(
                        sorted(
                            governed.filters,
                            key=lambda f: (f.column, f.operator.value, str(f.value)),
                        )
                    )
                    if population is not None and filters != population:
                        reason = (
                            "Its required filters cover different rows from the other measures."
                        )
                    else:
                        population = filters
                        metrics.append(name)
                        units[name] = unit
        elif name in view.dimensions and observed["type"] == "text":
            if 2 <= observed["distinct_count"] <= 12 and len(categories) < MAX_CATEGORIES:
                categories.append(name)
            else:
                reason = (
                    "At most three additional categories with two to twelve values are compared."
                )
        if reason:
            exclusions.append(dict(column=name, reason=reason))
    chosen_exclusions = [item for item in exclusions if item["column"] in selected]
    if chosen_exclusions:
        raise ClarificationRequiredError(
            " ".join(f"{x['column']}: {x['reason']}" for x in chosen_exclusions)
        )
    return dict(
        version=REQUEST_VERSION,
        target_column=target_column,
        target_value=target_value,
        selected=list(selected),
        columns=[target_column, *metrics, *categories],
        metrics=metrics,
        categories=categories,
        units=units,
        filters=[
            dict(column=f.column, operator=f.operator.value, value=f.value)
            for f in (population or ())
        ],
        exclusions=exclusions,
    )


def cohort_plan(
    scope: WorkspaceScope, did: UUID, view: DatasetView, request: dict[str, Any]
) -> QueryPlan:
    if request["version"] != REQUEST_VERSION:
        invalid("The saved group comparison method is not supported.")
    return replace(
        pattern_plan(scope, did, view, {**request, "version": PATTERN_REQUEST_VERSION}),
        question="Compare recorded category with other rows",
    )


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def cohort_result(
    value: QueryResult, request: dict[str, Any], engine_version: str
) -> dict[str, Any]:
    if len(value.rows) > MAX_ROWS:
        invalid("This comparison is limited to 10,000 matching rows; no partial sample was used.")
    names = request["columns"]
    if tuple(names) != value.columns or any(len(row) != len(names) for row in value.rows):
        invalid("The comparison evidence does not match its declared fields.")
    ti = names.index(request["target_column"])
    target = [row for row in value.rows if row[ti] == request["target_value"]]
    others = [
        row for row in value.rows if row[ti] is not None and row[ti] != request["target_value"]
    ]
    numeric, categories = [], []
    with localcontext() as precision:
        precision.prec = 128
        for name in request["metrics"]:
            i = names.index(name)
            a = [numerical(row[i]) for row in target if row[i] is not None]
            b = [numerical(row[i]) for row in others if row[i] is not None]
            eligible = min(len(a), len(b)) >= MIN_GROUP and len(a) + len(b) >= MIN_SUPPORT
            difference = None
            score = None
            if eligible:
                am, bm = sum(a, Decimal(0)) / len(a), sum(b, Decimal(0)) / len(b)
                difference = (am - bm).quantize(Decimal("0.000000000001"))
                variance = (
                    sum(((x - am) ** 2 for x in a), Decimal(0))
                    + sum(((x - bm) ** 2 for x in b), Decimal(0))
                ) / (len(a) + len(b) - 2)
                if variance > 0:
                    score = ((am - bm) / variance.sqrt()).quantize(Decimal("0.000001"))
            numeric.append(
                dict(
                    column=name,
                    unit=request["units"][name],
                    target_count=len(a),
                    other_count=len(b),
                    target_mean=encoded(mean(a)) if eligible else None,
                    other_mean=encoded(mean(b)) if eligible else None,
                    target_median=encoded(_median(a)) if eligible else None,
                    other_median=encoded(_median(b)) if eligible else None,
                    difference=encoded(difference) if difference is not None else None,
                    standardized_difference=encoded(score) if score is not None else None,
                    status="compared" if eligible else "insufficient_data",
                )
            )
        numeric.sort(
            key=lambda x: (
                x["status"] != "compared",
                -abs(Decimal(x["standardized_difference"] or "0")),
                x["column"],
            )
        )
        for name in request["categories"]:
            i = names.index(name)
            target_counts, other_counts = (
                Counter(str(row[i]) for row in target if row[i] is not None),
                Counter(str(row[i]) for row in others if row[i] is not None),
            )
            levels = sorted(target_counts.keys() | other_counts.keys())
            categories.append(
                dict(
                    column=name,
                    target_observed=sum(target_counts.values()),
                    other_observed=sum(other_counts.values()),
                    levels=[
                        dict(
                            value=label,
                            target_count=target_counts[label],
                            other_count=other_counts[label],
                            target_share=encoded(
                                (
                                    Decimal(target_counts[label]) / sum(target_counts.values())
                                ).quantize(Decimal("0.000001"))
                            )
                            if target_counts
                            else None,
                            other_share=encoded(
                                (
                                    Decimal(other_counts[label]) / sum(other_counts.values())
                                ).quantize(Decimal("0.000001"))
                            )
                            if other_counts
                            else None,
                        )
                        for label in levels
                    ],
                )
            )
    return dict(
        version=VERSION,
        engine_version=engine_version,
        target=dict(column=request["target_column"], value=request["target_value"]),
        status="compared"
        if any(x["status"] == "compared" for x in numeric)
        else "insufficient_data",
        numeric=numeric,
        categories=categories,
        coverage=dict(
            source_rows=value.records_analyzed,
            filtered_rows=len(value.rows),
            target_rows=len(target),
            other_rows=len(others),
            missing_target_rows=len(value.rows) - len(target) - len(others),
        ),
        limitations=[
            "These are recorded group differences, not causes or proof of what "
            "changing an input will do.",
            "Other rows combine every other nonmissing target label, weighted by "
            "their actual record counts. Missing labels are separate.",
            "Measures exclude missing values separately. Means and differences use "
            "twelve decimal places; medians retain exact decimal values.",
            "At least five observed values in each group and twenty combined are "
            "needed for a numerical comparison. Repeated records may not be "
            "independent.",
            "Standardized differences divide the mean gap by pooled within-group "
            "standard deviation. They rank descriptive gaps, not significance, "
            "accuracy or causal importance; zero spread has no score.",
            "Different category mixes, measurement timing and omitted variables can "
            "reverse a pooled comparison. These results do not adjust for those "
            "differences.",
            "A label such as Harvest or Successful describes the supplied record. "
            "It does not prove present readiness, future success or treatment "
            "effectiveness.",
        ],
        exclusions=request["exclusions"],
        next_steps=[
            "Check what one row represents and whether the selected label means a "
            "current state or a later outcome.",
            "Compare similar cases within the same crop, product or other relevant "
            "category before interpreting a pooled difference.",
            "To learn what changes an outcome, collect dated before-and-after "
            "observations, the changes made, and comparable cases without the "
            "change. This snapshot alone cannot prescribe a treatment, amount or "
            "number of days.",
        ],
        suggestions=[
            f"Show records where {json.dumps(request['target_column'])} "
            f"equals {json.dumps(request['target_value'])}"
        ],
    )
