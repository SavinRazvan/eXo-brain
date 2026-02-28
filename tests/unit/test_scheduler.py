"""
File: test_scheduler.py
Path: tests/unit/test_scheduler.py
Role: Unit tests for scheduler retries, failure propagation, and concurrency bounds.
Used By:
 - pytest
Depends On:
 - src/core/scheduler.py
 - src/core/task_graph.py
 - src/core/worker_pool.py
 - src/core/checkpoint_store.py
Notes:
 - Covers safety behavior for background runtime before host integration.
"""

from __future__ import annotations

import asyncio

from src.core.checkpoint_store import InMemoryCheckpointStore
from src.core.scheduler import TaskScheduler
from src.core.task_graph import TaskGraph, TaskNode, TaskStatus
from src.core.worker_pool import WorkerPool


def test_scheduler_runs_dependency_chain() -> None:
    async def fetch(_: dict) -> dict:
        return {"value": 2}

    async def process(payload: dict) -> dict:
        value = payload["dependencies"]["fetch"]["value"]
        return {"value": value * 3}

    graph = TaskGraph(
        [
            TaskNode(node_id="fetch", handler=fetch),
            TaskNode(node_id="process", handler=process, depends_on=["fetch"]),
        ]
    )
    scheduler = TaskScheduler(worker_pool=WorkerPool(max_concurrency=2), checkpoint_store=InMemoryCheckpointStore())
    result = asyncio.run(scheduler.execute(job_id="job_dep_chain", graph=graph))

    assert result.outcomes["fetch"].status == TaskStatus.COMPLETED
    assert result.outcomes["process"].status == TaskStatus.COMPLETED
    assert result.outcomes["process"].output["value"] == 6


def test_scheduler_retries_and_marks_downstream_cancelled() -> None:
    calls = {"boom": 0}

    async def boom(_: dict) -> dict:
        calls["boom"] += 1
        raise RuntimeError("failure")

    async def dependent(_: dict) -> dict:
        return {"ok": True}

    graph = TaskGraph(
        [
            TaskNode(node_id="boom", handler=boom, retry_limit=1),
            TaskNode(node_id="dependent", handler=dependent, depends_on=["boom"]),
        ]
    )
    scheduler = TaskScheduler(worker_pool=WorkerPool(max_concurrency=2), checkpoint_store=InMemoryCheckpointStore())
    result = asyncio.run(scheduler.execute(job_id="job_retry", graph=graph))

    assert calls["boom"] == 2
    assert result.outcomes["boom"].status == TaskStatus.FAILED
    assert result.outcomes["boom"].reason_code == "TASK_EXECUTION_ERROR"
    assert result.outcomes["dependent"].status == TaskStatus.CANCELLED
    assert result.outcomes["dependent"].reason_code == "UPSTREAM_FAILED"


def test_scheduler_respects_worker_pool_concurrency_bound() -> None:
    active = 0
    max_active = 0
    lock = asyncio.Lock()

    async def tracked(_: dict) -> dict:
        nonlocal active, max_active
        async with lock:
            active += 1
            max_active = max(max_active, active)
        await asyncio.sleep(0.03)
        async with lock:
            active -= 1
        return {"ok": True}

    graph = TaskGraph(
        [TaskNode(node_id=f"n{i}", handler=tracked) for i in range(5)]
    )
    scheduler = TaskScheduler(worker_pool=WorkerPool(max_concurrency=2), checkpoint_store=InMemoryCheckpointStore())
    result = asyncio.run(scheduler.execute(job_id="job_concurrency", graph=graph))

    assert all(outcome.status == TaskStatus.COMPLETED for outcome in result.outcomes.values())
    assert max_active <= 2
