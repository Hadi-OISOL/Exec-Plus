"""Use case: Keeps requested work intact when conversational intent is interpreted.

What it does: Identifies bounded calculation, record and evidence requirements that
an overview cannot fulfill, without requiring explanation requests to match a phrase list.
"""

import re
from dataclasses import dataclass

from execplus.domain.guidance import mentioned_columns, words
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


def is_contextual_reply(question: str, view: DatasetView) -> bool:
    normalized = words(question)
    return (
        is_guidance_followup(question)
        or normalized in {words(column.name) for column in view.columns}
        or bool(re.match(r"^(and|also|then|their|its|same|by)\b", normalized))
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
