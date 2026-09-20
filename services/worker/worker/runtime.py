from __future__ import annotations

import asyncio
from typing import Protocol

from packages.core.domain.models import Job, JobStatus
from packages.persistence.jobs import DurableJobQueue


class JobHandler(Protocol):
    async def handle(self, job: Job) -> None: ...
    async def handle_terminal_failure(self, job: Job, error: Exception) -> None: ...


async def run_once(
    queue: DurableJobQueue,
    handler: JobHandler,
    *,
    failure_retry_delay_seconds: int | None = None,
) -> bool:
    job = queue.claim_next()
    if job is None:
        return False

    try:
        await handler.handle(job)
    except Exception as exc:
        failed = queue.fail(
            job.id,
            error=f"{type(exc).__name__}: {exc}",
            retry_delay=failure_retry_delay_seconds,
        )
        if failed.status == JobStatus.FAILED:
            await handler.handle_terminal_failure(job, exc)
    else:
        if not queue.complete(job.id):
            raise RuntimeError(f"Could not complete claimed job {job.id}")

    return True


async def run_worker(
    queue: DurableJobQueue,
    handler: JobHandler,
    poll_interval_seconds: float = 0.5,
) -> None:
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")

    while True:
        processed = await run_once(queue, handler)
        if not processed:
            await asyncio.sleep(poll_interval_seconds)
