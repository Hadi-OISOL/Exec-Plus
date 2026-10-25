"""Use case: Tells a member what an uploaded file is for and how they can benefit from it.

What it does: Finds the upload inside the caller's workspace, reads its authorized snapshot and
returns the qualitative dataset-purpose-v1 payload with routable suggested questions.
"""

import asyncio
from typing import Any
from uuid import UUID

from execplus.application.services.analytics import AnalyticsService
from execplus.domain.goal_ranking import dataset_purpose
from execplus.domain.ingestion import IngestionError, User


async def purpose(
    analytics: AnalyticsService, actor: User, workspace_id: UUID, upload_id: UUID
) -> dict[str, Any]:
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
    context, table, _ = await asyncio.to_thread(
        analytics.descriptive_snapshot, actor, workspace_id, dataset_id, upload_id
    )
    return dataset_purpose(
        context.name,
        context.profile,
        context.view,
        table.headers,
        table.rows,
        context.agent_memory.role if context.agent_memory else "",
    )
