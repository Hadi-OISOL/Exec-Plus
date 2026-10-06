"""Use case: Retains private forecasts and later actual comparisons as immutable evidence.

What it does: Defines source-bound records independently of persistence and forecast methods.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ForecastRun:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    owner_id: UUID
    name: str
    upload_id: UUID
    revision_id: UUID
    understanding_id: UUID
    method: str
    method_version: str
    request: dict[str, Any]
    evidence: dict[str, Any]
    result: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class ForecastComparison:
    id: UUID
    workspace_id: UUID
    dataset_id: UUID
    owner_id: UUID
    forecast_id: UUID
    upload_id: UUID
    revision_id: UUID
    understanding_id: UUID
    evidence: dict[str, Any]
    result: dict[str, Any]
    created_at: datetime
