"""Use case: Routes a natural-language question to a validated, executed answer.

What it does: Asks a language model only to classify intent and propose a structured
plan; the proposal is revalidated by the same rules a structured API request follows,
and only a numerical intent ever reaches the query engine.
"""

from uuid import UUID

from execplus.application.contracts import ModelMessage, ModelRequest
from execplus.application.ports import LanguageModel
from execplus.application.services.analytics import AnalyticsService
from execplus.domain.errors import ClarificationRequiredError, UnsupportedQuestionError
from execplus.domain.ingestion import User
from execplus.domain.intent import route_response
from execplus.domain.models import (
    CalculationLineage,
    ModelTier,
    QueryResult,
    QuestionKind,
    VerifiedMetricAnswer,
)
from execplus.domain.semantics import DatasetView

NumericalAnswer = VerifiedMetricAnswer | tuple[QueryResult, CalculationLineage]

_SYSTEM_PROMPT = (
    "You classify a business question about one dataset and, only when it asks for a "
    "number, propose a structured query plan. Never calculate or state a numeric answer "
    "yourself; a separate system executes the plan and returns the real value. Reply "
    "with a single JSON object only, no prose, matching exactly one of these shapes:\n"
    '{"kind": "numerical", "plan": {"metric": "<metric column>", '
    '"aggregation": "sum|avg|count|min|max", "group_by": ["<dimension column>", ...], '
    '"filters": [{"column": "...", "operator": "eq|ne|lt|lte|gt|gte", "value": ...}]}}\n'
    '{"kind": "ambiguous", "message": "...", "options": ["...", "..."]}\n'
    '{"kind": "textual", "message": "..."}\n'
    '{"kind": "unsupported", "message": "..."}\n'
    "Only use metric and dimension names exactly as listed below; never invent a column. "
    "If a prior turn is given, resolve pronouns and follow-ups (like 'and by region?') "
    "against its structured metric/dimension/filter fields, not by guessing new ones."
)


def _describe_view(view: DatasetView) -> str:
    metrics = ", ".join(sorted(view.metrics)) or "(none)"
    dimensions = ", ".join(sorted(view.dimensions)) or "(none)"
    return f"Metrics: {metrics}\nDimensions: {dimensions}"


def _describe_prior_turn(lineage: CalculationLineage) -> str:
    # A structured reference to the prior turn's resolved plan, not its raw
    # question text or the model's prose reply, so follow-ups are grounded in
    # what was actually executed rather than a growing transcript.
    grouping = ", ".join(lineage.grouping) or "(none)"
    filters = "; ".join(lineage.filters) or "(none)"
    return (
        f"Previous turn: {lineage.aggregation} of {lineage.metric}, "
        f"grouped by {grouping}, filtered by {filters}."
    )


class IntentRouterService:
    def __init__(self, model: LanguageModel, analytics: AnalyticsService) -> None:
        self.model = model
        self.analytics = analytics

    async def ask(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        question: str,
        prior_turn: CalculationLineage | None = None,
    ) -> NumericalAnswer:
        view = await self.analytics.get_view(actor, workspace_id, dataset_id, upload_id)
        context = f"{_describe_view(view)}\n"
        if prior_turn is not None:
            context += f"{_describe_prior_turn(prior_turn)}\n"
        request = ModelRequest(
            messages=(
                ModelMessage("system", _SYSTEM_PROMPT),
                ModelMessage("user", f"{context}\nQuestion: {question}"),
            ),
            tier=ModelTier.SMALL,
        )
        response = await self.model.complete(request)
        routed = route_response(response.content, view)

        if routed.kind == QuestionKind.NUMERICAL and routed.request is not None:
            model_route = f"{response.provider}:{response.model}"
            if routed.request.group_by:
                # A grouped plan produces multiple rows, so it cannot be
                # reduced to a single verified scalar answer; run it as a
                # table query instead of forcing it through answer_metric.
                return await self.analytics.run_query(
                    actor, workspace_id, dataset_id, upload_id, routed.request, model_route
                )
            return await self.analytics.answer_metric(
                actor, workspace_id, dataset_id, upload_id, routed.request, model_route
            )
        if routed.kind == QuestionKind.AMBIGUOUS:
            options = f" Candidates: {', '.join(routed.options)}." if routed.options else ""
            raise ClarificationRequiredError(f"{routed.message}{options}")
        raise UnsupportedQuestionError(routed.message)
