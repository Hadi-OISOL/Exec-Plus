"""Use case: Saves exact change investigations using existing study records.

What it does: Executes two governed projections, binds their private receipts to
one immutable study version, and rechecks all source permissions at publication.
"""

from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.dataset_access import authorize_sources, dataset_access
from execplus.domain.contributions import (
    LIMITATIONS,
    METHOD,
    calculate_contributions,
    projection,
    validate_comparison,
)
from execplus.domain.evidence import receipt
from execplus.domain.ingestion import IngestionError, User
from execplus.domain.models import CalculationLineage, QueryResult
from execplus.domain.studies import Study, StudyVersion

if TYPE_CHECKING:
    from execplus.application.services.studies import StudyService


def ranked_fields(method: dict[str, Any]) -> tuple[str, ...]:
    side = method["baseline"]
    return (side["segment"], *side["dimensions"]) if side.get("dimensions") else ()


def check_current(
    repo: WorkspaceRepository, actor: User, wid: UUID, sources: list[dict[str, str]]
) -> None:
    authorize_sources(repo, actor, wid, sources)
    for source in sources:
        did, uid = UUID(source["dataset_id"]), UUID(source["upload_id"])
        revision = repo.active_revision(wid, did, uid)
        meaning = repo.latest_understanding(wid, did)
        if (
            not revision
            or str(revision.id) != source["revision_id"]
            or not meaning
            or str(meaning.id) != source.get("understanding_id")
            or meaning.state != "confirmed"
        ):
            raise IngestionError(
                "study_conflict",
                "A source or confirmed meaning changed. Review both snapshots and try again.",
                409,
            )


async def run_contribution(
    service: "StudyService",
    actor: User,
    wid: UUID,
    did: UUID,
    uid: UUID,
    name: str,
    question: str,
    raw: dict[str, Any],
    revision_id: UUID,
    understanding_id: UUID,
    study_id: UUID | None,
    parent_id: UUID | None,
) -> tuple[Study, StudyVersion, list[tuple[QueryResult, CalculationLineage]]]:
    from execplus.application.services.studies import audit, owns, visible

    if study_id and raw.get("mode") == "period":
        # An explicit rerun uses the selected new snapshot with the same two windows.
        raw = {
            **raw,
            "comparison": {
                **raw["comparison"],
                "dataset_id": str(did),
                "upload_id": str(uid),
                "revision_id": str(revision_id),
                "understanding_id": str(understanding_id),
            },
        }
    method = validate_comparison(raw, did, uid)
    other = method["comparison"]
    contexts = [
        service.analytics._context(actor, wid, did, uid),
        service.analytics._context(actor, wid, UUID(other["dataset_id"]), UUID(other["upload_id"])),
    ]
    sources = [context[3].sources[0] for context in contexts]
    if (
        sources[0].get("revision_id") != str(revision_id)
        or sources[0].get("understanding_id") != str(understanding_id)
        or any(
            sources[1].get(key) != other[key]
            for key in ("dataset_id", "upload_id", "revision_id", "understanding_id")
        )
    ):
        raise IngestionError(
            "study_conflict",
            "Review the current confirmed meaning on both selected snapshots.",
            409,
        )
    plans = [
        projection(
            context[1],
            UUID(source["dataset_id"]),
            context[2],
            context[3],
            method[label],
            method["decompose"],
        )
        for label, context, source in zip(
            ("baseline", "comparison"), contexts, sources, strict=True
        )
    ]
    if plans[0][1] != plans[1][1]:
        raise IngestionError(
            "contribution_unit",
            "Both sides need identical declared units and currency; conversions are not inferred.",
            422,
        )
    with service.uow() as repo:
        repo.workspace(wid, lock=True)
        check_current(repo, actor, wid, sources)
    version_id = uuid4()
    results = []
    for context, (plan, _) in zip(contexts, plans, strict=True):
        dataset_name, scope, table, view = context
        lineage = CalculationLineage(
            plan.query_id,
            wid,
            plan.dataset_id,
            dataset_name,
            len(table.rows),
            "contribution records",
            "analysis",
            (),
            (),
            plan.sql,
        )
        binding = dict(version_id=str(version_id), sources=sources)
        try:
            result = await service.analytics.executor.execute(plan, scope, table, view)
        except Exception:
            service.analytics._persist(
                actor,
                replace(
                    lineage, receipt={**receipt(plan, view.sources, None), "study_binding": binding}
                ),
            )
            raise
        lineage = replace(
            lineage,
            receipt={
                **receipt(plan, view.sources, result, row_query=True),
                "study_binding": binding,
            },
        )
        service.analytics._persist(actor, lineage)
        results.append((result, lineage))
    calculation = calculate_contributions(
        results[0][0].rows, results[1][0].rows, method["decompose"], ranked_fields(method)
    )
    now = datetime.now(timezone.utc)
    with service.uow() as repo:
        repo.workspace(wid, lock=True)
        check_current(repo, actor, wid, sources)
        if study_id:
            study = visible(repo, actor, wid, study_id)
            owns(study.owner_id, actor)
            previous = repo.study_versions(wid, study.id)
            if not previous or previous[-1].id != parent_id or len(previous) >= 50:
                raise IngestionError(
                    "study_conflict", "Another version finished first. Reload the study.", 409
                )
            sequence = previous[-1].number + 1
        else:
            repo.check_plan_stock(wid, "saved_studies", 1, now)
            study = Study(uuid4(), wid, did, actor.id, name, False, now)
            repo.add(study)
            sequence = 1
        upload = repo.upload(wid, did, uid)
        access = dataset_access(repo, actor, wid, did)
        baseline_revision = repo.active_revision(wid, did, uid)
        assert baseline_revision is not None
        version = StudyVersion(
            version_id,
            wid,
            study.id,
            sequence,
            uid,
            parent_id,
            question,
            method,
            dict(
                method_version=METHOD,
                query_ids=[str(r.query_id) for r, _ in results],
                sources=sources,
                definition=contexts[0][3].definition,
                comparison_definition=contexts[1][3].definition,
                preparation=[] if access.restricted else baseline_revision.recipe,
                preparation_version=baseline_revision.algorithm,
                source_uploaded_at=upload.created_at.isoformat(),
                component="bar",
                units=plans[0][1],
                calculation=calculation,
                limitations=LIMITATIONS,
            ),
            actor.id,
            now,
        )
        repo.add(version)
        audit(repo, actor, wid, "study.rerun" if sequence > 1 else "study.created", version.id)
    return study, version, results


def verify_contribution(
    version: StudyVersion, results: list[tuple[QueryResult, CalculationLineage]]
) -> None:
    if version.evidence.get("method_version") != METHOD or len(results) != 2:
        raise IngestionError("lineage_mismatch", "This contribution method is unavailable.", 409)
    calculated = calculate_contributions(
        results[0][0].rows,
        results[1][0].rows,
        version.method["decompose"],
        ranked_fields(version.method),
    )
    if calculated != version.evidence.get("calculation"):
        raise IngestionError(
            "lineage_mismatch", "The exact contribution no longer matches its saved evidence.", 409
        )
