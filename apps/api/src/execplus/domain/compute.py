"""Use case: Describes supported analytical execution and its resource limits.

What it does: Defines provider-neutral capabilities and validated budgets for bounded queries.
"""

import math
from dataclasses import dataclass
from enum import Enum


class ComputeOperation(str, Enum):
    SNAPSHOT_QUERY = "snapshot_query"
    DECLARED_JOIN = "declared_join"


@dataclass(frozen=True, slots=True)
class QueryBudget:
    timeout_seconds: float = 15.0
    memory_limit_mb: int = 256
    threads: int = 1
    input_rows: int = 200_000
    input_cells: int = 2_000_000
    result_rows: int = 100_000

    def __post_init__(self) -> None:
        if not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 300:
            raise ValueError("Query time budget must be finite and at most 300 seconds")
        bounds = (
            (self.memory_limit_mb, 16_384),
            (self.threads, 8),
            (self.input_rows, 200_000),
            (self.input_cells, 2_000_000),
            (self.result_rows, 100_000),
        )
        if any(type(value) is not int or not 1 <= value <= maximum for value, maximum in bounds):
            raise ValueError("Query budgets must use positive integers within supported limits")


@dataclass(frozen=True, slots=True)
class ComputeCapabilities:
    engine_id: str
    operations: frozenset[ComputeOperation]
    budget: QueryBudget
