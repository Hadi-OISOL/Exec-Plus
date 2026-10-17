"""Use case: Persists a query's calculation lineage and its audit trail entry.

What it does: Shared by every service that executes a query, so lineage is
recorded identically regardless of which engine path produced it (AGENTS.md rule 6).
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from uuid import UUID, uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.dataset_access import authorize_sources
from execplus.domain.ingestion import AuditEvent, IngestionError, User
from execplus.domain.models import CalculationLineage, QueryExecution

UnitOfWork = Callable[[], AbstractContextManager[WorkspaceRepository]]


def persist_query_execution(uow: UnitOfWork, actor: User, lineage: CalculationLineage) -> None:
    now = datetime.now(timezone.utc)
    with uow() as repo:
        repo.workspace(lineage.workspace_id, lock=True)
        repo.membership(lineage.workspace_id, actor.id)
        authorize_sources(
            repo, actor, lineage.workspace_id, lineage.receipt.get("sources"), lineage.dataset_id
        )
        repo.add(
            QueryExecution(
                id=lineage.query_id,
                workspace_id=lineage.workspace_id,
                dataset_id=lineage.dataset_id,
                actor_id=actor.id,
                dataset_name=lineage.dataset_name,
                metric=lineage.metric,
                aggregation=lineage.aggregation,
                grouping=lineage.grouping,
                filters=lineage.filters,
                sql=lineage.sql,
                records_analyzed=lineage.records_analyzed,
                created_at=now,
                model_route=lineage.model_route,
                receipt=lineage.receipt,
            )
        )
        repo.add(
            AuditEvent(
                uuid4(),
                lineage.workspace_id,
                actor.id,
                "query.executed"
                if lineage.receipt.get("outcome", "executed") == "executed"
                else "query.failed",
                "query",
                lineage.query_id,
                now,
            )
        )


def authorize_analysis_receipt(
    repo: WorkspaceRepository, actor: User, execution: QueryExecution
) -> str:
    """Private analysis receipts only become shareable through their exact saved study."""
    if execution.aggregation != "analysis":
        return "workspace"
    binding = execution.receipt.get("study_binding")
    if binding is None:
        if execution.actor_id != actor.id:
            raise IngestionError("not_found", "The private query is unavailable.", 404)
        return "private"
    try:
        if not isinstance(binding, dict):
            raise ValueError
        version = repo.study_version(execution.workspace_id, UUID(binding["version_id"]))
        study = repo.study(execution.workspace_id, version.study_id)
        query_ids = version.evidence["query_ids"]
        sources = version.evidence["sources"]
        position = query_ids.index(str(execution.id))
        if (
            version.method.get("kind") != "contribution"
            or study.owner_id != execution.actor_id
            or version.created_by != execution.actor_id
            or (not study.shared and study.owner_id != actor.id)
            or binding.get("sources") != sources
            or len(query_ids) != 2
            or len(sources) != 2
            or execution.receipt.get("sources") != [sources[position]]
        ):
            raise ValueError
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        raise IngestionError("not_found", "The saved study query is unavailable.", 404) from None
    authorize_sources(repo, actor, execution.workspace_id, sources, study.dataset_id)
    return "workspace" if study.shared else "private"
