"""Use case: Verifies durable cancellation waits for bounded synchronous source reads.

What it does: Waits for source-reader cleanup before terminal publication and worker disposal.
"""

import asyncio
from threading import Event

import pytest

from test_conversation_jobs import job_path, prepared, submit


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["cancel", "shutdown"])
async def test_cancellation_joins_the_router_reader_before_terminal_cleanup(
    integration, monkeypatch, action
):
    env = integration
    owner, _, _, path, model = prepared(env)
    job = submit(env, owner, path)
    entered, release, finished = Event(), Event(), Event()
    original = env.runtime.analytics.describe

    def reading(*args, **kwargs):
        entered.set()
        try:
            assert release.wait(10)
            return original(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(env.runtime.analytics, "describe", reading)
    worker = asyncio.create_task(env.runtime.jobs.process(concurrency=1))
    assert await asyncio.to_thread(entered.wait, 10)
    try:
        if action == "cancel":
            response = env.client.post(job_path(job) + "/cancel", headers=owner)
            assert response.json()["status"] == "cancelling"
        else:
            worker.cancel()
        await asyncio.sleep(0.4)
        assert not finished.is_set()
        assert not worker.done()
        assert env.client.get(job_path(job), headers=owner).json()["status"] in {
            "running",
            "cancelling",
        }
    finally:
        release.set()
    if action == "shutdown":
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(worker, 10)
    else:
        await asyncio.wait_for(worker, 10)
    assert finished.is_set()
    assert env.client.get(job_path(job), headers=owner).json()["status"] == (
        "cancelled" if action == "cancel" else "failed"
    )
    assert env.client.get(job_path(job) + "/result", headers=owner).json()["answer"] is None
    assert model.requests == []
