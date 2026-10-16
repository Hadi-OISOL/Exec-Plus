"""Use case: Separates durable model-usage accounting from database details.

What it does: Requires workspace serialization, explicit authorization and immutable
event publication for reservations and reconciliation.
"""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from execplus.domain.usage_metering import UsageAttempt, UsagePolicy, UsagePrice, UsageTotals


class UsageRepository(Protocol):
    def lock_workspace(self, workspace_id: UUID) -> None: ...

    def require_member(self, workspace_id: UUID, actor_id: UUID) -> None: ...

    def require_owner_full(self, workspace_id: UUID, actor_id: UUID) -> None: ...

    def require_operator(self, actor_id: UUID) -> None: ...

    def require_workspace_full(self, workspace_id: UUID, actor_id: UUID) -> None: ...

    def pending(
        self, workspace_id: UUID, limit: int, older_than: datetime | None = None
    ) -> tuple[UsageAttempt, ...]: ...

    def policy(self, workspace_id: UUID) -> UsagePolicy | None: ...

    def price(self, provider: str, model: str, at: datetime) -> UsagePrice | None: ...

    def attempt(self, workspace_id: UUID, attempt_id: UUID) -> UsageAttempt | None: ...

    def totals(self, workspace_id: UUID, policy: UsagePolicy | None) -> UsageTotals: ...

    def write_attempt(
        self,
        previous: UsageAttempt | None,
        value: UsageAttempt,
        event: str,
        actor_id: UUID,
        at: datetime,
    ) -> None: ...

    def add_policy(self, policy: UsagePolicy) -> None: ...

    def add_price(self, price: UsagePrice) -> None: ...

    def summary(
        self, workspace_id: UUID, starts_at: datetime, ends_at: datetime
    ) -> dict[str, Any]: ...
