"""Use case: Retains private, reproducible multi-company consolidation worksheets.

What it does: Records explicit source selections, immutable evidence and exact
results without granting access through organization ownership.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ConsolidationRun:
    id: UUID
    organization_id: UUID
    owner_id: UUID
    name: str
    request: dict[str, Any]
    evidence: dict[str, Any]
    result: dict[str, Any]
    created_at: datetime
