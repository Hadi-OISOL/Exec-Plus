"""Use case: Derives reusable starter questions from a dataset's authorized profile.

What it does: Turns KPI matches and recommended dimensions into example questions,
deterministically and without any model call.
"""

from execplus.domain.kpi_library import compatible_kpis
from execplus.domain.semantics import (
    DatasetView,
    recommend_breakdown_dimension,
    recommend_trend_dimension,
)


def suggested_questions(view: DatasetView, limit: int = 6) -> tuple[str, ...]:
    matches = compatible_kpis(view)
    questions = [f"What is the {match.definition.name.lower()}?" for match in matches]

    primary = matches[0].definition.name.lower() if matches else None
    trend_dimension = recommend_trend_dimension(view)
    if primary and trend_dimension:
        questions.append(f"How has {primary} changed over {trend_dimension}?")
    breakdown_dimension = recommend_breakdown_dimension(view)
    if primary and breakdown_dimension:
        questions.append(f"What is {primary} by {breakdown_dimension}?")

    seen: set[str] = set()
    unique: list[str] = []
    for question in questions:
        if question not in seen:
            seen.add(question)
            unique.append(question)
    return tuple(unique[:limit])
