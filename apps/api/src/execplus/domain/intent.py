"""Use case: Interprets a model's proposed question classification and query plan.

What it does: Treats a language model's JSON response as untrusted input, validating
every proposed metric, dimension, and filter against the dataset's semantic view
before it can ever reach the query engine.
"""

import json
import math
import re
from dataclasses import dataclass, replace
from typing import Any, cast

from execplus.domain.guidance import GUIDANCE_FOCUSES, mentioned_columns, words
from execplus.domain.models import QuestionKind
from execplus.domain.semantics import (
    RECORD_COUNT,
    TIME_PERIODS,
    AggregationKind,
    DatasetView,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    RowExtremum,
    RowOrder,
    RowRequest,
    supports_metric,
)

_AGGREGATIONS = {item.value for item in AggregationKind}
_OPERATORS = {item.value for item in FilterOperator}
_UNINTERPRETABLE = "The model response could not be interpreted."


@dataclass(frozen=True, slots=True)
class RoutedIntent:
    kind: QuestionKind
    request: MetricRequest | None = None
    options: tuple[str, ...] = ()
    message: str = ""
    rows: RowRequest | None = None
    limit: int = 100
    document_query: str = ""
    data_intent: "RoutedIntent | None" = None
    guide_columns: tuple[str, ...] = ()
    guide_focus: str = "orientation"
    validation_issue: str = ""
    target_column: str = ""
    target_value: str = ""
    data_steps: tuple["RoutedIntent", ...] = ()


INVALID_PLAN = "invalid_plan"


def _unsupported(message: str, issue: str = INVALID_PLAN) -> RoutedIntent:
    return RoutedIntent(QuestionKind.UNSUPPORTED, message=message, validation_issue=issue)


def _parse_filters(raw: Any, view: DatasetView) -> tuple[MetricFilter, ...] | None:
    if not isinstance(raw, list) or len(raw) > 20:
        return None
    filters = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        column, operator, value = item.get("column"), item.get("operator"), item.get("value")
        if (
            not isinstance(column, str)
            or view.column(column) is None
            or not isinstance(operator, str)
            or operator not in _OPERATORS
            or not isinstance(value, str | int | float | bool)
            or (isinstance(value, str) and (len(value) > 500 or "\x00" in value))
            or (isinstance(value, float) and not math.isfinite(value))
            or set(item) != {"column", "operator", "value"}
        ):
            return None
        filters.append(MetricFilter(column, FilterOperator(operator), value))
    return tuple(filters)


CONTRADICTORY_FILTERS = "contradictory_filters"


def contradictory_filters(filters: tuple[MetricFilter, ...]) -> str | None:
    """Return a field whose equality filters require two different values in one row."""
    seen: dict[str, str] = {}
    for item in filters:
        if item.operator not in (FilterOperator.EQ, FilterOperator.IEQ):
            continue
        value = str(item.value)
        if item.operator == FilterOperator.IEQ:
            value = value.casefold()
        if seen.setdefault(item.column, value) != value:
            return item.column
    return None


def _contradiction(filters: tuple[MetricFilter, ...]) -> RoutedIntent | None:
    column = contradictory_filters(filters)
    if column is None:
        return None
    return RoutedIntent(
        QuestionKind.UNSUPPORTED,
        options=(column,),
        message=f"Two different {column} values were required in the same row, "
        "so nothing could match.",
        validation_issue=CONTRADICTORY_FILTERS,
    )


def _parse_numerical(payload: dict[str, Any], view: DatasetView) -> RoutedIntent:
    plan = payload.get("plan")
    if not isinstance(plan, dict) or set(plan) - {
        "metric",
        "aggregation",
        "group_by",
        "filters",
        "order",
        "limit",
        "period",
        "times",
    }:
        return _unsupported("The model did not propose a usable query plan.")
    metric = plan.get("metric")
    aggregation = plan.get("aggregation")
    group_by = plan.get("group_by") or []
    order, limit = plan.get("order"), plan.get("limit")
    if (order is not None or limit is not None) and (
        order not in ("asc", "desc")
        or not group_by
        or (limit is not None and (type(limit) is not int or not 1 <= limit <= 1000))
    ):
        return _unsupported("Rank groups with order asc or desc and an optional limit of 1-1000.")
    if (
        not isinstance(metric, str)
        or not isinstance(aggregation, str)
        or aggregation not in _AGGREGATIONS
        or not supports_metric(view, metric, AggregationKind(aggregation))
        or not isinstance(group_by, list)
        or len(group_by) > 10
        or not all(isinstance(name, str) and name in view.dimensions for name in group_by)
    ):
        return _unsupported(
            "The model proposed an unsupported metric or dimension.",
            "count_plan" if aggregation == "count" else "",
        )
    period = plan.get("period")
    if period is not None and (
        period not in TIME_PERIODS
        or sum(1 for name in group_by if (column := view.column(name)) and column.type == "date")
        != 1
    ):
        return _unsupported("Use a calendar period only when grouping by one date field.")
    times = plan.get("times")
    if times is not None and (
        aggregation not in ("sum", "avg") or times not in view.metrics or times == metric
    ):
        return _unsupported("Multiply two different measures only inside a sum or average.")
    filters = _parse_filters(plan.get("filters") or [], view)
    if filters is None:
        return _unsupported("The model proposed an invalid filter.")
    if contradiction := _contradiction(filters):
        return contradiction
    request = MetricRequest(
        metric=metric,
        aggregation=AggregationKind(aggregation),
        group_by=tuple(group_by),
        filters=filters,
        order=order,
        limit=limit,
        period=period,
        times=times,
    )
    return RoutedIntent(QuestionKind.NUMERICAL, request=request)


_GRAINS = (
    ("day", r"\b(daily|days?|din)\b"),
    ("week", r"\b(weekly|weeks?|hafta|hafte)\b"),
    ("month", r"\b(monthly|months?|mahina|mahine|mahinay)\b"),
    ("quarter", r"\b(quarterly|quarters?)\b"),
    ("year", r"\b(yearly|annual|annually|years?|saal)\b"),
)
_WINDOW = (
    r"\b(last|this|next|previous|past|pichle|agle|over the|during the|across the|in the)"
    r"( \d+)? \w+"
)
_TREND = r"\b(trends?|trended|trending|over time|changed?|changes|over the)\b"
_RANKING = r"\b(highest|lowest|most|least|top|bottom|best|worst|max|min|maximum|minimum)\b"


_WEEKEND = r"\b(weekends?|week ends?|saturdays? and sundays?)\b"
_WEEKDAY = r"\b(days? of (the )?week|weekdays?|week days?)\b"
_DAY_NAMES = r"\b(mondays?|tuesdays?|wednesdays?|thursdays?|fridays?|saturdays?|sundays?)\b"


def _day_part(text: str, period: str | None) -> str | None:
    if re.search(_WEEKEND, text):
        return "weekend"
    named = re.search(_WEEKDAY, text) or (period is None and re.search(_DAY_NAMES, text))
    return "weekday" if named else None


_SUPERLATIVE = r"\b(highest|lowest|most|least|maximum|minimum|largest|smallest|biggest)\b"
_COMPARE = (
    r"\b(more|less|fewer|busier|busiest|quieter|quietest|compare|compared|comparison|vs|"
    r"versus|than|higher|lower|highest|lowest|most|least|difference|better|worse|best|worst)\b"
)


def per_day_request(question: str, request: MetricRequest | None) -> MetricRequest | None:
    """A weekday/weekend comparison of totals is misleading: compare the average per day."""
    if (
        request is None
        or request.period not in ("weekday", "weekend")
        or request.aggregation != AggregationKind.SUM
        or request.metric == RECORD_COUNT
        or not re.search(_COMPARE, words(question))
        or re.search(r"\b(total|totals|sum|overall)\b", words(question))
    ):
        return None
    return replace(request, aggregation=AggregationKind.AVG, per_day=True)


def with_time_grain(
    question: str, routed: RoutedIntent, view: DatasetView, inherited: str | None = None
) -> RoutedIntent:
    """Apply the calendar period and chronological order an explicit time question asks for."""
    request = routed.request
    if routed.kind != QuestionKind.NUMERICAL or request is None:
        return routed
    text = words(question)
    dated = [name for name in request.group_by if (c := view.column(name)) and c.type == "date"]
    part = _day_part(text, request.period)
    dates = sorted(
        name for name in view.dimensions if (c := view.column(name)) and c.type == "date"
    )
    if part and not dated and len(dates) == 1 and len(request.group_by) < 10:
        dated = [dates[0]]
        request = replace(request, group_by=(*request.group_by, dates[0]))
    if len(dated) != 1:
        return routed
    if part:
        return replace(routed, request=replace(request, period=cast(Any, part)))
    period = request.period
    if period is None:
        grains = re.sub(_WINDOW, " ", text)
        named = [grain for grain, pattern in _GRAINS if re.search(pattern, grains)]
        timed = bool((column := view.column(dated[0])) and column.has_time)
        if len(named) == 1 and (named[0] != "day" or timed):
            period = cast(Any, named[0])
        elif not named and inherited in TIME_PERIODS:
            period = cast(Any, inherited)
    order = request.order
    if (
        order is not None
        and request.limit is None
        and re.search(_TREND, text)
        and not re.search(_RANKING, text)
    ):
        order = None
    if (period, order) == (request.period, request.order):
        return routed
    return replace(routed, request=replace(request, period=period, order=order))


def with_extremum(question: str, routed: RoutedIntent, view: DatasetView) -> RoutedIntent:
    """'Which X has the highest Y' asks for every record at the extreme, ties included."""
    rows = routed.rows
    field_words = {token for column in view.columns for token in words(column.name).split()}
    text = " ".join(word for word in words(question).split() if word not in field_words)
    if (
        routed.kind != QuestionKind.ROWS
        or rows is None
        or rows.order_by is None
        or rows.extremum is not None
        or rows.order_by.column not in view.metrics
        or not re.search(r"\b(which|what|who)\b", text)
        or not re.search(_SUPERLATIVE, text)
        or re.search(r"\b(top|bottom|have|are|were|records|rows)\b|\d", text)
    ):
        return routed
    column = rows.order_by.column
    extremum = (
        RowExtremum(column, "max")
        if rows.order_by.direction == "desc"
        else RowExtremum(column, "min")
    )
    return replace(routed, rows=replace(rows, extremum=extremum, order_by=None))


def with_product(question: str, routed: RoutedIntent, view: DatasetView) -> RoutedIntent:
    """Apply a row-level product the question names explicitly, such as "units * unit_cost"."""
    request = routed.request
    if (
        routed.kind != QuestionKind.NUMERICAL
        or request is None
        or request.times is not None
        or request.aggregation not in (AggregationKind.SUM, AggregationKind.AVG)
    ):
        return routed
    for other in sorted(view.metrics - {request.metric}, key=len, reverse=True):
        for left, right in ((request.metric, other), (other, request.metric)):
            pattern = rf"(?<!\w){re.escape(left)}\s*(?:\u00d7|\*|\btimes\b|\bmultiplied by\b)\s*"
            if re.search(pattern + rf"{re.escape(right)}(?!\w)", question, re.IGNORECASE):
                return replace(routed, request=replace(request, metric=left, times=right))
    return routed


def _unverified_conversation_claims(message: str) -> bool:
    # This is a conservative claim boundary, not proof of arbitrary prose's truth.
    normalized = words(message)
    return bool(
        re.search(
            r"\b(?:i|we) (?:have |ve |just |already |now |successfully )*"
            r"(?:saved|updated|changed|remember|remembered|recall|recalled|retrieved|"
            r"analyzed|analysed|calculated|computed|checked|inspected|read|opened|loaded|"
            r"stored|recorded|deleted|cleared|sent|exported|executed|ran|completed|"
            r"finished|found|discovered|learned|learnt)\b",
            normalized,
        )
        or re.search(
            r"\b(?:private|confidential|personal) (?:goal|notes?|memory|preferences?|context)\b"
            r"|\byour (?:saved )?(?:goal|notes?|memory|preferences?)\b"
            r"|\b(?:data|dataset|file|records|results) (?:shows?|indicates?|suggests?|proves?)\b",
            normalized,
        )
    )


def _social_claims(message: str, view: DatasetView) -> bool:
    return bool(mentioned_columns(message, view) or _unverified_conversation_claims(message))


def _clarification_claims(message: str) -> bool:
    # Field names may explain an input; observations still need analytical evidence.
    return bool(
        _unverified_conversation_claims(message)
        or re.search(
            r"\b(?:doubled|tripled|increased|decreased|outperformed|correlated)\b"
            r"|\b(?:is|are|was|were) (?:the )?(?:highest|lowest|higher|lower|high|low)\b",
            words(message),
        )
    )


def route_response(raw: str, view: DatasetView) -> RoutedIntent:
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return _unsupported(_UNINTERPRETABLE)
    if not isinstance(payload, dict):
        return _unsupported(_UNINTERPRETABLE)

    if payload.get("kind") == "compound":
        steps = payload.get("steps")
        if (
            set(payload) != {"kind", "steps"}
            or not isinstance(steps, list)
            or len(steps) != 2
            or any(
                not isinstance(step, dict)
                or step.get("kind") not in {"numerical", "rows"}
                or set(step) != {"kind", "plan"}
                for step in steps
            )
        ):
            return _unsupported("Choose two independent calculations or record selections.")
        parsed = tuple(route_response(json.dumps(step), view) for step in steps)
        if any(step.kind not in {QuestionKind.NUMERICAL, QuestionKind.ROWS} for step in parsed):
            return _unsupported("Every compound step must be valid for the visible fields.")
        return RoutedIntent(QuestionKind.MIXED, data_steps=parsed)

    try:
        kind = QuestionKind(payload.get("kind"))
    except (ValueError, TypeError):
        return _unsupported(_UNINTERPRETABLE)

    if kind == QuestionKind.NUMERICAL:
        return _parse_numerical(payload, view)
    if kind == QuestionKind.COHORT_COMPARISON:
        target, value, columns = (
            payload.get("target_column"),
            payload.get("target_value"),
            payload.get("columns", []),
        )
        column = view.column(target) if isinstance(target, str) else None
        if (
            set(payload) - {"kind", "target_column", "target_value", "columns"}
            or column is None
            or column.type != "text"
            or target not in view.dimensions
            or "identifier" in column.tags
            or not isinstance(value, str)
            or not value.strip()
            or len(value) > 200
            or not isinstance(columns, list)
            or len(columns) > 12
            or not all(isinstance(name, str) and name in view.metrics for name in columns)
            or len(set(columns)) != len(columns)
        ):
            return _unsupported("Choose one visible category value and up to twelve measures.")
        return RoutedIntent(
            kind, guide_columns=tuple(columns), target_column=target, target_value=value
        )
    if kind == QuestionKind.PATTERNS:
        columns = payload.get("columns", [])
        if (
            set(payload) - {"kind", "columns"}
            or not isinstance(columns, list)
            or len(columns) > 12
            or len(set(map(str, columns))) != len(columns)
            or not all(
                isinstance(name, str)
                and (column := view.column(name)) is not None
                and "identifier" not in column.tags
                for name in columns
            )
        ):
            return _unsupported("Choose up to twelve existing fields to scan for patterns.")
        return RoutedIntent(kind, guide_columns=tuple(columns))
    if kind == QuestionKind.MIXED:
        if set(payload) != {"kind", "data", "document_query"}:
            return _unsupported("A combined request needs one data step and one document question.")
        query = payload["document_query"]
        data = payload["data"]
        if (
            not isinstance(query, str)
            or not query.strip()
            or len(query) > 500
            or not isinstance(data, dict)
            or data.get("kind") not in {"numerical", "rows"}
        ):
            return _unsupported("The combined plan is outside the supported bounds.")
        step = route_response(json.dumps(data), view)
        if step.kind not in {QuestionKind.NUMERICAL, QuestionKind.ROWS}:
            return step
        return RoutedIntent(kind, document_query=query.strip(), data_intent=step)
    if kind == QuestionKind.ROWS:
        plan = payload.get("plan")
        if not isinstance(plan, dict) or set(plan) - {
            "columns",
            "filters",
            "limit",
            "extremum",
            "order_by",
        }:
            return _unsupported("The model did not propose a usable record query.")
        columns = plan.get("columns", [])
        filters = _parse_filters(plan.get("filters", []), view)
        limit = plan.get("limit", 100)
        raw_extremum = plan.get("extremum")
        extremum = None
        if raw_extremum is not None:
            if (
                not isinstance(raw_extremum, dict)
                or set(raw_extremum) != {"column", "direction"}
                or not isinstance(raw_extremum["column"], str)
                or raw_extremum["column"] not in view.metrics
                or raw_extremum["direction"] not in ("min", "max")
            ):
                return _unsupported(
                    "Choose a visible numeric field for the highest or lowest records."
                )
            extremum = RowExtremum(raw_extremum["column"], raw_extremum["direction"])
        raw_order = plan.get("order_by")
        order_by = None
        if raw_order is not None:
            if (
                extremum is not None
                or not isinstance(raw_order, dict)
                or set(raw_order) != {"column", "direction"}
                or not isinstance(raw_order["column"], str)
                or raw_order["column"] not in view.metrics
                or raw_order["direction"] not in ("asc", "desc")
            ):
                return _unsupported("Order records by one visible numeric field, asc or desc.")
            order_by = RowOrder(raw_order["column"], raw_order["direction"])
        if (
            not isinstance(columns, list)
            or not all(isinstance(name, str) and view.column(name) for name in columns)
            or len(set(columns)) != len(columns)
            or filters is None
            or type(limit) is not int
            or not 1 <= limit <= 1000
        ):
            return _unsupported("The model proposed invalid record fields, filters or limit.")
        if contradiction := _contradiction(filters):
            return contradiction
        return RoutedIntent(
            kind, rows=RowRequest(filters, tuple(columns), extremum, order_by), limit=limit
        )
    if kind == QuestionKind.DIAGRAM:
        columns = payload.get("columns", [])
        if (
            set(payload) - {"kind", "columns"}
            or not isinstance(columns, list)
            or len(columns) > 80
            or not all(isinstance(name, str) and view.column(name) for name in columns)
            or len(set(columns)) != len(columns)
        ):
            return _unsupported("Choose up to eighty existing fields for a structure diagram.")
        return RoutedIntent(kind, guide_columns=tuple(columns))
    if kind == QuestionKind.OVERVIEW:
        columns = payload.get("columns", [])
        focus = payload.get("focus", "orientation")
        if focus == "conversation" or focus == "clarification":
            message = payload.get("message")
            if (
                set(payload) != {"kind", "focus", "columns", "message"}
                or columns != []
                or not isinstance(message, str)
                or not 1 <= len(message.strip()) <= (700 if focus == "clarification" else 400)
                or any(character.isdigit() or ord(character) < 32 for character in message)
                or re.search(r"https?://|www\.|[<>`\[\]{}]", message, re.IGNORECASE)
                or (
                    _clarification_claims(message)
                    if focus == "clarification"
                    else _social_claims(message, view)
                )
            ):
                return _unsupported(
                    "The clarification explanation could not be validated."
                    if focus == "clarification"
                    else "The conversational reply could not be validated.",
                    "",
                )
            return RoutedIntent(kind, message=message.strip(), guide_focus=focus)
        if (
            not isinstance(columns, list)
            or len(columns) > 3
            or not all(isinstance(name, str) and view.column(name) for name in columns)
            or len(set(columns)) != len(columns)
            or not isinstance(focus, str)
            or focus not in GUIDANCE_FOCUSES
        ):
            return _unsupported("Choose up to three existing columns to explain.")
        return RoutedIntent(kind, guide_columns=tuple(columns), guide_focus=focus)
    if kind == QuestionKind.AMBIGUOUS:
        options = payload.get("options")
        clean = tuple(str(option) for option in options) if isinstance(options, list) else ()
        message = str(payload.get("message") or "This question is ambiguous.")
        return RoutedIntent(QuestionKind.AMBIGUOUS, options=clean, message=message)
    if kind == QuestionKind.TEXTUAL:
        query = payload.get("query")
        if (
            isinstance(query, str)
            and query.strip()
            and len(query) <= 500
            and set(payload) == {"kind", "query"}
        ):
            return RoutedIntent(kind, document_query=query.strip())
        message = str(
            payload.get("message")
            or "This looks like a question needing a text answer, which isn't supported yet."
        )
        return RoutedIntent(QuestionKind.TEXTUAL, message=message)
    fallback = payload.get("message") or "This question is outside the supported scope."
    return _unsupported(str(fallback), "")


def canonical_cohort(question: str, view: DatasetView) -> RoutedIntent | None:
    quoted = r'("(?:[^"\\]|\\.)*")'
    match = re.fullmatch(
        r"Compare records where " + quoted + r" equals " + quoted + r" with other records\.?",
        question.strip(),
        re.IGNORECASE,
    )
    if match is None:
        return None
    try:
        target, value = (json.loads(part) for part in match.groups())
    except (ValueError, TypeError):
        return _unsupported("Choose an existing category and its exact value.")
    return route_response(
        json.dumps(
            {
                "kind": "cohort_comparison",
                "target_column": target,
                "target_value": value,
            }
        ),
        view,
    )


def canonical_records(question: str, view: DatasetView) -> RoutedIntent | None:
    quoted = r'("(?:[^"\\]|\\.)*")'
    match = re.fullmatch(
        r"Show records where " + quoted + r" equals " + quoted + r"\.?",
        question.strip(),
        re.IGNORECASE,
    )
    if match is None:
        return None
    try:
        column, value = (json.loads(part) for part in match.groups())
    except (ValueError, TypeError):
        return _unsupported("Choose an existing field and its exact value.")
    return route_response(
        json.dumps(
            {
                "kind": "rows",
                "plan": {
                    "filters": [{"column": column, "operator": "eq", "value": value}],
                    "limit": 100,
                },
            }
        ),
        view,
    )


def cohort_scope_needs_clarification(
    question: str, intent: RoutedIntent, view: DatasetView
) -> bool:
    if canonical_cohort(question, view) is not None:
        return False
    named = set(mentioned_columns(question, view))
    if named - {intent.target_column} - set(view.metrics):
        return True
    normalized = words(question)
    value = re.escape(words(intent.target_value))
    target = words(intent.target_column).split()
    # A terminal reference to the selected outcome field names what is being
    # studied, not which rows to include. Recognize only unique multiword field
    # spans (or the full name). Optional trailing replies can repeat the exact
    # field and then the exact selected category; no other predicate is consumed.
    # This does not supply or authorize a target category value.
    field_references = {
        " ".join(target[start:end])
        for start in range(len(target))
        for end in range(start + 2, len(target) + 1)
    } | {words(intent.target_column)}
    field_references = {
        alias
        for alias in field_references
        if sum(f" {alias} " in f" {words(column.name)} " for column in view.columns) == 1
    }
    if field_references:
        reference = (
            "(?:"
            + "|".join(
                re.escape(alias) for alias in sorted(field_references, key=len, reverse=True)
            )
            + ")"
        )
        normalized = re.sub(
            r"\b(?:in|of|on|for)\s+(?:the\s+)?"
            + reference
            + r"(?:\s+"
            + re.escape(words(intent.target_column))
            + r")?(?:\s+"
            + value
            + r")?\s*$",
            " ",
            normalized,
        )
    aliases = [" ".join(target[index:]) for index in range(len(target))]
    aliases = [
        alias
        for alias in aliases
        if sum(words(name).endswith(alias) for name in view.dimensions) == 1
    ]
    label = "(?:" + "|".join(re.escape(alias) for alias in aliases) + ")"
    normalized = re.sub(
        r"\b(?:where|with|whose|having|for|in|at)\s+(?:the\s+)?"
        + label
        + r"\s+(?:(?:is|equals|of|at)\s+)?"
        + value
        + r"\b",
        " ",
        normalized,
    )
    normalized = re.sub(
        r"\b(?:for|in|at)\s+(?:the\s+)?" + value + r"(?:\s+(?:stage|group|category))?\b",
        " ",
        normalized,
    )
    normalized = re.sub(
        r"\b(?:with|against|versus|from|than)\s+(?:the\s+)?other(?:s| records| groups)?\b",
        " ",
        normalized,
    )
    # Labels may themselves contain words such as 'after'; only residual request
    # words are interpreted as unsupported restrictions.
    for name in sorted(named | {intent.target_column}, key=len, reverse=True):
        normalized = normalized.replace(words(name), " ")
    normalized = normalized.replace(words(intent.target_value), " ")
    # A purpose phrase does not restrict rows; retain every word that follows it.
    normalized = re.sub(r"\bin order to\b", " ", normalized)
    return bool(
        re.search(
            r"\b(where|only|excluding|exclude|except|filters?|filtered|before|after|since|"
            r"between|last|next|past|days?|weeks?|months?|years?|in|from|during|within|"
            r"until|by|per|with|against|versus|vs|than|above|below|over|under|greater|less)\b",
            normalized,
        )
        or re.search(r"\b(?:at least|at most|compared to)\b", normalized)
        or re.search(r"[<>]=?|!=", question)
    )


_OPERATIONS = {
    "total": "sum",
    "average": "avg",
    "minimum": "min",
    "maximum": "max",
    "count": "count",
}


def canonical_question(question: str, view: DatasetView) -> RoutedIntent | None:
    """Plan the exact question templates this application offers, without a model."""
    names = sorted((column.name for column in view.columns), key=len, reverse=True)
    if not names:
        return None
    field = "(" + "|".join(re.escape(name) for name in names) + ")"
    operation = "(total|average|minimum|maximum|count)"
    exact = {name.casefold(): name for name in names}
    text = question.strip()

    def match(pattern: str) -> tuple[str, ...] | None:
        found = re.fullmatch(pattern + r"\s*[?.]?", text, re.IGNORECASE)
        return found.groups() if found else None

    def name(value: str) -> str:
        return exact[value.casefold()]

    def plan(kind: str, body: dict[str, Any]) -> RoutedIntent:
        return route_response(json.dumps({"kind": kind, **body}), view)

    def metric(
        op: str,
        measure: str,
        group: str | None,
        order: str | None = None,
        times: str = "",
        *,
        where: tuple[str, str] | None = None,
    ) -> RoutedIntent:
        body: dict[str, Any] = {
            "metric": name(measure),
            "aggregation": _OPERATIONS[op.casefold()],
            "group_by": [name(group)] if group else [],
        }
        if where:
            body["filters"] = [{"column": name(where[0]), "operator": "ieq", "value": where[1]}]
        if order:
            body["order"] = order
        if times:
            body["times"] = times
        return plan("numerical", {"plan": body})

    product = rf"(?:what is|show) the (total|average) of {field} \* {field}(?: by {field})?"
    if found := match(product):
        return metric(found[0], found[1], found[3], times=name(found[2]))
    if found := match(rf"(?:what is|show) the {operation} of {field}(?: by {field})?"):
        return metric(*found)
    if found := match(rf"(?:what is the|show|compare) {operation} {field}(?: by {field})?"):
        return metric(*found)
    if found := match(
        rf"which {field} has the (highest|lowest) {operation} {field}"
        rf"(?: where {field} equals (.{{1,200}}?))?"
    ):
        return metric(
            found[2],
            found[3],
            found[0],
            "desc" if found[1].casefold() == "highest" else "asc",
            where=(found[4], found[5]) if found[4] else None,
        )
    if found := match(rf"which {field} has the most records"):
        return plan(
            "numerical",
            {
                "plan": {
                    "metric": RECORD_COUNT,
                    "aggregation": "count",
                    "group_by": [name(found[0])],
                    "order": "desc",
                }
            },
        )
    if found := match(rf"how many records are there(?: by {field})?"):
        group = [name(found[0])] if found[0] else []
        return plan(
            "numerical",
            {"plan": {"metric": RECORD_COUNT, "aggregation": "count", "group_by": group}},
        )
    if found := match(rf"show (?:all )?records where {field} equals (.{{1,200}}?)"):
        filters = [{"column": name(found[0]), "operator": "eq", "value": found[1]}]
        return plan("rows", {"plan": {"columns": [], "filters": filters, "limit": 100}})
    if match(r"show the first 10 records") is not None:
        return plan("rows", {"plan": {"columns": [], "filters": [], "limit": 10}})
    if found := match(rf"does {field} relate to {field}"):
        return plan("patterns", {"columns": [name(found[0]), name(found[1])]})
    return None
