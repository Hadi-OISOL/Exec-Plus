"""Use case: Separates internal incident storage from HTTP and SQL implementations.

What it does: Defines bounded collection and staff-audited incident transactions.
"""

from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from execplus.domain.incidents import Incident, IncidentOccurrence
from execplus.domain.operations import StaffAudit, StaffGrant


class IncidentRepository(Protocol):
    def staff_grant(self, user_id: UUID, *, lock: bool = False) -> StaffGrant | None: ...
    def add_staff_audit(self, value: StaffAudit) -> None: ...
    def list_incidents(self, status: str, limit: int) -> tuple[Incident, ...]: ...
    def incident(self, incident_id: UUID) -> Incident: ...
    def update_incident(self, value: Incident, expected_version: int) -> None: ...


class IncidentStore(Protocol):
    def transaction(self) -> AbstractContextManager[IncidentRepository]: ...
    def collect(self, queued: tuple[IncidentOccurrence, ...], now: datetime) -> dict[str, int]: ...
