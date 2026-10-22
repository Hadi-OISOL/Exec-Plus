"""Use case: Isolates bounded allocation search from business rules.

What it does: Accepts exact integer problems and returns typed, independently checked outcomes.
"""

from typing import Protocol

from execplus.domain.large_allocation import IntegerAllocation, SolverOutcome
from execplus.domain.scheduled_allocation import ScheduledInteger, ScheduleOutcome


class AllocationSolver(Protocol):
    async def solve(self, problem: IntegerAllocation) -> SolverOutcome: ...

    async def solve_schedule(self, problem: ScheduledInteger) -> ScheduleOutcome: ...
