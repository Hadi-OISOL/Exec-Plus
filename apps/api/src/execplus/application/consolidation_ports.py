"""Use case: Separates private consolidation persistence from application logic.

What it does: Adds immutable run storage to existing authorized workspace lookups.
"""

from contextlib import AbstractContextManager
from typing import Protocol
from uuid import UUID

from execplus.application.ports import WorkspaceRepository
from execplus.domain.consolidation_records import ConsolidationRun


class ConsolidationRepository(WorkspaceRepository, Protocol):
    def lock_consolidation_owner(self, oid: UUID, owner_id: UUID) -> None: ...
    def consolidation_runs(self, oid: UUID, owner_id: UUID) -> tuple[ConsolidationRun, ...]: ...
    def consolidation_run(self, oid: UUID, rid: UUID, owner_id: UUID) -> ConsolidationRun: ...
    def add_consolidation_run(self, value: ConsolidationRun) -> None: ...


class ConsolidationStore(Protocol):
    def transaction(self) -> AbstractContextManager[ConsolidationRepository]: ...
