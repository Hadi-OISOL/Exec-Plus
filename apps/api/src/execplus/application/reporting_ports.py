"""Use case: Keeps aggregate product reporting independent of database SDKs.

What it does: Declares bounded usage projections over existing operational records.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from execplus.domain.product_usage import UsageFacts


class ReportingRepository(Protocol):
    def product_usage_facts(
        self, workspace_id: UUID, start: datetime, now: datetime
    ) -> UsageFacts: ...

    def activation_overview(self, workspace_id: UUID, *, manager: bool) -> dict[str, object]: ...

    def usage_totals(self, workspace_id: UUID, now: datetime) -> dict[str, int]: ...
