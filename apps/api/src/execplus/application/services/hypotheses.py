"""Use case: Tests what might be true in an upload and keeps each member's feedback private.

What it does: Runs one governed projection with an owner-private receipt, labels each candidate
from its rows, lets a model only propose specs inside the fixed grammar, and stores each
member's like/dislike per hypothesis type in a private object that only that member reads.
"""

import asyncio
import hashlib
import json
from dataclasses import replace
from typing import Any
from uuid import UUID

from execplus.application.contracts import ModelMessage, ModelRequest
from execplus.application.ports import LanguageModel, ObjectStorage
from execplus.application.services.analytics import AnalyticsService
from execplus.domain.errors import (
    ClarificationRequiredError,
    ProviderUnavailableError,
    UnsafeQueryError,
    UnsupportedQuestionError,
)
from execplus.domain.evidence import receipt
from execplus.domain.hypotheses import (
    MAX_ITEMS,
    MAX_ROWS,
    MODEL_SYSTEM,
    ROUTE,
    VERSION,
    candidates,
    evaluate,
    fields,
    model_prompt,
    ordered,
    parse_feedback,
    parse_model_specs,
    projection_plan,
    updated_feedback,
)
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.insights import select_fields
from execplus.domain.models import CalculationLineage, ModelTier

MODEL_SECONDS = 15.0
MODEL_SLOTS = 2
FEEDBACK_BYTES = 4096


def _key(workspace_id: UUID, actor_id: UUID) -> str:
    return f"workspaces/{workspace_id}/private/hypothesis-feedback/{actor_id}.json"


def read_feedback(
    storage: ObjectStorage, workspace_id: UUID, actor_id: UUID
) -> dict[str, dict[str, str]]:
    raw = storage.read_optional(_key(workspace_id, actor_id), FEEDBACK_BYTES)
    return parse_feedback(raw) if raw and len(raw) <= FEEDBACK_BYTES else {}


def save_feedback(
    analytics: AnalyticsService,
    actor: User,
    workspace_id: UUID,
    kind: str,
    vote: str,
    reason: str | None,
) -> dict[str, dict[str, str]]:
    with analytics.uow() as repo:
        repo.membership(workspace_id, actor.id)
    current = read_feedback(analytics.storage, workspace_id, actor.id)
    try:
        result = updated_feedback(current, kind, vote, reason)
    except ValueError:
        raise IngestionError(
            "invalid_feedback", "Use a listed hypothesis type, vote and reason.", 422
        ) from None
    content = json.dumps(result, sort_keys=True).encode()
    analytics.storage.put_part(
        _key(workspace_id, actor.id), content, hashlib.sha256(content).hexdigest()
    )
    return result


def _dataset(analytics: AnalyticsService, actor: User, workspace_id: UUID, upload_id: UUID) -> UUID:
    with analytics.uow() as repo:
        repo.membership(workspace_id, actor.id)
        dataset_id = next(
            (
                dataset.id
                for dataset in repo.datasets(workspace_id)
                if any(upload.id == upload_id for upload in repo.uploads(workspace_id, dataset.id))
            ),
            None,
        )
    if dataset_id is None:
        raise IngestionError("not_found", "This upload is unavailable.", 404)
    return dataset_id


async def _model_specs(model: LanguageModel | None, found: Any) -> list[Any]:
    if model is None:
        return []
    try:
        response = await asyncio.wait_for(
            model.complete(
                ModelRequest(
                    messages=(
                        ModelMessage("system", MODEL_SYSTEM),
                        ModelMessage("user", model_prompt(found)),
                    ),
                    tier=ModelTier.SMALL,
                )
            ),
            MODEL_SECONDS,
        )
        return parse_model_specs(response.content, found)
    except (ProviderUnavailableError, asyncio.TimeoutError, ValueError, KeyError, TypeError):
        return []


async def hypotheses(
    analytics: AnalyticsService,
    actor: User,
    workspace_id: UUID,
    upload_id: UUID,
    model: LanguageModel | None = None,
) -> dict[str, Any]:
    dataset_id = _dataset(analytics, actor, workspace_id, upload_id)
    context, table, scope = await asyncio.to_thread(
        analytics.descriptive_snapshot, actor, workspace_id, dataset_id, upload_id
    )
    view = context.view
    feedback = await asyncio.to_thread(read_feedback, analytics.storage, workspace_id, actor.id)
    body: dict[str, Any] = dict(
        version=VERSION,
        dataset_name=context.name,
        sources=list(view.sources),
        items=[],
        model_route=None,
        limitations=[],
    )
    if any(source.get("understanding_id") for source in view.sources) and (
        context.state != "confirmed"
    ):
        body["limitations"].append(
            "Confirm Data understanding for this revision before these checks run."
        )
        return body
    if context.profile["row_count"] > MAX_ROWS:
        body["limitations"].append(f"These checks cover files with up to {MAX_ROWS:,} rows.")
        return body
    found = fields(context, select_fields(context))
    specs = candidates(found)
    extra = [
        spec
        for spec in await _model_specs(model, found)
        if spec.key not in {item.key for item in specs}
    ][:MODEL_SLOTS]
    if extra:
        body["model_route"] = "model-proposed-specs"
    specs = ordered([*specs[: MAX_ITEMS - len(extra)], *extra], feedback)
    if not specs:
        body["limitations"].append("This file has no measures or groups these checks can test.")
        return body
    plan = projection_plan(scope, dataset_id, found)
    lineage = CalculationLineage(
        plan.query_id,
        workspace_id,
        dataset_id,
        context.name,
        table.row_count,
        "Hypothesis checks",
        "analysis",
        (),
        (),
        plan.sql,
        ROUTE,
    )
    with analytics.uow() as repo:
        analytics._authorize(repo, actor, workspace_id)
    try:
        result = await analytics.executor.execute(plan, scope, table, view)
    except (ClarificationRequiredError, UnsafeQueryError, UnsupportedQuestionError) as error:
        analytics._persist(actor, replace(lineage, receipt=receipt(plan, view.sources, None)))
        body["limitations"].append(f"These checks could not read the selected fields: {error}")
        return body
    except (Exception, asyncio.CancelledError):
        analytics._persist(actor, replace(lineage, receipt=receipt(plan, view.sources, None)))
        raise
    analytics._persist(actor, replace(lineage, receipt=receipt(plan, view.sources, result)))
    outcomes = await asyncio.to_thread(
        lambda: [evaluate(spec, context.name, result.columns, result.rows) for spec in specs]
    )
    await asyncio.to_thread(
        analytics.recheck_description, actor, workspace_id, dataset_id, upload_id, view.sources
    )
    body["items"] = [
        item.body(str(plan.query_id), feedback.get(item.spec.kind, {}).get("vote"))
        for item in outcomes
    ]
    body["limitations"].append(
        "These are checks on the rows in this file. A supported pattern is not proof of a cause."
    )
    return body
