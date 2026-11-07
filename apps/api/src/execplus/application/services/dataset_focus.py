"""Use case: Keeps each member's answers to the follow-up questions about one file private to them.

What it does: Reads and writes one small private object per workspace, dataset and member (the
same private-object pattern as hypothesis feedback), validates answers against the questions
this file's current columns produce, and merges answers given in chat.
"""

import asyncio
import hashlib
import json
from typing import TYPE_CHECKING, Any
from uuid import UUID

from execplus.application.ports import ObjectStorage
from execplus.domain.dataset_focus import STATUSES, VERSION, questions, validate
from execplus.domain.goal_ranking import profile_choices, ranking_fields
from execplus.domain.ingestion import IngestionError, User

if TYPE_CHECKING:
    from execplus.application.services.analytics import AnalyticsService

FOCUS_BYTES = 4096


def _key(workspace_id: UUID, dataset_id: UUID, actor_id: UUID) -> str:
    return f"workspaces/{workspace_id}/private/dataset-focus/{dataset_id}/{actor_id}.json"


def read_focus(
    storage: ObjectStorage, workspace_id: UUID, dataset_id: UUID, actor_id: UUID
) -> dict[str, Any]:
    raw = storage.read_optional(_key(workspace_id, dataset_id, actor_id), FOCUS_BYTES)
    try:
        payload = json.loads(raw) if raw and len(raw) <= FOCUS_BYTES else {}
    except ValueError:
        payload = {}
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        return dict(status="pending", answers={})
    return dict(
        status=payload.get("status") if payload.get("status") in STATUSES else "pending",
        answers={str(k): v for k, v in answers.items() if isinstance(v, str)},
    )


def write_focus(
    storage: ObjectStorage,
    workspace_id: UUID,
    dataset_id: UUID,
    actor_id: UUID,
    answers: dict[str, str],
    status: str,
) -> dict[str, Any]:
    saved = dict(status=status, answers=answers)
    content = json.dumps(saved, sort_keys=True).encode()
    storage.put_part(
        _key(workspace_id, dataset_id, actor_id), content, hashlib.sha256(content).hexdigest()
    )
    return saved


def dataset_for(
    analytics: "AnalyticsService", actor: User, workspace_id: UUID, upload_id: UUID
) -> UUID:
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


def follow_up(
    context: Any, headers: tuple[str, ...], rows: tuple[tuple[Any, ...], ...]
) -> dict[str, Any]:
    fields = ranking_fields(context.view)
    labels = profile_choices(headers, rows, fields.texts) if fields else ()
    return dict(
        version=VERSION,
        questions=questions(context, labels),
        answers=dict(context.focus),
        status=context.focus_status,
    )


async def save(
    analytics: "AnalyticsService",
    actor: User,
    workspace_id: UUID,
    upload_id: UUID,
    answers: Any,
    status: Any,
) -> dict[str, Any]:
    dataset_id = dataset_for(analytics, actor, workspace_id, upload_id)
    context, table, _ = await asyncio.to_thread(
        analytics.descriptive_snapshot, actor, workspace_id, dataset_id, upload_id
    )
    asked = follow_up(context, table.headers, table.rows)["questions"]
    kept = validate(asked, answers, status)
    saved = await asyncio.to_thread(
        write_focus, analytics.storage, workspace_id, dataset_id, actor.id, kept, status
    )
    return dict(version=VERSION, questions=asked, **saved)
