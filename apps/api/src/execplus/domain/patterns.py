"""Use case: Defines bounded measured patterns over a governed complete snapshot.

What it does: Selects eligible fields and describes associations with support and uncertainty.
"""

import math
from collections import Counter, defaultdict
from collections.abc import Callable
from decimal import Decimal, localcontext
from itertools import combinations
from typing import Any
from uuid import UUID, uuid4

from execplus.domain.decision_analysis import checksum
from execplus.domain.errors import ClarificationRequiredError
from execplus.domain.guidance import DescriptionContext
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryPlan, QueryResult, Scalar, WorkspaceScope
from execplus.domain.profiling import TableData
from execplus.domain.semantics import (
    DatasetView,
    MetricFilter,
    MetricRequest,
    build_where,
    quote_identifier,
    validate_read_only,
)
from execplus.domain.understanding import governed_request, preferred_aggregation

VERSION = "pattern-exploration-v1"
REQUEST_VERSION = "pattern-request-v1"
MAX_ROWS = 10_000
MAX_METRICS = 8
MAX_CATEGORIES = 4
MIN_SUPPORT = 20
MIN_GROUP = 5
MAX_CATEGORIES_PER_COLUMN = 12
MAX_FINDINGS = 6

Correlation = Callable[
    [tuple[float, ...], tuple[float, ...], tuple[float, ...], tuple[float, ...]],
    tuple[float | None, float] | None,
]
Association = Callable[[tuple[tuple[int, ...], ...]], float | None]


def invalid(message: str) -> None:
    raise IngestionError("pattern_input", message, 422)


def pattern_request(
    context: DescriptionContext, table: TableData, selected: tuple[str, ...] = ()
) -> dict[str, Any]:
    if context.state != "confirmed" or not context.view.sources[0].get("understanding_id"):
        raise ClarificationRequiredError(
            "Confirm what the data fields mean before finding patterns."
        )
    if len(selected) > MAX_METRICS + MAX_CATEGORIES or len(set(selected)) != len(selected):
        invalid("Choose up to twelve different fields for pattern exploration.")
    definitions = {item["name"]: item for item in (context.definition or {})["columns"]}
    profile = {item["name"]: item for item in context.profile["columns"]}
    if any(name not in definitions for name in selected):
        invalid("Choose fields that exist in this file.")
    candidates = (
        (list(selected) + [name for name in definitions if name not in selected])
        if len(selected) == 1
        else list(selected)
        if selected
        else list(definitions)
    )
    metrics: list[str] = []
    categories: list[str] = []
    exclusions: list[dict[str, str]] = []
    units: dict[str, str] = {}
    populations: dict[str, tuple[MetricFilter, ...]] = {}
    for name in candidates:
        column, observed = definitions[name], profile[name]
        reason = ""
        if column["role"] in {"identifier", "ignored"}:
            reason = "Identifiers and ignored fields do not describe useful associations."
        elif observed["type_conflicts"]:
            reason = "Correct inconsistent values before calculating patterns."
        elif observed["distinct_count"] <= 1:
            reason = "This field has fewer than two distinct observed values."
        elif name in context.view.metrics:
            unit = column["currency"] or column["unit"]
            if not unit or column["unit_column"]:
                reason = "Confirm one fixed unit for this measure first."
            elif len(metrics) >= MAX_METRICS:
                reason = (
                    "This scan is limited to eight measures; choose this field in a focused scan."
                )
            else:
                try:
                    request = governed_request(
                        context.view,
                        table,
                        MetricRequest(name, preferred_aggregation(context.view, name)),
                    )
                except ClarificationRequiredError as error:
                    reason = str(error)
                else:
                    metrics.append(name)
                    units[name] = unit
                    populations[name] = tuple(
                        sorted(
                            request.filters,
                            key=lambda item: (item.column, item.operator.value, str(item.value)),
                        )
                    )
        elif name in context.view.dimensions and observed["type"] != "date":
            if observed["distinct_count"] > MAX_CATEGORIES_PER_COLUMN:
                reason = "This field has more than twelve categories; use a focused breakdown."
            elif observed["distinct_count"] > max(2, context.profile["row_count"] // MIN_GROUP):
                reason = "There are too few rows per category for a useful comparison."
            elif len(categories) >= MAX_CATEGORIES:
                reason = (
                    "This scan is limited to four categories; choose this field in a focused scan."
                )
            else:
                categories.append(name)
        else:
            reason = "This scan compares numerical measures and small category groups, not dates."
        if reason:
            exclusions.append(dict(column=name, reason=reason))
    selected_exclusions = [item for item in exclusions if item["column"] in selected]
    if selected_exclusions:
        raise ClarificationRequiredError(
            " ".join(f"{item['column']}: {item['reason']}" for item in selected_exclusions)
        )
    if metrics:
        population_counts = Counter(populations[name] for name in metrics)
        common = (
            populations[selected[0]]
            if len(selected) == 1 and selected[0] in populations
            else max(population_counts, key=lambda population: population_counts[population])
        )
        mismatched = [name for name in metrics if populations[name] != common]
        if mismatched and len(selected) > 1:
            raise ClarificationRequiredError(
                "These measures use different required filters. "
                "Choose measures covering the same records."
            )
        for name in mismatched:
            metrics.remove(name)
            units.pop(name)
            exclusions.append(
                dict(
                    column=name,
                    reason="Its required filters select different records from this scan.",
                )
            )
        filters = common
    else:
        filters = ()
    if len(metrics) + len(categories) < 2:
        raise ClarificationRequiredError(
            "I need at least two usable fields to compare. "
            "Confirm the missing units or choose more fields."
        )
    declared = {
        item["column"]: item["aggregation"]
        for item in (context.definition or {}).get("metrics", [])
    }
    group_metrics = [name for name in metrics if declared.get(name, "avg") == "avg"]
    for name in metrics:
        if name not in group_metrics:
            exclusions.append(
                dict(
                    column=name,
                    reason="Group averages are excluded because its saved calculation is "
                    + declared[name]
                    + "; raw-value relationship checks remain available.",
                )
            )
    return dict(
        version=REQUEST_VERSION,
        selected=list(selected),
        columns=[*metrics, *categories],
        metrics=metrics,
        group_metrics=group_metrics,
        categories=categories,
        units=units,
        filters=[
            dict(column=item.column, operator=item.operator.value, value=item.value)
            for item in filters
        ],
        exclusions=exclusions,
        limits=dict(
            rows=MAX_ROWS,
            metrics=MAX_METRICS,
            categories=MAX_CATEGORIES,
            minimum_support=MIN_SUPPORT,
            minimum_group=MIN_GROUP,
            findings=MAX_FINDINGS,
        ),
    )


def pattern_plan(
    scope: WorkspaceScope, did: UUID, view: DatasetView, request: dict[str, Any]
) -> QueryPlan:
    from execplus.domain.semantics import FilterOperator

    if request["version"] != REQUEST_VERSION:
        invalid("The saved pattern method is not supported.")
    filters = tuple(
        MetricFilter(item["column"], FilterOperator(item["operator"]), item["value"])
        for item in request["filters"]
    )
    where, parameters = build_where(view, filters)
    fields = ", ".join(quote_identifier(name) for name in request["columns"])
    sql = f'SELECT {fields} FROM "dataset"'
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {fields} LIMIT {MAX_ROWS + 1}"
    validate_read_only(sql)
    return QueryPlan(
        uuid4(), scope.workspace_id, did, "Explore measured patterns", sql, tuple(parameters)
    )


def encoded(value: Decimal) -> str:
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def approximate(value: float | Decimal) -> str:
    if not math.isfinite(float(value)):
        invalid("A statistical score could not be calculated reliably.")
    rounded = Decimal(str(value)).quantize(Decimal("0.000001"))
    return format(rounded if rounded else abs(rounded), "f")


def numerical(value: Scalar) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | Decimal):
        invalid("A selected measure contains a non-numerical value.")
    return Decimal(str(value))


def normalized(values: list[Decimal]) -> tuple[float, ...]:
    low, high = min(values), max(values)
    if low == high:
        return ()
    return tuple(float((value - low) / (high - low)) for value in values)


def ranks(values: list[Decimal]) -> tuple[float, ...]:
    counts = Counter(values)
    positions = {}
    start = 1
    for value in sorted(counts):
        positions[value] = (start + start + counts[value] - 1) / 2
        start += counts[value]
    return tuple(positions[value] for value in values)


def mean(values: list[Decimal]) -> Decimal:
    return (sum(values, Decimal(0)) / len(values)).quantize(Decimal("0.000000000001"))


def finding_id(kind: str, columns: list[str]) -> str:
    return checksum(dict(kind=kind, columns=columns))[:16]


def _numeric(
    rows: tuple[tuple[Scalar, ...], ...],
    names: list[str],
    left: str,
    right: str,
    units: dict[str, str],
    correlations: Correlation,
) -> dict[str, Any] | None:
    li, ri = names.index(left), names.index(right)
    pairs = [
        (numerical(row[li]), numerical(row[ri]))
        for row in rows
        if row[li] is not None and row[ri] is not None
    ]
    if len(pairs) < MIN_SUPPORT:
        return None
    x, y = normalized([pair[0] for pair in pairs]), normalized([pair[1] for pair in pairs])
    if not x or not y:
        return None
    scores = correlations(
        x, y, ranks([pair[0] for pair in pairs]), ranks([pair[1] for pair in pairs])
    )
    if scores is None:
        return None
    pearson, spearman = scores
    if not all(math.isfinite(value) and -1 <= value <= 1 for value in scores if value is not None):
        invalid("A statistical score could not be calculated reliably.")
    strongest = spearman if pearson is None or abs(spearman) >= abs(pearson) else pearson
    strong = abs(strongest) >= 0.5
    points = (
        pairs
        if len(pairs) <= 200
        else [pairs[index * (len(pairs) - 1) // 199] for index in range(200)]
    )
    direction = "tend to rise together" if strongest >= 0 else "tend to move in opposite directions"
    notes = [
        "These values occur in the same rows. "
        "This does not establish cause, event order or a future outcome.",
        "Scores summarize the explored sample; "
        "they are not prediction accuracy or statistical significance.",
    ]
    if abs(strongest) >= 0.995:
        notes.append(
            "The relationship is almost perfect. Check whether these fields duplicate, derive from "
            "or leak information about each other before building a prediction model."
        )
    if len(pairs) > 200:
        notes.append(
            "The chart shows 200 evenly selected points from the sorted evidence. "
            "Scores use every complete pair."
        )
    if pearson is None:
        notes.append(
            "The straight-line score is unavailable because converting these exact values to "
            "statistical precision would merge distinct observations. "
            "The rank score preserves their exact order."
        )
    return dict(
        id=finding_id("numeric_relationship", [left, right]),
        type="numeric_relationship",
        strength="strong" if strong else "weak",
        title=f"{left} and {right} {direction}" if strong else f"Checking {left} with {right}",
        summary=(
            (
                f"Among {len(pairs)} complete rows, {left} and {right} {direction}. "
                if strong
                else f"No clear pattern: we checked {left} with {right} in {len(pairs)} rows. "
            )
            + f"Rank relationship: {approximate(spearman)}; straight-line relationship: "
            f"{approximate(pearson) if pearson is not None else 'unavailable'}."
        ),
        columns=[left, right],
        score=approximate(abs(strongest)),
        support=len(pairs),
        excluded=len(rows) - len(pairs),
        statistics=dict(
            pearson=approximate(pearson) if pearson is not None else None,
            spearman=approximate(spearman),
        ),
        chart=dict(
            kind="scatter",
            x=left,
            y=right,
            x_unit=units[left],
            y_unit=units[right],
            points=[dict(x=encoded(xv), y=encoded(yv)) for xv, yv in points],
        ),
        notes=notes,
    )


def _groups(
    rows: tuple[tuple[Scalar, ...], ...],
    names: list[str],
    category: str,
    metric: str,
    unit: str,
) -> dict[str, Any] | None:
    ci, mi = names.index(category), names.index(metric)
    groups: dict[str, list[Decimal]] = defaultdict(list)
    for row in rows:
        if row[ci] is not None and row[mi] is not None:
            groups[str(row[ci])].append(numerical(row[mi]))
    if len(groups) > MAX_CATEGORIES_PER_COLUMN:
        return None
    usable = {key: values for key, values in groups.items() if len(values) >= MIN_GROUP}
    values = [value for group in usable.values() for value in group]
    if len(usable) < 2 or len(values) < MIN_SUPPORT:
        return None
    center = sum(values, Decimal(0)) / len(values)
    total_variance = sum(((value - center) ** 2 for value in values), Decimal(0))
    if not total_variance:
        return None
    between = sum(
        (
            Decimal(len(group)) * (sum(group, Decimal(0)) / len(group) - center) ** 2
            for group in usable.values()
        ),
        Decimal(0),
    )
    score = between / total_variance
    strong = score >= Decimal("0.2")
    means = {key: mean(values) for key, values in usable.items()}
    highest = max(means, key=lambda key: means[key])
    lowest = min(means, key=lambda key: means[key])
    points = [dict(x=key, y=encoded(means[key]), count=len(usable[key])) for key in sorted(usable)]
    return dict(
        id=finding_id("group_difference", [category, metric]),
        type="group_difference",
        strength="strong" if strong else "weak",
        title=f"{metric} differs across {category}"
        if strong
        else f"Comparing {metric} by {category}",
        summary=(
            ("" if strong else "No clear group pattern: ")
            + f"Average {metric} is {encoded(means[highest])} {unit} for {highest} "
            f"and {encoded(means[lowest])} {unit} for {lowest}, "
            f"across {len(values)} covered rows."
        ),
        columns=[category, metric],
        score=approximate(score),
        support=len(values),
        excluded=len(rows) - len(values),
        statistics=dict(eta_squared=approximate(score)),
        chart=dict(kind="bar", x=category, y=metric, y_unit=unit, points=points),
        notes=[
            "Groups need at least five complete rows; "
            "missing values and smaller groups are excluded.",
            "Arithmetic means are rounded to twelve decimal places. Group differences describe "
            "these records; they do not show what changing a category would cause.",
        ],
    )


def _categories(
    rows: tuple[tuple[Scalar, ...], ...],
    names: list[str],
    left: str,
    right: str,
    association: Association,
) -> dict[str, Any] | None:
    li, ri = names.index(left), names.index(right)
    pairs = [
        (str(row[li]), str(row[ri])) for row in rows if row[li] is not None and row[ri] is not None
    ]
    left_counts, right_counts = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    if max(len(left_counts), len(right_counts)) > MAX_CATEGORIES_PER_COLUMN:
        return None
    pairs = [
        (x, y) for x, y in pairs if left_counts[x] >= MIN_GROUP and right_counts[y] >= MIN_GROUP
    ]
    left_counts, right_counts = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    if len(pairs) < MIN_SUPPORT or min(len(left_counts), len(right_counts)) < 2:
        return None
    if min(*left_counts.values(), *right_counts.values()) < MIN_GROUP:
        return None
    xs, ys = sorted(left_counts), sorted(right_counts)
    counts = Counter(pairs)
    score = association(tuple(tuple(counts[x, y] for y in ys) for x in xs))
    if score is None:
        return None
    if not math.isfinite(score) or not 0 <= score <= 1:
        invalid("A category relationship could not be calculated reliably.")
    strongest = max(counts, key=lambda pair: counts[pair])
    strong = score >= 0.3
    return dict(
        id=finding_id("category_association", [left, right]),
        type="category_association",
        strength="strong" if strong else "weak",
        title=f"{left} and {right} occur together in a pattern"
        if strong
        else f"Checking {left} alongside {right}",
        summary=(
            ("" if strong else "No clear category pattern: ")
            + f"{strongest[0]} with {strongest[1]} occurs in {counts[strongest]} "
            f"of {len(pairs)} covered rows. Overall category association: {approximate(score)}."
        ),
        columns=[left, right],
        score=approximate(score),
        support=len(pairs),
        excluded=len(rows) - len(pairs),
        statistics=dict(cramers_v=approximate(score)),
        chart=dict(
            kind="matrix",
            x=left,
            y=right,
            points=[dict(x=x, y=y, count=counts[x, y]) for x in xs for y in ys],
        ),
        notes=[
            "Category association ranges from zero to one and has no direction. "
            "It is not statistical significance or an event sequence.",
            "Missing values and category levels with fewer than five rows are excluded; "
            "small groups can produce unstable patterns.",
        ],
    )


def pattern_result(
    value: QueryResult,
    request: dict[str, Any],
    engine_version: str,
    correlations: Correlation,
    association: Association,
) -> dict[str, Any]:
    if len(value.rows) > MAX_ROWS:
        invalid(
            "This file has more than 10,000 matching rows. "
            "Choose a smaller governed dataset; no partial sample was analyzed."
        )
    if tuple(request["columns"]) != value.columns or any(
        len(row) != len(value.columns) for row in value.rows
    ):
        invalid("The pattern evidence does not match its declared fields.")
    candidates: list[dict[str, Any]] = []
    checked = 0
    names, metrics, categories = request["columns"], request["metrics"], request["categories"]
    with localcontext() as precision:
        precision.prec = 128
        for left, right in combinations(metrics, 2):
            if len(request["selected"]) == 1 and request["selected"][0] not in {left, right}:
                continue
            checked += 1
            finding = _numeric(value.rows, names, left, right, request["units"], correlations)
            if finding:
                candidates.append(finding)
        for category in categories:
            for metric in request["group_metrics"]:
                if len(request["selected"]) == 1 and request["selected"][0] not in {
                    category,
                    metric,
                }:
                    continue
                checked += 1
                finding = _groups(value.rows, names, category, metric, request["units"][metric])
                if finding:
                    candidates.append(finding)
        for left, right in combinations(categories, 2):
            if len(request["selected"]) == 1 and request["selected"][0] not in {left, right}:
                continue
            checked += 1
            finding = _categories(value.rows, names, left, right, association)
            if finding:
                candidates.append(finding)
    candidates.sort(key=lambda finding: (-Decimal(finding["score"]), finding["id"]))
    explored = [finding for finding in candidates if finding["strength"] == "weak"][:2]
    evaluated = len(candidates)
    candidates = [finding for finding in candidates if finding["strength"] == "strong"]
    selected: list[dict[str, Any]] = []
    for kind in ("numeric_relationship", "group_difference", "category_association"):
        first = next((finding for finding in candidates if finding["type"] == kind), None)
        if first:
            selected.append(first)
    selected.extend(finding for finding in candidates if finding not in selected)
    findings = selected[:MAX_FINDINGS]
    return dict(
        version=VERSION,
        engine_version=engine_version,
        findings=findings,
        exploratory=explored,
        status="patterns_found"
        if findings
        else "insufficient_data"
        if not evaluated
        else "no_strong_patterns",
        coverage=dict(
            source_rows=value.records_analyzed,
            filtered_rows=len(value.rows),
            eligible_columns=len(names),
            checked_candidates=checked,
            suppressed_candidates=checked - len(candidates),
            selected_findings=len(findings),
            omitted_findings=max(0, len(candidates) - len(findings)),
            evaluated_candidates=evaluated,
            insufficient_candidates=checked - evaluated,
        ),
        limitations=[
            "Exploratory associations in this file, not causes, predictions, event order "
            "or proof that a pattern will repeat.",
            "Searching many pairs can find chance patterns. No significance tests or prediction "
            "accuracy are reported; check another dataset before relying on a finding.",
            "At least twenty complete rows are needed per comparison and five per group. "
            "Repeated or related rows may overstate independent support.",
            "Display thresholds are |correlation| >= 0.5, category separation >= 0.2 "
            "and category association >= 0.3; these are exploration rules, not confidence levels.",
            "Scores use all matching rows and are approximate to six decimal places. "
            "Source values and counts retain their original exact representation.",
            "At most eight measures and four categories are selected in source order. "
            "This scan does not cover every possible relationship or nonlinear pattern.",
        ],
        exclusions=request["exclusions"],
    )
