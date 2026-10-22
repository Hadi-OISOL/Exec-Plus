"""Use case: Keeps requested work intact when conversational intent is interpreted.

What it does: Identifies bounded calculation, record and evidence requirements that
an overview cannot fulfill, without requiring explanation requests to match a phrase list.
"""

import re
from dataclasses import dataclass

from execplus.domain.context_retrieval import references_earlier_result
from execplus.domain.guidance import is_greeting, mentioned_columns, words
from execplus.domain.intent import RoutedIntent
from execplus.domain.models import CalculationLineage, QuestionKind
from execplus.domain.semantics import (
    PRODUCT_SIGN,
    DatasetView,
    FilterOperator,
    MetricRequest,
)
from execplus.domain.understanding import measure_unit


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
    return is_greeting(question) or words(question) in {
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


def asks_for_ideal_conditions(question: str) -> bool:
    """A desired outcome is needed; maximizing every input is not an objective."""
    return bool(
        re.search(
            r"\b(perfect|ideal|optimal|best)\b.{0,80}\bconditions?\b",
            words(question),
        )
    )


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


def is_temporal_followup(question: str) -> bool:
    return bool(re.fullmatch(r"(?:what about )?last year", words(question)))


def is_contextual_reply(question: str, view: DatasetView) -> bool:
    normalized = words(question)
    return (
        is_result_explanation(question)
        or references_earlier_result(question)
        or is_temporal_followup(question)
        or normalized in {words(column.name) for column in view.columns}
        or bool(
            re.match(
                r"^(and|also|then|their|its|same|by|what about|show me only|only|compare those)\b",
                normalized,
            )
        )
        or bool(re.match(r"^(break|split|divide) (it|this|that|these|those|them)\b", normalized))
        or bool(re.search(r"\b(it|this|that|these|those|them) (down |up )?(by|per)\b", normalized))
        or (
            len(normalized.split()) <= 6
            and bool(re.match(r"^(when|where|which|who|why|how)\b", normalized))
            and bool(re.search(r"\b(they|them|it|those|these)\b", normalized))
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
        or re.search(r"\bdoes\b.*\bmean\b|\bdo\s+(?:you|u)\b.*\bmean\b", residual)
    )
    operations = (
        r"\b(totals?|sums?|averages?|avg|counts?|minimums?|maximums?|min|max|calculate|compute)\b"
    )
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
        (
            not definition
            and re.search(r"\b(filters?|filtered|excluding|exclude|except)\b", residual)
        )
        or re.search(r"\bfilter\s+(?:to|by|out|the|these|rows?|records?)\b", residual)
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
        r"\b(totals?|sums?|averages?|avg|counts?|minimums?|maximums?|min|max|highest|lowest)\b",
        normalized,
    )
    return len(named) > 1 or len(operations) > 1


def preserves_followup_scope(
    question: str, intent: RoutedIntent, prior: CalculationLineage, view: DatasetView
) -> bool:
    """Allow explicit changes while refusing an accidentally broadened continuation."""
    if intent.kind == QuestionKind.NUMERICAL and intent.request is not None:
        filters = intent.request.filters
        metric, aggregation, groups = (
            intent.request.label,
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
            re.search(
                r"\b(totals?|sums?|averages?|avg|mean|counts?|min|minimums?|max|maximums?)\b",
                normalized,
            )
        )
        if aggregation != prior.aggregation and not explicit_operation:
            return False
        dropped = set(prior.grouping) - set(groups)
        narrowed = {
            item.column
            for item in filters
            if item.operator in (FilterOperator.EQ, FilterOperator.IEQ)
        }
        regrouped = bool((set(groups) & named) - set(prior.grouping))
        if (
            dropped
            and not (dropped <= narrowed or regrouped)
            and not re.search(r"\b(overall|ungrouped|without grouping|across all)\b", normalized)
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
    covered = {request.metric for request in requests}
    operations = {request.aggregation.value for request in requests}
    for step in intent.data_steps:
        if step.rows is not None:
            covered.update(step.rows.columns or view.metrics)
            if step.rows.extremum is not None:
                covered.add(step.rows.extremum.column)
                operations.add(step.rows.extremum.direction)
    if not named <= covered:
        return False
    requested = {
        operation
        for expression, operation in (
            (r"\b(totals?|sums?)\b", "sum"),
            (r"\b(averages?|avg|mean)\b", "avg"),
            (r"\bcounts?\b", "count"),
            (r"\b(minimums?|min|lowest)\b", "min"),
            (r"\b(maximums?|max|highest)\b", "max"),
        )
        if re.search(expression, normalized)
    }
    return requested <= operations and _compound_pairs_match(question, intent, view)


def _compound_pairs_match(question: str, intent: RoutedIntent, view: DatasetView) -> bool:
    operations = (
        (r"\b(totals?|sums?)\b", "sum"),
        (r"\b(averages?|avg|mean)\b", "avg"),
        (r"\bcounts?\b", "count"),
        (r"\b(minimums?|min|lowest)\b", "min"),
        (r"\b(maximums?|max|highest)\b", "max"),
    )
    normalized = " " + words(question) + " "
    aliases: dict[str, str] = {}
    for index, column in enumerate(
        sorted(view.columns, key=lambda col: len(words(col.name)), reverse=True)
    ):
        alias = f"columnref{index}"
        label = " " + words(column.name) + " "
        if label in normalized:
            normalized = normalized.replace(label, " " + alias + " ")
            aliases[alias] = column.name
    performed = set()
    for step in intent.data_steps:
        if step.request is not None:
            performed.add((step.request.metric, step.request.aggregation.value, "numerical"))
        if step.rows is not None and step.rows.extremum is not None:
            performed.add((step.rows.extremum.column, step.rows.extremum.direction, "rows"))
    global_metrics = set(aliases.values()) & set(view.metrics)
    global_operations = {
        name for expression, name in operations if re.search(expression, normalized)
    }
    for clause in re.split(r"\b(?:and|also|plus|then)\b", normalized):
        selected = {name for expression, name in operations if re.search(expression, clause)}
        fields = {
            name for alias, name in aliases.items() if re.search(r"\b" + alias + r"\b", clause)
        }
        row_request = bool(re.search(r"\b(records?|rows?|which|who)\b", clause))
        if not selected:
            if not row_request and len(global_operations) == 1 and global_operations != {"count"}:
                selected = global_operations
            else:
                continue
        if len(selected) != 1:
            return False
        operation = next(iter(selected))
        if operation == "count" and (row_request or not fields):
            targets = {"*"}
        elif operation == "count":
            targets = fields
        else:
            targets = fields & set(view.metrics)
            if not targets and len(global_metrics) == 1:
                targets = global_metrics
            if not targets:
                return False
        kind = "rows" if row_request and operation in {"min", "max"} else "numerical"
        if not {(name, operation, kind) for name in targets} <= performed:
            return False
    return True


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def loosely_named_metrics(question: str, view: DatasetView) -> tuple[str, ...]:
    """Measures whose distinctive name words appear in the question, e.g. purchase -> purchases."""
    asked = {_stem(word) for word in words(question).split()}
    return tuple(
        name
        for name in sorted(view.metrics)
        if any(len(token) > 3 and _stem(token) in asked for token in words(name).split())
    )


def asks_derived_measure(
    question: str, metric: str, aggregation: str, grouped: bool, view: DatasetView
) -> bool:
    """A rate, ratio or difference needs arithmetic between results, not one aggregate."""
    field_words = {token for column in view.columns for token in words(column.name).split()}
    text = " ".join(word for word in words(question).split() if word not in field_words)
    if re.search(
        r"\b(minus|subtract|subtracted|net|divided by|margin)\b|\bdifference between\b", text
    ):
        return True

    def stems(names: frozenset[str]) -> set[str]:
        return {_stem(token) for name in names for token in words(name).split()}

    metric_stems, dimension_stems = stems(view.metrics), stems(view.dimensions)
    for match in re.finditer(r"\bper (\w+)", words(question)):
        stem = _stem(match.group(1))
        if stem in metric_stems and stem not in dimension_stems:
            return True
    if not (re.search(r"\b(rate|ratio|percentage|percent|proportion)\b", text) or "%" in question):
        return False
    if metric == "*":
        return aggregation == "count" and not grouped
    return aggregation in {"sum", "min", "max"}


_VALUE_WORDS = r"\b(value|valuation|worth|revenue|turnover|gmv)\b"
_QUANTITY_WORDS = frozenset(
    {"unit", "units", "qty", "quantity", "quantities", "stock", "hand", "pieces", "items", "sold"}
)
_PRICE_WORDS = frozenset({"price", "cost", "rate"})


def product_choices(question: str, request: MetricRequest, view: DatasetView) -> tuple[str, ...]:
    """Offer quantity times price when a named value (e.g. inventory value) is not a field."""
    field_words = {token for column in view.columns for token in words(column.name).split()}
    text = " ".join(word for word in words(question).split() if word not in field_words)
    if (
        request.times is not None
        or request.aggregation.value not in ("sum", "avg")
        or request.metric not in view.metrics
        or not re.search(_VALUE_WORDS, text)
        or measure_unit(view.definition, request.metric)[1]
        or not _QUANTITY_WORDS & set(words(request.metric).split())
    ):
        return ()
    priced = [
        name
        for name in sorted(view.metrics)
        if name != request.metric
        and (measure_unit(view.definition, name)[1] or _PRICE_WORDS & set(words(name).split()))
    ]
    group = f" by {request.group_by[0]}" if len(request.group_by) == 1 else ""
    operation = "total" if request.aggregation.value == "sum" else "average"
    return (
        (
            *(
                f"What is the {operation} of {request.metric}{PRODUCT_SIGN}{name}{group}?"
                for name in priced[:3]
            ),
            f"What is the {operation} of {request.metric}{group}?",
        )
        if priced
        else ()
    )


_ADVICE = (
    r"\bwhat (should|can|could|do|must) (i|we|you|hr|\w+) (do|focus on|work on|improve|change|"
    r"prioriti[sz]e|fix|look at)\b"
    r"|\bhow (can|do|should|could) (i|we) (grow|increase|improve|boost|raise|reduce|cut)\b"
    r"|\b(next steps?|action items?|what do you recommend|what would you recommend|"
    r"any recommendations?|where should (i|we) focus)\b"
    r"|\bkya karna chahiye\b|\bkya karun\b|\bkya karein\b|\bkya karen\b"
)


def asks_for_next_steps(question: str) -> bool:
    """An open request for what to do next, answered with grounded analyst findings."""
    text = words(question)
    return bool(re.search(_ADVICE, text)) and not re.search(r"\bwhat should i ask\b", text)
