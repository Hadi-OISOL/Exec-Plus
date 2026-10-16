"""Use case: Compares pooled and within-group relationships on identical covered rows.

What it does: Retains governed populations, exact values, exclusions and descriptive limits.
"""

import math
from collections import Counter
from dataclasses import replace
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID

from execplus.domain.decision_analysis import checksum
from execplus.domain.evidence import scalar_record
from execplus.domain.guidance import DescriptionContext
from execplus.domain.models import QueryPlan, QueryResult, Scalar, WorkspaceScope
from execplus.domain.patterns import (
    MAX_CATEGORIES_PER_COLUMN,
    MAX_ROWS,
    MIN_SUPPORT,
    Correlation,
    approximate,
    encoded,
    invalid,
    normalized,
    numerical,
    pattern_plan,
    pattern_request,
    ranks,
)
from execplus.domain.patterns import (
    REQUEST_VERSION as PATTERN_REQUEST_VERSION,
)
from execplus.domain.profiling import TableData
from execplus.domain.semantics import DatasetView

VERSION = "group-relationship-comparison-v1"
REQUEST_VERSION = "group-relationship-request-v1"
EVIDENCE_VERSION = "group-relationship-evidence-v1"
MIN_GROUPS = 2


def group_relationship_request(
    context: DescriptionContext,
    table: TableData,
    selected: tuple[str, ...],
    group_by: str,
) -> dict[str, Any]:
    if len(selected) != 2 or len(set((*selected, group_by))) != 3:
        invalid("Choose two different measures and a separate category to compare groups.")
    governed = pattern_request(context, table, (*selected, group_by))
    if governed["metrics"] != list(selected) or governed["categories"] != [group_by]:
        invalid("Choose two numerical measures and one category with confirmed roles and units.")
    return dict(
        version=REQUEST_VERSION,
        selected=list(selected),
        columns=[*selected, group_by],
        metrics=list(selected),
        categories=[group_by],
        group_by=group_by,
        units=governed["units"],
        filters=governed["filters"],
        exclusions=[],
        limits=dict(
            rows=MAX_ROWS,
            groups=MAX_CATEGORIES_PER_COLUMN,
            minimum_complete_pairs=MIN_SUPPORT,
            minimum_groups=MIN_GROUPS,
            chart_points=200,
        ),
    )


def group_relationship_plan(
    scope: WorkspaceScope, did: UUID, view: DatasetView, request: dict[str, Any]
) -> QueryPlan:
    if request["version"] != REQUEST_VERSION:
        invalid("The saved grouped relationship method is not supported.")
    return replace(
        pattern_plan(scope, did, view, {**request, "version": PATTERN_REQUEST_VERSION}),
        question="Compare relationships within groups",
    )


def _statistics(
    pairs: list[tuple[Decimal, Decimal]], correlations: Correlation
) -> tuple[dict[str, str | None], dict[str, str]] | None:
    left, right = [pair[0] for pair in pairs], [pair[1] for pair in pairs]
    scores = correlations(normalized(left), normalized(right), ranks(left), ranks(right))
    if scores is None:
        return None
    pearson, spearman = scores
    if not all(math.isfinite(score) and -1 <= score <= 1 for score in scores if score is not None):
        invalid("A grouped relationship score could not be calculated reliably.")
    values: dict[str, str | None] = {}
    directions: dict[str, str] = {}
    for name, score in (("pearson", pearson), ("spearman", spearman)):
        values[name] = approximate(score) if score is not None else None
        directions[name] = (
            "unavailable"
            if score is None
            else "weak"
            if abs(score) < 0.5
            else "positive"
            if score > 0
            else "negative"
        )
    return values, directions


def group_relationship_result(
    value: QueryResult,
    request: dict[str, Any],
    engine_version: str,
    correlations: Correlation,
) -> dict[str, Any]:
    if len(value.rows) > MAX_ROWS:
        invalid(
            "This file has more than 10,000 matching rows. "
            "Choose a smaller governed dataset; no partial sample was analyzed."
        )
    if (
        request["version"] != REQUEST_VERSION
        or tuple(request["columns"]) != value.columns
        or len(value.columns) != 3
        or any(len(row) != 3 for row in value.rows)
    ):
        invalid("The grouped relationship evidence does not match its declared fields.")
    buckets: dict[str, list[tuple[Scalar, ...]]] = {}
    scalars: dict[str, dict[str, object]] = {}
    labels: dict[str, str] = {}
    missing_category = missing_pair = 0
    for row in value.rows:
        if row[2] is None:
            missing_category += 1
            continue
        exact = scalar_record(row[2])
        key = checksum(exact)
        scalars[key], labels[key] = exact, str(row[2])
        buckets.setdefault(key, []).append(row)
        if row[0] is None or row[1] is None:
            missing_pair += 1
    if len(buckets) > MAX_CATEGORIES_PER_COLUMN:
        invalid("This comparison supports at most twelve observed category levels.")
    duplicates = Counter(labels.values())
    labels = {
        key: f"{label} ({scalars[key]['type']})" if duplicates[label] > 1 else label
        for key, label in labels.items()
    }
    # A literal category may itself contain a type suffix; never merge its display identity.
    duplicates = Counter(labels.values())
    labels = {
        key: f"{label} [{key}]" if duplicates[label] > 1 else label
        for key, label in labels.items()
    }
    groups: list[dict[str, Any]] = []
    covered: list[tuple[Decimal, Decimal, str]] = []
    excluded = dict(sparse_group_rows=0, constant_group_rows=0, unstable_group_rows=0)
    with localcontext() as precision:
        precision.prec = 128
        for key in sorted(buckets, key=lambda item: (labels[item], item)):
            rows = buckets[key]
            pairs = [
                (numerical(row[0]), numerical(row[1]))
                for row in rows
                if row[0] is not None and row[1] is not None
            ]
            status, scores = "eligible", None
            if len(pairs) < MIN_SUPPORT:
                status = "sparse"
            elif len({pair[0] for pair in pairs}) < 2 or len({pair[1] for pair in pairs}) < 2:
                status = "constant"
            else:
                scores = _statistics(pairs, correlations)
                if scores is None:
                    status = "unstable"
            if status == "eligible":
                covered.extend((left, right, labels[key]) for left, right in pairs)
            else:
                excluded[f"{status}_group_rows"] += len(pairs)
            groups.append(
                dict(
                    id=key[:16],
                    value=scalars[key],
                    label=labels[key],
                    rows=len(rows),
                    complete_pairs=len(pairs),
                    excluded_pairs=len(rows) - len(pairs),
                    status=status,
                    statistics=scores[0] if scores else None,
                    directions=scores[1] if scores else None,
                )
            )
        eligible = sum(group["status"] == "eligible" for group in groups)
        pooled_scores = (
            _statistics([(left, right) for left, right, _ in covered], correlations)
            if eligible >= MIN_GROUPS
            else None
        )
    pooled = None
    comparisons: dict[str, dict[str, list[str]]] = {}
    for name in ("pearson", "spearman"):
        compared: dict[str, list[str]] = dict(
            reversal_groups=[], same_direction_groups=[], weak_groups=[], unavailable_groups=[]
        )
        for group in groups:
            if group["status"] != "eligible" or pooled_scores is None:
                continue
            direction = group["directions"][name]
            pooled_direction = pooled_scores[1][name]
            category = (
                "unavailable_groups"
                if "unavailable" in (direction, pooled_direction)
                else "weak_groups"
                if "weak" in (direction, pooled_direction)
                else "same_direction_groups"
                if direction == pooled_direction
                else "reversal_groups"
            )
            compared[category].append(group["label"])
        comparisons[name] = compared
    if pooled_scores is not None:
        points = sorted(covered)
        if len(points) > 200:
            points = [points[index * (len(points) - 1) // 199] for index in range(200)]
        left, right = request["metrics"]
        pooled = dict(
            support=len(covered),
            statistics=pooled_scores[0],
            directions=pooled_scores[1],
            chart=dict(
                kind="scatter",
                x=left,
                y=right,
                x_unit=request["units"][left],
                y_unit=request["units"][right],
                points=[dict(x=encoded(x), y=encoded(y), group=group) for x, y, group in points],
            ),
            notes=[
                "The pooled scores use exactly the same complete rows as the eligible groups. "
                "Groups are not given equal weight: every covered row contributes once.",
                "The chart shows up to 200 evenly selected points from sorted evidence; "
                "scores use every covered pair.",
            ],
        )
    return dict(
        version=VERSION,
        engine_version=engine_version,
        status="compared" if pooled is not None else "insufficient_data",
        reason=(
            None
            if pooled is not None
            else "At least two usable groups with twenty complete, varying pairs each are needed."
            if eligible < MIN_GROUPS
            else "The pooled relationship could not be calculated reliably for these values."
        ),
        columns=request["metrics"],
        group_by=request["group_by"],
        units=request["units"],
        pooled=pooled,
        groups=groups,
        comparisons=comparisons,
        coverage=dict(
            source_rows=value.records_analyzed,
            filtered_rows=len(value.rows),
            covered_rows=len(covered),
            excluded_rows=len(value.rows) - len(covered),
            missing_category_rows=missing_category,
            missing_pair_rows=missing_pair,
            **excluded,
            observed_groups=len(groups),
            eligible_groups=eligible,
        ),
        exclusions=request["exclusions"],
        limitations=[
            "These are observed associations, not causes, predictions or event order. "
            "A different direction after grouping does not identify why the difference occurs.",
            "At least two usable groups with twenty complete pairs each are required. "
            "Missing categories/pairs, sparse groups and constant groups are excluded. "
            "Repeated or related records may overstate independent support.",
            "Directions are highlighted only at |correlation| >= 0.5 for both pooled and group "
            "scores. This is a display rule, not statistical significance or confidence.",
            "Pearson describes straight-line association; Spearman describes rank association. "
            "Weak scores do not rule out nonlinear relationships or other groupings.",
            "Scores are approximate to six decimal places. Exact ranks preserve tied values. "
            "A straight-line score is unavailable if float conversion merges distinct values; "
            "the rank score can still be available.",
            "Nearly perfect relationships may involve duplicate or derived fields; "
            "check for prediction leakage before using them in a prediction model.",
        ],
    )
