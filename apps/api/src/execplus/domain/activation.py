"""Use case: Defines evidence-based observations and privacy-safe activation records.

What it does: Ranks profile facts and calculates comparisons without model arithmetic.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID

from execplus.domain.errors import UnsupportedQuestionError
from execplus.domain.profiling import Revision


@dataclass(frozen=True)
class Feedback:
    id: UUID
    workspace_id: UUID
    actor_id: UUID
    feature: str
    rating: int
    category: str
    release: str
    created_at: datetime


@dataclass(frozen=True)
class ReportSchedule:
    id: UUID
    workspace_id: UUID
    owner_id: UUID
    item_id: UUID
    interval_hours: int
    next_due: datetime
    enabled: bool
    created_at: datetime


@dataclass(frozen=True)
class ReportDelivery:
    id: UUID
    workspace_id: UUID
    schedule_id: UUID
    due_at: datetime
    status: str
    created_at: datetime


def observations(revision: Revision) -> list[dict[str, object]]:
    data = revision.profile
    checks = data["quality_checks"]
    assert isinstance(checks, list)
    ordered = sorted(checks, key=lambda check: (-check["count"], check["code"]))
    facts: list[dict[str, object]] = []
    for check in ordered:
        if check["count"]:
            facts.append(
                {
                    "code": check["code"],
                    "text": (
                        f"{check['code'].replace('_', ' ')}: "
                        f"{check['count']} of {check['denominator']}."
                    ),
                    "next_step": check["explanation"],
                    "evidence": {"revision_id": str(revision.id), "field": check["code"]},
                }
            )
    facts.extend(
        [
            {
                "code": "coverage",
                "text": f"{data['row_count']} rows across {data['column_count']} columns.",
                "next_step": "Review the profile before interpreting totals.",
                "evidence": {"revision_id": str(revision.id), "field": "row_count,column_count"},
            },
            {
                "code": "quality",
                "text": f"Data quality score: {data['quality_score']} out of 100.",
                "next_step": "Inspect quality checks and preview any cleaning changes.",
                "evidence": {"revision_id": str(revision.id), "field": "quality_score"},
            },
            {
                "code": "provenance",
                "text": "This profile is linked to a retained, checksum-verified source.",
                "next_step": "Open a recommended dashboard to explore verified results.",
                "evidence": {"revision_id": str(revision.id), "field": "source_checksum"},
            },
        ]
    )
    return [
        dict(fact, rank=index + 1, algorithm="observations-v1")
        for index, fact in enumerate(facts[:3])
    ]


def comparison(
    current: object, previous: object, current_id: UUID, previous_id: UUID
) -> dict[str, Any]:
    if not isinstance(current, (Decimal, int)) or not isinstance(previous, (Decimal, int)):
        raise UnsupportedQuestionError("Choose two comparable scalar numerical executions.")
    with localcontext() as context:
        context.prec = 80
        delta = Decimal(current) - Decimal(previous)
        percent = (
            (delta / abs(Decimal(previous)) * 100).quantize(Decimal("0.01")) if previous else None
        )
    return {
        "observation": (
            f"The result changed from {previous} to {current}; the difference is {delta}."
        ),
        "interpretation": "This comparison does not establish why the change occurred.",
        "delta": str(delta),
        "percent_change": str(percent) if percent is not None else None,
        "percent_note": "Relative to the absolute previous value; undefined for a zero baseline.",
        "evidence_ids": [str(previous_id), str(current_id)],
        "algorithm": "comparison-v1",
    }
