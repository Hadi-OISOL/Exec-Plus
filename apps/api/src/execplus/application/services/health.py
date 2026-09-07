"""Use case: Evaluates whether the API can serve traffic.

What it does: Runs readiness probes and returns a deployment-facing status.
"""

import asyncio

from execplus.application.contracts import ComponentStatus
from execplus.application.ports import ReadinessProbe


class HealthService:
    def __init__(self, probes: tuple[ReadinessProbe, ...] = ()) -> None:
        self._probes = probes

    async def readiness(self) -> tuple[bool, tuple[ComponentStatus, ...]]:
        if not self._probes:
            return True, ()
        statuses = tuple(await asyncio.gather(*(self._check(probe) for probe in self._probes)))
        return all(status.healthy for status in statuses), statuses

    async def _check(self, probe: ReadinessProbe) -> ComponentStatus:
        try:
            return await asyncio.wait_for(probe.check(), timeout=5)
        except Exception:
            return ComponentStatus(probe.name, False, "unavailable")
