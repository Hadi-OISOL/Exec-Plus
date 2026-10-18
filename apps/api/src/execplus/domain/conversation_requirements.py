"""Use case: Keeps requested work intact when conversational intent is interpreted.

What it does: Identifies bounded calculation, record and evidence requirements that
an overview cannot fulfill, without requiring explanation requests to match a phrase list.
"""

import re
from dataclasses import dataclass

from execplus.domain.guidance import mentioned_columns, words
from execplus.domain.intent import RoutedIntent
from execplus.domain.models import CalculationLineage, QuestionKind
from execplus.domain.semantics import DatasetView


def is_guidance_followup(question: str) -> bool:
    return words(question) in {
        "",
        "what",
        "what do you mean",
        "what does it mean",
        "what does that mean",
        "explain that",
        "explain again",
        "i don t understand",
        "i dont understand",
        "i do not understand",
        "can you explain again",
        "tell me more",
        "make it simpler",
        "explain simply",
        "explain that simply",
        "explain it simply",
        "explain the result",
        "what does this result mean",
    }


def is_acknowledgement(question: str) -> bool:
    return words(question) in {
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank you",
        "thank you so much",
        "ok thanks",
        "okay thanks",
        "shukriya",
    }


def starts_new_orientation(
    question: str, columns: tuple[str, ...] = (), focus: str = "orientation"
) -> bool:
    return (
        not columns
        and focus == "orientation"
        and not is_guidance_followup(question)
        and not is_acknowledgement(question)
    )


@dataclass(frozen=True, slots=True)
class RequestRequirements:
    calculation: bool = False
    records: bool = False
    row_scope: bool = False
    documents: bool = False
    artifact: bool = False
    analysis: bool = False

    @property
    def needs_data_selection(self) -> bool:
        return self.calculation or self.records or self.row_scope

    @property
    def overview_conflicts(self) -> bool:
        return self.needs_data_selection or self.documents or self.artifact or self.analysis


def is_result_explanation(question: str) -> bool:
    return is_guidance_followup(question) or words(question) in {
        "why",
        "why is that",
        "why might that be",
        "why did that happen",
        "what caused that",
        "explain those results",
        "compare those two",
    }


def is_contextual_reply(question: str, view: DatasetView) -> bool:
    normalized = words(question)
    return (
        is_result_explanation(question)
        or normalized in {words(column.name) for column in view.columns}
        or bool(
            re.match(
                r"^(and|also|then|their|its|same|by|what about|show me only|only|compare those)\b",
                normalized,
            )
        )
    )


def request_requirements(question: str, view: DatasetView) -> RequestRequirements:
    normalized = words(question)
    named = mentioned_columns(question, view)
    residual = " " + normalized + " "
    for name in sorted(named, key=lambda value: len(words(value)), reverse=True):
        residual = residual.replace(" " + words(name) + " ", " ")
    definition = bool(
        re.search(r"\b(meaning|definition|means|represents|stands for)\b", residual)
        or re.search(r"\bdoes\b.*\bmean\b", residual)
    )
    operations = r"\b(total|sum|average|avg|count|minimum|maximum|min|max|calculate|compute)\b"
    calculation = bool(
        re.search(operations, residual)
        or (not definition and re.search(r"\bmean\b", residual))
        or re.search(r"\b(how many|how much|work out|add up)\b", residual)
        or re.search(r"[+*/=<>]|(?<!\w)-(?!\w)", question)
        or (set(named) & set(view.metrics) and re.search(r"\b(by|per)\b", residual))
    )
    records = bool(
        re.search(r"\b(show|list|find|display|fetch|get|return)\b.*\b(rows?|records?)\b", residual)
        or re.search(r"\b(first|last|top|bottom)\s+\d+\b", residual)
    )
    row_scope = bool(
        re.search(r"\b(filters?|filtered|excluding|exclude|except)\b", residual)
        or re.search(
            r"\b(where|only)\s+(?!the\s+(?:data|file)\b|this\s+(?:data|file)\b)\S+", residual
        )
        or re.search(r"\b(since|before|after|between)\s+\S+", residual)
        or re.search(r"[<>]=?|!=|==", question)
        or (
            not definition
            and set(named) & set(view.dimensions)
            and re.search(r"\b(for|in)\s+(?!(?:this|the|my|our|a|an)\b)\S+", residual)
        )
    )
    return RequestRequirements(
        calculation=calculation,
        records=records,
        row_scope=row_scope,
        documents=bool(re.search(r"\b(documents?|policy|contract|according|passage)\b", residual)),
        artifact=bool(
            re.search(r"\b(diagram|flowchart|chart|graph|plot|pdf|export|download)\b", residual)
        ),
        analysis=bool(
            re.search(
                r"\b(compare|comparison|correlation|causes?|caused|predict|forecast)\b", residual
            )
        ),
    )


def requires_compound_data(question: str, view: DatasetView) -> bool:
    normalized = words(question)
    if not re.search(r"\b(and|also|plus|then)\b", normalized):
        return False
    named = set(mentioned_columns(question, view)) & set(view.metrics)
    operations = re.findall(
        r"\b(total|sum|average|avg|count|minimum|maximum|min|max)\b", normalized
    )
    return len(named) > 1 or len(operations) > 1


def preserves_followup_scope(
    question: str, intent: RoutedIntent, prior: CalculationLineage, view: DatasetView
) -> bool:
    """Allow explicit changes while refusing an accidentally broadened continuation."""
    if intent.kind == QuestionKind.NUMERICAL and intent.request is not None:
        filters = intent.request.filters
        metric, aggregation, groups = (
            intent.request.metric,
            intent.request.aggregation.value,
            intent.request.group_by,
        )
    elif intent.kind == QuestionKind.ROWS and intent.rows is not None:
        filters = intent.rows.filters
        metric, aggregation, groups = "", "rows", ()
    else:
        return True
    normalized = words(question)
    named = set(mentioned_columns(question, view))
    rendered = {f"{item.column} {item.operator.value} {item.value!r}" for item in filters}
    temporal = bool(
        re.search(r"\b(year|month|week|day|yesterday|today|before|after|since)\b", normalized)
    )
    for previous in prior.filters:
        if previous in rendered:
            continue
        column = next((col for col in view.columns if previous.startswith(col.name + " ")), None)
        if column is None:
            return False
        replacements = [item for item in filters if item.column == column.name]
        explicit_value = any(
            words(str(item.value)) and words(str(item.value)) in normalized for item in replacements
        )
        if not replacements or not (
            column.name in named or explicit_value or (temporal and column.type == "date")
        ):
            return False
    if prior.aggregation != "rows" and aggregation != "rows":
        if metric != prior.metric and metric not in named:
            return False
        explicit_operation = bool(
            re.search(r"\b(total|sum|average|avg|mean|count|min|minimum|max|maximum)\b", normalized)
        )
        if aggregation != prior.aggregation and not explicit_operation:
            return False
        if not set(prior.grouping) <= set(groups) and not re.search(
            r"\b(overall|ungrouped|without grouping|across all)\b", normalized
        ):
            return False
    return True


def compound_covers_request(question: str, intent: RoutedIntent, view: DatasetView) -> bool:
    normalized = words(question)
    if re.search(
        r"\b(ratio|percentage|difference|subtract|divide|multiply|using the result|"
        r"using that|then use|above average|below average)\b",
        normalized,
    ):
        return False
    requests = [step.request for step in intent.data_steps if step.request is not None]
    named = set(mentioned_columns(question, view)) & set(view.metrics)
    if not named <= {request.metric for request in requests}:
        return False
    requested = {
        operation
        for expression, operation in (
            (r"\b(total|sum)\b", "sum"),
            (r"\b(average|avg|mean)\b", "avg"),
            (r"\bcount\b", "count"),
            (r"\b(minimum|min)\b", "min"),
            (r"\b(maximum|max)\b", "max"),
        )
        if re.search(expression, normalized)
    }
    return requested <= {request.aggregation.value for request in requests}
