"""Use case: Produces an evidence-grounded narrative summary of a dashboard.

What it does: Asks a language model to describe already-executed results and rejects
any summary that states a number the executed evidence does not contain.
"""

from decimal import Decimal

from execplus.application.contracts import ModelMessage, ModelRequest
from execplus.application.ports import LanguageModel
from execplus.application.services.analytics import DashboardSummary
from execplus.domain.errors import UnverifiedAnswerError
from execplus.domain.models import ModelTier, Scalar
from execplus.domain.summary_guard import is_grounded

_SYSTEM_PROMPT = (
    "Write a two-sentence management summary of the figures below. State only what "
    "the figures show; never introduce a number that is not listed."
)


def _numeric_values(rows: tuple[tuple[object, ...], ...]) -> list[Decimal]:
    values: list[Decimal] = []
    for row in rows:
        for cell in row:
            if isinstance(cell, bool):
                continue
            if isinstance(cell, int | float | Decimal):
                values.append(Decimal(str(cell)))
    return values


def _evidence(summary: DashboardSummary) -> tuple[Decimal, ...]:
    values: list[Decimal] = []
    for card in summary.cards:
        values.extend(_numeric_values(card.result.rows))
    for breakdown in (summary.trend, summary.breakdown):
        if breakdown is not None:
            values.extend(_numeric_values(breakdown.result.rows))
    return tuple(values)


def _card_line(metric: str, value: Scalar) -> str:
    return f"{metric}: {value if value is not None else 'no data'}"


def _describe(summary: DashboardSummary) -> str:
    lines = [
        _card_line(card.metric, card.result.rows[0][0] if card.result.rows else None)
        for card in summary.cards
    ]
    if summary.trend is not None:
        lines.append(
            f"{summary.trend.lineage.metric} by {summary.trend.dimension}: "
            f"{summary.trend.result.rows}"
        )
    if summary.breakdown is not None:
        lines.append(
            f"{summary.breakdown.lineage.metric} by {summary.breakdown.dimension}: "
            f"{summary.breakdown.result.rows}"
        )
    return "\n".join(lines)


class SummaryService:
    def __init__(self, model: LanguageModel) -> None:
        self.model = model

    async def summarize(self, summary: DashboardSummary) -> str:
        evidence = _evidence(summary)
        request = ModelRequest(
            messages=(
                ModelMessage("system", _SYSTEM_PROMPT),
                ModelMessage("user", _describe(summary)),
            ),
            tier=ModelTier.LARGE,
        )
        response = await self.model.complete(request)
        if not is_grounded(response.content, evidence):
            raise UnverifiedAnswerError(
                "The generated summary referenced a number outside the executed evidence"
            )
        return response.content
