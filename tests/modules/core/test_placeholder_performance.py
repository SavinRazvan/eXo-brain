"""
File: test_placeholder_performance.py
Path: tests/modules/core/test_placeholder_performance.py
Role: Baseline performance sanity tests for bounded worker pool behavior.
Used By:
 - pytest
Depends On:
 - src/core/worker_pool.py
Notes:
 - Keeps a lightweight guard for max concurrency configuration.
"""

import asyncio

from src.core.worker_pool import WorkerPool


def test_worker_pool_rejects_invalid_concurrency_configuration() -> None:
    try:
        WorkerPool(max_concurrency=0)
        assert False, "Expected ValueError for invalid concurrency"
    except ValueError as exc:
        assert "max_concurrency" in str(exc)


def test_worker_pool_runs_async_task() -> None:
    async def scenario() -> int:
        pool = WorkerPool(max_concurrency=1)

        async def work() -> int:
            await asyncio.sleep(0)
            return 7

        return await pool.run(work)

    assert asyncio.run(scenario()) == 7
