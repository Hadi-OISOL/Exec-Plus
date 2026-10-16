"""Use case: Enforces one access policy consistently across dataset services.

What it does: Resolves current grants, protects immutable evidence and produces
projected profiles before any planner, calculation or model can inspect a source.
"""

import copy
from dataclasses import replace
from typing import Any
from uuid import UUID

from execplus.application.ports import WorkspaceRepository
from execplus.domain.dataset_access import (
    ACCESS_KEYS,
    DatasetAccess,
    access_for,
    denied,
    project_table,
)
from execplus.domain.ingestion import User
from execplus.domain.profiling import CURRENT_ALGORITHM, TableData, profile_for
from execplus.domain.semantics import DatasetView


def dataset_access(repo: WorkspaceRepository, actor: User, wid: UUID, did: UUID) -> DatasetAccess:
    membership = repo.membership(wid, actor.id)
    repo.dataset(wid, did)
    return access_for(
        repo.dataset_access_policy(wid, did), actor.id, membership.created_at.isoformat()
    )


def require_full_access(
    repo: WorkspaceRepository, actor: User, wid: UUID, did: UUID
) -> DatasetAccess:
    access = dataset_access(repo, actor, wid, did)
    access.require_full()
    return access


def require_workspace_access(repo: WorkspaceRepository, actor: User, wid: UUID) -> None:
    for item in repo.datasets(wid):
        policy = repo.dataset_access_policy(wid, item.id)
        if policy is not None and policy.enabled:
            require_full_access(repo, actor, wid, item.id)


def authorize_sources(
    repo: WorkspaceRepository, actor: User, wid: UUID, sources: Any, dataset_id: UUID | None = None
) -> None:
    if not isinstance(sources, (list, tuple)) or not sources:
        if dataset_id is not None and dataset_access(repo, actor, wid, dataset_id).policy is None:
            return
        raise denied()
    for source in sources:
        if not isinstance(source, dict):
            raise denied()
        try:
            access = dataset_access(repo, actor, wid, UUID(source["dataset_id"]))
        except (ValueError, TypeError, KeyError):
            raise denied() from None
        if {key: source[key] for key in ACCESS_KEYS if key in source} != access.reference():
            raise denied()


def scoped_definition(
    definition: dict[str, Any] | None, access: DatasetAccess, headers: tuple[str, ...]
) -> tuple[dict[str, Any] | None, frozenset[str]]:
    if not definition or not access.restricted:
        return definition, frozenset()
    visible = set(headers)
    value = copy.deepcopy(definition)
    value["description"] = ""
    value["relationships"] = []
    value["columns"] = [item for item in value["columns"] if item["name"] in visible]
    blocked = set()
    for column in value["columns"]:
        if column.get("unit_column") and column["unit_column"] not in visible:
            blocked.add(column["name"])
            column["unit_column"] = ""
    metrics = []
    for metric in value.get("metrics", []):
        if metric["column"] not in visible:
            continue
        if any(item["column"] not in visible for item in metric.get("filters", [])):
            blocked.add(metric["column"])
        else:
            metrics.append(metric)
    value["metrics"] = metrics
    return value, frozenset(blocked)


def scope_snapshot(
    table: TableData,
    view: DatasetView,
    full_profile: dict[str, Any],
    definition: dict[str, Any] | None,
    access: DatasetAccess,
) -> tuple[TableData, DatasetView, dict[str, Any], dict[str, Any] | None]:
    table = project_table(table, view, access)
    definition, blocked = scoped_definition(definition, access, table.headers)
    visible = set(table.headers)
    view = replace(
        view,
        columns=tuple(column for column in view.columns if column.name in visible),
        metrics=frozenset(view.metrics & visible - blocked),
        dimensions=frozenset(view.dimensions & visible),
        definition=definition,
        sources=tuple({**source, **access.reference()} for source in view.sources),
    )
    limited_profile = (
        profile_for(table, str(full_profile.get("algorithm", CURRENT_ALGORITHM)))
        if access.restricted
        else full_profile
    )
    return table, view, limited_profile, definition
