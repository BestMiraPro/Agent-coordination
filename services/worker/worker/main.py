from __future__ import annotations

import asyncio


async def run_worker() -> None:
    """Worker entrypoint.

    Phase 1 will replace this placeholder with PostgreSQL-backed durable-job polling.
    """
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run_worker())
