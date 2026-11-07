"""Use case: Tells a member what an uploaded file is for and how they can benefit from it.

What it does: Finds the upload inside the caller's workspace, reads its authorized snapshot and
returns the qualitative dataset-purpose-v1 payload with routable suggested questions (led by the
member's own follow-up answers) and the private dataset-focus-v1 follow-up questions.
"""

import asyncio
from typing import Any
from uuid import UUID

from execplus.application.services.analytics import AnalyticsService
from execplus.application.services.dataset_focus import dataset_for, follow_up
from execplus.domain.dataset_focus import focused_questions
from execplus.domain.goal_ranking import dataset_purpose, ranking_fields
from execplus.domain.ingestion import User


async def purpose(
    analytics: AnalyticsService, actor: User, workspace_id: UUID, upload_id: UUID
) -> dict[str, Any]:
    dataset_id = dataset_for(analytics, actor, workspace_id, upload_id)
    context, table, _ = await asyncio.to_thread(
        analytics.descriptive_snapshot, actor, workspace_id, dataset_id, upload_id
    )
    body = dataset_purpose(
        context.name,
        context.profile,
        context.view,
        table.headers,
        table.rows,
        context.agent_memory.role if context.agent_memory else "",
    )
    fields = ranking_fields(context.view)
    first = focused_questions(context.focus, context.view, fields.scores if fields else ())
    if first:
        seen = {item["question"] for item in first}
        body["suggested_questions"] = [
            *first,
            *(item for item in body["suggested_questions"] if item["question"] not in seen),
        ]
    body["follow_up"] = follow_up(context, table.headers, table.rows)
    return body
