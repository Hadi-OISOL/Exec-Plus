"""Use case: Drafts a plain-language reading of a new upload for its owner to confirm.

What it does: Has the model read the file profile and a bounded sample, then checks its reply.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4

from execplus.application.contracts import ModelMessage
from execplus.application.ports import FileParser, LanguageModel, ObjectStorage, WorkspaceRepository
from execplus.application.services.dataset_access import require_full_access
from execplus.application.services.forecasts import read_complete
from execplus.application.services.structured_reading import (
    READING_TIMEOUT_SECONDS,
    read_validated,
    reading_failure_notice,
)
from execplus.application.usage_context import attributed_operation
from execplus.domain.data_brief import (
    fallback_brief,
    ground_brief,
    model_input,
    next_question,
    parse_brief,
    sample_values,
    system_prompt,
)
from execplus.domain.errors import ProviderUnavailableError, UnverifiedAnswerError
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.profiling import Revision, reconstruct
from execplus.domain.understanding import infer_definition

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]


class DataBriefService:
    def __init__(
        self,
        unit_of_work: UnitOfWork,
        model: LanguageModel,
        storage: ObjectStorage,
        parser: FileParser,
        sample_limit: int = 0,
        model_enabled: bool = False,
    ) -> None:
        self.uow = unit_of_work
        self.model = model
        self.storage = storage
        self.parser = parser
        self.sample_limit = sample_limit
        self.model_enabled = model_enabled
        self.reading_timeout_seconds = READING_TIMEOUT_SECONDS

    def _context(
        self, actor: User, workspace_id: UUID, dataset_id: UUID, upload_id: UUID
    ) -> dict[str, Any]:
        with self.uow() as repo:
            repo.workspace(workspace_id, lock=True)
            member = repo.membership(workspace_id, actor.id)
            access = require_full_access(repo, actor, workspace_id, dataset_id)
            dataset = repo.dataset(workspace_id, dataset_id)
            upload = repo.upload(workspace_id, dataset_id, upload_id)
            revision = repo.active_revision(workspace_id, dataset_id, upload_id)
            if revision is None:
                raise IngestionError("not_found", "Profile this upload first.", 404)
            saved = repo.latest_understanding(workspace_id, dataset_id)
            preference = repo.data_preference(workspace_id, dataset_id, actor.id)
            proposal = infer_definition(
                revision.profile, preference.domain_hint if preference else "auto"
            )
            definition = saved.definition if saved else proposal
            if saved and saved.revision_id != revision.id:
                previous = {column["name"]: column for column in saved.definition["columns"]}
                definition = {
                    **saved.definition,
                    "columns": [
                        previous.get(column["name"], column) for column in proposal["columns"]
                    ],
                }
            return dict(
                access_reference=access.reference(),
                upload=upload,
                revision=revision,
                saved=saved,
                definition=definition,
                agent_memory=repo.agent_memory(workspace_id, actor.id),
                can_edit=member.role in {"owner", "admin"} or dataset.created_by == actor.id,
            )

    def _recheck(
        self,
        repo: WorkspaceRepository,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        context: dict[str, Any],
    ) -> None:
        repo.workspace(workspace_id, lock=True)
        member = repo.membership(workspace_id, actor.id)
        access = require_full_access(repo, actor, workspace_id, dataset_id)
        dataset = repo.dataset(workspace_id, dataset_id)
        upload = repo.upload(workspace_id, dataset_id, upload_id)
        revision = repo.active_revision(workspace_id, dataset_id, upload_id)
        saved = repo.latest_understanding(workspace_id, dataset_id)
        if (
            access.reference() != context["access_reference"]
            or revision != context["revision"]
            or upload.checksum != context["upload"].checksum
            or saved != context["saved"]
            or repo.agent_memory(workspace_id, actor.id) != context["agent_memory"]
            or (member.role in {"owner", "admin"} or dataset.created_by == actor.id)
            != context["can_edit"]
        ):
            raise IngestionError(
                "source_changed",
                "Your file or saved answers changed while I was reading. "
                "Please open the review again.",
                409,
            )

    def _recheck_before_retry(
        self, actor: User, wid: UUID, did: UUID, uid: UUID, context: dict[str, Any]
    ) -> None:
        with self.uow() as repo:
            self._recheck(repo, actor, wid, did, uid, context)

    def _sample(
        self, upload: Any, revision: Revision, definition: dict[str, Any]
    ) -> dict[str, Any] | None:
        if self.sample_limit <= 0 or revision.source_checksum != upload.checksum:
            return None
        try:
            content = BytesIO(self.storage.read(upload))
            self.parser.parse(
                content, upload.filename, upload.content_type, stored_format=upload.format
            )
            table = reconstruct(self.parser.read_table(content, upload.format), revision)
        except (IngestionError, ValueError, OSError):
            return None
        return sample_values(table, definition, self.sample_limit)

    @attributed_operation("data_reading")
    async def draft(
        self,
        actor: User,
        workspace_id: UUID,
        dataset_id: UUID,
        upload_id: UUID,
        review_missing: bool = False,
    ) -> dict[str, Any]:
        context = self._context(actor, workspace_id, dataset_id, upload_id)
        saved, revision = context["saved"], context["revision"]
        result: dict[str, Any] = dict(
            revision_id=str(revision.id),
            version=saved.version if saved else 0,
            state="needs_review"
            if saved and saved.revision_id != revision.id
            else saved.state
            if saved
            else "inferred",
            can_edit=context["can_edit"],
            definition=context["definition"],
            already_confirmed=bool(
                saved and saved.state == "confirmed" and saved.revision_id == revision.id
            ),
            model_route=None,
            notice="",
            sampled=False,
            model_enabled=self.model_enabled,
            next_question=next_question(context["definition"]),
        )
        if result["already_confirmed"] and not review_missing:
            self._recheck_before_retry(actor, workspace_id, dataset_id, upload_id, context)
            return result
        if review_missing and saved and saved.revision_id == revision.id:
            definition = context["definition"]
            missing = {
                column["name"]
                for column in definition["columns"]
                if column["role"] != "ignored"
                and (
                    not column["meaning"]
                    or (
                        column["role"] == "metric"
                        and not (column["unit"] or column["currency"] or column["unit_column"])
                    )
                )
            }
            if not missing and result["already_confirmed"]:
                self._recheck_before_retry(actor, workspace_id, dataset_id, upload_id, context)
                return result
            brief = fallback_brief(revision.profile, definition)
            brief["columns"] = [column for column in brief["columns"] if column["name"] in missing]
            brief["questions"] = []
            brief = ground_brief(brief, definition, preserve_saved=True)
            self._recheck_before_retry(actor, workspace_id, dataset_id, upload_id, context)
            return {**result, **brief, "already_confirmed": False, "review_mode": "missing"}
        profile, definition = revision.profile, context["definition"]
        samples = await read_complete(lambda: self._sample(context["upload"], revision, definition))
        self._recheck_before_retry(actor, workspace_id, dataset_id, upload_id, context)
        try:
            brief, response, repaired = await read_validated(
                self.model,
                (
                    ModelMessage("system", system_prompt(samples)),
                    ModelMessage(
                        "user",
                        model_input(
                            profile, definition, samples, context["agent_memory"].context()
                        ),
                    ),
                ),
                lambda raw: parse_brief(raw, profile, definition, samples),
                timeout_seconds=self.reading_timeout_seconds,
                before_retry=lambda: self._recheck_before_retry(
                    actor, workspace_id, dataset_id, upload_id, context
                ),
            )
            result["model_route"] = f"{response.provider}:{response.model}"
            result["sampled"] = samples is not None
            result["repaired"] = repaired
        except (ProviderUnavailableError, UnverifiedAnswerError, TimeoutError, ValueError) as error:
            brief = fallback_brief(profile, definition)
            result["notice"] = (
                reading_failure_notice(error) + " Your file is still available. "
                "These questions use its profile and saved answers."
            )
        with self.uow() as repo:
            self._recheck(repo, actor, workspace_id, dataset_id, upload_id, context)
            repo.add(
                AuditEvent(
                    uuid4(),
                    workspace_id,
                    actor.id,
                    "data_brief.drafted",
                    "upload",
                    upload_id,
                    datetime.now(timezone.utc),
                )
            )
        return {**result, **ground_brief(brief, definition, preserve_saved=saved is not None)}
