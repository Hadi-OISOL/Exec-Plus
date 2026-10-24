"""Use case: Executes trusted CP-SAT search with hard process and concurrency bounds.

What it does: Strips the environment, kills/drains on timeout or cancellation and validates output.
"""

import asyncio
import json
import os
import signal
import sys
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path

from execplus.domain.ingestion import IngestionError
from execplus.domain.large_allocation import IntegerAllocation, SolverOutcome
from execplus.domain.scheduled_allocation import ScheduledInteger, ScheduleOutcome


class CpSatAllocationSolver:
    def __init__(self) -> None:
        self._slots = asyncio.Semaphore(2)
        self._worker = Path(__file__).with_name("cp_sat_worker.py")
        self._executable = sys.executable
        self._wall_seconds = 4.0

    async def solve(self, problem: IntegerAllocation) -> SolverOutcome:
        output = await self._execute(asdict(problem))
        if output is None:
            return SolverOutcome("UNKNOWN", None, None, "hard_wall_limit")
        return self._parse(output, set())[0]

    async def solve_schedule(self, problem: ScheduledInteger) -> ScheduleOutcome:
        output = await self._execute(asdict(problem))
        if output is None:
            return ScheduleOutcome(SolverOutcome("UNKNOWN", None, None, "hard_wall_limit"), None)
        outcome, raw = self._parse(output, {"periods"})
        periods = raw["periods"]
        if (periods is None) != (outcome.quantities is None) or (
            periods is not None
            and (
                not isinstance(periods, list)
                or len(periods) != len(problem.period_costs)
                or any(p is not None and (type(p) is not int or not 0 <= p < 12) for p in periods)
            )
        ):
            raise IngestionError(
                "allocation_solver_unavailable",
                "The solver returned invalid evidence. No recommendation was saved.",
                503,
            )
        return ScheduleOutcome(outcome, tuple(periods) if periods is not None else None)

    async def _execute(self, value: dict[str, object]) -> bytes | None:
        payload = json.dumps(value, separators=(",", ":")).encode()
        if len(payload) > 100_000:
            raise IngestionError(
                "allocation_solver_input", "The bounded allocation input is too large.", 422
            )
        try:
            await asyncio.wait_for(self._slots.acquire(), 0.25)
        except asyncio.TimeoutError:
            raise IngestionError(
                "allocation_solver_busy",
                "Two allocations are already running. Try again shortly.",
                503,
            ) from None
        try:
            spawning = asyncio.create_task(
                asyncio.create_subprocess_exec(
                    self._executable,
                    "-I",
                    str(self._worker),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    start_new_session=True,
                    cwd="/",
                    env={"LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"},
                )
            )
            try:
                process = await asyncio.shield(spawning)
            except asyncio.CancelledError:
                while not spawning.done():
                    with suppress(asyncio.CancelledError):
                        await asyncio.shield(spawning)
                process = spawning.result()
                task = asyncio.create_task(self._exchange(process, payload))
                await self._stop(process, task)
                raise
            task = asyncio.create_task(self._exchange(process, payload))
            try:
                output = await asyncio.wait_for(asyncio.shield(task), self._wall_seconds)
            except asyncio.TimeoutError:
                await self._stop(process, task)
                return None
            except BaseException:
                await self._stop(process, task)
                raise
            if process.returncode != 0:
                raise IngestionError(
                    "allocation_solver_unavailable",
                    "The bounded solver could not finish safely. No recommendation was saved.",
                    503,
                )
        finally:
            self._slots.release()
        return output

    def _parse(self, output: bytes, extra: set[str]) -> tuple[SolverOutcome, dict[str, object]]:
        try:
            raw = json.loads(output)
            if not isinstance(raw, dict) or set(raw) != {
                "status",
                "quantities",
                "objective",
                "termination",
                *extra,
            }:
                raise ValueError("Invalid solver output")
            values = raw["quantities"]
            if (
                not isinstance(raw["status"], str)
                or raw["status"] not in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"}
                or raw["termination"] != "solver_completed"
                or (
                    raw["objective"] is not None
                    and (type(raw["objective"]) is not int or not 0 <= raw["objective"] < 2**53)
                )
            ):
                raise ValueError("Invalid solver status or objective")
            if values is not None and (
                not isinstance(values, list)
                or len(values) > 50
                or any(type(x) is not int or not 0 <= x <= 1_000_000 for x in values)
            ):
                raise ValueError("Invalid solver quantities")
            return SolverOutcome(
                raw["status"],
                tuple(values) if values is not None else None,
                raw["objective"],
                raw["termination"],
            ), raw
        except (ValueError, KeyError, TypeError):
            raise IngestionError(
                "allocation_solver_unavailable",
                "The solver returned invalid evidence. No recommendation was saved.",
                503,
            ) from None

    async def _exchange(self, process: asyncio.subprocess.Process, payload: bytes) -> bytes:
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(payload)
        await process.stdin.drain()
        process.stdin.close()
        output = bytearray()
        while True:
            chunk = await process.stdout.read(4096)
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > 32_768:
                raise IngestionError(
                    "allocation_solver_unavailable",
                    "The solver output exceeded its safe limit.",
                    503,
                )
        await process.wait()
        return bytes(output)

    async def _stop(self, process: asyncio.subprocess.Process, task: asyncio.Task[bytes]) -> None:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)

        async def drain() -> None:
            with suppress(Exception, asyncio.CancelledError):
                await task
            await process.wait()

        pending = asyncio.create_task(drain())
        while not pending.done():
            with suppress(asyncio.CancelledError):
                await asyncio.shield(pending)
        pending.result()
