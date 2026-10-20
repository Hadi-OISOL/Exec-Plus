"""Use case: Lets a bounded team of deterministic analysts brief a newly opened dataset.

What it does: Computes exact findings, chart specifications and catalog actions, and pairs
every headline number with an independent cross-check that decides whether it is shown.
"""

import math
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID, uuid4

from execplus.domain.decision_analysis import detect_distribution
from execplus.domain.discovery import category_candidates, measure_candidates, readable_number
from execplus.domain.errors import UnsafeQueryError
from execplus.domain.guidance import DescriptionContext
from execplus.domain.ingestion import IngestionError
from execplus.domain.models import QueryPlan, Scalar, WorkspaceScope
from execplus.domain.patterns import Correlation, approximate, normalized, ranks
from execplus.domain.semantics import (
    DatasetView,
    FilterOperator,
    MetricFilter,
    build_where,
    quote_identifier,
    validate_read_only,
)

VERSION = "insights-v1"
ROUTE = "deterministic:insights-v1"
MAX_ROWS = 50_000
MAX_MEASURES = 6
MAX_CATEGORIES = 4
MAX_SLICES = 8
MAX_GROUPS = 12
MIN_GROUP = 5
MIN_PAIRS = 20
MAX_CHECKS = 24
MAX_OUTLIER_DISTINCT = 1000
MAX_DUPLICATE_FIELDS = 80
TOLERANCE = 1e-6
LIMITS = dict(
    rows=MAX_ROWS,
    measures=MAX_MEASURES,
    categories=MAX_CATEGORIES,
    checks=MAX_CHECKS,
    slices=MAX_SLICES,
    groups=MAX_GROUPS,
)
ACTION_KINDS = frozenset(
    {
        "check_missing",
        "review_duplicates",
        "investigate_outliers",
        "compare_groups",
        "show_group",
        "explore_relationship",
        "what_if",
        "review_meaning",
        "ask",
    }
)
CAUSAL_NOTE = "This describes rows in this file; it does not show a cause or predict an outcome."


@dataclass(frozen=True)
class Selection:
    measures: tuple[str, ...]
    categories: tuple[str, ...]
    segment_measures: tuple[str, ...]
    units: dict[str, str | None]
    limitations: tuple[str, ...]

    @property
    def columns(self) -> tuple[str, ...]:
        return (*self.measures, *self.categories)


@dataclass(frozen=True)
class Check:
    label: str
    primary: str
    aggregation: str
    column: str | None = None
    filters: tuple[MetricFilter, ...] = ()
    secondary: str | None = None
    method: str = ""
    query_id: str | None = None

    @property
    def sql(self) -> bool:
        return self.aggregation != "statistic"

    def agrees(self) -> bool:
        if self.secondary is None:
            return False
        if self.aggregation == "statistic":
            return abs(float(self.primary) - float(self.secondary)) <= TOLERANCE
        return self.primary == self.secondary

    def body(self) -> dict[str, Any]:
        def shown(value: str | None) -> str | None:
            if value is None:
                return None
            if self.aggregation == "statistic":
                return approximate(float(value))
            return readable_number(Decimal(value))

        return dict(
            label=self.label,
            primary=shown(self.primary),
            secondary=shown(self.secondary),
            method=self.method,
            query_id=self.query_id,
            agrees=self.agrees(),
        )


@dataclass(frozen=True)
class Card:
    id: str
    analyst: str
    title: str
    statements: tuple[str, ...]
    evidence: tuple[dict[str, Any], ...]
    chart: dict[str, Any] | None
    checks: tuple[Check, ...]
    actions: tuple[dict[str, Any], ...]
    score: float

    def body(self, headline: int = 0) -> dict[str, Any]:
        return dict(
            id=self.id,
            analyst=self.analyst,
            title=self.title,
            summary=self.statements[headline],
            statements=list(self.statements),
            evidence=list(self.evidence),
            chart=self.chart,
            cross_check=dict(
                status="verified" if self.checks else "not_applicable",
                checks=[check.body() for check in self.checks],
            ),
            actions=list(self.actions),
        )


def _text(value: Scalar) -> str:
    if value is None:
        return "(missing)"
    if isinstance(value, bool):
        return "true" if value else "false"
    return readable_number(value)


def _exact(value: Scalar) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _number(value: Scalar) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _mean(values: list[Decimal]) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return (sum(values, Decimal(0)) / len(values)).quantize(Decimal("1e-12"))


def _quantile(ordered: list[Decimal], fraction: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        position = Decimal(len(ordered) - 1) * fraction
        lower = int(position)
        weight = position - lower
        left = ordered[lower]
        return left if not weight else left + weight * (ordered[lower + 1] - left)


def _places(values: list[Decimal]) -> int:
    return max((max(0, -int(value.normalize().as_tuple().exponent)) for value in values), default=0)


def _readable(value: Decimal) -> str:
    with localcontext() as context:
        context.prec = 50
        if not value:
            return "0"
        step = Decimal("0.01") if abs(value) >= 1 else Decimal(1).scaleb(value.adjusted() - 2)
        return _text(value.quantize(step))


def _evidence(label: str, value: str, unit: str | None = None) -> dict[str, Any]:
    return dict(label=label, value=value, unit=unit)


def _unit(unit: str | None) -> str:
    return f" {unit}" if unit else ""


def action(kind: str, label: str, key: str, **payload: Any) -> dict[str, Any]:
    if kind not in ACTION_KINDS:
        raise ValueError("Unsupported insight action")
    return dict(id=f"{kind}:{key}", kind=kind, label=label, payload=payload)


def _ask(question: str) -> dict[str, Any]:
    return action("ask", f"Ask: {question}", question, type="ask", question=question)


def _count(label: str, value: int, column: str | None = None, *filters: MetricFilter) -> Check:
    return Check(label, str(value), "count", column, filters, method="duckdb-count")


def queryable(name: str) -> bool:
    try:
        validate_read_only(f'SELECT {quote_identifier(name)} FROM "dataset"')
    except UnsafeQueryError:
        return False
    return True


def select_fields(context: DescriptionContext) -> Selection:
    confirmed = context.state == "confirmed"
    rules: dict[str, list[dict[str, Any]]] = {}
    for rule in (context.definition or {}).get("metrics", []):
        rules.setdefault(rule["column"], []).append(rule)
    definitions = {item["name"]: item for item in (context.definition or {}).get("columns", [])}
    limitations: list[str] = []
    measures: list[str] = []
    blocked = [
        name
        for name in [*measure_candidates(context), *category_candidates(context)]
        if not queryable(name)
    ]
    if blocked:
        limitations.append(
            f"{', '.join(blocked[:3])}: the field name matches a reserved query word, "
            "so the analysts skipped it."
        )
    for name in measure_candidates(context):
        if name in blocked:
            continue
        if confirmed and any(rule.get("filters") for rule in rules.get(name, [])):
            limitations.append(
                f"{name}: its saved calculation uses required filters, so ask about it directly."
            )
        else:
            measures.append(name)
    if len(measures) > MAX_MEASURES:
        limitations.append(
            f"The analysts covered the first {MAX_MEASURES} ranked measures; "
            "ask about other measures directly."
        )
    measures = measures[:MAX_MEASURES]
    categories = [name for name in category_candidates(context) if name not in blocked]
    if len(categories) > MAX_CATEGORIES:
        limitations.append(
            f"The analysts covered the first {MAX_CATEGORIES} ranked categories; "
            "ask about other categories directly."
        )
    categories = categories[:MAX_CATEGORIES]
    units: dict[str, str | None] = {}
    for name in measures:
        column = definitions.get(name, {})
        units[name] = (column.get("currency") or column.get("unit") or None) if confirmed else None
    segment = tuple(
        name
        for name in measures
        if not confirmed or all(rule["aggregation"] == "avg" for rule in rules.get(name, []))
    )
    return Selection(tuple(measures), tuple(categories), segment, units, tuple(limitations))


def projection_plan(scope: WorkspaceScope, dataset_id: UUID, selection: Selection) -> QueryPlan:
    fields = ", ".join(quote_identifier(name) for name in selection.columns)
    sql = f'SELECT {fields} FROM "dataset" ORDER BY {fields} LIMIT {MAX_ROWS + 1}'
    validate_read_only(sql)
    return QueryPlan(uuid4(), scope.workspace_id, dataset_id, "Analyst team projection", sql)


def check_plan(
    scope: WorkspaceScope, dataset_id: UUID, view: DatasetView, check: Check
) -> QueryPlan:
    parameters: list[Scalar] = []
    if check.aggregation == "duplicates":
        names = ", ".join(quote_identifier(column.name) for column in view.columns)
        sql = (
            f'SELECT {names}, COUNT(*) AS "__value" FROM "dataset" '
            f"GROUP BY {names} ORDER BY {names} LIMIT 100000"
        )
    else:
        target = quote_identifier(check.column) if check.column else "*"
        function = "AVG" if check.aggregation == "avg" else "COUNT"
        clauses, parameters = build_where(view, check.filters)
        sql = f'SELECT {function}({target}) AS "__value" FROM "dataset"'
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " LIMIT 1"
    validate_read_only(sql)
    return QueryPlan(
        uuid4(),
        scope.workspace_id,
        dataset_id,
        f"Cross-check: {check.label}",
        sql,
        tuple(parameters),
    )


def check_value(check: Check, rows: tuple[tuple[Scalar, ...], ...]) -> str:
    if check.aggregation == "duplicates":
        return str(sum(int(row[-1]) - 1 for row in rows if isinstance(row[-1], int)))
    value = rows[0][0] if rows else None
    return "none" if value is None else _exact(value)


def _quality(
    context: DescriptionContext, selection: Selection, columns: dict[str, list[Scalar]]
) -> Card:
    profile = context.profile
    rows, width = profile["row_count"], profile["column_count"]
    observed = profile["columns"]
    missing = sorted(
        ((column["missing"], column["name"]) for column in observed if column["missing"]),
        key=lambda item: (-item[0], item[1]),
    )
    duplicates = next(
        (item["count"] for item in profile["quality_checks"] if item["code"] == "duplicate_rows"),
        0,
    )
    constant = [column["name"] for column in observed if column["distinct_count"] == 1]
    negatives = [
        (name, sum(1 for value in columns[name] if value is not None and _number(value) < 0))
        for name in selection.measures
    ]
    negatives = [(name, count) for name, count in negatives if count][:2]
    statements: list[str] = []
    checks = [_count("Rows in the file", rows)]
    actions: list[dict[str, Any]] = []
    conflicted = {
        column["name"] for column in observed if column["type_conflicts"] or column["invalid_dates"]
    }
    if missing:
        total = sum(count for count, _ in missing)
        count, name = missing[0]
        statements.append(
            f"{total} cells are empty; {name} has the most, with {count} of {rows} rows empty."
        )
        for count, name in missing[:3]:
            if name not in conflicted and queryable(name):
                checks.append(_count(f"Nonempty {name} values", rows - count, name))
        actions.append(
            action(
                "check_missing",
                f"Check missing values in {name}",
                name,
                type="prepare",
                column=name,
            )
        )
    if duplicates:
        statements.append(f"{duplicates} rows repeat an earlier row exactly.")
        actions.append(
            action(
                "review_duplicates",
                f"Review {duplicates} repeated rows",
                "rows",
                type="prepare",
                check="duplicate_rows",
            )
        )
    if (
        not conflicted
        and len(context.view.columns) <= MAX_DUPLICATE_FIELDS
        and all(queryable(column.name) for column in context.view.columns)
    ):
        checks.append(
            Check("Repeated rows", str(duplicates), "duplicates", method="duckdb-group-count")
        )
    if constant and rows > 1:
        statements.append(
            f"{', '.join(constant[:3])} {'has' if len(constant) == 1 else 'have'} "
            "the same value in every row, so it cannot explain differences."
        )
    for name, count in negatives:
        statements.append(
            f"{name} has {count} negative values; check their meaning before treating them "
            "as errors."
        )
        checks.append(
            _count(
                f"Negative {name} values",
                count,
                None,
                MetricFilter(name, FilterOperator.LT, 0),
            )
        )
    issues = bool(statements)
    if not issues:
        statements.append(
            f"All {rows} rows and {width} columns passed basic checks: "
            "no empty cells, repeated rows or constant fields."
        )
    statements.append(f"The file has {rows} rows and {width} columns.")
    actions.append(_ask("Are there any data quality issues?"))
    chart = (
        dict(
            type="bar",
            title="Empty cells by field",
            x=dict(field="label", label="Field", unit=None),
            y=dict(field="value", label="Empty cells", unit=None),
            rows=[dict(label=name, value=str(count)) for count, name in missing[:MAX_GROUPS]],
        )
        if missing
        else None
    )
    evidence = (
        _evidence("Rows", str(rows)),
        _evidence("Columns", str(width)),
        _evidence("Empty cells", str(sum(count for count, _ in missing))),
        _evidence("Repeated rows", str(duplicates)),
        _evidence("Constant fields", str(len(constant))),
    )
    return Card(
        "quality:file",
        "quality",
        "Data quality check" if issues else "Data quality: no basic issues",
        tuple(statements),
        evidence,
        chart,
        tuple(checks),
        tuple(actions),
        0.85 if issues else 0.1,
    )


def _composition(category: str, values: list[Scalar], measure: str | None) -> Card | None:
    total = len(values)
    counts = Counter(values)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], _text(item[0])))
    present = [(value, count) for value, count in ordered if value is not None]
    if not present or total == 0:
        return None

    def percent(count: int) -> str:
        with localcontext() as context:
            context.prec = 50
            return format((Decimal(count) * 100 / total).quantize(Decimal("0.1")), "f")

    slices = [(_text(value), count) for value, count in ordered]
    if len(slices) > MAX_SLICES:
        slices = [
            *slices[: MAX_SLICES - 1],
            ("Other", sum(count for _, count in slices[MAX_SLICES - 1 :])),
        ]
    leader, count = present[0]
    smallest, low = present[-1]
    statements = [
        f"{_text(leader)} is the largest {category} group with {count} of {total} rows "
        f"({percent(count)}%).",
        f"{category} has {len(present)} groups; the smallest is {_text(smallest)} with {low} rows.",
    ]
    if counts.get(None):
        statements.append(f"{counts[None]} rows have no {category} value.")
    actions = [
        action(
            "show_group",
            f"Show records where {category} is {_text(leader)}",
            f"{category}:{_text(leader)}",
            type="ask",
            question=f"Show all records where {category} equals {_text(leader)}",
        )
    ]
    if measure:
        question = f"Compare average {measure} by {category}"
        actions.append(
            action(
                "compare_groups",
                f"Compare {measure} across {category}",
                f"{measure}:{category}",
                type="ask",
                question=question,
            )
        )
    return Card(
        f"composition:{category}",
        "composition",
        f"How rows split by {category}",
        tuple(statements),
        (
            _evidence("Largest group", _text(leader)),
            _evidence("Rows in largest group", str(count)),
            _evidence("Share of rows", percent(count), "%"),
            _evidence("Groups", str(len(present))),
        ),
        dict(
            type="pie" if len(slices) == 2 else "donut",
            title=f"Rows by {category}",
            x=dict(field="label", label=category, unit=None),
            y=dict(field="count", label="Rows", unit=None),
            rows=[
                dict(label=label, count=str(value), percent=percent(value))
                for label, value in slices
            ],
        ),
        (
            _count(
                f"Rows where {category} = {_text(leader)}",
                count,
                None,
                MetricFilter(category, FilterOperator.EQ, leader),
            ),
        ),
        tuple(actions),
        0.3 + 0.3 * count / total,
    )


def _bins(ordered: list[Decimal]) -> list[dict[str, str]]:
    low, high = ordered[0], ordered[-1]
    if low == high:
        return [dict(label=_text(low), start=_text(low), end=_text(high), count=str(len(ordered)))]
    step = Decimal(1).scaleb(-min(_places(ordered) + 2, 12))
    count = min(10, max(2, math.ceil(math.log2(len(ordered))) + 1))
    with localcontext() as context:
        context.prec = 50
        edges = [low] + [
            (low + (high - low) * index / count).quantize(step) for index in range(1, count)
        ]
    edges.append(high)
    result = []
    for index in range(count):
        start, end = edges[index], edges[index + 1]
        last = index == count - 1
        members = sum(
            1 for value in ordered if start <= value and (value <= end if last else value < end)
        )
        result.append(
            dict(
                label=f"{_text(start)} to {_text(end)}",
                start=_text(start),
                end=_text(end),
                count=str(members),
            )
        )
    return result


def _summary(values: list[Decimal]) -> dict[str, Decimal]:
    ordered = sorted(values)
    return dict(
        minimum=ordered[0],
        q1=_quantile(ordered, Decimal("0.25")),
        median=_quantile(ordered, Decimal("0.5")),
        mean=_mean(values),
        q3=_quantile(ordered, Decimal("0.75")),
        maximum=ordered[-1],
    )


def _distribution(
    context: DescriptionContext,
    measure: str,
    values: list[Decimal],
    unit: str | None,
    what_if: dict[str, str],
) -> Card | None:
    if not values:
        return None
    stats = _summary(values)
    ordered = sorted(values)
    spread = stats["maximum"] - stats["minimum"]
    statements = (
        f"{measure} ranges from {_readable(stats['minimum'])} to "
        f"{_readable(stats['maximum'])}{_unit(unit)}; the middle half of rows falls between "
        f"{_readable(stats['q1'])} and {_readable(stats['q3'])}.",
        f"Average {measure}: {_readable(stats['mean'])}{_unit(unit)}; "
        f"median: {_readable(stats['median'])}{_unit(unit)}.",
    )
    actions = [_ask(f"What is the average {measure}?")]
    if measure in what_if:
        actions.append(
            action(
                "what_if",
                f"Run what-if on {measure}",
                measure,
                type="scenario",
                metric=measure,
                aggregation=what_if[measure],
            )
        )
    if context.state != "confirmed":
        actions.append(
            action(
                "review_meaning",
                f"Confirm what {measure} measures",
                measure,
                type="review_meaning",
                column=measure,
            )
        )
    labels = (
        ("Minimum", "minimum"),
        ("Lower quartile", "q1"),
        ("Median", "median"),
        ("Average", "mean"),
        ("Upper quartile", "q3"),
        ("Maximum", "maximum"),
    )
    skew = float(abs(stats["mean"] - stats["median"]) / spread) if spread else 0.0
    return Card(
        f"distribution:{measure}",
        "distribution",
        f"How {measure} is spread",
        statements,
        (
            *(_evidence(label, _text(stats[key]), unit) for label, key in labels),
            _evidence("Values", str(len(values))),
        ),
        dict(
            type="histogram",
            title=f"{measure} distribution",
            x=dict(field="label", label=measure, unit=unit),
            y=dict(field="count", label="Rows", unit=None),
            rows=_bins(ordered),
        ),
        (
            Check(
                f"Average {measure}",
                _exact(stats["mean"]),
                "avg",
                measure,
                method="duckdb-avg",
            ),
        ),
        tuple(actions),
        0.3 + min(0.2, skew),
    )


def _segment(
    measure: str,
    category: str,
    rows: list[tuple[Scalar, Scalar]],
    unit: str | None,
    spread: Decimal,
) -> tuple[float, Card] | None:
    groups: dict[Scalar, list[Decimal]] = {}
    for group, value in rows:
        if group is not None and value is not None:
            groups.setdefault(group, []).append(_number(value))
    if len(groups) > MAX_GROUPS:
        return None
    eligible = {group: values for group, values in groups.items() if len(values) >= MIN_GROUP}
    if len(eligible) < 2:
        return None
    means = sorted(
        ((_mean(values), _text(group), group, len(values)) for group, values in eligible.items()),
        key=lambda item: (-item[0], item[1]),
    )
    top, bottom = means[0], means[-1]
    gap = top[0] - bottom[0]
    relative = float(gap / spread) if spread else 0.0
    statements = (
        f"{top[1]} has the highest average {measure} ({_readable(top[0])}"
        f"{_unit(unit)}), {_readable(gap)} more than {bottom[1]} "
        f"({_readable(bottom[0])}{_unit(unit)}).",
        f"Across {len(means)} {category} groups with at least {MIN_GROUP} rows, "
        f"average {measure} ranges from {_readable(bottom[0])} to "
        f"{_readable(top[0])}{_unit(unit)}.",
        CAUSAL_NOTE,
    )
    question = f"Compare average {measure} by {category}"
    card = Card(
        f"segment:{measure}:{category}",
        "segment",
        f"{measure} by {category}",
        statements,
        (
            _evidence("Highest group", top[1]),
            _evidence("Highest average", _text(top[0]), unit),
            _evidence("Lowest group", bottom[1]),
            _evidence("Lowest average", _text(bottom[0]), unit),
            _evidence("Gap", _text(gap), unit),
            _evidence("Groups compared", str(len(means))),
        ),
        dict(
            type="bar",
            title=f"Average {measure} by {category}",
            x=dict(field="label", label=category, unit=None),
            y=dict(field="value", label=f"Average {measure}", unit=unit),
            rows=[
                dict(label=label, value=_text(mean), count=str(size))
                for mean, label, _, size in means
            ],
        ),
        tuple(
            Check(
                f"Average {measure} where {category} = {label}",
                _exact(mean),
                "avg",
                measure,
                (MetricFilter(category, FilterOperator.EQ, raw),),
                method="duckdb-avg",
            )
            for mean, label, raw, _ in (top, bottom)
        ),
        (
            action(
                "compare_groups",
                f"Compare {measure} across {category}",
                f"{measure}:{category}",
                type="ask",
                question=question,
            ),
            action(
                "show_group",
                f"Show records where {category} is {top[1]}",
                f"{category}:{top[1]}",
                type="ask",
                question=f"Show all records where {category} equals {top[1]}",
            ),
        ),
        0.4 + 0.5 * min(1.0, relative),
    )
    return relative, card


def _pearson(left: list[float], right: list[float]) -> float | None:
    count = len(left)
    left_mean, right_mean = math.fsum(left) / count, math.fsum(right) / count
    xy = math.fsum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    xx = math.fsum((a - left_mean) ** 2 for a in left)
    yy = math.fsum((b - right_mean) ** 2 for b in right)
    if not xx or not yy:
        return None
    return xy / math.sqrt(xx * yy)


def _average_ranks(values: list[Decimal]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        for position in range(start, end + 1):
            result[order[position]] = (start + end) / 2 + 1
        start = end + 1
    return result


def _relationship(
    measures: tuple[str, ...],
    columns: dict[str, list[Scalar]],
    correlations: Correlation,
) -> Card | None:
    scores: dict[
        tuple[str, str], tuple[float | None, float, int, list[tuple[Decimal, Decimal]]]
    ] = {}
    for index, left in enumerate(measures):
        for right in measures[index + 1 :]:
            pairs = [
                (_number(a), _number(b))
                for a, b in zip(columns[left], columns[right], strict=True)
                if a is not None and b is not None
            ]
            if len(pairs) < MIN_PAIRS:
                continue
            x = normalized([pair[0] for pair in pairs])
            y = normalized([pair[1] for pair in pairs])
            if not x or not y:
                continue
            result = correlations(
                x, y, ranks([pair[0] for pair in pairs]), ranks([pair[1] for pair in pairs])
            )
            if result is not None:
                scores[(left, right)] = (result[0], result[1], len(pairs), pairs)
    if not scores:
        return None
    (left, right), (pearson, spearman, support, pairs) = max(
        scores.items(), key=lambda item: abs(item[1][1])
    )
    rows = []
    for a in measures:
        for b in measures:
            key = (a, b) if (a, b) in scores else (b, a)
            if a == b:
                score: str | None = approximate(1.0)
                size = str(sum(1 for value in columns[a] if value is not None))
            elif key in scores:
                score, size = approximate(scores[key][1]), str(scores[key][2])
            else:
                score, size = None, "0"
            rows.append(dict(x=a, y=b, score=score, support=size))
    strong = abs(spearman) >= 0.5
    direction = "tend to rise together" if spearman >= 0 else "tend to move in opposite directions"
    shown = _readable(Decimal(approximate(spearman)))
    statements = (
        (
            f"{left} and {right} {direction} (rank score {shown}, {support} rows)."
            if strong
            else f"No strong relationship among {len(measures)} measures: the strongest pair is "
            f"{left} with {right} (rank score {shown})."
        ),
        f"{len(scores)} measure pairs were compared using complete rows only.",
        CAUSAL_NOTE,
    )
    own_left = [float(pair[0]) for pair in pairs]
    own_right = [float(pair[1]) for pair in pairs]
    own_rank = _pearson(
        _average_ranks([pair[0] for pair in pairs]), _average_ranks([pair[1] for pair in pairs])
    )
    checks = [
        Check(
            f"Rank score for {left} and {right}",
            repr(spearman),
            "statistic",
            secondary=None if own_rank is None else repr(own_rank),
            method="python-average-rank-pearson",
        )
    ]
    if pearson is not None:
        own = _pearson(own_left, own_right)
        checks.append(
            Check(
                f"Straight-line score for {left} and {right}",
                repr(pearson),
                "statistic",
                secondary=None if own is None else repr(own),
                method="python-pearson",
            )
        )
    return Card(
        "relationship:measures",
        "relationship",
        "How the measures relate",
        statements,
        (
            _evidence("Strongest pair", f"{left} / {right}"),
            _evidence("Rank score", approximate(spearman)),
            _evidence(
                "Straight-line score", approximate(pearson) if pearson is not None else "n/a"
            ),
            _evidence("Complete rows", str(support)),
            _evidence("Pairs compared", str(len(scores))),
        ),
        dict(
            type="heatmap",
            title="Rank relationship between measures",
            x=dict(field="x", label="Measure", unit=None),
            y=dict(field="y", label="Measure", unit=None),
            value=dict(field="score", label="Rank relationship", unit=None),
            rows=rows,
        ),
        tuple(checks),
        (
            action(
                "explore_relationship",
                f"Check how {left} relates to {right}",
                f"{left}:{right}",
                type="patterns",
                columns=[left, right],
            ),
        ),
        0.2 + 0.7 * abs(spearman),
    )


def outlier_detector(values: list[Decimal]) -> dict[str, Any] | None:
    frequencies = sorted(Counter(values).items())
    try:
        return detect_distribution([(value, count) for value, count in frequencies])
    except IngestionError:
        return None


def _outlier(measure: str, values: list[Decimal], unit: str | None) -> Card | None:
    if len(values) < 8 or len(set(values)) > MAX_OUTLIER_DISTINCT:
        return None
    result = outlier_detector(values)
    if result is None or not result["findings"]:
        return None
    median = Decimal(result["baseline"])
    flagged = [(Decimal(item["value"]), item["count"]) for item in result["findings"]]
    above = [(value, count) for value, count in flagged if value > median]
    below = [(value, count) for value, count in flagged if value < median]
    total = sum(count for _, count in flagged)
    checks, filters, sides = [], [], []
    if above:
        upper = min(value for value, _ in above)
        count = sum(count for _, count in above)
        checks.append(
            _count(
                f"{measure} values at or above {_text(upper)}",
                count,
                None,
                MetricFilter(measure, FilterOperator.GTE, upper),
            )
        )
        filters.append(dict(column=measure, operator="gte", value=_text(upper)))
        sides.append(f"{count} at or above {_text(upper)}")
    if below:
        lower = max(value for value, _ in below)
        count = sum(count for _, count in below)
        checks.append(
            _count(
                f"{measure} values at or below {_text(lower)}",
                count,
                None,
                MetricFilter(measure, FilterOperator.LTE, lower),
            )
        )
        filters.append(dict(column=measure, operator="lte", value=_text(lower)))
        sides.append(f"{count} at or below {_text(lower)}")
    stats = _summary(values)
    return Card(
        f"outlier:{measure}",
        "outlier",
        f"Unusual {measure} values",
        (
            f"{total} of {len(values)} {measure} values are unusually far from the median "
            f"({_readable(median)}{_unit(unit)}): {' and '.join(sides)}.",
            "Unusual means far from typical values in this file, not necessarily wrong.",
        ),
        (
            _evidence("Unusual rows", str(total)),
            _evidence("Median", _text(median), unit),
            _evidence("Method", str(result["method"]).upper()),
            _evidence("Threshold", _text(Decimal(result["threshold"]))),
        ),
        dict(
            type="box",
            title=f"{measure} spread and unusual values",
            x=dict(field="label", label="Measure", unit=None),
            y=dict(field="median", label=measure, unit=unit),
            rows=[
                dict(
                    label=measure,
                    low=_text(stats["minimum"]),
                    q1=_text(stats["q1"]),
                    median=_text(stats["median"]),
                    q3=_text(stats["q3"]),
                    high=_text(stats["maximum"]),
                )
            ],
            outliers=[dict(value=_text(value), count=str(count)) for value, count in flagged[:50]],
        ),
        tuple(checks),
        (
            action(
                "investigate_outliers",
                f"Investigate {total} unusual {measure} rows",
                measure,
                type="anomalies",
                metric=measure,
                filters=filters,
            ),
        ),
        0.55 + min(0.3, total / len(values)),
    )


def analyse(
    context: DescriptionContext,
    selection: Selection,
    names: tuple[str, ...],
    rows: tuple[tuple[Scalar, ...], ...],
    correlations: Correlation,
    what_if: dict[str, str],
) -> tuple[list[Card], list[str]]:
    columns = {name: [row[index] for row in rows] for index, name in enumerate(names)}
    numbers = {
        name: [_number(value) for value in columns[name] if value is not None]
        for name in selection.measures
    }
    limitations: list[str] = []
    cards: list[Card] = [_quality(context, selection, columns)]
    lead = selection.measures[0] if selection.measures else None
    for category in selection.categories[:3]:
        card = _composition(category, columns[category], lead)
        if card:
            cards.append(card)
    for measure in selection.measures[:3]:
        card = _distribution(context, measure, numbers[measure], selection.units[measure], what_if)
        if card:
            cards.append(card)
    segments = []
    for measure in selection.segment_measures:
        values = numbers[measure]
        spread = max(values) - min(values) if values else Decimal(0)
        options = [
            found
            for category in selection.categories
            if (
                found := _segment(
                    measure,
                    category,
                    list(zip(columns[category], columns[measure], strict=True)),
                    selection.units[measure],
                    spread,
                )
            )
        ]
        if options:
            segments.append(max(options, key=lambda item: item[0]))
    cards.extend(card for _, card in sorted(segments, key=lambda item: -item[0])[:3])
    if len(selection.measures) >= 2:
        card = _relationship(selection.measures, columns, correlations)
        if card:
            cards.append(card)
        else:
            limitations.append(
                f"Measure relationships need at least {MIN_PAIRS} complete rows "
                "with varying values."
            )
    outliers = []
    for measure in selection.measures:
        if len(set(numbers[measure])) > MAX_OUTLIER_DISTINCT:
            limitations.append(
                f"{measure}: the unusual-value check covers measures with at most "
                f"{MAX_OUTLIER_DISTINCT} distinct values."
            )
            continue
        card = _outlier(measure, numbers[measure], selection.units[measure])
        if card:
            outliers.append(card)
    cards.extend(sorted(outliers, key=lambda card: -card.score)[:2])
    return cards, limitations


def cross_check(cards: list[Card]) -> tuple[list[Card], list[dict[str, str]]]:
    kept, dropped = [], []
    for card in cards:
        failed = [check for check in card.checks if not check.agrees()]
        if failed:
            reason = (
                "The independent check could not run."
                if failed[0].secondary is None
                else "The independent check disagreed."
            )
            dropped.append(dict(id=card.id, reason=f"{failed[0].label}: {reason}"))
        else:
            kept.append(card)
    return kept, dropped


def deterministic_order(cards: list[Card]) -> list[Card]:
    return sorted(cards, key=lambda card: (-card.score, card.id))


def kpis(
    context: DescriptionContext, selection: Selection, rows_verified: bool
) -> list[dict[str, Any]]:
    profile = context.profile
    rows, width = profile["row_count"], profile["column_count"]
    cells = rows * width
    missing = sum(column["missing"] for column in profile["columns"])
    duplicates = next(
        (item["count"] for item in profile["quality_checks"] if item["code"] == "duplicate_rows"),
        0,
    )
    with localcontext() as decimal_context:
        decimal_context.prec = 50
        completeness = (
            format((Decimal(cells - missing) * 100 / cells).quantize(Decimal("0.1")), "f")
            if cells
            else "0.0"
        )
    return [
        dict(
            id="rows",
            label="Rows",
            value=str(rows),
            unit=None,
            detail="Checked by a separate count query."
            if rows_verified
            else "From the file profile.",
        ),
        dict(id="columns", label="Columns", value=str(width), unit=None, detail=""),
        dict(
            id="measures",
            label="Measures analysed",
            value=str(len(selection.measures)),
            unit=None,
            detail="",
        ),
        dict(
            id="categories",
            label="Categories analysed",
            value=str(len(selection.categories)),
            unit=None,
            detail="",
        ),
        dict(
            id="completeness",
            label="Complete cells",
            value=completeness,
            unit="%",
            detail=f"{missing} of {cells} cells are empty.",
        ),
        dict(
            id="duplicate_rows",
            label="Repeated rows",
            value=str(duplicates),
            unit=None,
            detail="",
        ),
    ]


def default_next_actions(cards: list[Card]) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    for card in cards:
        for item in card.actions:
            if item["kind"] != "ask" and item["id"] not in {entry["id"] for entry in chosen}:
                chosen.append(item)
                break
        if len(chosen) == 5:
            break
    return chosen
