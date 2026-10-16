"""Use case: Persists a query's calculation lineage and its audit trail entry.

What it does: Shared by every service that executes a query, so lineage is
recorded identically regardless of which engine path produced it (AGENTS.md rule 6).
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from uuid import uuid4

from execplus.application.ports import WorkspaceRepository
from execplus.application.services.dataset_access import authorize_sources
from execplus.domain.ingestion import AuditEvent, User
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
