"""Use case: Lets a new person tell Osalytix who they are once, so wording can adapt to them.

What it does: Fixes the skippable questionnaire, validates chosen answers and exposes the few
answers that may shape explanations; it never supplies numbers, filters or confirmed meanings.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from execplus.domain.ingestion import IngestionError

TEXT_LIMIT = 120


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    kind: str
    options: tuple[str, ...] = ()
    hint: str = ""


QUESTIONNAIRE: tuple[Question, ...] = (
    Question("preferred_name", "What should I call you?", "text", hint="A first name is enough."),
    Question(
        "role",
        "Which describes you best?",
        "single",
        (
            "Owner / founder",
            "Manager",
            "Analyst",
            "Finance",
            "Sales / marketing",
            "Operations",
            "Student / researcher",
            "Other",
        ),
    ),
    Question(
        "industry",
        "What industry do you work in?",
        "single",
        (
            "Retail",
            "Manufacturing",
            "Agriculture",
            "Finance",
            "Healthcare",
            "SaaS / tech",
            "Services",
            "Education",
            "Government / NGO",
            "Other",
        ),
    ),
    Question(
        "company_size",
        "How big is your organisation?",
        "single",
        ("Just me", "2-10 people", "11-50", "51-200", "201-1,000", "More than 1,000"),
    ),
    Question(
        "data_comfort",
        "How comfortable are you with data?",
        "single",
        (
            "New to data",
            "Comfortable with spreadsheets",
            "Analyst",
            "Data scientist",
        ),
    ),
    Question(
        "goals",
        "What do you want to get done?",
        "multi",
        (
            "Track KPIs",
            "Find problems early",
            "Forecast",
            "Compare segments",
            "Clean data",
            "Build reports for others",
            "Explore freely",
        ),
        "Pick as many as you like.",
    ),
    Question(
        "data_sources",
        "Where does your data live?",
        "multi",
        ("Excel / CSV", "Google Sheets", "Databases", "Accounting / ERP", "CRM", "Other"),
    ),
    Question(
        "typical_questions",
        "What do you usually ask about?",
        "multi",
        ("Totals & trends", "Rankings", "Comparisons", "Anomalies", "Forecasts", "Relationships"),
    ),
    Question(
        "decision_frequency",
        "How often do you make decisions from data?",
        "single",
        ("Daily", "Weekly", "Monthly", "Quarterly", "Rarely"),
    ),
    Question(
        "time_horizon",
        "How far ahead do you usually plan?",
        "single",
        ("Weeks", "Months", "Quarters", "Years"),
    ),
    Question(
        "answer_style",
        "How should answers be shaped?",
        "single",
        ("Short headline first", "Step by step", "Tables", "Charts first"),
    ),
    Question(
        "detail_level",
        "How much detail do you want?",
        "single",
        ("Just the answer", "Answer with short reasoning", "Full detail"),
    ),
    Question(
        "language",
        "Which language should I reply in?",
        "single",
        (
            "English",
            "Urdu or Roman Urdu",
            "Mixed",
            "Arabic",
            "Spanish",
            "French",
            "Chinese",
            "Hindi",
            "Another language",
        ),
    ),
    Question(
        "number_format",
        "How should numbers be shown?",
        "single",
        ("Plain", "With units and %", "Exact decimals"),
    ),
    Question(
        "chart_preference",
        "Which charts do you prefer?",
        "single",
        ("Bars", "Lines", "Tables instead of charts", "Let Osalytix choose"),
    ),
    Question(
        "next_steps",
        "Suggest next steps after each answer?",
        "single",
        ("Yes, please", "Only when I ask"),
    ),
    Question(
        "regions_currency",
        "Which regions or currency do you work in?",
        "text",
        hint="For example: Pakistan, PKR. Optional.",
    ),
    Question("anything_else", "Anything else I should know?", "text", hint="Optional."),
)
QUESTIONS = {question.id: question for question in QUESTIONNAIRE}
CONTEXT_KEYS = (
    "role",
    "industry",
    "goals",
    "answer_style",
    "detail_level",
    "language",
    "number_format",
)
STATUSES = ("completed", "skipped")


@dataclass(frozen=True)
class UserProfile:
    user_id: UUID
    version: int = 0
    preferred_name: str = ""
    answers: dict[str, Any] = field(default_factory=dict)
    completed_at: datetime | None = None
    skipped_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def status(self) -> str:
        if self.completed_at:
            return "completed"
        return "skipped" if self.skipped_at else "pending"

    def context(self) -> dict[str, Any]:
        chosen = {key: self.answers[key] for key in CONTEXT_KEYS if self.answers.get(key)}
        if self.preferred_name:
            chosen = {"preferred_name": self.preferred_name, **chosen}
        return chosen


def questionnaire() -> list[dict[str, Any]]:
    return [
        dict(id=q.id, prompt=q.prompt, kind=q.kind, options=list(q.options), hint=q.hint)
        for q in QUESTIONNAIRE
    ]


def _invalid(detail: str) -> IngestionError:
    return IngestionError("invalid_profile", detail, 422)


def validate_text(value: Any) -> str:
    if not isinstance(value, str) or len(value) > TEXT_LIMIT or any(ord(c) < 32 for c in value):
        raise _invalid(f"Use plain text up to {TEXT_LIMIT} characters.")
    return value.strip()


def validate_answers(answers: Any) -> dict[str, Any]:
    if not isinstance(answers, dict):
        raise _invalid("Answers must map question ids to chosen values.")
    kept: dict[str, Any] = {}
    for key, value in answers.items():
        question = QUESTIONS.get(key)
        if question is None or key == "preferred_name":
            raise _invalid("Unknown question.")
        if question.kind == "text":
            text = validate_text(value)
            if text:
                kept[key] = text
        elif question.kind == "single":
            if value not in question.options:
                raise _invalid(f"Choose one listed option for {key}.")
            kept[key] = value
        else:
            if not isinstance(value, list) or any(item not in question.options for item in value):
                raise _invalid(f"Choose listed options for {key}.")
            if value:
                kept[key] = list(dict.fromkeys(value))
    return kept
