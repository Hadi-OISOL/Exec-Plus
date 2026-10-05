"""Use case: Runs the durable conversation worker with bounded polling and shutdown.

What it does: Stops claiming work on a shutdown signal and waits for cancellation cleanup.
"""

import asyncio
from contextlib import suppress

from execplus.application.services.jobs import JobService


async def work(
    jobs: JobService,
    stop: asyncio.Event,
    *,
    watch: bool = False,
    concurrency: int = 4,
    poll_seconds: float = 0.5,
) -> dict[str, int]:
    if not 0.1 <= poll_seconds <= 10 or not 1 <= concurrency <= 8:
        raise ValueError("Use concurrency 1-8 and polling 0.1-10 seconds")
    processed = 0
    while not stop.is_set():
        task = asyncio.create_task(jobs.process(concurrency=concurrency))
        stopped = asyncio.create_task(stop.wait())
        try:
            await asyncio.wait({task, stopped}, return_when=asyncio.FIRST_COMPLETED)
            if stop.is_set():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                break
            processed += (await task)["processed"]
        finally:
            stopped.cancel()
            with suppress(asyncio.CancelledError):
                await stopped
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        if not watch:
            break
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop.wait(), poll_seconds)
    return {"processed": processed}
