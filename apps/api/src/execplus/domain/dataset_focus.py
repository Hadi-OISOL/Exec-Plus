"""Use case: Asks a few short questions about one file so later answers follow what you want.

What it does: Builds three to five deterministic follow-up questions from the file's measures,
groups, dates and ranking fields, validates the chosen answers and turns them into column and
time-view preferences that order insights, suggested questions and the dashboard. Answers never
become filters, numbers, permissions or confirmed meanings.
"""

from dataclasses import replace
from typing import Any

from execplus.domain.discovery import category_candidates, measure_candidates
from execplus.domain.exploration_selection import suggested_aggregation
from execplus.domain.goal_ranking import LEVELS, WANTS, ranking_fields
from execplus.domain.guidance import DescriptionContext
from execplus.domain.ingestion import IngestionError
from execplus.domain.semantics import DatasetView

VERSION = "dataset-focus-v1"
STATUSES = ("completed", "skipped")
MAX_QUESTIONS = 5
MAX_OPTIONS = 6
TEXT_LIMIT = 120
GRAINS = {
    "Day by day": "day",
    "Week by week": "week",
    "Month by month": "month",
    "Quarter by quarter": "quarter",
    "Year by year": "year",
    "No time view": "",
}
DECISIONS = ("Where to focus effort", "What to fix first", "How to plan ahead", "Just exploring")
RELATIONS = (
    "I run or own this",
    "I analyse it for someone else",
    "I appear in it",
    "Just exploring",
)


def _question(
    id: str, prompt: str, kind: str, options: tuple[str, ...] | list[str], hint: str = ""
) -> dict[str, Any]:
    return dict(id=id, prompt=prompt, kind=kind, options=list(options), hint=hint)


def questions(context: DescriptionContext, labels: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """Questions shaped by this file's own columns; a question without options is left out."""
    plain = replace(context, focus={})
    view = context.view
    ranking = ranking_fields(view)
    measures = measure_candidates(plain)
    categories = category_candidates(plain)
    dated = any(column.type == "date" or column.has_time for column in view.columns)
    found: list[dict[str, Any]] = []
    if ranking is not None:
        found.append(
            _question(
                "persona",
                "What do you do? Your trade or main skills",
                "text",
                labels,
                "For example: mechanic, car repair",
            )
        )
        found.append(_question("level", "How experienced are you in that work?", "single", LEVELS))
        found.append(_question("want", "What do you want from these records?", "single", WANTS))
        found.append(
            _question(
                "measure", "Which score should decide what is best?", "single", ranking.scores
            )
        )
        categories = [name for name in categories if name not in ranking.labels]
    elif measures:
        found.append(
            _question(
                "measure", "Which number matters most to you?", "single", measures[:MAX_OPTIONS]
            )
        )
    if categories:
        found.append(
            _question(
                "segment",
                "Which group do you want to compare?",
                "single",
                categories[:MAX_OPTIONS],
            )
        )
    if ranking is None:
        if dated:
            found.append(
                _question(
                    "time", "How do you want to follow it over time?", "single", tuple(GRAINS)
                )
            )
        found.append(
            _question(
                "decision",
                "What decision should this data help with?",
                "text",
                DECISIONS,
                "Pick one or write your own.",
            )
        )
        found.append(
            _question("relation", "How are you connected to this data?", "single", RELATIONS)
        )
    return found[:MAX_QUESTIONS]


def _invalid(detail: str) -> IngestionError:
    return IngestionError("invalid_focus", detail, 422)


def validate(asked: list[dict[str, Any]], answers: Any, status: Any) -> dict[str, str]:
    if status not in STATUSES:
        raise _invalid("Choose completed or skipped.")
    if not isinstance(answers, dict):
        raise _invalid("Answers must map question ids to chosen values.")
    known = {item["id"]: item for item in asked}
    kept: dict[str, str] = {}
    for key, value in answers.items():
        item = known.get(key)
        if item is None:
            raise _invalid("Unknown question for this file.")
        if item["kind"] == "single":
            if value not in item["options"]:
                raise _invalid(f"Choose one listed option for {key}.")
            kept[key] = value
            continue
        if not isinstance(value, str) or len(value) > TEXT_LIMIT or any(ord(c) < 32 for c in value):
            raise _invalid(f"Use plain text up to {TEXT_LIMIT} characters.")
        if value.strip():
            kept[key] = value.strip()
    return kept


def grain(focus: dict[str, str]) -> str:
    return GRAINS.get(focus.get("time", ""), "")


def planner_hint(focus: dict[str, str], view: DatasetView) -> dict[str, str]:
    """Only existing column names and a fixed time-view label; never free text."""
    names = {column.name for column in view.columns}
    hint = {key: focus[key] for key in ("measure", "segment") if focus.get(key) in names}
    if focus.get("time") in GRAINS:
        hint["time"] = focus["time"]
    return hint


def focused_questions(
    focus: dict[str, str], view: DatasetView, scores: tuple[str, ...] = ()
) -> list[dict[str, str]]:
    names = {column.name for column in view.columns}
    measure = focus.get("measure") if focus.get("measure") in names else None
    segment = focus.get("segment") if focus.get("segment") in names else None
    if measure:
        op = "average" if measure in scores or suggested_aggregation(measure) == "avg" else "total"
        if segment:
            return [
                dict(
                    title=f"Which {segment} leads on {measure}",
                    question=f"Which {segment} has the highest {op} {measure}?",
                )
            ]
        return [dict(title=f"Your {measure}", question=f"What is the {op} {measure}?")]
    if segment:
        return [
            dict(title=f"Records by {segment}", question=f"Which {segment} has the most records?")
        ]
    return []
