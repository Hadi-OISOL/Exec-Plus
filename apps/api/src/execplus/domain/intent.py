"""Use case: Interprets a model's proposed question classification and query plan.

What it does: Treats a language model's JSON response as untrusted input, validating
every proposed metric, dimension, and filter against the dataset's semantic view
before it can ever reach the query engine.
"""

import json
import math
import re
from dataclasses import dataclass
from typing import Any

from execplus.domain.guidance import GUIDANCE_FOCUSES, mentioned_columns, words
from execplus.domain.models import QuestionKind
from execplus.domain.semantics import (
    AggregationKind,
    DatasetView,
    FilterOperator,
    MetricFilter,
    MetricRequest,
    RowExtremum,
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


def _unsupported(message: str, issue: str = "") -> RoutedIntent:
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


def _parse_numerical(payload: dict[str, Any], view: DatasetView) -> RoutedIntent:
    plan = payload.get("plan")
    if not isinstance(plan, dict) or set(plan) - {"metric", "aggregation", "group_by", "filters"}:
        return _unsupported("The model did not propose a usable query plan.")
    metric = plan.get("metric")
    aggregation = plan.get("aggregation")
    group_by = plan.get("group_by") or []
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
    filters = _parse_filters(plan.get("filters") or [], view)
    if filters is None:
        return _unsupported("The model proposed an invalid filter.")
    request = MetricRequest(
        metric=metric,
        aggregation=AggregationKind(aggregation),
        group_by=tuple(group_by),
        filters=filters,
    )
    return RoutedIntent(QuestionKind.NUMERICAL, request=request)


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
        if not isinstance(plan, dict) or set(plan) - {"columns", "filters", "limit", "extremum"}:
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
        if (
            not isinstance(columns, list)
            or not all(isinstance(name, str) and view.column(name) for name in columns)
            or len(set(columns)) != len(columns)
            or filters is None
            or type(limit) is not int
            or not 1 <= limit <= 1000
        ):
            return _unsupported("The model proposed invalid record fields, filters or limit.")
        return RoutedIntent(kind, rows=RowRequest(filters, tuple(columns), extremum), limit=limit)
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
                    else "The conversational reply could not be validated."
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
    return _unsupported(str(fallback))


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
