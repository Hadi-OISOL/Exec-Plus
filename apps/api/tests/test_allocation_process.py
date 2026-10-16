"""Use case: Verifies actual process lifetime and output boundaries for allocation.

What it does: Exercises hard deadlines, repeated cancellation, admission and secret-free startup.
"""

import asyncio
import os
import textwrap
from pathlib import Path

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.infrastructure.allocation.cp_sat import CpSatAllocationSolver
from execplus.infrastructure.allocation.cp_sat_worker import bounded_input
from test_large_allocation import ROWS, prepare_allocation, request


def fake_worker(tmp_path: Path, body: str):
    worker = tmp_path / "worker.py"
    worker.write_text(textwrap.dedent(body))
    solver = CpSatAllocationSolver()
    solver._worker = worker
    return solver


async def started(pid_file):
    for _ in range(200):
        if pid_file.exists():
            return int(pid_file.read_text())
        await asyncio.sleep(0.01)
    raise AssertionError("worker never started")


def gone(pid):
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.asyncio
async def test_hard_deadline_kills_and_reaps_worker_before_return(tmp_path):
    pid_file = tmp_path / "pid"
    solver = fake_worker(
        tmp_path,
        "import os,time\nfrom pathlib import Path\n"
        f"Path({str(pid_file)!r}).write_text(str(os.getpid()))\ntime.sleep(10)\n",
    )
    solver._wall_seconds = 0.2
    result = await solver.solve(prepare_allocation(request(), ROWS).integers)
    assert result.status == "UNKNOWN" and result.termination == "hard_wall_limit"
    gone(int(pid_file.read_text()))
    assert solver._slots._value == 2


@pytest.mark.asyncio
async def test_cancellation_reaps_worker_and_keeps_slot_until_drained(tmp_path):
    pid_file = tmp_path / "pid"
    solver = fake_worker(
        tmp_path,
        "import os,time\nfrom pathlib import Path\n"
        f"Path({str(pid_file)!r}).write_text(str(os.getpid()))\ntime.sleep(10)\n",
    )
    task = asyncio.create_task(solver.solve(prepare_allocation(request(), ROWS).integers))
    pid = await started(pid_file)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    gone(pid)
    assert solver._slots._value == 2


@pytest.mark.asyncio
async def test_concurrent_admission_is_bounded_without_spawning_third_worker(tmp_path):
    solver = fake_worker(tmp_path, "import time\ntime.sleep(10)\n")
    problem = prepare_allocation(request(), ROWS).integers
    tasks = [asyncio.create_task(solver.solve(problem)) for _ in range(2)]
    await asyncio.sleep(0.1)
    try:
        with pytest.raises(IngestionError) as error:
            await solver.solve(problem)
        assert error.value.code == "allocation_solver_busy"
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert solver._slots._value == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body", ["print('x'*40000)", "print('{}')", "raise RuntimeError('private-value')"]
)
async def test_oversized_malformed_and_failed_workers_return_content_free_errors(tmp_path, body):
    solver = fake_worker(tmp_path, body)
    with pytest.raises(IngestionError) as error:
        await solver.solve(prepare_allocation(request(), ROWS).integers)
    assert error.value.code == "allocation_solver_unavailable"
    assert "private-value" not in str(error.value)
    assert solver._slots._value == 2


@pytest.mark.asyncio
async def test_environment_secrets_are_not_forwarded_and_chunked_json_is_accepted(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("EXECPLUS_TEST_SECRET", "never-send-this")
    solver = fake_worker(
        tmp_path,
        """
        import json,os,sys,time
        assert 'EXECPLUS_TEST_SECRET' not in os.environ
        data=json.dumps(dict(status='UNKNOWN',quantities=None,objective=None,termination='solver_completed'))
        for part in (data[:8],data[8:]):
            sys.stdout.write(part);sys.stdout.flush();time.sleep(.02)
    """,
    )
    assert (await solver.solve(prepare_allocation(request(), ROWS).integers)).status == "UNKNOWN"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value", [("status", []), ("objective", True), ("objective", 2**53), ("termination", [])]
)
async def test_malformed_typed_solver_fields_are_content_free_failures(tmp_path, field, value):
    import json

    raw = dict(status="UNKNOWN", quantities=None, objective=None, termination="solver_completed")
    raw[field] = value
    solver = fake_worker(tmp_path, f"print({json.dumps(raw)!r})")
    with pytest.raises(IngestionError) as error:
        await solver.solve(prepare_allocation(request(), ROWS).integers)
    assert error.value.code == "allocation_solver_unavailable"


def test_worker_refuses_unbounded_or_code_like_input():
    for value in [{"code": "print(1)"}, {"benefits": []}, None]:
        with pytest.raises((ValueError, TypeError)):
            bounded_input(value)
